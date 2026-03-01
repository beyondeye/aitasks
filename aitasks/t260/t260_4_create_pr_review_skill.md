---
priority: high
effort: medium
depends: [t260_3]
issue_type: feature
status: Ready
labels: [skills]
created_at: 2026-03-01 15:31
updated_at: 2026-03-01 15:31
---

## Context

This is child task 4 of the "Create aitasks from Pull Requests" feature (t260). This task creates a new Claude Code skill (`/aitask-pr-review`) that reads intermediate PR data extracted by `aitask_pr_import.sh` (t260_3), analyzes the PR with AI assistance, and creates a properly structured aitask + implementation plan.

**Why this task is needed:** The bash script (t260_3) extracts raw data from PRs, but the actual analysis — understanding the purpose, evaluating the approach, identifying concerns, and creating a structured task — requires AI reasoning. This skill bridges raw PR data to actionable tasks.

**Depends on:** t260_3 (needs the intermediate data format and the `--data-only` flag on `aitask_pr_import.sh`)

**Flow similarity:** This skill follows the same pattern as `aitask-explore` — iterative analysis with user interaction, task creation, optional hand-off to implementation.

## Key Files to Create

1. **Create `.claude/skills/aitask-pr-review/SKILL.md`** — New skill definition

## Reference Files for Patterns

- **`.claude/skills/aitask-explore/SKILL.md`** — PRIMARY REFERENCE. This skill demonstrates:
  - Step 0a: Profile selection via `aitask_scan_profiles.sh`
  - Step 0c: Remote sync via `aitask_pick_own.sh --sync`
  - Step 1: Exploration setup with AskUserQuestion
  - Step 2: Iterative exploration loop with "Continue/Create task/Abort" options
  - Step 2b: Related task discovery and folding
  - Step 3: Task creation via `aitask_create.sh --batch --commit`
  - Step 4: Decision point (continue to implementation vs save for later)
  - Step 5: Hand-off to `task-workflow/SKILL.md` Step 3

- **`.claude/skills/task-workflow/SKILL.md`** — Shared workflow that handles Steps 3-9 (status checks, assignment, environment, planning, implementation, review, archival)

- **`.claude/skills/task-workflow/planning.md`** — Planning workflow details

## Implementation Plan

### Skill YAML Header
```yaml
---
name: aitask-pr-review
description: Create an aitask from a pull request by analyzing PR data and generating a structured task with implementation plan.
user-invocable: true
---
```

### Step 0a: Profile Selection
Identical to `aitask-explore` Step 0a:
- Run `./aiscripts/aitask_scan_profiles.sh`
- Parse output, handle NO_PROFILES / single / multiple profiles
- Load selected profile

### Step 0c: Sync with Remote
Identical: `./aiscripts/aitask_pick_own.sh --sync`

### Step 1: PR Selection

Use `AskUserQuestion`:
- Question: "How would you like to select the pull request to review?"
- Header: "PR Source"
- Options:
  - "Enter PR number" (description: "Specify a PR/MR number to import and analyze")
  - "Browse open PRs" (description: "List all open PRs and choose one")
  - "Use existing PR data" (description: "Select from previously imported PR data in .aitask-pr-data/")

**If "Enter PR number":**
- Ask for the number via AskUserQuestion
- Run: `./aiscripts/aitask_pr_import.sh --batch --pr <num> --data-only`
- Read the generated intermediate file from `.aitask-pr-data/<num>.md`

**If "Browse open PRs":**
- Run: `./aiscripts/aitask_pr_import.sh --batch --list` (needs a --list flag that just outputs PR listing)
- Parse output and present via AskUserQuestion (paginated, 3 per page)
- After selection, run `--data-only` import for chosen PR

**If "Use existing PR data":**
- Glob `.aitask-pr-data/*.md` files
- Present available files via AskUserQuestion
- Read the selected file

### Step 2: PR Analysis

Read the intermediate data file. Present structured summary to user:

