---
priority: high
effort: medium
depends: [t635_2, t635_3]
issue_type: feature
status: Ready
labels: [gates, task-archive, task_workflow]
created_at: 2026-06-10 18:53
updated_at: 2026-06-10 18:53
---

## Context

Phase 2 of `aidocs/gates/integration-roadmap.md` (decision D5). Today
task-workflow Step 9 archives the task at workflow end, which kills
re-entry — workflow-end and all-gates-pass no longer coincide once gates
exist (human review pending, manual verification pending, ...).

## Scope

- Step 9 archival becomes gate-guarded: if any declared gate is not `pass`,
  the task stays active (status per the framework doc — `status` enum
  unchanged, decision D6) instead of archiving.
- Archival is offered (or profile-gated auto-applied) in a later session
  when the last gate passes — wire this into the Step 3 status checks so a
  fully-passed task gets the archival offer on next pick.
- `aitask_archive` script refuses to archive a task with non-pass declared
  gates (profile-gated escape hatch per the framework doc integration
  table).
- Rejected alternatives (recorded in roadmap D5): archive-then-unarchive
  escape hatch; re-entry from archive (fights "archived = immutable
  record").

## Sequencing constraint

Depends on t635_3 (dependency-unblock semantics) — deferring archival
without an explicit unblock point regresses dependent-task availability.

## References

- `aidocs/gates/integration-roadmap.md` (Phase 2, D5)
- `aidocs/gates/aitask-gate-framework.md` ("Relationship to existing status
  field", integration table row for aitask-archive)
