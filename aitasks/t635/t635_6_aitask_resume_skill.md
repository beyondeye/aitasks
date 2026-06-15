---
priority: high
effort: medium
depends: [t635_5]
issue_type: feature
status: Implementing
labels: [gates, claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-10 18:53
updated_at: 2026-06-15 15:47
---

## Context

Phase 2 of `aidocs/gates/integration-roadmap.md` (decision D8). The
user-facing unified flow is gate-aware aitask-pick (t635_7), but a separate
`aitask-resume` skill is wanted as the PROGRAMMATIC surface: for initial
testing of re-entry, for TUI invocation (board In-Flight view ops,
t635_9), and for any interaction surface that needs direct "resume this
task / run these specific gates" control without the full pick funnel.

## Scope

- New skill `aitask-resume <task-id> [--gate <name>]`: thin re-entrant
  orchestration scoped to resuming an in-flight task from its ledger state
  or running specific gates. Shares the resume logic from t635_5 — do not
  fork it.
- Stub + per-profile rendering per the standard skill authoring conventions
  (`aidocs/framework/skill_authoring_conventions.md`,
  `aidocs/framework/stub-skill-pattern.md`); headless variant for TUI /
  programmatic launches.
- This skill is the seed of the framework doc's `aitask-run-gates`
  orchestrator: when t635_11 lands the full orchestrator engine, `aitask-
  resume` becomes its front (no second engine).
- Claude Code is the source of truth; suggest follow-up tasks for
  agent-specific surfaces in Codex/OpenCode if any are touched.

## Coordination (from t635_5)

Ledger-driven re-entry (t635_5) **landed**. The resume engine this skill wraps
is already built — **consume it, do not fork**:

- `aitask_gate.sh resume-point <task-id>` / `gate_ledger.resume_point()` →
  the 3-state resume API: `PLAN` | `IMPLEMENT` | `POSTIMPL` (keyed off the
  recorded `plan_approved`/`review_approved` checkpoints; distinct from
  `archive_status`/`dependents_status` — see `aidocs/gates/ledger-driven-reentry.md`).
- task-workflow Step 3 **Check 5** + the **Re-entry Routing** subsection
  (end of Step 4) implement the in-conversation resume; the generalized
  `crash-recovery.md` is the ledger-driven survey. `aitask-resume` should be a
  thin programmatic front over the same derivation + routing contract.

## References

- `aidocs/gates/ledger-driven-reentry.md` (the resume derivation + routing this skill wraps)
- `aidocs/gates/integration-roadmap.md` (Phase 2, D8)
- `aidocs/gates/aitask-gate-framework.md` ("Orchestrator skill" — invocation
  shape and re-entry contract to stay compatible with)
