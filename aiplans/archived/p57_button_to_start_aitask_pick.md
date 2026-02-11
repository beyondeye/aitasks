---
Task: t57_button_to_start_aitask_pick.md
Branch: main
Base branch: main
---

## Context

Task t57 requests adding a "Pick" button to the aitask_board task detail screen that opens a new terminal and launches Claude Code with `/aitask-pick <task_number>`. Additionally, the user wants status and assigned_to information displayed on the task cards in the board view (currently only shown in the detail screen).

## File to modify
- `aitask_board/aitask_board.py`

## Changes

### 1. Show status and assigned_to on TaskCard (board view)

In `TaskCard.compose()` (line ~198), add status and assigned_to to the info line displayed on each card.

### 2. Add "Pick" button to TaskDetailScreen

In `TaskDetailScreen.compose()` (line ~403), add a "Pick" button as the first button in the button row.

### 3. Add Pick button handler in TaskDetailScreen

Handler dismisses the modal with `"pick"` result.

### 4. Handle "pick" result in KanbanApp.action_view_details

Update the callback to also handle `"pick"` result.

### 5. Add `run_aitask_pick` method to KanbanApp

Opens a new terminal via `$TERMINAL` env var and launches `claude "/aitask-pick <N>"` using `subprocess.Popen`.

## Verification

1. Run the board: `python aitask_board/aitask_board.py`
2. Verify task cards now show status and assigned_to on a second info line
3. Open a task detail (Enter), verify "Pick" button appears
4. Click "Pick" — a new terminal should open with Claude Code running `/aitask-pick <N>`
5. Verify the board remains responsive after launching
