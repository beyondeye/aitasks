---
Task: t497_brainstorm_action_from_board.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Add Brainstorm Action to Board TUI (t497)

## Context

The board TUI needs a "Brainstorm" action in the task detail screen. When triggered, it opens an `AgentCommandScreen` dialog (like pick/create do) to launch the brainstorm TUI (`ait brainstorm <num>`) either in the terminal or via tmux.

## Steps

1. Add `BRAINSTORM_TUI_SCRIPT` constant
2. Add `b`/`B` bindings to `TaskDetailScreen.BINDINGS`
3. Add `(B)rainstorm` button in `detail_buttons_workflow` row
4. Add button press handler (`brainstorm_task`)
5. Add `action_brainstorm()` method
6. Handle `"brainstorm"` result in `check_edit` callback
7. Add `_run_brainstorm_in_terminal()` method
8. Add board-level `b` binding to `KanbanApp.BINDINGS`
9. Add `check_action` guard for `brainstorm_task`
10. Add `action_brainstorm_task()` method to KanbanApp

## Final Implementation Notes

- **Actual work done:** All 10 steps implemented as planned in a single file (`aitask_board.py`). Added brainstorm action at both TaskDetailScreen level (button + keybinding) and KanbanApp board level (keybinding).
- **Deviations from plan:** None — implementation followed the plan exactly.
- **Issues encountered:** None.
- **Key decisions:**
  - Button uses `variant="primary"` to differentiate from Pick's "warning"
  - Button disabled only in `read_only` mode (brainstorming works on any task including done)
  - Follows the "create task" pattern (direct script) rather than "pick" pattern (codeagent dry-run)
  - Follow-up task t509 created for tmux window deduplication
