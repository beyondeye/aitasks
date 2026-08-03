#!/usr/bin/env bash
# test_task_lock.sh - Automated tests for aitask_lock.sh
# Run: bash tests/test_task_lock.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

# Shared assertion helpers (see tests/lib/asserts.sh)
. "$PROJECT_DIR/tests/lib/asserts.sh"




# Create a paired repo setup: bare "remote" + local clone with task files
setup_paired_repos() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    # Create bare "remote" repo
    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet "$remote_dir"

    # Create local working repo
    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir"
    (
        cd "$local_dir"
        git config user.email "test@test.com"
        git config user.name "Test"

        # Create task directory structure
        mkdir -p aitasks/archived

        # Copy the scripts we need
        setup_fake_aitask_repo "$PWD"
        cp "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
        chmod +x .aitask-scripts/aitask_lock.sh

        git add -A
        git commit -m "Initial setup" --quiet
        git push --quiet 2>/dev/null
    )

    echo "$tmpdir"
}

# Create a second clone of the same remote
clone_second_local() {
    local tmpdir="$1"
    local remote_dir="$tmpdir/remote.git"
    local local2_dir="$tmpdir/local2"

    git clone --quiet "$remote_dir" "$local2_dir"
    (
        cd "$local2_dir"
        git config user.email "test2@test.com"
        git config user.name "Test2"

        # Copy scripts
        setup_fake_aitask_repo "$PWD"
        cp "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
        chmod +x .aitask-scripts/aitask_lock.sh
    )

    echo "$local2_dir"
}

# Disable strict mode for test error handling
set +e

echo "=== aitask_lock.sh Tests ==="
echo ""

# --- Test 1: Init creates branch ---
echo "--- Test 1: Init creates branch ---"

TMPDIR_1="$(setup_paired_repos)"
output=$(cd "$TMPDIR_1/local" && ./.aitask-scripts/aitask_lock.sh --init 2>&1)

# Branch should exist on remote
branch_exists=$(git -C "$TMPDIR_1/local" ls-remote --heads origin aitask-locks 2>/dev/null | grep -c "aitask-locks")
assert_eq "Branch exists on remote" "1" "$branch_exists"

assert_contains_ci "Output mentions created" "created" "$output"

rm -rf "$TMPDIR_1"

# --- Test 2: Init is idempotent ---
echo "--- Test 2: Init is idempotent ---"

TMPDIR_2="$(setup_paired_repos)"
(cd "$TMPDIR_2/local" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)
output2=$(cd "$TMPDIR_2/local" && ./.aitask-scripts/aitask_lock.sh --init 2>&1)

assert_contains_ci "Idempotent init says already exists" "already exists" "$output2"

rm -rf "$TMPDIR_2"

# --- Test 3: Lock creates lock file ---
echo "--- Test 3: Lock creates lock file ---"

TMPDIR_3="$(setup_paired_repos)"
(cd "$TMPDIR_3/local" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)
(cd "$TMPDIR_3/local" && ./.aitask-scripts/aitask_lock.sh --lock 1 --email "user@test.com" >/dev/null 2>&1)

# Verify lock file exists in branch tree
lock_exists=$(cd "$TMPDIR_3/local" && git fetch origin aitask-locks --quiet 2>/dev/null && git ls-tree "origin/aitask-locks" 2>/dev/null | grep -c "t1_lock.yaml")
assert_eq "Lock file exists in branch tree" "1" "$lock_exists"

rm -rf "$TMPDIR_3"

# --- Test 4: Lock file YAML content ---
echo "--- Test 4: Lock file YAML content ---"

TMPDIR_4="$(setup_paired_repos)"
(cd "$TMPDIR_4/local" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)
(cd "$TMPDIR_4/local" && ./.aitask-scripts/aitask_lock.sh --lock 42 --email "alice@example.com" >/dev/null 2>&1)

