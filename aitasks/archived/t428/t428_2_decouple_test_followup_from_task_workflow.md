---
priority: high
effort: medium
depends: [t428_1]
issue_type: refactor
status: Done
labels: [testing, qa]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-22 11:22
updated_at: 2026-03-22 12:40
completed_at: 2026-03-22 12:40
---

## Context

Remove the test-followup-task procedure integration from task-workflow Step 8b. The new `/aitask-qa` skill (t428_1) replaces this embedded procedure with a standalone, more capable alternative. This child task handles the cleanup and decoupling.

## Key Files to Modify

- **`.claude/skills/task-workflow/SKILL.md`** (~line 335-341): Remove Step 8b section entirely. Replace with a brief note after Step 8 commit: "For test coverage analysis, run `/aitask-qa <task_id>` after implementation."
- **`.claude/skills/task-workflow/test-followup-task.md`**: Keep file but add deprecation header at the top
- **`.claude/skills/task-workflow/profiles.md`** (~line 32): Remove `test_followup_task` row from schema table. Add `qa_mode` and `qa_run_tests` rows.
- **`aitasks/metadata/profiles/fast.yaml`** (line 11): Remove `test_followup_task: ask`
- **`aitasks/metadata/profiles/remote.yaml`**: Remove `test_followup_task: no`
- **All files referencing `test-followup-task` or Step 8b**: Search and update

## Implementation Steps

1. Edit `task-workflow/SKILL.md`:
   - Remove the "### Step 8b: Test Follow-up Task (Optional)" section (lines ~335-341)
   - After Step 8 "Commit changes" path (before Step 9), add: "**Note:** For test coverage analysis and test plan generation, run `/aitask-qa <task_id>` after implementation."
   - Update the Procedures list at the bottom to mark test-followup-task.md as deprecated
   - Update Step numbering if needed (Step 9 stays as Step 9)

2. Edit `test-followup-task.md`:
   - Add deprecation header at top:
     ```
     > **DEPRECATED:** This procedure has been replaced by the standalone `/aitask-qa` skill.
     > It is retained for historical reference only. See `.claude/skills/aitask-qa/SKILL.md`.
     ```

3. Edit `profiles.md`:
   - Remove `test_followup_task` row from the schema table
   - Add new rows for `qa_mode` and `qa_run_tests` (these are aitask-qa profile keys)

4. Edit profile files:
   - `fast.yaml`: Remove `test_followup_task: ask` line
   - `remote.yaml`: Remove `test_followup_task: no` line

5. Search for other references:
   - `grep -r "test_followup_task\|test-followup-task\|Step 8b" .claude/skills/`
   - Update any found references

## Reference Files

- `.claude/skills/task-workflow/SKILL.md` — Main workflow containing Step 8b
- `.claude/skills/task-workflow/test-followup-task.md` — Procedure to deprecate
- `.claude/skills/task-workflow/profiles.md` — Profile schema docs
- `.claude/skills/aitask-pick/SKILL.md` — References Step 8b indirectly
- `aitasks/metadata/profiles/fast.yaml` — Profile to clean up
- `aitasks/metadata/profiles/remote.yaml` — Profile to clean up
- Memory file `feedback_test_followup.md` — References the old Step 8b behavior

## Verification Steps

1. Search for any remaining references: `grep -r "test_followup_task\|test-followup\|Step 8b" .claude/ aitasks/metadata/profiles/`
2. Verify fast.yaml and remote.yaml parse correctly: `python3 -c "import yaml; yaml.safe_load(open('aitasks/metadata/profiles/fast.yaml'))"`
3. Read through task-workflow/SKILL.md to verify Step 8 flows directly to Step 9
