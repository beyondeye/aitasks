---
priority: high
effort: high
depends: [t221_1]
issue_type: refactor
status: Implementing
labels: []
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-23 11:14
updated_at: 2026-02-23 12:09
---

## Context

This is child task 3 of t221 (Move aitasks/aiplans to separate branch). The parent task implements a symlink + worktree architecture where task/plan data lives on an orphan `aitask-data` branch, accessed via a permanent worktree at `.aitask-data/` with symlinks.

This child task adds the setup and migration infrastructure to `aitask_setup.sh`: creating the `aitask-data` orphan branch, setting up the permanent worktree, creating symlinks, and migrating existing repos from legacy mode.

## Key Files to Modify

1. **`aiscripts/aitask_setup.sh`** — Add `setup_data_branch()` function and migration logic
2. **`.gitignore`** — Add entries for `.aitask-data/`, `aitasks/`, `aiplans/`

## Reference Files for Patterns

- `aiscripts/aitask_setup.sh` (lines 664-732) — Existing `aitask-ids` and `aitask-locks` branch initialization pattern
- `aiscripts/aitask_lock.sh` (lines 58+) — `init_lock_branch()` orphan branch creation pattern
- `aiscripts/lib/task_utils.sh` — `_ait_detect_data_worktree()` detection logic (added by t221_1)

## Implementation Plan

### Step 1: Add `setup_data_branch()` to aitask_setup.sh

Follow the existing pattern from `aitask-ids` and `aitask-locks` initialization. The function should:

1. Check if `aitask-data` branch already exists (local or remote)
2. If not, create orphan branch:
   ```bash
   git checkout --orphan aitask-data
   git rm -rf . 2>/dev/null || true
   mkdir -p aitasks/metadata aitasks/archived aiplans/archived
   # Copy metadata files if present
   git add .
   git commit -m "ait: Initialize aitask-data branch"
   git push -u origin aitask-data
   git checkout main
   ```
3. Create permanent worktree:
   ```bash
   git worktree add .aitask-data aitask-data
   ```
4. Create symlinks (if not already present):
   ```bash
   ln -sf .aitask-data/aitasks aitasks
   ln -sf .aitask-data/aiplans aiplans
   ```
5. Update `.gitignore` on main (idempotent)

### Step 2: Add migration logic for existing repos

When an existing repo has `aitasks/` and `aiplans/` on main:

1. Create temporary backup of task/plan data
2. Create the `aitask-data` orphan branch
3. Copy all task/plan files to the new branch
4. Commit on `aitask-data` branch
5. Switch back to main
6. `git rm -r aitasks/ aiplans/` from main
7. Create worktree and symlinks
8. Update `.gitignore`
9. Commit changes on main

### Step 3: Add auto-update for CLAUDE.md

When setup runs with data branch migration (or new bootstrap with separate branch):
- Check if `CLAUDE.md` exists
- If exists: append `## Git Operations on Task/Plan Files` section (skip if already present)
- If not: create minimal `CLAUDE.md` with the section
- Section content explains using `./ait git` for task/plan git operations

### Step 4: Interactive setup flow

Add a question to the `ait setup` flow asking:
- "Do you want to use a separate branch for task data? (Recommended for multi-PC workflows)"
- Options: "Yes, create aitask-data branch" / "No, keep tasks on main (legacy mode)"

### Step 5: Add `.gitignore` entries

When in branch mode, ensure `.gitignore` on main contains:
```
# Task data (lives on aitask-data branch, accessed via symlinks)
aitasks/
aiplans/
.aitask-data/
```

## Verification Steps

1. **Fresh setup:** Run `ait setup` in a new repo, verify branch/worktree/symlinks created
2. **Migration:** Start with legacy repo (tasks on main), run migration, verify:
   - All task/plan files present in `.aitask-data/`
   - Symlinks work: `ls aitasks/` shows task files
   - `git log --oneline aitask-data` shows the data
   - `git log --oneline main` no longer has task file commits
3. **CLAUDE.md:** Verify section appended/created correctly
4. **Idempotent:** Run setup twice — second run should detect existing setup and skip
5. **Shellcheck:** `shellcheck aiscripts/aitask_setup.sh`
