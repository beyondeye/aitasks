---
Task: t248_unlock_in_board_also_remove_assigned.md
Branch: main
Base branch: main
---

## Context

When unlocking a task in the `ait board` TUI, the lock is released but the task metadata (`status: Implementing`, `assigned_to: user@email.com`) is left unchanged. This means a task can appear as "Implementing" and assigned to someone even after being unlocked — which is misleading. The user wants a confirmation dialog that offers to reset the task back to "Ready" and clear the assignment when unlocking an Implementing+assigned task.

## Plan

### File modified
- `aiscripts/board/aitask_board.py`

### 1. Added `ResetTaskConfirmScreen` modal dialog (after `UnlockConfirmScreen`)

New `ModalScreen` subclass following the exact same pattern as `UnlockConfirmScreen`. Shows task status info and assignment, with "Reset to Ready" and "Keep current" buttons.

### 2. Modified `unlock_task()` method in `TaskDetailScreen`

After a successful unlock, checks if `status == "Implementing"` AND `assigned_to` is non-empty. If so, chains the `ResetTaskConfirmScreen` dialog before dismissing. On confirm: reloads task, sets status to "Ready", clears `assigned_to`, saves with timestamp. On decline: dismisses normally (lock released, metadata kept).

## Final Implementation Notes
- **Actual work done:** Implemented exactly as planned. Added `ResetTaskConfirmScreen` class (+40 lines) and modified `do_unlock()` (+15 lines) to chain the reset dialog after successful unlock.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Used `variant="warning"` for the "Reset to Ready" button to visually distinguish it from the destructive "Force Unlock" (`variant="error"`) in the existing `UnlockConfirmScreen`.
