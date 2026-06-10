---
priority: high
effort: medium
depends: [t635_5]
issue_type: feature
status: Ready
labels: [gates, claudeskills]
created_at: 2026-06-10 18:53
updated_at: 2026-06-10 18:53
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

## References

- `aidocs/gates/integration-roadmap.md` (Phase 2, D8)
- `aidocs/gates/aitask-gate-framework.md` ("Orchestrator skill" — invocation
  shape and re-entry contract to stay compatible with)
