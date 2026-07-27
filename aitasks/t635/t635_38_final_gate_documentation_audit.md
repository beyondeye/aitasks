---
priority: medium
effort: medium
depends: [t635_18, t635_34, t635_37]
issue_type: documentation
status: Ready
labels: [gates, documentation, web_site]
gates: [risk_evaluated]
anchor: 635
created_at: 2026-07-27 22:47
updated_at: 2026-07-27 22:47
---

## Goal

After the comprehensive gate documentation sweep and the currently evolving registry/profile surfaces have landed, audit every gate-related documentation surface against the final implementation and remove stale or superseded guidance.

This is a final coherence pass, not a substitute for the incremental documentation owned by each user-facing task.

## Scope

1. Build a source-of-truth inventory from the landed CLI, registry schema, profile semantics, task-workflow behavior, gate ledger/orchestrator, verifier skills, and TUI surfaces.
2. Audit all gate documentation, including `aidocs/gates/`, the website concepts/workflows/skills/TUIs/commands/configuration pages, relevant task-workflow and gate skill guidance, registry header comments, CLI help, and cross-references.
3. Reconcile the documentation with the final active-gates/rendered-gates model, `sync-registry`, no-verifier warning, registry-driven profile picker, procedure-versus-machine behavior, and any other landed t635 changes.
4. Remove obsolete design-history language from user-facing docs; retain only current-state behavior. Correct internal roadmap/design docs where they claim a current implementation contract.
5. Add or extend focused drift checks where a stable machine-checkable source of truth exists; otherwise record deliberate non-automatable review points.

## Acceptance criteria

- Every documented gate command, configuration key, registry field, workflow step, and UI surface is verified against the landed implementation or removed/updated.
- Website navigation and cross-references cover the complete current gate workflow and build successfully.
- `aidocs/gates/aitask-gate-framework.md` and `aidocs/gates/integration-roadmap.md` agree with current behavior, with no stale phase/model claims presented as current.
- The audit explicitly records reviewed surfaces and any intentionally deferred documentation, so later gate work has a fresh baseline.

## Dependencies

- t635_18 provides the comprehensive website documentation sweep.
- t635_34 provides installed-registry reconciliation and the active-gate no-verifier warning.
- t635_37 provides the registry-driven profile gate-picker semantics.
