---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: performance
status: Done
labels: [backend, verification]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 635
implemented_with: claudecode/opus5
created_at: 2026-08-10 14:56
updated_at: 2026-08-10 18:52
completed_at: 2026-08-10 18:52
---

## Origin

Spawned from t1416 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_ls.sh:177-198 — build_dep_satisfied_set spawns one
  aitask_gate.sh subprocess per gated active task, making ait ls ~12.5s on this
  repo (307 candidates x ~47ms each)`

## Diagnostic context

Measured while sizing t1416's cost probe, not while chasing a bug — which is why
it had gone unnoticed: `ait ls` has simply always been slow, and nothing
attributed the cost.

`build_dep_satisfied_set()` greps for every active task whose frontmatter carries
`gates:` / `active_gates:` / `also_blocks_dependents:`, then loops:

```bash
decision=$(TASK_DIR="$TASK_DIR" "$gate_script" deps-unblock "$id" ...)
```

Each iteration is a fresh `aitask_gate.sh` process which in turn starts a fresh
Python interpreter to run `gate_ledger.py deps-unblock`. Measured on the
framework repo: one call ~47 ms, 307 candidates, `time ait ls 15` = **12.5 s** —
i.e. essentially the entire runtime of `ait ls`.

The `aitask_gate.sh` comment above the verb claimed it was "a new, low-frequency
decision (only on `ait ls`, only for gated active tasks)"; t1416 corrected that
comment, but not the fan-out itself, which was out of its scope.

## Why it matters more after t1416

t1416 made `deps-unblock` re-validate a code-bound human-gate signature. The
no-git pre-filter keeps that free for a task with no stamped witness, but each
task that DOES carry one adds a `code_digest()` (~5 ms). Because every task is
its own process, the lazy digest cannot amortize, so the added cost is linear in
the number of signed tasks: +2.2% at W=50, crossing +10% at **W≈230**. Batching
removes that scaling concern entirely as a side effect.

## Suggested fix

Add a batched verb — `gate_ledger.py deps-unblock-batch` reading task files (or
ids) from stdin and printing `<id> <decision>` lines — and have
`build_dep_satisfied_set()` feed it its whole candidate list in ONE process.
Expected: 307 subprocesses → 1, ~12.5 s → well under 1 s, and one `code_digest()`
for the entire `ait ls` instead of one per signed task (pass it down via
`dependents_status(..., current_digest=...)`, which already accepts it).

Keep the per-task verb: `tests/test_dependency_unblock.sh` asserts shell/python
parity on it, and other callers use it as a single-task decision.

## Verification

- `tests/test_dependency_unblock.sh` must stay green, including its `:111`
  shell/python parity assertion.
- A new test pinning that the batch verb and the per-task verb return identical
  decisions for the same fixture set (they must not become two implementations).
- Before/after timing of `ait ls` on a repo with a few hundred gated tasks,
  measured within one run (this box runs concurrent agents, so cross-run absolute
  numbers are not comparable).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-10T14:54:20Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-10T15:43:13Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-10T15:51:59Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:964da9803a4f1930

> **✅ gate:risk_evaluated** run=2026-08-10T15:51:59Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1472/risk_evaluated_2026-08-10T15:51:59Z-risk_evaluated-a1.log`
