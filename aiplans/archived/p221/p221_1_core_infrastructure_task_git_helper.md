---
Task: t221_1_core_infrastructure_task_git_helper.md
Parent Task: aitasks/t221_move_aitasks_and_aiplans_to_separate_branch.md
Sibling Tasks: aitasks/t221/t221_2_*.md, aitasks/t221/t221_3_*.md, aitasks/t221/t221_4_*.md, aitasks/t221/t221_5_*.md, aitasks/t221/t221_6_*.md
Branch: main (no worktree)
---

# Plan: Core Infrastructure — task_git() helper and ait git command (t221_1)

## Steps

### Step 1: Add worktree detection and helpers to `task_utils.sh`

Add after line 18 (existing `ARCHIVED_PLAN_DIR` variable), before the Platform Detection section:

- `_AIT_DATA_WORKTREE` variable (cached detection result)
- `_ait_detect_data_worktree()` — detects `.aitask-data/` worktree
- `task_git()` — runs git commands targeting the task data worktree
- `task_sync()` — pulls task data from remote
- `task_push()` — pushes task data to remote

### Step 2: Add `ait git` subcommand to dispatcher

In the `ait` script, add `git)` case to the command routing. Also add to help text.

### Step 3: Verify backward compatibility

Legacy mode (no `.aitask-data/`) must work identically to current behavior.

## Verification

- [x] `./ait git status` works in legacy mode
- [x] `shellcheck aiscripts/lib/task_utils.sh` — only pre-existing info-level warnings
- [x] Existing tests pass (terminal_compat, sed_compat, global_shim, resolve_tar_gz, detect_env)
- [x] Branch mode detection works (`.aitask-data/.git` detected → `_AIT_DATA_WORKTREE=".aitask-data"`)

## Final Implementation Notes
- **Actual work done:** Added 4 functions (`_ait_detect_data_worktree`, `task_git`, `task_sync`, `task_push`) to `task_utils.sh` and `ait git` subcommand to the dispatcher, exactly as planned
- **Deviations from plan:** None — implementation followed the plan exactly
- **Issues encountered:** ShellCheck doesn't allow `# shellcheck source=` directives inside case branches — removed the directive (SC1091 info-level is expected)
- **Key decisions:** The `ait git` command skips the update check (added to the skip list alongside `help`, `install`, `setup`) for faster passthrough
- **Notes for sibling tasks:** The `task_git()`, `task_sync()`, and `task_push()` functions are now available to all scripts that source `task_utils.sh`. The `_AIT_DATA_WORKTREE` variable is cached after first detection. In legacy mode (no `.aitask-data/`), all functions pass through to plain `git` with zero overhead beyond the detection check.
