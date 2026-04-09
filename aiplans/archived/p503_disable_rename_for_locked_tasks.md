---
Task: t503_disable_rename_for_locked_tasks.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Plan

Disable the rename button in the board TUI task detail screen when a task is locked/assigned for implementation.

### Change

**File:** `.aitask-scripts/board/aitask_board.py:1860`

Add `or is_locked` to the rename button's `disabled` condition, matching the pattern used by the Lock button.

## Final Implementation Notes
- **Actual work done:** Added `or is_locked` to the rename button disabled condition at line 1860
- **Deviations from plan:** None — single-line change as planned
- **Issues encountered:** None
- **Key decisions:** Followed the existing pattern from the Lock button (line 1847) which already uses `disabled=is_done_or_ro or is_locked`
