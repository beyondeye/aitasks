---
Task: t221_4_update_python_board.md
Parent Task: aitasks/t221_move_aitasks_and_aiplans_to_separate_branch.md
Sibling Tasks: aitasks/t221/t221_5_*.md, aitasks/t221/t221_6_*.md
Archived Sibling Plans: aiplans/archived/p221/p221_1_core_infrastructure_task_git_helper.md, aiplans/archived/p221/p221_2_update_write_scripts_to_use_task_git.md, aiplans/archived/p221/p221_3_setup_and_migration.md
Branch: main (no worktree)
---

# Plan: Update Python Board for Worktree-Aware Git Operations (t221_4)

## Context

t221 moves task/plan data from main to an orphan `aitask-data` branch, accessed via a worktree at `.aitask-data/`. Shell scripts (t221_1, t221_2) already use `task_git()` helpers. This task updates the Python TUI board to route its 6 git subprocess calls through worktree detection.

## File to Modify

**`aiscripts/board/aitask_board.py`** — 6 git subprocess calls need updating

## Steps

### Step 1: Add worktree detection helper (after line 28)

- [x] Add `DATA_WORKTREE` constant and `_task_git_cmd()` helper function

### Step 2: Update `refresh_git_status()` (line 305-307)

- [x] Replace `["git", "status", ...]` with `[*_task_git_cmd(), "status", ...]`

### Step 3: Update `revert_task()` (line 1359-1361)

- [x] Replace `["git", "checkout", ...]` with `[*_task_git_cmd(), "checkout", ...]`

### Step 4: Update `_execute_delete()` — git rm (line 2493-2495)

- [x] Replace `["git", "rm", ...]` with `[*_task_git_cmd(), "rm", ...]`

### Step 5: Update `_execute_delete()` — git commit (line 2518-2520)

- [x] Replace `["git", "commit", ...]` with `[*_task_git_cmd(), "commit", ...]`

### Step 6: Update `_git_commit_tasks()` — git add (line 2539-2541)

- [x] Replace `["git", "add", ...]` with `[*_task_git_cmd(), "add", ...]`

### Step 7: Update `_git_commit_tasks()` — git commit (line 2543-2545)

- [x] Replace `["git", "commit", ...]` with `[*_task_git_cmd(), "commit", ...]`

## Verification

1. Legacy mode: Run `ait board` without `.aitask-data/` — all git operations work as before
2. Check `_task_git_cmd()` returns `["git"]` when no worktree exists
3. Check `_task_git_cmd()` returns `["git", "-C", ".aitask-data"]` when worktree exists

## Final Implementation Notes
- **Actual work done:** Added `DATA_WORKTREE` constant and `_task_git_cmd()` helper function to `aitask_board.py`, updated all 6 git subprocess calls to use `[*_task_git_cmd(), ...]` pattern. Python `*` unpacking mirrors the shell `task_git()` approach from t221_1.
- **Deviations from plan:** None — implementation followed the plan exactly
- **Issues encountered:** None — straightforward mechanical replacement
- **Key decisions:** Used `(DATA_WORKTREE / ".git").exists()` check (same as shell scripts' `_ait_detect_data_worktree`) to detect branch mode. The `.git` file (not directory) is created by `git worktree add`.
- **Notes for sibling tasks:** The Python board now has its own worktree detection via `_task_git_cmd()`, independent of the shell `task_git()` helper. t221_5 (skills/docs) doesn't need to update anything board-related since the board auto-detects. t221_6 (testing) should verify the board's git operations work in both legacy and branch modes — the `_task_git_cmd()` function can be tested by checking its return value with/without `.aitask-data/` directory present.
