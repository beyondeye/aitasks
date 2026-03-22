> **DEPRECATED:** This procedure has been replaced by the standalone `/aitask-qa` skill.
> It is retained for historical reference only. See `.claude/skills/aitask-qa/SKILL.md`.

---

# Test Follow-up Task Procedure

This procedure is referenced from Step 8b. It optionally creates a follow-up task for testing (integration tests, deeper unit tests, or end-to-end tests) based on the profile setting and user choice.

**Input:** `task_id`, `task_name`, `is_child`, `parent_id`, active profile

**Procedure:**

0. **Pre-check — tests already created:** If automated tests (unit tests, integration tests, end-to-end tests, etc.) were already created or modified as part of this task's implementation, skip this entire procedure — a test follow-up task is not needed. Display: "Tests already created/modified in this task. Skipping test follow-up." and return.

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
