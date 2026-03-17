---
Task: t407_revert_t369_3.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Revert t369_3 (gather_explain_context skill integration)

## Context

Task t369_3 added the `gather_explain_context` profile key and "Historical Context Prompt" step to the aitask-pick and planning workflows. The user wants to revert these skill-level changes while keeping the underlying scripts (t369_1, t369_2) intact.

Commit b53c1bd2210c added 27 lines across 3 files. A subsequent refactoring (t402, commit 159ac36) moved surrounding code in SKILL.md, so `git revert` won't apply cleanly. Manual removal is needed.

## Changes (3 files)

### 1. `.claude/skills/aitask-pick/SKILL.md` — Remove Step 0a-bis section (lines 12-26)

Remove the entire "Step 0a-bis: Historical Context Prompt" section (lines 12-26). This is a self-contained block between "Step 0a" and "Step 0b".

### 2. `.claude/skills/task-workflow/planning.md` — Remove Historical context gathering block (lines 106-115)

Remove the "Historical context gathering" bullet point and all its sub-content (lines 106-115). The line before is the "Stop here" child checkpoint line, the line after is "Create a detailed, step-by-step implementation plan."

### 3. `.claude/skills/task-workflow/profiles.md` — Remove gather_explain_context row (line 31)

Remove the single table row for `gather_explain_context` from the Profile Schema Reference table.

### 4. Delete `aitasks/metadata/profiles/fast_with_historical_ctx.yaml`

This profile's entire purpose was the `gather_explain_context: 1` feature. Without it, it's a near-duplicate of `fast`. Delete it entirely.

### 5. Remove dead `gather_explain_context` keys from remaining profiles

- `fast.yaml`: remove `gather_explain_context: 0`
- `default.yaml`: remove `gather_explain_context: ask`
- `remote.yaml`: remove `gather_explain_context: 0`

## Impact Analysis

### Cross-dependency check

### Cross-dependency check

- The kept scripts (`aitask_explain_context.sh`, `aitask_explain_format_context.py`) are standalone — no dependency on the skill sections being removed.
- No other skills reference Step 0a-bis or `explain_context_max_plans`.

**Safe to revert independently.**

## Post-Revert Task Management

Per task description:
1. Update t369 status back to Ready with revert notes
2. Add revert notes to archived child t369_3

## Verification

- `shellcheck` not needed (no shell scripts modified)
- Visual review: confirm Step 0a flows directly to Step 0b in SKILL.md
- Confirm profiles.md table has no orphaned references

## Final Implementation Notes
- **Actual work done:** Manually removed the 3 blocks added by commit b53c1bd2210c (Step 0a-bis, historical context gathering, profile schema row). Also deleted `fast_with_historical_ctx.yaml` profile and removed dead `gather_explain_context` keys from fast, default, and remote profiles.
- **Deviations from plan:** None — executed as planned.
- **Issues encountered:** `git revert` not possible due to subsequent refactoring in t402. Manual removal was straightforward since the added blocks were self-contained.
- **Key decisions:** Deleted `fast_with_historical_ctx.yaml` entirely per user request (its sole purpose was this feature).
