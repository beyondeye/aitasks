---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitor]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-30 11:09
updated_at: 2026-03-30 11:41
---

Fix arrow keys (up/down) not working in the TUI Switcher (jump dialog) when opened from the monitor TUI. The keys work correctly when the switcher is opened from other TUIs (board, codebrowser, settings, brainstorm).

## Root Cause

The `on_key` method in `MonitorApp` (`monitor_app.py:680-687`) unconditionally intercepts UP/DOWN arrow keys with `event.stop()` and `event.prevent_default()`, even when a modal dialog (TuiSwitcherOverlay) is open. This prevents the `_WrappingListView` inside the switcher from receiving arrow key events.

## How Other TUIs Avoid This

- **Board TUI** (`aitask_board.py:2773-2777`): Uses `check_action` to disable navigation actions when `TuiSwitcherOverlay` is the active screen
- **Other TUIs** (CodeBrowser, Settings, Brainstorm): Have no custom `on_key` method, so the modal naturally receives key events

## Fix

In `monitor_app.py`'s `on_key` method, add a guard to skip arrow key interception when a modal screen (specifically `TuiSwitcherOverlay`) is active. For example, add an early return before the UP/DOWN handling:

```python
# Don't intercept keys when a modal overlay is active
if isinstance(self.screen, ModalScreen):
    return
```

Or more specifically check for `TuiSwitcherOverlay`.

## Key Files

- `.aitask-scripts/monitor/monitor_app.py` — `on_key` method (lines 656-687)
- `.aitask-scripts/lib/tui_switcher.py` — `TuiSwitcherOverlay` and `_WrappingListView`

## Verification

- Run `ait monitor`, press `j` to open the jump dialog
- Verify UP/DOWN arrow keys navigate the list items
- Verify arrow keys still work for zone navigation when the dialog is closed
- Verify Tab still cycles zones correctly
