---
Task: t436_task_data_push_issue.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Robust `./ait git push` with automatic rebase retry (t436)

## Context

When multiple users/PCs push to the `aitask-data` branch concurrently, `./ait git push` almost always fails on the first attempt because the remote has advanced. Claude Code recovers by pulling and retrying, but this produces visual noise in the run log. Since concurrent pushes are the norm (not the exception), this should be handled gracefully at the script level.

Per t437: the issue is not isolated to `push`. The current `task_sync()` uses `pull --ff-only` which fails silently when local has diverged from remote, leaving subsequent `add`/`commit`/`push` operating on a stale branch. The fix must address the entire sync-commit-push pipeline.

## Approach

Three changes in `.aitask-scripts/lib/task_utils.sh`, plus a dispatcher intercept in `ait`:

1. **`task_sync()`** — Switch from `pull --ff-only` to `pull --rebase` so sync succeeds even when local has unpushed commits (from a previous failed push cycle)
2. **`task_push()`** — Add pull-rebase-then-push retry loop (max 3 attempts)
3. **`ait` dispatcher** — Intercept `./ait git push` to route through the robust `task_push()`

## Implementation Steps

### Step 1: Fix `task_sync()` in `.aitask-scripts/lib/task_utils.sh`

Replace `--ff-only` with `--rebase` (lines 51-58). When there are no local unpushed commits, `--rebase` behaves identically to `--ff-only`. When there ARE local unpushed commits (from a previous failed push), `--rebase` replays them on top of the remote changes instead of silently failing.

```bash
task_sync() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git -C "$_AIT_DATA_WORKTREE" pull --rebase --quiet 2>/dev/null || true
    else
        git pull --rebase --quiet 2>/dev/null || true
    fi
}
```

### Step 2: Enhance `task_push()` in `.aitask-scripts/lib/task_utils.sh`

Replace the current `task_push()` (lines 61-68) with a retry-with-rebase version, plus two internal helpers:

```bash
# Push task data to remote with automatic pull-rebase on conflict.
# Retries up to 3 times. Failures are non-fatal (best-effort push).
task_push() {
    local max_attempts=3
    local attempt
    for (( attempt=1; attempt<=max_attempts; attempt++ )); do
        if _task_push_once 2>/dev/null; then
            return 0
        fi
        # Pull with rebase to incorporate remote changes, then retry
        if [[ $attempt -lt $max_attempts ]]; then
            _task_pull_rebase 2>/dev/null || true
        fi
    done
    # All attempts exhausted — best-effort, don't fail the workflow
    return 0
}

# Internal: single push attempt
_task_push_once() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git -C "$_AIT_DATA_WORKTREE" push --quiet
    else
        git push --quiet
    fi
}

# Internal: pull with rebase to catch up with remote
_task_pull_rebase() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git -C "$_AIT_DATA_WORKTREE" pull --rebase --quiet
    else
        git pull --rebase --quiet
    fi
}
```

### Step 3: Intercept `push` in the `ait` dispatcher (line 230)

Change line 230 of `ait`:
```bash
git)          shift; source "$SCRIPTS_DIR/lib/task_utils.sh"; task_git "$@" ;;
```

To:
```bash
git)          shift; source "$SCRIPTS_DIR/lib/task_utils.sh"
              if [[ "${1:-}" == "push" ]]; then
                  task_push
              else
                  task_git "$@"
              fi
              ;;
```

This way, `./ait git push` from SKILL.md uses the retry logic, while all other `./ait git <cmd>` operations pass through unchanged.

### Step 4: Verify no other patterns are missed

- `task_push()` called from `aitask_pick_own.sh` line 248 — gets new retry logic automatically
- `task_sync()` called from `aitask_pick_own.sh` `sync_remote()` — gets `--rebase` automatically
- `./ait git push` in 5 SKILL.md files — goes through the new dispatcher intercept
- No SKILL.md changes needed — the fix is entirely in the bash layer

### Step 5: Add automated tests — `tests/test_task_push.sh`

Create a new test file following the project's test conventions (self-contained, `assert_eq`/`assert_contains` helpers, PASS/FAIL summary). Tests use bare git repos as "remotes" to simulate real push/conflict scenarios.

**Test setup helpers:**
- `setup_remote_and_clone()` — Creates a bare "remote" repo and a "local" clone with git config. Returns paths.
- `source_task_utils()` — Sources `task_utils.sh` functions into the test environment.
- `advance_remote()` — Creates a second clone, makes a non-conflicting commit, pushes to remote. Simulates another user's push.

**Tests:**

1. **`task_push` succeeds on clean push (legacy mode)** — Local has a commit ahead of remote. `_AIT_DATA_WORKTREE="."`. `task_push` succeeds on first attempt, returns 0. Verify remote has the commit.

2. **`task_push` succeeds on clean push (branch mode)** — Same but with `_AIT_DATA_WORKTREE` pointing to a `.aitask-data` worktree clone. Verifies `git -C` path works.

3. **`task_push` auto-rebases on conflict (legacy mode)** — Local commits, then `advance_remote()` pushes a non-conflicting commit. `task_push` should fail first push, pull-rebase, then succeed on retry. Verify remote has both commits.

4. **`task_push` auto-rebases on conflict (branch mode)** — Same conflict scenario using `.aitask-data` worktree.

5. **`task_push` returns 0 even when all retries fail** — Point origin to a nonexistent path. `task_push` should exhaust retries silently and return 0 (best-effort).

6. **`task_sync` uses rebase (legacy mode)** — Local has an unpushed commit, remote has advanced. `task_sync` should rebase local on top of remote (not fail like `--ff-only` would). Verify local has both commits and local commit is on top.

7. **`task_sync` uses rebase (branch mode)** — Same scenario with `.aitask-data` worktree.

8. **`ait git push` dispatcher intercept** — Run `./ait git push` against the test remote after `advance_remote()` conflict. Verify it succeeds (proving it uses `task_push` with retry, not raw `git push`).

9. **`ait git <other>` passes through unchanged** — Run `./ait git status` and `./ait git log` — verify they work normally.

## Files Modified

1. `.aitask-scripts/lib/task_utils.sh` — Fix `task_sync()` (`--rebase`), replace `task_push()`, add `_task_push_once()` and `_task_pull_rebase()` helpers
2. `ait` — Intercept `push` subcommand in `git)` case
3. `tests/test_task_push.sh` — New automated test file (9 tests)

## Verification

1. Run `bash tests/test_task_push.sh` — all 9 tests (18 assertions) pass
2. Run `shellcheck .aitask-scripts/lib/task_utils.sh` — passes (only pre-existing SC1091/SC2086 infos)
3. Run `shellcheck ait` — passes (only pre-existing SC1091 info)

## Final Implementation Notes
- **Actual work done:** Implemented all 3 planned changes (task_sync rebase, task_push retry, dispatcher intercept) plus 9 automated tests covering both legacy and branch modes, conflict resolution, failure tolerance, and dispatcher routing
- **Deviations from plan:** None — implemented exactly as planned
- **Issues encountered:** Initial test implementation used subshells which don't propagate PASS/FAIL counters; fixed by using pushd/popd instead
- **Key decisions:** Tests create bare git repos as "remotes" and use `advance_remote()` to simulate concurrent pushers, providing realistic conflict scenarios without needing network access
