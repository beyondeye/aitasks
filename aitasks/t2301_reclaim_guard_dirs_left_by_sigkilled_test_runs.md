---
priority: low
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [tests, test_infrastructure, tmp_cleanup]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2290
implemented_with: claudecode/opus5_5
created_at: 2026-11-15 13:09
updated_at: 2026-11-19 10:21
---

## Problem

`tests/lib/tmpdir_guard.sh` (t2290) gives `tests/run_all_python_tests.sh` and
`tests/run_shell_test.sh` a private per-run `TMPDIR` and removes it on a normal
exit and on INT/TERM/HUP. A guarding shell that is **SIGKILLed** runs no
handler: its `ait_<label>_<pid>_*` directory stays under `/tmp`, and the phase's
process group (xdist workers, nested test shells) may outlive it and keep
writing there.

Today `tmpdir_guard_begin` only **reports** such directories (owner pid gone)
and never deletes them, because deleting safely needs liveness evidence for
the orphaned workers. Reclaim them automatically.

## Scope

- Record per-run metadata inside the guard dir at begin: owner pid + start
  time, and each phase's pgid (written by `tmpdir_guard_run`).
- Reclaim a reported dir only when ALL hold: owner dead (pid + starttime, so a
  recycled pid does not count as alive), every recorded pgid empty, and no
  process has its cwd or an open fd under the dir (`/proc/*/cwd`, `/proc/*/fd`;
  `lsof +D` fallback off Linux).
- When any of that cannot be verified (no /proc, no lsof, unreadable
  metadata, pre-metadata dir) keep the dir and keep reporting it. Unknown is
  never rounded up to dead.
- Cover the dead-wrapper-with-surviving-writer case explicitly: a dir whose
  owner is dead but whose pgid still has members is kept.
- Tests next to `tests/test_tmpdir_guard.sh` case (f): reclaimed when fully
  dead; kept with a live pgid member; kept with a cwd holder; kept when
  metadata is missing.

## References

- `tests/lib/tmpdir_guard.sh` ("NOT COVERED" header block, `tmpdir_guard_begin`)
- `aiplans/archived/p2290_stop_tests_and_helpers_leaking_tmp_dirs.md` (step 6 / step 8)

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-19T08:21:19Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-22T09:31:42Z status=pass attempt=1 type=human
