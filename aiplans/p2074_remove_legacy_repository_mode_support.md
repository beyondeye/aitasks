---
Task: t2074_remove_legacy_repository_mode_support.md
Base branch: main
Output branch: main
---

### Pre-phase (risk mitigations)
1. [measure_flip_breakage] (carried by t2074_1, before any wave-2 batch
   starts) Run the full bash and Python suite once in an isolated
   `git worktree` with the **enforcement probe** applied (see "Probe
   definition"). Never commit the patch. Record the failing set **per test
   case**, not per file, and use `./ait note` to send each wave-2 child its
   slice. This replaces the heuristic counts below.

# t2074 — Remove legacy (code-branch task data) repository mode

## Context

aitasks supports two layouts for task data. In **branch mode**, an orphan
`aitask-data` branch is checked out at `.aitask-data/`, and `aitasks/` and
`aiplans/` are symlinked into the code checkout. In **legacy mode**, `aitasks/`
is a real dir on the code branch and `task_git` is plain `git`. During the t2070
shadow review the user decided to remove legacy mode completely, because two
models keep producing legacy-only defects.

The only supported model from now on is the data branch with the data worktree.
Before any task-data write, stage, commit, pull or push, every entry point
validates that layout and refuses anything else with an actionable message.
`ait setup` is the only converter. It uses the existing one-way migration, which
preserves data and fails closed. It is also the repair tool for the broken states
it can repair losslessly.

**User decisions (this session):**
1. Split the work into child tasks.
2. Existing legacy installs are refused at runtime and told to run `ait setup`.
   Setup migrates. Declining the migration aborts setup and changes nothing.
   `ait upgrade` installs files and prints the notice, but never migrates.

## Audit findings (evidence)

**Single root.** Every runtime legacy branch traces to rung 4 of
`_ait_detect_data_worktree` (`.aitask-scripts/lib/task_utils.sh:145`,
`_AIT_DATA_WORKTREE="."`). Rungs 1-3 (:81-121) accept a layout on the mere
existence of `.aitask-data/.git`. They do no ownership, branch or link check.

The `"."` branches:
- `task_utils.sh`:
  - `_ait_data_gitdir` :185
  - `ait_data_mode` :210
  - `_data_wedge_gitdir` :274
  - `_data_wedge_state` :282
  - `_ait_data_git` :298
  - `task_git_health` :513
  - `task_git` :552
- `aitask_sync.sh` :279, :568-584, :696
- `lib/txn_snapshot.sh` :75
- `lib/task_automerge.sh` :83

These inherit the same behaviour: the artifact and attachment resolvers,
`task_sync`/`task_data_converge`/`_ait_owned_pull`, `aitask_pick_own.sh` and
`aitask_task_commit.sh`.

These probe the filesystem themselves:
- `aitask_init_data.sh`: `LEGACY_MODE` at :142-147 and :179-183. `NO_DATA_BRANCH`
  at :207/:215, which the skills treat as "proceed".
- `aitask_lock_diag.sh` :181.
- `board/board_task_manager.py:66` `_task_git_cmd`: only checks
  `./.aitask-data/.git`, and returns `["git"]` otherwise.
- `board/aitask_board.py` :236 and :2851.
- `lib/desync_state.py` :150-159.

**Writer bypass.** `assert_task_data_writable` (`task_utils.sh:488`) and
`assert_data_worktree_clean` (:435) return before resolving the layout when
`AIT_GIT_SKIP_STATE_CHECK=1`. Callers that set it:
- `aitask_metadata_commit.sh:141`
- `aitask_sync.sh:2196`

`aitask_update.sh` calls the guard at :677, :1602 and :1874, and batch mode
writes the file without `--commit` (:2291), so `task_git` is never reached.

**Setup shortcut.** `aitask_setup.sh::setup_data_branch` :1571 reports
"already configured" on `.aitask-data/.git` existence alone.

**Tokens and their consumers:**

| Token | Producer | Consumers |
|---|---|---|
| `LEGACY_MODE_SKIP` | `aitask_remote_drift_check.sh:152` (plus the `--unsynced` bypass) | `task-workflow/remote-drift-check.md` :43-57/:115, `merge-target-sync.md` :43-49 |
| `LEGACY_MODE` / `NO_DATA_BRANCH` | `aitask_init_data.sh` | `task-workflow/SKILL.md` Step 7 :561, pickrem/pickweb `SKILL.md.j2` Step 0a |
| `legacy` | `ait_data_mode` | `aitask_metadata_commit.sh:144` `MODE:legacy` → `lib/metadata_commit.py:156` → `cross_repo_settings.py` `REASON_DEST_LEGACY_LAYOUT` (stays as a refusal of a foreign unconverted repo) |
| `missing_worktree` | `desync_state.py` | `syncer_app.py` |

Goldens:
- `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md`
- `remote-drift-check-default.md`
- `cross-repo-child-assignment-default.md`
- `tests/golden/skills/aitask-{pickrem,pickweb}/SKILL-remote-claude.md`

Committed remote prerenders: `{.claude,.agents,.opencode}/skills/{task-workflow,aitask-pickrem,aitask-pickweb}-remote*-/`.

**Setup.**
- `setup_data_branch` (1563-2057) has the opt-out prompt at 1643-1658.
- It falls back to legacy at 1716-1721, at 1747-1764, and through
  `abort_data_branch_setup` (1485).
- It already contains a fail-closed migration (`needs_migration`). The
  migration keeps every file but not per-file history.
- `install.sh` creates real `aitasks/` before setup (`create_data_dirs` :517),
  so a fresh install always migrates.
- `install.sh` `ensure_data_root` (:457-511) turns a dangling link into a real
  dir.
- `install.sh` has legacy early returns at :1244 and :1500.
- No flag or env var selects legacy.
- A missing network remote is already independent:
  `test_data_branch_setup.sh` T5 and T25.

**Tests** (the dominant cost). About 125 files run on legacy fixtures, almost
all of them implicitly: `git init`, a real `aitasks/`, a plain commit, then
task writers.

Existing branch builders:
- `tests/lib/sync_fixture.sh:41 setup_repo` (a real worktree)
- `tests/lib/branch_mode_repo.py:45` (a real worktree)
- `tests/lib/metadata_update_fixture.sh:188`, `test_task_push.sh:158
  setup_branch_mode` and `tests/lib/board_fixture.py:494-650`. These build
  `.aitask-data` as a **standalone clone or repo, not a registered worktree**,
  so the strict classifier will reject them.

Legacy builders:
- `metadata_update_fixture.sh:124/146`
- `branch_mode_repo.py:268 make_legacy_repo` (keep, for refusal tests)
- `board_fixture` `branch_mode=False`

Retired-behaviour cases:

| File | Cases |
|---|---|
| `test_init_data.sh` | T1, T21, T9, T23 |
| `test_task_git.sh` | T1, T4, T6, T10, T15 |
| `test_remote_drift_check.sh` | T1, and the T8/T8b controls |
| `test_task_push.sh` | T1, T3, T6, T26 |
| `test_sync.sh` | T7 |
| `test_metadata_commit_seam.sh` | T14 |
| `test_task_data_writer_guard.sh` | §A |
| `test_note_cross_repo.sh` | case 9 |
| `test_t644_branch_mode_upgrade.sh` | scenario C |
| `test_install_create_data_dirs.sh` | T2, T4 |
| `test_data_branch_setup.sh` | T14, T23 |

**Unrelated "legacy" (exclude):**
- Legacy plan headers and `verify_build`.
- The shadow "Default (= Legacy)" tier and the web-merge marker.
- Archive `old.tar.*` and old frontmatter.
- PID-less locks, tmux legacy socket/session, `AITASKS_PROJECT_<s>`, the
  `~/.aitask` home migration and model/agent aliases.
- "Separate branch" meaning the per-task worktree branch. This includes the
  pinned anchor `SKILL.md:843` "If a separate branch was created:", which must
  not be reworded.
- "Current-branch mode", and other orphan branches (`aitask-locks`, crew).

**In-flight overlap.**
- t2070 and t2071 committed during planning (02459e5a5, a2d675a1c).
- t2064 is still Implementing, and owns uncommitted hunks in `task_utils.sh`,
  `test_ait_git_gateway_pull.sh`, `test_task_git.sh` and `test_task_push.sh`.
- `lib/data_symlinks.sh` (sourced by `task_utils.sh:26`), `aitask_setup.sh`
  and `aitask_update.sh` are clean.

**Backlog with legacy criteria:**
- t1619: the MV decline branch.
- t1625: the MV `LEGACY_MODE` link token.
- t1678: the index lock in "both modes".
- t1984: the legacy plus branch concurrency cell.
- t1708: "every pin runs in a LEGACY-mode fixture".
- t1796: detection reasoning.

## Target contract (binding on every child)

### C1. Two classifiers: repository resolution vs local path readiness (neither dies)

There are two separate questions, so there are two functions. Both live in
`lib/data_symlinks.sh`, print `<state>[:<reason>]` and **always return 0**.
**Neither ever terminates**, including on indeterminate topology. Dying is
reserved for the `ait_require_*` enforcers in C2.

**C1a. `ait_data_repo_state` — which data worktree does this repository
use, and is it valid?** Resolution order, first hit wins. Main-root discovery
runs **only when local resolution fails**:
1. **The cwd is inside the data worktree itself.** Toplevel's HEAD is
   `aitask-data` (or the rebase `head-name`) and it is a registered worktree of
   the same common dir. That data worktree is the answer. This preserves T13c:
   inside `.aitask-data`, `aitasks/` and `aiplans/` are real dirs, legitimately.
2. **A local marker:** `./.aitask-data`, then `<toplevel>/.aitask-data`.
   Validated as described below. A usable separate-git-dir primary with a valid
   local data worktree resolves here, without ever calling
   `ait_main_worktree_root`.
3. **The main checkout's marker**, via `ait_main_worktree_root`. This covers an
   unlinked linked worktree, preserving T13d. If that call returns 2:
   - and `ait_linked_worktree_roots` proves this checkout is not linked, fall
     through to rule 4;
   - otherwise the answer is `indeterminate:topology` (a state, not a die).
4. **No marker anywhere:**
   - a real `aitasks/` at the toplevel: `legacy`;
   - otherwise: `uninitialized`;
   - outside any git work tree: `not_a_repo`.

**Validation** of a resolved `<data>` (rules 1-3). Report the first failure,
or `branch`. A bare `.git` existence test no longer suffices.
1. **Live worktree.** `<data>` is the toplevel of a git worktree. A stale
   `gitdir:` file, an empty `.git`, or a pruned admin dir gives
   `broken:stale_marker`.
2. **Same repository.** `<data>`'s canonical `git-common-dir` equals this
   checkout's. Otherwise `broken:foreign_repo`: an unrelated repo, a clone, or
   another repo's worktree.
3. **Right branch.** HEAD is `refs/heads/aitask-data`. While a rebase is in
   progress, read the branch from `rebase-*/head-name` instead: that is valid
   but wedged, and is reported by the wedge machinery. Otherwise
   `broken:wrong_branch`.

**C1b. `ait_data_paths_state` — can this process safely read and write task
files through its relative `$TASK_DIR`/`$PLAN_DIR`?**

The root it validates is the process cwd that those relative paths resolve
against. That is `$PWD` after `ait`'s `cd` or `ait_cd_repo_root`.

Precondition: C1a = `branch`. Then:
- **ready:** `canon($PWD/$TASK_DIR)` == `canon(<data>/aitasks)` and
  `canon($PWD/$PLAN_DIR)` == `canon(<data>/aiplans)`. This holds in three
  places:
  - inside the data worktree (real dirs);
  - in the primary (symlinks);
  - in a `--link-worktree`'d worktree (symlinks through its `.aitask-data`
    link).
