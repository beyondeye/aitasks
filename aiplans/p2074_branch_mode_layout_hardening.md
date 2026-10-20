---
Task: t2074_branch_mode_layout_hardening.md
Base branch: main
Output branch: main
---

# t2074 (rescoped): branch-mode layout hardening, keeping legacy mode

## Context

t2074 was originally planned and split into 14 children to **remove** legacy
repository mode. In that mode task data lives on the code branch and `task_git`
runs plain `git`. On 2026-10-20 the user **reversed** that decision: legacy mode
stays supported. t2074 is rescoped to the **branch-mode** defects the audit
found, which exist whether or not legacy mode stays:

- **Layout detection is too trusting.** Detection rungs 1–3
  (`lib/task_utils.sh:81-121`) accept any `.aitask-data/.git`: a stale `gitdir`
  file, an unrelated repo or clone, or a worktree on the wrong branch. When
  `.aitask-data` is gone but the dangling data links remain, rung 4 silently
  falls back to plain git on the code branch.
- **The writer guard is bypassed before the layout is checked.**
  `assert_task_data_writable` (`:488`) and `assert_data_worktree_clean`
  (`:435`) return on `AIT_GIT_SKIP_STATE_CHECK=1` before any layout check, and
  `aitask_update.sh --batch` without `--commit` writes without ever reaching
  git.
- **Setup cannot see or repair a broken layout.** It reports "already
  configured" whenever `.aitask-data/.git` exists (`aitask_setup.sh:1571`).
  `ait_ensure_data_symlinks` keeps a link that resolves to the wrong existing
  dir.
- **The board can run git against the wrong repo.**
  `board_task_manager._task_git_cmd` (`:66`) probes the cwd-relative
  `./.aitask-data/.git` and falls back to `["git"]`, so from a non-root cwd in
  branch mode it targets the code repo.
- **Mixed or misdirected primaries go unnoticed.** A real `aitasks/` beside a
  valid data worktree, or a link to another dir, makes writers write to the
  wrong place without any error.

**Legacy behaviour does not change.** These all stay as they are: the setup
opt-out prompt, the legacy fallbacks, the `LEGACY_MODE` and `LEGACY_MODE_SKIP`
tokens, plain-git passthrough, the legacy test fixtures and the legacy docs.

**User-directed structure (2026-10-20): five children.**
- t2074_1: classification.
- t2074_3: setup and safe repair.
- t2074_9: fixtures + shell enforcement + Python/board enforcement, absorbing
  t2074_2 and t2074_10.
- t2074_12: docs.
- t2074_14: manual verification.

Classification (t2074_1) and repair (t2074_3) stay independently actionable.

## Contract

### C1a `ait_data_repo_state`

Lives in `lib/data_symlinks.sh`. It prints `<state>[:<reason>]`, **always
returns 0 and never dies**, including under `set -euo pipefail`, inside `$( )`
and inside `local x="$( )"`.

**Resolution order:**
1. The cwd is inside the data worktree itself. This preserves T13c of
   `tests/test_task_git.sh`.
2. A local marker: `./.aitask-data`, then `<toplevel>/.aitask-data`. A usable
   separate-git-dir primary resolves here without `ait_main_worktree_root`.
3. The main checkout's marker, via `ait_main_worktree_root`, consulted only if
   local resolution fails. This preserves T13d, the unlinked crew worktree.
   - If it returns 2 and `ait_linked_worktree_roots` proves this checkout is
     not linked, fall through to the no-marker table.
   - Otherwise the state is `indeterminate:topology`.
4. Otherwise apply the no-marker precedence table below. `not_a_repo` applies
   outside any work tree.

**Validation of a resolved `<data>`.** The first failure wins; if none fails,
the state is `branch`.
1. `broken:stale_marker`: `<data>` is not a live worktree toplevel. This
   covers a stale `gitdir:` file, an empty `.git`, a pruned admin dir, and a
   `.aitask-data` that exists without `.git`.
2. `broken:foreign_repo`: `<data>`'s canonical `git-common-dir` differs from
   this checkout's. This covers an unrelated repo, a clone, or another repo's
   worktree.
