---
priority: medium
effort: medium
depends: [t227_2]
issue_type: feature
status: Implementing
labels: [ui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-24 16:52
updated_at: 2026-02-24 22:09
---

Add lock status display and Lock/Unlock buttons to the board TUI task detail screen. Also reorganize the buttons into two rows and add lock indicators on kanban cards.

## Context

Users need to manually lock tasks before starting Claude Web sessions and unlock them after. The board TUI currently has no lock-related functionality. Also, the detail screen has too many buttons for a single row with the addition of Lock/Unlock.

## Key Files to Modify
- `aiscripts/board/aitask_board.py` -- TaskDetailScreen (lines 1144-1342), TaskCard, board init

## Reference Patterns
- Button pattern: existing Pick/Edit/Delete buttons at lines 1252-1266
- Subprocess pattern: `revert_task()` at lines 1307-1322
- ReadOnlyField pattern: metadata display at lines 1196-1247

## Changes

### 1. Lock Status Display
- On TaskDetailScreen open, run `aitask_lock.sh --check <task_id>` via subprocess (5s timeout)
- Parse YAML output: `locked_by`, `locked_at`, `hostname`
- Show ReadOnlyField: "Unlocked" or "Locked by <email> since <time> (<hostname>)"
- If `locked_at` > 24h ago: append "(may be stale)" in warning color
- Lock infrastructure unavailable: show "Not available"

### 2. Button Reorganization (Two Rows)
- Row 1 -- Workflow actions (`Horizontal(id="detail_buttons_workflow")`): Pick, Lock, Unlock, Close
- Row 2 -- File operations (`Horizontal(id="detail_buttons_file")`): Edit, Save Changes, Revert, Delete

### 3. Lock/Unlock Buttons (Row 1)
- "Lock" button (variant="warning"): disabled if already locked or Done/Folded/ReadOnly
- "Unlock" button (variant="error"): disabled if not locked
- Lock handler: prompt for email via input dialog (list stored emails + option to type new one). Run `aitask_lock.sh --lock`
- Unlock handler: if locked by different user, show confirmation with lock metadata. Run `aitask_lock.sh --unlock`
- After operation: refresh lock status display, notify user

### 4. Lock Indicator on TaskCard (Kanban Board)
- At board startup, run `aitask_lock.sh --list` once to build a lock map
- In TaskCard rendering, show lock indicator (emoji or CSS class) for locked tasks
- Handle lock infrastructure not initialized: silently skip

## Verification
- `python -m py_compile aiscripts/board/aitask_board.py`
- Launch board, open task details, verify lock status displays
- Test Lock/Unlock buttons, verify with `aitask_lock.sh --list`
- Verify lock indicator on kanban cards
