---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: [t635_2, t635_3]
issue_type: feature
status: Implementing
labels: [gates, task-archive, task_workflow]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-10 18:53
updated_at: 2026-06-14 18:46
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

## Coordination (from t635_3)

Dependency-unblock semantics landed in t635_3 (design:
`aidocs/gates/dependency-unblock-semantics.md`). The unblock decision lives in
`lib/gate_ledger.py` `dependents_status` (surfaced as `aitask_gate.sh
deps-unblock`, consumed by `aitask_ls.sh`): a gated active task releases its
dependents once its required (`blocks_dependents`) gates pass. Keep **archival**
here a DISTINCT, later event — the *all-gates-pass* point — so a task can release
its dependents (integration gates pass) yet stay active and re-enterable while
slow human/async gates pend. Do not collapse unblock into archival. t635_3 is
dormant until this task makes a gated task linger active; it lands first per the
roadmap sequencing constraint.

## References

- `aidocs/gates/integration-roadmap.md` (Phase 2, D5)
- `aidocs/gates/aitask-gate-framework.md` ("Relationship to existing status
  field", integration table row for aitask-archive)
- `aidocs/gates/dependency-unblock-semantics.md` (t635_3 — unblock vs archival)

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-14T15:46:18Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-14T15:46:19Z status=pass attempt=1 type=machine
