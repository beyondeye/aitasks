---
Task: t221_6_testing_and_validation.md
Parent Task: aitasks/t221_move_aitasks_and_aiplans_to_separate_branch.md
Sibling Tasks: (none pending)
Archived Sibling Plans: aiplans/archived/p221/p221_1_core_infrastructure_task_git_helper.md, aiplans/archived/p221/p221_2_update_write_scripts_to_use_task_git.md, aiplans/archived/p221/p221_3_setup_and_migration.md, aiplans/archived/p221/p221_4_update_python_board.md, aiplans/archived/p221/p221_5_update_skills_claude_md_and_website_docs.md
Branch: main (no worktree)
---

# Plan: Testing and Validation (t221_6)

## Context

t221 moved aitasks/aiplans to a separate git branch. Siblings t221_1-t221_5 added `task_git()`/`task_sync()`/`task_push()` in `task_utils.sh`, the `ait git` dispatcher, `setup_data_branch()` in `aitask_setup.sh`, updated all write scripts, the Python board, and skill files. This task creates comprehensive tests to validate the infrastructure works correctly in both legacy and branch modes.

## Steps

### Step 1: Create `tests/test_task_git.sh`

- [x] Unit tests for `task_git()`, `task_sync()`, `task_push()`, `_ait_detect_data_worktree()`, and `ait git`
- [x] 11 test cases, 17 assertions — all passing

### Step 2: Create `tests/test_data_branch_migration.sh`

- [x] End-to-end integration tests with full project setup and migration
- [x] 7 test cases, 21 assertions — all passing

### Step 3: Run all tests + shellcheck

- [x] New tests pass (17 + 21 = 38 assertions)
- [x] All 12 existing tests pass (no regressions)
- [x] Shellcheck clean (`--severity=error` produces zero findings)

## Final Implementation Notes
- **Actual work done:** Created `tests/test_task_git.sh` (11 test cases, 17 assertions) testing `_ait_detect_data_worktree()`, `task_git()`, `task_sync()`, `task_push()`, `ait git` command, and caching behavior in both legacy and branch modes. Created `tests/test_data_branch_migration.sh` (7 test cases, 21 assertions) testing end-to-end workflow: symlink access, `ait git` routing, `aitask_ls.sh`, `aitask_create.sh --batch --commit`, and `aitask_update.sh --batch --commit` all working correctly after `setup_data_branch` migration.
- **Deviations from plan:** (1) Used `TEST_SCRIPT_DIR` for the test's own dir to avoid collision with `SCRIPT_DIR` variable used by `setup_data_branch()` — this function reads `$SCRIPT_DIR/..` as the project root. (2) Used `DEFAULT_BRANCH` variable to handle systems where default branch is `master` instead of `main`. (3) Changed Test 7 assertion from checking specific filename to checking directory-level `aitasks` in `git status --porcelain` output (git shows untracked directories as `?? dirname/` when all contents are untracked).
- **Issues encountered:** (1) The biggest issue: `setup_data_branch()` uses `$SCRIPT_DIR/..` to determine the project root. When sourcing `aitask_setup.sh --source-only`, it overwrites `SCRIPT_DIR` to the real project's `aiscripts/` dir. If not corrected before calling `setup_data_branch()`, it operates on the real project instead of the test directory. This accidentally migrated the real project to branch mode during debugging. Fixed by always setting `SCRIPT_DIR` to the test repo's `aiscripts/` dir after sourcing and before any `setup_data_branch()` call. (2) Default git branch is `master` on this system, not `main` — fixed with `DEFAULT_BRANCH` detection.
- **Key decisions:** Followed the exact test pattern from `test_data_branch_setup.sh` (the t221_3 test) for helper functions, setup functions, and SCRIPT_DIR management. Used `pushd/popd` for function-level tests (Tests 1-5, 8-10) where shell variables need to be checked in the main shell. Used subshells `(cd ... && ...)` for ait executable tests (Tests 6-7). The migration test uses a single `setup_migrated_project()` call with sequential tests against the same temp dir.
- **Notes for sibling tasks:** This is the last child task of t221, so no further siblings. The `SCRIPT_DIR` collision with `setup_data_branch()` is a known gotcha — any future test that sources `aitask_setup.sh --source-only` and calls `setup_data_branch()` must set `SCRIPT_DIR` to the test repo's `aiscripts/` directory before the call.
