---
Task: t502_fix_child_task_rename_path_bug_in_aitask_update.md
Worktree: (none - current branch)
Branch: main
Base branch: main
---

# Plan: Fix child task rename path bug (t502)

## Context
In `aitask_update.sh`, the rename logic at line 1354 hardcodes `$TASK_DIR` as the destination directory. For child tasks (e.g., `47_1`), this places the renamed file in `aitasks/` instead of `aitasks/t47/`. The fix uses `dirname "$file_path"` to preserve the original directory.

## Changes

### 1. Fix rename path in aitask_update.sh (line 1354)

Replace:
```bash
final_path="$TASK_DIR/$new_filename"
```
With:
```bash
local parent_dir
parent_dir=$(dirname "$file_path")
final_path="$parent_dir/$new_filename"
```

This works for both parent tasks (`dirname` -> `aitasks/`) and child tasks (`dirname` -> `aitasks/t47/`).

### 2. Fix test_task_lock.sh — add missing archive_utils.sh copy

`task_utils.sh` sources `archive_utils.sh`, but the test setup only copied `terminal_compat.sh` and `task_utils.sh`. Added the missing `cp` for `archive_utils.sh` at all 6 test setup locations.

## Final Implementation Notes
- **Actual work done:** Fixed the child task rename path bug (1 line change) and fixed all 29 previously-failing tests in test_task_lock.sh by adding missing `archive_utils.sh` copy to test setups.
- **Deviations from plan:** Added test fixes (not in original plan) per user request.
- **Issues encountered:** test_task_lock.sh had pre-existing failures due to `archive_utils.sh` not being copied into test temp directories. This was caused by `archive_utils.sh` being added as a dependency of `task_utils.sh` at some point but the test setup not being updated.
- **Key decisions:** Used `dirname "$file_path"` which naturally handles both parent (`aitasks/`) and child (`aitasks/t47/`) paths without special-casing.
