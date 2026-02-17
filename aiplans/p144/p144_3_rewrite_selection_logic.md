---
Task: t144_3_rewrite_selection_logic.md
Parent Task: aitasks/t144_ait_clear_old_rewrite.md
Sibling Tasks: (none remaining)
Archived Sibling Plans: aiplans/archived/p144/p144_1_rename_clear_old_to_zip_old.md, aiplans/archived/p144/p144_2_tar_gz_fallback_resolve_functions.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

The current `aitask_zip_old.sh` uses an obsolete "keep most recent" selection strategy that can archive files still needed by active work. This task rewrites the selection logic with a safety-aware approach: only archive files that are NOT relevant to any active task (via parent-child relationships or dependency references).

## Key Files

- **`aiscripts/aitask_zip_old.sh`** — Rewrite selection logic (main target)
- **`tests/test_zip_old.sh`** — New test file (19 test cases)

## Implementation Steps

### Step 1: Add `get_active_parent_numbers()` function
### Step 2: Add `get_dependency_task_ids()` function
### Step 3: Add `is_parent_active()` and `is_dependency()` helpers
### Step 4: Replace selection logic in `main()`
### Step 5: Update dry-run output
### Step 6: Update git commit message
### Step 7: Update usage/help text
### Step 8: Remove old functions and variables
### Step 9: Create `tests/test_zip_old.sh` (19 test cases)

## Step 10 (Post-Implementation) — Step 9 of task-workflow

Archive child task, update parent's `children_to_implement`, check if all children done (t144_3 is the last child → also archive parent).

## Verification

- `bash -n aiscripts/aitask_zip_old.sh` (syntax check)
- `bash tests/test_zip_old.sh` (run all 19 tests)
- `./ait zip-old --dry-run` on real project
- `./ait zip-old --dry-run -v` for detailed output

## Final Implementation Notes

- **Actual work done:** All 9 steps completed. Replaced the old "keep most recent" selection functions with new safety-aware logic using two rules: (1) keep archived siblings of active parents, (2) keep dependencies of active tasks. Removed 4 old functions (`find_most_recent`, `find_most_recent_child`, `get_files_to_archive`, `get_child_files_to_archive`) and `KEEP_TASK`/`KEEP_PLAN` variables. Added 4 new functions (`get_active_parent_numbers`, `get_dependency_task_ids`, `is_parent_active`, `is_dependency`) and 1 unified `collect_files_to_archive`. Created 19 test cases (53 assertions) all passing.
- **Deviations from plan:** (1) Fixed `verbose()` to output to stderr — the original function sent to stdout, which corrupted return values from functions called via command substitution (this was a pre-existing latent bug). (2) Changed `collect_files_to_archive` to use a global `_COLLECT_RESULT` variable instead of stdout return, to avoid subshell losing global `SKIPPED_*` variables. (3) Simplified `archive_files` to always treat input as paths relative to base_dir (removed the `*/*` heuristic which was fragile and had a pre-existing bug for parent files).
- **Issues encountered:** Command substitution subshell issue — `SKIPPED_ACTIVE_PARENTS` and `SKIPPED_DEPS` were being set inside `collect_files_to_archive()` called via `$(...)`, which runs in a subshell and loses global variable changes. Fixed by using a global `_COLLECT_RESULT` variable pattern (same pattern used by sibling t144_2 for `_AIT_EXTRACT_RESULT`).
- **Key decisions:** All file paths in the archive pipeline are now relative to base_dir (e.g., `t50_old.md` for parents, `t10/t10_1_name.md` for children). This is simpler and more consistent than the old mixed approach.
- **Notes for sibling tasks:** This is the last child task — no siblings remaining.
