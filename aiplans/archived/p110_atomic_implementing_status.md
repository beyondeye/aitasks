---
Task: t110_atomic_implementing_status.md
Branch: main
Base branch: main
---

# Plan: t110 — Atomic Task Locking

## Context

When `aitask-pick` assigns a task, it sets status to "Implementing" and pushes. Two users on different PCs can pick the same task simultaneously — both see it as "Ready", both set "Implementing", and one push overwrites the other. The fix: use a separate git orphan branch (`aitask-locks`) with per-task lock files, using the same atomic git plumbing pattern as `aitask_claim_id.sh`.

## Files to Create/Modify

| # | File | Action |
|---|------|--------|
| 1 | `aiscripts/aitask_lock.sh` | **CREATE** — Core atomic lock script |
| 2 | `tests/test_task_lock.sh` | **CREATE** — Comprehensive test suite |
| 3 | `aiscripts/aitask_setup.sh` | **MODIFY** — Add `setup_lock_branch()` |
| 4 | `.claude/skills/aitask-pick/SKILL.md` | **MODIFY** — Integrate lock/unlock at Steps 0c, 4, 9, Task Abort Procedure |
| 5 | `aitasks/metadata/claude_settings.seed.json` | **MODIFY** — Add permission entry |

## Step 1: Create `aiscripts/aitask_lock.sh`

Mirror structure of `aiscripts/aitask_claim_id.sh`. Same conventions: `set -euo pipefail`, source `lib/terminal_compat.sh`, `BRANCH="aitask-locks"`, `MAX_RETRIES=5`, `DEBUG=false`.

### Modes

- **`--init`**: Initialize `aitask-locks` orphan branch with empty tree
- **`--lock <task_id> --email <email>`**: Atomic lock acquisition with retry (idempotent for same email)
- **`--unlock <task_id>`**: Atomic lock release (idempotent)
- **`--check <task_id>`**: Exit 0 = locked (prints YAML), Exit 1 = free
- **`--list`**: List all active locks
- **`--cleanup`**: Remove stale locks for archived tasks

## Step 2: Create `tests/test_task_lock.sh`

14 tests (21 assertions) including race simulation with parallel background processes.

## Step 3: Modify `aiscripts/aitask_setup.sh`

Add `setup_lock_branch()` function after `setup_id_counter()`, call in `main()`.

## Step 4: Modify `.claude/skills/aitask-pick/SKILL.md`

- Step 0c: stale lock cleanup
- Step 4: lock acquisition before status update
- Step 9: lock release via Lock Release Procedure
- Task Abort Procedure: lock release before status revert

## Step 5: Modify `aitasks/metadata/claude_settings.seed.json`

Add `Bash(./aiscripts/aitask_lock.sh:*)` permission.

## Final Implementation Notes
- **Actual work done:** Implemented all 5 files as planned. Created `aitask_lock.sh` (280 lines) with 6 modes, test suite with 14 tests (21 assertions all passing), setup integration, SKILL.md workflow integration, and permission entry.
- **Deviations from plan:**
  - Fixed `grep -v` piping bug: when removing the last entry from a tree, `grep -v` exits 1 with `pipefail`, causing broken output. Fixed with `{ grep -v ... || true; } | git mktree` pattern.
  - Restructured SKILL.md: renamed "Abort Handling" to "Task Abort Procedure" (a named procedure like "Issue Update Procedure"). Created separate "Lock Release Procedure" section for reusability. All lock release points reference the procedure instead of inline commands.
- **Issues encountered:** `pipefail` + `grep -v` interaction when all lines are removed — the pipeline exit code is non-zero, causing the `||` fallback to concatenate duplicate output. Solved by wrapping `grep -v` in a group with `|| true`.
- **Key decisions:**
  - Graceful degradation: if lock branch doesn't exist, warn but don't block the workflow (backward compat)
  - Per-file locks (not single file) to avoid contention between different tasks
  - Separate branch from `aitask-ids` for cleaner isolation
  - Lock refresh: same email re-locking is idempotent (timestamp updated)
