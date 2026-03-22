---
name: aitask-qa
description: Run QA analysis on any task — analyze changes, discover test gaps, run tests, and create follow-up test tasks
user-invocable: true
---

## Workflow

### Step 0 (pre-parse): Extract `--profile` argument

If the skill arguments contain `--profile <name>`:
- Extract the `<name>` value (the word following `--profile`)
- Store it as `profile_override`
- Remove `--profile <name>` from the argument string before passing to Step 0b
- If `--profile` appears but no name follows, warn: "Missing profile name after --profile" and set `profile_override` to null

If no `--profile` in arguments, set `profile_override` to null.

### Step 0a: Select Execution Profile

Execute the **Execution Profile Selection Procedure** (see `.claude/skills/task-workflow/execution-profile-selection.md`) with:
- `skill_name`: `"qa"`
- `profile_override`: the value parsed from `--profile` argument (or null)

Store the selected profile as `active_profile`. Initialize `feedback_collected` to `false`.

### Step 1: Task Selection

Accept optional task ID argument: `/aitask-qa 42` or `/aitask-qa 16_2`

#### 1a: Direct Task Selection (if argument provided)

**Format 1: Parent or standalone task (e.g., `/aitask-qa 42`):**
- Try active first:
  ```bash
  ./.aitask-scripts/aitask_query_files.sh resolve <number>
  ```
  Parse the output: if first line is `TASK_FILE:<path>`, use that path.
- If `NOT_FOUND`, try archived:
  ```bash
  ./.aitask-scripts/aitask_query_files.sh archived-task <number>
  ```
  Parse the output: `ARCHIVED_TASK:<path>` means found, `NOT_FOUND` means not found.
- If still not found: display error and fall through to interactive selection (Step 1b).

**Format 2: Child task (e.g., `/aitask-qa 16_2`):**
- Parse as parent=16, child=2
- Try active first:
  ```bash
  ./.aitask-scripts/aitask_query_files.sh child-file <parent> <child>
  ```
- If `NOT_FOUND`, try archived:
  ```bash
  ./.aitask-scripts/aitask_query_files.sh archived-task <parent>_<child>
  ```
- If still not found: display error and fall through to interactive selection (Step 1b).

**Confirm selection:**
- Read the task file and generate a 1-2 sentence summary
- **Profile check:** If `skip_task_confirmation` is `true`:
  - Display: "Profile '<name>': auto-confirming task selection"
  - Skip confirmation and proceed to Step 2

  Otherwise, use `AskUserQuestion`:
  - Question: "Run QA analysis on this task? Summary: <brief summary>"
  - Header: "Confirm task"
  - Options: "Yes, proceed" / "No, select different task"
- If "No": fall through to interactive selection (Step 1b)
- If "Yes": proceed to Step 2

**Determine task context:**
- Set `is_child` based on whether the task ID contains `_` (e.g., `16_2`)
- Set `parent_id` if child task
- Set `is_archived` based on whether the path starts with `aitasks/archived/`
- Set `task_id` from the filename (e.g., `42` or `16_2`)

#### 1b: Interactive Task Selection (no argument or fallback)

List candidate tasks from two sources:

**Source 1 — Recently archived tasks:**
```bash
./.aitask-scripts/aitask_query_files.sh recent-archived 15
```
Parse `RECENT_ARCHIVED:<path>|<completed_at>|<issue_type>|<task_name>` lines.

**Source 2 — Active tasks with status Done or Implementing:**
```bash
./.aitask-scripts/aitask_ls.sh -v -s Done 15
./.aitask-scripts/aitask_ls.sh -v -s Implementing 15
```

Merge both lists (archived first, then active), deduplicate by task number.

**Read each task file** and generate brief summaries.

**Paginated selection** (same pattern as aitask-pick Step 2c):
- `page_size = 3` (3 tasks per page + 1 "Show more" slot)
- For each task: label = filename, description = `[<status/completed_at>] <brief summary>`
- If more tasks available: add "Show more tasks" option
- Last page: show up to 4 tasks

**Determine task context** (same as Step 1a).

Proceed to Step 2.

### Step 2: Change Analysis

#### 2a: Gather task context

- Read the target task file
- Find the plan file:
  - If active: `aitask_query_files.sh plan-file <task_id>`
  - If archived: also check `aiplans/archived/` — for parent tasks: `aiplans/archived/p<N>_*.md`, for child tasks: `aiplans/archived/p<parent>/p<parent>_<child>_*.md`
- Read the plan file if found (contains implementation details and final notes)

#### 2b: Detect commits

Use the commit detection pattern from `aitask_issue_update.sh`:

```bash
git log --oneline --all --grep="(t<task_id>)" 2>/dev/null || true
```

**Note:** The parentheses in `(t<task_id>)` act as delimiters — `(t88)` won't match `(t88_1)`.

If commits found:
- Extract the first (oldest) and last (newest) commit hashes
- Get changed files:
  ```bash
  git diff <first_commit>^..<last_commit> --name-only 2>/dev/null || true
  ```
- Get diff stats:
  ```bash
  git diff <first_commit>^..<last_commit> --stat 2>/dev/null || true
  ```

