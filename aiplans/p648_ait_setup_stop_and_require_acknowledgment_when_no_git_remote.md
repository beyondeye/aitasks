---
Task: t648_ait_setup_stop_and_require_acknowledgment_when_no_git_remote.md
Base branch: main
plan_verified: []
---

# Plan: t648 — `ait setup` warns + requires acknowledgment when no git remote is configured

## Context

`ait setup` currently silently skips the `aitask-locks` (lock) and `aitask-ids` (ID counter) orphan-branch initialization steps when the local repo has no `origin` remote configured. The user gets only a quiet `info` line and no indication that lock-based task picking and atomic ID assignment will be broken later. The first symptom is a cryptic `LOCK_ERROR:fetch_failed` from `/aitask-pick`, with no path back to the root cause unless the user knows to run `aitask_lock_diag.sh`.

The task asks for two changes:

1. **Primary** — make `setup_lock_branch()` show a clear warning, explain the consequence and the fix (`git remote add origin <url>` then re-run `ait setup`), and prompt for acknowledgment before continuing setup. Per user clarification, the same warn+acknowledge pattern is also applied to `setup_id_counter()` (identical bug, identical pattern), with a module-level flag so the user is only prompted once per setup run.

2. **Secondary** — in `aitask_lock.sh`, add an `ls-remote --exit-code --heads origin <branch>` probe before each user-facing fetch so the script returns exit code `10` (`LOCK_INFRA_MISSING`) when the branch genuinely doesn't exist on remote, and reserves exit code `11` (`LOCK_ERROR:fetch_failed`) for actual network/auth failures. Per user clarification, this is applied only to the two `die_code 11` sites (`lock_task` line 112 and `unlock_task` line 201). The non-fatal sites (`check_lock`, `list_locks`, `cleanup_locks`) already degrade gracefully and stay unchanged.

## Files to modify

### 1. `.aitask-scripts/aitask_setup.sh`

Add a new helper just above `setup_id_counter()` (around line 738):

```bash
# Module-level flag so warn_missing_remote_for_branch() prompts only once
# per setup run. Both setup_id_counter and setup_lock_branch consult this.
_AIT_SETUP_NO_REMOTE_ACKED=""

# Warn that a required orphan branch cannot be initialized because no git
# remote is configured. Explain the fix and prompt for acknowledgment.
# On acknowledgment, set the module-level flag and return 0 — the caller
# should then `return` to skip its lock/init step. On refusal, abort setup.
# Subsequent calls during the same run are no-ops (return 0 silently).
#
# Args: $1 = branch name (e.g. "aitask-locks"), $2 = purpose label
warn_missing_remote_for_branch() {
    local branch="$1"
    local purpose="$2"

    if [[ "$_AIT_SETUP_NO_REMOTE_ACKED" == "1" ]]; then
        info "Skipping '$branch' setup — no remote (already acknowledged)"
        return 0
    fi

    warn "No git remote 'origin' configured."
    info "Cannot initialize the '$branch' orphan branch without a remote."
    info "$purpose will not work for cross-machine coordination, and"
    info "later 'ait pick' calls may fail with LOCK_ERROR:fetch_failed."
    info ""
    info "To fix:"
    info "  git remote add origin <url>"
    info "  ait setup    # re-run after adding the remote"
    info ""

    local answer
    if [[ -t 0 ]]; then
        printf "  Continue setup without '%s' (acknowledge)? [Y/n] " "$branch"
        read -r answer
    else
        info "(non-interactive: auto-accepting acknowledgment)"
        answer="Y"
    fi

    case "${answer:-Y}" in
        [Yy]*|"")
            _AIT_SETUP_NO_REMOTE_ACKED=1
            warn "Continuing without '$branch'. Re-run 'ait setup' after adding the remote."
            return 0
            ;;
        *)
            die "Setup aborted. Configure a git remote and re-run 'ait setup'."
            ;;
    esac
}
```

Modify `setup_id_counter()` (lines 746–749). Replace:

```bash
    if ! git -C "$project_dir" remote get-url origin &>/dev/null; then
        info "No git remote configured — skipping task ID counter setup"
        return
    fi
```

with:

```bash
    if ! git -C "$project_dir" remote get-url origin &>/dev/null; then
        warn_missing_remote_for_branch "aitask-ids" "Atomic task ID assignment"
        return
    fi
```