- **`unlinked`:** the paths are absent in a linked worktree. Git routing
  through C1a still works, but filesystem writers must refuse. The recovery is
  `aitask_init_data.sh --link-worktree <root>`. A writer must never `mkdir`
  its way into a real dir there.
- **`misdirected`:** a path resolves somewhere else, e.g. a link to another
  existing dir, or a `TASK_DIR` override pointing outside `<data>`.
- **`dangling`:** a link exists but resolves nowhere.
- **`mixed`:** a real `aitasks/` or `aiplans/` dir in a primary or linked
  checkout while a valid data worktree exists.

### C0. Command-requirement table (the single source; C2, C4, C5 and every test derive from it)

| Class | Requires | Enforced by | Members (t2074_9 enumerates and records the full list) |
|---|---|---|---|
| **Git routing** | C1a = `branch` | `ait_require_data_repo`, in `_ait_detect_data_worktree` **and** `assert_data_worktree_clean` (the latter guards every `task_git`) | `task_git`, `task_sync`, `task_push`, `task_git_pull`, `task_data_converge`, `./ait git …`, `aitask_remote_drift_check.sh`, `aitask_lock.sh` / `aitask_pick_own.sh` git steps |
| **Local task-path readers** | C1a = `branch` **and** C1b = `ready` | `ait_require_data_paths` at the read entry point: the `ait` dispatcher for dispatched commands, a direct call at the top of each reader that skills invoke by path, and `lib/data_layout.py` at Python TUI startup | `ait ls`, `aitask_query_files.sh`, board, trails, stats, codebrowser task views, monitor task lookups, `aitask_explain_context.sh` |
| **Local task-path writers** | C1a = `branch` **and** C1b = `ready` | `ait_require_data_paths`, **first** in `assert_task_data_writable`, before the bypass. `AIT_GIT_SKIP_STATE_CHECK=1` skips only the wedge check | update, create, archive, fold, note, gate, plan_externalize, board column, every atomic-write caller, with or without `--commit` |
| **Exempt diagnostics and recovery** | nothing; they *report* states | none | setup, upgrade, install, help, version, engine, `git-health`, `aitask_lock_diag.sh`, `aitask_init_data.sh`, `aitask_data_layout.sh` |

