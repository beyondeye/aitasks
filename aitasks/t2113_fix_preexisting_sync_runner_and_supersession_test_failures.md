---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [testing, macos]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2096
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-21 17:14
updated_at: 2026-10-21 17:41
---

## Origin

Spawned from t2096 during Step 8b review. Both failures were seen on the
**unfixed** `main` tree (baseline full Python suite, 2026-10-21, macOS,
runner=unittest — pytest not installed) and identically after t2096's change;
t2096 touches neither module.

## Upstream defect

- `tests/test_sync_action_runner.py:643` — 9 `TimeoutContainmentTests` fail in
  `_assert_stopped` with `assertIsNone(result.stray_session)` (a stray session
  survives the timeout path): `test_a_runner_cut_down_by_the_term_cap_leaves_no_transport`,
  `test_a_runner_started_after_the_first_listing_is_still_stopped`,
  `test_a_stopped_runner_is_resumed_to_clean_up`,
  `test_control_an_uncoordinated_grace_falls_to_the_kill_rounds`,
  `test_timeout_stops_a_child_in_its_own_process_group`,
  `test_timeout_stops_a_nested_bounded_runner`,
  `test_timeout_stops_a_same_group_child`,
  `test_timeout_stops_an_fd_dropping_descendant`,
  `test_unprovable_stop_reports_the_session`.
- `tests/test_model_supersession.py:873` —
  `RobustnessTests.test_recovery_command_quotes_the_repository_path` fails:
  the command starts `cd '/private/var/folders/.../my project' && …` while the
  test expects `cd '<root>' && …`. Looks like the macOS `/var` → `/private/var`
  symlink: one side is realpath-resolved, the other is not.

## Diagnostic context

Found while establishing an attribution baseline for t2096 (the
`baseline_suite_before_rung` pre-phase). `PYTHON SUITE: FAILED (runner=unittest,
exit=1)`, `FAILED (failures=10, skipped=31)` on both the before and the after run.

Unknown whether the sync-runner failures are host-specific (load, process-table
timing) or deterministic — first step is to re-run the module alone and see
whether they reproduce.

## Suggested fix

- supersession: compare against `os.path.realpath(root)` (or resolve the
  command's path the same way) — decide which side is the contract.
- sync runner: reproduce in isolation, then diagnose why a session survives the
  containment path.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-21T14:41:03Z status=pass attempt=1 type=human