lock_content=$(cd "$TMPDIR_4/local" && git fetch origin aitask-locks --quiet 2>/dev/null && git show "origin/aitask-locks:t42_lock.yaml" 2>/dev/null)
assert_contains_ci "YAML has task_id" "task_id: 42" "$lock_content"
assert_contains_ci "YAML has locked_by" "locked_by: alice@example.com" "$lock_content"
assert_contains_ci "YAML has locked_at" "locked_at:" "$lock_content"
assert_contains_ci "YAML has hostname" "hostname:" "$lock_content"

rm -rf "$TMPDIR_4"

# --- Test 5: Check returns 0 for locked task ---
echo "--- Test 5: Check returns 0 for locked task ---"

TMPDIR_5="$(setup_paired_repos)"
(cd "$TMPDIR_5/local" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)
(cd "$TMPDIR_5/local" && ./.aitask-scripts/aitask_lock.sh --lock 1 --email "user@test.com" >/dev/null 2>&1)

assert_exit_zero "Check locked task exits 0" bash -c "cd '$TMPDIR_5/local' && ./.aitask-scripts/aitask_lock.sh --check 1"

# Also verify it outputs content
check_output=$(cd "$TMPDIR_5/local" && ./.aitask-scripts/aitask_lock.sh --check 1 2>/dev/null)
assert_contains_ci "Check outputs lock info" "locked_by: user@test.com" "$check_output"

rm -rf "$TMPDIR_5"

# --- Test 6: Check returns 1 for unlocked task ---
echo "--- Test 6: Check returns 1 for unlocked task ---"

TMPDIR_6="$(setup_paired_repos)"
(cd "$TMPDIR_6/local" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)

assert_exit_nonzero "Check unlocked task exits non-zero" bash -c "cd '$TMPDIR_6/local' && ./.aitask-scripts/aitask_lock.sh --check 99"

rm -rf "$TMPDIR_6"

# --- Test 7: Unlock removes lock file ---
echo "--- Test 7: Unlock removes lock file ---"

TMPDIR_7="$(setup_paired_repos)"
(cd "$TMPDIR_7/local" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)
(cd "$TMPDIR_7/local" && ./.aitask-scripts/aitask_lock.sh --lock 1 --email "user@test.com" >/dev/null 2>&1)
(cd "$TMPDIR_7/local" && ./.aitask-scripts/aitask_lock.sh --unlock 1 >/dev/null 2>&1)

# Verify lock file is gone
lock_gone=$(cd "$TMPDIR_7/local" && git fetch origin aitask-locks --quiet 2>/dev/null && git ls-tree "origin/aitask-locks" 2>/dev/null | grep -c "t1_lock.yaml")
assert_eq "Lock file removed after unlock" "0" "$lock_gone"

rm -rf "$TMPDIR_7"

# --- Test 8: Unlock is idempotent ---
echo "--- Test 8: Unlock is idempotent ---"

TMPDIR_8="$(setup_paired_repos)"
(cd "$TMPDIR_8/local" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)

# Unlock a task that was never locked — should succeed
assert_exit_zero "Unlock never-locked task exits 0" bash -c "cd '$TMPDIR_8/local' && ./.aitask-scripts/aitask_lock.sh --unlock 99"

rm -rf "$TMPDIR_8"

# --- Test 9: Same email re-lock succeeds (refresh) ---
echo "--- Test 9: Same email re-lock succeeds ---"

TMPDIR_9="$(setup_paired_repos)"
(cd "$TMPDIR_9/local" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)
(cd "$TMPDIR_9/local" && ./.aitask-scripts/aitask_lock.sh --lock 1 --email "user@test.com" >/dev/null 2>&1)

# Re-lock with same email should succeed
assert_exit_zero "Re-lock with same email succeeds" bash -c "cd '$TMPDIR_9/local' && ./.aitask-scripts/aitask_lock.sh --lock 1 --email 'user@test.com'"

rm -rf "$TMPDIR_9"

# --- Test 10: Different email lock fails ---
echo "--- Test 10: Different email lock fails ---"

TMPDIR_10="$(setup_paired_repos)"
(cd "$TMPDIR_10/local" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)
(cd "$TMPDIR_10/local" && ./.aitask-scripts/aitask_lock.sh --lock 1 --email "alice@test.com" >/dev/null 2>&1)

