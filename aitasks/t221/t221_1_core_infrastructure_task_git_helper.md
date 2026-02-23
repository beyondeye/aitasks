---
priority: high
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: []
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-23 11:14
updated_at: 2026-02-23 11:16
---

## Context

This is the foundation child task for t221 (Move aitasks/aiplans to separate branch). The parent task implements a symlink + worktree architecture where task/plan data lives on an orphan `aitask-data` branch, accessed via a permanent worktree at `.aitask-data/` with symlinks `aitasks -> .aitask-data/aitasks` and `aiplans -> .aitask-data/aiplans`.

This child task creates the core infrastructure that all other child tasks depend on: the `task_git()` helper function and the `ait git` dispatcher command.

## Key Files to Modify

1. **`aiscripts/lib/task_utils.sh`** — Add worktree detection and git helper functions
2. **`ait`** — Add `git` subcommand to the dispatcher

## Reference Files for Patterns

- `aiscripts/lib/task_utils.sh` (lines 14-18) — Existing `TASK_DIR`/`PLAN_DIR` variable pattern
- `aiscripts/aitask_lock.sh` (lines 25-30) — Pattern for separate branch management with `TASK_DIR` usage
- `ait` (lines 102-122) — Existing dispatcher command routing pattern

## Implementation Plan

### Step 1: Add worktree detection and helpers to `task_utils.sh`

Add AFTER the existing directory variable defaults (line 18), BEFORE the platform detection section:

```bash
# --- Task Data Worktree Detection ---
# Detects if task data lives in a separate worktree (.aitask-data/)
# or on the current branch (legacy mode). All scripts use task_git()
# for git operations on task/plan files.

_AIT_DATA_WORKTREE=""

# Detect whether task data lives in a separate worktree
# Sets _AIT_DATA_WORKTREE to ".aitask-data" (branch mode) or "." (legacy mode)
_ait_detect_data_worktree() {
    if [[ -n "$_AIT_DATA_WORKTREE" ]]; then return; fi
    if [[ -d ".aitask-data/.git" || -f ".aitask-data/.git" ]]; then
        _AIT_DATA_WORKTREE=".aitask-data"
    else
        _AIT_DATA_WORKTREE="."
    fi
}

# Run git commands targeting the task data worktree
# In branch mode: git -C .aitask-data <args>
# In legacy mode: git <args>
task_git() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git -C "$_AIT_DATA_WORKTREE" "$@"
    else
        git "$@"
    fi
}

# Sync task data from remote (independent of code sync in branch mode)
task_sync() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git -C "$_AIT_DATA_WORKTREE" pull --ff-only --quiet 2>/dev/null || true
    else
        git pull --ff-only --quiet 2>/dev/null || true
    fi
}

# Push task data to remote (independent of code push in branch mode)
task_push() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git -C "$_AIT_DATA_WORKTREE" push --quiet 2>/dev/null || true
    else
        git push --quiet 2>/dev/null || true
    fi
}
```

### Step 2: Add `ait git` subcommand to dispatcher

In the `ait` dispatcher script, add a new case in the command routing (around line 102):

```bash
git)  shift; source "$SCRIPTS_DIR/lib/task_utils.sh"; task_git "$@" ;;
```

Also add to the `show_usage()` help text:
```
  git            Run git commands against task data (worktree-aware)
```

### Step 3: Verify backward compatibility

In legacy mode (no `.aitask-data/` directory), `task_git` and `ait git` must pass through to plain `git` with no behavior change.

## Verification Steps

1. **Legacy mode test:** Without `.aitask-data/`, verify `./ait git status` works like `git status`
2. **Function test:** Source `task_utils.sh`, verify `task_git status` works
3. **Detection test:** Create a mock `.aitask-data/.git` file, verify `_ait_detect_data_worktree` sets `_AIT_DATA_WORKTREE=".aitask-data"`
4. **Run existing tests:** `bash tests/test_*.sh` — all must pass unchanged
5. **Shellcheck:** `shellcheck aiscripts/lib/task_utils.sh`
