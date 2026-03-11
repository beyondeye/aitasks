---
Task: t368_keyboard_shortcuts_in_task_detail.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Add keyboard shortcuts to TaskDetailScreen buttons (t368)

## Context

The board TUI's `TaskDetailScreen` modal has 8 action buttons but no keyboard shortcuts. This is inconsistent with `PickCommandScreen` which uses the `(X)` pattern in button labels with matching `BINDINGS` + `action_*` methods. The task asks to follow the same pattern and ensure shortcuts only fire when the button is enabled.

## Changes (single file: `.aitask-scripts/board/aitask_board.py`)

### 1. Expanded BINDINGS (TaskDetailScreen class)

Added 16 bindings (lowercase + uppercase for each of 8 buttons) following the PickCommandScreen pattern with `show=False`.

### 2. Updated button labels in compose()

Changed button text to show shortcut hints:
- `Pick` -> `(P)ick`, `Lock` -> `(L)ock`, `Unlock` -> `(U)nlock`, `Close` -> `(C)lose`
- `Save Changes` -> `(S)ave Changes`, `Revert` -> `(R)evert`, `Edit` -> `(E)dit`, `Delete` -> `(D)elete`

### 3. Added action methods

Each action method checks `button.disabled` before delegating to the existing handler method, ensuring shortcuts only work when the corresponding button is enabled.

- [x] Step 1: Add BINDINGS
- [x] Step 2: Update button labels
- [x] Step 3: Add action methods
- [x] Syntax verification passed

## Final Implementation Notes
- **Actual work done:** Added keyboard shortcuts for all 8 buttons in TaskDetailScreen, matching the existing PickCommandScreen pattern exactly
- **Deviations from plan:** None — implemented as planned
- **Issues encountered:** None
- **Key decisions:** Used the same `show=False` + dual case binding pattern from PickCommandScreen; each action method checks `button.disabled` before delegating to prevent shortcuts firing on disabled buttons
