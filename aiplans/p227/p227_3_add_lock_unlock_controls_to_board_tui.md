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

### Step 1: Add lock status display to TaskDetailScreen [DONE]
- Location: `aiscripts/board/aitask_board.py` after line 1247 (existing metadata fields)
- Uses lock map from TaskManager (populated via `--list`) instead of per-task `--check` calls
- Display as ReadOnlyField with staleness indicator (>24h = yellow warning)
- Shows "🔒 Locked: email on hostname since time" or "🔓 Lock: Unlocked"

### Step 2: Reorganize buttons into two rows [DONE]
- Replace single `Horizontal(id="detail_buttons")` with:
  - `Container(id="detail_buttons_area")` wrapping two rows
  - `Horizontal(id="detail_buttons_workflow")`: Pick, Lock, Unlock, Close
  - `Horizontal(id="detail_buttons_file")`: Save Changes, Revert, Edit, Delete
- Kept original `#detail_buttons` CSS for other modals (CommitMessageScreen, DeleteConfirmScreen, etc.)

### Step 3: Implement Lock button handler [DONE]
- Created `LockEmailScreen` modal with pre-filled Input from `_get_user_email()` (userconfig.yaml → emails.txt)
- Run `aitask_lock.sh --lock <task_id> --email <email>` via subprocess (15s timeout)
- Dismisses with "locked" to trigger board refresh

### Step 4: Implement Unlock button handler [DONE]
- If locked by different user: shows `UnlockConfirmScreen` confirmation dialog with lock metadata
- If locked by same user or no user email: unlocks directly
- Run `aitask_lock.sh --unlock <task_id>` via subprocess (15s timeout)
- Dismisses with "unlocked" to trigger board refresh

### Step 5: Add lock indicator to TaskCard [DONE]
- Added `lock_map` dict to TaskManager with `refresh_lock_map()` method
- Parses `aitask_lock.sh --list` output: `t<N>: locked by <email> on <hostname> since <time>`
- Lock map refreshed on every `refresh_board()` call (auto-refresh + manual + post lock/unlock)
- TaskCard shows "🔒 email" in info row for locked tasks

### Step 6: Update CSS [DONE]
- Added styles for `#detail_buttons_area`, `#detail_buttons_workflow`, `#detail_buttons_file`
- Preserved `#detail_buttons` CSS for other modal screens

## Key Files
- **Modified:** `aiscripts/board/aitask_board.py` (TaskManager, TaskCard, TaskDetailScreen, 2 new modal screens, CSS)

## Verification
- `python -m py_compile aiscripts/board/aitask_board.py` — passes
- Launch board, open task details, verify lock status displays
- Test Lock/Unlock buttons
- Verify lock indicator on kanban cards

## Post-Review Changes

### Change Request 1 (2026-02-24 23:30)
- **Requested by user:** Move lock indicator on TaskCard to its own line (before status line) instead of being inline with effort/labels/issue. Also confirmed lock line should remain visible when task status is Implementing and assigned.
- **Changes made:** Moved lock indicator from `info` list (effort/labels/issue row) to a separate `yield Label(...)` on its own line, positioned before the status/deps/children section. Lock shows regardless of task status.
- **Files affected:** `aiscripts/board/aitask_board.py` (TaskCard.compose)

## Final Implementation Notes
- **Actual work done:** Added ~170 lines to `aitask_board.py`: `_get_user_email()` helper, `refresh_lock_map()` in TaskManager, lock indicator in TaskCard, lock status ReadOnlyField in TaskDetailScreen, two-row button layout, `LockEmailScreen` and `UnlockConfirmScreen` modals, lock/unlock button handlers, CSS for new button rows.
- **Deviations from plan:** Used lock map (`--list`) instead of per-task `--check` for lock status on detail screen — more efficient since the map is already populated. Added `USERCONFIG_FILE` and `EMAILS_FILE` constants. Used `Container(id="detail_buttons_area")` as wrapper for the two button rows.
- **Issues encountered:** None — file compiled cleanly on first attempt.
- **Key decisions:** Lock map is refreshed on every `refresh_board()` call (shared with git status refresh). The "locked"/"unlocked" dismiss results from detail screen naturally fall through to the existing `refresh_board()` call in `check_edit`, so no explicit handling needed. Lock/Unlock buttons use emoji labels (🔒/🔓) for visual consistency with task card indicators.
- **Notes for sibling tasks:** The `_get_user_email()` function reads `userconfig.yaml` → `emails.txt` fallback, consistent with the shell `get_user_email()` from t227_5. The `lock_map` in TaskManager is a dict keyed by task_id string (e.g., "47" or "47_1") — same format as `aitask_lock.sh --list` output. Sibling t227_4 (make aitask-pick lock-aware) can reference this implementation for the lock check pattern.

## Post-Implementation (Step 9)
Archive this child task.
