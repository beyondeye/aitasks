---
priority: medium
effort: low
depends: [t398_1, t398_2]
issue_type: feature
status: Implementing
labels: [aitask_revert]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-16 10:39
updated_at: 2026-03-16 16:28
---

Refine post-revert task management logic, add archived-task location helpers, ensure end-to-end flow works.

## Context
This is child 3 of t398 (aitask-revert). Depends on t398_1 and t398_2. This child refines the revert skill and script with post-revert task management details, adds a helper subcommand for locating archived tasks, updates the ait dispatcher help text, and performs end-to-end testing.

## Key Files to Modify
- `.claude/skills/aitask-revert/SKILL.md` — Add/refine post-revert management steps
- `.aitask-scripts/aitask_revert_analyze.sh` — Add `--find-task <task_id>` subcommand
- `ait` — Update help text to include revert-analyze command

## Reference Files for Patterns
- `.aitask-scripts/lib/task_utils.sh` — resolve_task_file(), resolve_plan_file() for searching active, archived, old.tar.gz
- `.aitask-scripts/aitask_update.sh` — `--batch` mode for updating task status

## Implementation Plan

### 1. Post-revert task management instructions
Ensure the revert task description (built in Step 4 of the skill) includes correct post-revert steps for each disposition:

**"Delete task and plan":**
- Instructions to remove original task and plan files after code revert is committed
- Handle both active and archived locations

**"Keep archived":**
- Instructions to update the archived task file with a "Revert Notes" section:
  ```markdown
  ## Revert Notes
  - **Reverted by:** t<revert_task_id>
  - **Date:** YYYY-MM-DD
  - **Type:** Complete/Partial
  - **Areas reverted:** <list>
  - **Areas kept:** <list> (partial only)
  ```

**"Move back to Ready":**
- Instructions to un-archive task file (move from `aitasks/archived/` → `aitasks/`)
- Un-archive plan file (move from `aiplans/archived/` → `aiplans/`)
- Update task status to Ready via `aitask_update.sh --batch <id> --status Ready`
- Add Revert Notes section to task description

### 2. Add `--find-task <task_id>` subcommand
Add to `aitask_revert_analyze.sh`:
- Locate task file across: active (`aitasks/`), archived (`aitasks/archived/`), deep archive (`old.tar.gz`)
- Locate plan file similarly in `aiplans/`
- Leverage `resolve_task_file()` and `resolve_plan_file()` from task_utils.sh
- Output: `TASK_LOCATION|<location_type>|<path>` and `PLAN_LOCATION|<location_type>|<path>`
- Location types: `active`, `archived`, `tar_gz`, `not_found`

### 3. Update ait dispatcher
- Add revert-analyze to the help text in `show_usage()`
- Ensure the command routing case statement includes `revert-analyze`

### 4. End-to-end testing
- Trace through a complete revert scenario manually
- Verify: discovery → analysis → type selection → task creation → disposition instructions
- Test all 3 disposition types produce correct task descriptions
- Test with both parent tasks (with children) and standalone tasks

## Verification Steps
- Revert task descriptions include correct post-revert management steps for all 3 dispositions
- `./ait revert-analyze --find-task <known_archived_id>` correctly locates files
- `./ait --help` (or `./ait` with no args) shows revert-analyze in the command list
- Full end-to-end: pick a known completed task, run through revert flow, verify task description
