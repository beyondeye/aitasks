---
Task: t299_revert_button_in_ait_settings_for_board_settings.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

Task t299: The board settings tab in `ait settings` TUI currently only has a "Save Board Settings" button. When users modify settings (auto-refresh, sync on refresh), there's no way to discard changes and revert to the saved state. A "Revert" button should appear alongside Save when modifications have been made.

## Plan

### File to modify
`aiscripts/settings/settings_app.py`

### Changes

**1. Store original board settings values in `_populate_board_tab()` (~line 1611)**

After reading settings from `self.config_mgr.board`, store the original values as instance variables so we can detect dirty state.

**2. Replace the standalone Save button with a Horizontal button row (~line 1626)**

Replace the current single `Button("Save Board Settings", ...)` with a `Horizontal` container (using the existing `tab-buttons` CSS class) holding both Save and Revert buttons — following the exact same pattern as the profiles tab (line 1849).

The Revert button is always rendered (like profile Revert buttons), keeping the UI consistent with the profiles tab pattern.

**3. Add `_revert_board_settings()` method (after `save_board_settings()`, ~line 1654)**

Following the `_revert_profile()` pattern: reload config from disk and repopulate the tab.

**4. Add button handler in `on_button_pressed()` (~line 1933)**

After the existing `btn_board_save` handler, add handler for `btn_board_revert`.

### Verification

1. Run `./ait settings`
2. Navigate to Board tab (press `b`)
3. Verify Save and Revert buttons appear side by side
4. Change a setting → click Revert → verify setting reverts
5. Verify Save still works as before

## Final Implementation Notes
- **Actual work done:** Added a "Revert Board Settings" button next to the existing Save button in the board settings tab, plus a `_revert_board_settings()` method and its button handler. All 4 planned changes implemented as described.
- **Deviations from plan:** Dropped the "store original values" step (plan item 1) since it wasn't needed — the Revert button is always visible (matching the profiles tab pattern) and revert works by reloading from disk, not by comparing against stored originals.
- **Issues encountered:** None.
- **Key decisions:** Followed the profiles tab pattern exactly — Revert button always visible, uses `warning` variant, reloads config from disk via `config_mgr.load_all()` then repopulates the tab.
