---
Task: t305_aitaskcreate_not_working_without_git_remote.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Fix aitask-create failing without git remote (t305)

## Context

When using aitasks in a git repo without a configured remote (`origin`), multiple scripts fail hard because they use `require_remote()` which calls `die`. The primary failure is in `aitask_claim_id.sh` (task ID claiming), but `aitask_lock.sh` (task locking) also has the same issue — and it's called during the task-pick workflow via `aitask_pick_own.sh`.

**Key insight:** If there's no git remote, there's no multi-user/multi-PC collaboration possible. Both the atomic ID counter and the locking system exist to prevent conflicts between multiple users. Without a remote, these mechanisms serve no purpose and should gracefully degrade to no-ops/local mode.

**Affected scripts and their `require_remote()` calls:**
- `aitask_claim_id.sh`: `claim_next_id()` (line 121), `peek_counter()` (line 187), `init_counter_branch()` (line 83)
- `aitask_lock.sh`: `lock_task()` (92), `unlock_task()` (174), `check_lock()` (228), `list_locks()` (250), `cleanup_locks()` (285), `init_lock_branch()` (62)
- `aitask_create.sh`: calls `aitask_claim_id.sh --claim` from two paths (lines 518, 1271)
- `aitask_pick_own.sh`: calls `aitask_lock.sh` via `acquire_lock()` → exit 10 maps to `LOCK_INFRA_MISSING` → hard failure

**Already handling no-remote gracefully (no changes needed):**
- `aitask_sync.sh`: outputs `NO_REMOTE` and exits 0 (line 148)
- `task_sync()`/`task_push()` in `task_utils.sh`: `|| true` (fail silently)
- `aitask_archive.sh`: calls `aitask_lock.sh --unlock ... 2>/dev/null || true`
- `aitask_setup.sh`: checks for remote before init (lines 716-717, 758-759)

## Changes

### 1. `aiscripts/aitask_claim_id.sh` — Local branch counter with auto-upgrade

- Add `has_remote()` helper (non-fatal check, returns true/false) near existing `require_remote()`
- Add local branch helpers: `has_local_branch()`, `init_local_branch()`, `claim_local()`, `try_push_local_to_remote()`
- Modify `claim_next_id()`: if no remote, use local `aitask-ids` branch (auto-created on first claim with `scan_max_task_id() + ID_BUFFER`). If remote exists but remote branch doesn't, auto-push local branch to remote.
- Modify `peek_counter()`: if no remote, read from local branch (or show estimate if no branch yet)
- Keep `init_counter_branch()` strict (`require_remote`) — init is inherently a remote operation
- After remote CAS success, sync local branch with `git update-ref`
- Update `show_help()` to document the local branch + auto-upgrade behavior

### 2. `aiscripts/aitask_lock.sh` — Graceful no-op when no remote

- Add `has_remote()` helper (same pattern as claim_id)
- Modify `lock_task()`: if no remote, emit debug message and return 0 (success no-op)
- Modify `unlock_task()`: if no remote, return 0 (no-op)
- Modify `check_lock()`: if no remote, return 1 (not locked)
- Modify `list_locks()`: if no remote, print "No locks (no remote configured)" and return 0
- Modify `cleanup_locks()`: if no remote, return 0 (no-op)
- Keep `init_lock_branch()` strict (`require_remote`)

### 3. `aiscripts/aitask_create.sh` — Simplify fallback in `finalize_draft()`

Lines 523-542: Simplify messaging now that the no-remote case is handled upstream.

### 4. `tests/test_claim_id.sh` — Update and add tests

### 5. `tests/test_task_lock.sh` — Add no-remote tests

## Verification

1. `bash tests/test_claim_id.sh` — all tests pass
2. `bash tests/test_task_lock.sh` — all tests pass
3. `shellcheck aiscripts/aitask_claim_id.sh aiscripts/aitask_lock.sh`

## Final Implementation Notes

- **Actual work done:** Implemented local git branch counter for `aitask_claim_id.sh` with auto-upgrade to remote when a remote is later added. Made `aitask_lock.sh` gracefully no-op when no remote (locks serve no purpose without multi-user access). Simplified `aitask_create.sh` fallback messaging.
- **Deviations from plan:** Initial plan used simple local file scan (`scan_max_task_id() + 1`). After discussion, upgraded to local git branch counter (`aitask-ids` branch maintained locally via `git update-ref`). This provides a proper monotonic counter with auto-upgrade to remote-based CAS when a remote becomes available. Locks kept as no-ops since they're meaningless without a remote.
- **Issues encountered:** None — all tests passed on first run after each iteration.
- **Key decisions:** (1) Local counter uses same `ID_BUFFER=10` as remote init, not `+1` like the old scan fallback. (2) After successful remote CAS push, local branch is synced via `git update-ref` to stay in sync. (3) Auto-upgrade: when remote exists but `aitask-ids` branch is missing, local branch is pushed to remote transparently.
