---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Done
labels: []
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-17 10:13
updated_at: 2026-03-17 10:31
completed_at: 2026-03-17 10:31
---

## Goal

Consolidate the two sequential bash script calls in task-workflow Step 4 (lock pre-check + ownership claim) into a single `aitask_pick_own.sh` call.

Currently, Step 4 in `.claude/skills/task-workflow/SKILL.md` runs:
1. `aitask_lock.sh --check <task_num>` — read-only lock pre-check
2. `aitask_pick_own.sh <task_num> --email "<email>"` — actual lock acquisition + status update + commit

The pre-check is largely redundant because `aitask_pick_own.sh` already returns `LOCK_FAILED:<owner>` when lock acquisition fails, and the SKILL already handles that case with user prompts and `--force` retry.

## Changes Required

### 1. Enhance `aitask_pick_own.sh` LOCK_FAILED output

Change `LOCK_FAILED:<owner>` to include lock details:
```
LOCK_FAILED:<owner>:<locked_at>:<hostname>
```

This eliminates the need for a separate `aitask_lock.sh --check` call after a LOCK_FAILED response. The details are already available inside `aitask_lock.sh --lock` when it detects a conflict — they just need to be propagated up.

### 2. Simplify task-workflow SKILL.md Step 4

Remove the "Lock pre-check (read-only)" subsection (lines ~118-141) that calls `aitask_lock.sh --check`. Consolidate the lock conflict handling into the existing `LOCK_FAILED` handler:

**Before (two calls):**
- `aitask_lock.sh --check` → if locked by same user, say "refreshing" → if locked by other, ask user (force/proceed/pick different)
- `aitask_pick_own.sh` → if LOCK_FAILED, call `--check` again for details → ask user again

**After (one call):**
- `aitask_pick_own.sh` → if LOCK_FAILED, parse details from output → ask user (force unlock / pick different) → retry with `--force` if needed
- Same-user lock refresh is handled automatically by `aitask_lock.sh --lock` (same owner = refresh)

### 3. Update Step 7 pre-implementation guard

Step 7 already uses only `aitask_pick_own.sh` (no pre-check), so it just needs to parse the new `LOCK_FAILED` format.

### 4. Check other consumers

Verify that `aitask-pickrem` and `aitask-pickweb` skills parse `LOCK_FAILED` output — update them to handle the new format.

## Notes

- The `aitask_lock.sh --check` command itself should NOT be removed — it's still useful as a standalone CLI tool (`ait lock --check`). Only its use in task-workflow Step 4 is being eliminated.
- The race window between pre-check and acquisition is also eliminated, simplifying the overall flow.
