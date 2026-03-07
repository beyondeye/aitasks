---
Task: t326_3_update_tests_and_final_cleanup.md
Parent Task: aitasks/t326_refactoring_of_installed_files.md
Sibling Tasks: aitasks/t326/t326_1_*.md, aitasks/t326/t326_2_*.md
Archived Sibling Plans: aiplans/archived/p326/p326_1_*.md, aiplans/archived/p326/p326_2_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t326_3 — Update tests and final cleanup

## Overview

Update all test files from `aiscripts/` to `.aitask-scripts/`, remove the backward-compat symlink, and run comprehensive verification to ensure the rename is complete and nothing is broken.

## Steps

### 1. Update Bash Test Files (~42 files, ~631 occurrences)

Systematic find-and-replace in all `tests/test_*.sh`:
- `aiscripts/` → `.aitask-scripts/`

High-occurrence files (verify extra carefully):
- `tests/test_task_lock.sh` (~85)
- `tests/test_explain_cleanup.sh` (~57)
- `tests/test_claim_id.sh` (~55)
- `tests/test_setup_git.sh` (~34)
- `tests/test_pr_contributor_metadata.sh` (~34)
- `tests/test_draft_finalize.sh` (~32)
- `tests/test_lock_force.sh` (~25)
- `tests/test_zip_old.sh` (~24)

**Important:** Some tests may check path strings in assertions (e.g., `assert_contains "$output" "aiscripts/"`). These expected-output strings also need updating.

### 2. Update Python Test Files (~5 files)

- `tests/test_aitask_stats_py.py`
- `tests/test_config_utils.py`
- `tests/test_board_config_split.py`
- `tests/test_aitask_merge.py`
- Any other `tests/test_*.py`

### 3. Remove Backward-Compat Symlink

```bash
rm aiscripts  # It's a symlink, safe to rm
git add -A aiscripts
```

### 4. Run All Bash Tests

```bash
for f in tests/test_*.sh; do
    echo "=== $f ==="
    bash "$f" || echo "FAILED: $f"
done
```

Fix any failures before proceeding.

### 5. Run All Python Tests

```bash
for f in tests/test_*.py; do
    echo "=== $f ==="
    python3 "$f" || echo "FAILED: $f"
done
```

### 6. Run Shellcheck

```bash
shellcheck .aitask-scripts/aitask_*.sh
```

### 7. Final Stale Reference Check

```bash
grep -r 'aiscripts/' --include='*.sh' --include='*.md' --include='*.py' --include='*.json' --include='*.yml' --include='*.yaml' . | grep -v '.aitask-scripts' | grep -v archived/ | grep -v CHANGELOG
```
Should return 0 matches.

### 8. Verify Core Operations

```bash
./ait --version
./ait ls
```

### 9. Commit

```bash
git add tests/
git commit -m "refactor: Update tests and remove aiscripts symlink (t326_3)"
```

## Verification
- `ls -la aiscripts` → should fail (symlink removed)
- `ls .aitask-scripts/aitask_*.sh` → lists all scripts
- All bash and Python tests pass
- Shellcheck clean
- No stale `aiscripts/` references in source files
- `./ait --version` and `./ait ls` work

## Final Implementation Notes
- **Actual work done:** Replaced all `aiscripts/` → `.aitask-scripts/` references across 36 test files (bash + python), 15 core scripts (comment-only usage examples + 3 functional code fixes), 1 website script, and removed the backward-compat symlink. Total: 57 files changed, ~573 lines modified.
- **Deviations from plan:** The initial `sed 's|aiscripts/|.aitask-scripts/|g'` only caught references with a trailing slash. Many bare `aiscripts` references (e.g., `SCRIPT_DIR="$PROJECT_DIR/aiscripts"`, Python `sys.path.insert`) required a second pass with targeted patterns (`/aiscripts"` → `/.aitask-scripts"`, `/aiscripts'` → `/.aitask-scripts'`). Additionally, 15 core scripts in `.aitask-scripts/` had leftover comment-only references and 3 functional code bugs that the symlink had been masking — these were NOT in the original plan scope (expected to be done in t326_1/t326_2) but had to be fixed here since the symlink removal exposed them.
- **Issues encountered:** (1) `aitask_setup.sh` global shim checked for `aiscripts` directory in the heredoc-generated shim script — not caught by t326_1 because it's inside a heredoc. (2) `aitask_install.sh` VERSION path still referenced `aiscripts/VERSION`. (3) `aitask_review_detect_env.sh` directory pattern detection checked for `aiscripts/*`. All three were masked by the symlink during t326_1/t326_2.
- **Key decisions:** Left `aiscripts__` codebrowser snapshot name examples in comments (e.g., `aiscripts__lib__20260226_120000`) unchanged — these are historical snapshot directory names, not references to the scripts directory. Left `test_explain_cleanup.sh` fixture directory names (`aiscripts__20260226_*`) unchanged for the same reason.
- **Notes for sibling tasks:** This was the final child task. The rename is now complete with zero stale references. One pre-existing test failure exists in `test_data_branch_setup.sh` (7 failing tests about CLAUDE.md generation) — tracked as t328.

## Step 9 (Post-Implementation)
After verification, proceed to archival per the task-workflow. Since this is the last child task, the parent task (t326) will also be archived automatically.
