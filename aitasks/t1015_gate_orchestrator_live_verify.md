---
priority: medium
effort: medium
depends: [t635_12]
issue_type: manual_verification
status: Ready
labels: [gates]
verifies: ['635_11']
created_at: 2026-06-17 00:35
updated_at: 2026-06-28 18:14
boardidx: 300
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

## Available verifiers (from t635_12 — now landed)

t635_12 shipped the first real machine-gate verifiers, so this task can run now:
- `build_verified` → `aitask-gate-build` (project_config.yaml `verify_build`)
- `tests_pass` → `aitask-gate-tests-pass` (`test_command`)
- `lint` → `aitask-gate-lint` (`lint_command`)

All three are registered in `aitasks/metadata/gates.yaml` and **skip (exit 2)**
when their command is unset. To drive the checklist, point a scratch task's
`gates:` at one (e.g. `gates: [build_verified]`) with a `verify_build` set to a
controllable command (`true` / `false`) in a scratch `project_config.yaml`, then
run `ait gates run <id>`. See the t635_12 plan
(`aiplans/archived/p635/p635_12_build_test_machine_gates.md`) and
`tests/test_gate_verifiers.sh` for the exact fixture shapes.

## Coordination (from t635_14 — landed 2026-06-28)

t635_14 (profile→gate-declaration unification) makes profiles **declare** gates: the
shipped `fast` profile sets `default_gates: [risk_evaluated]`, so a real `ait`
pick under `fast` now exercises the orchestrator end-to-end **without scratch
fixtures** — a child created under `fast` declares `risk_evaluated`, and a picked
gateless task gets it backfilled at Step 7. The `aitask-gate-risk` verifier
(t635_13) is the live machine gate. So this MV can additionally verify the *real
pick flow*, not just `ait gates run` against a hand-built task. New runtime
behaviors to confirm (all from t635_14): gate **injection at creation** (new tasks
carry `gates:` from the profile), the **Step-7 backfill** (a gateless picked task
adopts `default_gates`, while an explicit `gates: []` opt-out is preserved), and
**exactly one** `risk_evaluated` record end-to-end (the Step-7 self-record is
suppressed for declared tasks via `aitask_gate.sh should-self-record`, so the
orchestrator's verifier is the sole authoritative recorder — it is NOT masked).
See `aiplans/archived/p635/p635_14_profile_gate_declaration_unification.md`.

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
- [ ] Live declared-gate pick (t635_14): a child created under `fast` carries
      `gates: [risk_evaluated]`; a gateless task picked under `fast` is backfilled at
      Step 7 (and an explicit `gates: []` is left untouched); the end-to-end run
      records exactly ONE authoritative `risk_evaluated` (verifier-origin, not a
      masked self-record).
