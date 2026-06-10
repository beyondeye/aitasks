---
priority: low
effort: medium
depends: [t635_11]
issue_type: feature
status: Ready
labels: [gates, task_workflow]
created_at: 2026-06-10 18:56
updated_at: 2026-06-10 18:56
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

## References

- `aidocs/gates/aitask-gate-framework.md` ("Human-gate verifier", signal
  kinds)
- `aidocs/gates/integration-roadmap.md` (Phase 5, D2)
