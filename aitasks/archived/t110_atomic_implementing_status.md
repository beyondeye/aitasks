---
priority: high
effort: medium
depends: [112]
issue_type: feature
status: Done
labels: [aitasks, bash]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-13 02:35
updated_at: 2026-02-13 11:49
completed_at: 2026-02-13 11:49
---

## Problem

When `aitask-pick` assigns a task, it sets the task's `status` field from `Ready` to `Implementing`, then commits and pushes. This is meant to signal to other users/agents that the task is being worked on. However, this has the same race condition as the old task ID allocation: if two PCs pick the same task simultaneously, both may set it to `Implementing` before either push succeeds. The current mechanism relies on a soft lock (git push of the status change) which has a race window.

## Proposed Solution

Use a mechanism similar to the atomic task ID counter (`aitask_claim_id.sh` / `aitask-ids` branch) but for task locking:

### Separate Git Branch for Locks

Use a separate orphan branch (e.g., `aitask-locks`) on the remote to store lock state. This branch is independent from the source code branches and the `aitask-ids` counter branch.

### Per-Task Lock Files (Preferred over Single File)

Instead of a single file listing all locked task IDs, use **individual lock files** per task:
- Filename: `t<taskid>_lock.yaml` (e.g., `t109_lock.yaml`)
- Each lock file contains YAML frontmatter with lock metadata:
  ```yaml
  task_id: 109
  locked_by: user@example.com
  locked_at: 2026-02-13 14:30
  hostname: my-pc
  ```

**Rationale for per-file locks:** A single shared file would create contention — every lock/unlock modifies the same file, causing frequent push conflicts. Per-file locks are independent, so two PCs locking *different* tasks never conflict. The only conflict is when two PCs try to lock the *same* task, which is exactly the race we want to detect and reject.

### Atomic Lock Acquisition

Locking a task uses the same git plumbing approach as `aitask_claim_id.sh`:
1. `git fetch origin aitask-locks`
2. Check if `t<taskid>_lock.yaml` already exists in the branch tree
   - If it exists → task is already locked, abort with clear message ("Task t<N> is already being worked on by <email> since <date>")
3. Create new blob (lock metadata), build new tree (add the lock file), create commit
4. `git push origin <commit>:refs/heads/aitask-locks`
5. If push fails (race) → another PC locked it first, retry fetch and check

### Atomic Lock Release

Unlocking removes the lock file from the branch:
1. `git fetch origin aitask-locks`
2. Verify the lock file exists (idempotent: if already gone, succeed silently)
3. Build new tree without the lock file, create commit
4. `git push origin <commit>:refs/heads/aitask-locks`
5. Retry on push failure (race)

### Integration with `aitask-pick` Workflow

**Step 0c (existing git pull):** Also fetch `aitask-locks` to get current lock state.

**Step 2 (task selection):** Before showing tasks, read the lock branch and filter out or mark locked tasks. The `aitask_ls.sh` script (or a new helper) should check lock state to show accurate "Implementing" status.

**Step 4 (assign task):** Instead of just writing `status: Implementing` to the task file and pushing:
1. First, atomically acquire the lock on `aitask-locks` branch
2. If lock acquired → proceed to update local task file status
3. If lock failed → inform user the task was just claimed by someone else, return to task selection

**Step 9 (post-implementation / archival):** Release the lock atomically when archiving the task.

**Abort handling:** Release the lock when reverting task status.

### Stale Lock Cleanup

Add a cleanup routine that runs at the beginning of `aitask-pick`:
1. Fetch `aitask-locks` branch
2. For each lock file `t<id>_lock.yaml`:
   - Check if the corresponding task is archived (exists in `aitasks/archived/`)
   - If archived → the lock is stale, atomically remove it
3. Optionally: warn about locks older than N days (configurable) that might indicate abandoned work

This could be a function in `aitask_claim_id.sh` (e.g., `--cleanup-locks`) or a separate internal script.

### Script Design

Create `aiscripts/aitask_lock.sh` (internal, not exposed via `ait` dispatcher) with modes:
- `--lock <task_id> --email <email>`: Acquire lock atomically
- `--unlock <task_id>`: Release lock atomically
- `--check <task_id>`: Check if task is locked (exit 0 if locked, 1 if free)
- `--list`: List all currently locked tasks
- `--cleanup`: Remove stale locks for archived tasks
- `--init`: Initialize the `aitask-locks` branch (called from `ait setup`)

### Changes Required

1. **New file:** `aiscripts/aitask_lock.sh` — atomic lock management
2. **Modify:** `aiscripts/aitask_setup.sh` — add `setup_lock_branch()` to initialize `aitask-locks`
3. **Modify:** `.claude/skills/aitask-pick/SKILL.md` — integrate lock acquire/release into workflow
4. **Modify:** `aiscripts/aitask_ls.sh` — optionally check lock state for accurate status display
5. **New file:** `tests/test_task_lock.sh` — comprehensive tests (similar to `tests/test_claim_id.sh`)

### Open Questions for Planning Phase

- Should `aitask_ls.sh` always check the lock branch (requires network) or only when explicitly requested (e.g., `--check-locks` flag)?
- Should the local task file `status: Implementing` still be updated as a secondary signal, or should lock state completely replace it?
- Should locks have a TTL (time-to-live) for automatic expiry of abandoned locks?
- Should the lock branch be the same as `aitask-ids` (reuse the branch) or separate? Separate is cleaner but adds another branch.

## Reference Files

- aiscripts/aitask_claim_id.sh (pattern to follow for atomic git operations)
- aiscripts/aitask_create.sh (finalize_draft shows the atomic claim + fallback pattern)
- .claude/skills/aitask-pick/SKILL.md (Steps 0c, 4, 9, and Abort Handling need changes)
- aiscripts/aitask_setup.sh (add lock branch initialization)
- tests/test_claim_id.sh (test pattern to follow)
- aiplans/archived/p108_force_git_pull_at_start_of_task_create.md (design decisions from t108)
