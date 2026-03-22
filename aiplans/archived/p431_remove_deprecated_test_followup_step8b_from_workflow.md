---
Task: t431_remove_deprecated_test_followup_step8b_from_workflow.md
Worktree: (none - current branch)
Branch: main
Base branch: main
---

## Context

Task 428 deprecated the test-followup procedure and replaced it with `/aitask-qa`. However, two artifacts remain:
1. The deprecated procedure file `test-followup-task.md` still exists
2. SKILL.md still lists it in the Procedures section (line 486)

The `test_followup_task` profile key and Step 8b section were already removed by t428 — no work needed there.

## Plan

### 1. Delete `test-followup-task.md`
- Delete `.claude/skills/task-workflow/test-followup-task.md` — the file has a DEPRECATED banner and is no longer referenced by any active workflow step

### 2. Remove the deprecated listing from SKILL.md
- In `.claude/skills/task-workflow/SKILL.md` line 486, remove:
  ```
  - **Test Follow-up Task Procedure** (`test-followup-task.md`) — DEPRECATED: replaced by `/aitask-qa` skill.
  ```

### 3. No changes needed
- `profiles.md` — `test_followup_task` key is already absent
- Profile YAML files (`fast.yaml`, `default.yaml`, `remote.yaml`) — `test_followup_task` key is already absent
- `aitask-qa/SKILL.md` line 305 — mentions the deprecated procedure as historical context, fine to keep

## Verification
- `grep -r 'test.followup\|test-followup\|Step 8b' .claude/skills/task-workflow/` should return no matches (except possibly aitask-qa reference)
- `grep -r 'test_followup_task' aitasks/metadata/profiles/` should return no matches

## Final Implementation Notes
- **Actual work done:** Deleted `test-followup-task.md` and removed its listing from SKILL.md's Procedures section. Most cleanup (Step 8b section removal, profile key removal) was already done by t428.
- **Deviations from plan:** None — the task description listed 5 files to modify but investigation showed only 2 still had references to remove.
- **Issues encountered:** None.
- **Key decisions:** Kept the historical mention in `aitask-qa/SKILL.md` (line 305) since it provides useful context about the skill's origin.
