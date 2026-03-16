---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [revert, scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-16 23:09
updated_at: 2026-03-16 23:11
---

## Bug: aitask_query_files.sh missing `archived-task` subcommand

### Problem
The `aitask-revert` skill (`.claude/skills/aitask-revert/SKILL.md`, line 28) calls:
```bash
./.aitask-scripts/aitask_query_files.sh archived-task <number>
```
This subcommand does not exist in `aitask_query_files.sh`, causing:
```
Error: Unknown subcommand: 'archived-task'. Use --help for usage.
```
This blocks `aitask-revert` from resolving tasks that might be in the archive during Step 1 (Task Discovery).

### Root Cause
The `archived-task` subcommand was referenced in the skill definition but never implemented in `aitask_query_files.sh`. The script has `archived-children` (for child tasks in archive) but no equivalent for parent-level archived tasks.

### Fix
Add an `archived-task` subcommand to `.aitask-scripts/aitask_query_files.sh` that:
1. Takes a task number argument (e.g., `archived-task 369`)
2. Looks for `$ARCHIVED_DIR/t${num}_*.md`
3. Returns `ARCHIVED_TASK:<path>` if found, `NOT_FOUND` otherwise

Follow the existing patterns in the script (e.g., `cmd_task_file`, `cmd_archived_children`) for implementation style.

Also update the script's help text and header comments to include the new subcommand.

### Files to Modify
- `.aitask-scripts/aitask_query_files.sh` — add `cmd_archived_task()` function and dispatch case

### Verification
```bash
# Should return NOT_FOUND for a non-existent task
./.aitask-scripts/aitask_query_files.sh archived-task 99999

# Should return ARCHIVED_TASK:<path> for a task that is in aitasks/archived/
# (pick any archived task number to test)
./.aitask-scripts/aitask_query_files.sh archived-task <some_archived_id>
```