3. `broken:wrong_branch`: HEAD is not `refs/heads/aitask-data`.
   - **Exception: in-progress operations with a detached HEAD are valid but
     wedged.** The branch is then read from the operation's own record:
     `rebase-merge/head-name`, `rebase-apply/head-name`, or `BISECT_START` for
     bisect. Each must name `aitask-data`.
   - The existing wedge machinery (`AIT_GIT_INPROGRESS_STATES`, which includes
     `BISECT_LOG`) still reports these states, so `./ait git rebase --abort`
     and `./ait git bisect reset` stay reachable.
   - Any other detached HEAD (e.g. `checkout <sha>`, or a bisect started from
     another branch) is `wrong_branch`, as is any other branch.
   - MERGE, cherry-pick and revert keep HEAD on the branch.

**No-marker precedence table** (no `.aitask-data/.git`). Each of `aitasks` and
`aiplans` is typed as exactly one of:
- `data_link`: a symlink whose raw target is the `AIT_DATA_LINKS` literal from
  `ait_data_link_target` (`.aitask-data/aitasks` or `.aitask-data/aiplans`).
- `real_dir`
- `other_link`
- `absent`

The first matching row wins:

| # | Evidence | State |
|---|---|---|
| 1 | **Either** path is `data_link`, whatever the other path is. This includes a real `aitasks/` beside a dangling `aiplans -> .aitask-data/aiplans`. | `broken:missing_storage` (conflicting live evidence is refused, never routed to plain git) |
| 2 | No `data_link`, and at least one `real_dir` | `legacy` (supported). A stale `.aitask-data` registration and a leftover `aitask-data` ref are ignored as harmless leftovers. |
| 3 | No `data_link`, no `real_dir`, and a registered (possibly prunable) worktree record exists at `<root>/.aitask-data` | `broken:missing_storage` |
| 4 | Only `other_link` and/or `absent` | Unchanged from today: `legacy` if `aitasks` resolves to a dir, otherwise `uninitialized` |

A leftover `aitask-data` branch ref is **never** evidence for any row.

### C1b `ait_data_paths_state`

Applies in branch mode only. It compares canonical `$PWD/$TASK_DIR` and
`$PWD/$PLAN_DIR` against `<data>/aitasks` and `<data>/aiplans`. States:
- `ready`: matches inside the data worktree, in the primary, or in a
  `--link-worktree`'d worktree.
- `unlinked`: the paths are absent in a linked worktree.
- `misdirected`: a path resolves somewhere else, including a `TASK_DIR`
  override outside `<data>`.
- `dangling`
- `mixed`: a real dir exists beside a valid data worktree.

In legacy mode it reports `legacy`, which is acceptable.

### Enforcement table (single source for wiring and tests)

Every refusal names its recovery.

| Situation | Git routing (`task_git`, sync, push, `./ait git`) | Named readers / all writers |
|---|---|---|
| C1a `branch`, C1b `ready` | runs | runs |
| C1a `branch`, C1b `unlinked` | runs (T13d preserved) | **refuse** → `--link-worktree` |
| C1a `branch`, C1b `misdirected` / `dangling` / `mixed` | runs | **refuse** → `ait setup` repair (manual steps for `mixed`) |
| C1a `broken:*` (incl. `missing_storage`) or `indeterminate` | **refuse** | **refuse** |
| C1a `legacy` / `uninitialized` | **unchanged** (plain git) | **unchanged** |

**Wiring:**
- `_ait_detect_data_worktree`: rungs 1–3 validate the marker they find. Rung 4
  classifies first: `broken:missing_storage` dies, and only `legacy` and
  `uninitialized` still answer `"."`. This is the git class.
- `assert_task_data_writable` checks the layout first. `AIT_GIT_SKIP_STATE_CHECK`
  then skips only the wedge check. This is the writer class. Every writer
  (update, create, archive, fold, note, gate, plan_externalize, board column,
  the atomic-write callers) must reach the guard before its first write, with
  or without `--commit`.
- **Readers have a narrowed, named contract.** Refusal is guaranteed only at
  three entry points: `aitask_ls.sh`, `aitask_query_files.sh` (every
  subcommand), and board startup. Inside each script the order is:
  1. `cross_repo_reexec_or_continue` (`aitask_ls.sh:20`,
     `aitask_query_files.sh:639`). A `--project` call re-execs the destination,
     which validates its own layout; the source is never validated for a
     redirected call.
  2. Argument parsing and the help/usage exits (`aitask_ls.sh:206-222`,
     `aitask_query_files.sh:44/647-653/713`). These work on any layout.
  3. `ait_require_data_paths`, immediately before the first task-data read.

  Other readers (stats, codebrowser, explain_context, monitor, trails) are out
  of scope by design. They are read-only, cannot mutate data, and on a damaged
  layout they show whatever is on disk. The docs state this limitation.
