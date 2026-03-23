---
Task: t446_fix_task_creation_batch_git_log_branch_mode.md
Worktree: (current directory)
Branch: main
Base branch: main
---

# Plan: Fix task-creation-batch.md git log command for branch mode

## Problem

In branch mode, `git log -1 --name-only --pretty=format:'' | grep '^aitasks/t'` queries the main branch instead of the `aitask-data` branch where task commits live. This returns wrong results or nothing.

## Fix

Change `git log` to `./ait git log` in all 7 locations across skill/procedure files where this pattern appears. `./ait git` routes through `task_git()` which automatically targets `.aitask-data` in branch mode.

## Files changed

1. `.claude/skills/task-workflow/task-creation-batch.md:28`
2. `.claude/skills/aitask-explore/SKILL.md:172`
3. `.claude/skills/aitask-review/SKILL.md:205,221`
4. `.claude/skills/aitask-pr-import/SKILL.md:258`
5. `.claude/skills/aitask-revert/SKILL.md:626`
6. `.claude/skills/aitask-wrap/SKILL.md:223`

## Final Implementation Notes

- **Actual work done:** Changed `git log` to `./ait git log` in all 7 occurrences across 6 files. Exact same single-pattern fix everywhere.
- **Deviations from plan:** None. The task description already identified the fix precisely.
- **Issues encountered:** None.
- **Key decisions:** Confirmed that other bare `git` commands in skills (e.g., `git log --all --grep`, `git diff <hash>`, `git diff --stat`) are correct as-is because they operate on code commits (main branch) or specific commit hashes, not task file history.
