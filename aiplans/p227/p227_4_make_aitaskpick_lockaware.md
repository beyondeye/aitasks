---
Task: t227_4_make_aitaskpick_lockaware.md
Parent Task: aitasks/t227_aitask_own_failure_in_cluade_web.md
Sibling Tasks: aitasks/t227/t227_1_*.md, aitasks/t227/t227_2_*.md, aitasks/t227/t227_3_*.md, aitasks/t227/t227_5_*.md, aitasks/t227/t227_6_*.md
Worktree: (none - current branch)
Branch: main
Base branch: main
---

# Plan: t227_4 — Make aitask-pick lock-aware

## Context

With locking now a separate pre-pick operation, `aitask-pick` should detect pre-existing locks and warn users.

## Implementation Steps

### Step 1: Add lock pre-check to task-workflow Step 4
- Location: `.claude/skills/task-workflow/SKILL.md`, before the `aitask_own.sh` call in Step 4
- Insert read-only lock check: `aitask_lock.sh --check <task_id>`

### Step 2: Handle locked-by-different-user case
- Parse YAML output for locked_by, locked_at, hostname
- AskUserQuestion with three options:
  - "Force unlock and claim" → `aitask_own.sh --force`
  - "Proceed anyway" → normal `aitask_own.sh`
  - "Pick a different task" → return to selection

### Step 3: Handle locked-by-same-email case
- Display "Task already locked by you — refreshing lock."
- Proceed normally

### Step 4: Handle not-locked and check-fails cases
- Proceed normally (existing behavior unchanged)

## Key Files
- **Modify:** `.claude/skills/task-workflow/SKILL.md` — Step 4 (lines 70-131)

## Verification
- Read modified SKILL.md and verify lock pre-check logic
- Verify all three user paths: force unlock, proceed anyway, pick different

## Post-Implementation (Step 9)
Archive this child task.