```
## PR Summary
- **Title:** <title>
- **Author:** <contributor> (<contributor_email>)
- **State:** <state>
- **Branch:** <head_branch> → <base_branch>
- **Changes:** +<additions> -<deletions> across <changed_files> files
- **URL:** <pr_url>

## Description
<PR description, first 500 chars>

## Key Changes
<List of changed files with brief description of what changed>
```

Then perform AI analysis:
- **Purpose/Intent:** What is this PR trying to achieve?
- **Proposed Solution:** What approach does the PR take?
- **Quality Assessment:** Code quality, test coverage, edge cases
- **Concerns:** Potential issues, missing tests, breaking changes
- **Codebase Alignment:** Does the approach match existing patterns/conventions?

Present analysis to user.

### Step 3: Interactive Q&A Loop

Same pattern as explore's Step 2:
- User can ask questions about the PR
- AI can explore the codebase to compare PR approach with existing code
- Can dive deeper into specific files or review comments

Use `AskUserQuestion`:
- Question: "How would you like to proceed?"
- Options:
  - "Continue analyzing" (description: "Ask more questions or explore specific aspects")
  - "Create task from this PR" (description: "Generate an aitask based on the analysis")
  - "Abort" (description: "Stop without creating a task")

### Step 4: Related Task Discovery

Same as explore's Step 2b:
- List pending tasks: `./aiscripts/aitask_ls.sh -v --status all --all-levels 99`
- Filter to Ready/Editing, exclude tasks with children
- Present related tasks for potential folding

### Step 5: Task Creation

Create the task description incorporating:
- PR context (title, author, URL)
- AI analysis summary (purpose, approach, concerns)
- Recommended implementation approach (may differ from PR's approach)
- Files to modify
- Testing requirements
- Reference to original PR for context

```bash
./aiscripts/aitask_create.sh --batch --commit \
    --name "<sanitized_pr_title>" \
    --desc-file - \
    --priority "<priority>" \
    --effort "<effort>" \
    --type "<issue_type>" \
    --labels "<labels>" \
    --pull-request "<pr_url>" \
    --contributor "<username>" \
    --contributor-email "<email>"
```

If folded tasks exist, update them same as explore skill.

### Step 6: Decision Point

Profile check for `explore_auto_continue`:
- If true: proceed to Step 7
- Otherwise, AskUserQuestion:
  - "Task created. How would you like to proceed?"
  - Options:
    - "Save for later" (description: "End here, pick up with /aitask-pick <N> later") — DEFAULT (first option)
    - "Continue to implementation" (description: "Proceed to plan and implement now")

**Note:** Default is "Save for later" (unlike explore which defaults to continue). This is intentional — PR-originated tasks typically need more review before implementation.

### Step 7: Hand-off to task-workflow

Set context variables and hand off to `.claude/skills/task-workflow/SKILL.md` Step 3:
- `task_file`, `task_id`, `task_name`
- `is_child: false` (PR review creates standalone parent tasks)
- `parent_id: null`, `parent_task_file: null`
- `active_profile` (from Step 0a)
- `previous_status: Ready`
- `folded_tasks: [...]` (if any)

### Settings Registration

Add to `.claude/settings.local.json` (if skill registration is needed).

## Verification Steps

1. **End-to-end test with a real PR:**
   - Ensure a PR exists in the repo (or use a public repo's PR)
   - Run `/aitask-pr-review` in Claude Code
   - Verify profile selection works
   - Verify PR data is fetched and displayed
   - Verify AI analysis is meaningful
   - Verify task creation with `pull_request:` and `contributor:` metadata
   - Verify task file contains proper description

2. **Test "Use existing PR data" path:**
   - First run `./ait pr-import --batch --pr <num> --data-only`
   - Then run `/aitask-pr-review` and select "Use existing PR data"

3. **Test abort flow:**
   - Start the skill, analyze a PR, then select "Abort"
   - Verify no task is created
