---
priority: high
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [testing, qa]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-22 11:21
updated_at: 2026-03-22 11:39
---

## Context

Create the core `aitask-qa` skill as a standalone Claude Code skill for test/QA analysis. This replaces the tightly-coupled `test-followup-task.md` procedure currently embedded in task-workflow Step 8b. The new skill can be invoked independently on any task (active, archived, or recently completed) via `/aitask-qa [task_id]`.

## Key Files to Create/Modify

- **Create: `.claude/skills/aitask-qa/SKILL.md`** — The main skill definition
- **Modify: `.aitask-scripts/aitask_query_files.sh`** — Add `recent-archived [limit]` subcommand for listing recently archived tasks sorted by `completed_at`
- **Modify: `.claude/settings.local.json`** — Register skill trigger
- **Modify: `aitasks/metadata/profiles/profiles.md`** — Document new profile keys (`qa_mode`, `qa_run_tests`)

## Skill Workflow Design

### Step 0: Profile Selection
Execute the standard Execution Profile Selection Procedure (see `.claude/skills/task-workflow/execution-profile-selection.md`).

### Step 1: Task Selection
- Accept optional argument: task ID (e.g., `/aitask-qa 42` or `/aitask-qa 16_2`)
- If argument provided:
  - Try active first: `aitask_query_files.sh resolve <N>`
  - If NOT_FOUND, try archived: `aitask_query_files.sh archived-task <N>`
  - Confirm selection (respect `skip_task_confirmation` profile key)
- If no argument:
  - List recently archived tasks: `aitask_query_files.sh recent-archived 15`
  - Also include active tasks with status `Done` or `Implementing` via `aitask_ls.sh -s all`
  - Use paginated AskUserQuestion selection (same pattern as aitask-pick Step 2c)

### Step 2: Change Analysis
- Read the target task file + plan file (active or archived via `aitask_query_files.sh plan-file`)
- For archived tasks, also check `aiplans/archived/` for the plan file
- Detect commits: `git log --oneline --all --grep="(t<task_id>)"`
- If commits found: `git diff <first_commit>^..<last_commit> --stat` + `--name-only` for changed files
- If no commits (not yet implemented): analyze the plan file for expected changes
- Categorize changes: source code files vs. test files vs. config/docs

### Step 3: Test Discovery
- Scan for existing test files matching changed source patterns
- Map changed source files to existing test files using naming conventions
- Identify test gaps: source files with changes but no corresponding tests

### Step 4: Test Execution (if applicable)
- Read `aitasks/metadata/project_config.yaml` for `test_command` and `lint_command` keys
- If `test_command` configured: run it (or filter to relevant tests if command supports it)
- If `lint_command` configured: run it against changed files
- If neither configured: auto-detect from project structure (look for `tests/`, `pytest.ini`, `package.json` scripts, `Makefile` test targets, etc.) and suggest running discovered tests
- Collect pass/fail results
- Present results summary
- **Profile check:** If `qa_run_tests` is `false`, skip this step

### Step 5: Test Plan Proposal
- Based on change analysis and gap detection, propose categorized test ideas:
  - **Unit tests**: Individual function behavior
  - **Integration tests**: Cross-script interactions
  - **Edge cases**: Error handling, boundary conditions, platform compatibility
- **Profile check:** If `qa_mode` is set, use that action directly:
  - `"ask"` → show AskUserQuestion
  - `"create_task"` → create follow-up task
  - `"implement"` → enter implementation mode
  - `"plan_only"` → export test plan only
- Otherwise, use AskUserQuestion: "How would you like to proceed?"
  - "Create follow-up test task" → create task via `aitask_create.sh --batch`
  - "Implement tests now" → enter implementation mode
  - "Export test plan only" → save plan to file
  - "Skip" → end

### Step 6: Follow-up Task Creation (if selected)
- Compose detailed task description with: target task reference, change summary, specific test proposals, existing test patterns to follow
- Create via `aitask_create.sh --batch --commit`
- If target was a child task: create as sibling with `--parent`

### Step 7: Satisfaction Feedback
- Execute the standard Satisfaction Feedback Procedure (see `.claude/skills/task-workflow/satisfaction-feedback.md`)

## Reference Files for Patterns

- `.claude/skills/aitask-pick/SKILL.md` — Task selection pattern, profile integration, paginated AskUserQuestion
- `.claude/skills/task-workflow/test-followup-task.md` — Original procedure being replaced (reference for task creation logic)
- `.claude/skills/task-workflow/execution-profile-selection.md` — Profile selection procedure
- `.claude/skills/task-workflow/satisfaction-feedback.md` — Feedback procedure
- `.aitask-scripts/aitask_query_files.sh` — Script to extend with `recent-archived` subcommand
- `.aitask-scripts/aitask_issue_update.sh` lines 243-274 — Commit detection pattern to reuse
- `.claude/skills/aitask-review/SKILL.md` — Example of a standalone skill with argument handling

## New Script Subcommand: `recent-archived`

Add to `.aitask-scripts/aitask_query_files.sh`:
- Subcommand: `recent-archived [limit]` (default limit: 15)
- Scans `aitasks/archived/t*.md` files (parent tasks only, not children in subdirs)
- Reads `completed_at` from YAML frontmatter via existing `read_yaml_field()` from `task_utils.sh`
- Sorts by `completed_at` descending, returns top N results
- Output format: `RECENT_ARCHIVED:<path>|<completed_at>|<issue_type>|<task_name>`
- Falls back to file modification time if `completed_at` is missing
- Also check `aitasks/archived/t*/t*_*.md` for recently archived child tasks
- Output: `NO_RECENT_ARCHIVED` if no files found

## Verification Steps

1. Create the skill file and verify it loads: check `/aitask-qa` appears in skill list
2. Test `recent-archived` subcommand: `./aitask-scripts/aitask_query_files.sh recent-archived 5`
3. Test with a known archived task ID: `/aitask-qa <known_id>`
4. Test interactive mode (no argument): `/aitask-qa`
5. Verify profile keys are documented in profiles.md
