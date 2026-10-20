---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [framework, git, data_integrity, bash_scripts]
gates: [risk_evaluated]
anchor: 2074
created_at: 2026-10-20 12:31
updated_at: 2026-10-20 12:31
---

## Context

This is the first child of t2074, which removes legacy repository mode (task data
kept on the code branch with no `aitask-data` branch). It also sets the
**foundation** that every later child builds on. The binding contract is
**C0, C1a and C1b** in `aiplans/p2074_remove_legacy_repository_mode_support.md`
(section "Target contract"). Read that section first; this task implements C1a
and C1b exactly as written there.

The problem today: detection in `_ait_detect_data_worktree`
(`.aitask-scripts/lib/task_utils.sh:77-147`) accepts a layout as soon as
`.aitask-data/.git` exists. It does not check ownership, branch or links. When
it finds no marker, rung 4 falls through to `"."`, which is legacy. Before
enforcement can replace rung 4 (t2074_9), the framework needs classifiers that
report states and **never die**.

**This task is additive only.** No existing caller changes behaviour.

## Deliverables

1. In `.aitask-scripts/lib/data_symlinks.sh` (sourced by `task_utils.sh:26`, and
   with no in-flight edits), add `ait_data_repo_state` (C1a) and
   `ait_data_paths_state` (C1b).
   - Both print `<state>[:<reason>]` and always return 0, including under
     `set -euo pipefail`, inside `$( )` and inside `local x="$( )"`.
   - **Neither ever terminates.** That includes indeterminate topology, which
     returns `indeterminate:topology`.
   - C1a resolution order:
     1. The cwd is inside the data worktree itself (preserves T13c of
        `tests/test_task_git.sh`).
     2. A local `./.aitask-data`, then `<toplevel>/.aitask-data`. A usable
        separate-git-dir primary resolves here **without**
        `ait_main_worktree_root`.
     3. The main checkout's marker via `ait_main_worktree_root` (preserves the
        T13d unlinked crew worktree case). When that returns 2, use the
        `ait_linked_worktree_roots` proof as in today's rung 3: if this
        checkout is provably not linked, fall through to step 4; otherwise
        answer `indeterminate:topology`.
     4. No marker: `legacy` (a real `aitasks/` at the toplevel), otherwise
        `uninitialized`. Outside any work tree: `not_a_repo`.
   - Validation of a resolved `<data>`, in order: `broken:stale_marker` (not a
     live worktree toplevel), `broken:foreign_repo` (the canonical
     `git-common-dir` differs), `broken:wrong_branch` (HEAD is not
     `refs/heads/aitask-data`; during a rebase, read `rebase-*/head-name`
     instead, because a rebase in progress is valid and wedged, not broken).
   - C1b: precondition C1a = `branch`. The states are:
     - `ready`: `canon($PWD/$TASK_DIR)` == `canon(<data>/aitasks)` and the same
       for `PLAN_DIR`.
     - `unlinked`: the paths are absent in a linked worktree.
     - `misdirected`: a path resolves elsewhere. This includes a `TASK_DIR`
       override outside `<data>`.
     - `dangling`
     - `mixed`: a real dir next to a valid data worktree.
   - Run filesystem-first checks (gitdir file, `commondir`, `HEAD`, `readlink`)
     with a git fallback. Cache once per process.
2. A new CLI, `.aitask-scripts/aitask_data_layout.sh`, that prints both states
   (one line per classifier) for the cwd. Follow
   `aidocs/framework/aitasks_extension_points.md` for adding a helper script:
   permission whitelists and every listed touchpoint.
3. A new `.aitask-scripts/lib/data_layout.py`. Python consumes the CLI **once
   per process** and never re-implements the checks.
4. `./ait git-health` (`task_git_health`, `task_utils.sh:513`) additionally
   prints the C1a/C1b state and reason. Leave the existing legacy line in place
   for t2074_9 to remove. **Shared-file gate:** `task_utils.sh` carries
   uncommitted t2064 hunks. If they are still there, skip this item and
   hand it to t2074_9 with `./ait note`. Do not edit the file.

## Tests

Add a new `tests/test_data_layout_classifier.sh`, using the file-backed counters
from CLAUDE.md if any case runs in a subshell.

**Fixtures.** One fixture per state and reason:
- stale gitdir file;
- empty `.git`;
- pruned admin dir;
- unrelated repo at `.aitask-data`;
- a clone at `.aitask-data`;
- a worktree of another repo;
- wrong branch;
- mixed layout;
- dangling, misdirected (resolving to an existing other dir) and missing links;
- a `TASK_DIR` override outside `<data>`.

**Positive cases:**
- mid-rebase;
- T13c (cwd inside `.aitask-data`): `branch` / `ready`;
- T13d (unlinked crew worktree): `branch` / `unlinked`;
- a `--link-worktree`'d worktree: `branch` / `ready`;
- a usable separate-git-dir primary: `branch`, with no main-root call;
- its unresolved linked checkout: `indeterminate:topology`, returned rather
  than died;
- a submodule or nested repo: its own repository's state.

**Also add:**
- a never-dies test under errexit for every fixture;
- a filesystem-vs-git differential;
- a Python/shell parity test, as `tests/test_data_layout.py`.

## Verification

- `bash tests/test_data_layout_classifier.sh`
- `bash tests/run_all_python_tests.sh --test-dir` for the new Python test
- `shellcheck` on the new script
- the existing `tests/test_task_git.sh` and `tests/test_init_data.sh` stay green
  (no behaviour change)

## Notes

Retire nothing here. The enforcers (`ait_require_data_repo` /
`ait_require_data_paths`) belong to t2074_9.
