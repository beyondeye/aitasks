---
Task: t283_crash_when_refresh_in_ait_settings.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

Pressing 'r' for refresh in `ait settings` TUI crashes with `DuplicateIds` error. The `action_reload_configs()` calls `_populate_board_tab()` which uses `container.remove_children()` (async in Textual — defers actual removal) then immediately mounts new widgets with hardcoded IDs (`board_cf_refresh`, `board_cf_sync`, `btn_board_save`). The old widgets still exist, causing duplicate ID errors.

The agent tab and profiles tab already handle this correctly using `_repop_counter` in widget IDs. The board tab was missed.

## Fix

**File:** `aiscripts/settings/settings_app.py`

### 1. Add `_repop_counter` to `_populate_board_tab()`

Add counter increment and suffix to all widget IDs (`board_cf_refresh`, `board_cf_sync`, `btn_board_save`).

### 2. Update `save_board_settings()` handler

Change from hardcoded ID queries to `field_key`-based queries for CycleFields and ID prefix matching for the button handler.

## Verification

- Press 'r' in settings TUI — no crash, shows "Configs reloaded from disk"
- Board tab Save button still works after refresh
- Multiple 'r' presses in succession work

## Final Implementation Notes
- **Actual work done:** Added `_repop_counter` to `_populate_board_tab()` widget IDs, matching the existing pattern in `_populate_agent_tab()` and `_populate_profiles_tab()`. Updated `save_board_settings()` to query CycleFields by `field_key` attribute instead of hardcoded IDs. Integrated board save button into the existing `on_button_pressed()` generic handler using `startswith` matching.
- **Deviations from plan:** Initially created a second `@on(Button.Pressed)` generic handler, but discovered an existing one at line 1645 that already handles profile buttons with `startswith` matching. Consolidated the board save case into the existing handler instead.
- **Issues encountered:** None — fix was straightforward once the root cause was confirmed.
- **Key decisions:** Used `field_key` attribute queries (existing CycleField property) instead of ID-based queries for robustness with dynamic IDs.
