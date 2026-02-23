---
Task: t216_1_create_ait_sync_bash_script.md
Parent Task: aitasks/t216_ait_board_out_of_sync_if_changes_from_other_pc.md
Sibling Tasks: aitasks/t216/t216_2_*.md, aitasks/t216/t216_3_*.md, aitasks/t216/t216_4_*.md
---

# Implementation Plan: t216_1 — Create `ait sync` bash script

## Overview

Create `aiscripts/aitask_sync.sh` — a bidirectional sync script for task data that supports both batch (structured output) and interactive (colored progress + conflict resolution) modes. Add to the `ait` dispatcher and create comprehensive tests.

## Step 1: Create `aiscripts/aitask_sync.sh`

### Structure

```
#!/usr/bin/env bash
set -euo pipefail

# Source shared libraries
# Argument parsing (--batch, --help)
# _git_with_timeout() — portable timeout wrapper
# check_remote() — verify remote exists
# auto_commit() — commit uncommitted task changes
# do_fetch() — fetch with timeout
# do_pull_rebase() — pull --rebase with conflict handling
# do_push() — push with timeout + retry
# main() — orchestrate the sync flow
# Output result
```

### Batch output protocol (single line on stdout)

| Output | Meaning |
|--------|---------|
| `NOTHING` | Already up-to-date |
| `PUSHED` | Local changes pushed, nothing to pull |
| `PULLED` | Remote changes pulled, nothing to push |
| `SYNCED` | Both push and pull completed |
| `CONFLICT:<f1>,<f2>` | Merge conflicts (rebase aborted) |
| `NO_NETWORK` | Timeout or network failure |
| `NO_REMOTE` | No remote configured |
| `ERROR:<message>` | Unexpected error |

### Core logic flow

1. `_ait_detect_data_worktree` → mode detection
2. `task_git remote get-url origin` → `NO_REMOTE` if fails
3. Auto-commit: `task_git status --porcelain -- aitasks/ aiplans/` → if dirty, add + commit
4. Count local ahead: `task_git rev-list --count @{u}..HEAD`
5. Fetch with timeout (10s) → `NO_NETWORK` on failure/timeout
6. Count remote ahead: `task_git rev-list --count HEAD..@{u}`
7. Pull rebase if remote has commits → handle conflicts
8. Push if local has commits → retry once on rejection
9. Output result

### Portable timeout wrapper

```bash
NETWORK_TIMEOUT=10

_git_with_timeout() {
    if command -v timeout &>/dev/null; then
        timeout "$NETWORK_TIMEOUT" task_git "$@"
    else
        task_git "$@" &
        local pid=$!
        local i=0
        while kill -0 "$pid" 2>/dev/null && [[ $i -lt $NETWORK_TIMEOUT ]]; do
            sleep 1
            i=$((i + 1))
        done
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
            return 124
        fi
        wait "$pid"
    fi
}
```

### Conflict handling

**Batch mode:**
```bash
if ! task_git rebase --continue 2>/dev/null; then
    conflicted=$(task_git diff --name-only --diff-filter=U | tr '\n' ',' | sed 's/,$//')
    task_git rebase --abort
    echo "CONFLICT:${conflicted}"
    exit 0
fi
```

**Interactive mode:**
- List conflicted files with `info` helper
- Open each in `$EDITOR` (default: `nano`)
- After editing: `task_git add <file>`
- `task_git rebase --continue`
- If user aborts editor: offer to abort rebase

### Interactive mode messages

Use `info()`, `success()`, `warn()` from `terminal_compat.sh`:
- "Checking for uncommitted changes..."
- "Auto-committing N modified task files..."
- "Fetching from remote..."
- "Pulling N new commits (rebase)..."
- "Pushing N commits to remote..."
- "Sync complete: pushed N, pulled M"

## Step 2: Add to `ait` dispatcher

In `/home/ddt/Work/aitasks/ait`:

1. **Line 99** — add `sync` to skip-update-check:
   ```bash
   help|--help|-h|--version|-v|install|setup|git|sync) ;;
   ```

2. **Line ~116** — add command routing:
   ```bash
   sync)         shift; exec "$SCRIPTS_DIR/aitask_sync.sh" "$@" ;;
   ```

3. **Line ~33** — add to help text:
   ```
     sync           Sync task data with remote (push/pull)
   ```

## Step 3: Create `tests/test_sync.sh`

Pattern: `test_task_git.sh` (paired repo setup).

### Test infrastructure

```bash
setup_sync_repos() {
    # Create bare remote
    # Clone to local1 (main test)
    # Clone to local2 (simulates other PC)
    # Set up aitasks/ directory in both
    # For data-branch mode: create aitask-data branch + worktree
}
```

### Test cases

1. **NOTHING** — clean repo, no changes
2. **PUSHED** — local uncommitted changes → auto-commit + push
3. **PULLED** — remote changes (from local2) → pull
4. **SYNCED** — both local and remote changes, no conflict
5. **CONFLICT (batch)** — both modify same file → CONFLICT output, rebase aborted
6. **NO_REMOTE** — repo with no remote → NO_REMOTE output
7. **Legacy mode** — no .aitask-data → sync on main branch
8. **Auto-commit** — verify uncommitted changes committed before sync
9. **Push after pull** — local + remote changes → pull rebase → push

## Verification

- [ ] `shellcheck aiscripts/aitask_sync.sh`
- [ ] `bash tests/test_sync.sh` — all PASS
- [ ] `./ait sync --help` shows usage
- [ ] `./ait sync --batch` in real repo → expected output
- [ ] `./ait sync` interactive → progress messages

## Post-Implementation (Step 9)

Archive t216_1, update parent children_to_implement.
