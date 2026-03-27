---
task_id: 472
plan_status: completed
---

# Plan: Per-column refresh in board (t472)

## Context

The board TUI reloaded all tasks from disk and rebuilt the entire UI on any update. This task introduces granular refresh primitives to replace full reloads where possible.

## Approach

Added 4 new methods and updated 6 call sites in `aitask_board.py`.

### New Methods

1. **`TaskManager.reload_task(filename)`** — Reload single task from disk, handling parent/child/new/deleted cases
2. **`KanbanApp._recompose_column(col_widget)`** — Replace column contents in-place using `textual.compose.compose()` to avoid layout flicker
3. **`KanbanApp.refresh_column(col_id)`** — Re-render single column, with edge-case handling for unordered column appearing/disappearing
4. **`KanbanApp.refresh_columns(col_ids)`** — Re-render multiple columns (used for lateral task moves)

### Call Site Changes

| Call site | Before | After |
|-----------|--------|-------|
| `_toggle_expand()` | `refresh_board()` | `refresh_column(col_id)` |
| `_move_task_lateral()` | `refresh_board()` | `refresh_columns({old, new})` |
| `_move_task_vertical()` | `refresh_board()` | `refresh_column(col_id)` |
| `_move_task_to_extreme()` | `refresh_board()` | `refresh_column(col_id)` |
| `check_edit` default | `refresh_board()` | `reload_task()` + column refresh |
| `on_action_chosen` cancel | `refresh_board()` | `apply_filter()` only |

### Key Design Decision

Initial approach replaced column widgets entirely (`mount(before=old) + old.remove()`), causing visible flicker. Fixed by switching to in-place content replacement: `remove_children()` + `_compose_widgets(col)` + `mount_all()`, which keeps the column shell in the DOM.

## Final Implementation Notes
- **Actual work done:** All 4 primitives implemented, 6 call sites updated, flicker-free in-place recomposition
- **Deviations from plan:** Initial widget-swap approach caused visible flicker; rewrote to use `textual.compose.compose()` for in-place content replacement
- **Issues encountered:** Textual's `Widget.recompose()` is async-only; used the public `textual.compose.compose()` function instead for synchronous contexts
- **Key decisions:** Kept full reload for: startup, manual refresh, timer, sync, create, archive, delete, column structure changes