- There is no dispatcher gate.
- **errexit audit.** Cover every new die path: each `local x="$(…)"` call
  site of the detection accessors and each `if`/`||`-guarded one. Each site
  gets a test.

### C4 Setup repair (branch mode only; the legacy decline prompt and fallbacks are untouched)

- Setup reports "configured" only for C1a `branch` **and** C1b `ready`.
- When C1a is `branch` but C1b is not `ready`, dispatch on C1b:
  - `dangling`, `misdirected` or absent links get the link repair.
  - `mixed`, or a real file at a link path, is refused.
  - `unlinked` gets `--link-worktree` guidance.
- When C1a ≠ `branch`, dispatch on C1a.
- **Link repair** uses a new shared `ait_repair_data_links <root> <data>
  [--with-data-link]`, extracted from the two-phase `ait_link_worktree_data`
  (`lib/data_symlinks.sh:190`). Do not reuse `ait_ensure_data_symlinks`, which
  keeps resolving links.
  - Preflight: report every real file or dir conflict and change nothing.
  - Apply: repoint mismatched links (raw literal for `aitasks`/`aiplans`,
    canonical target for `.aitask-data`), create absent ones, warn with the old
    target, and never touch the old target's contents.
  - `--link-worktree` keeps its `LINKED` / `ALREADY_LINKED` / exit-2 contract.
- These states are refused with move-aside steps that never delete:
  `foreign_repo`, `wrong_branch`, `mixed`, unique files in a stale dir, and
  `indeterminate`.
- `stale_marker` and `missing_storage` go through the **bounded worktree
  repair** below.

**Bounded worktree repair. Never `git worktree prune`.** Prune is
repository-wide: it deletes the admin dir, staged index included, of every
worktree whose path is missing, even one that was merely moved.

