---
Task: t316_enforce_pre_implementation_own_lock_in_task_workflow_and_wra.md
Branch: (current branch, main)
---

## Context

Task t316 addresses a safety gap: if plan mode deferral or any other edge case causes Step 4 (Assign Task / claim ownership) to be skipped, implementation could start without the task being locked. This adds a guard at the beginning of every implementation step that verifies own/lock was performed, and runs it if not.

## Changes

### 1. `.claude/skills/task-workflow/SKILL.md` — Step 7 guard

Add a "Pre-implementation ownership guard" at the very beginning of Step 7 that checks both `status` is `Implementing` AND `assigned_to` matches the current user's email. If either condition fails, run `aitask_pick_own.sh` with full error handling.

### 2. `.claude/skills/aitask-pickrem/SKILL.md` — Step 8 guard

Same guard but non-interactive — failures trigger the Abort Procedure.

### 3. Codex CLI wrappers — Plan mode prerequisite

Add plan mode prerequisite to `.agents/skills/aitask-pickrem/SKILL.md` and `.agents/skills/aitask-pickweb/SKILL.md` (matching the pattern from `.agents/skills/aitask-pick/SKILL.md`).

### 4. `aitask-pickweb` — Explanatory note

Add note in Step 6 that ownership deferral to `aitask-web-merge` is by design.

### 5. `aitask-wrap` — No guard needed

No implementation step exists; work is already done before wrap runs.

## Final Implementation Notes

- **Actual work done:** Added pre-implementation ownership guards to task-workflow Step 7 and aitask-pickrem Step 8. Added plan mode prerequisites to Codex CLI wrappers for pickrem and pickweb. Added explanatory note to aitask-pickweb Step 6.
- **Deviations from plan:** During review, the guard was enhanced to also check `assigned_to` matches the current user's email (not just status check). This strengthens the guard against cases where a different user's ownership was left on the task.
- **Issues encountered:** None.
- **Key decisions:** The guard checks two conditions (status + assigned_to) rather than just status, providing stronger verification that the correct user owns the task before implementation begins.
