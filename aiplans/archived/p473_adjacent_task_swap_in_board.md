---
Task: t473_adjacent_task_swap_in_board.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# Plan: Adjacent Task Swap in Board TUI

## Context

`_move_task_vertical()` (Shift+Up/Down) is the most frequent board interaction. Currently it calls `refresh_column()` which destroys all widgets in the column via `remove_children()` and re-creates them via `mount_all()`. For a simple swap of two adjacent tasks, we can use Textual's `Widget.move_child()` to reorder widgets in the DOM directly — no destroy/recreate cycle needed.

## Key file

`.aitask-scripts/board/aitask_board.py`

## Implementation

### Step 1: Add `_swap_adjacent_cards()` method to KanbanApp

Insert before `_move_task_vertical()` (~line 3505). This method swaps the DOM positions of two adjacent task "blocks" (a TaskCard plus any trailing child-wrapper Horizontals for expanded children).

### Step 2: Modify `_move_task_vertical()` to use DOM swap

Replace the `refresh_column()` call with logic that finds both TaskCard widgets, determines above/below based on direction, calls `_swap_adjacent_cards()`, and falls back to `refresh_column()` if either card isn't in the DOM.

## Verification

1. Run the board: `./ait board`
2. Test Shift+Up / Shift+Down on tasks in various positions
3. Test with expanded parent tasks (children visible)
4. Test with filtered view active
5. Verify focus stays on the moved card
6. Test rapid repeated swaps
7. Edge cases: single-task column, task at column boundaries

## Final Implementation Notes
- **Actual work done:** Added `_swap_adjacent_cards()` method and modified `_move_task_vertical()` to use DOM-level `Widget.move_child()` instead of full column rebuild via `refresh_column()`. Fallback to `refresh_column()` if widgets aren't found in the DOM.
- **Deviations from plan:** None — implementation matched plan exactly.
- **Issues encountered:** None.
- **Key decisions:** Used `move_child(widget, before=anchor)` in a loop over the below-block to naturally handle expanded child-wrappers. The anchor stays stable because it's the card_above widget reference.

## Step 9 Reference

After implementation: User review → commit → archive → push per task-workflow Step 9.
