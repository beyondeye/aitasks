---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [gates]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 635
implemented_with: claudecode/opus5
created_at: 2026-07-27 09:15
updated_at: 2026-08-06 10:52
completed_at: 2026-08-06 10:52
boardidx: 47104
---

## Problem

`cmd_begin_procedure` (`.aitask-scripts/aitask_gate.sh:833-842`) derives the
attempt number as "existing gate-run marker count for this gate + 1". But a
completed attempt leaves **two** markers: the `running` block `begin-procedure`
opens, plus the terminal block the gate skill appends. So the counter advances
by 2 per attempt.

Observed live during the t635_27 gate verification on scratch task t1255:
`begin-procedure` reported ATTEMPT **1 -> 3 -> 5**.

`cmd_append`'s auto-increment path (`aitask_gate.sh:217-229`) uses the same
marker-count derivation and mis-numbers identically whenever `attempt=` is not
passed explicitly.

## Impact

Confined to the recorded `attempt=` ledger field and the `<attempt>` argument
handed to the gate skill. The orchestrator's retry budget is **not** affected:
`gate_orchestrator.py:_attempts_used()` counts terminal `fail`/`error` runs, so
budget enforcement is correct. This is a ledger-accuracy / reporting defect, not
a gating-correctness one.

## Fix direction

Count only terminal markers (`pass`/`fail`/`skip`/`error`), not every marker —
or track attempts off the same `_attempts_used()` notion the orchestrator uses,
so the bash and Python sides agree.

## Verification

Add a test asserting consecutive `begin-procedure` calls on a procedure gate
report 1, 2, 3 across full attempt cycles (running + terminal each).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-05T20:58:16Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-06T07:13:06Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-06T07:52:15Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:7458a3777669c8f0

> **✅ gate:risk_evaluated** run=2026-08-06T07:52:15Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1262/risk_evaluated_2026-08-06T07:52:15Z-risk_evaluated-a1.log`
