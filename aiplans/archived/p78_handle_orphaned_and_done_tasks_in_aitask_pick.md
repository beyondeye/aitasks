---
Task: t78_handle_orphaned_and_done_tasks_in_aitask_pick.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

# Plan: Handle Orphaned and Done-but-Unarchived Tasks in aitask-pick (t78)

## Context

The aitask-pick skill workflow has two gaps where completed tasks can remain unarchived:
1. **Orphaned parent tasks**: A parent task whose children are all completed and archived, but the parent itself was never archived.
2. **Done but unarchived tasks**: A task with `status: Done` that was never moved to `aitasks/archived/`.

Root cause of gap #1: In current Step 8 for child tasks, when all children are complete, the workflow only says "Parent task can now be completed" but never actually archives the parent.

## Implementation Steps

### Step 1: Renumber steps and insert new Step 3 "Task Status Checks"
- [x] Insert new Step 3 between current Step 2 and Step 3
- [x] Renumber old Steps 3-8 to Steps 4-9

### Step 2: Update all cross-references
- [x] Fix all step number references throughout the file

### Step 3: Fix child task completion in Step 9 to auto-archive parent
- [x] Update "Check if all children complete" to actually archive the parent

## Final Implementation Notes
- **Actual work done:** All three planned changes implemented as described. Added new Step 3 (Task Status Checks) with two checks for done-but-unarchived and orphaned parent tasks. Renumbered all subsequent steps (old 3→4, 4→5, 5→6, 6→7, 7→8, 8→9). Updated all cross-references. Fixed Step 9 child completion to auto-archive the parent task when all children are done.
- **Deviations from plan:** Simplified sub-step numbering from "6.1-6.6" to "6.1" per user feedback, since sub-steps beyond 6.1 were never individually referenced.
- **Issues encountered:** The replace_all for Step 0 references missed one occurrence due to different indentation levels (4 spaces vs 6 spaces). Fixed with a separate targeted edit.
- **Key decisions:** Status checks happen after task selection (Step 3) rather than before (originally proposed as Step 0.5/1), for more logical flow.