1. **Identify the target exactly.** Select the record in `git worktree list
   --porcelain` whose path canonicalizes to `<root>/.aitask-data`, and
   cross-check that `<common>/worktrees/<name>/gitdir` points at
   `<root>/.aitask-data/.git`. Then:
   - **(A) No registration, and `aitask-data` is not checked out anywhere.**
     There is no old index to protect.
     - `<root>/.aitask-data` must be absent or an empty dir; anything else is
       refused.
     - `refs/heads/aitask-data` must exist locally, or be fetched from
       `origin` the way `setup_data_branch` Step 1 does it (exact ref probe,
       git's error reported).
     - Then run an **ordinary** `git worktree add` (no `--force`, setup's
       Step 2) and repair the links.
     - If no branch exists anywhere, refuse with restore instructions.
   - **(B) Exactly one registration**, possibly with a missing or unreadable
     admin dir, `index` or `HEAD`: go to step 2.
   - **Otherwise refuse** and change nothing: multiple records, a `locked`
     record, or `aitask-data` checked out by a *different* registration.
2. **Target-preservation preflight (case B only; read-only).** A forced re-add
   reuses the admin dir and replaces its `index`. Proceed only when all three
   hold:
   - `GIT_INDEX_FILE=<admin>/index git --git-dir=<common> diff-index --cached
     --quiet refs/heads/aitask-data` exits 0. A missing or unreadable index
     counts as a failure.
   - `_ait_inprogress_state_at <admin>` is empty.
   - `<admin>/HEAD` is `ref: refs/heads/aitask-data`.

   Otherwise refuse, change nothing, and print instructions in this order:
   - restore the moved dir, or run `git worktree repair <moved path>`;
   - inspect the staged state with
     `GIT_INDEX_FILE=<admin>/index git diff --cached aitask-data`;
   - only after saving it, remove the registration by hand.

   No backup mechanism is added.

   Because a moved-aside copy would still point at the reused admin dir,
   re-adding for `missing_storage` needs **interactive confirmation**: "if you
   moved `.aitask-data`, answer no and restore it instead". A non-interactive
   run refuses.
3. **Re-register only that path** with `git worktree add --force
   <root>/.aitask-data aitask-data`. Pass a single `--force`, never two, so a
   lock is never overridden. A dir that was moved back is re-linked with `git
   worktree repair <root>/.aitask-data`.
4. **Pin git's behaviour.** Record a probe table on the installed git: what
   `add --force` does to the same path's old admin dir, and whether `repair`
   touches other records. Pin the result in a test. If git cannot replace
   exactly one registration, drop the automatic path and refuse with manual
   steps.

**Missing-storage recovery messages:**
- If a branch exists, the message says to run `ait setup`, which performs the
  bounded repair.
- If no branch exists, it says to restore from a backup or another clone.
- In the row-1 mixed case it refuses to touch the real dir and prints
  compare-and-merge steps.

## Children (five)

### t2074_1 `data_layout_classifier` (feature; no deps; additive only)

- Implement C1a and C1b in `lib/data_symlinks.sh`.
- Add `.aitask-scripts/aitask_data_layout.sh`, which prints `REPO:` and
  `PATHS:`. Follow `aidocs/framework/aitasks_extension_points.md` for the
  whitelists.
- Add `.aitask-scripts/lib/data_layout.py`. It never re-implements the checks;
  it calls the CLI and exposes two entry points with different freshness:
  - `snapshot()`: cached, for **display only** (status lines, startup
    banners).
  - `require_branch_ready()` / `require_repo_branch()`: **fresh on every
    call**. They run the CLI and raise on a refusing state. Long-lived Python
    processes (board, TUIs) must call these immediately before each git
    operation and each task-file write. A worktree that was valid at startup
    can switch branches or break later. The same `git -C` prefix would then
    silently target the new branch.

  The shell side may cache per process, because each framework command is a
  short-lived process. This is stated in the code comment, together with the
  rule that any long-running shell loop must re-validate before each mutation.
- Add `git-health` state reporting, behind the shared-file gate on
  `task_utils.sh`. If the gate is blocked, hand the item to t2074_9 with
  `./ait note`.

Tests: `tests/test_data_layout_classifier.sh` plus `tests/test_data_layout.py`.
- **One fixture per state and reason:**
  - `stale_marker`: stale gitdir file, empty `.git`, pruned admin dir, and
    `.aitask-data` without `.git`
  - `foreign_repo`: an unrelated repo, a clone, and another repo's worktree
  - `wrong_branch`: a detached `checkout <sha>`, and a bisect from another
    branch
  - links: dangling, misdirected (to an existing other dir), missing in a
    linked worktree, and a `TASK_DIR` override outside `<data>`
  - `mixed`
- **`missing_storage`, one fixture per precedence row:**
  - row 1: links dangle after `.aitask-data` is deleted
  - row 1 mixed: a real `aitasks/` plus a dangling `aiplans` link. This is
    refused, not legacy.
  - row 3: a prunable record remains and neither path exists
  - row 4: an `other_link` with no marker (behaviour unchanged)
- **Positive cases:**
  - mid-rebase, and mid-bisect with `BISECT_START`=`aitask-data`: `branch`
  - T13c: `branch` / `ready`
  - T13d: `branch` / `unlinked`
  - a `--link-worktree`'d worktree: `branch` / `ready`
  - a separate-git-dir primary: `branch`, with no main-root call
  - an unresolved linked checkout of that primary: `indeterminate:topology`,
    returned rather than died
  - a nested repo or submodule: its own state
- **Legacy controls:**
  - legacy root and subdir
  - a legacy repo with a leftover `aitask-data` ref
  - a legacy repo with a stale `.aitask-data` record plus a real `aitasks/`

  All of these stay `legacy`.
- **Also:** never-dies checks under errexit for every fixture, a
  filesystem-vs-git differential, and Python/shell parity.
- `test_task_git.sh` and `test_init_data.sh` stay green.

### t2074_3 `setup_layout_repair` (refactor; depends on t2074_1)

Covers everything under C4: the "configured" fix, C1b dispatch,
`ait_repair_data_links`, the refusals, the bounded worktree repair (no prune,
probe table, case A/B, preservation preflight, interactive confirmation /
non-interactive refusal) and the missing-storage messages.

Tests:
- **Same-fixture recovery:** refuse, then recover, then re-read both
  classifiers (`branch` / `ready`) for every C4 row.
- **"Configured":** a misdirected primary link is not "already configured" and
  gets repaired.
- **Misdirected link to an existing dir:** the final target is the literal, and
  the old dir's manifest is byte-identical.
- **Real-dir conflict:** refused, nothing changed.
- **Case (A) restoration:**
  - (i) local branch: ordinary add, `branch` / `ready`, tip unchanged
  - (ii) remote-only branch: fetched, then restored
  - (iii) no branch: refused, nothing changed
  - (iv) a non-empty `.aitask-data` without `.git`: refused
- **Case (B) target preservation:** the dir is moved aside, then one of
  (a) staged ≠ working ≠ tip, (b) `MERGE_HEAD` or `rebase-merge` in the admin
  dir, (c) detached HEAD. Each is refused.
  - The admin dir, index included, stays byte-identical.
  - The moved copy still re-links with `git worktree repair`.
  - Its staged change is still in `git diff --cached`.
  - Positive control: a clean index proceeds after confirmation, and
    non-interactive refuses.
  - Missing-metadata variants (`index` deleted, `HEAD` deleted): refused,
    unchanged.
  - Planted control: an unguarded `add --force` on (a) must fail the manifest
    comparison.
- **Two-worktree isolation:** the data dir is deleted, and an unrelated linked
  worktree is moved aside with staged changes.
  - After repair, the unrelated admin dir is byte-identical (every file,
    index included).
  - It is still listed, and still re-links.
  - Planted control: a plain `git worktree prune` must fail this comparison.
- **Legacy tests stay green:** `test_data_branch_setup.sh` (decline and
  fallbacks unchanged) and `test_init_data.sh` link cases.

### t2074_9 `branch_layout_enforcement` (refactor; depends on t2074_1, t2074_3, t2064)

This child absorbs t2074_2 and t2074_10. It runs as ordered steps.

**Step 0, shared-file gate.** For `.aitask-scripts/lib/task_utils.sh`,
`tests/test_task_push.sh` and `tests/test_task_git.sh`, check that `git diff
--quiet` passes and t2064's commit is in `git log`. Re-check right before the
first edit. Do non-overlapping work first; if the gate is still blocked, stop
and ask. Read the inbox notes (t2074_1 may hand over the `git-health` item).

**Step A, fixture preparation (from t2074_2).** Convert only the branch-mode
fixtures that strict validation rejects, i.e. non-registered or stubbed
layouts. Keep each fixture's signature.
- `tests/lib/board_fixture.py` (`branch_mode=True`)
- `tests/lib/metadata_update_fixture.sh:188`
- `tests/test_task_push.sh:158 setup_branch_mode` (behind the gate)
- `tests/test_remote_drift_check.sh:111 mark_branch_mode` (a `mkdir` stub)
- `tests/test_plan_approved_marker_drift.sh:86` (a `.git` stub)

Add the shared `tests/lib/data_branch_fixture.sh` helper:
`ait_fixture_to_branch_mode` (registered worktree, production
`ait_ensure_data_symlinks`) and `fixture_data_git`. Its self-test checks that
the layout classifies like a real `setup_data_branch` layout. **Legacy
fixtures stay.**

Measurement: run the whole suite once with the Step B validation applied as a
throwaway patch in an isolated worktree (never committed) to find any other
stub layout, and convert those too. Read every builder before reusing it.

**Step B, shell enforcement.**
- Implement the wiring: the rung 1–4 validation, the writer guard placed
  before the bypass, and the reader guards (with the placement order) in
  `aitask_ls.sh` and `aitask_query_files.sh`.
- Run the errexit audit.
- Run the writer audit.
- Add `git-health` reporting if t2074_1 handed it over.

Tests, in a new `tests/test_data_layout_refusal.sh` derived from the
enforcement table:
- **Broken states:** every class refuses.
- **`unlinked`:** git routing works (`./ait git status`, `task_git log`,
  `task_sync` against a remote fixture), while readers and writers refuse.
- **Legacy and uninitialized:** positive controls, unchanged.
- **Fixture data:** each fixture carries dirty, untracked and ignored data
  (`aitasks/new/` drafts, a gitignored file under `aiplans/`).
- **Commands:**
  - `task_git add/commit`, `task_sync`, `task_push`, `./ait git pull/push`
  - `aitask_task_commit.sh`, `aitask_archive.sh`
  - `aitask_update.sh --batch` without `--commit`, with and without
    `AIT_GIT_SKIP_STATE_CHECK=1`
- **No-mutation proof:**
  - a before/after manifest (type, symlink target, mode, sha256) of
    `aitasks/`, `aiplans/` and `.aitask-data/`, ignored and untracked files
    included;
  - snapshots of both repos (HEAD, every ref, `ls-files -s`,
    `status --porcelain --ignored`) and of the bare remote's refs;
  - a positive control per case;
  - a planted write-before-refusal mutant that must fail the comparison.
- **Missing storage:** delete `.aitask-data` in a fixture with a remote.
  `task_git commit`, `./ait git push` and `aitask_update.sh --batch` all
  refuse, and no commit lands on the code branch (HEAD, refs and index
  snapshots). Then `ait setup` restores, and both classifiers re-read
  `branch` / `ready`.
- **Bisect recovery:** mid-bisect in the data worktree, `./ait git bisect
  reset` succeeds and `./ait git status` works, while a write still refuses
  via the wedge check.
- **Representative reads:** `./ait ls` and `aitask_query_files.sh resolve <n>`
  refuse on `misdirected` and on `unlinked`. They work in `ready`, in
  `legacy` and inside `.aitask-data`.
- **Reader ordering, for both readers:**
  - broken source + healthy `--project` destination: succeeds;
  - healthy source + broken destination: refuses with the destination's
    state;
  - `--help`, or `aitask_query_files.sh` with no subcommand, on a broken
    layout: exits 0.
- **T13c/T13d acceptance:** git operations work from both shapes. A writer
  works inside `.aitask-data`, and refuses in an unlinked worktree without
  creating a real `aitasks/`.
- **errexit:** one test per audited site.

**Step C, Python and board enforcement (from t2074_10).**
- `board_task_manager._task_git_cmd` resolves from the repo root, not the cwd,
  and **validates fresh on every call**. It never uses the cached
  `snapshot()`. Board operations split into two named classes that follow the
  enforcement table:
  - **Git inspection of the data worktree: needs C1a only**, via
    `require_repo_branch()`. Read-only commands (status/dirty indicators, log,
    diff, show) still run while C1b is `misdirected` / `dangling` / `mixed` /
    `unlinked`, because they inspect the valid data worktree, not the local
    paths.
  - **Mutations: need C1a and C1b**, via `require_branch_ready()`, checked
    immediately before the operation. These are every board path that changes
    task data:
    - task-file edits and column/board-index moves;
    - revert, `git checkout --` (`board_detail_screen.py:59,1970`);
    - delete, `git rm -f` (`aitask_board.py:6629`);
    - any board-initiated commit.

  `_task_git_cmd` takes an explicit class argument, so a mutating caller cannot
  silently get the repository-only check. A test enumerates every caller and
  asserts its class.
  - In `legacy` / `uninitialized` it explicitly returns `["git"]`, as today.
  - Broken states raise with the recovery.
  - Every caller (`aitask_board.py:6629`, `board_detail_screen.py:59,1970`)
    surfaces the error and never falls back to plain git.
- Board startup applies the reader-class check, refusing with the recovery
  text on a non-ready branch layout. The `aitask_board.py` :236/:2851 sync gate
  becomes an explicit refusal toast for broken branch layouts; legacy is
  unchanged.
- `desync_state`, `cross_repo_settings` and `REASON_DEST_LEGACY_LAYOUT` are not
  touched.
- Tests:
  - from a non-root cwd, a valid layout resolves to the data worktree;
  - a broken `board_fixture` is refused, with no git run against the code
    repo;
  - the legacy board fixture still works;
  - **Same-process transitions.** Each transition gets its own test, and each
    test's expectations come from the enforcement table. Every test runs in
    one Python process (a live board app via `App.run_test`, or the
    `board_task_manager` API). It starts from a valid layout, where one
    inspection and one mutation both succeed. Then it applies a single
    transition:
    - **(a) Branch switch** (C1a becomes `broken:wrong_branch`): the next
      inspection **and** the next mutation (edit, revert, delete) all refuse.
    - **(b) Missing storage** (`.aitask-data` deleted, so C1a becomes
      `broken:missing_storage`): inspection and every mutation refuse. No
      command falls back to plain git on the code repo.
    - **(c) Redirected link** (`aitasks` repointed to another existing dir;
      C1a stays `branch`, C1b becomes `misdirected`): inspection **succeeds**
      against the valid data worktree. Edit, revert and delete each **refuse**.

    For every refusal, check that nothing changed: the content manifest
    (including the redirected-to dir in case c) and the HEAD/refs/index
    snapshots of both the data and the code repo.

    Planted control: a variant that reads the cached `snapshot()` must fail
    case (a), because it would mutate on the new branch.

**Verification for this child:**
- Every bash test, run individually.
- `bash tests/run_all_python_tests.sh`; the last line must read
  `PYTHON SUITE: PASSED`.
- `shellcheck`.

### t2074_12 `broken_layout_docs` (documentation; depends on t2074_3, t2074_9)

- Add a website troubleshooting section for **damaged branch-mode layouts**.
  For each C1a and C1b state, give the exact refusal text and the C4 recovery.
  Include `missing_storage`, the bisect and rebase wedged cases, the case (A)
  and case (B) repair paths and their refusals, and the never-prune rule.
- State the narrowed reader contract: which readers refuse and which do not.
- Link the section from the setup and sync pages with `relref`.
- Update the `git-health` output quoted in `installation/_index.md`.
- Update the aidocs references to the new classifier, in
  `aitasks_extension_points.md` and `tui_conventions.md`, if they describe
  detection.
- Leave the legacy docs as they are.
- Validation: `hugo build --gc --minify` and `python3 check_links.py --build`
  must pass. Run `check_link_relevance.py` and triage the result.

### t2074_14 manual verification (depends on t2074_3, t2074_9; `verifies: [2074_3, 2074_9]`)

Checklist:
- each broken state → refusal → `ait setup` repair, including a deleted
  `.aitask-data`;
- a moved-aside `.aitask-data`: setup refuses with instructions in a
  non-interactive run, and asks for confirmation in an interactive one;
- mid-bisect in the data worktree: `./ait git bisect reset` works;
- a misdirected link is repaired and the old dir is left untouched;
- an unlinked crew worktree: `./ait git status` works and a write refuses;
- the board refuses to start on a broken layout;
- a legacy project still works exactly as before: setup decline, `./ait git`,
  and writes.

## Task restructuring (applied after approval)

0. **Rescope the fold inputs first.** Before anything is folded, rewrite the
   t2074_2 and t2074_10 descriptions **and** their plans to the approved scope,
   using `aitask_update.sh --batch <id> --desc-file -` and committing. t2074_2
   becomes the Step A content; t2074_10 becomes the Step C content, including
   the fresh-validation rule and the same-process transition tests. Their old
   requirements are removed:
   - legacy-fixture conversion;
   - quarantine and probe completion;
   - refusing legacy Python operation;
   - `desync_state` / `cross_repo_settings` / `REASON_DEST_LEGACY_LAYOUT`
     changes.

   The fold then carries only approved scope into the `## Merged from`
   sections. Provenance is kept by the fold metadata (`folded_tasks`,
   `folded_into`) and by git history, which holds the pre-rescope text.
1. **Merge t2074_2 and t2074_10 into t2074_9**, following the framework fold
   conventions:
   - `aitask_fold_validate.sh --exclude-self 2074_9 2074_2 2074_10`;
   - then `aitask_fold_content.sh <t2074_9 file> <t2074_2 file> <t2074_10
     file> | aitask_update.sh --batch 2074_9 --desc-file -`, which produces the
     `## Merged from t<N>` sections;
   - then `aitask_fold_mark.sh --commit-mode fresh 2074_9 2074_2 2074_10`,
     which marks them Folded and removes them from `children_to_implement`.

   The folded task files stay as references until archival, as the convention
   requires. Their plan content is incorporated into the rewritten `p2074_9`
   plan as Steps A and C. Before removing `p2074_2` and `p2074_10`, read what
   `aitask_fold_mark.sh` and the archival path do with folded plans. Remove the
   two plans in the scoped commit only if neither handles them.
2. **Delete the dropped-scope children** t2074_4–8, t2074_11 and t2074_13:
   their task and plan files, with `aitask_update.sh --batch 2074
   --remove-child`. Their content is legacy-removal work, so it is dropped,
   not merged. None was started, and no notes were sent.
3. **Rename the parent** to `branch_mode_layout_hardening` with
   `aitask_update.sh --name`. Then `./ait git mv` the plan file to
   `aiplans/p2074_branch_mode_layout_hardening.md`, since rename does not move
   plans. Rewrite the parent description and plan to this document.
4. **Rewrite the kept children's descriptions and plans** to the sections
   above:
   - t2074_3 becomes `setup_layout_repair`;
   - t2074_9 becomes `branch_layout_enforcement` (after the fold content
     lands);
   - t2074_12 becomes `broken_layout_docs`;
   - for t2074_14, rewrite the checklist and run `--remove-verifies 2074_10`.

   Update every `Parent Task:` and sibling header in the child plans.
5. **Dependencies.** Remove self-dependencies and references to absorbed or
   deleted children.

   | Child | depends |
   |---|---|
   | t2074_1 | `[]` |
   | t2074_3 | `[2074_1]` |
   | t2074_9 | `[2074_1, 2074_3, 2064]` |
   | t2074_12 | `[2074_3, 2074_9]` |
   | t2074_14 | `[2074_3, 2074_9]` |
6. **Commit.** Commit every task and plan path, including the deletions, with
   `aitask_task_commit.sh` / `./ait git`, naming each path. Change no code.

## Risk

### Code-health risk: medium
- Strict validation rejects stub or clone-style branch fixtures and breaks
  their tests · severity: medium · → mitigation: covered by t2074_9 Step A
  conversion plus the one-off measurement run
- A new die path is masked by `local x="$(…)"`, or a writer still bypasses the
  check · severity: medium · → mitigation: covered by the t2074_9 Step B
  errexit and writer audits and the no-mutation tests
- Repair destroys worktree metadata (an unrelated worktree, or the target's
  staged index) · severity: high · → mitigation: covered by t2074_3's bounded
  repair (no prune, case A/B, preservation preflight) plus the isolation and
  preservation tests with planted controls
- Collision with t2064 on `task_utils.sh` / `test_task_push.sh` / `test_task_git.sh`
  · severity: medium · → mitigation: covered by the t2074_9 Step 0 gate and
  `depends:` on t2064

### Goal-achievement risk: low
- Legacy behaviour regresses by accident · severity: medium · → mitigation:
  covered by the legacy controls in t2074_1, t2074_3 and t2074_9 (Steps B and
  C), plus the t2074_14 legacy item

## Verification (of the restructuring)

- `./.aitask-scripts/aitask_ls.sh -v --children 2074 99` lists exactly
  t2074_1, 3, 9, 12 and 14, with the dependency table above.
- The parent's `children_to_implement` is
  `[t2074_1, t2074_3, t2074_9, t2074_12, t2074_14]`.
- t2074_2 and t2074_10 have status Folded (`folded_into: 2074_9`), and t2074_9
  has `folded_tasks` and the `## Merged from` sections.
- No task or plan file remains for t2074_4–8, t2074_11 or t2074_13.
- **The text scans are review aids, not gates.** Apply them only to the
  **active implementation requirements**: the descriptions and plans of
  t2074_1, t2074_3, t2074_9, t2074_12 and t2074_14, including t2074_9's
  `## Merged from` sections.

  They do **not** apply to:
  - the parent t2074 description and plan, which deliberately contain this
    restructuring section, its instructions and these scan expressions;
  - restructuring or migration instructions;
  - scan expressions;
  - negative-test and planted-control descriptions.

  Each match is triaged in context, not counted:
  - `remove_legacy`, `t2074_13`, `t2074_10`, `t2074_2`: fine as fold
    provenance or historical references; flagged only if they state a
    requirement.
  - `quarantine`, `legacy fixture`, `convert.*legacy`, `NEEDS_CONVERSION`,
    `LEGACY_MODE_SKIP`, `REASON_DEST_LEGACY_LAYOUT`, `desync_state`,
    `refuse.*legacy`, `once per process`: allowed only in explicit "unchanged /
    not touched / out of scope" statements, or in shell-side per-process cache
    wording.
  - `snapshot()`: allowed as display-only usage, and in the cached-snapshot
    planted negative control; flagged as a requirement anywhere else.
- **t2074_9 completeness check (mechanical).** Turn this plan's t2074_9
  section into a numbered requirement checklist (Steps 0, A, B and C, each
  test bullet, the verification commands). For each item, record where it
  appears in t2074_9's final description, by section heading plus a quoted
  line. Every item must be located, and no active requirement in the
  description may lack a matching checklist item. Record the checklist in the
  restructuring commit's notes, i.e. in t2074_9's plan.
- **Historical vs active.** The folded files t2074_2 and t2074_10 (status
  Folded, rescoped text) are references only, deleted at archival. Pre-rescope
  text survives only in git history and the earlier commits of the parent
  plan, never in an active description.
- Not one code file has changed.
