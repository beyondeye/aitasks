---
priority: high
effort: high
depends: [t2074_1, t2074_3, 2064]
issue_type: refactor
status: Ready
labels: [framework, git, data_integrity, bash_scripts, task-workflow]
gates: [risk_evaluated]
folded_tasks: [2074_2, 2074_10]
anchor: 2074
created_at: 2026-10-20 12:33
updated_at: 2026-10-20 17:01
---

## Context

This task is part of t2074, which was rescoped to **branch-mode layout
hardening**. **Legacy mode stays supported and must not change.** This child
enforces the strict layout classification that t2074_1 provides. It absorbs
t2074_2 (fixture preparation, see **Step A** below) and t2074_10 (Python and
board enforcement, see **Step C** below). Each is carried in its `## Merged
from` section.

The binding contract is in `aiplans/p2074_branch_mode_layout_hardening.md`:
the C1a/C1b states, the **enforcement table** and the wiring. Read it first.

Depends on t2074_1 (classifiers and `lib/data_layout.py`), t2074_3 (setup
repair, which the missing-storage test uses) and t2064 (shared files).

## Enforcement table (the source for every wiring choice and test)

Every refusal names its recovery.

| Situation | Git routing (`task_git`, sync, push, `./ait git`) | Named readers / all writers |
|---|---|---|
| C1a `branch`, C1b `ready` | runs | runs |
| C1a `branch`, C1b `unlinked` | runs | refuse → `--link-worktree` |
| C1a `branch`, C1b `misdirected` / `dangling` / `mixed` | runs | refuse → `ait setup` repair (manual steps for `mixed`) |
| C1a `broken:*` (incl. `missing_storage`) or `indeterminate` | refuse | refuse |
| C1a `legacy` / `uninitialized` | unchanged (plain git) | unchanged |

## Step 0: shared-file gate (first)

For `.aitask-scripts/lib/task_utils.sh`, `tests/test_task_push.sh` and
`tests/test_task_git.sh`:
- `git diff --quiet -- <file>` must pass, and t2064's commit must appear in
  `git log`.
- Re-check immediately before the first edit.
- Do the non-overlapping work first.
- If the gate still fails, stop and ask the user.

Also read this task's `## Inbox`: t2074_1 may hand over the `git-health` item.

## Step A: fixture preparation

See `## Merged from t2074_2` below. It must land before Step B's enforcement.

## Step B: shell enforcement

1. **Rung validation in `_ait_detect_data_worktree` (`task_utils.sh:77-147`),
   the git class.**
   - Rungs 1–3 validate the marker they find, using C1a.
   - Rung 4 classifies first: `broken:missing_storage` dies, and only
     `legacy` and `uninitialized` still answer `"."`.
   - Broken states die with their recovery.
2. **Writer guard, the writer class.** `assert_task_data_writable` (`:487`)
   calls `ait_require_data_paths` **first**, before the
   `AIT_GIT_SKIP_STATE_CHECK` bypass. The bypass then skips only the wedge
   check. `assert_data_worktree_clean` (`:434`) checks C1a only.
3. **Writer audit.** Every writer must reach the guard before its first write,
   with or without `--commit`: update (`aitask_update.sh` :677/:1602/:1874/:2291),
   create, archive, fold, note, gate, plan_externalize, board column and the
   atomic-write callers.
4. **Reader guards, a named and narrowed contract.** Add guards to
   `aitask_ls.sh` and to every subcommand of `aitask_query_files.sh`. In each
   file the order is:
   1. `cross_repo_reexec_or_continue` (`aitask_ls.sh:20`,
      `aitask_query_files.sh:639`);
   2. then argument parsing and the help/usage exits (`aitask_ls.sh:206-222`,
      `aitask_query_files.sh:44/647-653/713`);
   3. then `ait_require_data_paths`, just before the first task-data read.

   Other readers (stats, codebrowser, explain_context, monitor, trails) are
   out of scope by design.
5. **errexit audit.** Cover every new die path. That means every
   `local x="$(…)"` call site and every `if`- or `||`-guarded call site of the
   detection accessors. Each site gets a test.
6. **`git-health` state reporting**, if t2074_1 handed it over.
7. Legacy behaviour stays untouched: the `LEGACY_MODE` and `LEGACY_MODE_SKIP`
   tokens, plain-git passthrough, and the setup prompt.

### Step B tests (new `tests/test_data_layout_refusal.sh`, derived from the table)

