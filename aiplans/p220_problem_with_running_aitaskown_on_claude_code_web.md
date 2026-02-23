---
Task: t220_problem_with_running_aitaskown_on_claude_code_web.md
Branch: main (no worktree)
---

# Plan: Fix Lock System Issues (t220)

## Context

When running `aitask_own.sh` on Claude Code Web, it fails with `LOCK_INFRA_MISSING` even though the lock branch is initialized. The root cause: `acquire_lock()` in `aitask_own.sh` classifies **any** lock failure that isn't "already locked by" as `LOCK_INFRA_MISSING` (line 166). This includes network timeouts, fetch failures, and race exhaustion — all of which are NOT infrastructure missing.

Additionally, task t217 was locked by a killed process, creating a stale lock that blocks future pick attempts. The current cleanup only handles locks for *archived* tasks, not stale locks on active tasks.

Finally, the aitask-pick/pickrem workflow needs to properly abort (not continue) when lock acquisition fails, and offer force-unlock for stale locks.

## Dependency: t221 (aitasks/aiplans to separate branch)

**IMPORTANT:** Task t221 is refactoring all git operations on aitasks/aiplans to go through `task_git()` / `ait git` instead of plain `git`, to support storing task data on a separate branch. This affects t220 as follows:

- `aitask_own.sh` `commit_and_push()` currently does `git add aitasks/` / `git commit` / `git push` → after t221 these become `task_git add aitasks/` / `task_git commit` / `task_git push`
- `aitask_lock.sh` is **NOT affected** by t221 (it already uses its own `aitask-locks` orphan branch)
- Skills referencing direct `git add aitasks/` will become `./ait git add aitasks/`
- The diagnostic script should also check for `.aitask-data/` worktree existence

**Implementation strategy:** The changes below for lock exit codes, `--force` flag, error classification, and force_acquire_lock are independent of the task_git refactoring. They work on `aitask_lock.sh` (unchanged by t221) and `aitask_own.sh`'s locking logic (orthogonal to git operation routing). The `commit_and_push()` function in aitask_own.sh will be updated by t221_2 separately.

When implementing this task after t221, verify that:
1. `aitask_own.sh` uses `task_git` for add/commit/push (done by t221_2)
2. The diagnostic script checks both `aitask-locks` branch AND `aitask-data` worktree if present
3. Skills reference `./ait git` where they currently reference `git` for task file operations

## Changes

### 1. Add `die_code()` helper to `terminal_compat.sh`

**File:** `aiscripts/lib/terminal_compat.sh` (line 17, after `die()`)

Add:
```bash
die_code() { local code="$1"; shift; echo -e "${RED}Error: $1${NC}" >&2; exit "$code"; }
```

This avoids inlining `echo + exit` at every call site in `aitask_lock.sh`.

### 2. Add structured exit codes to `aitask_lock.sh`

**File:** `aiscripts/aitask_lock.sh`

Replace `die()` calls with `die_code()` using specific exit codes:

| Exit Code | Meaning | Where |
|-----------|---------|-------|
| 0 | Success | (unchanged) |
| 1 | Already locked by another user | `lock_task()` line 121 (unchanged — `die()` already exits 1) |
| 10 | No remote configured | `require_remote()` line 44 |
| 11 | Fetch failed (network/missing branch) | `lock_task()` line 101, `unlock_task()` line 182 |
| 12 | Race exhaustion (max retries) | `lock_task()` line 162, `unlock_task()` line 216 |

Changes:
- `require_remote()` (line 42-46): `die(...)` → `die_code 10 "..."`
- `lock_task()` fetch failure (line 101): `die(...)` → `die_code 11 "..."`
- `lock_task()` race exhaustion (line 162): `die_code 12 "..."`
- `unlock_task()` fetch failure (line 182): `die_code 11 "..."`
- `unlock_task()` race exhaustion (line 216): `die_code 12 "..."`

**Note:** `check_lock()`, `list_locks()`, and `cleanup_locks()` also use `require_remote()`, so they inherit exit 10 instead of exit 1 for no-remote errors. All callers already swallow these with `|| true` or check for non-zero generically, so this is backward-safe.

### 3. Improve error classification and add `--force` to `aitask_own.sh`

**File:** `aiscripts/aitask_own.sh`

