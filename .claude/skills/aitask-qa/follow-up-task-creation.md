# Follow-up Task Creation Procedure

Creates a structured follow-up test task based on the QA analysis. Referenced
from Step 6 of the main SKILL.md workflow.

**Input:**
- `task_id` — target task identifier
- `is_child` — whether the target task is a child task
- `parent_id` — parent number if child task
- Change summary from Step 2
- Test coverage map from Step 3
- Test proposals from Step 5

**Output:**
- Created task file path

---

## Compose task description

Include in the follow-up task:
- Reference to the target task by ID and name
- Change summary from Step 2 (files modified, diff stats)
- Test coverage map from Step 3
- Specific test proposals from Step 5
- Existing test patterns to follow (discovered in Step 3a)

## Create the task

Execute the **Batch Task Creation Procedure** (see `../task-workflow/task-creation-batch.md`) with:

**If `is_child` is true** (create as sibling of the target task's parent):
- mode: `child`
- parent_num: `<parent_id>`
- no_sibling_dep: `true`
- name: `"test_<short_description>"`
- priority: `medium`
- effort: `medium`
- issue_type: `test`
- labels: `"testing,qa"`
- description: `<composed description>`

**If `is_child` is false** (create as standalone task):
- mode: `parent`
- name: `"test_t<task_id>_<short_description>"`
- priority: `medium`
- effort: `medium`
- issue_type: `test`
- labels: `"testing,qa"`
- description: `<composed description>`

Display: "Created testing follow-up task: <filename>"
