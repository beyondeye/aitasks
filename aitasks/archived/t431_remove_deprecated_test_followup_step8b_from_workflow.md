---
priority: high
effort: low
depends: []
issue_type: chore
status: Done
labels: [skills]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-22 13:03
updated_at: 2026-03-22 13:13
completed_at: 2026-03-22 13:13
---

## Context

Task 428 refactored the test follow-up procedure into a standalone `/aitask-qa` skill. The `test-followup-task.md` procedure file already has a `DEPRECATED` banner at the top. However, the main `task-workflow/SKILL.md` still references Step 8b and calls the deprecated procedure, causing users to be prompted with "Would you like to create a follow-up task for testing?" during every task completion.

## Key Files to Modify
- `.claude/skills/task-workflow/SKILL.md` — Remove Step 8b section and its reference from Step 8 ("Proceed to Step 8b")
- `aitasks/metadata/profiles/fast.yaml` — Remove `test_followup_task` key (no longer used)
- `aitasks/metadata/profiles/default.yaml` — Remove `test_followup_task` key if present
- `aitasks/metadata/profiles/remote.yaml` — Remove `test_followup_task` key if present
- `.claude/skills/task-workflow/profiles.md` — Remove `test_followup_task` from the profile schema documentation

## Implementation
1. In `SKILL.md`: Remove the entire "Step 8b: Test Follow-up Task" section (lines referencing test-followup-task.md)
2. In `SKILL.md`: Update Step 8 "Commit changes" path to go directly to Step 9 instead of "Proceed to Step 8b"
3. Remove `test_followup_task` from all profile YAML files
4. Update profile schema docs to remove `test_followup_task` key
5. Optionally delete `.claude/skills/task-workflow/test-followup-task.md` entirely (or keep for historical reference)

## Manual Verification
1. Run `/aitask-pick` on a task, complete implementation, commit — should NOT be asked about test follow-up
2. Check that `/aitask-qa` still works independently as the replacement
