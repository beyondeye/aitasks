---
Task: t226_ait_git_not_whitelisted.md
Branch: main (current branch)
---

## Context

The `./ait git` command is used by 6 skills (task-workflow, aitask-pickrem, aitask-wrap, aitask-fold, aitask-explore, ait-git) for committing task/plan file changes to the correct branch. However, `./ait git` is not whitelisted in `seed/claude_settings.local.json`, meaning new projects bootstrapped with `ait setup` will prompt users for permission every time a skill runs `./ait git`.

The active `.claude/settings.local.json` already has it (line 72), but the seed template does not.

## Plan

**File to modify:** `seed/claude_settings.local.json`

Add `"Bash(./ait git:*)"` to the `permissions.allow` array, placed after the regular `git` commands and before the `./aiscripts/` entries.

## Final Implementation Notes
- **Actual work done:** Added `"Bash(./ait git:*)"` to `seed/claude_settings.local.json` line 27, between `git log` and `./aiscripts/aitask_ls.sh` entries
- **Deviations from plan:** None
- **Issues encountered:** None
- **Key decisions:** Placed after regular git commands, before aiscripts entries, matching the logical grouping
