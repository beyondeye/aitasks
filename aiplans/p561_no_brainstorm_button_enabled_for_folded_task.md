---
Task: t561_no_brainstorm_button_enabled_for_folded_task.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

## Context

In the aitask board TUI (`TaskDetailScreen`), the brainstorm button is enabled for tasks with status "Folded". Folded tasks are merged into another task and should not allow brainstorming — similar to how Pick, Edit, Revert, Rename, and Lock buttons are already disabled for folded tasks.

## Plan

**File:** `.aitask-scripts/board/aitask_board.py`, line 2090

**Change:** Add `is_done_or_ro` check to the brainstorm button's `disabled` condition, matching the pattern used by other workflow buttons.

Current:
```python
yield Button("(B)rainstorm", variant="primary", id="btn_brainstorm", disabled=self.read_only or is_locked)
```

Fixed:
```python
yield Button("(B)rainstorm", variant="primary", id="btn_brainstorm", disabled=is_done_or_ro or is_locked)
```

`is_done_or_ro` (line 1962) already encapsulates `is_done or is_folded or self.read_only`, so this single change covers folded tasks, done tasks, and read-only mode — and the `is_locked` check is preserved.

## Verification

1. Run `shellcheck` on modified files (N/A — Python file)
2. Launch `ait board`, open a folded task, verify the brainstorm button is grayed out / disabled
3. Open a normal "Ready" task and verify brainstorm button is still enabled
4. Open a "Done" task and verify brainstorm button is disabled
