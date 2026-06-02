---
priority: high
effort: medium
depends: []
issue_type: chore
status: Implementing
labels: [ait_brainstorm, brainstom_modules]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-02 10:43
updated_at: 2026-06-02 11:39
---

## Origin

Risk-mitigation ("after") follow-up for t756_3, created from the approved plan's
risk evaluation.

## Risk addressed

code-health apply and auto-apply risks:

- The implementation adds new behavior across central brainstorm TUI, crew
  registration, group persistence, DAG badge rendering, and session apply paths;
  regressions in existing op launch/apply flows are plausible despite focused
  tests.
- The module-agent auto-apply and multi-output parser add a new lifecycle shape
  that is similar to existing pollers but not yet factored into a shared
  abstraction, increasing maintenance coupling inside `brainstorm_app.py` and
  `brainstorm_session.py`.

## Goal

Add higher-level integration or contract coverage for module-agent auto-apply,
group metadata, multi-output parsing, and linked child-task creation with a
stubbed create script.
