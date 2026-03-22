---
Task: t429_investigate_parallel_task_creation_error.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Fix Parallel Child Task Creation Race Condition

## Context

When the planning workflow creates multiple child tasks by launching parallel
`aitask_create.sh --batch --parent N --commit` calls, race conditions cause:

1. **Duplicate child numbers** — `get_next_child_number()` (lines 161-194 of
   `aitask_create.sh`) scans the filesystem for existing children but has no
   locking, so two concurrent calls can both get `child_num=1`.
2. **Parent file corruption** — `update_parent_children_to_implement()` reads
   and writes the parent file concurrently, causing lost updates to
   `children_to_implement`.
3. **Git index.lock errors** — concurrent `task_git add`/`task_git commit`
   calls conflict on git's index lock.

Parent task IDs use an atomic git-based counter (`aitask_claim_id.sh`), but
child IDs rely on local filesystem scan, which is safe for single-process use
but breaks under concurrent invocation on the same machine.

## Implementation

### Step 1: Add `mkdir`-based lock functions to `aitask_create.sh`

Add two functions after the existing `get_next_child_number()` (after line 194):

```bash
# Acquire per-parent lock for child task creation (prevents parallel races)
acquire_child_lock() {
    local parent_num="$1"
    local lock_dir="/tmp/aitask_child_lock_${parent_num}"
    local max_retries=20
    local retry=0

    while ! mkdir "$lock_dir" 2>/dev/null; do
        retry=$((retry + 1))
        if [[ $retry -ge $max_retries ]]; then
            die "Failed to acquire child creation lock for parent $parent_num after $max_retries attempts"
        fi
        # Check for stale lock (older than 120 seconds)
        if [[ -d "$lock_dir" ]]; then
            local lock_age
            lock_age=$(( $(date +%s) - $(stat -c %Y "$lock_dir" 2>/dev/null || stat -f %m "$lock_dir" 2>/dev/null || echo "0") ))
            if [[ "$lock_age" -gt 120 ]]; then
                warn "Removing stale child lock for parent $parent_num (age: ${lock_age}s)"
                rmdir "$lock_dir" 2>/dev/null || true
                continue
            fi
        fi
        # Backoff: 0.5s per retry
        sleep 0.5
    done
}

release_child_lock() {
    local parent_num="$1"
    local lock_dir="/tmp/aitask_child_lock_${parent_num}"
    rmdir "$lock_dir" 2>/dev/null || true
}
```

Notes:
- `mkdir` is atomic on POSIX — exactly one process succeeds
- `stat -c %Y` is GNU (Linux), `stat -f %m` is BSD (macOS) — try both
- 120s stale timeout covers slow networks/git operations
- 20 retries × 0.5s = 10s max wait, sufficient for serial child creation

### Step 2: Wrap `--batch --parent N --commit` path in lock

In the batch mode child creation path (lines 1231-1263), wrap the critical
section from `get_next_child_number` through `task_git commit`:

```bash
if [[ -n "$BATCH_PARENT" ]]; then
    # Child task: create directly (parent ID is already unique)
    acquire_child_lock "$BATCH_PARENT"
    trap 'release_child_lock "$BATCH_PARENT"' EXIT

    local parent_file
    parent_file=$(get_parent_task_file "$BATCH_PARENT")
    [[ -z "$parent_file" || ! -f "$parent_file" ]] && { release_child_lock "$BATCH_PARENT"; die "Parent task t$BATCH_PARENT not found"; }

    local child_num
    child_num=$(get_next_child_number "$BATCH_PARENT")
    # ... rest of child creation ...
    task_git commit -m "ait: Add child task ${task_id}: ${humanized_name}"

    release_child_lock "$BATCH_PARENT"
    trap - EXIT
```

### Step 3: Wrap `finalize_draft()` child path in lock

In `finalize_draft()` (lines 482-512), wrap the child finalization section:

```bash
if [[ -n "$parent_num" ]]; then
    acquire_child_lock "$parent_num"
    trap 'release_child_lock "$parent_num"' EXIT

    local child_num
    child_num=$(get_next_child_number "$parent_num")
    # ... rest of child finalization ...
    task_git commit -m "ait: Add child task ${task_id}: ${humanized_name}"

    release_child_lock "$parent_num"
    trap - EXIT
```

### Step 4: Update comment at lines 137-142

Update the design note to reflect the lock:

```bash
# Child task IDs use get_next_child_number() (local scan + mkdir-based lock).
# The lock serializes concurrent child creation for the same parent, which can
# happen when the planning workflow creates multiple children in parallel.
```

### Step 5: Add parallel child creation test

Create `tests/test_parallel_child_create.sh` that:
1. Sets up a test repo with a parent task
2. Launches 5 parallel `aitask_create.sh --batch --parent N --commit` calls
3. Verifies all children get unique sequential numbers (1-5)
4. Verifies parent's `children_to_implement` contains all 5 children
5. Verifies no git errors occurred

### Step 6: Post-Implementation

Follow Step 9 from the task workflow for cleanup, archival, and push.

## Key Files

- `.aitask-scripts/aitask_create.sh` — Main file to modify (lines 161-194, 1231-1263, 482-512, 137-142)
- `tests/test_parallel_child_create.sh` — New test file
- `tests/test_claim_id.sh` — Reference for test patterns

## Verification

1. Run existing tests: `bash tests/test_claim_id.sh` (ensure no regression)
2. Run new test: `bash tests/test_parallel_child_create.sh`
3. Run shellcheck: `shellcheck .aitask-scripts/aitask_create.sh`
4. Manual test: create a parent task, then run 3 parallel child create commands

## Final Implementation Notes
- **Actual work done:** Added `acquire_child_lock()`/`release_child_lock()` functions using POSIX `mkdir` atomicity. Wrapped both child creation paths (batch `--commit` and `finalize_draft()`) in lock/unlock. Updated design comment. Created 4-test suite (21 assertions) covering sequential, parallel (5 concurrent), stale lock cleanup, and staggered contention.
- **Deviations from plan:** None — implemented as planned.
- **Issues encountered:** None — all tests passed on first run.
- **Key decisions:** Used `mkdir`-based locking over `flock` for macOS portability. Used `stat -c %Y || stat -f %m` fallback for stale lock detection on both Linux and macOS. Lock covers the entire critical section including git commit to prevent index.lock conflicts.
