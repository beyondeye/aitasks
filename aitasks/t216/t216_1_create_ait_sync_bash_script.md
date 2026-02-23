---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitask_board]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-23 15:51
updated_at: 2026-02-23 18:43
---

## Context

Parent task t216 requires synchronizing the `ait board` TUI with remote task data when changes are made from other PCs. This child task creates the core `ait sync` bash script that handles bidirectional sync of task data (push local changes, pull remote changes) with conflict handling.

With task data on a separate `aitask-data` branch (implemented in t221), syncing is safe and independent from code changes. The script must work in both data-branch mode (`.aitask-data` worktree) and legacy mode (tasks on main branch).

## Key Files to Modify

- **Create:** `aiscripts/aitask_sync.sh` — the core sync script
- **Create:** `tests/test_sync.sh` — comprehensive test suite
- **Modify:** `ait` — add `sync` command to dispatcher (line ~116), help text (line ~33), skip-update-check list (line 99)

## Reference Files for Patterns

- `aiscripts/lib/task_utils.sh` (lines 29-68) — `_ait_detect_data_worktree()`, `task_git()`, `task_sync()`, `task_push()` — reuse these for mode detection and git operations
- `aiscripts/lib/terminal_compat.sh` — `die()`, `info()`, `warn()`, `success()` helpers for colored output
- `aiscripts/aitask_own.sh` — pattern for sync-only mode, structured output for LLM parsing (OWNED/LOCK_FAILED/etc)
- `aiscripts/aitask_init_data.sh` — pattern for structured output (INITIALIZED/LEGACY_MODE/etc)
- `tests/test_task_git.sh` — pattern for paired repo test setup (bare remote + local clone)

## Implementation Plan

### 1. Create `aiscripts/aitask_sync.sh`

**Boilerplate:** `#!/usr/bin/env bash`, `set -euo pipefail`, source `task_utils.sh` and `terminal_compat.sh`

**Arguments:** `--batch` (structured output, no interactive prompts), `--help` (usage info), default = interactive mode

**Batch output protocol** (single line on stdout):
- `SYNCED` — both push and pull completed
- `PUSHED` — local changes pushed, nothing to pull
- `PULLED` — remote changes pulled, nothing to push
- `NOTHING` — already up-to-date
- `CONFLICT:<file1>,<file2>,...` — merge conflicts detected (rebase aborted in batch mode)
- `NO_NETWORK` — fetch/push timed out or failed
- `NO_REMOTE` — no remote configured
- `ERROR:<message>` — unexpected error

**Core sync logic (in order):**

1. Detect mode via `_ait_detect_data_worktree` from `task_utils.sh`
2. Check for remote: `task_git remote get-url origin 2>/dev/null` — if fails, output `NO_REMOTE`
3. Auto-commit any uncommitted changes in `aitasks/` and `aiplans/`:
   - `task_git status --porcelain -- aitasks/ aiplans/` to check
   - If dirty: `task_git add aitasks/ aiplans/ && task_git commit -m "ait: Auto-commit task changes before sync"`
4. Count local-only commits: `task_git rev-list --count @{u}..HEAD 2>/dev/null` → set `local_has_commits`
5. Fetch with timeout (10s): `_git_with_timeout fetch origin` — on timeout/failure output `NO_NETWORK`
6. Count remote-only commits: `task_git rev-list --count HEAD..@{u} 2>/dev/null` → set `remote_has_commits`
7. If remote has changes: `task_git pull --rebase`
   - On conflict in **batch mode**: `task_git rebase --abort`, extract files via `task_git diff --name-only --diff-filter=U`, output `CONFLICT:<comma-separated-files>`
   - On conflict in **interactive mode**: show conflicted files, open `$EDITOR` for each, `task_git add`, `task_git rebase --continue`
8. If local has commits: `_git_with_timeout push` — retry once if rejected (remote advanced during our rebase)
9. Determine and output result: NOTHING, PUSHED, PULLED, or SYNCED based on what happened

**Portable timeout wrapper `_git_with_timeout()`:**
```bash
_git_with_timeout() {
    if command -v timeout &>/dev/null; then
        timeout "$NETWORK_TIMEOUT" task_git "$@"
    else
        # macOS fallback: background process with watchdog
        task_git "$@" &
        local pid=$!
        local i=0
        while kill -0 "$pid" 2>/dev/null && [[ $i -lt $NETWORK_TIMEOUT ]]; do
            sleep 1
            i=$((i + 1))
        done
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null || true
            return 124
        fi
        wait "$pid"
    fi
}
```

**Interactive mode extras:**
- Colored progress messages: `info "Fetching from remote..."`, `success "Sync complete"`, etc.
- Conflict resolution: show file list, open `$EDITOR` (default: `nano`) per file, mark resolved, continue rebase
- Summary at end: "Pushed N commits, pulled M commits"

### 2. Add to `ait` dispatcher

In `ait` file:
- Line ~99 (skip-update-check): add `sync` to the case pattern
- Line ~116 (command routing): add `sync)  shift; exec "$SCRIPTS_DIR/aitask_sync.sh" "$@" ;;`
- Line ~33 (help text): add `  sync           Sync task data with remote (push/pull)`

### 3. Create `tests/test_sync.sh`

Following `test_task_git.sh` pattern with paired repos (bare remote + local clone + second clone for "other PC"):

**Test cases:**
1. NOTHING — clean repo, no changes anywhere
2. PUSHED — local uncommitted changes get auto-committed and pushed
3. PULLED — remote-only changes (pushed from second clone) get pulled
4. SYNCED — both local and remote changes, no conflict
5. CONFLICT (batch) — conflicting edits to same file, verify rebase aborted and files reported
6. NO_REMOTE — repo with no remote
7. Legacy mode — verify sync works without `.aitask-data` worktree
8. Auto-commit — verify uncommitted changes are committed before sync
9. Push retry — verify push retries after rebase when remote advanced

## Verification Steps

1. `shellcheck aiscripts/aitask_sync.sh` — lint
2. `bash tests/test_sync.sh` — run all test cases
3. Manual test: `./ait sync --batch` in this repo — should output NOTHING or SYNCED
4. Manual test: `./ait sync` (interactive) — should show progress messages
5. Verify `./ait sync --help` shows usage
