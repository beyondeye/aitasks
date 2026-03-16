---
Task: t398_2_revert_skill.md
Parent Task: aitasks/t398_aitask_revert.md
Sibling Tasks: aitasks/t398/t398_1_revert_analyze_script.md, aitasks/t398/t398_3_post_revert_integration.md, aitasks/t398/t398_4_website_documentation.md
Archived Sibling Plans: aiplans/archived/p398/p398_1_revert_analyze_script.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t398_2 — Skill Definition (`aitask-revert/SKILL.md`)

## Overview

Create `.claude/skills/aitask-revert/SKILL.md` — the complete interactive revert workflow. The skill is user-invocable as `/aitask-revert` or `/aitask-revert <task_id>`.

## Steps

### Step 1: Create skill directory and file

Create `.claude/skills/aitask-revert/SKILL.md` with frontmatter:
```yaml
---
name: aitask-revert
description: Revert changes associated with completed tasks — fully or partially
user-invocable: true
---
```

### Step 2: Write Step 0 — Profile Selection

Same pattern as `aitask-explore/SKILL.md` Step 0a:
- Scan profiles with `aitask_scan_profiles.sh`
- Auto-load single profile or ask user to select
- Store profile for use throughout

### Step 3: Write Step 1 — Task Discovery

Three paths via AskUserQuestion:
1. **Direct argument** (`/aitask-revert 42`): Parse, validate task exists (check active + archived using `resolve_task_file` pattern or `aitask_query_files.sh`), skip to Step 2
2. **"Browse recent tasks"**: Call `aitask_revert_analyze.sh --recent-tasks --limit 20`, present with AskUserQuestion pagination (3 per page + "Show more", same as aitask-pick Step 2c)
3. **"Search by files"**: Invoke `user-file-select` skill, then use `aitask_explain_extract_raw_data.sh --gather <files>` to produce reference.yaml, parse task IDs from it, present discovered tasks

### Step 4: Write Step 2 — Task Analysis & Confirmation

- Read the task file (may be archived)
- Run `aitask_revert_analyze.sh --task-commits <id>` to list commits
- Run `aitask_revert_analyze.sh --task-areas <id>` to show area breakdown
- For parent tasks with children: show per-child commit breakdown
- Display formatted summary
- AskUserQuestion: "Confirm this is the task to revert" / "Select different task" / "Cancel"

### Step 5: Write Step 3 — Revert Type Selection

AskUserQuestion:
- "Complete revert" (all changes)
- "Partial revert" (select areas)

### Step 6: Write Step 3a — Complete Revert Path

Ask disposition with AskUserQuestion:
- "Delete task and plan" — remove entirely
- "Keep archived" — add revert notes to archived file
- "Move back to Ready" — un-archive and reset status

Store disposition choice for Step 4.

### Step 7: Write Step 3b — Partial Revert Path

- Present areas from `--task-areas` output
- AskUserQuestion with `multiSelect: true` — select areas to REVERT (unselected = keep)
- Also offer "Other" for free text granular specification
- Show confirmation summary: "Will revert: X, Y. Will keep: Z, W."
- AskUserQuestion: "Confirm" / "Adjust selection" / "Cancel"
- If "Adjust": loop back to area selection

### Step 8: Write Step 4 — Create Revert Task

Build detailed task description with:
- Reference to original task ID
- Summary of original task
- For complete: all commits listed, disposition instructions
- For partial: areas to revert with files/commits, areas to keep, disposition instructions
- Post-revert task management instructions specific to chosen disposition

Create via: `aitask_create.sh --batch --name "revert_t<id>" --type refactor --desc-file -`

### Step 9: Write Step 5 — Decision Point

AskUserQuestion (same as aitask-explore):
- "Continue to implementation" → handoff
- "Save for later" → display task file location, end

### Step 10: Write Step 6 — Handoff

Set context variables and follow task-workflow SKILL.md from Step 3:
- `task_file`, `task_id`, `task_name`, `is_child: false`, `active_profile`, `previous_status: Ready`, `skill_name: "revert"`

### Step 11: Register skill

Add `aitask-revert` to `.claude/settings.local.json` if needed for tool permissions.

## Step 9 Reference
After implementation, follow task-workflow Step 9 for archival.
