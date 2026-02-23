---
priority: high
effort: medium
depends: [t221_1]
issue_type: refactor
status: Ready
labels: []
created_at: 2026-02-23 11:14
updated_at: 2026-02-23 11:15
---

## Context

This is child task 2 of t221 (Move aitasks/aiplans to separate branch). The parent task implements a symlink + worktree architecture where task/plan data lives on an orphan `aitask-data` branch. This child task updates all shell scripts that perform git write operations on task/plan files to use the `task_git()` helper from `task_utils.sh` (created in t221_1).

The key principle: replace all direct `git add/commit/push/rm` calls that operate on `aitasks/` or `aiplans/` with `task_git add/commit/push/rm`. In legacy mode (no `.aitask-data/` worktree), `task_git` passes through to plain `git` — so this change is fully backward compatible.

## Key Files to Modify

1. **`aiscripts/aitask_own.sh`** — Lines 120 (git pull), 186 (git add aitasks/), 192 (git commit), 196 (git push)
2. **`aiscripts/aitask_archive.sh`** — Lines ~236-242 (git add, git rm, git commit)
3. **`aiscripts/aitask_create.sh`** — Git add + commit operations for new task files
4. **`aiscripts/aitask_update.sh`** — Git add + commit operations for metadata updates
5. **`aiscripts/aitask_zip_old.sh`** — Git add + commit for tar.gz archives

## Reference Files for Patterns

- `aiscripts/lib/task_utils.sh` — Contains `task_git()`, `task_sync()`, `task_push()` (added by t221_1)
- `aiscripts/aitask_own.sh` — Representative pattern: `git add aitasks/` → `task_git add aitasks/`

## Implementation Plan

### Step 1: Update aitask_own.sh

This is the simplest and most representative script. Changes:
- Add `source "$SCRIPT_DIR/lib/task_utils.sh"` (it already sources terminal_compat.sh)
- Line 120: `git pull --ff-only --quiet` → `task_sync` (in `sync_remote()`)
- Line 186: `git add aitasks/` → `task_git add aitasks/`
- Line 192: `git commit -m "..."` → `task_git commit -m "..."`
- Line 196: `git push --quiet` → `task_push` (in `commit_and_push()`)
- Also change the stale lock cleanup call context if needed

### Step 2: Update aitask_archive.sh

Find all `git add`, `git rm`, and `git commit` calls that operate on task/plan files. Replace with `task_git` equivalents. Ensure `task_utils.sh` is sourced (it may already be).

### Step 3: Update aitask_create.sh

Find git commit operations for new task files. Replace `git add` + `git commit` with `task_git add` + `task_git commit`.

### Step 4: Update aitask_update.sh

Find git operations for metadata updates. Replace with `task_git` equivalents.

### Step 5: Update aitask_zip_old.sh

Find git operations for tar.gz archive commits. Replace with `task_git` equivalents.

### Important notes

- Do NOT change `aitask_lock.sh` or `aitask_claim_id.sh` — they use their own separate branches
- Do NOT change read-only scripts (`aitask_ls.sh`, `aitask_stats.sh`, etc.)
- Each script must source `task_utils.sh` if it doesn't already
- The `EMAILS_FILE="aitasks/metadata/emails.txt"` path in aitask_own.sh does NOT need changing (symlinks handle file reads)

## Verification Steps

1. **Legacy mode:** Run each modified script in a repo without `.aitask-data/` — behavior must be identical
2. **Shellcheck:** `shellcheck aiscripts/aitask_own.sh aiscripts/aitask_archive.sh aiscripts/aitask_create.sh aiscripts/aitask_update.sh aiscripts/aitask_zip_old.sh`
3. **Existing tests:** `bash tests/test_*.sh`
4. **Manual test:** Create a task, update it, archive it — verify git operations work
