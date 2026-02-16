---
priority: medium
effort: high
depends: [t129_1]
issue_type: feature
status: Implementing
labels: [claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-15 17:15
updated_at: 2026-02-16 11:47
---

## Context
This task creates the `/aitask-explore` skill — a user-driven exploration workflow for cases where the developer doesn't have a specific task in mind. Instead of defining a task first then running `/aitask-pick`, the user starts by exploring the codebase with Claude's help, and when ready, crystallizes findings into a task that can optionally proceed to implementation.

This is part of the dynamic task skill initiative (t129). The shared workflow (task-workflow skill from t129_1) handles the implementation pipeline after task creation.

## Key Files to Create

1. **Create** `.claude/skills/aitask-explore/SKILL.md`
   - User-invocable skill with proper YAML frontmatter
   - Contains exploration workflow steps

## Reference Files for Patterns

- `.claude/skills/aitask-pick/SKILL.md` — pattern for profile loading (Step 0a), remote sync (Step 0c), and AskUserQuestion usage
- `.claude/skills/task-workflow/SKILL.md` — the shared workflow to hand off to after task creation
- `aiscripts/aitask_create.sh` — use `--batch --commit` to create tasks programmatically
- `aitasks/metadata/profiles/*.yaml` — execution profile format (reuse existing keys)
- `aitasks/metadata/labels.txt` — available labels for task creation

## Implementation Plan

### Step 1: Create the skill SKILL.md with YAML frontmatter

### Step 2: Implement the workflow steps

**Step 0a: Select Execution Profile** — same pattern as aitask-pick: check for profiles in `aitasks/metadata/profiles/*.yaml`, auto-load if one, ask if multiple. Reuse existing profile keys plus new optional key `explore_auto_continue`.

**Step 0c: Sync with Remote** — same as aitask-pick: `git pull --ff-only --quiet 2>/dev/null || true` and lock cleanup.

**Step 1: Exploration Setup**
- Use AskUserQuestion to ask: "What would you like to explore?"
- Options for exploration type:
  - "Investigate a problem" (e.g., "why is X slow?", "where does Y break?")
  - "Explore codebase area" (e.g., "understand the auth module")
  - "General exploration" (e.g., "look for improvement opportunities")
- User can also provide free text via "Other" option

**Step 2: Iterative Exploration**
- Claude explores the codebase based on user's focus area
- Uses Read, Glob, Grep, and Task (Explore agents) to investigate
- After each exploration round, use AskUserQuestion:
  - "Continue exploring" — keep going, user may redirect focus
  - "I have enough, create a task" — proceed to task creation
  - "Abort exploration" — stop without creating a task
- Take notes on findings throughout (mental tracking, not written to file)

**Step 3: Task Creation**
- Summarize exploration findings for the user
- Propose task metadata: title, priority, effort, labels, description
- Ask user to confirm or modify via AskUserQuestion
- Create task using: `./aiscripts/aitask_create.sh --batch --commit --name "<name>" --desc-file - --priority <p> --effort <e> --labels <l>`
- Read back the created task file to get the assigned task ID

**Step 4: Decision Point**
- Profile check: if `explore_auto_continue: true`, skip to implementation
- Otherwise, AskUserQuestion: "Task created: t<N>_<name>.md. How would you like to proceed?"
  - "Continue to implementation" → set context variables, read and follow `.claude/skills/task-workflow/SKILL.md`
  - "Save for later" → inform user the task is ready for `/aitask-pick <N>`

### Step 3: Integration with shared workflow
When continuing to implementation, set these context variables:
- task_file: path to the created task file
- task_id: the assigned task number
- task_name: extracted from filename
- is_child: false (explore creates standalone tasks)
- parent_id: N/A
- active_profile: the loaded profile from Step 0a
- previous_status: Ready

## Verification Steps

1. Read the created SKILL.md and verify it follows the aitask-pick pattern for profile loading and AskUserQuestion usage
2. Verify the handoff to task-workflow uses the correct context variables
3. Verify the aitask_create.sh invocation has all required flags
4. Manual testing: run `/aitask-explore`, go through exploration, create a task, verify it appears in `aitasks/`
