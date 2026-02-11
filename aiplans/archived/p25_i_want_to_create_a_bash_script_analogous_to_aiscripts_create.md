---
Task: t25_i_want_to_create_a_bash_script_analogous_to_aiscripts_create.md
Worktree: none (working in main repository)
Branch: current
---

# Implementation Plan: aitasks_update.sh

## Overview
Create `aitasks_update.sh` - a bash script for updating existing AI tasks with two modes:
1. **Interactive mode** (default) - fzf-based task selection and metadata editing
2. **Batch mode** (`--batch` flag) - CLI parameters for scripted/automated updates

## Design Decisions
- **Label handling:** Support both `--labels` (replace all) and `--add-label`/`--remove-label` (modify)
- **Editor:** Use `$EDITOR` environment variable (standard Unix convention)
- **Task selection:** fzf menu by default; direct task number via argument

## Implementation Steps

- [x] Step 1: Create script with argument parsing and help
- [x] Step 2: Task file resolution function
- [x] Step 3: YAML parsing function (adapted from aitasks_ls.sh)
- [x] Step 4: Interactive mode implementation
- [x] Step 5: Batch mode implementation
- [x] Step 6: YAML writing function
- [x] Step 7: File rename handling
- [x] Step 8: Make executable and test

## Batch Mode Tests Passed
- [x] Priority update
- [x] Multiple field updates (-p, -e)
- [x] Add labels (--add-label)
- [x] Remove labels (--remove-label)
- [x] Clear all labels (--labels "")
- [x] Silent mode (--silent)
- [x] Task rename (--name)
- [x] Description update (-d)
- [x] aitasks_ls.sh correctly parses updated files

## Interactive Mode Fixes Applied
- [x] Loop until "Done - save changes" is selected
- [x] Added "Exit - discard changes" option
- [x] Exclude current task from dependencies list
- [x] Fix description parsing (sed pattern)
- [x] Fix GUI editor support (--wait flag for code, subl, etc.)
- [x] Fix fzf terminal access within case statement

## Post-Implementation

- [ ] Archive task file to `aitasks/archived/`
- [ ] Archive this plan file to `aiplans/archived/`

---
COMPLETED: 2026-02-01 18:45
