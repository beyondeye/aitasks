---
priority: low
effort: low
depends: []
issue_type: performance
status: Done
labels: [aitask_board]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-27 17:01
updated_at: 2026-03-29 08:43
completed_at: 2026-03-29 08:43
boardidx: 90
---

Follow-up to t472 (per-column refresh). Add a dedicated swap operation for adjacent tasks within a column that avoids rebuilding the entire column.

Currently `_move_task_vertical()` calls `refresh_column()` which destroys and recreates all cards in the column. For a simple swap of two adjacent tasks, this is overkill — we can just swap the two TaskCard widgets in the DOM.

## Proposed approach

Add a `swap_adjacent_cards(card_a, card_b)` method to KanbanApp that:
1. Swaps `board_idx` values on the two Task objects (already done by `TaskManager.swap_tasks()`)
2. Swaps the two TaskCard widgets' positions in the KanbanColumn DOM without rebuilding the column
3. Handles expanded children (if either parent has children visible, the child wrapper widgets move with the parent)
4. Preserves focus on the moved card

This is the most frequent board interaction (Shift+Up/Down) so eliminating the column rebuild here has the highest UX impact.

## Key files
- `.aitask-scripts/board/aitask_board.py` — `_move_task_vertical()` (~line 3509), `TaskManager.swap_tasks()` (~line 379)

## Reference
- t472 introduced `refresh_column()` / `_recompose_column()` using `textual.compose.compose()` for in-place column recomposition
- Textual's `Widget.move_child()` or `DOMNode.move_child()` may be useful for DOM reordering without remove/mount cycles
