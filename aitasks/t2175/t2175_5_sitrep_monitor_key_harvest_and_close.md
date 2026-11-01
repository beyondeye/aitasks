---
priority: medium
effort: medium
depends: [t2175_4]
issue_type: feature
status: Ready
labels: [sitrep]
anchor: 2175
created_at: 2026-10-31 19:58
updated_at: 2026-11-01 17:40
---


# Monitor key: harvest-and-close

Child of t2175. Depends on the sitrep skill and window child.

## Scope
- A keybinding in `ait monitor` / `ait minimonitor` (see `aidocs/framework/tui_conventions.md`, shortcut scopes) that runs harvest for the selected finished/frozen agent, shows what was captured (items and any harvest warnings), and only then offers to close/drop the agent. Refuses to drop when harvest failed.
- Launch/focus the sitrep window from the TUI switcher / monitor (key to be chosen against existing bindings); show an indicator of open Pick-now items in the monitor if cheap.
- Spawn/drop mechanics: invoke `drop` through `run-shell -b` as `aitask_frozen.sh` requires, never inline in a TUI pane.
- Tests per `tui_conventions.md` and `testing_conventions.md` (Textual `run_test`, no in-flight workers at block exit).
