---
Task: t221_move_aitasks_and_aiplans_to_separate_branch.md
Branch: main (no worktree)
---

# Plan: Move aitasks/aiplans to Separate Git Branch (t221)

## Context

Currently `aitasks/` and `aiplans/` live on the `main` branch alongside code. This causes:
1. **Merge conflicts on multi-PC sync** — pulling task status changes can conflict with unrelated code changes
2. **Noisy commit history** — `ait:` administrative commits (task creation, status changes, archival) pollute the code log
3. **Coupled sync** — must push/pull all code just to sync task status

The goal is to move task/plan data to a separate branch so task sync is independent of code sync, while keeping the developer experience seamless.

## Architecture: Symlink + Worktree Approach

### Core Idea

1. Create an orphan branch `aitask-data` (like existing `aitask-locks` and `aitask-ids`)
2. Task/plan files live on this branch
3. A permanent worktree at `.aitask-data/` checks out this branch
4. **Symlinks** `aitasks -> .aitask-data/aitasks` and `aiplans -> .aitask-data/aiplans` make files accessible at the original paths
5. All file reads (scripts, skills, board) work unchanged via symlinks
6. Git operations for task data use `git -C .aitask-data` instead of plain `git`

### Why Symlinks?

- **Zero changes to path references** — all scripts, skills, and the Python board continue using `aitasks/` and `aiplans/` paths for file reads
- **Only git operations change** — scripts that commit/push task data need to target the data worktree
- Follows the existing pattern of `aitask-locks`/`aitask-ids` orphan branches

### Backward Compatibility

The system auto-detects which mode to use:
- If `.aitask-data/` worktree exists → **branch mode** (new)
- Otherwise → **legacy mode** (current behavior, everything on main)

All scripts work in both modes transparently via a `task_git()` helper function.

## Key Changes

### 1. New helper: `task_git()` in `task_utils.sh`

```bash
_AIT_DATA_WORKTREE=""
_ait_detect_data_worktree() {
    if [[ -n "$_AIT_DATA_WORKTREE" ]]; then return; fi
    if [[ -d ".aitask-data/.git" || -f ".aitask-data/.git" ]]; then
        _AIT_DATA_WORKTREE=".aitask-data"
    else
        _AIT_DATA_WORKTREE="."
    fi
}

task_git() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git -C "$_AIT_DATA_WORKTREE" "$@"
    else
        git "$@"
    fi
}

task_sync() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git -C "$_AIT_DATA_WORKTREE" pull --ff-only --quiet 2>/dev/null || true
    else
        git pull --ff-only --quiet 2>/dev/null || true
    fi
}
```

### 2. New `ait git` dispatcher command

Add a `git` subcommand to the `ait` dispatcher that routes through `task_git()`:

```bash
# In ait dispatcher:
git)  shift; source "$SCRIPTS_DIR/lib/task_utils.sh"; task_git "$@" ;;
```

**Why this is critical:**
- **Python board**: Can call `["./ait", "git", ...]` instead of `["git", ...]` for all task-related git operations
- **Claude Code ad-hoc usage**: When users ask Claude to commit task file changes outside of skills, CLAUDE.md instructs Claude to use `./ait git add/commit/push` instead of plain `git`. Since CLAUDE.md is always loaded, this works in ALL contexts (with or without aitask skills loaded)
- **Human CLI usage**: Developers can use `ait git status` to check task data status
- **Single source of detection logic**: Only `task_utils.sh` needs the worktree detection; everything else routes through `ait git` or `task_git()`

### 3. Scripts requiring git operation changes

Replace `git add aitasks/` / `git commit` / `git push` with `task_git` equivalents:

| Script | Git operations | Changes needed |
|--------|---------------|----------------|
| `aitask_own.sh` | add, commit, push, pull | `task_git`/`task_sync` |
| `aitask_archive.sh` | add, rm, commit | `task_git` |
| `aitask_create.sh` | add, commit | `task_git` |
| `aitask_update.sh` | add, commit | `task_git` |
| `aitask_zip_old.sh` | add, commit | `task_git` |
| `aitask_claim_id.sh` | (uses own branch) | No changes |
| `aitask_lock.sh` | (uses own branch) | No changes |

### 4. Python board git operations

The board has 4 git operation types that need worktree awareness:

| Operation | Current code | Change needed |
|-----------|-------------|---------------|
| **Status check** | `["git", "status", "--porcelain", "--", "aitasks/"]` | Use `ait git` or internal detection |
| **Commit tasks** | `["git", "add", filepath]` + `["git", "commit", "-m", msg]` | Route through `ait git` |
| **Delete tasks** | `["git", "rm", "-f", path]` + `["git", "commit", ...]` | Route through `ait git` |
| **Revert task** | `["git", "checkout", "--", filepath]` | Route through `ait git` |

Implementation: Add a `_task_git_cmd()` helper method that returns `["./ait", "git"]` if `.aitask-data/` exists, else `["git"]`. All 4 operations use this prefix.

### 5. Skills and Claude Code ad-hoc changes

**Skills**: Most delegate git ops to scripts (already handled). The main exception is the **Task Abort Procedure** in `task-workflow/SKILL.md` which does direct `git add aitasks/ && git commit`. Solution: either create `aitask_abort.sh` or update the skill to use `./ait git`.

**Non-user-invocable skill** `.claude/skills/ait-git/SKILL.md`: A safety net skill with `user-invocable: false` containing the same `ait git` instructions. This ensures Claude has the information even if CLAUDE.md is truncated or missing. The skill description should mention "git commands against aitasks aiplans directory" so it gets surfaced in relevant contexts. This skill ships with the framework via `install.sh` like all other Claude Code skills — NOT created by `ait setup`.

