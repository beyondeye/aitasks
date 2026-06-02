---
priority: high
effort: medium
depends: []
issue_type: manual_verification
status: Implementing
labels: [ait_brainstorm, brainstom_modules]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-02 10:43
updated_at: 2026-06-02 11:25
---

## Origin

Risk-mitigation ("after") follow-up for t756_3, created from the approved plan's
risk evaluation.

## Risk addressed

goal-achievement live workflow risks:

- The functional `module_decompose --link-to-task` path shells out to real
  child-task creation during apply; unit tests cover graph effects but not the
  full live create/commit/module_tasks workflow.
- The module op TUI flow and live agent-launch/apply cycle were not manually
  exercised in the implementation session, so there is a bounded risk that the
  implemented wiring does not fully satisfy the intended user workflow even
  though static/unit checks pass.

## Goal

Manually verify `module_decompose` / `module_merge` TUI flows, live agent
launch/apply, `from_sections` behavior, and `--link-to-task` child creation plus
`module_tasks` persistence.

## Verification Checklist

- [ ] module_decompose on _umbrella HEAD spawns per-module roots with correct module_label / parents / current_heads.
- [ ] module_merge produces a 2-parent destination node and refuses a non-ancestor destination (guard fires before agent input assembly).
- [ ] An existing op targeted at a module changes only that subgraph (B1 regression).
- [ ] --link-to-task creates a child aitask and writes module_tasks[M].
- [ ] --from-sections slices deterministically on clean section markers.
- [ ] Existing brainstorm tests still pass.
