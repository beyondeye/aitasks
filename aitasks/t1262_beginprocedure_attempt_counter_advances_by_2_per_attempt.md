---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [gates]
anchor: 635
created_at: 2026-07-27 09:15
updated_at: 2026-07-27 09:15
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
