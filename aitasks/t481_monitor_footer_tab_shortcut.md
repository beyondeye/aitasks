---
priority: low
effort: low
depends: []
issue_type: chore
status: Ready
labels: [aitask_monitor]
created_at: 2026-03-30 11:02
updated_at: 2026-03-30 11:02
---

Add "Tab" to the keyboard shortcuts displayed in the Textual Footer of the `ait monitor` TUI.

Currently the footer shows bindings for Jump TUI (j), Quit (q), Switch (s), Refresh (r), and Zoom (z), but Tab (zone cycling between attention/pane-list/preview) is not listed. Since Tab is now the primary navigation mechanism (added in t477), it should be visible in the footer.

## Key Files
- `.aitask-scripts/monitor/monitor_app.py` — `BINDINGS` list in `MonitorApp`

## Implementation
Add a `Binding("tab", "next_zone", "Tab: Panes")` entry to the `BINDINGS` list. The `action_next_zone` method doesn't need to exist separately since Tab is already handled in `on_key`, but having it in BINDINGS makes it show in the footer. Add an empty `action_next_zone` that passes (the real logic is in `on_key`).

## Verification
- Run `ait monitor` and confirm "Tab: Panes" appears in the footer bar
- Verify Tab still cycles zones correctly (handled by `on_key` which fires before bindings)
