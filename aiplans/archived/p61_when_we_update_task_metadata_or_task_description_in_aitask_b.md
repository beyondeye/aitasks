---
Task: t61_when_we_update_task_metadata_or_task_description_in_aitask_b.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: t61 - Git modification tracking & commit shortcuts for aitask_board

## Context

The aitask_board Python Textual app (`aitask_board/aitask_board.py`) allows editing task metadata (priority, effort, status, etc.) and moving tasks between columns. However:
- There's no visual indication of which tasks have unsaved/uncommitted changes vs the git repo
- There's no way to commit changes from within the board
- The `updated_at` metadata field is never updated when saving from the board
- Board saves can overwrite changes made externally by Claude Code (e.g., status set to "Implementing")

## Implementation Plan

All changes are in **`aitask_board/aitask_board.py`** (single file).

### Step 1: Add `datetime` import
### Step 2: Add helper methods to `Task` class (`_update_timestamp`, `save_with_timestamp`, `reload_and_save_board_fields`)
### Step 3: Update all 5 `task.save()` call sites to use new methods
### Step 4: Rewrite `TaskDetailScreen.save_changes()` with reload-merge-save pattern
### Step 5: Add git status tracking to `TaskManager`

- `refresh_git_status()` — runs `git status --porcelain -- aitasks/`, parses output using `.splitlines()` (not `.strip().splitlines()` to preserve leading whitespace in porcelain format), stores relative paths of modified `.md` files
- `is_modified(task)` / `get_modified_tasks()`

### Step 6: Show asterisk on modified task cards

- Modified tasks display `t61 *` with CSS class `task-modified` (orange `#FFB86C`)

### Step 7: Integrate git status refresh into board refresh

- `refresh_board()` calls `self.manager.refresh_git_status()` before rebuilding
- `action_view_details()` callback calls `refresh_board()` on dismiss of detail screen (regardless of result), so asterisk and commit actions update immediately after saving metadata or reverting

### Step 8: Add `CommitMessageScreen` modal
### Step 9: Add commit execution logic to `KanbanApp`

- `_git_commit_tasks()` stages only specific files (not `git add aitasks/`), preventing accidental commits of other changes

### Step 10: Add keyboard bindings (`c` and `C`)

- `c` — commit selected task, `C` — commit all modified tasks
- Both bindings show/hide dynamically in the footer via `check_action()`: `commit_selected` only visible when focused task is modified, `commit_all` only visible when any tasks are modified

### Step 11: Add Revert button to task detail dialog

- Added "Revert" button (variant="error") between "Save Changes" and "Edit" in `TaskDetailScreen`
- Button is disabled when the task has no git modifications
- On click, runs `git checkout -- <filepath>` to restore the last committed version
- After revert, reloads task data in-place (`task_data.load()`), dismisses dialog, and board refreshes automatically

## Bug Fixes During Implementation

- **Git status parsing bug**: Initial implementation used `result.stdout.strip().splitlines()` which stripped leading whitespace from the first line of `git status --porcelain` output. The porcelain format uses 2-character status codes (e.g., ` M`) where a leading space is significant. Fixed by using `.splitlines()` without `.strip()`.

## Verification

Manual testing of:
- Asterisk display (appears immediately after saving in detail dialog, disappears after commit or revert)
- `updated_at` timestamp (set on metadata saves and dependency removal, not on board-layout changes)
- Commit single (`c`) and commit all (`C`) with commit message dialog
- No-overwrite of external changes (reload-merge-save for metadata, reload-and-save-board-fields for layout)
- Board moves preserve externally-modified fields
- Dynamic footer visibility of commit shortcuts
- Revert button restores last committed version
