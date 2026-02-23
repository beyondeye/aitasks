---
priority: medium
effort: medium
depends: [t221_1, t221_2, t221_3, t221_4, t221_5]
issue_type: test
status: Implementing
labels: []
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-23 11:15
updated_at: 2026-02-23 14:05
---

## Context

This is child task 6 of t221 (Move aitasks/aiplans to separate branch). The parent task implements a symlink + worktree architecture. This child task creates comprehensive tests for both legacy mode and branch mode, and validates the entire migration workflow end-to-end.

## Key Files to Create

1. **`tests/test_task_git.sh`** (NEW) — Tests for `task_git()` helper and `ait git` command
2. **`tests/test_data_branch_migration.sh`** (NEW) — End-to-end migration test

## Reference Files for Patterns

- `tests/test_task_lock.sh` — Existing test pattern with `assert_eq`/`assert_contains` helpers
- `tests/test_claim_id.sh` — Pattern for testing branch-based operations in isolated temp repos
- `tests/test_setup_git.sh` — Pattern for testing git setup operations

## Implementation Plan

### Step 1: Create test_task_git.sh

Test the core infrastructure:

```bash
# Test 1: Legacy mode detection
# - In a repo without .aitask-data/, verify task_git passes through to plain git
# - Verify _AIT_DATA_WORKTREE is set to "."

# Test 2: Branch mode detection
# - Create .aitask-data/ directory with .git file
# - Verify _AIT_DATA_WORKTREE is set to ".aitask-data"

# Test 3: ait git command
# - Run ./ait git status in legacy mode — verify output matches git status
# - Run ./ait git status in branch mode — verify it targets the worktree

# Test 4: task_sync in legacy mode
# - Verify task_sync calls git pull --ff-only

# Test 5: task_push in legacy mode
# - Verify task_push calls git push
```

### Step 2: Create test_data_branch_migration.sh

Full end-to-end migration test:

```bash
# Setup: Create a temp repo with tasks on main (legacy mode)
# 1. Init repo, create aitasks/ and aiplans/ with sample files
# 2. Commit everything on main

# Test migration:
# 3. Run the migration (setup_data_branch or ait setup --migrate-data-branch)
# 4. Verify: aitask-data branch exists
# 5. Verify: .aitask-data/ worktree exists
# 6. Verify: symlinks aitasks -> .aitask-data/aitasks, aiplans -> .aitask-data/aiplans
# 7. Verify: aitasks/ and aiplans/ in .gitignore on main
# 8. Verify: task files accessible via symlinks (cat aitasks/t1_test.md)
# 9. Verify: git operations on task files target data branch
#    - Modify a task file
#    - ./ait git add aitasks/t1_test.md
#    - ./ait git commit -m "test"
#    - Verify commit appears on aitask-data branch, not main

# Test existing scripts work:
# 10. Run aitask_ls.sh — verify it lists tasks
# 11. Run aitask_create.sh --batch — verify task created and committed on data branch
```

### Step 3: Run all existing tests

Verify no regressions:
```bash
bash tests/test_claim_id.sh
bash tests/test_detect_env.sh
bash tests/test_draft_finalize.sh
bash tests/test_task_lock.sh
bash tests/test_terminal_compat.sh
bash tests/test_zip_old.sh
bash tests/test_setup_git.sh
bash tests/test_resolve_tar_gz.sh
bash tests/test_t167_integration.sh
bash tests/test_global_shim.sh
bash tests/test_sed_compat.sh
```

### Step 4: Shellcheck all modified scripts

```bash
shellcheck aiscripts/aitask_own.sh aiscripts/aitask_archive.sh aiscripts/aitask_create.sh aiscripts/aitask_update.sh aiscripts/aitask_zip_old.sh aiscripts/lib/task_utils.sh
```

## Verification Steps

1. All new tests pass with PASS summary
2. All existing tests pass with no regressions
3. Shellcheck produces no errors on modified scripts
4. Manual walkthrough: create task → update → archive in branch mode
