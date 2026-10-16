---
priority: medium
effort: medium
depends: [t2038_1]
issue_type: feature
status: Ready
labels: [monitor, tmux]
anchor: 2034
created_at: 2026-10-16 08:11
updated_at: 2026-10-16 08:11
---

Discovery and capture in the Go server (parent: Go monitor status server task).

## Source (`monitor/monitor_core.py`)

- Pane discovery with shadows (`discover_panes_with_shadows_async`), categories
  (`PaneCategory`), agent prefixes / TUI names, companion filtering
  (`is_live_companion_marker` `:378`, `_is_companion_process` `:404`), pane
  ordering (`pane_sort_key` `:1267`).
- Session→project map and per-session `tmux.monitor` config
  (`load_monitor_config` `:3806`).
- Concurrent capture over the control client: `capture-pane -p -e -S -<n>`
  (`_capture_args`); the parked-agent semantics from t2034_2.

## Verification

Comparison with the Python producer on a live private tmux server: same panes,
same categories, same order, same captured content.
