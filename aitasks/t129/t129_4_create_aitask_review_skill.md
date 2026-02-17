---
priority: medium
effort: high
depends: [t129_3]
issue_type: feature
status: Implementing
labels: [claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-15 17:15
updated_at: 2026-02-17 14:38
---

## Context
This task creates the `/aitask-review` Claude Code skill — a Claude-driven code review workflow that uses configurable review modes (from t129_3) to perform targeted reviews, present findings, and create tasks from selected issues.

This is part of the dynamic task skill initiative (t129). The review modes infrastructure (t129_3) must be complete before this task. The shared workflow (task-workflow skill from t129_1) handles the implementation pipeline after task creation.

## Key Files to Create

1. **Create** `.claude/skills/aitask-review/SKILL.md`
   - User-invocable skill with proper YAML frontmatter
   - Contains code review workflow steps

## Reference Files for Patterns

- `.claude/skills/aitask-pick/SKILL.md` — pattern for profile loading, AskUserQuestion, pagination
- `.claude/skills/aitask-explore/SKILL.md` — pattern for the sister skill (explore), similar structure
- `.claude/skills/task-workflow/SKILL.md` — the shared workflow to hand off to after task creation
- `aitasks/metadata/reviewmodes/*.md` — review mode files to load and present to user
- `aitasks/metadata/profiles/*.yaml` — execution profile format
- `aiscripts/aitask_create.sh` — use `--batch --commit` to create tasks

## Implementation Plan

### Step 1: Create the skill SKILL.md with YAML frontmatter

### Step 2: Implement the workflow steps

**Step 0a: Select Execution Profile** — same as aitask-pick/aitask-explore.

**Step 0c: Sync with Remote** — same pattern.

**Step 1: Review Setup**

1a. Ask user for target paths/modules via AskUserQuestion with free text:
- "What code areas should be reviewed?" with options like:
  - "Specific paths" (enter paths via "Other")
  - "Entire codebase" (review everything)

1b. Load review modes from `aitasks/metadata/reviewmodes/`:
- List all .md files in the directory
- Read each file's YAML frontmatter (name, description, environment)
- Auto-detect project environment by checking for:
  - pyproject.toml/setup.py → python
  - build.gradle/build.gradle.kts → android/kotlin
  - CMakeLists.txt → cpp/cmake
  - package.json → javascript/typescript
  - *.sh scripts in project → bash/shell
- Sort modes: environment-matching first, then universal, then non-matching
- Present via AskUserQuestion multiSelect: "Select review modes to apply:"
  - Each option: label = name from frontmatter, description = description from frontmatter
- Profile check: if `review_default_modes` set, pre-select those modes

1c. Read the full content of each selected review mode file — these become the review instructions.

**Step 2: Automated Review**
- For each selected review mode:
  - Read its review instructions (the markdown body after frontmatter)
  - Systematically explore the specified target paths following the instructions
  - Record findings with: review mode name, severity (high/medium/low), location (file:line), description, suggested fix
- Use Glob, Grep, Read tools and Explore agents for thorough review

**Step 3: Findings Presentation**
- Present findings grouped by review mode and severity
- Format: markdown table or bulleted list with file:line references
- Use AskUserQuestion multiSelect: "Select findings to address:"
- If no findings found: inform user and end workflow

**Step 4: Task Creation**
- AskUserQuestion: "How should the selected findings become tasks?"
  - "Single task with all findings" → create one task with all findings in description
  - "Separate task per finding" → create multiple standalone tasks
  - "Group by review mode" → create one task per review mode that had findings
- For single task: use aitask_create.sh --batch --commit
- For multiple tasks: create a parent task first, then children:
  - Parent: "Code review: <target area>"
  - Children: one per finding or per mode, using --parent flag
- Profile check: if `review_auto_continue: true`, skip decision point

**Step 5: Decision Point**
- If single task: "Continue to implementation" or "Save for later"
- If multiple tasks: "Pick one to start" (select from children) or "Save all for later"
- When continuing: set context variables and read `.claude/skills/task-workflow/SKILL.md`

## Verification Steps

1. Read the created SKILL.md and verify it follows the aitask-pick pattern
2. Verify review mode loading reads from correct directory
3. Verify environment auto-detection logic covers common project types
4. Verify task creation uses correct aitask_create.sh flags
5. Verify handoff to task-workflow uses correct context variables
6. Manual testing: install review modes, run /aitask-review on a known codebase area