**a) Add `--force` flag:**
- Add `FORCE=false` to configuration section (line 36)
- Add `--force)` case to `parse_args()` (after `--sync` case at line 92)
- Update help text and header comments

**b) Rewrite `acquire_lock()` (lines 140-168) with case-based exit code classification:**
```bash
acquire_lock() {
    local task_id="$1" email="$2"
    [[ -z "$email" ]] && return 0

    local lock_output lock_exit=0
    lock_output=$("$SCRIPT_DIR/aitask_lock.sh" --lock "$task_id" --email "$email" 2>&1) || lock_exit=$?

    [[ $lock_exit -eq 0 ]] && return 0

    case $lock_exit in
        1)  # Already locked by another user
            local owner
            owner=$(echo "$lock_output" | grep -o 'already locked by [^ ]*' | sed 's/already locked by //')
            [[ -z "$owner" ]] && owner="unknown"
            echo "LOCK_FAILED:$owner"
            return 1 ;;
        10) echo "LOCK_INFRA_MISSING"; return 2 ;;
        11) echo "LOCK_ERROR:fetch_failed"; return 3 ;;
        12) echo "LOCK_ERROR:race_exhaustion"; return 3 ;;
        *)  echo "LOCK_ERROR:unknown"; return 3 ;;
    esac
}
```

**c) Add `force_acquire_lock()` function (new, after `acquire_lock()`):**
```bash
force_acquire_lock() {
    local task_id="$1" email="$2"
    [[ -z "$email" ]] && return 0

    # Check who currently holds the lock
    local check_output previous_owner
    check_output=$("$SCRIPT_DIR/aitask_lock.sh" --check "$task_id" 2>&1) || true
    previous_owner=$(echo "$check_output" | grep '^locked_by:' | sed 's/locked_by: *//')
    [[ -z "$previous_owner" ]] && previous_owner="unknown"

    # Force unlock then re-lock
    "$SCRIPT_DIR/aitask_lock.sh" --unlock "$task_id" 2>/dev/null || true

    local lock_output lock_exit=0
    lock_output=$("$SCRIPT_DIR/aitask_lock.sh" --lock "$task_id" --email "$email" 2>&1) || lock_exit=$?

    if [[ $lock_exit -eq 0 ]]; then
        echo "FORCE_UNLOCKED:$previous_owner"
        return 0
    fi
    echo "LOCK_ERROR:force_lock_failed"
    return 3
}
```

**d) Update `main()` (lines 219-230) to handle --force and return code 3:**
```bash
    local lock_result=0
    acquire_lock "$TASK_ID" "$EMAIL" || lock_result=$?

    if [[ $lock_result -eq 1 && "$FORCE" == true ]]; then
        local force_result=0
        force_acquire_lock "$TASK_ID" "$EMAIL" || force_result=$?
        if [[ $force_result -ne 0 ]]; then
            exit 1
        fi
    elif [[ $lock_result -eq 1 ]]; then
        exit 1
    elif [[ $lock_result -eq 2 ]]; then
        die "Run 'ait setup' to initialize lock infrastructure."
    elif [[ $lock_result -eq 3 ]]; then
        exit 1
    fi
```

**e) Update output format documentation in header comments:**
Add `FORCE_UNLOCKED:<previous_owner>` and `LOCK_ERROR:<message>` to the structured output list.

### 4. Create diagnostic script `aiscripts/aitask_lock_diag.sh`

New file (standalone, not registered in `ait` dispatcher). Tests all lock system prerequisites with PASS/FAIL output:

1. Git available + version
2. `origin` remote configured (with URL displayed)
3. Lock branch exists on remote (`git ls-remote --heads origin aitask-locks`)
4. Fetch lock branch works (`git fetch origin aitask-locks`)
5. Parse lock branch tree (`git rev-parse "origin/aitask-locks^{tree}"`)
6. Git plumbing: `git hash-object --stdin`, `git mktree`, `git commit-tree`
7. Push test (`git push --dry-run origin ...`)
8. `hostname` command available
9. `date` command format works
10. List current locks (`aitask_lock.sh --list`)
11. Environment info: `$HOME`, `$GIT_SSH_COMMAND`, `$GIT_ASKPASS`, git credential helper
12. Data worktree check: if `.aitask-data/` exists, verify it's a valid worktree on `aitask-data` branch (t221 compatibility)

Script is read-only (no state modification, uses `--dry-run` for push test).

