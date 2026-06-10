---
priority: high
effort: medium
depends: [t635_1]
issue_type: feature
status: Ready
labels: [gates]
created_at: 2026-06-10 18:53
updated_at: 2026-06-10 18:53
---

## Context

Phase 2 of `aidocs/gates/integration-roadmap.md` — "open problem 1", flagged
as needing proper design during the 2026-06-10 design session. Today
`depends:` effectively unblocks when the upstream task completes and
archives. With gate-deferred archival (t635_4, decision D5), a task whose
machine gates pass but whose human review pends for days would block
dependents LONGER than today — a regression unless the unblock point is made
explicit. The framework doc only brushes this (open question 4, cross-task
gates, deferred from v1).

## Goal

Design (with trade-offs and rejected alternatives) and implement the
dependency-unblock point for gated tasks. Produce a design doc under
`aidocs/gates/` before implementation.

Candidate shapes from the roadmap:
- Unblock at all-gates-pass (strict/simple; inherits the slow-human-gate
  regression).
- Per-task `unblock_after: [tests_pass]` subset (flexible; per-task noise).
- Registry-level `unblocks_dependents:` flag per gate (e.g. machine gates
  unblock, human gates do not) — declared once where gate semantics live.
  Current lean, not yet decided.

Must also define behavior for ungated upstream tasks (unchanged) and mixed
chains (gated upstream, ungated dependent).

## Sequencing constraint

Must land before or together with t635_4 (gate-guarded archival) — the
archival change without this design regresses dependent-task availability.

## References

- `aidocs/gates/integration-roadmap.md` (Phase 2, open problem 1)
- `aidocs/gates/aitask-gate-framework.md` (open question 4)
