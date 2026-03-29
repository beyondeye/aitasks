---
Task: t476_childs_do_not_expand.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

Parent task children cannot be expanded/collapsed with "x" on the board TUI. The issue occurs even on fresh board load — pressing "x" on a parent task that has children has no visible effect. A full refresh with "r" only fixes it if the parent happens to be internally marked as expanded (in `expanded_tasks` set). This is NOT related to the DOM swap optimization.

## Root Cause

Classic Python `or` gotcha with mutable default arguments at `.aitask-scripts/board/aitask_board.py` line 759:

```python
self.expanded_tasks = expanded_tasks or set()
```

When the board starts, `self.expanded_tasks` is `set()` (empty). This empty set is passed to each `KanbanColumn` during `refresh_board()`. But `set()` is **falsy** in Python, so `expanded_tasks or set()` creates a **brand new empty set** instead of preserving the shared reference.

**Effect:**
- Board's `expanded_tasks` and each KanbanColumn's `expanded_tasks` are **different objects**
- `_toggle_expand()` modifies the board's set, but `compose()` reads the column's (separate) set
- Children never render because the column's set is always empty

**Why "r" sometimes fixes it:**
- After toggling "x" a few times, the board's set becomes non-empty (truthy)
- `refresh_board()` creates NEW columns, passing the now-truthy set
- `expanded_tasks or set()` returns the board's actual set (truthy wins over `set()`)
- Column now shares the correct reference → children render → future toggles work

## Fix

**File:** `.aitask-scripts/board/aitask_board.py`, line 759

Change:
```python
self.expanded_tasks = expanded_tasks or set()
```
To:
```python
self.expanded_tasks = expanded_tasks if expanded_tasks is not None else set()
```

This preserves the shared set reference even when empty, while still handling `None` gracefully.

## Verification

1. Launch `ait board` fresh. Focus a parent task with children. Press "x" → children should expand immediately
2. Press "x" again → children collapse
3. Move tasks up/down, then press "x" → still works
4. Press "r" → board state consistent, expand/collapse still works
5. Switch view modes and back → expand/collapse works

## Final Implementation Notes
- **Actual work done:** Single-line fix at `.aitask-scripts/board/aitask_board.py` line 759 — changed `expanded_tasks or set()` to `expanded_tasks if expanded_tasks is not None else set()`
- **Deviations from plan:** None — the fix was exactly as planned
- **Issues encountered:** Initial investigation went down a DOM swap rabbit hole before the user clarified the real symptoms (expand/collapse failing on fresh load, not related to task movement)
- **Key decisions:** Used `is not None` check rather than removing the default entirely, to maintain the same API contract for KanbanColumn
