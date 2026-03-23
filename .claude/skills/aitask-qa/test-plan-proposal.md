# Test Plan Proposal Procedure

Generates categorized test proposals based on change analysis and gap detection,
then determines the user's preferred action. Referenced from Step 5 of the main
SKILL.md workflow.

**Input:**
- Change analysis from Step 2 (categorized files, diff stats)
- Test coverage map from Step 3 (gaps identified)
- Test results from Step 4 (pass/fail, health score)
- `tier` — context variable: `s` (standard) or `e` (exhaustive). This procedure is never called when `tier = q`.
- Target task's `issue_type` from frontmatter
- `active_profile` — loaded execution profile (or null)

**Output:**
- Categorized test plan proposals
- User's chosen action (create task, implement, export, skip)

---

## 5a: Generate test proposals `[Tier: s, e]`

Based on change analysis (Step 2) and gap detection (Step 3), propose categorized test ideas:

- **Unit tests:** Individual function behavior, edge cases, error paths
- **Integration tests:** Cross-script interactions, end-to-end command flows
- **Edge cases:** Error handling, boundary conditions, platform compatibility (macOS/Linux)

Each proposal should include:
- What to test (specific function/behavior)
- Why (what risk it mitigates)
- How (test approach, framework to use)

### Regression test hints `[Tier: s, e]` (only for `issue_type: bug` tasks)

When the target task has `issue_type: bug` in its frontmatter, add a **Regression Testing** category to the test proposals:

- **Red-green verification cycle:**
  1. Write a test that reproduces the original bug (expected to fail without the fix)
  2. Verify the test fails when the fix is reverted (`git stash` or comment out fix)
  3. Verify the test passes with the fix in place

- Include this as a specific, actionable recommendation in the test plan

**When `tier = e`:** If the user selects "Implement tests now" in Step 5b, prompt them to actually perform the red-green cycle:
- Write the regression test first
- Offer to temporarily revert the fix to verify the test catches the bug
- Restore the fix and confirm the test passes

### Edge case brainstorming `[Tier: e]`

**Skip when `tier = s`.** Only run when `tier = e`.

Go beyond standard proposals to brainstorm deeper edge cases:
- Concurrency and race conditions (if applicable)
- Resource exhaustion (large files, many tasks, deep nesting)
- Platform-specific quirks (macOS BSD tools vs GNU, shell version differences)
- Malformed input and corrupt data (broken YAML frontmatter, missing fields)
- Interaction effects between the changed code and other features

## 5b: Determine action `[Tier: s, e]`

**Profile check:** If `qa_mode` is set, use that action directly:
- `"ask"` — show AskUserQuestion below
- `"create_task"` — proceed to Step 6 (create follow-up task)
- `"implement"` — enter implementation mode (implement tests in current session)
- `"plan_only"` — export test plan to a file and end

Display: "Profile '<name>': qa_mode=<value>"

Otherwise, use `AskUserQuestion`:
- Question: "How would you like to proceed with the test plan?"
- Header: "QA Action"
- Options:
  - "Create follow-up test task" (description: "Create an aitask with the test plan for later implementation")
  - "Implement tests now" (description: "Write and commit the proposed tests in this session")
  - "Export test plan only" (description: "Save the test plan to a file without creating a task")
  - "Skip" (description: "End QA analysis without further action")

**If "Skip":** Proceed to Step 7 (Satisfaction Feedback).
**If "Export test plan only":** Write the test plan to `aiplans/qa_t<task_id>.md` and proceed to Step 7.
**If "Implement tests now":** Implement the proposed tests, commit them, then proceed to Step 7.
**If "Create follow-up test task":** Proceed to Step 6.
