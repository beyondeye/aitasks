---
Task: t330_parent_task_locked_after_child_implementation.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

When `/aitask-pick <parent>` is run on a parent task with no children, Step 4 locks the parent. If planning then creates child tasks, the parent status is reverted to "Ready" but the **parent lock is not released**. This causes the parent to appear locked in `ait board` across all subsequent sessions until the very last child is archived (triggering parent archival, which releases the parent lock at `aitask_archive.sh:463`).

The user's requirement: "Only child tasks should be locked. Leave parent locking to manual via ait board."

## Plan

### Change 1: Release parent lock after child creation (PRIMARY FIX)

**File:** `.claude/skills/task-workflow/planning.md` (~line 79)

After the existing `aitask_update.sh --batch` call that reverts parent status, add a lock release:

```bash
./.aitask-scripts/aitask_lock.sh --unlock <parent_num> 2>/dev/null || true
```

This goes between the status revert and the "Write implementation plans" bullet. Both "Start first child" and "Stop here" paths benefit since the unlock happens before the checkpoint.

### No changes needed

- `aitask_pick_own.sh` — already only locks the specific task_id passed
- `aitask_lock.sh` — `--unlock` is already idempotent (gracefully handles "not locked")
- `aitask_archive.sh` — parent lock release at line 463 remains as safety net (idempotent)

## Verification

1. After making changes, read `planning.md` to confirm the instructions are clear
2. Trace the workflow mentally: `/aitask-pick <parent>` → no children → Step 4 locks parent → planning creates children → status reverted + **lock released** → child selected → only child locked
3. No script tests needed — changes are to skill instruction files only

## Final Implementation Notes
- **Actual work done:** Added a single lock release instruction in `planning.md` after the parent status revert when creating child tasks. The `aitask_lock.sh --unlock` call is idempotent and best-effort (`2>/dev/null || true`).
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Kept the safety-net parent lock release in `aitask_archive.sh:463` (when parent is archived after all children complete) since it's idempotent and provides a belt-and-suspenders safeguard.
