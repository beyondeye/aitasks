---
priority: medium
effort: medium
depends: [t635_12]
issue_type: manual_verification
status: Ready
labels: [gates]
verifies: ['635_11']
created_at: 2026-06-17 00:35
updated_at: 2026-06-17 00:35
boardidx: 100
---

## Origin

Risk-mitigation ("after") follow-up for t635_11 (gate orchestrator + verifier
contract), created at Step 8d from the approved plan's risk evaluation.

## Risk addressed

Goal-achievement risk (medium): no concrete verifier exercises the engine until
t635_12 — t635_11 validated the orchestrator only against stub verifier scripts.
The live behavioral validation against a REAL verifier must run once one exists.

## Goal

Autonomously drive the live gate orchestrator (`ait gates run` /
`aitask-run-gates`) end-to-end against the FIRST real machine-gate verifier
(landed by t635_12), confirming the engine's runtime behavior — not just stubs.

## Verification checklist

- [ ] On a task declaring a real machine gate, `ait gates run <id>` dispatches the
      verifier and records the correct terminal status from its exit code.
- [ ] Retry-within-budget: a transient/failing verifier re-runs up to
      `max_retries+1`, then is reported exhausted.
- [ ] Stopping heuristic: two deterministic failures with NO code change stop early
      (do not burn the full budget); a real code fix re-enables the gate; the
      gate passes on the fixed tree (fail → fix → pass loop).
- [ ] Parallel dispatch: two unlocked machine gates run within `max_parallel_gates`
      and leave a well-formed ledger (no interleaving / duplicate terminals).
- [ ] Human gate: an unsignalled `file-touch` gate stays `pending` and the engine
      never self-signals; creating the signal file flips it to `pass` on re-run.
- [ ] Archive-readiness reflects skip-as-satisfied for any not-applicable gate.
