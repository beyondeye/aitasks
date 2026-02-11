---
Task: t60_aitask_create_integration_in_board.md
Branch: main (working on current branch)
Base branch: main
---

# Plan: Integrate aitask_create into aiboard TUI

## Context

The aiboard Python TUI (Textual-based kanban board) needs a keyboard shortcut to spawn a new terminal running the interactive `aitask_create.sh` script. This follows the existing pattern used by `run_aitask_pick` which already spawns a new terminal for Claude.

## File to modify

- `aitask_board/aitask_board.py` (single file)

## Implementation Steps

### 1. Add keybinding `n` for "New Task"

Add after the existing git commit bindings in the BINDINGS list.

### 2. Add `action_create_task()` method

Following the exact `run_aitask_pick` pattern — spawn a new terminal running `./aitask_create.sh`.

## Verification

1. Run the board app
2. Press `n` — new terminal opens with aitask_create.sh
3. Create a task, press `r` to refresh board

## Post-Review Changes

### Change Request 1 (2026-02-10 11:45)
- **Requested by user:** Move column movement shortcuts to the end of the footer bar
- **Changes made:** Moved `ctrl+right`/`ctrl+left` Column Movement bindings to the end of the BINDINGS list
- **Files affected:** `aitask_board/aitask_board.py`

## Final Implementation Notes
- **Actual work done:** Added `n` keybinding and `action_create_task()` method to spawn a new terminal running `./aitask_create.sh`. Also reordered BINDINGS to move column movement shortcuts to the end of the footer bar per user request.
- **Deviations from plan:** Original task suggested `c` key but it was already taken by Commit; used `n` instead. Added footer reordering as post-review change.
- **Issues encountered:** None.
- **Key decisions:** Used `subprocess.Popen` (not `self.suspend()`) to spawn an independent terminal, matching the existing `run_aitask_pick` pattern.

## Post-Implementation

Step 9 from aitask-pick: archive task and plan files.