Defaults and ordering:
- **The dispatcher fails closed.** A command not mapped in the table is
  treated as a reader.
- A command that both reads local paths and routes git takes the stricter
  class.
- `assert_data_worktree_clean` checks **only** C1a. A `ready` C1b is never a
  precondition for git routing, so an unlinked crew worktree (T13d) can run
  `./ait git status` / `task_git` successfully, but cannot read or write
  through its absent `aitasks/`.

**Cost and parity.** Checks run on the filesystem first (the gitdir file,
`commondir`, `HEAD`, `readlink`) and fall back to git. A differential test pins
the result against git's own answers. Results are cached once per process, in
the existing `_AIT_DATA_WORKTREE` cache.

**One implementation.** A new CLI, `aitask_data_layout.sh` (follow
`aidocs/framework/aitasks_extension_points.md` for the helper whitelist), wraps
the classifier. Python reads it through a new `lib/data_layout.py`, once per
process. Nothing re-implements the checks in Python. Go has no resolver
(verified), so it is unaffected.

### C2. Enforcement, before any write or git

There are two enforcers. Each prints a state-specific message that names the
recovery which actually works for that state (see C4).
- `ait_require_data_repo` dies unless C1a = `branch`. It is called by
  `_ait_detect_data_worktree` (in place of rung 4's `"."`) and **first** in
  `assert_data_worktree_clean`, which makes it the git-routing class. Its
  states include `indeterminate:topology`; the classifier itself never dies.
- `ait_require_data_paths` dies unless C1a = `branch` and C1b = `ready`. It is
  called **first, unconditionally**, in `assert_task_data_writable` (writer
  class) and at each reader-class entry point, exactly as C0 lists them.
  **It is not called from `assert_data_worktree_clean`.**
  `AIT_GIT_SKIP_STATE_CHECK=1` bypasses only the wedge check in either guard,
  never layout validation.

Every `"."` branch listed above is deleted. Every early return in a writer
guard that precedes layout resolution is audited. Every task/plan writer
(update, create, archive, fold, note, gate, plan_externalize, the atomic-write
callers, board column) must reach the guard **before its first write**, with
or without `--commit`.

Nested repos and submodules resolve to their own repository, and therefore to
`uninitialized` or `legacy`, never to the parent's data branch.

### C3. errexit audit

`_ait_data_gitdir` and `ait_data_mode` lose their "ALWAYS returns 0" contract.
Enumerate every `local x="$(…)"` call site of the detection accessors, and every
call site guarded by `if` or `||`: `local` masks a `die` inside `$( )`. Fix each
by priming detection with a direct statement first, or by switching it to the
classifier. Each site gets a test.

`aitask_gate.sh::_persist_task_file`'s non-git seam (:1049) switches to the
classifier.

### C4. Recovery contract (setup)

`setup_data_branch` replaces the :1571 shortcut with both classifiers, read
**before any setup write**.
- **Configured** means C1a = `branch` **and** C1b = `ready`. Only then is
  "already configured" reported.
- If C1a = `branch` but C1b is not `ready`, dispatch on the C1b result (rows
  below):
  - primary link repair for `dangling` / `misdirected` / absent links;
  - a conflict refusal for `mixed` or for a real file at a link path;
  - linked-worktree guidance for `unlinked`.
- If C1a ≠ `branch`, take the repository-level path. Each C1a state is
  handled on its own:
- C1a `uninitialized`: create the branch.
- `legacy`: migrate, with one confirmation. A decline exits non-zero with
  nothing changed.
- `broken`: **repair only when provably lossless**:
  - C1b `dangling`, `misdirected` and absent links in the primary. Do **not**
    use `ait_ensure_data_symlinks`: it deliberately keeps any resolving link
    whatever its target. Instead, extract the two-phase logic of
    `ait_link_worktree_data` (`lib/data_symlinks.sh:190`) into a shared
    `ait_repair_data_links <root> <data> [--with-data-link]`, used by both
    `--link-worktree` and setup's primary repair:
    - **preflight (read-only):** every real file or dir at a link path is a
      conflict. Report all of them and change nothing.
    - **apply:** repoint any link whose target is not the expected one (the
      raw literal for `aitasks`/`aiplans`, the canonical target for
      `.aitask-data`), create absent links, and `warn` with the old target.
      The old target's contents are never touched.
  - C1b `mixed`: refuse (it is a conflict) and print the compare-and-merge
    steps.
  - `stale_marker`, when the `aitask-data` branch exists and the stale dir holds
    nothing beyond the branch tip: `git worktree prune` / `repair`, then
    re-add.
  - `foreign_repo`, `wrong_branch`, a stale dir holding unique files, and
    `indeterminate:topology`: **refuse**, change nothing, and print exact
    manual steps. Those are move-aside commands that never delete.
- C1b `unlinked` (a linked worktree): the recovery is
  `aitask_init_data.sh --link-worktree <root>`, which uses the shared helper.

The runtime message for each state must name exactly the recovery this matrix
gives.

### C5. Front door

The `ait` dispatcher maps every subcommand to its C0 class.
- Git-routing commands are admitted on C1a = `branch`.
- Readers and writers are admitted on C1a = `branch` **and** C1b = `ready`.
- Exempt commands always run.
- An unmapped command defaults to the reader class.

The mapping table is committed beside the dispatcher, with a rationale for
each exempt entry. A drift test fails if any dispatched subcommand is
unmapped. C2 stays the backstop for scripts invoked directly, which is how
skills call them.

### C6. No silent migration

`aitask_init_data.sh` never converts.
- `LEGACY_MODE` becomes `NEEDS_CONVERSION` (exit 3).
- `NO_DATA_BRANCH` exits 3, and stays distinct from `NOT_INITIALIZED`.
- `--link-worktree` on a legacy primary gives `NEEDS_CONVERSION` (exit 3).

Every consumer changes in the same child as its producer.

### C7. Missing remote ≠ missing branch

A repo with a local `aitask-data` branch and no `origin` is fully supported.

### Probe definition (used by wave 2 acceptance)

The probe is a throwaway patch, applied only in an isolated worktree:
- rung 4 calls `die`;
- rungs 1-3 accept only C1a = `branch`;
- the writer guards require C1b = `ready`.

**Retired cases are isolated, never expected to fail.** A retired case that
runs in a file's own shell, such as `test_task_git.sh` T1, which calls
detection directly, would kill the whole file under the probe and hide every
later case. So the batch that owns such a file **moves each retired case,
verbatim, into a quarantine file**: `tests/test_legacy_retired_<area>.sh`, or
`tests/test_legacy_retired_<area>.py` for the few Python cases. Each moved case
keeps its body, and the quarantine file's header names t2074_9 as its deleter.
The probe excludes the quarantine files **by name**. That list, file-level,
lives in t2074_1's committed plan.

**Completion evidence is mandatory, separate from pass/fail.** t2074_1
records, on the current tree and before conversion, a per-file baseline:
- for bash files: the summary line and its `TOTAL` count;
- for Python: the collected test ids.

A batch passes when **every** non-quarantined file in it:
- exits 0 on the current tree;
- exits 0 under the probe;
- prints its summary line under the probe;
- reaches `TOTAL` ≥ baseline − (assertions moved to quarantine). For Python,
  every retained test id must appear in the junit output as passed.

An early exit, a missing summary, or a short count fails the probe, whatever
the allowlist says.

The suite as a whole passes only after t2074_9, which deletes the quarantine
files and adds their refusal-test replacements. Its acceptance is the full
suite under real enforcement, with no probe.

## Decomposition (child tasks, strict wave order)

Each child is self-contained: it carries its own steps, files and
verification.

Children that touch t2064's files get the **shared-file gate** as their first
step:
- for each named file, `git diff --quiet -- <file>` passes, and t2064's commit
  is in `git log`;
- re-run the check immediately before the first edit;
- do all non-overlapping work first;
- if the gate still fails, stop and ask.

Those children also get a `depends:` on t2064.

**Wave 1** (parallel):
- **t2074_1 `branch_mode_test_fixtures`** (test). New shared helpers in
  `tests/lib/data_branch_fixture.sh`:
  - `ait_fixture_to_branch_mode <repo> [--remote <bare>]` converts a fixture
    with a real `aitasks/` and `aiplans/` into a **registered** orphan
    `aitask-data` worktree. It uses production `ait_ensure_data_symlinks`, the
    `.gitignore`, and main-index removal, and pushes the data branch when a
    remote exists.
  - `fixture_data_git`.

  Python: `convert_to_branch_mode(root)` in `tests/lib/branch_mode_repo.py`.

  **Convert the clone-style builders to registered worktrees**, keeping their
  signatures:
  - `board_fixture.py` `branch_mode=True`
  - `metadata_update_fixture.sh:188`
  - and the legacy builders at :124 and :146

  `test_task_push.sh:158` waits for t2074_7.

  Self-test: a differential showing the helper's layout classifies like a real
  `setup_data_branch` layout. Add a fixture-layout section to
  `aidocs/framework/testing_conventions.md`.

  Also carries the pre-phase `measure_flip_breakage` and the retired-case
  allowlist. This child depends on t2074_2, because the probe uses the
  classifier.
- **t2074_2 `data_layout_classifier`** (feature). Additive only: no existing
  caller changes behaviour.
  - C1a and C1b in `lib/data_symlinks.sh`.
  - `aitask_data_layout.sh` (state CLI) and `lib/data_layout.py`.
  - `./ait git-health` reports the state and reason.

  Controls, one fixture per state and reason. The `broken` reasons that need
  dedicated fixtures:
  - malformed marker: stale gitdir file, empty `.git`, admin dir pruned
  - wrong target: an unrelated repo, a clone, or a worktree of another repo at
    `.aitask-data`
  - wrong branch
  - mixed layout: a valid data worktree plus a real `aitasks/`
  - links: dangling, misdirected, or missing in a linked worktree

  Positive cases:
  - a valid layout mid-rebase, which is `branch` and wedged, not broken
  - **T13c equivalent:** cwd inside `.aitask-data` gives C1a `branch` and
    C1b `ready`
  - **T13d equivalent:** an unlinked crew worktree gives C1a `branch`
    (resolved to the main checkout's data worktree) and C1b `unlinked`
  - a `--link-worktree`'d worktree is `branch` / `ready`
  - a usable separate-git-dir primary with a valid local data worktree is
    `branch`, resolved without main-root discovery
  - an unresolved linked checkout of such a primary is
    `indeterminate:topology`, returned rather than died
  - a submodule or nested repo is its own repository's state
  - a C1b `misdirected` link to an existing other dir, and a `TASK_DIR`
    override outside `<data>`

  Also assert that both classifiers return 0 and print a state for every
  fixture, under `set -euo pipefail`, from `$( )` and from `local`.

  Also:
  - a filesystem-vs-git differential;
  - a Python/shell parity test.
- **t2074_3 `setup_install_transition`** (refactor; depends on t2074_2).
  Applies to `aitask_setup.sh`, `install.sh`, `aitask_upgrade.sh`, and the
  setup role of `aitask_init_data.sh`.
  - C4 replaces the :1571 shortcut.
  - Remove the fresh-setup `[Y/n]` opt-out. The migration keeps one
    confirmation; a decline means a non-zero exit with "task data unchanged".
    Non-interactive runs auto-accept, as now.
  - The 1716, 1747 and `abort_data_branch_setup` fallbacks become a teardown
    followed by a non-zero exit, with originals intact. Tests 26, 26b, 27 and
    31 assert the exit status.
  - The `_ait_data_branch_exclude_re` and `commit_framework_data_files` early
    returns become pre-conversion guards.
  - In `install.sh`, `ensure_data_root`'s dangling-link repair becomes a
    refusal that points to `ait setup`. A legacy project gets a prominent
    conversion notice on install and upgrade, with no migration.
  - Extract `ait_repair_data_links` from `ait_link_worktree_data`.
    `--link-worktree` keeps its `LINKED` / `ALREADY_LINKED` / exit-2 contract,
    and `test_init_data.sh` link cases stay green.
  - **Setup "configured" test:** a valid data worktree with a misdirected
    primary `aitasks` link gives C1a `branch` and C1b `misdirected`. `ait
    setup` must **not** report "already configured". It must run the C1b link
    repair.
  - **Recovery tests:** on the same damaged fixture, the runtime refusal is
    followed by the advertised recovery, then both classifiers are re-read and
    must be `branch` / `ready`. This covers every C4 row, including "refuse,
    nothing changed" (a manifest compare, see C-evidence below). It explicitly
    includes:
    - a primary `aitasks` link that resolves to **another existing dir**: after
      repair the link target is the expected literal, and the old target dir's
      manifest is byte-identical;
    - a real-dir conflict at a link path: refused, nothing changed;
    - an unlinked crew worktree: a writer refuses, then `--link-worktree`
      makes it `ready`.
  - Tests: `test_data_branch_setup.sh`, `test_install_create_data_dirs.sh`
    T2/T4, `test_t644` scenario C (upgrade prints the notice and leaves the
    data), `test_setup_hooks_only.sh`, and `test_agent_instructions.sh` T43.
  - Send a note to t1619.

**Wave 2** (depends on t2074_1 and t2074_2; the batches are independent of each
other).
- Convert every fixture with the t2074_1 helpers.
- Rewrite code-branch commit assertions to use `fixture_data_git`, keeping
  every original behavioural assertion.
- Never delete suites and never weaken unrelated assertions.
- Acceptance is the **probe definition** above.

The batches:
- **t2074_4 `convert_tests_artifacts_attachments`**: `test_artifact_*`,
  `test_attach_*`, `test_gate_record`, `test_note_append`,
  `test_aitask_merge_boardgroup`. Note to t1708.
- **t2074_5 `convert_tests_task_writers`**:
  - create, update, draft, label, followup and file_references tests
  - archive_*, fold_*, zip_old, auto_merge_file_ref, migrate_archives
  - issue_import*, pr_contributor, contribute, revert_*, deps_unblock, t167
- **t2074_6 `convert_tests_gates_locks`**:
  - gate_*, verification_*, plan_externalize
  - ledger and note_* tests, except cross_repo
  - lock_*, crash_recovery, pick_own, anchor_*, claim_id, live_endpoint_*,
    resource_admission
- **t2074_7 `convert_tests_crew_board_python`**:
  - crew_*, brainstorm_*, codeagent_*
  - board/ls/boardcol, shadow_*, projects_doctor, chatlink, change_surface,
    web_merge
  - Python: history_data, trail_links, task_declared_parity,
    settings_superseded_models, codebrowser_startup_focus_live,
    model_supersession
  - board_movement and board_gate_digest_budget: drop their legacy comparison
    half
  - verified_update*, usage_update, install_superseded_*,
    prune_retired_skills, install_engine_binary
- **t2074_8 `convert_tests_sync_git_core`** (depends on t2064; shared-file
  gate). Re-read the landed t2070/t2071 state first, then convert:
  - `test_sync.sh` (`setup_sync_repos`)
  - `test_task_push.sh` (`setup_remote_and_clone`, `j_setup`, and
    `setup_branch_mode` turned into a registered worktree)
  - `test_sync_failopen_probes.sh`, `test_txn_snapshot.sh`
  - the non-retired cases of `test_task_git.sh`
  - the `test_remote_drift_check.sh` fixtures: replace the `mark_branch_mode`
    `mkdir` stub
  - `test_metadata_commit_seam.sh`, and the `_AIT_DATA_WORKTREE="."` presets

  Move retired cases verbatim into `tests/test_legacy_retired_sync_git.sh`
  (quarantine, see the probe definition). That includes in-shell detection
  cases such as `test_task_git.sh` T1/T4/T6/T10/T13e/T15, and the T13c/T13d
  cases stay where they are. The other batches do the same for any retired
  case in their own files: `test_init_data.sh` T1/T21 and
  `test_task_data_writer_guard.sh` §A go to t2074_6's quarantine file,
  `test_metadata_commit_seam.sh` T14 stays with this batch.

**Wave 3:**
- **t2074_9 `runtime_layout_enforcement`** (refactor; depends on
  t2074_3 … t2074_8, and on t2064 through the gate). Implement C2, C3, C5 and
  C6 in:
  - `task_utils.sh`, `aitask_sync.sh`, `txn_snapshot.sh`, `task_automerge.sh`
  - the resolver comments
  - `aitask_remote_drift_check.sh`: remove `LEGACY_MODE_SKIP` and `--unsynced`
  - `aitask_init_data.sh`
  - `aitask_metadata_commit.sh`: `MODE:` is always `branch`; the line stays
    for skew detection
  - `aitask_lock_diag.sh`: `check_fail` with the state and reason
  - `aitask_gate.sh`
  - `ait`
  - `aitask_board_column.sh`

  Consumers change in the same child:
  - `remote-drift-check.md` and `merge-target-sync.md`
  - `SKILL.md` Step 7 tokens and the :551 wording
  - pickrem/pickweb `SKILL.md.j2` Step 0a: `NEEDS_CONVERSION` and
    `NO_DATA_BRANCH` now stop with the Stopped banner
  - every `--unsynced` call site
  - goldens and remote prerenders, regenerated with repo tooling
    (`aitask_skill_render.sh … --force` / `aitask_skill_rerender.sh remote`,
    then `aitask_skill_verify.sh`)

  Delete every `tests/test_legacy_retired_*` quarantine file and add its
  refusal-test replacements. `test_task_git.sh` T15 becomes a refusal test.
  Enforcement acceptance re-runs the T13c and T13d equivalents:
  - git ops work from both shapes;
  - a writer works inside `.aitask-data`;
  - a writer refuses in the unlinked worktree and creates no real `aitasks/`.

  **Negative tests (C-evidence)** go in a new
  `tests/test_data_layout_refusal.sh`.
  - **States and expectations are derived from C0.**
    - Every unsupported C1a state and reason, plus a nested repo: **all**
      non-exempt classes refuse.
    - Every non-`ready` C1b state with C1a = `branch` (`unlinked`,
      `misdirected`, `dangling`, `mixed`):
      - **readers and writers refuse**, with `ait ls`, `aitask_query_files.sh`
        and a board-startup probe on the reader side;
      - **git-routing commands succeed** (positive), e.g. `./ait git status`,
        `task_git log`, `task_sync` against a remote fixture.
    - Exempt diagnostics run in every state and report it.
  - **Fixtures carry dirty data:** a modified tracked task, an untracked new
    task, and ignored or untracked data such as `aitasks/new/` drafts and a
    gitignored file under `aiplans/`.
  - **Commands:** `task_git add/commit`, `task_sync`, `task_push`,
    `./ait git pull/push`, `aitask_task_commit.sh`, `aitask_archive.sh`, and
    `aitask_update.sh --batch`. Run `aitask_update.sh --batch` **without
    `--commit`, with and without `AIT_GIT_SKIP_STATE_CHECK=1`**.
  - **Pass condition:** every command C0 says must refuse exits non-zero with
    the state-specific message. Every command C0 says must run succeeds.
  - **No-mutation proof:** take a before/after manifest of every path under
    `aitasks/`, `aiplans/` and `.aitask-data/`, including ignored and
    untracked files. Each entry records type, symlink target, mode and sha256.
    Also snapshot both repos (HEAD, every ref, `ls-files -s`,
    `status --porcelain --ignored`) and the bare remote's refs.
  - **Controls:** each case has a positive control on a real branch-mode
    fixture. A planted write-before-refusal mutant must make the manifest
    compare fail.
  - Add the errexit tests from C3.

  Send notes to t1625, t1678, t1984 and t1796, quoting the committed SHA.
- **t2074_10 `python_layout_enforcement`** (refactor; depends on t2074_7 and
  t2074_9).
  - `board_task_manager._task_git_cmd` resolves through `lib/data_layout.py`
    from the repo root, not the cwd, and raises a clear error on a non-branch
    state. Its callers are `aitask_board.py:6629` and
    `board_detail_screen.py:59,1970`.
  - The `aitask_board.py` :236/:2851 gates become an explicit refusal toast.
  - `desync_state.py` `missing_worktree` and its `syncer_app.py` consumer are
    reworded as a broken layout.
  - `REASON_DEST_LEGACY_LAYOUT` stays as a refusal, worded "destination not
    converted — run `ait setup` there".
  - Tests: `test_desync_state.py`, `test_syncer_rows.py`, `test_cross_repo_*`,
    and a board test against a broken-layout fixture.

**Wave 4** (depends on t2074_9):
- **t2074_11 `instructions_and_skill_prose`** (documentation).
  - Edit `seed/aitasks_agent_instructions.seed.md` :58-60 and :73, and the
    hand-maintained `CLAUDE.md` :265-279.
  - Edit `.claude/skills/ait-git/SKILL.md` :9 and :57-59,
    `task-workflow/repo-structure.md` :30-36, `SKILL.md` :762, and
    `cross-repo-child-assignment.md` :131.
  - Edit `README.md` :20 and :93-98.
  - Regenerate `AGENTS.md`, `.codex/instructions.md` and
    `.opencode/instructions.md` through the setup assemblers, then the goldens,
    the prerenders and `aitask_skill_verify.sh`.
  - Run the port check on the non-rendered `.agents/` and `.opencode/`
    wrappers. Any stray file there gets a follow-up task.
- **t2074_12 `website_and_aidocs_sweep`** (documentation; depends on t2074_3
  and t2074_9). Audit all of `website/content/`. Known hits:
  - `overview.md:48`
  - `installation/_index.md` :60-62, :89 (the new `git-health` output) and
    :98-104
  - `commands/setup-install.md`: add the required data-branch step, the
    migration and its decline behaviour, broken-layout repair, and the upgrade
    notice
  - `commands/sync.md` :148, :206-218 and :386-394
  - `concepts/git-branching-model.md:29`
  - `development/_index.md` :124-133
  - `workflows/parallel-development.md` :16/:24 and
    `workflows/repo-maintenance.md:56`
  - `tuis/board/how-to.md:484`, `reference.md` :594/:704-716, and
    `tuis/syncer/_index.md` :277/:289
  - `skills/aitask-pickrem.md:38` and `skills/aitask-pickweb.md:54`

  Add a new "Unsupported or damaged layouts" troubleshooting section: the
  state and reason table, the C4 recovery for each row, and the conversion
  procedure. Blog posts stay, as history.

  aidocs: `framework/aitasks_extension_points.md` :122-125 and
  `framework/tui_conventions.md:476`.

  Deliverable: a **website sweep report** in Final Implementation Notes,
  listing every page and section reviewed, the change made, and each retained
  reference with its justification.

  Validation: `hugo build --gc --minify`, `python3 check_links.py --build`,
  and a triaged `check_link_relevance.py`.

**Wave 5** (depends on all):
- **t2074_13 `legacy_removal_final_rescan`** (chore).
  - Reconcile t1619, t1625, t1678, t1984, t1708 and t1796 through the normal
    workflow.
  - Repeat the framework-wide scan, covering explicit terms and implicit
    fallbacks (`git -C .aitask-data … || git`, `["git"]`, `-d aitasks && ! -L`,
    bare `.aitask-data/.git` existence tests, `_AIT_DATA_WORKTREE`).
  - Classify every remaining match as historical, rejection test, setup-only
    conversion or repair, or unrelated, and record the table.
  - Carries the post-phase `legacy_branch_tripwire`.

After the children are created, offer a manual-verification sibling. It would
cover:
- the TTY setup on a fresh repo;
- migrating a real legacy project, where a decline aborts with nothing
  changed;
- a refusal followed by the advertised repair for each broken reason;
- the board and `./ait` refusal text;
- the upgrade notice.

## Parent acceptance (retained here)

Every acceptance criterion in the task stays on this parent, and is checked at
archival against t2074_13's report.

## Post-implementation (Step 9)

Each child follows Step 9 on its own. The parent archives when its last child
does.

### Post-phase (risk mitigations)
1. [legacy_branch_tripwire] (carried by t2074_13) Add
   `tests/test_no_legacy_layout_branches.sh`.
   - It fails if any of these returns to `.aitask-scripts/` or `install.sh`:
     - `_AIT_DATA_WORKTREE="."`
     - `LEGACY_MODE` or `LEGACY_MODE_SKIP`
     - an `ait_data_mode` legacy branch
     - a plain-`git` fallback for task data
     - a bare `.aitask-data/.git` existence test used as acceptance outside
       the classifier
   - A per-line allowlist covers the setup-only migration and repair.
   - A planted-probe control proves each pattern fires.
2. [remote_skill_init_smoke] (carried by t2074_9) Freshly clone a branch-mode
   repo, without running `ait setup`.
   - `aitask_init_data.sh` must print `INITIALIZED`, and then the classifier
     must report `branch`.
   - A legacy clone must give `NEEDS_CONVERSION` (exit 3).
   - A clone with no data branch must give `NO_DATA_BRANCH` (exit 3).
   - Both of those must drive the pickrem/pickweb Stopped-banner path.

## Verification (whole effort)

- `bash tests/run_all_python_tests.sh`: the last line must read
  `PYTHON SUITE: PASSED`. Run it with `set -o pipefail`.
- Run every `tests/test_*.sh` individually.
- `./.aitask-scripts/aitask_skill_verify.sh` and
  `tests/test_skill_render_*.sh`.
- `shellcheck .aitask-scripts/aitask_*.sh`.
- `cd website && hugo build --gc --minify && python3 check_links.py --build`.
- Run a real fresh `ait setup` in a temp repo, once with `origin` and once
  without.
- In a real legacy temp repo:
  - `./ait ls`, `./ait git status` and a direct
    `aitask_update.sh --batch` (no `--commit`) are all refused, with the
    manifest unchanged;
  - then `ait setup` converts it, with the data byte-identical
    (`diff -r` against a pre-conversion copy).
- For each repairable broken fixture: the refusal, then `ait setup`, then the
  state reads `branch`. For each non-repairable one: the refusal and the
  printed manual steps, then the state reads `branch`.

## Risk

### Code-health risk: high
- Flipping rung 4 and tightening rungs 1-3 breaks test files no batch
  converted. About 125 files rely on implicit legacy fixtures, and the
  clone-style branch fixtures would be rejected
  · severity: high · → mitigation: inline pre-phase measure_flip_breakage
- Later work reintroduces legacy branches or bare marker acceptance
  · severity: medium · → mitigation: inline post-phase legacy_branch_tripwire
- A `die` inside `$( )` is masked by `local`, or a writer guard returns before
  validating, so an unsupported layout gets written
  · severity: high · → mitigation: covered by C2 and C3 and by the t2074_9
  no-mutation tests (with/without `--commit` and the bypass variable)
- Collision with t2064 on `task_utils.sh` and shared tests
  · severity: medium · → mitigation: covered by the shared-file gate and
  `depends:` on t2074_8 and t2074_9; the classifier is placed in the clean
  `data_symlinks.sh`
- Validation adds git calls to every process
  · severity: low · → mitigation: covered by C1's filesystem-first checks,
  the per-process cache and the differential test

### Goal-achievement risk: medium
- Remote and web Step 0a flows that relied on "proceed silently" now abort
  · severity: medium · → mitigation: inline post-phase remote_skill_init_smoke
- Advertised recoveries don't actually fix the state they are printed for
  · severity: medium · → mitigation: covered by the C4 matrix and t2074_3's
  refusal → recovery → re-read tests on the same fixture
- A missed implicit fallback or website page still implies legacy support
  · severity: medium · → mitigation: covered by the t2074_13 rescan and the
  website report
- Existing legacy users are blocked after upgrade until they run `ait setup`
  · severity: low · → mitigation: covered by the upgrade notice, the
  state-specific refusal and the MV sibling

### Planned mitigations
- timing: pre-phase | name: measure_flip_breakage | type: test | priority: high | effort: medium | inline_risk: low | added_complexity: low | addresses: flip breaks unconverted tests | desc: isolated-worktree full-suite run under the enforcement probe; per-case failing set and retired-case allowlist per batch
- timing: post-phase | name: legacy_branch_tripwire | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: legacy branches reintroduced | desc: source-tripwire test with planted-probe control and setup-migration allowlist
- timing: post-phase | name: remote_skill_init_smoke | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: remote/web Step 0a aborts unexpectedly | desc: fresh-clone init_data smoke covering INITIALIZED / NEEDS_CONVERSION / NO_DATA_BRANCH paths
