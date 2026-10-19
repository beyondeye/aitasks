---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [frozen, session_persistence]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2040
followup_kind: risk_mitigation
implemented_with: claudecode/opus5_5
created_at: 2026-10-19 15:39
updated_at: 2026-10-19 17:12
---

## Origin

Risk-mitigation ("after") follow-up for t2045, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement: attempt mark not retired after a replaced op_nonce

- The attempt mark is not retired when an earlier failed reconcile lease replaced
  `op_nonce` (documented residual; stamp is still cleared, so the
  freeze-again goal holds) · severity: low · → mitigation: retire_mark_after_replaced_lease

## Goal

t2045 made `agent_freeze._reconcile_restoring` retire the pane's marks after a
successful `restore-confirm`. It derives the gone-pane attempt mark's value
(`@aitask_restore_attempt=<id>:<nonce8>`) from the PRE-lease `rec["op_nonce"]`,
which is the coordinator's nonce. That nonce is lost when an EARLIER reconcile
pass took the lease on the same `restoring` record and then failed to settle it
(`RECONCILE_FAILED` on `restore-confirm` or on the abort path, i.e. store
errors). The next pass's pre-lease `op_nonce` is then that dead pass's nonce.
The stamp still clears, but the mark stays. A lingering mark makes the live
tracked pane read as a restore survivor of its own record
(`frozen_ops.find_restore_survivors`) whenever no stand-in is mounted.

This follow-up must:
- In reconcile's restoring confirm branch, recover the mark from the pane itself
  when the nonce-derived value does not match. Read the pane's mark
  (`frozen_ops.window_facts`); if it claims this record
  (`restore_attempt_record("", mark) == record_id`), clear it under a COMPOUND
  single-dispatch guard: mark value AND `pane_pid == launch_pid`. This keeps the
  t1875 recycled-`%N` rule.
- Extend `tests/test_agent_freeze.py`'s `_FakeTmux._if_shell` to evaluate
  compound `#{&&:…,…}` conditions. Today it only parses `#{==:#{opt},val}`.
- Tests: the replaced-nonce shape (the stale lease nonce is in `op_nonce`)
  retires the mark. Negative control: another record's mark on the pane, or a
  different pane_pid, is kept.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-19T14:12:33Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-19T14:26:54Z status=pass attempt=1 type=human
