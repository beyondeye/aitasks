---
Task: t94_add_additional_task_type_refactoring.md
---

## Context

Task t94 requests adding a `refactor` issue type alongside `feature` and `bug`. Currently types are hardcoded in every script. The user wants to centralize valid types into `aitasks/metadata/task_types.txt`, mirroring the `labels.txt` pattern, with a seed file shipped in the release tarball.

## Part 1: Create Seed File and Install Infrastructure

### 1a. Create `seed/task_types.txt`
```
bug
feature
refactor
```
One type per line, sorted alphabetically.

### 1b. Update `install.sh` — add `install_seed_task_types()` function
Mirror the pattern from `install_seed_profiles()` (lines 188-210), but simpler since it's a single file:
- Source: `$INSTALL_DIR/seed/task_types.txt`
- Destination: `$INSTALL_DIR/aitasks/metadata/task_types.txt`
- Only install if destination doesn't exist (or `--force`)
- Clean up seed file after install
- Call this function from `main()` alongside `install_seed_profiles`

### 1c. Release workflow (`.github/workflows/release.yml`)
No change needed — the tarball already includes the entire `seed/` directory (line 45).

## Part 2: Add Helper Functions to Scripts

Add a `TASK_TYPES_FILE` variable and three helper functions to each script that needs them.

Scripts that need these functions:
- `aiscripts/aitask_create.sh` — validation + fzf selection
- `aiscripts/aitask_update.sh` — validation + fzf selection
- `aiscripts/aitask_issue_import.sh` — validation only (for --type override)

## Part 3: Replace Hardcoded Type Lists

All scripts updated to read from `aitasks/metadata/task_types.txt` instead of hardcoded lists.

### README.md
- Update YAML example to show `refactor` as an option
- Add documentation explaining that task types can be customized by editing `aitasks/metadata/task_types.txt`

## Verification

1. `./aiscripts/aitask_create.sh --batch --name "test_refactor" --type refactor --desc "test" --priority low --effort low` — should succeed
2. `./aiscripts/aitask_create.sh --batch --name "test_bad" --type invalid --desc "test" --priority low --effort low` — should fail with dynamic error
3. `./aiscripts/aitask_update.sh --batch <N> --type refactor` — should succeed
4. Clean up test task after verification

## Final Implementation Notes
- **Actual work done:** Centralized task types into `aitasks/metadata/task_types.txt` file (one type per line). Added `refactor` as a new type. Updated all 8 files: install.sh, aitask_create.sh, aitask_update.sh, aitask_issue_import.sh, aitask_ls.sh, aitask_stats.sh, aitask_board.py, and README.md.
- **Deviations from plan:** User requested centralizing types into a file (like labels.txt) instead of just adding "refactor" to hardcoded lists. This was a scope expansion from the original task description.
- **Issues encountered:** None — all syntax checks and functional tests passed on first attempt.
- **Key decisions:** Used `printf '%s\n'` instead of `echo -e` for fallback defaults in helper functions (more portable). Moved `rm -rf seed/` from install_seed_profiles to main() so all seed installers can access the seed directory.

## Post-Implementation
Step 9 of aitask-pick workflow: archive task and plan files.
