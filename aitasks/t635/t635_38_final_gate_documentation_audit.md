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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t635_18** id=2026-09-10T18:37:06Z.dbd7adf46e747a27e680d49e from=t635_18 at=2026-09-10T18:37:06Z base=e2f12c49990459143f2e387db431b5222fc66ef7 base_branch=main dirty=no host=omg16
>
> | Docs-coordination sweep, run outside any task: `from=` names the related task,
> | not an agent working on it, so it is unverified. Advisory only; status
> | readings are moment-relative. Verify before acting.
> | 
> | 1. As the "final" audit this depends only on t635_18/34/37, but these t635
> |    children are still open (Ready) as of this sweep and will change gate docs
> |    after it: t635_16, t635_24 (legacy verify_build removal), t635_26, t635_28,
> |    t635_29, t635_30 (task gate editing surface), t635_31, t635_32. Either add
> |    them to depends, or treat this as a baseline audit rather than the last one.
> | 
> | 2. The Gates concept page may end up written by t1687 (Concepts gap sweep)
> |    rather than t635_18 — both plan it and no owner has been picked. Include
> |    whichever lands in the audit inventory.
