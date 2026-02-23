---
Task: t221_2_update_write_scripts_to_use_task_git.md
Parent Task: aitasks/t221_move_aitasks_and_aiplans_to_separate_branch.md
Sibling Tasks: aitasks/t221/t221_3_*.md, aitasks/t221/t221_4_*.md, aitasks/t221/t221_5_*.md, aitasks/t221/t221_6_*.md
Archived Sibling Plans: aiplans/archived/p221/p221_1_core_infrastructure_task_git_helper.md
Branch: main (no worktree)
---

# Plan: Update write scripts to use task_git() (t221_2)

## Context

t221_1 added `task_git()`, `task_sync()`, and `task_push()` helpers to `aiscripts/lib/task_utils.sh`. These wrap git commands to target the task data worktree (`.aitask-data/`) in branch mode, or pass through to plain `git` in legacy mode. This task replaces all direct git calls on task/plan files with these helpers across 5 scripts.

## Steps

### Step 1: Update aitask_own.sh
- [x] Add `source "$SCRIPT_DIR/lib/task_utils.sh"` after terminal_compat.sh source
- [x] `sync_remote()`: Replace `git pull` with `task_sync`
- [x] `commit_and_push()`: Replace `git add`, `git commit`, `git push` with `task_git`/`task_push`

### Step 2: Update aitask_archive.sh
- [x] `archive_parent()`: Replace all `git add`, `git commit` with `task_git` equivalents
- [x] Folded task cleanup: Replace `git rm` with `task_git rm`
- [x] `archive_child()`: Replace all `git add`, `git commit` with `task_git` equivalents

### Step 3: Update aitask_create.sh
- [x] Add `source "$SCRIPT_DIR/lib/task_utils.sh"`
- [x] Child task creation: Replace `git add`, `git commit`
- [x] Parent task creation: Replace `git add`, `git commit`
- [x] Interactive commit_task(): Replace `git add`, `git commit`
- [x] Batch mode: Replace all `git add`, `git commit`

### Step 4: Update aitask_update.sh
- [x] Add `source "$SCRIPT_DIR/lib/task_utils.sh"`
- [x] Interactive commit: Replace `git add`, `git commit`
- [x] Batch mode: Replace `git add`, `git commit`

### Step 5: Update aitask_zip_old.sh
- [x] Add `source "$SCRIPT_DIR/lib/task_utils.sh"`
- [x] Commit block: Replace `git add`, `git commit`

## Verification

- [x] `shellcheck` on all 5 modified scripts
- [x] Existing tests pass
- [x] Grep confirms no remaining direct git operations on task/plan paths

## Final Implementation Notes
- **Actual work done:** Replaced all direct `git add/commit/push/rm` calls with `task_git`/`task_sync`/`task_push` equivalents in 5 scripts, added `source task_utils.sh` to 4 scripts (archive.sh already had it), and fixed 2 test files that needed `task_utils.sh` in their temp environments
- **Deviations from plan:** Also needed to fix `tests/test_draft_finalize.sh` and `tests/test_zip_old.sh` — both created temp directories without `task_utils.sh`, causing source failures. Also replaced `git diff --cached --quiet` with `task_git diff --cached --quiet` and `git rev-parse` with `task_git rev-parse` in own.sh/create.sh/update.sh/archive.sh for full consistency
- **Issues encountered:** Two tests (draft_finalize: 25 failures, zip_old: hanging) were broken because their `setup_test_env()` functions only copied `terminal_compat.sh` to temp dirs. Adding `task_utils.sh` copy fixed both
- **Key decisions:** Used `task_push` in aitask_own.sh instead of keeping the custom warning message, since push is already best-effort and the calling skill handles failures
- **Notes for sibling tasks:** All 5 write scripts now source `task_utils.sh` and use `task_git()` for task/plan git operations. Read-only scripts (`aitask_ls.sh`, `aitask_stats.sh`) were intentionally NOT changed. `aitask_lock.sh` and `aitask_claim_id.sh` use their own separate branch logic and were also NOT changed. Test files that set up isolated temp environments need to copy `task_utils.sh` alongside `terminal_compat.sh`