Modify `setup_lock_branch()` (lines 788–791). Replace:

```bash
    if ! git -C "$project_dir" remote get-url origin &>/dev/null; then
        info "No git remote configured — skipping task lock branch setup"
        return
    fi
```

with:

```bash
    if ! git -C "$project_dir" remote get-url origin &>/dev/null; then
        warn_missing_remote_for_branch "aitask-locks" "Task locking"
        return
    fi
```

Note: ordering in `main()` already calls `setup_id_counter` before `setup_lock_branch`, so the user is prompted once during the ID-counter step and the lock-branch step then quietly logs "Skipping 'aitask-locks' setup — no remote (already acknowledged)".

### 2. `.aitask-scripts/aitask_lock.sh`

Add a new helper near the existing `has_remote()` (around line 47):

```bash
# Check whether the lock branch exists on origin (returns 0=yes, 1=no).
# Used to distinguish LOCK_INFRA_MISSING from LOCK_ERROR:fetch_failed.
lock_branch_exists_on_remote() {
    git ls-remote --exit-code --heads origin "$BRANCH" &>/dev/null
}
```

Modify `lock_task()` (lines 109–113). Replace:

```bash
        # Step 1: Fetch latest lock branch
        debug "Fetching branch '$BRANCH' from origin..."
        if ! git fetch origin "$BRANCH" --quiet 2>/dev/null; then
            die_code 11 "Failed to fetch '$BRANCH' from origin. Run 'ait setup' to initialize."
        fi
```

with:

```bash
        # Step 1: Verify lock branch exists on remote, then fetch
        debug "Probing branch '$BRANCH' on origin..."
        if ! lock_branch_exists_on_remote; then
            die_code 10 "Lock branch '$BRANCH' not found on remote. Run 'ait setup' to initialize."
        fi
        debug "Fetching branch '$BRANCH' from origin..."
        if ! git fetch origin "$BRANCH" --quiet 2>/dev/null; then
            die_code 11 "Failed to fetch '$BRANCH' from origin (network or auth issue)."
        fi
```

Modify `unlock_task()` (lines 199–202). Replace:

```bash
        # Step 1: Fetch latest
        if ! git fetch origin "$BRANCH" --quiet 2>/dev/null; then
            die_code 11 "Failed to fetch '$BRANCH'. Run 'ait setup' to initialize."
        fi
```

with:

```bash
        # Step 1: Verify lock branch exists on remote, then fetch
        if ! lock_branch_exists_on_remote; then
            die_code 10 "Lock branch '$BRANCH' not found on remote. Run 'ait setup' to initialize."
        fi
        if ! git fetch origin "$BRANCH" --quiet 2>/dev/null; then
            die_code 11 "Failed to fetch '$BRANCH' (network or auth issue)."
        fi
```

`check_lock`, `list_locks`, and `cleanup_locks` are intentionally left unchanged — their existing fetch-failure handling already returns "no locks" or silently continues, which is correct whether the cause is missing-branch or transient network failure.

The exit-code-to-string mapping in `aitask_pick_own.sh` (lines 185–188) already maps `10 → LOCK_INFRA_MISSING` and `11 → LOCK_ERROR:fetch_failed`, and the `task-workflow/SKILL.md` workflow already documents handlers for both, so no consumer-side changes are required.

### 3. `tests/test_setup_git.sh`

Append three new tests after Test 14, before the Summary section. They use the existing `setup_fake_project` helper and source the modified setup script.

- **Test 15:** `warn_missing_remote_for_branch` non-interactive auto-acknowledges and sets the flag.
  - Reset `_AIT_SETUP_NO_REMOTE_ACKED=""` then call `warn_missing_remote_for_branch "aitask-locks" "Test purpose" </dev/null` and capture stdout.
  - Assert output contains `"No git remote 'origin' configured"`, `"git remote add origin"`, and `"auto-accepting acknowledgment"`.
  - Assert `$_AIT_SETUP_NO_REMOTE_ACKED == 1` after the call.

- **Test 16:** `warn_missing_remote_for_branch` second call is silent and idempotent.
  - With the flag still set from Test 15, call the helper again; capture output.
  - Assert output contains `"already acknowledged"` and does NOT contain `"git remote add origin"` (no second prompt block).

