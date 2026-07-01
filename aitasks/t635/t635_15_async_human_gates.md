---
priority: low
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: [t635_11, t635_21]
issue_type: feature
status: Implementing
labels: [gates, task_workflow]
gates: [risk_evaluated]
risk_mitigation_tasks: [1109]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-10 18:56
updated_at: 2026-07-01 14:54
---

## Context

Phase 5 of `aidocs/gates/integration-roadmap.md` (decision D2,
hybrid-by-mode): attended sessions keep their interactive approvals
(recorded to the ledger by t635_2); headless/remote lanes treat the same
gates as genuine async human gates and stop cleanly at pending-human.

## Scope

- `type: human` gates with `signal: file-touch`: pending-block semantics,
  signal target `.aitask-gates/<task-id>/<gate>.signed`, exit code 4
  (pending) per the framework doc human-gate verifier contract.
- `ait gate pass <task-id> <gate>` (refuses machine gates; records signer +
  timestamp) and `ait gate fail <task-id> <gate> [--reason]`.
- The non-negotiable autonomy rule, repeated verbatim in every human-gate
  verifier and the registry: agents MUST NEVER create the signal for a
  human gate, suggest automating its creation, or bypass its absence.
- Hybrid switch: in headless profiles, review/merge approval checkpoints
  resolve as async human gates (workflow stops pending) instead of
  AskUserQuestion. One gate definition, two signal transports — no forked
  gate semantics per mode.

## Out of scope

Remote comment/label signals and projection (t635_16); autonomous-lane
auto-completion policy (t635_17).

## Coordination note — already landed in t635_11

t635_11 (orchestrator + verifier contract) shipped the **read side** of human
gates, so this task owns only the **write/create side** plus the hybrid switch.
Already in place — do NOT rebuild:

- **Read-side `file-touch` detection.** The orchestrator
  (`lib/gate_orchestrator.py`) already substitutes `signal_target`
  (`<task-id>`→`t<id>`, `<gate>`) and, when the signal file exists, appends
  `pass`; when absent, appends `pending` — and NEVER self-signals. So
  pending-block semantics + the exit-code-4-pending mapping for human gates
  already work for the read path.
- **`ait gate fail <task-id> <gate> [--reason]`** already exists
  (`aitask_gate_fail.sh`, wired into the `ait gate` dispatcher).
- The **non-negotiable autonomy rule** is already documented verbatim in the
  registry header (`aitasks/metadata/gates.yaml`) and the `aitask-gate-template`
  skill.

**This task's remaining scope:** signal **CREATION** — `ait gate pass
<task-id> <gate>` (refuses machine gates; records signer + timestamp) — plus the
hybrid switch (headless profiles resolve review/merge approvals as async human
gates that stop pending instead of AskUserQuestion). Build on the read-side
detection above; do not fork the gate semantics.

## References

- `aidocs/gates/aitask-gate-framework.md` ("Human-gate verifier", signal
  kinds)
- `aidocs/gates/integration-roadmap.md` (Phase 5, D2)

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-01T11:33:50Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-01T11:53:25Z status=pass attempt=1 type=human
