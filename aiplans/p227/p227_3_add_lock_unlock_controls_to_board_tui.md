---
Task: t227_3_add_lock_unlock_controls_to_board_tui.md
Parent Task: aitasks/t227_aitask_own_failure_in_cluade_web.md
Sibling Tasks: aitasks/t227/t227_1_*.md, aitasks/t227/t227_2_*.md, aitasks/t227/t227_4_*.md, aitasks/t227/t227_5_*.md, aitasks/t227/t227_6_*.md
Worktree: (none - current branch)
Branch: main
Base branch: main
---

# Plan: t227_3 — Add lock/unlock controls to board TUI

## Context

Users need to manually lock tasks before starting Claude Web sessions. The board TUI has no lock-related functionality currently.

## Implementation Steps

### Step 1: Add lock status display to TaskDetailScreen
- Location: `aiscripts/board/aitask_board.py` after line 1247 (existing metadata fields)
- On screen open, run `aitask_lock.sh --check <task_id>` via subprocess (5s timeout)
- Parse YAML output for: locked_by, locked_at, hostname
- Display as ReadOnlyField with staleness indicator (>24h = warning)

### Step 2: Reorganize buttons into two rows
- Replace single `Horizontal(id="detail_buttons")` with:
  - `Horizontal(id="detail_buttons_workflow")`: Pick, Lock, Unlock, Close
  - `Horizontal(id="detail_buttons_file")`: Edit, Save Changes, Revert, Delete

### Step 3: Implement Lock button handler
- Show input dialog listing emails from `aitasks/metadata/emails.txt` + free text
- Pre-fill from `userconfig.yaml` if available (from t227_5)
- Run `aitask_lock.sh --lock <task_id> --email <email>` via subprocess
- Refresh lock status display and notify

### Step 4: Implement Unlock button handler
- If locked by different user: show confirmation dialog with lock metadata
- Run `aitask_lock.sh --unlock <task_id>` via subprocess
- Refresh and notify

### Step 5: Add lock indicator to TaskCard
- On board startup, run `aitask_lock.sh --list` to build lock map
- In TaskCard rendering, show lock indicator for locked tasks
- Handle missing lock infrastructure gracefully

### Step 6: Update CSS if needed
- Style the two button rows
- Style the lock indicator on cards

## Key Files
- **Modify:** `aiscripts/board/aitask_board.py` (TaskDetailScreen, TaskCard, board init)

## Reference Patterns
- Button: lines 1252-1266
- Subprocess: `revert_task()` lines 1307-1322
- ReadOnlyField: metadata display lines 1196-1247

## Verification
- `python -m py_compile aiscripts/board/aitask_board.py`
- Launch board, open task details, verify lock status
- Test Lock/Unlock buttons
- Verify lock indicator on kanban cards

## Post-Implementation (Step 9)
Archive this child task.
