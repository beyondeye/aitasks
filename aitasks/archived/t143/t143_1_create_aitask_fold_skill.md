---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [claudeskills, aitask_fold]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-17 10:02
updated_at: 2026-02-17 10:35
completed_at: 2026-02-17 10:35
---

## Context

This is child task 1 of t143 (aitask fold skill). The parent task requests creating a new `/aitask-fold` Claude Code skill that identifies connected tasks and allows folding them into a single task, either interactively or via explicit task IDs.

The aitasks project already has a "folding" mechanism in `/aitask-explore` (Step 2b and Step 3) where pending tasks with overlapping scope can be folded into a newly created task. The `/aitask-fold` skill provides the same capability as a standalone workflow.

## Key Files to Modify

- **Create: `.claude/skills/aitask-fold/SKILL.md`** — The complete skill definition (new directory + file)

## Reference Files for Patterns

- **`.claude/skills/aitask-explore/SKILL.md`** — Primary pattern reference. Step 2b (lines 133-162) shows related task discovery. Step 3 (lines 163-222) shows content merging and `folded_tasks` frontmatter setting. Step 5 (lines 247-258) shows handoff to task-workflow.
- **`.claude/skills/aitask-pick/SKILL.md`** — Pattern for profile selection (Step 0a), direct task selection with argument (Step 0b), remote sync (Step 0c), and handoff to task-workflow.
- **`.claude/skills/task-workflow/SKILL.md`** — Handoff target. Context Requirements table (lines 7-22) defines required variables. Step 9 (lines 523-549) handles folded task deletion on archival.
- **`aiscripts/aitask_update.sh`** — Used for `--folded-tasks` and `--desc-file` updates.
- **`aiscripts/aitask_ls.sh`** — Used for listing eligible tasks (`-v --status all --all-levels 99`).

## Implementation Plan

### SKILL.md Structure

```yaml
---
name: aitask-fold
description: Identify and merge related tasks into a single task, then optionally execute it.
---
```

### Workflow Steps to Implement

**Step 0a: Select Execution Profile** — Same pattern as aitask-pick/aitask-explore (read profiles from `aitasks/metadata/profiles/*.yaml`). Copy the exact step from aitask-pick.

**Step 0b: Check for Explicit Task IDs (Optional Argument)** — If invoked with arguments (e.g., `/aitask-fold 106,108,112` or `/aitask-fold 106 108 112`):
- Parse comma-separated or space-separated task IDs
- For each ID: find the task file via `ls aitasks/t<id>_*.md`, validate eligibility (Ready/Editing, no children, standalone parent)
- If any task is invalid, show warning with reason (e.g., "t108: status is Implementing — skipping") and exclude from set
- If fewer than 2 valid tasks remain, inform user and abort
- Skip to Step 2 with valid tasks

**Step 0c: Sync with Remote** — Same `git pull --ff-only --quiet` and `aitask_lock.sh --cleanup` pattern.

**Step 1: Interactive Task Discovery** (only if no arguments provided)
- List all eligible tasks via `./aiscripts/aitask_ls.sh -v --status all --all-levels 99`
- Filter to Ready/Editing, no children, standalone parent-level only
- If fewer than 2 eligible, abort
- Read title + first ~5 lines of each task body
- Identify related groups by shared labels and semantic content similarity
- Present using AskUserQuestion with multiSelect
- If fewer than 2 selected, abort

**Step 2: Primary Task Selection**
- Present selected tasks, ask which is the "primary" (survives, others merge into it)
- Use AskUserQuestion, paginate if >4 tasks

**Step 3: Merge Content**
- Read full description body of each non-primary task
- Read primary task's current description
- Build updated description: keep primary description, append merged content under `## Merged from t<N>: <task_name>` headers, append `## Folded Tasks` reference section
- Update via `./aiscripts/aitask_update.sh --batch <primary_num> --desc-file -`
- Set folded_tasks via `./aiscripts/aitask_update.sh --batch <primary_num> --folded-tasks "<ids>"`
- If primary already has folded_tasks, merge (append) rather than replace
- Commit: `git add aitasks/ && git commit -m "Fold tasks into t<primary_id>: merge t<id1>, t<id2>, ..."`

**Step 4: Decision Point**
- Profile check: if `explore_auto_continue` is `true`, auto-continue
- Otherwise AskUserQuestion: continue to implementation or save for later

**Step 5: Hand Off to Shared Workflow**
- Set context variables: task_file, task_id, task_name, is_child=false, parent_id=null, parent_task_file=null, active_profile, previous_status=Ready, folded_tasks
- Follow `.claude/skills/task-workflow/SKILL.md` from Step 3

### Edge Cases to Handle
- Only 1 task selected → abort
- Primary already has folded_tasks → append new IDs
- Task has depends on another selected task → warn but allow
- Invalid/ineligible tasks → warn and exclude, continue if >=2 remain

## Verification Steps

1. Read the created SKILL.md and verify YAML frontmatter is correct
2. Verify all bash commands reference existing scripts with correct flags
3. Verify the handoff context variables match task-workflow's Context Requirements table
4. Compare structure with aitask-explore/SKILL.md to ensure consistency
