---
Task: t262_button_to_collapse_expand_column.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

Task t262 is a follow-up to t261 (lock refresh performance). The board can become sluggish with many tasks. Adding column collapse/expand lets users hide columns they don't need, reducing rendered widgets and improving responsiveness. The column header also needs redesigning: currently clicking anywhere on it opens the edit dialog — we need separate collapse/expand and edit buttons instead.

## Plan

### 1. TaskManager: Collapsed State Persistence

**File:** `aiscripts/board/aitask_board.py` (TaskManager class, ~line 186)

- Add `collapsed_columns` property (reads/writes `self.settings["collapsed_columns"]`)
- Add `toggle_column_collapsed(col_id)` method — toggles the ID in the list, calls `save_metadata()`
- Add `is_column_collapsed(col_id)` convenience method
- In `delete_column()` (~line 380): clean up collapsed state when a column is deleted

### 2. New Header Widget Classes

**File:** `aiscripts/board/aitask_board.py` (replace ClickableColumnHeader at line 397)

- `CollapseToggleButton(Static)` — renders `▶` (collapsed) or `▼` (expanded), `can_focus=False`, on_click calls `app.toggle_column_collapse(col_id)`
- `ColumnEditButton(Static)` — renders `✎`, `can_focus=False`, on_click calls `app.open_column_edit(col_id)`
- `ColumnHeader(Static)` — composite widget:
  - **Expanded:** Horizontal row with `[▼] Title (N) [✎]`
  - **Collapsed:** Vertical layout with title, count on separate line, and `[▶]` button
- For the "unordered" column: same `ColumnHeader` but without the edit button
- Delete old `ClickableColumnHeader` class

### 3. KanbanColumn: Collapsed Rendering

- Add `collapsed: bool = False` parameter to `__init__`
- In `compose()`: if collapsed, only yield the header (no TaskCards)
- In `on_mount()`: if collapsed, set `width=10, min_width=8`

### 4. refresh_board(): Pass Collapsed State

- When mounting each KanbanColumn, read `self.manager.is_column_collapsed(col_id)` and pass `collapsed=` param

### 5. KanbanApp: Toggle Action + Keyboard Shortcut

- Add `toggle_column_collapse(col_id)` method
- Add keyboard binding: `X` (Shift+X) — contextual shortcut for focused card's column
- Add `action_toggle_column_collapsed()` action

### 6. Command Palette: Collapse/Expand Entries

- Add "Collapse Column" and "Expand Column" to KanbanCommandProvider
- Add `action_collapse_column()` and `action_expand_column()` with filtered ColumnSelectScreen
- Modify `ColumnSelectScreen.__init__` to accept optional `columns` list parameter

### 7. Documentation Updates

- `website/content/docs/board/reference.md` — settings docs, column operations table
- `website/content/docs/board/how-to.md` — new section, updated editing instructions

## Post-Review Changes

### Change Request 1 (2026-02-26 16:30)
- **Requested by user:** Make edit button (✎) have black background and white text. Make collapsed columns selectable so X shortcut can expand them.
- **Changes made:**
  - Added `col-header-edit-btn` CSS class with `background: black; color: white;` for the ColumnEditButton
  - Added `CollapsedColumnPlaceholder` focusable widget (renders "···") inside collapsed columns
  - Updated `action_toggle_column_collapsed()` to detect focused placeholder and expand the column
  - Updated `_nav_lateral()` to navigate to/from collapsed column placeholders
  - Updated `action_nav_up/down` to handle placeholder focus (no-op)
  - Updated `action_focus_board()` to fall back to placeholders if no cards exist
- **Files affected:** `aiscripts/board/aitask_board.py`

### Change Request 2 (2026-02-26 16:35)
- **Requested by user:** Task movement (Shift+Left/Right) should skip over collapsed columns
- **Changes made:** Updated `_move_task_lateral()` to skip collapsed columns when finding the target column — uses a while loop to advance past collapsed columns in the direction of movement
- **Files affected:** `aiscripts/board/aitask_board.py`

## Final Implementation Notes
- **Actual work done:** Implemented column collapse/expand with persistent state in board_config.json, redesigned column headers with separate collapse toggle (▶/▼) and edit (✎) buttons, added keyboard shortcut (Shift+X), command palette entries, focusable collapsed placeholder for navigation, and comprehensive documentation updates.
- **Deviations from plan:** Added `CollapsedColumnPlaceholder` (not in original plan) to make collapsed columns focusable for keyboard navigation and X shortcut. Also added task movement skipping over collapsed columns.
- **Issues encountered:** None significant — Textual framework handled composite widgets well.
- **Key decisions:** Used simple Unicode arrows (▶/▼) instead of emoji for universal terminal support. Collapsed column width set to 12 chars (enough for title + count). Edit button styled with black bg/white text for visual distinction.
