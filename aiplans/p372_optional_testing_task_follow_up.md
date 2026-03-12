---
Task: t372_optional_testing_task_follow_up.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

When implementing features with AI code agents, automated testing is often handled within the task itself. But for complex features requiring deeper unit testing, integration tests, or end-to-end testing, a follow-up task ensures developers don't forget. This task adds an optional step in the task-workflow that creates a testing follow-up task just before archival, controlled by a new `test_followup_task` execution profile field.

## Plan

### Step 1: Add `test_followup_task` to execution profile infrastructure

**File: `.aitask-scripts/settings/settings_app.py`**

1. Add to `PROFILE_SCHEMA` (after `enableFeedbackQuestions` line ~96):
   ```python
   "test_followup_task": ("enum", ["yes", "no", "ask"]),
   ```

2. Add to `PROFILE_FIELD_INFO` (after `enableFeedbackQuestions` entry, ~line 200):
   ```python
   "test_followup_task": (
       "Create a testing follow-up task before archival",
       "Controls whether a follow-up task is created for testing after implementation (Step 8b):\n"
       "  'yes': always create a testing follow-up task\n"
       "  'no': never create a testing follow-up task\n"
       "  'ask': prompt the user to decide\n"
       "  (unset): same as 'ask'"
   ),
   ```

3. Add to `PROFILE_FIELD_GROUPS` — add a new group "Post-Implementation" after "Feedback" (~line 268):
   ```python
   ("Post-Implementation", ["test_followup_task"]),
   ```

### Step 2: Add default values to profile YAML files

**File: `aitasks/metadata/profiles/fast.yaml`** — Add `test_followup_task: ask`
**File: `aitasks/metadata/profiles/remote.yaml`** — Add `test_followup_task: no`
**File: `seed/profiles/fast.yaml`** — Add `test_followup_task: ask`
**File: `seed/profiles/remote.yaml`** — Add `test_followup_task: no`

### Step 3: Add Test Follow-up Task Procedure to procedures.md

**File: `.claude/skills/task-workflow/procedures.md`**

Add to Table of Contents:
```markdown
- [Test Follow-up Task Procedure](#test-follow-up-task-procedure) — Referenced from Step 8b
```

Add new procedure section (after Lock Release Procedure):

```markdown
## Test Follow-up Task Procedure

This procedure is referenced from Step 8b. It optionally creates a follow-up task for testing (integration tests, deeper unit tests, or end-to-end tests) based on the profile setting and user choice.

**Input:** `task_id`, `task_name`, `is_child`, `parent_id`, active profile

**Procedure:**

1. **Profile check:** If the active profile has `test_followup_task` set:
   - If `"yes"`: Create follow-up task. Display: "Profile '<name>': creating test follow-up task"
   - If `"no"`: Skip. Display: "Profile '<name>': skipping test follow-up". Return.
   - If `"ask"`: Show AskUserQuestion below

   Otherwise (no profile or key not set), show `AskUserQuestion`:
   - Question: "Would you like to create a follow-up task for testing? (integration tests, deeper unit tests, or end-to-end tests for the feature just implemented)"
   - Header: "Testing"
   - Options:
     - "Yes, create testing task" (description: "Create a follow-up task to brainstorm and add tests")
     - "No, skip" (description: "No additional testing task needed")

   If "No, skip": Return.

2. **Ask whether to brainstorm test ideas now:**

   Use `AskUserQuestion`:
   - Question: "Would you like to brainstorm specific test ideas now, or leave that to the follow-up task?"
   - Header: "Test ideas"
   - Options:
     - "Brainstorm now" (description: "Use available context to suggest specific tests in the task description")
     - "Leave to follow-up" (description: "Create task with basic reference info only — exploration happens when the task is picked")

3. **Compose follow-up task description** using context already available in the current conversation (do NOT run additional explorations):
   - Reference the current task by ID and name
   - Summarize what was implemented (from the plan's Final Implementation Notes or from memory of the implementation)
   - List key files that were modified
   - **If "Brainstorm now" was selected:**
     - Brainstorm specific testing ideas: integration tests, deeper unit tests, end-to-end tests relevant to the feature
     - Include any testing-relevant context already known (e.g., existing test patterns, test frameworks used, test directories)
   - **If "Leave to follow-up" was selected:**
     - Add a generic instruction: "Brainstorm ways to add integration tests, deeper unit tests, or end-to-end tests for the feature described above. Explore the codebase for existing test patterns and frameworks before proposing tests."
   - **Always include (regardless of brainstorm choice):**
     - If any tests were created or modified during the current task's implementation, reference them by file path so the follow-up task knows what test coverage already exists

4. **Create the task:**

   If `is_child` is true (create as sibling):
   ```bash
   ./.aitask-scripts/aitask_create.sh --batch --commit \
     --parent <parent_id> \
     --no-sibling-dep \
     --name "test_<short_description>" \
     --type test \
     --priority medium \
     --effort medium \
     --labels "testing" \
     --desc-file - <<'TASK_DESC'
   <composed description>
   TASK_DESC
   ```

   If `is_child` is false (create as standalone parent task):
   ```bash
   ./.aitask-scripts/aitask_create.sh --batch --commit \
     --name "test_t<task_id>_<short_description>" \
     --type test \
     --priority medium \
     --effort medium \
     --labels "testing" \
     --desc-file - <<'TASK_DESC'
   <composed description>
   TASK_DESC
   ```

5. Display: "Created testing follow-up task: <filename>"
```

