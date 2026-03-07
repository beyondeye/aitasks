---
priority: high
effort: high
depends: [t326_2]
issue_type: refactor
status: Done
labels: [install_scripts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-07 22:45
updated_at: 2026-03-07 23:52
completed_at: 2026-03-07 23:52
---

Update all test files from aiscripts/ to .aitask-scripts/, remove backward-compat symlink, and run full verification.

## Context
After t326_1 (core rename) and t326_2 (skills/docs/configs), this final task updates all test files and performs the cleanup: removing the backward-compat symlink and running comprehensive verification. Tests are separated because they represent ~47 files with ~631 occurrences — the largest single category.

## Key Files to Modify

### Bash Test Files (~42 files, ~631 occurrences)
All files in `tests/test_*.sh`. Major files by occurrence count:
- `tests/test_task_lock.sh` (~85 occurrences)
- `tests/test_explain_cleanup.sh` (~57 occurrences)
- `tests/test_claim_id.sh` (~55 occurrences)
- `tests/test_setup_git.sh` (~34 occurrences)
- `tests/test_pr_contributor_metadata.sh` (~34 occurrences)
- `tests/test_draft_finalize.sh` (~32 occurrences)
- `tests/test_lock_force.sh` (~25 occurrences)
- `tests/test_zip_old.sh` (~24 occurrences)
- `tests/test_extract_auto_naming.sh` (~21 occurrences)
- `tests/test_init_data.sh` (~19 occurrences)
- `tests/test_data_branch_migration.sh` (~18 occurrences)
- And ~31 more test files with fewer occurrences

### Python Test Files (~5 files)
- `tests/test_aitask_stats_py.py`
- `tests/test_config_utils.py`
- `tests/test_board_config_split.py`
- `tests/test_aitask_merge.py`
- And any other `tests/test_*.py` files

## Implementation Steps
1. Use grep to find all test files with aiscripts/ references
2. For each test file, replace `aiscripts/` with `.aitask-scripts/`
3. Be careful with test assertions that check paths — the expected output strings may also need updating
4. Remove the backward-compat symlink: `rm aiscripts` (it's a symlink, safe to rm)
5. Run ALL bash tests: `for f in tests/test_*.sh; do echo "=== $f ==="; bash "$f"; done`
6. Run ALL Python tests
7. Run `shellcheck .aitask-scripts/aitask_*.sh`
8. Final grep for stale references:
   ```bash
   grep -r 'aiscripts/' --include='*.sh' --include='*.md' --include='*.py' --include='*.json' --include='*.yml' --include='*.yaml' . | grep -v '.aitask-scripts' | grep -v archived/ | grep -v CHANGELOG
   ```
9. Commit changes

## Verification Steps
- `ls -la aiscripts` should fail (symlink removed)
- `ls .aitask-scripts/aitask_*.sh` lists all scripts
- `./ait --version` works
- `./ait ls` works
- All bash tests pass
- All Python tests pass
- `shellcheck .aitask-scripts/aitask_*.sh` clean
- Final stale reference grep returns 0 matches