- **Broken states:** every class refuses.
- **`unlinked`:** git routing works (`./ait git status`, `task_git log`, and
  `task_sync` against a remote fixture), while readers and writers refuse.
- **`legacy` and `uninitialized`:** positive controls, unchanged.
- **Fixture data:** each fixture carries dirty, untracked and ignored data
  (`aitasks/new/` drafts, a gitignored file under `aiplans/`).
- **Commands under test:**
  - `task_git add/commit`, `task_sync`, `task_push`, `./ait git pull/push`
  - `aitask_task_commit.sh`, `aitask_archive.sh`
  - `aitask_update.sh --batch` **without `--commit`**, both with and without
    `AIT_GIT_SKIP_STATE_CHECK=1`
- **No-mutation proof:**
  - a before/after manifest (type, symlink target, mode, sha256) of
    `aitasks/`, `aiplans/` and `.aitask-data/`, ignored and untracked files
    included;
  - snapshots of both repos (HEAD, every ref, `ls-files -s`,
    `status --porcelain --ignored`) and of the bare remote's refs;
  - a positive control for each case;
  - a planted write-before-refusal mutant, which must make the comparison
    fail.
- **Missing storage:**
  1. Delete `.aitask-data` in a fixture that has a remote.
  2. `task_git commit`, `./ait git push` and `aitask_update.sh --batch` all
     refuse, and no commit lands on the code branch (check the HEAD, refs and
     index snapshots).
  3. `ait setup` restores the layout (t2074_3).
  4. Both classifiers re-read `branch` / `ready`.
- **Bisect recovery:** mid-bisect in the data worktree,
  `./ait git bisect reset` succeeds and `./ait git status` works. A write
  still refuses via the wedge check.
- **Representative reads:** `./ait ls` and `aitask_query_files.sh resolve <n>`
  refuse on `misdirected` and on `unlinked`. They work in `ready`, in `legacy`
  and inside `.aitask-data`.
- **Reader ordering**, for both readers:
  - a broken source with a healthy `--project` destination succeeds;
  - a healthy source with a broken destination refuses with the destination's
    state;
  - `--help`, and `aitask_query_files.sh` with no subcommand, exit 0 on a
    broken layout.
- **T13c / T13d acceptance:**
  - git operations work from both shapes;
  - a writer works inside `.aitask-data`;
  - a writer refuses in an unlinked worktree and creates no real `aitasks/`.
- **errexit:** one test per audited site.

## Step C: Python and board enforcement

See `## Merged from t2074_10` below.

## Verification (whole child)

- Every `tests/test_*.sh`, run individually.
- `bash tests/run_all_python_tests.sh`: the last line must read
  `PYTHON SUITE: PASSED`. Use `set -o pipefail`.
- `shellcheck .aitask-scripts/aitask_*.sh`.

## Merged from t2074_2: branch mode test fixtures


## Context

This is part of t2074 (rescoped: branch-mode layout hardening). **Legacy mode
stays supported.** t2074_9 makes the classification stricter (t2074_1's C1a
validation: live worktree, same repository, right branch). Some **branch-mode**
test fixtures build `.aitask-data` as a standalone repo, a clone, or a bare
`mkdir` stub instead of a registered worktree. The strict validation rejects
those fixtures as `broken:*`.

This work prepares those fixtures **before** enforcement lands. It is merged
into t2074_9 as that child's **Step A**. The binding contract is in
`aiplans/p2074_branch_mode_layout_hardening.md`.

## Scope (Step A)

Convert only the branch-mode fixtures that strict validation rejects. Keep each
fixture's signature, and read every builder before reusing it:
- `tests/lib/board_fixture.py` (`_layout`/`build_tree`/`build_fixture_tree`,
  `branch_mode=True`)
- `tests/lib/metadata_update_fixture.sh:188`
- `tests/test_task_push.sh:158 setup_branch_mode` (it moves a clone into
  `.aitask-data`). This is behind the t2064 shared-file gate in t2074_9
  Step 0.
- `tests/test_remote_drift_check.sh:111 mark_branch_mode` (a `mkdir
  .aitask-data` stub)
- `tests/test_plan_approved_marker_drift.sh:86` (a `mkdir -p
  .aitask-data/.git` stub)

Add a shared helper, `tests/lib/data_branch_fixture.sh`:
- `ait_fixture_to_branch_mode <repo> [--remote <bare>]`: a registered orphan
  `aitask-data` worktree at `.aitask-data`, built with production
  `ait_ensure_data_symlinks`, the `.gitignore` entries and the main-index
  removal. It pushes the data branch when a remote is given.
