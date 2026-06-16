---
priority: medium
effort: high
depends: [t635_6]
issue_type: feature
status: Implementing
labels: [gates, claudeskills]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-10 18:54
updated_at: 2026-06-16 18:06
---

## Context

Phase 4 of `aidocs/gates/integration-roadmap.md` — the full engine from
the framework doc lands, behind the already-shipped `aitask-resume` front
(t635_6). One engine, not two.

## Scope

- Full registry schema in `aitasks/metadata/gates.yaml`: `verifier`,
  `type`, `max_retries`, `unlocks` DAG, `timeout_seconds`, human-gate
  `signal`/`signal_target` fields (per the framework doc registry table).
- `aitask-run-gates` orchestrator implementing the doc's decision tree and
  re-entry contract (idempotent no-op, skip-already-passed, retry within
  budget, stop at pending-human, no frontmatter writes, append-only,
  task-level lock around appends, stopping heuristic for identical
  repeated failures).
- Verifier skill contract (positional args `<task-id> <attempt> <run-id>`,
  exit codes 0/1/2/3, sidecar log, append via `ait gate append` only) +
  `aitask-gate-template` scaffold skill.
- Parallel dispatch of unlocked machine gates (profile flag
  `max_parallel_gates`, default per doc open question 6).
- `ait gates run` / `ait gates unlocked` / `ait gate fail` / `ait gate log`
  complete the CLI surface started in t635_1.
- `aitask-resume` (t635_6) is refit as the front of this engine.

## References

- `aidocs/gates/aitask-gate-framework.md` ("Orchestrator skill", "Verifier
  skill contract", "Tooling", "Worked example")
- `aidocs/gates/integration-roadmap.md` (Phase 4)

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-16T15:06:23Z status=pass attempt=1 type=human