# Lock with different email should fail
output10=$(cd "$TMPDIR_10/local" && ./.aitask-scripts/aitask_lock.sh --lock 1 --email "bob@test.com" 2>&1 || true)
assert_exit_nonzero "Different email lock fails" bash -c "cd '$TMPDIR_10/local' && ./.aitask-scripts/aitask_lock.sh --lock 1 --email 'bob@test.com'"
assert_contains_ci "Error mentions existing locker" "alice@test.com" "$output10"

rm -rf "$TMPDIR_10"

# --- Test 11: Race simulation ---
echo "--- Test 11: Race simulation ---"

TMPDIR_11="$(setup_paired_repos)"
(cd "$TMPDIR_11/local" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)

local2_dir=$(clone_second_local "$TMPDIR_11")

# Two PCs try to lock the same task simultaneously
(cd "$TMPDIR_11/local" && ./.aitask-scripts/aitask_lock.sh --lock 1 --email "pc1@test.com" 2>/dev/null) > "$TMPDIR_11/result1" 2>&1 &
pid1=$!
(cd "$local2_dir" && ./.aitask-scripts/aitask_lock.sh --lock 1 --email "pc2@test.com" 2>/dev/null) > "$TMPDIR_11/result2" 2>&1 &
pid2=$!

wait $pid1; exit1=$?
wait $pid2; exit2=$?

