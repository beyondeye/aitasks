---
Task: t65_explode_parent_task_in_board.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

Task t65 requests an "expand/collapse" feature for the aitask_board TUI. When a parent task with children is selected, pressing 'x' should toggle showing its child tasks inline below it, indented with a 1-character left margin. Child tasks are selectable (focusable) but cannot be moved or reordered — they always follow their parent.

Currently, only parent tasks (`aitasks/*.md`) are rendered on the board as TaskCards. Child tasks (`aitasks/t<N>/t<N>_<child>_*.md`) are loaded into `child_task_datas` but only visible in the detail view. The infrastructure for loading and querying children already exists in `TaskManager`.

**File to modify:** `aitask_board/aitask_board.py`

---

## Implementation Plan

### 1. Add `is_child` and `column_id` attributes to `TaskCard` (line 281)

Extend the constructor to accept:
- `is_child: bool = False` — marks child task cards
- `column_id: str = ""` — tracks which column the card is displayed in (needed because child tasks don't have `boardcol` metadata)

### 2. Adjust child card left margin in `TaskCard.on_mount` (line 361)

For child cards, add 1-character left margin.

### 3. Pass `column_id` from `KanbanColumn.compose` and render expanded children (line 376)

Add `expanded_tasks` parameter to `KanbanColumn.__init__`. In `compose()`, after yielding each parent TaskCard, check if it's expanded and yield child TaskCards.

### 4. Add `expanded_tasks` state and 'x' binding to `TaskBoardApp`

- Add `self.expanded_tasks: set = set()` to `__init__`
- Add `Binding("x", "toggle_expand", "Expand")` to BINDINGS
- New `action_toggle_expand` method
- Update `check_action` to conditionally show 'x' only for parents with children

### 5. Update `_get_column_cards` to use `column_id` (line 1200)

### 6. Update `_nav_lateral` to use `column_id` (line 1253)

### 7. Block movement for child cards

In `_move_task_lateral` and `_move_task_vertical`, add early return for child cards.

### 8. Pass `expanded_tasks` in `refresh_board` (line 1134)

### 9. Handle `_refocus_card` for child tasks (line 1156)

No change needed — existing code already searches all TaskCards by filename.

---

## Verification

1. Run the board: `python aitask_board/aitask_board.py`
2. Navigate to a parent task with children (look for "👶 N children" indicator)
3. Press 'x' — child tasks should appear below with left margin indent
4. Press 'x' again — children should collapse
5. Navigate up/down through parent and child cards
6. Try Shift+arrows on a child card — should not move
7. Move the parent (Shift+Left/Right) — children should follow in the new column
8. Use search filter — verify cards filter correctly
9. Press 'r' to refresh — expanded state should be preserved

## Post-Review Changes

### Change Request 1 (2026-02-10)
- **Requested by user:** Rename "Explode/Implode" terminology to "Expand/Collapse"
- **Changes made:** Updated all naming to use expand/collapse terminology
- **Files affected:** Plan file only (applied before implementation)

### Change Request 2 (2026-02-10)
- **Requested by user:** Fix child cards showing "1 child" indicator; fix up/down arrow navigation not working on child cards
- **Changes made:** Added `not self.is_child` guard on children count display; changed `action_nav_up/down` to use `focused.column_id` instead of `focused.task_data.board_col`
- **Files affected:** `aitask_board/aitask_board.py`

### Change Request 3 (2026-02-10)
- **Requested by user:** Hide movement actions (Shift+arrows) when child card is focused; dynamic Expand/Collapse label for 'x' binding
- **Changes made:** Added check_action returns for movement actions on child cards; attempted two-binding approach for dynamic label but Textual only shows first binding per key. Simplified to single "Toggle Children" label per user preference.
- **Files affected:** `aitask_board/aitask_board.py`

## Final Implementation Notes
- **Actual work done:** Implemented expand/collapse feature with 'x' shortcut, child task rendering with left margin, keyboard navigation through parent+child cards, movement blocking for child cards, and conditional footer action display
- **Deviations from plan:** Used "Toggle Children" label instead of dynamic Expand/Collapse (Textual limitation with duplicate key bindings). Added `action_nav_up/down` column_id fix (not in original plan). Added check_action for movement actions (not in original plan).
- **Issues encountered:** Child tasks' `board_col` is empty (no boardcol metadata), causing navigation to fail when using `task_data.board_col`. Fixed by using `column_id` attribute on TaskCard. Textual's frozen Binding dataclass prevents runtime label changes, and duplicate key bindings don't show the second binding's label.
- **Key decisions:** Used `column_id` attribute on TaskCard rather than DOM-based column detection for simplicity and reliability.

## Step 9 Reference

Post-implementation: archive task and plan files per aitask-pick workflow.
