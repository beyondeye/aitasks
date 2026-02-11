---
priority: medium
effort: low
depends: []
issue_type: feature
status: Done
labels: [claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-10 11:04
updated_at: 2026-02-10 11:27
completed_at: 2026-02-10 11:27
---

When aitask-pick opens a parent task and finds it has an empty children_to_implement list, this means all child tasks have been completed but the parent task was not archived. The workflow should detect this case and proceed to archive the parent task (after notifying the user).

Similarly, when aitask-pick picks a task that is already in the 'Done' status but hasn't been archived yet, the workflow should:
1. Verify the task is actually done (check if there is a plan file in aiplans/ with implementation details)
2. If verified as complete, proceed to archive the task (after notifying the user), i.e., proceed to the post-implementation steps of the workflow

These two cases represent gaps in the current aitask-pick skill workflow that can leave completed tasks unarchived.

### Implementation Details

Modify the aitask-pick skill file at .claude/skills/aitask-pick/instructions.md:

**Case 1 - Orphaned parent task (empty children_to_implement):**
- After Step 0 selects a parent task and checks for children directory
- If children directory does NOT exist AND children_to_implement is empty, check for archived children
- If archived children exist, this is an orphaned parent -> notify user and offer to archive
- Execute post-implementation archival steps (Step 8 for parent tasks)

**Case 2 - Done but unarchived task:**
- After Step 0 reads the task file, check its status
- If status is 'Done', verify completion (check for plan file in aiplans/)
- Notify user and offer to archive
- Execute post-implementation archival steps (Step 8)
