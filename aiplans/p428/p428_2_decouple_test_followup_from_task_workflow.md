---
Task: t428_2_decouple_test_followup_from_task_workflow.md
Parent Task: aitasks/t428_new_skill_aitask_qa.md
Sibling Tasks: aitasks/t428/t428_1_*.md, aitasks/t428/t428_3_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Decouple test-followup from task-workflow

## Overview

Remove Step 8b (Test Follow-up Task) from the shared task-workflow and replace with a reference to the standalone `/aitask-qa` skill. Clean up profile keys and references.

## Steps

### 1. Edit `.claude/skills/task-workflow/SKILL.md`

- **Remove Step 8b section** (lines ~335-341): Delete the entire "### Step 8b: Test Follow-up Task (Optional)" section
- **Add note after Step 8 commit** (after "Proceed to Step 9" in the "Commit changes" path): Add a brief note:
  ```
  **Note:** For test coverage analysis and test plan generation, run `/aitask-qa <task_id>` after implementation.
  ```
- **Update Procedures list** (~line 493): Change the test-followup-task entry to indicate deprecation:
  ```
  - **Test Follow-up Task Procedure** (`test-followup-task.md`) — DEPRECATED: replaced by `/aitask-qa` skill
  ```
- **Update Step 6 reference** (~line 214): The note "If child tasks were created and the child checkpoint returned 'Stop here' → collect Satisfaction Feedback" currently mentions proceeding to Step 8b indirectly. Verify the flow: Step 8 → Step 9 (no Step 8b in between).

### 2. Edit `.claude/skills/task-workflow/test-followup-task.md`

Add deprecation header at the very top (before existing content):
```markdown
> **DEPRECATED:** This procedure has been replaced by the standalone `/aitask-qa` skill.
> It is retained for historical reference only. See `.claude/skills/aitask-qa/SKILL.md`.

---

```

### 3. Edit `.claude/skills/task-workflow/profiles.md`

- Remove the `test_followup_task` row from the schema table
- Add new rows for aitask-qa profile keys:
  - `qa_mode` | string | no | `"ask"`, `"create_task"`, `"implement"`, `"plan_only"` | aitask-qa Step 5
  - `qa_run_tests` | bool | no | `true` = run tests; `false` = skip | aitask-qa Step 4

### 4. Edit profile files

- `aitasks/metadata/profiles/fast.yaml`: Remove line `test_followup_task: ask`
- `aitasks/metadata/profiles/remote.yaml`: Remove line `test_followup_task: no`

### 5. Search and update all references

Run: `grep -r "test_followup_task\|test-followup-task\|Step 8b" .claude/skills/ aitasks/metadata/profiles/`

Update any found references. Known locations:
- `.claude/skills/aitask-pickrem/SKILL.md` — may reference Step 8b
- `.claude/skills/aitask-pickweb/SKILL.md` — may reference Step 8b
- Memory file `feedback_test_followup.md` — update to reference `/aitask-qa`

## Verification

1. `grep -r "test_followup_task\|test-followup\|Step 8b" .claude/ aitasks/metadata/profiles/` — should return only the deprecated file and updated references
2. Verify YAML validity of fast.yaml and remote.yaml
3. Read through SKILL.md Step 8 → Step 9 flow to confirm no broken references

## Post-Implementation

Step 9 of task-workflow for archival.
