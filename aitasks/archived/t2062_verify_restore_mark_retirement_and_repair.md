---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Done
labels: [frozen, session_persistence]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2040
followup_kind: review_finding
implemented_with: claudecode/opus5_5
created_at: 2026-10-19 15:04
updated_at: 2026-10-20 13:05
completed_at: 2026-10-20 13:05
---

## Origin

Review finding on t2045 (reconcile retires the frozen stamp after a confirm),
verified CONFIRMED by fault injection. It is pre-existing best-effort behaviour
shared by the restore coordinator; t2045 extended the same helper to reconcile
and did not regress it.

## The defect

`agent_frozen_ops.retire_restore_marks(pane, record_id, nonce)` (shared by
`agent_restore._clear_frozen_stamp` and `agent_freeze._reconcile_restoring`)
issues the two guarded clears (`clear_stamp_if`, `clear_restore_attempt`) and
never checks they took. By then the record has already been confirmed `live`,
and the callers return `RESTORED:` / `LIVE:` regardless.

Repro (in `tests/test_agent_freeze.py` `ReconcileRestoringTests`, using the
`_abandoned_and_marked` / `_recover` helpers t2045 added): set
`self.tmux.set_option_ok = False` before `_recover`. The result is
`LIVE:<id>|liveness` with `@aitask_frozen=<id>` and the attempt mark both
still on the pane. After `set_option_ok = True`, `freeze_pane(AGENT_PANE)` still
returns `FREEZE_SKIPPED:<id>|already frozen`. Later reconcile passes skip
`live` records, so a transient tmux failure becomes a permanent restriction:
the recovered agent can never be frozen again.

**Checking the `if-shell` exit status is not enough.** Its branch can fail
while `if-shell` itself reports success (the fake models this, and so does
real tmux).

## Fix direction

- Verify the clear by re-reading the pane (`frozen_ops.window_facts` /
  `pane_facts`). Report a retained stamp distinctly. Do NOT report it as a
  clean `RESTORED:` / `LIVE:`; a `WARNING:` line or a detail suffix works.
- Provide a guarded repair path for a `live` record whose own tracked pane
  (pane_pid == the record's pane_pid) still carries `@aitask_frozen == <id>`.
  Options: reconcile's pass over `live` records only for this one shape, or
  `freeze_pane` treating "stamp names a `live` record whose pane_pid matches
  this pane's live process" as stale rather than "already frozen". Keep the
  t1875 recycled-`%N` rule: every clear stays a guarded single dispatch.
- Tests: failure injection on both clears for both engines (coordinator and
  reconcile), plus a negative control where the stamp is legitimately live
  (a mounted stand-in of a `frozen` record is never "repaired").

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-20T09:23:35Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-20T10:04:32Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-20T10:05:45Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:4b43aefac56a3199

> **✅ gate:risk_evaluated** run=2026-10-20T10:05:45Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2062/risk_evaluated_2026-10-20T10:05:45Z-risk_evaluated-a1.log`
