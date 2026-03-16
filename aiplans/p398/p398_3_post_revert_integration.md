---
Task: t398_3_post_revert_integration.md
Parent Task: aitasks/t398_aitask_revert.md
Sibling Tasks: aitasks/t398/t398_1_revert_analyze_script.md, aitasks/t398/t398_2_revert_skill.md, aitasks/t398/t398_4_website_documentation.md
Archived Sibling Plans: aiplans/archived/p398/p398_1_revert_analyze_script.md, aiplans/archived/p398/p398_2_revert_skill.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t398_3 — Post-Revert Management & Integration

## Overview

Refine the SKILL.md and analysis script with detailed post-revert task management, add `--find-task` helper, update `ait` help text, and validate end-to-end.

## Steps

### Step 1: Add `--find-task <task_id>` to `aitask_revert_analyze.sh`

Add a subcommand that locates task and plan files across all storage locations:
- Active: `aitasks/t<id>*.md`
- Archived: `aitasks/archived/t<id>*.md`
- Deep archive: `aitasks/archived/old.tar.gz`
- Same for plans in `aiplans/`

Leverage `resolve_task_file()` and `resolve_plan_file()` from `task_utils.sh`.

Output:
```
TASK_LOCATION|active|aitasks/t42_feature.md
PLAN_LOCATION|archived|aiplans/archived/p42_feature.md
```

Location types: `active`, `archived`, `tar_gz`, `not_found`

### Step 2: Refine post-revert instructions in SKILL.md

Update Step 4 (Create Revert Task) to include detailed instructions for each disposition:

**"Delete task and plan":**
```markdown
## Post-Revert Steps
1. Delete original task file: `<task_path>`
2. Delete original plan file: `<plan_path>`
3. Commit deletions via `./ait git`
```

**"Keep archived":**
```markdown
## Post-Revert Steps
1. Update archived task file with Revert Notes section:
   ## Revert Notes
   - **Reverted by:** t<revert_id>
   - **Date:** YYYY-MM-DD
   - **Type:** Complete|Partial
   - **Areas reverted:** <list>
   - **Areas kept:** <list> (partial only)
2. Commit updates via `./ait git`
```

**"Move back to Ready":**
```markdown
## Post-Revert Steps
1. Move task file from archived to active: `aitasks/archived/` → `aitasks/`
2. Move plan file from archived to active: `aiplans/archived/` → `aiplans/`
3. Update task status: `aitask_update.sh --batch <id> --status Ready --assigned-to ""`
4. Add Revert Notes section to task description
5. Commit all changes via `./ait git`
```

### Step 3: Update `ait` dispatcher help text

Add `revert-analyze` to the `show_usage()` function with a brief description.

### Step 4: End-to-end validation

Test the complete flow manually:
1. Identify a known completed task with commits
2. Run `./ait revert-analyze --recent-tasks` — verify it appears
3. Run `./ait revert-analyze --task-commits <id>` — verify correct commits
4. Run `./ait revert-analyze --task-areas <id>` — verify area grouping
5. Run `./ait revert-analyze --find-task <id>` — verify file locations
6. Trace through the SKILL.md workflow mentally for all 3 dispositions

## Step 9 Reference
After implementation, follow task-workflow Step 9 for archival.
