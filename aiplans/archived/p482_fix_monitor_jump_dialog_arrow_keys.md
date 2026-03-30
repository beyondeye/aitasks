---
Task: t482_fix_monitor_jump_dialog_arrow_keys.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

Arrow keys (up/down) don't work in the TUI Switcher dialog (jump dialog, opened with `j`) when launched from the monitor TUI. They work fine from all other TUIs.

**Root cause:** `MonitorApp.on_key()` at `monitor_app.py:656-687` unconditionally intercepts ALL keys (Tab, Shift+Tab, Up, Down, and preview-zone forwarding) with `event.stop()` and `event.prevent_default()`, even when a modal dialog (TuiSwitcherOverlay) is open. This prevents the ListView's default binding-driven `action_cursor_up`/`action_cursor_down` from ever firing.

**Event flow:** In Textual, key events bubble from the focused widget → parent containers → Screen → App. The App's `on_key` fires last. But `event.prevent_default()` at the App level prevents the binding system from processing keys for all widgets, including the modal's ListView. This kills arrow navigation in the switcher.

## Plan

**File:** `.aitask-scripts/monitor/monitor_app.py` (line ~657)

Add a single guard at the very top of `on_key()`, immediately after `key = event.key`:

```python
def on_key(self, event) -> None:
    key = event.key

    # Let modal screens (e.g. TuiSwitcherOverlay) handle their own keys
    if isinstance(self.screen, ModalScreen):
        return

    # Tab/Shift+Tab always cycle zones ...
```

This returns early for ALL keys (not just Up/Down) when any ModalScreen is active. This is correct because:
- **Up/Down:** Must reach ListView for cursor navigation
- **Tab:** Must not cycle monitor zones while modal is open
- **Preview forwarding:** Must not forward to tmux while modal is open
- **Other keys (j, q, s, etc.):** Already handled by TuiSwitcherOverlay's own BINDINGS

`ModalScreen` is already imported at line 38. No new imports needed.

## Verification

1. Run `ait monitor`, press `j` to open the jump dialog
2. Verify UP/DOWN arrow keys navigate the list items
3. Close dialog with Escape or `j`
4. Verify UP/DOWN still navigate zones normally
5. Verify Tab still cycles zones when dialog is closed
6. Verify preview zone key forwarding still works

## Final Implementation Notes
- **Actual work done:** Added a 3-line guard at the top of `MonitorApp.on_key()` that checks `isinstance(self.screen, ModalScreen)` and returns early, exactly as planned
- **Deviations from plan:** None
- **Issues encountered:** None — `ModalScreen` was already imported at line 38
- **Key decisions:** Used `ModalScreen` (broad) instead of `TuiSwitcherOverlay` (specific) to cover any future modals
