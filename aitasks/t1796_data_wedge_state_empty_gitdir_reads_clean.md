---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
anchor: 1733
followup_kind: upstream_defect
created_at: 2026-09-11 15:07
updated_at: 2026-09-11 15:07
---

## Origin

Spawned from t1747_3 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/task_utils.sh:236 — _ait_inprogress_state_at answers "clean" for an empty git-dir, so on an unresolvable branch-mode data git-dir _data_wedge_state (:290) reads "not wedged": assert_task_data_writable (:396) lets the write through, and ait_pull_mutex_acquire (:1076) returns 0 without taking the pull mutex. Same fail-open class as A10, outside the audited Group A.`

Line numbers are as of `b92aebc20` (t1747_3's code commit). Re-resolve them by
function name before editing.

## Diagnostic context

t1747_3 fixed row A10 of the fail-open git-probe sweep: `aitask_sync.sh::_sync_gitdir`.
The fix resolves the git-dir by **mode**, never by emptiness, through
`lib/task_utils.sh::_data_wedge_gitdir`, and returns 2 when the answer is empty. The
rule, the fix shape and the dispositions are documented in
`aidocs/framework/failopen_git_probes.md`.

That same helper family has a second, unaudited consumer path. `_data_wedge_gitdir`
answers `''` for an unresolvable branch-mode git-dir, and `_ait_inprogress_state_at`
returns 0 with empty stdout for an empty argument. So `_data_wedge_state` reports
"not wedged" for a git-dir it could not even locate. Two consumers read that result
bare:

- **`assert_task_data_writable`**, the pre-write guard at 16 sites across 9
  task-data writers. It returns 0 (writable) for a worktree whose state could not be
  inspected.
- **`ait_pull_mutex_acquire`**. Its `[[ -z "$gitdir" ]] && return 0` skips the pull
  mutex entirely. The function's comment calls this "the pre-existing behaviour".

t1747_3 measured the reachable route: from any linked worktree, including the
workflow's `aiwork/` worktrees and unlinked crew worktrees, `_ait_data_gitdir` misses
its fast path and runs `git -C .aitask-data rev-parse --absolute-git-dir`. When that
fails, the data git-dir cannot be resolved. With a PATH shim failing exactly that
verb, the unfixed `ait sync` published a withheld commit. The same condition reaches
these two task_utils consumers.

`_ait_detect_data_worktree` decides the mode from whether `.aitask-data/.git`
exists, and caches the result. So an unreadable git-dir does **not** flip detection
to legacy mode, and the mode-based resolution is sound. The gap is only in how the
empty answer is consumed.

## Suggested fix

- Give `_data_wedge_state` a distinct "could not inspect" status. Per the canonical
  doc, it should travel on the exit status, not stdout.
- Give each consumer an explicit disposition for it:
  - `assert_task_data_writable` should refuse, as it does for a wedge;
  - `ait_pull_mutex_acquire` should decide between refusing and a documented
    unlocked fallback.
- Enumerate every consumer of `_data_wedge_state` / `_ait_inprogress_state_at` /
  `_data_wedge_gitdir` in a call-site table, and pin that table with a test.
  t1747_3's `tests/test_sync_failopen_probes.sh` scan S is the shape to copy.

Coordinate with **t1740**, which plans to generalize `ait_pull_mutex_acquire` to
take a git-dir.
