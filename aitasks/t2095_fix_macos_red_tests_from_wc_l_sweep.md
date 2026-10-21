---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [bash_scripts, testing, macos, tests]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [2098]
assigned_to: dario-e@beyond-eye.com
anchor: 1681
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-21 12:18
updated_at: 2026-10-21 14:44
---

## Origin

Spawned from t1751 during Step 8b review. t1751 fixed BSD `wc -l` padding in
count assertions. Its sweep ran every `tests/**/*.sh` that uses `wc -l` on
macOS 15 / Darwin 24.6.0 (bash 5.3.9 and /bin/bash 3.2.57), and turned up
these **pre-existing failures that have nothing to do with padding**. Each was
reproduced serially, not only under the parallel sweep.

## Upstream defect

- `tests/test_revert_analyze_batch.sh:223-224` — the NUL-stream control
  asserts GNU grep's binary-file behaviour (0 matches); macOS grep returns 1,
  so the file is red on macOS.
- `tests/test_task_git.sh` cases 13b/13c/13d/15b and
  `tests/test_task_worktree_helper.sh` cases 3/5 — expected paths are built
  from `/var/folders/…` (`mktemp`/`$TMPDIR`), but the helpers return the
  realpath `/private/var/folders/…`. Red on macOS.
- `tests/test_scratchpad_spawn_live.sh:218` — its first `cd` has no
  `enter_scratch_cwd`, so `tests/test_cd_guard_lint.sh` fails 2 checks
  ("no cd/pushd guard violations", "every cwd-changing test calls
  enter_scratch_cwd first"). Platform-independent.
- `tests/test_fixture_root.sh` — the control "the old shape leaks all three
  (the probe can see a leak)" gets `0|0` instead of `0|3`, so the leak probe
  cannot see a leak.
- `tests/test_run_project_command.sh` — "G: an error verdict still reports its
  LOG" expects `set` but gets the log path
  (`/var/folders/…/aitask_verify_build_XXXX.log`).
- `tests/test_sync_deferral_and_quarantine.sh` — "self: and the action offers
  commit-on-behalf" and "other: and never offers commit-on-behalf" get a
  `DEFERRED_FILE:unknown_liveness|…|testhost|<pid>|…` record ("the holder could
  not be verified as gone") instead of the expected self/other action text.
  The fixture's holder liveness may not be verifiable on this host.

Already tracked elsewhere, not repeated here: `tests/test_shadow_phase_advisory.sh`
("all 9 capabilities still dispatched" gets 1/2) → t1779.

## Diagnostic context

t1751's first sweep only flagged padded values, so in files it fixed for
padding (`test_run_project_command.sh`, `test_sync_deferral_and_quarantine.sh`,
`test_revert_analyze_batch.sh`) the remaining failures surfaced only once the
padding was trimmed. All are present at the pre-t1751 HEAD (c108f7b4e) as well.
`test_crew_git_noninteractive.sh` failed only under parallel load and passes
serially, so it is not included.

## Suggested fix

Triage each one independently; they share no root cause. Consider splitting
into children. The realpath cases probably want `pwd -P` / `realpath` on the
expected side. The NUL control probably needs to pin the grep it tests, or
assert per platform. The cd-guard case needs one `enter_scratch_cwd` call.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-21T09:51:33Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-21T11:29:50Z status=pass attempt=1 type=human
