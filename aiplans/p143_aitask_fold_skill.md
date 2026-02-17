# Plan: Implement aitask-fold skill (t143)

## Context

The aitasks project already has a "folding" mechanism in `/aitask-explore` where pending tasks with overlapping scope can be folded into a newly created task. However, there's no standalone skill to fold existing tasks without going through the explore workflow. The `/aitask-fold` skill fills this gap — it identifies related tasks and merges them into a single task, either interactively or via explicit task IDs.

The `docs/skills.md` file (line 153) already references `/aitask-fold` but the skill doesn't exist yet.

## Task Decomposition

Split into 2 child tasks:

### Child 1: t143_1 — Create aitask-fold SKILL.md
Create `.claude/skills/aitask-fold/SKILL.md` with the full skill workflow.

### Child 2: t143_2 — Update docs/skills.md
Add `/aitask-fold` to TOC, overview table, and full documentation section in `docs/skills.md`.

## SKILL.md Design

### Frontmatter
```yaml
---
name: aitask-fold
description: Identify and merge related tasks into a single task, then optionally execute it.
---
```

### Workflow Steps

**Step 0a: Select Execution Profile** — Same pattern as aitask-pick/aitask-explore (read profiles from `aitasks/metadata/profiles/*.yaml`).

**Step 0b: Check for Explicit Task IDs (Optional Argument)** — If invoked with arguments (e.g., `/aitask-fold 106,108,112` or `/aitask-fold 106 108 112`):
- Parse comma-separated or space-separated task IDs
- For each ID: find the task file via `ls aitasks/t<id>_*.md`, read it, validate it's eligible (Ready/Editing, no children, standalone parent)
- If any task is invalid, show warning with reason (e.g., "t108: status is Implementing — skipping", "t112: has children — skipping", "t115: file not found — skipping") and exclude from the set
- If fewer than 2 valid tasks remain after filtering, inform user and abort
- Otherwise, skip to Step 2 (Primary Selection) with the valid tasks

**Step 0c: Sync with Remote** — Same `git pull --ff-only` and lock cleanup pattern.

**Step 1: Interactive Task Discovery** (only if no arguments provided)
- List all eligible pending tasks:
  ```bash
  ./aiscripts/aitask_ls.sh -v --status all --all-levels 99 2>/dev/null
  ```
- Filter to Ready/Editing, no children, standalone parent-level
- If fewer than 2 eligible tasks, inform user and abort
- Read title + first ~5 lines of each task body
- **Identify related groups** by shared labels and semantic similarity (AI assessment)
- Present suggested groups using AskUserQuestion with multiSelect:
  - Question: "Select tasks to fold together into a single task (minimum 2):"
  - Header: "Fold tasks"
  - Options: Each eligible task with filename label and brief description
- If user selects fewer than 2 tasks, inform and abort

**Step 2: Primary Task Selection**
- Present selected tasks and ask which should be the "primary" (the one that survives):
  - AskUserQuestion: "Which task should be the primary (other tasks' content will be merged into it)?"
  - Header: "Primary"
  - Options: Each selected task with filename and brief summary (paginate if >4)

**Step 3: Merge Content**
- Read the full content (description body) of each non-primary task
- Read the primary task's current description
- Build updated description:
  - Keep original primary description
  - Append merged content from each non-primary task under `## Merged from t<N>: <task_name>` headers
  - Append `## Folded Tasks` reference section (same format as aitask-explore)
- Update the primary task's description:
  ```bash
  ./aiscripts/aitask_update.sh --batch <primary_num> --desc-file - <<'TASK_DESC'
  <merged description>
  TASK_DESC
  ```
- Set `folded_tasks` frontmatter on the primary task:
  ```bash
  ./aiscripts/aitask_update.sh --batch <primary_num> --folded-tasks "<comma-separated non-primary IDs>"
  ```
- Commit:
  ```bash
  git add aitasks/
  git commit -m "Fold tasks into t<primary_id>: merge t<id1>, t<id2>, ..."
  ```

**Step 4: Decision Point**
- Profile check: if `explore_auto_continue` is `true`, auto-continue
- Otherwise, AskUserQuestion: "Tasks folded successfully. How would you like to proceed?"
  - "Continue to implementation" → hand off to task-workflow
  - "Save for later" → inform user, end workflow

**Step 5: Hand Off to Shared Workflow**
- Set context variables (task_file, task_id, task_name, is_child=false, parent_id=null, parent_task_file=null, active_profile, previous_status=Ready, folded_tasks=list of non-primary IDs)
- Read and follow `.claude/skills/task-workflow/SKILL.md` from Step 3

### Edge Cases
- **Only 1 task selected**: Abort with message "Need at least 2 tasks to fold"
- **Primary task already has folded_tasks**: Merge existing list with new IDs (append, don't replace)
- **Task has `depends` on another selected task**: Warn but allow (dependencies will be irrelevant after fold)
- **Task doesn't exist or ineligible**: Warn and exclude, continue with remaining valid tasks (abort only if <2 remain)

## docs/skills.md Changes

1. Add `/aitask-fold` to Table of Contents (after `/aitask-explore` line)
2. Add row to Skill Overview table: `| /aitask-fold | Identify and merge related tasks into a single task |`
3. Add full section between `/aitask-explore` and `/aitask-create` sections with usage, workflow overview, key capabilities, and profile key reference

## Verification

1. Read the created SKILL.md and verify it follows the same format as aitask-explore/aitask-pick
2. Verify docs/skills.md has correct TOC links and section ordering
3. Check that all bash commands reference existing scripts with correct flags
4. Verify the handoff to task-workflow matches the Context Requirements table

## Step 9 Reference

Post-implementation cleanup is handled by task-workflow Step 9 which already supports:
- Reading `folded_tasks` from the archived task file
- Deleting folded task files via `git rm`
- Releasing locks for folded tasks
- Updating/closing linked issues for folded tasks
