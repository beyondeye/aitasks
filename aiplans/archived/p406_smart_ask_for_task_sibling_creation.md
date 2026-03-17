---
Task: t406_smart_ask_for_task_sibling_creation.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

Task 406: The test-followup-task procedure always asks about creating a test follow-up task, even when tests were already created during the current implementation. Add a simple instruction to skip the procedure when tests already exist.

## Plan

### File: `.claude/skills/task-workflow/test-followup-task.md`

Add a single pre-check instruction (Step 0) before Step 1 to skip the procedure when tests were already created/modified.

### File: `memory/feedback_test_followup.md`

Update to reflect new behavior (auto-skip when tests already exist, otherwise respect profile setting).

## Final Implementation Notes
- **Actual work done:** Added Step 0 pre-check to `test-followup-task.md` that instructs the agent to skip the entire procedure if automated tests were already created/modified in the current task. Updated the feedback memory to reflect the new two-tier logic (pre-check first, then profile setting).
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Kept the instruction as simple prose (no git-based detection logic) per user feedback. The executing agent uses its conversation context to determine whether tests were created.
