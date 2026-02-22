---
Task: t193_periodically_auto_refresh_board.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

Task t193: The Python TUI board (`ait board`) currently only refreshes when the user manually presses `r`. This task adds periodic auto-refresh (default 5 min) and a settings modal to configure the interval. Settings are persisted in `board_config.json`.

## File to modify

- `aiscripts/board/aitask_board.py` — all changes are in this single file

## Implementation Plan

### 1. Extend `TaskManager` to handle settings

- Add `self.settings: dict = {}` to `__init__` (~line 209)
- In `load_metadata()` (~line 223): read `self.settings = data.get("settings", {"auto_refresh_minutes": 5})`; also set default in the `else` branch
- In `save_metadata()` (~line 234): include `"settings": self.settings` in the written dict
- Add `auto_refresh_minutes` property + setter for convenience

### 2. Add `SettingsScreen` modal class

Insert after `DeleteColumnConfirmScreen` (~line 1585), following the same pattern as `ColumnEditScreen`:

- `SettingsScreen(ModalScreen)` with `__init__(self, manager)`
- `compose()`: Container with title label, a `CycleField` for interval options `["0", "1", "2", "5", "10", "15", "30"]` (reusing existing widget), a hint label `"0 = disabled"`, and Save/Cancel buttons
- `save_settings()`: reads CycleField value, converts to int, calls `self.dismiss({"auto_refresh_minutes": value})`
- `action_cancel()`: `self.dismiss(None)`

### 3. Add CSS for settings dialog

In `KanbanApp.CSS` (~line 1782), add rules for `#settings_dialog`, `#settings_title`, `.settings-hint` — following the existing `#column_edit_dialog` pattern.

### 4. Add auto-refresh timer to `KanbanApp`

- Add `self._auto_refresh_timer = None` in `__init__` (~line 1819)
- `_start_auto_refresh_timer()`: stops existing timer, starts `self.set_interval(minutes * 60, ...)` if minutes > 0
- `_stop_auto_refresh_timer()`: stops timer if running
- `_auto_refresh_tick()`: skips if `self._modal_is_active()` returns True, otherwise calls `self.action_refresh_board()`
- Call `_start_auto_refresh_timer()` from `on_mount()` (~line 1855)

### 5. Add settings action + binding

- Add `Binding("S", "open_settings", "Settings")` to `BINDINGS` (~line 1810)
- `action_open_settings()`: guard with `_modal_is_active()`, push `SettingsScreen`
- `_handle_settings_result(result)`: if not None, update `manager.settings`, save metadata, restart timer, show notification

### 6. Update command palette

In `KanbanCommandProvider`, add "Settings" entry to both `discover()` and `search()` methods.

### 7. Show auto-refresh status in subtitle

- Set `TITLE = "aitasks board"` on `KanbanApp`
- Add `_update_subtitle()`: sets `self.sub_title` to "Auto-refresh: Nmin" or "Auto-refresh: off"
- Call from `on_mount()` and `_handle_settings_result()`

## Config file result

After first save, `board_config.json` gains:
```json
{
  "columns": [...],
  "column_order": [...],
  "settings": {
    "auto_refresh_minutes": 5
  }
}
```

Backward compatible: existing configs without `settings` key default to 5 minutes.

## Verification

1. Run `python aiscripts/board/aitask_board.py` — board should launch with subtitle "Auto-refresh: 5min"
2. Press `S` — settings modal opens with interval set to 5
3. Change to 0, save — subtitle shows "Auto-refresh: off", no periodic refresh occurs
4. Change to 1, save — board auto-refreshes after 1 minute (verify by watching for re-render)
5. Open a modal (Enter on a task) — auto-refresh should skip while modal is open
6. Press Escape, wait — auto-refresh resumes on next tick
7. Check `board_config.json` — `settings` key persisted correctly

## Final Implementation Notes

- **Actual work done:** All 7 plan steps implemented exactly as planned in a single file (`aiscripts/board/aitask_board.py`, +147 lines). Added `SettingsScreen` modal, auto-refresh timer via `set_interval()`, settings persistence in `board_config.json`, `S` keybinding, command palette entry, and subtitle status display.
- **Deviations from plan:** None — implementation matched the plan precisely.
- **Issues encountered:** None.
- **Key decisions:** Used `set_interval()` (not `set_timer()`) for periodic execution. Timer skips ticks when a modal is active rather than pausing/resuming. Reused existing `CycleField` widget and `ColumnEditScreen` modal pattern for consistency.