- `fixture_data_git`

Self-test: the helper's layout must classify `branch`/`ready`, the same as a
real `setup_data_branch` layout.

**Legacy fixtures stay unchanged.** Do not convert them.

**Measurement.** Run the whole suite once with the Step B validation applied
as a throwaway patch in an isolated `git worktree`. Never commit the patch.
This finds any other stubbed or clone-style branch layout; convert those too,
and record the list.

## Verification

- The self-test passes.
- Every test that uses a converted fixture passes: the board Python tests,
  `test_task_push.sh`, `test_remote_drift_check.sh`,
  `test_plan_approved_marker_drift.sh`, `test_usage_update.sh` and
  `test_verified_update.sh`.

## Merged from t2074_10: python layout enforcement


## Context

This task is part of t2074, rescoped to branch-mode layout hardening. **Legacy
mode stays supported.** It brings the board into line with the layout
enforcement table, and it is merged into t2074_9 as that child's **Step C**.
The binding contract is in `aiplans/p2074_branch_mode_layout_hardening.md`.

The bug: `board/board_task_manager.py:66` `_task_git_cmd` probes the
cwd-relative `./.aitask-data/.git` and otherwise falls back to `["git"]`. When
the board runs in branch mode from a cwd other than the repo root, it targets
the code repo. It also never re-validates during its long life.

## Scope (Step C)

**Repo-root resolution, validated fresh.** `_task_git_cmd` resolves from the
repo root, not the cwd. It **validates fresh on every call** through
`lib/data_layout.py` (from t2074_1) and never uses the cached `snapshot()`. A
worktree that was valid at startup can switch branches or break later, and the
same `git -C` prefix would then silently target the new branch.

**Two named operation classes**, following the enforcement table:
- **Git inspection of the data worktree (C1a only)**, via
  `require_repo_branch()`. This covers read-only status/dirty indicators, log,
  diff and show. These still run while C1b is `misdirected`, `dangling`,
  `mixed` or `unlinked`.
- **Mutations (C1a and C1b)**, via `require_branch_ready()`, checked
  immediately before each operation. This covers task-file edits,
  column/board-index moves, revert (`git checkout --`,
  `board_detail_screen.py:59,1970`), delete (`git rm -f`,
  `aitask_board.py:6629`) and any board-initiated commit.

`_task_git_cmd` takes an explicit class argument. A test enumerates every
caller and asserts its class.

Behaviour by state:
- In `legacy` or `uninitialized`, return `["git"]` explicitly, as today.
- A broken state raises with its recovery.
- Callers surface the error and never fall back to plain git.

**Board startup** applies the reader-class check and refuses, with the recovery
text, on a branch layout that is not ready. The sync gate at
`aitask_board.py:236` and `:2851` becomes an explicit refusal toast for broken
branch layouts. Legacy behaviour is unchanged.

**Not touched:** `desync_state`, `cross_repo_settings` and
`REASON_DEST_LEGACY_LAYOUT`.

## Tests

- From a non-root cwd, a valid layout resolves to the data worktree.
- A broken `board_fixture` is refused, and no git command runs against the
  code repo.
- The legacy board fixture still works.

**Same-process transitions.** Each transition gets its own test, and the
expected outcomes come from the enforcement table. Every test runs in one
process (`App.run_test` or the `board_task_manager` API). It starts from a valid
layout, where one inspection and one mutation both succeed, then applies the
transition:
- **(a) Branch switch** (`broken:wrong_branch`): inspection and every mutation
  refuse.
- **(b) `.aitask-data` deleted** (`broken:missing_storage`): inspection and
  every mutation refuse, with no plain-git fallback.
- **(c) `aitasks` repointed to another existing dir** (`branch`/`misdirected`):
  inspection succeeds; edit, revert and delete each refuse.

Every refusal must prove nothing changed:
- the content manifest is unchanged, including the redirected-to dir in (c);
- the HEAD, refs and index snapshots of both the data repo and the code repo
  are unchanged.

Planted control: a variant that reads the cached `snapshot()` must fail
case (a).

## Verification

Run `bash tests/run_all_python_tests.sh`. The last line must read
`PYTHON SUITE: PASSED`.

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t2074_2** (`t2074_2_branch_mode_test_fixtures.md`)
- **t2074_10** (`t2074_10_python_layout_enforcement.md`)