**CLAUDE.md update**: Add a section:
```markdown
## Git Operations on Task/Plan Files
When committing changes to files in `aitasks/` or `aiplans/`, use `./ait git`
instead of plain `git`. This ensures correct branch targeting when task data
lives on a separate branch.
- `./ait git add aitasks/t42_foo.md`
- `./ait git commit -m "ait: Update task t42"`
- `./ait git push`
In legacy mode (no separate branch), `ait git` passes through to plain `git`.
```

### 6. Setup/migration (`aitask_setup.sh`)

New `setup_data_branch()` function:
- Create `aitask-data` orphan branch
- Create worktree: `git worktree add .aitask-data aitask-data`
- Create symlinks: `aitasks -> .aitask-data/aitasks`, `aiplans -> .aitask-data/aiplans`
- Add to `.gitignore`: `.aitask-data/`, `aitasks/`, `aiplans/`

Migration from legacy mode:
- Move existing `aitasks/` and `aiplans/` content to the data branch
- `git rm -r aitasks/ aiplans/` from main
- Create symlinks
- Update `.gitignore`

**Auto-update CLAUDE.md**: When `ait setup` runs with data branch migration (or new project bootstrap with separate branch), it must:
- Check if `CLAUDE.md` exists in the project root
- If it exists: append/update a `## Git Operations on Task/Plan Files` section with `ait git` instructions (idempotent — skip if section already present)
- If it doesn't exist: create a minimal `CLAUDE.md` containing the `ait git` section
- The section content:
  ```markdown
  ## Git Operations on Task/Plan Files
  When committing changes to files in `aitasks/` or `aiplans/`, always use
  `./ait git` instead of plain `git`. This ensures correct branch targeting
  when task data lives on a separate branch.
  - `./ait git add aitasks/t42_foo.md`
  - `./ait git commit -m "ait: Update task t42"`
  - `./ait git push`
  In legacy mode (no separate branch), `./ait git` passes through to plain `git`.
  ```
- This ensures the instructions are always present regardless of whether aitask skills are loaded

### 7. `.gitignore` additions on main branch

```
# Task data (lives on aitask-data branch, accessed via symlinks)
aitasks/
aiplans/
.aitask-data/
```

## What Does NOT Change

- All `TASK_DIR`/`PLAN_DIR` path references for file reads (symlinks handle this)
- Skill file path references (still `aitasks/t<N>_*.md`)
- Python board file loading logic (follows symlinks)
- `aitask_lock.sh` / `aitask_claim_id.sh` (already use separate branches)
- Read-only scripts: `aitask_ls.sh`, `aitask_stats.sh`, `aitask_changelog.sh`, `aitask_issue_update.sh`
- `aireviewguides/` (stays on main, not task data)

## Complexity Assessment: HIGH → Break into child subtasks

### Proposed Child Tasks

**t221_1: Core infrastructure — task_git() helper, ait git command, auto-detection**
- Add `task_git()`, `task_sync()`, `_ait_detect_data_worktree()` to `task_utils.sh`
- Add `ait git` subcommand to `ait` dispatcher
- Backward compatible: falls through to plain `git` when no data worktree exists
- Files: `aiscripts/lib/task_utils.sh`, `ait`

**t221_2: Update write scripts to use task_git()**
- Refactor git operations in: `aitask_own.sh`, `aitask_archive.sh`, `aitask_create.sh`, `aitask_update.sh`, `aitask_zip_old.sh`
- Replace `git add aitasks/`, `git commit`, `git push` with `task_git` equivalents
- Depends on t221_1
- Files: 5 scripts in `aiscripts/`

**t221_3: Setup and migration**
- Add `setup_data_branch()` to `aitask_setup.sh`
- Create orphan branch, worktree, symlinks
- Migration logic: move existing data from main to data branch
- Update `.gitignore` on main
- Auto-update/create `CLAUDE.md` with `ait git` instructions (idempotent)
- Depends on t221_1

**t221_4: Update Python board**
- Add `_task_git_cmd()` helper for worktree-aware git commands
- Update all 4 git operations: status, commit, delete, revert
- Depends on t221_1

**t221_5: Update skills, CLAUDE.md, and website docs**
- Update `task-workflow/SKILL.md` abort procedure to use `./ait git` or create `aitask_abort.sh`
- Create non-user-invocable skill `.claude/skills/ait-git/SKILL.md` — loaded when running git commands against aitasks/aiplans, explains `ait git` usage and branch model
- Update CLAUDE.md with `ait git` instructions (manual update for the aitasks repo itself; `ait setup` handles it for other projects)
- Update website docs that reference git operations on task files (board/reference.md, etc.)
- Depends on t221_2

**t221_6: Testing and validation**
- Write test script for branch mode vs legacy mode
- End-to-end test: create data branch, symlinks, run full workflow
- Validate existing tests still pass
- Depends on t221_1 through t221_5

## Verification

- Run existing tests: `bash tests/test_*.sh` (must pass in legacy mode)
- Test branch mode: create data branch, verify symlinks, run full task workflow
- Test `ait git` from CLI, from board subprocess, from Claude Code context
- Test sync: simulate multi-PC scenario — clone, make task changes, sync independently
- Test migration: start with legacy repo, run `ait setup --migrate-data-branch`, verify all data preserved
- Run shellcheck: `shellcheck aiscripts/aitask_*.sh`