# Exactly one should succeed (exit 0) and one should fail
TOTAL=$((TOTAL + 1))
if [[ ($exit1 -eq 0 && $exit2 -ne 0) || ($exit1 -ne 0 && $exit2 -eq 0) ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Race simulation - expected exactly one success (exit1=$exit1, exit2=$exit2)"
fi

rm -rf "$TMPDIR_11"

# --- Test 12: Cleanup removes stale locks ---
echo "--- Test 12: Cleanup removes stale locks ---"

TMPDIR_12="$(setup_paired_repos)"
(cd "$TMPDIR_12/local" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)

# Lock task 1
(cd "$TMPDIR_12/local" && ./.aitask-scripts/aitask_lock.sh --lock 1 --email "user@test.com" >/dev/null 2>&1)

# Create archived task file to mark it as stale
(
    cd "$TMPDIR_12/local"
    echo "---" > aitasks/archived/t1_test_task.md
    git add -A && git commit -m "Archive task" --quiet && git push --quiet 2>/dev/null
)

# Run cleanup
(cd "$TMPDIR_12/local" && ./.aitask-scripts/aitask_lock.sh --cleanup >/dev/null 2>&1)

# Verify lock was removed
lock_after_cleanup=$(cd "$TMPDIR_12/local" && git fetch origin aitask-locks --quiet 2>/dev/null && git ls-tree "origin/aitask-locks" 2>/dev/null | grep -c "t1_lock.yaml")
assert_eq "Stale lock removed by cleanup" "0" "$lock_after_cleanup"

rm -rf "$TMPDIR_12"

# --- Test 12b-12h: --cleanup exit contract (t1370) ---
#
# `--cleanup` runs on every pick via aitask_pick_own.sh's sync_remote(), which
# used to discard both its stderr and its exit status. It now reports:
#   0  completed (nothing to do, or all stale locks removed)
#   11 the lock branch could not be READ — stale locks left in place
#   12 the branch was readable but the removal push was rejected every time
# The silent paths are ubiquitous, so each is pinned with an empty-stderr
# negative control.

# Run --cleanup in $1, capturing stderr to a FILE (command substitution would
# run the assignment in a subshell and lose the exit code).
cleanup_in() {
    local dir="$1" err_file="$2" rc=0
    (cd "$dir" && ./.aitask-scripts/aitask_lock.sh --cleanup >/dev/null 2>"$err_file") || rc=$?
    echo "$rc"
}

# Make the bare remote reject every push. $2 = extra sh run before rejecting,
# used to make the remote unreadable for the retry fetch that follows.
reject_pushes() {
    local tmpdir="$1" pre="${2:-}"
    printf '#!/bin/sh\n%s\necho "rejected by test hook" >&2\nexit 1\n' "$pre" \
        > "$tmpdir/remote.git/hooks/pre-receive"
    chmod +x "$tmpdir/remote.git/hooks/pre-receive"
}

# Lock task 1 and archive it, so cleanup identifies exactly one stale lock.
seed_stale_lock() {
    local dir="$1"
    (cd "$dir" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)
    (cd "$dir" && ./.aitask-scripts/aitask_lock.sh --lock 1 --email "user@test.com" >/dev/null 2>&1)
    (
        cd "$dir"
        echo "---" > aitasks/archived/t1_test_task.md
        git add -A && git commit -m "Archive task" --quiet && git push --quiet 2>/dev/null
    )
}

# --- Test 12b: empty lock branch -> exit 0, silent ---
# Regression test for a `set -euo pipefail` abort: the lock-file listing used to
# pipe `git ls-tree` through `grep`, and an empty branch made grep exit 1, which
# killed the sweep (exit 1) before the emptiness guard could return 0. This is
# the ordinary state of any project where nothing is currently locked.
echo "--- Test 12b: cleanup on an empty lock branch is silent ---"

TMPDIR_12B="$(setup_paired_repos)"
(cd "$TMPDIR_12B/local" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)
rc_12b=$(cleanup_in "$TMPDIR_12B/local" "$TMPDIR_12B/err.txt")
assert_eq "empty lock branch exits 0" "0" "$rc_12b"
assert_eq "empty lock branch stays silent" "" "$(cat "$TMPDIR_12B/err.txt")"

rm -rf "$TMPDIR_12B"

# --- Test 12c: live (non-stale) lock -> exit 0, silent ---
echo "--- Test 12c: cleanup with nothing stale is silent ---"

TMPDIR_12C="$(setup_paired_repos)"
(cd "$TMPDIR_12C/local" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)
(cd "$TMPDIR_12C/local" && ./.aitask-scripts/aitask_lock.sh --lock 1 --email "user@test.com" >/dev/null 2>&1)
rc_12c=$(cleanup_in "$TMPDIR_12C/local" "$TMPDIR_12C/err.txt")
assert_eq "nothing stale exits 0" "0" "$rc_12c"
assert_eq "nothing stale stays silent" "" "$(cat "$TMPDIR_12C/err.txt")"

rm -rf "$TMPDIR_12C"

# --- Test 12d: successful removal -> exit 0, no warning ---
echo "--- Test 12d: a successful sweep exits 0 without warning ---"

TMPDIR_12D="$(setup_paired_repos)"
seed_stale_lock "$TMPDIR_12D/local"
rc_12d=$(cleanup_in "$TMPDIR_12D/local" "$TMPDIR_12D/err.txt")
assert_eq "successful sweep exits 0" "0" "$rc_12d"
assert_eq "successful sweep does not warn" "" "$(cat "$TMPDIR_12D/err.txt")"

rm -rf "$TMPDIR_12D"

# --- Test 12e: lock branch absent on a reachable remote -> exit 0, silent ---
# `git fetch` fails here too, but with "couldn't find remote ref" — genuinely
# nothing to clean, and it must not be reported as a read failure.
echo "--- Test 12e: absent lock branch is not a failure ---"

TMPDIR_12E="$(setup_paired_repos)"   # deliberately no --init
rc_12e=$(cleanup_in "$TMPDIR_12E/local" "$TMPDIR_12E/err.txt")
assert_eq "absent lock branch exits 0" "0" "$rc_12e"
assert_eq "absent lock branch stays silent" "" "$(cat "$TMPDIR_12E/err.txt")"

rm -rf "$TMPDIR_12E"

# --- Test 12f: unreachable remote -> exit 11, classified warning ---
echo "--- Test 12f: unreachable remote reports exit 11 ---"

TMPDIR_12F="$(setup_paired_repos)"
(cd "$TMPDIR_12F/local" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)
(cd "$TMPDIR_12F/local" && git remote set-url origin /nonexistent/repo.git)
rc_12f=$(cleanup_in "$TMPDIR_12F/local" "$TMPDIR_12F/err.txt")
err_12f="$(cat "$TMPDIR_12F/err.txt")"
assert_eq "unreachable remote exits 11" "11" "$rc_12f"
assert_contains "unreachable remote names the lock branch" "lock branch" "$err_12f"
assert_contains "unreachable remote says cleanup did not run" "cleanup did not run" "$err_12f"
assert_contains "unreachable remote gives a connectivity hint" "remote unreachable" "$err_12f"

rm -rf "$TMPDIR_12F"

# --- Test 12g: push rejected on every attempt -> exit 12, names the leftovers ---
echo "--- Test 12g: exhausted removal push reports exit 12 ---"

TMPDIR_12G="$(setup_paired_repos)"
seed_stale_lock "$TMPDIR_12G/local"
reject_pushes "$TMPDIR_12G"
rc_12g=$(cleanup_in "$TMPDIR_12G/local" "$TMPDIR_12G/err.txt")
err_12g="$(cat "$TMPDIR_12G/err.txt")"
assert_eq "exhausted push exits 12" "12" "$rc_12g"
assert_contains "exhausted push names what was left uncleaned" "1 stale lock(s)" "$err_12g"
assert_contains "exhausted push reports the real attempt count" "5 push attempt(s)" "$err_12g"
# The lock must still be there — the warning would be a lie otherwise.
lock_still_there=$(cd "$TMPDIR_12G/local" && git ls-tree "origin/aitask-locks" 2>/dev/null | grep -c "t1_lock.yaml")
assert_eq "rejected removal leaves the stale lock in place" "1" "$lock_still_there"

rm -rf "$TMPDIR_12G"

# --- Test 12h: remote becomes unreadable mid-retry -> exit 11, not 12 ---
# The hook rejects the push AND disables the bare repo's HEAD, so the retry
# fetch fails. That is a READ failure: reporting it as 12 would hand the user a
# push-retry hint for a connectivity problem, and would claim MAX_RETRIES
# attempts when only one was made.
echo "--- Test 12h: a failed retry-fetch is reported as a read failure ---"

TMPDIR_12H="$(setup_paired_repos)"
seed_stale_lock "$TMPDIR_12H/local"
reject_pushes "$TMPDIR_12H" 'mv HEAD HEAD.disabled 2>/dev/null'
rc_12h=$(cleanup_in "$TMPDIR_12H/local" "$TMPDIR_12H/err.txt")
err_12h="$(cat "$TMPDIR_12H/err.txt")"
assert_eq "mid-retry read failure exits 11, not 12" "11" "$rc_12h"
assert_contains "mid-retry failure names the leftover locks" "1 stale lock(s) left in place" "$err_12h"
assert_contains "mid-retry failure gives a connectivity hint" "remote unreachable" "$err_12h"
assert_not_contains "mid-retry failure does not claim push exhaustion" "push attempt(s)" "$err_12h"

rm -rf "$TMPDIR_12H"

# --- Test 12h2: lock branch deleted mid-retry -> exit 0, silent ---
# "Branch absent" means nothing to clean, whether it is discovered by the first
# fetch or by the retry refresh. Reporting it as 11 would warn about an
# unreadable remote that is in fact perfectly readable — and retrying would push
# the rebuilt tree back, resurrecting every lock the deleted branch held.
echo "--- Test 12h2: a branch deleted mid-sweep is nothing to clean ---"

TMPDIR_12H2="$(setup_paired_repos)"
seed_stale_lock "$TMPDIR_12H2/local"
# The quarantine env a pre-receive hook inherits forbids ref updates
# ("ref updates forbidden inside quarantine environment"), so it must be
# cleared before the hook can delete the branch it is rejecting a push to.
reject_pushes "$TMPDIR_12H2" \
    'unset GIT_QUARANTINE_PATH GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES
     git update-ref -d refs/heads/aitask-locks >/dev/null 2>&1'
rc_12h2=$(cleanup_in "$TMPDIR_12H2/local" "$TMPDIR_12H2/err.txt")
err_12h2="$(cat "$TMPDIR_12H2/err.txt")"
assert_eq "branch deleted mid-sweep exits 0" "0" "$rc_12h2"
assert_eq "branch deleted mid-sweep stays silent" "" "$err_12h2"
# The branch must stay deleted — a retry would have recreated it with the locks.
branch_12h2=$(cd "$TMPDIR_12H2/local" && git ls-remote --heads origin aitask-locks 2>/dev/null | wc -l | tr -d '[:space:]')
assert_eq "a deleted lock branch is not resurrected" "0" "$branch_12h2"

rm -rf "$TMPDIR_12H2"

# --- Test 12i: a stray non-t<N> lock file does not abort the sweep ---
# Same pipefail class as 12b: the task-id extraction used to pipe through
# `grep -oE '^t[0-9]+'`, so one unrecognized filename killed the whole sweep.
echo "--- Test 12i: an unrecognized lock file is skipped, not fatal ---"

TMPDIR_12I="$(setup_paired_repos)"
seed_stale_lock "$TMPDIR_12I/local"
(
    cd "$TMPDIR_12I/local"
    git fetch origin aitask-locks --quiet 2>/dev/null
    blob=$(echo "junk" | git hash-object -w --stdin)
    tree=$( { git ls-tree "$(git rev-parse origin/aitask-locks^{tree})"
              printf '100644 blob %s\tnotalock_lock.yaml\n' "$blob"; } | git mktree )
    commit=$(echo "add stray lock file" | git commit-tree "$tree" -p "$(git rev-parse origin/aitask-locks)")
    git push --quiet origin "$commit:refs/heads/aitask-locks" 2>/dev/null
)
rc_12i=$(cleanup_in "$TMPDIR_12I/local" "$TMPDIR_12I/err.txt")
assert_eq "stray lock file does not abort the sweep" "0" "$rc_12i"
remaining_12i=$(cd "$TMPDIR_12I/local" && git fetch origin aitask-locks --quiet 2>/dev/null && git ls-tree --name-only "origin/aitask-locks" 2>/dev/null | tr '\n' ' ')
assert_contains "stray lock file is left alone" "notalock_lock.yaml" "$remaining_12i"
assert_not_contains "stale t1 lock is still removed" "t1_lock.yaml" "$remaining_12i"

rm -rf "$TMPDIR_12I"

# --- Test 13: List shows all locks ---
echo "--- Test 13: List shows all locks ---"

TMPDIR_13="$(setup_paired_repos)"
(cd "$TMPDIR_13/local" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)
(cd "$TMPDIR_13/local" && ./.aitask-scripts/aitask_lock.sh --lock 1 --email "alice@test.com" >/dev/null 2>&1)
(cd "$TMPDIR_13/local" && ./.aitask-scripts/aitask_lock.sh --lock 2 --email "bob@test.com" >/dev/null 2>&1)

list_output=$(cd "$TMPDIR_13/local" && ./.aitask-scripts/aitask_lock.sh --list 2>/dev/null)
assert_contains_ci "List shows task 1" "t1:" "$list_output"
assert_contains_ci "List shows task 2" "t2:" "$list_output"

rm -rf "$TMPDIR_13"

# --- Test 14: Syntax check ---
echo "--- Test 14: Syntax check ---"

assert_exit_zero "Syntax check passes" bash -n "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh"

# --- Test 15: Auto-detect email from userconfig.yaml ---
echo "--- Test 15: Auto-detect email from userconfig.yaml ---"

TMPDIR_15="$(setup_paired_repos)"
(cd "$TMPDIR_15/local" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)

# Create userconfig.yaml with email
(
    cd "$TMPDIR_15/local"
    mkdir -p aitasks/metadata
    echo "email: autouser@test.com" > aitasks/metadata/userconfig.yaml
)

# Lock without --email flag — should auto-detect from userconfig
assert_exit_zero "Auto-detect email lock succeeds" bash -c "cd '$TMPDIR_15/local' && ./.aitask-scripts/aitask_lock.sh --lock 50"

# Verify lock was acquired with the correct email
check_output_15=$(cd "$TMPDIR_15/local" && ./.aitask-scripts/aitask_lock.sh --check 50 2>/dev/null)
assert_contains_ci "Auto-detect used userconfig email" "locked_by: autouser@test.com" "$check_output_15"

rm -rf "$TMPDIR_15"

# --- Test 16: Auto-detect email from emails.txt fallback ---
echo "--- Test 16: Auto-detect email from emails.txt fallback ---"

TMPDIR_16="$(setup_paired_repos)"
(cd "$TMPDIR_16/local" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)

# Create only emails.txt (no userconfig.yaml)
(
    cd "$TMPDIR_16/local"
    mkdir -p aitasks/metadata
    echo "fallback@test.com" > aitasks/metadata/emails.txt
)

# Lock without --email flag — should fall back to emails.txt
assert_exit_zero "Fallback email lock succeeds" bash -c "cd '$TMPDIR_16/local' && ./.aitask-scripts/aitask_lock.sh --lock 51"

# Verify lock was acquired with the fallback email
check_output_16=$(cd "$TMPDIR_16/local" && ./.aitask-scripts/aitask_lock.sh --check 51 2>/dev/null)
assert_contains_ci "Fallback used emails.txt email" "locked_by: fallback@test.com" "$check_output_16"

rm -rf "$TMPDIR_16"

# --- Test 17: Fail gracefully when no email source ---
echo "--- Test 17: Fail gracefully when no email source ---"

TMPDIR_17="$(setup_paired_repos)"
(cd "$TMPDIR_17/local" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)

# No userconfig.yaml, no emails.txt — should fail
(
    cd "$TMPDIR_17/local"
    rm -f aitasks/metadata/userconfig.yaml aitasks/metadata/emails.txt 2>/dev/null
)

output17=$(cd "$TMPDIR_17/local" && ./.aitask-scripts/aitask_lock.sh --lock 52 2>&1 || true)
assert_exit_nonzero "No email source fails" bash -c "cd '$TMPDIR_17/local' && ./.aitask-scripts/aitask_lock.sh --lock 52"
assert_contains_ci "Error mentions no email" "No email provided" "$output17"

rm -rf "$TMPDIR_17"

# --- Test 18: Bare task ID shortcut ---
echo "--- Test 18: Bare task ID shortcut ---"

TMPDIR_18="$(setup_paired_repos)"
(cd "$TMPDIR_18/local" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)

# Create userconfig for auto-detect
(
    cd "$TMPDIR_18/local"
    mkdir -p aitasks/metadata
    echo "email: bare@test.com" > aitasks/metadata/userconfig.yaml
)

# Use bare task ID (no --lock prefix)
assert_exit_zero "Bare task ID lock succeeds" bash -c "cd '$TMPDIR_18/local' && ./.aitask-scripts/aitask_lock.sh 50"

# Verify lock was acquired
check_output_18=$(cd "$TMPDIR_18/local" && ./.aitask-scripts/aitask_lock.sh --check 50 2>/dev/null)
assert_contains_ci "Bare ID used correct email" "locked_by: bare@test.com" "$check_output_18"

rm -rf "$TMPDIR_18"

# --- Test 19: Bare task ID with explicit --email ---
echo "--- Test 19: Bare task ID with explicit --email ---"

TMPDIR_19="$(setup_paired_repos)"
(cd "$TMPDIR_19/local" && ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)

# Use bare task ID with --email
assert_exit_zero "Bare ID with --email succeeds" bash -c "cd '$TMPDIR_19/local' && ./.aitask-scripts/aitask_lock.sh 50 --email explicit@test.com"

# Verify lock used the explicit email
check_output_19=$(cd "$TMPDIR_19/local" && ./.aitask-scripts/aitask_lock.sh --check 50 2>/dev/null)
assert_contains_ci "Bare ID used explicit email" "locked_by: explicit@test.com" "$check_output_19"

rm -rf "$TMPDIR_19"

# --- Test 20: No remote = lock is no-op ---
echo "--- Test 20: No remote = lock is no-op ---"

TMPDIR_20="$(mktemp -d)"
(
    cd "$TMPDIR_20"
    git init --quiet
    git config user.email "test@test.com"
    git config user.name "Test"
    mkdir -p aitasks/metadata
    setup_fake_aitask_repo "$PWD"
    echo "email: user@test.com" > aitasks/metadata/userconfig.yaml
    cp "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/aitask_lock.sh
    echo "init" > dummy.txt && git add dummy.txt && git commit -m "init" --quiet
)
assert_exit_zero "Lock with no remote is no-op" bash -c "cd '$TMPDIR_20' && ./.aitask-scripts/aitask_lock.sh --lock 1 --email user@test.com"

rm -rf "$TMPDIR_20"

# --- Test 21: No remote = check returns not-locked ---
echo "--- Test 21: No remote = check returns not-locked ---"

TMPDIR_21="$(mktemp -d)"
(
    cd "$TMPDIR_21"
    git init --quiet
    git config user.email "test@test.com"
    git config user.name "Test"
    mkdir -p aitasks/metadata
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/aitask_lock.sh
    echo "init" > dummy.txt && git add dummy.txt && git commit -m "init" --quiet
)
assert_exit_nonzero "Check with no remote returns not-locked" bash -c "cd '$TMPDIR_21' && ./.aitask-scripts/aitask_lock.sh --check 1"

rm -rf "$TMPDIR_21"

# --- Test 22: No remote = list shows no locks ---
echo "--- Test 22: No remote = list shows no locks ---"

TMPDIR_22="$(mktemp -d)"
(
    cd "$TMPDIR_22"
    git init --quiet
    git config user.email "test@test.com"
    git config user.name "Test"
    mkdir -p aitasks/metadata
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/aitask_lock.sh
    echo "init" > dummy.txt && git add dummy.txt && git commit -m "init" --quiet
)
list_output_22=$(cd "$TMPDIR_22" && ./.aitask-scripts/aitask_lock.sh --list 2>&1)
assert_contains_ci "List with no remote mentions no remote" "no remote" "$list_output_22"

rm -rf "$TMPDIR_22"

# --- Test 23: No remote = init still fails ---
echo "--- Test 23: No remote = init still fails ---"

TMPDIR_23="$(mktemp -d)"
(
    cd "$TMPDIR_23"
    git init --quiet
    git config user.email "test@test.com"
    git config user.name "Test"
    mkdir -p aitasks/metadata
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/aitask_lock.sh
    echo "init" > dummy.txt && git add dummy.txt && git commit -m "init" --quiet
)
assert_exit_nonzero "Init with no remote fails" bash -c "cd '$TMPDIR_23' && ./.aitask-scripts/aitask_lock.sh --init"

rm -rf "$TMPDIR_23"

# --- Test 24: Lock with branch missing on remote returns LOCK_INFRA_MISSING (exit 10) ---
echo "--- Test 24: Lock with missing branch returns exit 10 (LOCK_INFRA_MISSING) ---"

TMPDIR_24="$(setup_paired_repos)"
# Note: remote+local are set up, but --init is NOT called, so aitask-locks
# does not exist on remote. The previous behavior was exit 11 (fetch_failed);
# the new probe should distinguish this and return exit 10.

stderr_file_24="$(mktemp "${TMPDIR:-/tmp}/ait_test24_XXXXXX")"
(cd "$TMPDIR_24/local" && ./.aitask-scripts/aitask_lock.sh 1 --email "user@test.com" 2>"$stderr_file_24" >/dev/null)
rc=$?
stderr=$(cat "$stderr_file_24")
rm -f "$stderr_file_24"

assert_eq "Lock with missing branch exits 10 (LOCK_INFRA_MISSING)" "10" "$rc"
assert_contains_ci "Stderr explains branch missing" "not found on remote" "$stderr"

rm -rf "$TMPDIR_24"

# --- Summary ---
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