### Step 4: Add Step 8b to task-workflow SKILL.md

**File: `.claude/skills/task-workflow/SKILL.md`**

1. Insert a thin **Step 8b: Test Follow-up Task** between Step 8 and Step 9:

   ```markdown
   ### Step 8b: Test Follow-up Task (Optional)

   After code is committed and before post-implementation cleanup, optionally create a follow-up task for testing.

   Execute the **Test Follow-up Task Procedure** (see `procedures.md`).

   Proceed to Step 9.
   ```

2. Update Step 8 "Commit changes" path: change "Proceed to Step 9" to "Proceed to Step 8b" (line ~342).

3. Add `Test Follow-up Task Procedure` to the Procedures list at the bottom of the file (~line 505-511):
   ```markdown
   - **Test Follow-up Task Procedure** — Optionally create testing follow-up task. Referenced from Step 8b.
   ```

### Step 5: Update profiles.md documentation

**File: `.claude/skills/task-workflow/profiles.md`**

Add `test_followup_task` to the schema table (after `enableFeedbackQuestions` row, line 31):

```markdown
| `test_followup_task` | string | no | `"yes"` = always create testing follow-up; `"no"` = never; `"ask"` = prompt; omit = ask | Step 8b |
```

### Step 6: Update website documentation

**File: `website/content/docs/skills/aitask-pick/execution-profiles.md`**

Add to the "Standard Profile Fields" table (after `explore_auto_continue` row, line 32):
```markdown
| `test_followup_task` | string | `"yes"`, `"no"`, or `"ask"` — create a testing follow-up task before archival |
```

Update the example YAML to include `test_followup_task: ask`.

**File: `website/content/docs/tuis/settings/reference.md`**

Add a new "Post-Implementation" section after the "Exploration" section (~line 111):
```markdown
### Post-Implementation

| Key | Type | Options | Description |
|-----|------|---------|-------------|
| `test_followup_task` | enum | `yes`, `no`, `ask` | Create a testing follow-up task before archival |
```

**File: `website/content/docs/tuis/settings/_index.md`**

Add to the profile field groups list (after "Exploration" line ~87):
```
- **Post-Implementation** -- test_followup_task
```

### Step 7: Verify

- Verify YAML syntax of modified profile files
- Verify Python syntax of settings_app.py
- Review all changes for consistency

## Files to Modify

1. `.aitask-scripts/settings/settings_app.py` — Profile schema, field info, field groups
2. `.claude/skills/task-workflow/procedures.md` — Add Test Follow-up Task Procedure
3. `.claude/skills/task-workflow/SKILL.md` — Add Step 8b (thin reference to procedure), update procedures list
4. `.claude/skills/task-workflow/profiles.md` — Add field to schema table
5. `aitasks/metadata/profiles/fast.yaml` — Add `test_followup_task: ask`
6. `aitasks/metadata/profiles/remote.yaml` — Add `test_followup_task: no`
7. `seed/profiles/fast.yaml` — Add `test_followup_task: ask`
8. `seed/profiles/remote.yaml` — Add `test_followup_task: no`
9. `website/content/docs/skills/aitask-pick/execution-profiles.md` — Add field to table + example
10. `website/content/docs/tuis/settings/reference.md` — Add Post-Implementation section
11. `website/content/docs/tuis/settings/_index.md` — Add group to list

## Verification

- `python3 -c "import yaml; yaml.safe_load(open('aitasks/metadata/profiles/fast.yaml'))"` — verify YAML
- `python3 -c "import yaml; yaml.safe_load(open('aitasks/metadata/profiles/remote.yaml'))"` — verify YAML
- `python3 -c "import ast; ast.parse(open('.aitask-scripts/settings/settings_app.py').read())"` — verify Python syntax
- Review procedure and step text for consistency with existing patterns

## Final Implementation Notes

- **Actual work done:** All 11 files modified as planned — added `test_followup_task` profile field to settings_app.py (schema, field info, field groups), both live and seed profile YAMLs, the Test Follow-up Task Procedure to procedures.md, Step 8b to SKILL.md, and all three website documentation pages.
- **Deviations from plan:** None — implementation followed the plan exactly.
- **Issues encountered:** Had to read remote.yaml before editing (tool requirement). No other issues.
- **Key decisions:** Placed `test_followup_task` in a new "Post-Implementation" group rather than in "Feedback" — keeps field grouping semantically clear.

## Post-implementation: Step 9 (archival, merge, cleanup)
