---
Task: t239_post_impl_workflow_do_not_use_ait_git.md
Branch: main (no worktree)
Base branch: main
---

## Context

The post-implementation workflow in `task-workflow/SKILL.md` tells Claude to "Stage and commit all implementation changes (including the updated plan file)" as a single operation. Claude interprets this as one `git add` covering both code files and `aiplans/` files, which fails when task data lives on a separate branch (via `.aitask-data/` worktree). Claude then has to retry with two separate operations — this happens every time, adding noise and overhead.

The `aitask-wrap` skill already implements the correct two-commit pattern (lines 263-270). We need to apply the same pattern to `task-workflow/SKILL.md` and `aitask-pickrem/SKILL.md`.

## Changes

### 1. `task-workflow/SKILL.md` — Step 8 commit instructions (lines 453-454)

Replace the vague single-commit instruction with explicit two-commit pattern separating code (regular `git`) from plan files (`./ait git`).

### 2. `task-workflow/SKILL.md` — Task Abort Procedure (lines 620-621)

Add `aiplans/` to staging command so deleted/modified plan files are captured.

### 3. `aitask-pickrem/SKILL.md` — Step 9 commit instructions (lines 319-321)

Same two-commit pattern fix as Change 1.

## Verification

1. Read modified files and verify two-commit pattern is consistent
2. Compare with correct pattern in `aitask-wrap/SKILL.md` lines 263-270
3. Grep for remaining "Stage and commit all" across `.claude/skills/`

## Final Implementation Notes
- **Actual work done:** All three changes implemented as planned. Replaced vague single-commit instructions with explicit two-commit patterns in `task-workflow/SKILL.md` (Step 8 and Task Abort Procedure) and `aitask-pickrem/SKILL.md` (Step 9).
- **Deviations from plan:** None.
- **Issues encountered:** None — straightforward text edits.
- **Key decisions:** Left `aitask-pickweb/SKILL.md` unchanged since it intentionally uses `git add -A` (all files on same branch during web execution).
