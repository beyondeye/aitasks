---
priority: medium
effort: high
depends: [t1157_6, t1149_3]
issue_type: feature
status: Ready
labels: [tui, workflows, remote, python, installation]
gates: [risk_evaluated]
anchor: 1157
created_at: 2026-07-17 16:53
updated_at: 2026-07-17 16:56
---

## Context

Seventh child of t1157. Once the workflow host, session model, router, and core flows land, extend the Chatlink TUI and configuration UX from the currently in-flight t1149 work. The TUI must become workflow-aware without commanding the daemon; Discord remains the control surface for approval/resume/restart. This child must begin by re-reading the archived t1149_2/t1149_3 implementation records and adapting to their final APIs.

## Key files to modify

- `.aitask-scripts/chatlink/chatlink_app.py`: project/workflow/attempt status, budget/proposal/paused state presentation.
- `.aitask-scripts/chatlink/wizard.py` and `config_write.py` if created by t1149_3: layered host/project workflow editing and migration.
- `.aitask-scripts/chatlink/preflight.py`: renderable aggregate health result consumption.
- `tests/test_chatlink_tui.sh` plus config/wizard tests.

## Reference files

- t1149_2 and t1149_3 archived plans and implementation notes (mandatory fresh read).
- t1157_1 host config and t1157_2 session persistence APIs.
- Existing `ChatlinkApp` read-only polling/worker constraints and TUI conventions.

## Implementation plan

1. Depend on the shipped t1149 configuration panel/wizard APIs; do not overwrite their in-flight work.
2. Display gateway connection health plus project/workflow rows, active attempts, budget remaining, paused/awaiting-approval/expired states, and safe audit context.
3. Keep polling cheap and read-only; expensive validation runs in cached workers. Never let the TUI command, kill, resume, approve, or create sessions.
4. Extend the wizard to edit per-project workflow definitions and the per-machine host registry separately, preserve unknown config keys, and keep secrets outside YAML. Make legacy-to-workflow migration explicit and reviewable.
5. Surface duplicate triggers, unavailable projects, missing host token, and per-workflow agent/image preflight failures with actionable text.
6. Preserve smoke construction/no-I/O behavior, shortcut scope, existing configuration behavior, and accessibility of the original status/audit view.

## Verification

- Pilot tests render multiple projects/workflows/attempt states and corrupt/expired records without crashing.
- Polling never runs expensive probes; explicit refresh uses the cache/worker path.
- Wizard round trips host/project edits, preserves unknown keys, never reveals secrets, and performs explicit legacy migration.
- Existing t1149 panel/wizard tests remain green.
