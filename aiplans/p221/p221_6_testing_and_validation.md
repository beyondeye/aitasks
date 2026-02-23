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

- [ ] Unit tests for `task_git()`, `task_sync()`, `task_push()`, `_ait_detect_data_worktree()`, and `ait git`
- [ ] 11 test cases covering legacy/branch detection, passthrough, worktree targeting, sync, push, caching

### Step 2: Create `tests/test_data_branch_migration.sh`

- [ ] End-to-end integration tests with full project setup and migration
- [ ] 7 test cases covering symlinks, ait git routing, script operations in branch mode

### Step 3: Run all tests + shellcheck

- [ ] New tests pass
- [ ] Existing tests pass (no regressions)
- [ ] Shellcheck clean on modified scripts
