---
Task: t221_3_setup_and_migration.md
Parent Task: aitasks/t221_move_aitasks_and_aiplans_to_separate_branch.md
Sibling Tasks: aitasks/t221/t221_4_*.md, aitasks/t221/t221_5_*.md, aitasks/t221/t221_6_*.md
Archived Sibling Plans: aiplans/archived/p221/p221_1_core_infrastructure_task_git_helper.md, aiplans/archived/p221/p221_2_update_write_scripts_to_use_task_git.md
Branch: main (no worktree)
---

# Plan: Setup and Migration — setup_data_branch() (t221_3)

## Context

t221 moves task/plan data from main to an orphan `aitask-data` branch, accessed via a permanent worktree at `.aitask-data/` with symlinks. t221_1 added `task_git()`/`task_sync()`/`task_push()` to `task_utils.sh` and `ait git` to the dispatcher. t221_2 updated all write scripts to use these helpers. This task adds the setup and migration infrastructure to `aitask_setup.sh`.

## Files to Modify

1. **`aiscripts/aitask_setup.sh`** — Add `setup_data_branch()` + `update_claudemd_git_section()` functions, integrate into `main()` flow
2. **`tests/test_data_branch_setup.sh`** (NEW) — Automated tests

## Steps

### Step 1: Add `update_claudemd_git_section()` and `setup_data_branch()` to aitask_setup.sh (after line 732)

- [x] `update_claudemd_git_section()` — idempotent CLAUDE.md updater
- [x] `setup_data_branch()` — full setup/migration function following existing patterns

### Step 2: Integrate into main() flow

- [x] Add `setup_data_branch` call after `setup_lock_branch` and before `setup_python_venv`

### Step 3: Create automated test file

- [x] `tests/test_data_branch_setup.sh` — 9 test cases covering fresh setup, migration, idempotency, clone-on-new-PC, no-remote, CLAUDE.md updates

## Verification

- [x] `bash tests/test_data_branch_setup.sh` — all tests pass
- [x] `bash tests/test_setup_git.sh` — no regressions
- [x] `shellcheck aiscripts/aitask_setup.sh`

## Final Implementation Notes
- **Actual work done:** Added `update_claudemd_git_section()` and `setup_data_branch()` functions to `aitask_setup.sh` (~170 lines total), integrated into `main()` flow, created `tests/test_data_branch_setup.sh` with 44 assertions across 9 test cases
- **Deviations from plan:** None — implementation followed the plan exactly
- **Issues encountered:** shellcheck test used `grep -c "error"` which matched message text; fixed to use `--severity=error` flag
- **Key decisions:** Used `git mktree < /dev/null` + `git commit-tree` + `git update-ref` for orphan branch creation (no `git checkout --orphan` needed, avoids disturbing working tree). Works without remote via `git update-ref` instead of `git push`.
- **Notes for sibling tasks:** The `setup_data_branch()` function is now available. t221_4 (Python board) can test the new worktree detection. t221_5 (skills/docs) should reference this function when documenting the setup flow. t221_6 (testing) can extend `test_data_branch_setup.sh` with end-to-end workflow tests. The `update_claudemd_git_section()` is also reusable — called by `setup_data_branch()` but can also be called independently.
