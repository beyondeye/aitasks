---
Task: t492_keybindings_footer_hide.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Hide normal keybindings when preview pane is focused (t492)

## Context

In the monitor TUI, when the preview pane is focused all keypresses except Tab are forwarded to tmux. But the footer still shows all normal keybindings (j/q/s/i/r/z/k), which is misleading. The footer should dynamically show only relevant bindings per zone.

## Approach

Use Textual's built-in `check_action()` + `refresh_bindings()` for dynamic action visibility.

## Changes

### `.aitask-scripts/monitor/monitor_app.py`

1. **Added Tab binding to BINDINGS** — `Binding("tab", "switch_zone", "← Back (Tab)")` for Footer display. The on_key handler still intercepts Tab before the action fires.

2. **Added `check_action()` override** — Returns `True` only for `switch_zone` when in PREVIEW zone; returns `True` for everything except `switch_zone` when in PANE_LIST zone. This controls what the Footer shows.

3. **Added `action_switch_zone()` no-op** — Required so the binding doesn't error; Tab is actually handled in `on_key`.

4. **Added `self.refresh_bindings()`** in `_update_zone_indicators()` — Triggers Footer update on every zone change.

## Verification

- [x] Syntax check passes
- [ ] Manual test: footer shows normal bindings in PANE_LIST zone
- [ ] Manual test: footer shows only "← Back (Tab)" in PREVIEW zone
- [ ] Manual test: Tab still cycles zones correctly
- [ ] Manual test: all keybindings still work in their respective zones

## Final Implementation Notes
- **Actual work done:** Implemented exactly as planned — 3 additions to `monitor_app.py`: Tab binding in BINDINGS, `check_action()` override for dynamic footer visibility, and `refresh_bindings()` call in zone indicator update
- **Deviations from plan:** None
- **Issues encountered:** None
- **Key decisions:** Used Textual's `check_action()` returning `True`/`False` for show/hide (not `None` for grayed-out), keeping the approach minimal. The `action_switch_zone` no-op is necessary to avoid binding resolution errors even though Tab is handled in `on_key`.
