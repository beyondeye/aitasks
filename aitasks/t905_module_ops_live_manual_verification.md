---
priority: high
effort: medium
depends: []
issue_type: manual_verification
status: Implementing
labels: [ait_brainstorm, brainstom_modules]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-02 10:43
updated_at: 2026-06-02 11:04
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