- **Test 17:** `setup_lock_branch` skips cleanly when no remote is configured.
  - Build a fake project with `setup_fake_project`, `git init` it but skip `git remote add`.
  - Reset `_AIT_SETUP_NO_REMOTE_ACKED=""`, set `SCRIPT_DIR` to the temp project, run `setup_lock_branch </dev/null` and capture stdout.
  - Assert output contains `"No git remote 'origin' configured"` (the warning fired) and the function returned 0 (no abort).
  - Assert no `aitask-locks` ref was created locally: `git -C "$tmpdir" rev-parse refs/heads/aitask-locks 2>/dev/null` should fail.

Each test cleans up its tmpdir with `rm -rf`. Pattern follows existing tests 1–14: source script with `--source-only`, override `SCRIPT_DIR`, run function via `</dev/null` to trigger the non-interactive branch, assert on captured output.

### 4. `tests/test_task_lock.sh`

Add one new test in the existing test file. Use the existing `setup_paired_repos` helper to get a clone with origin pointing at a bare remote, but **skip the lock-branch init**. Then attempt to lock and assert the new exit code.

- **Test (LOCK_INFRA_MISSING):** lock when branch is missing on remote.
  - Use `setup_paired_repos` to create remote+local but do NOT run `aitask_lock.sh --init`.
  - From the local clone, run `aitask_lock.sh 1 --email t@t.com` and capture exit code with `set +e; ...; rc=$?; set -e`.
  - Assert `rc == 10`.
  - Assert stderr contains `"not found on remote"`.

The complementary `--unlock` exit-10 test is omitted because `unlock_task` is only called from `aitask_pick_own.sh` after a successful lock (which would now fail with exit 10 first), so the new code path is naturally exercised whenever the user runs `ait pick` with no lock infra.

## How to verify

1. **Lint** — both scripts must pass shellcheck:
   ```bash
   shellcheck .aitask-scripts/aitask_setup.sh .aitask-scripts/aitask_lock.sh
   ```

2. **Unit tests** — both updated test files pass:
   ```bash
   bash tests/test_setup_git.sh
   bash tests/test_task_lock.sh
   ```

3. **Setup integration** — manual repro of the original bug scenario:
   ```bash
   tmp=$(mktemp -d); cd "$tmp"
   git init -q
   # No `git remote add origin` — this is the bug-trigger state.
   /path/to/ait setup    # should warn + acknowledge once during setup_id_counter,
                          # then quietly skip setup_lock_branch with the
                          # "already acknowledged" line. Setup completes.
   ```
   Then add a remote and re-run `ait setup`; the warning should no longer fire and both `aitask-ids` and `aitask-locks` should initialize.

4. **Lock-error differentiation** — manual repro:
   ```bash
   # In a clone with a real remote but no aitask-locks branch:
   cd /path/to/clone
   ./.aitask-scripts/aitask_lock.sh 1 --email t@t.com
   echo $?    # expect 10 (LOCK_INFRA_MISSING), not 11 (fetch_failed)
   ```
   `aitask_pick_own.sh` should now print `LOCK_INFRA_MISSING` (handled with the documented "Inform user to run `ait setup` and abort" path) instead of `LOCK_ERROR:fetch_failed`.

5. **Cross-platform sanity** — the new helper uses only POSIX bash constructs (`printf`, `read`, `case`, `[[ -t 0 ]]`) and `git ls-remote --exit-code` (supported by every git ≥ 1.8). No macOS-specific portability work needed.

## Out of scope (called out for follow-ups)

- The `check_lock` / `list_locks` / `cleanup_locks` fetch sites in `aitask_lock.sh` (lines 248, 273, 311). Per user clarification, these stay unchanged because their current degrade-gracefully behavior is already correct.
- Documentation updates to `website/content/docs/commands/setup-install.md` describing the new acknowledgment prompt. The current page does not enumerate every prompt setup shows; if a doc update is desired, it can be a small follow-up task.
- Step 9 (Post-Implementation): standard merge/archive flow per `task-workflow/SKILL.md`. The change is small and isolated to non-UI shell scripts; no separate worktree/branch is being used (profile `create_worktree: false`).
