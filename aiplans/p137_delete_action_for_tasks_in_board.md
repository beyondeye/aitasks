---
Task: t137_delete_action_for_tasks_in_board.md
Branch: main (no worktree)
---

## Context

The aitask board TUI needs a Delete button in the task detail screen. Requirements:
- Only non-Implementing tasks can be deleted
- Child tasks cannot be deleted individually (would break parent's subdivision)
- Deleting a parent with children deletes all children too
- Associated plan files are also deleted
- Confirmation dialog shows all files that will be removed

## File to modify

`aiscripts/board/aitask_board.py`

## Implementation Plan

### 1. Add `DeleteConfirmScreen` modal (~after line 783)

Follow the `RemoveDepConfirmScreen` pattern. Accept a list of filenames to display.

### 2. Modify `TaskDetailScreen.compose()` button row (line ~995-1003)

- Rename `"Edit (System Editor)"` → `"Edit"`
- Add Delete button, disabled if status is Implementing OR if it's a child task

### 3. Add Delete button handler in `TaskDetailScreen` (~after line 1064)

### 4. Handle "delete" result in `KanbanApp.action_view_details()` (line ~1418)

- Collect all files to delete (task + plan + children + child plans)
- Show DeleteConfirmScreen with file list
- On confirmation: `git rm`, remove empty dirs, `git commit`, reload board

### 5. Add CSS rule for disabled delete button (~line 1146)

## Verification

- Run `python aiscripts/board/aitask_board.py`
- Open detail for a non-Implementing parent task → Delete button enabled
- Open detail for a child task → Delete button disabled
- Open detail for Implementing task → Delete button disabled
- Click Delete → dialog shows all files to be deleted
- Cancel → returns to detail screen
- Confirm → files deleted, committed, board refreshes

## Final Implementation Notes
- **Actual work done:** Implemented all planned items plus two additional user-requested features: (1) dynamic delete button state updates when cycling status field, (2) Done tasks are now read-only with all action buttons disabled, and Done status cannot be set manually via the CycleField
- **Deviations from plan:** Added `_update_delete_button()` method to dynamically toggle the button. For Done tasks, replaced CycleFields with ReadOnlyFields and disabled Pick/Revert/Edit/Delete buttons. Removed "Done" from status cycle options.
- **Issues encountered:** None
- **Key decisions:** Child task detection uses `filepath.parent.name.startswith("t")` to distinguish child tasks (in `aitasks/t<N>/`) from parent tasks (in `aitasks/`). Used `git rm -f` with fallback to `os.remove` for untracked files.
