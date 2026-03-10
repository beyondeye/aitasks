---
Task: t360_task_with_no_code_but_child_task_create_archive_option.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

When a design-only parent task creates child tasks during planning (Step 6.1), the
workflow incorrectly proceeds to Step 8 (Review/Archive) after the child task checkpoint.
If the user archives the parent, the child tasks also get archived — destroying the work
just created.

## Root Cause

In `.claude/skills/task-workflow/SKILL.md` line 241, the Step 6 block says:
"After the checkpoint in `planning.md`, proceed to Step 7."

This is unconditional and doesn't account for the child-creation path in `planning.md`,
where the child task checkpoint can either end the workflow ("Stop here") or restart the
pick process ("Start first child"). Neither should proceed to Step 7/8/9.

## Fix

**File: `.claude/skills/task-workflow/SKILL.md`**

Replaced the unconditional "proceed to Step 7" with conditional logic:
- If child tasks were created and "Stop here" → END the workflow
- If child tasks were created and "Start first child" → restart with `/aitask-pick <parent>_1`
- Otherwise (normal single-task plan) → proceed to Step 7

This is a skill-definition fix only — no shell scripts changed.

## Verification

- Read the updated SKILL.md and trace through the child-task-creation scenario
- The parent task revert (status → Ready) and lock release still happen BEFORE the
  checkpoint (in planning.md lines 76-86), so they are unaffected

## Final Implementation Notes
- **Actual work done:** Added conditional branching in SKILL.md Step 6 to handle the three possible outcomes after the planning checkpoint: "Stop here" (end workflow), "Start first child" (restart pick), and normal plan (proceed to Step 7). Single-file, 4-line change.
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** The fix was placed in SKILL.md rather than planning.md because planning.md already correctly describes the child checkpoint behavior — the gap was in SKILL.md's unconditional "proceed to Step 7" instruction.