### 5. Update `task-workflow/SKILL.md` Step 4 lock handling

**File:** `.claude/skills/task-workflow/SKILL.md` (lines 104-109)

Replace the current lock output parsing with expanded handling:

- **`LOCK_FAILED:<owner>`**: Run `aitask_lock.sh --check <task_num>` to get lock details (locked_by, locked_at, hostname). Ask user via `AskUserQuestion`: "Task t<N> is locked by <owner> (since <locked_at>, hostname: <hostname>). Force unlock?" Options: "Force unlock and claim" / "Pick a different task". If force: re-run with `--force`.
- **`LOCK_ERROR:<message>`**: Display error + suggest running `./aiscripts/aitask_lock_diag.sh`. Ask user: "Retry" / "Continue without lock" / "Abort".
- **`FORCE_UNLOCKED:<previous_owner>`** + `OWNED:<task_id>`: Inform user and proceed.
- **`LOCK_INFRA_MISSING`**: Unchanged (abort, run `ait setup`).

### 6. Update `aitask-pickrem/SKILL.md` Step 5 lock handling

**File:** `.claude/skills/aitask-pickrem/SKILL.md` (lines 138-143)

Add `force_unlock_stale` profile support:

- **`LOCK_FAILED:<owner>`**: Check profile `force_unlock_stale` (default: `false`). If `true`: auto-retry with `--force`. If `false`: abort.
- **`LOCK_ERROR:<message>`**: Display error + suggest running `./aiscripts/aitask_lock_diag.sh`. Abort.
- **`FORCE_UNLOCKED:<previous_owner>`** + `OWNED:<task_id>`: Display and proceed.

Add `force_unlock_stale` to the Extended Profile Schema table (line 408 area):
```
| `force_unlock_stale` | bool | `false` | `true`, `false` | Step 5: Auto force-unlock stale locks |
```

### 7. Update `remote.yaml` profile

**File:** `aitasks/metadata/profiles/remote.yaml`

Add:
```yaml
force_unlock_stale: true
```

### 8. Tests

**File:** `tests/test_lock_force.sh` (new)

Using `setup_paired_repos` pattern from `test_task_lock.sh`:

1. **Force-lock when locked by another user**: Lock as alice, `aitask_own.sh --force --email bob` → assert `FORCE_UNLOCKED:alice` + `OWNED`
2. **No force when locked**: Lock as alice, `aitask_own.sh --email bob` (no --force) → assert `LOCK_FAILED:alice`
3. **Force when not locked**: `aitask_own.sh --force --email bob` on unlocked task → assert `OWNED` (no FORCE_UNLOCKED)
4. **Exit code 10**: Remove origin remote, run lock → assert exit 10
5. **LOCK_ERROR classification**: Simulate exit 11 → verify `LOCK_ERROR:fetch_failed` output

**File:** `tests/test_lock_diag.sh` (new)

1. Syntax check (`bash -n`)
2. Run in paired repo with initialized lock branch → all PASS
3. Run in paired repo without lock branch → "lock branch" check FAIL

## Implementation Order

1. `aiscripts/lib/terminal_compat.sh` — add `die_code()`
2. `aiscripts/aitask_lock.sh` — structured exit codes
3. `aiscripts/aitask_own.sh` — `--force` flag + improved `acquire_lock()` + `force_acquire_lock()`
4. `aiscripts/aitask_lock_diag.sh` — new diagnostic script (standalone, not in dispatcher)
5. `aitasks/metadata/profiles/remote.yaml` — add `force_unlock_stale`
6. `.claude/skills/task-workflow/SKILL.md` — update Step 4
7. `.claude/skills/aitask-pickrem/SKILL.md` — update Step 5 + schema
8. Tests — `test_lock_force.sh` + `test_lock_diag.sh`

## Verification

```bash
bash tests/test_task_lock.sh          # Existing tests still pass
bash tests/test_lock_force.sh         # New force-lock tests pass
bash tests/test_lock_diag.sh          # New diagnostic tests pass
shellcheck aiscripts/aitask_lock.sh aiscripts/aitask_own.sh aiscripts/aitask_lock_diag.sh
./aiscripts/aitask_lock_diag.sh       # Manual: all checks PASS in dev environment
```

**After t221 lands:** Also verify diagnostic script works in branch mode (with `.aitask-data/` worktree).
