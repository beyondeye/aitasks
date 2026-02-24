---
priority: medium
effort: low
depends: [t227_3]
issue_type: feature
status: Implementing
labels: [aitakspick]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-24 16:52
updated_at: 2026-02-24 22:35
---

Make `aitask-pick` lock-aware by adding a lock pre-check in `task-workflow/SKILL.md` Step 4, before attempting `aitask_own.sh`.

## Context

With locking now a separate pre-pick operation (via board or CLI), `aitask-pick` should detect if a task is already locked by someone else and warn the user interactively before proceeding.

## Key Files to Modify
- `.claude/skills/task-workflow/SKILL.md` -- Step 4 (lines 70-131)

## Changes

Add lock pre-check before the `aitask_own.sh` call:

1. Run `aitask_lock.sh --check <task_id>` (read-only)
2. If locked by a DIFFERENT user: parse YAML output, use AskUserQuestion:
   - "Task t<N> is already locked by <email> (since <time>, hostname: <hostname>). How to proceed?"
   - Options: "Force unlock and claim" / "Proceed anyway" / "Pick a different task"
   - Force unlock: proceed with `aitask_own.sh --force`
   - Proceed anyway: proceed with normal `aitask_own.sh`
   - Pick different: return to task selection
3. If locked by SAME email: display "Task already locked by you -- refreshing lock." Proceed normally.
4. If not locked or check fails: proceed normally (existing behavior unchanged).

## Verification
- Read the modified SKILL.md and verify the lock pre-check logic
- Verify all three user paths work: force unlock, proceed anyway, pick different
