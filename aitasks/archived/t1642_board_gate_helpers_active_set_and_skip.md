---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [board, gates]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1595
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-08-30 19:35
updated_at: 2026-08-31 09:14
completed_at: 2026-08-31 09:14
---

## Origin

Spawned from t1603_2 during Step 8b review. t1603_2 built the board's
workflow-phase derivation seam and deliberately **did not reuse** the two
helpers below, because each carries one of the defects recorded here. That
divergence is documented at the seam's call site as an accepted residual; this
task is the reconciliation.

## Upstream defect

- `.aitask-scripts/board/aitask_board.py:1846-1861` — `_human_pending_gates`
  tests `current.status != "pass"`, so a gate whose current run is `skip`
  (terminal-satisfied per `gate_ledger.SATISFIED_STATUSES == {"pass", "skip"}`,
  and therefore absent from `archive_pending`) is reported as a pending human
  gate. A task at `archive_decision == "ALL_PASS"` with a skipped
  `review_approved` shows "pending human gate" in the in-flight view and lands
  in the `human` actor column, when nothing is in fact owed.
- `.aitask-scripts/board/aitask_board.py:1864-1872` — `_has_failed_gate`
  iterates all of `state.current` minus `filtered_gates`. A gate deleted
  outright from the task's `gates:` field is in **neither** `active_gates` nor
  `filtered_gates` — `gate_ledger.read_active_tuple_from_text`
  (`gate_ledger.py:732-738`) fills `filtered` only from `active_gates_filtered`
  and otherwise falls back to `[]` — so a stale historical `fail` for such a
  gate still classifies the task as having a failed gate. This contradicts
  `TaskGateState`'s own documented rule that decision surfaces must key off the
  active set (`gate_ledger.py:162-165`).

## Diagnostic context

Both were found while writing t1603_2's phase ladder against the same inputs.
The fix t1603_2 applied for its own seam is the shape that resolves both here:

- derive the pending-human set from `state.archive_pending` filtered by the
  registry's `type == "human"`, rather than from a raw status comparison. That
  inherits `gate_ledger._gate_satisfied` (so `skip` is satisfied and a stale
  signature is not), and it is active-set-scoped for free because
  `archive_pending` is a subset of `active_gates` by construction
  (`gate_ledger.py:2101` passes `active`);
- derive the failed set by iterating `state.active_gates` and inspecting each
  one's current run, rather than scanning all of `state.current`.

See `derive_workflow_phase` in `aitask_board.py` for the worked form, and
`tests/test_board_workflow_phase.py` — `test_skipped_human_gate_is_satisfied_not_pending`
and `test_inactive_historical_failure_does_not_classify` — for fixtures that
already pin the correct behavior on the new seam.

## Suggested fix

Rewrite both helpers in the shape above and have `_inflight_item_for` consume
them unchanged. Note this **changes the actor grouping** for the two cases, so
`tests/test_board_inflight_view.py` needs cases for a skipped human gate and for
a historical failure of a gate absent from both lists. Consider whether the two
helpers should simply delegate to the same predicates `derive_workflow_phase`
computes, so the phase axis and the actor axis cannot disagree.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-30T20:24:14Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-31T06:03:39Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-31T06:14:54Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:2d54dba359824386

> **✅ gate:risk_evaluated** run=2026-08-31T06:14:54Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1642/risk_evaluated_2026-08-31T06:14:54Z-risk_evaluated-a1.log`