If no commits found (task not yet implemented or commits not tagged):
- Analyze the plan file for expected changes
- Display: "No commits found for t<task_id>. Using plan file for analysis."

#### 2c: Categorize changes

Sort changed files into categories:
- **Source code:** `.sh`, `.py`, `.js`, `.ts`, `.go`, `.rs`, `.toml`, `.yaml` (excluding test files)
- **Test files:** Files matching `test_*`, `*_test.*`, `tests/`, `__tests__/`, `*_spec.*`
- **Config/docs:** `.md`, `.json` (config), `.yml` (CI), `Makefile`, etc.

Display a summary table of changes by category.

### Step 3: Test Discovery

#### 3a: Scan for existing tests

For each changed source file, look for corresponding test files using common naming conventions:
- `tests/test_<name>.sh` (bash test pattern used in this project)
- `tests/<name>_test.py`, `test_<name>.py`
- `__tests__/<name>.test.ts`, `<name>.spec.ts`

#### 3b: Map source to tests

Create a mapping of source files to their test files (if any exist).

#### 3c: Identify gaps

List source files that have changes but no corresponding test files. These are the primary candidates for new tests.

Display the test coverage map:
```
Source File                          Test File              Status
.aitask-scripts/aitask_foo.sh       tests/test_foo.sh      Covered
.aitask-scripts/aitask_bar.sh       (none)                 GAP
```

### Step 4: Test Execution

**Profile check:** If `qa_run_tests` is `false`:
- Display: "Profile '<name>': skipping test execution"
- Skip to Step 5

#### 4a: Discover test commands

Read `aitasks/metadata/project_config.yaml` for:
- `test_command` — primary test runner
- `lint_command` — linter command

If neither configured, auto-detect from project structure:
- Look for `tests/test_*.sh` files (this project's pattern)
- Check for `pytest.ini`, `package.json` test scripts, `Makefile` test targets

#### 4b: Run tests

- If `test_command` configured: run it
- If individual test files found matching changed source: run those specifically
- If `lint_command` configured: run it against changed files

Collect pass/fail results.

#### 4c: Present results

Display test results summary:
```
Test Results:
  tests/test_foo.sh ........... PASS
  tests/test_bar.sh ........... FAIL (exit code 1)
  shellcheck aitask_baz.sh .... PASS
```

### Step 5: Test Plan Proposal

#### 5a: Generate test proposals

Based on change analysis (Step 2) and gap detection (Step 3), propose categorized test ideas:

- **Unit tests:** Individual function behavior, edge cases, error paths
- **Integration tests:** Cross-script interactions, end-to-end command flows
- **Edge cases:** Error handling, boundary conditions, platform compatibility (macOS/Linux)

Each proposal should include:
- What to test (specific function/behavior)
- Why (what risk it mitigates)
- How (test approach, framework to use)

#### 5b: Determine action

**Profile check:** If `qa_mode` is set, use that action directly:
- `"ask"` → show AskUserQuestion below
- `"create_task"` → proceed to Step 6 (create follow-up task)
- `"implement"` → enter implementation mode (implement tests in current session)
- `"plan_only"` → export test plan to a file and end

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

### Step 6: Follow-up Task Creation

Compose a detailed task description including:
- Reference to the target task by ID and name
- Change summary from Step 2 (files modified, diff stats)
- Test coverage map from Step 3
- Specific test proposals from Step 5
- Existing test patterns to follow (discovered in Step 3a)

**Create the task:**

If `is_child` is true (create as sibling of the target task's parent):
```bash
./.aitask-scripts/aitask_create.sh --batch --commit \
  --parent <parent_id> \
  --no-sibling-dep \
  --name "test_<short_description>" \
  --type test \
  --priority medium \
  --effort medium \
  --labels "testing,qa" \
  --desc-file - <<'TASK_DESC'
<composed description>
TASK_DESC
```

If `is_child` is false (create as standalone task):
```bash
./.aitask-scripts/aitask_create.sh --batch --commit \
  --name "test_t<task_id>_<short_description>" \
  --type test \
  --priority medium \
  --effort medium \
  --labels "testing,qa" \
  --desc-file - <<'TASK_DESC'
<composed description>
TASK_DESC
```

Display: "Created testing follow-up task: <filename>"

Proceed to Step 7.

### Step 7: Satisfaction Feedback

Execute the **Satisfaction Feedback Procedure** (see `.claude/skills/task-workflow/satisfaction-feedback.md`) with `skill_name: "qa"`.

---

## Notes

- This skill works with both active and archived tasks
- For archived tasks, plan files in `aiplans/archived/` contain the richest implementation context
- The commit detection pattern `(t<N>)` uses parentheses as delimiters to avoid partial matches
- Profile keys `qa_mode` and `qa_run_tests` control automation level
- When no commits are found, the skill falls back to plan-file analysis
- This skill does NOT modify task status or claim ownership — it is read-only analysis
- The skill replaces the tightly-coupled test-followup-task procedure (Step 8b) for standalone use; the embedded procedure remains available in task-workflow for inline use
