#!/usr/bin/env bash
# test_task_lock.sh - Automated tests for aitask_lock.sh
# Run: bash tests/test_task_lock.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qi "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

assert_exit_zero() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (command exited non-zero)"
    fi
}

assert_exit_nonzero() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected non-zero exit, got 0)"
    else
        PASS=$((PASS + 1))
    fi
}

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
        mkdir -p aiscripts/lib
        cp "$PROJECT_DIR/aiscripts/aitask_lock.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh" aiscripts/lib/
        chmod +x aiscripts/aitask_lock.sh

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
        mkdir -p aiscripts/lib
        cp "$PROJECT_DIR/aiscripts/aitask_lock.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh" aiscripts/lib/
        chmod +x aiscripts/aitask_lock.sh
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
output=$(cd "$TMPDIR_1/local" && ./aiscripts/aitask_lock.sh --init 2>&1)

# Branch should exist on remote
branch_exists=$(git -C "$TMPDIR_1/local" ls-remote --heads origin aitask-locks 2>/dev/null | grep -c "aitask-locks")
assert_eq "Branch exists on remote" "1" "$branch_exists"

assert_contains "Output mentions created" "created" "$output"

rm -rf "$TMPDIR_1"

# --- Test 2: Init is idempotent ---
echo "--- Test 2: Init is idempotent ---"

TMPDIR_2="$(setup_paired_repos)"
(cd "$TMPDIR_2/local" && ./aiscripts/aitask_lock.sh --init >/dev/null 2>&1)
output2=$(cd "$TMPDIR_2/local" && ./aiscripts/aitask_lock.sh --init 2>&1)

assert_contains "Idempotent init says already exists" "already exists" "$output2"

rm -rf "$TMPDIR_2"

# --- Test 3: Lock creates lock file ---
echo "--- Test 3: Lock creates lock file ---"

TMPDIR_3="$(setup_paired_repos)"
(cd "$TMPDIR_3/local" && ./aiscripts/aitask_lock.sh --init >/dev/null 2>&1)
(cd "$TMPDIR_3/local" && ./aiscripts/aitask_lock.sh --lock 1 --email "user@test.com" >/dev/null 2>&1)

# Verify lock file exists in branch tree
lock_exists=$(cd "$TMPDIR_3/local" && git fetch origin aitask-locks --quiet 2>/dev/null && git ls-tree "origin/aitask-locks" 2>/dev/null | grep -c "t1_lock.yaml")
assert_eq "Lock file exists in branch tree" "1" "$lock_exists"

rm -rf "$TMPDIR_3"

# --- Test 4: Lock file YAML content ---
echo "--- Test 4: Lock file YAML content ---"

TMPDIR_4="$(setup_paired_repos)"
(cd "$TMPDIR_4/local" && ./aiscripts/aitask_lock.sh --init >/dev/null 2>&1)
(cd "$TMPDIR_4/local" && ./aiscripts/aitask_lock.sh --lock 42 --email "alice@example.com" >/dev/null 2>&1)

lock_content=$(cd "$TMPDIR_4/local" && git fetch origin aitask-locks --quiet 2>/dev/null && git show "origin/aitask-locks:t42_lock.yaml" 2>/dev/null)
assert_contains "YAML has task_id" "task_id: 42" "$lock_content"
assert_contains "YAML has locked_by" "locked_by: alice@example.com" "$lock_content"
assert_contains "YAML has locked_at" "locked_at:" "$lock_content"
assert_contains "YAML has hostname" "hostname:" "$lock_content"

rm -rf "$TMPDIR_4"

# --- Test 5: Check returns 0 for locked task ---
echo "--- Test 5: Check returns 0 for locked task ---"

TMPDIR_5="$(setup_paired_repos)"
(cd "$TMPDIR_5/local" && ./aiscripts/aitask_lock.sh --init >/dev/null 2>&1)
(cd "$TMPDIR_5/local" && ./aiscripts/aitask_lock.sh --lock 1 --email "user@test.com" >/dev/null 2>&1)

assert_exit_zero "Check locked task exits 0" bash -c "cd '$TMPDIR_5/local' && ./aiscripts/aitask_lock.sh --check 1"

# Also verify it outputs content
check_output=$(cd "$TMPDIR_5/local" && ./aiscripts/aitask_lock.sh --check 1 2>/dev/null)
assert_contains "Check outputs lock info" "locked_by: user@test.com" "$check_output"

rm -rf "$TMPDIR_5"

# --- Test 6: Check returns 1 for unlocked task ---
echo "--- Test 6: Check returns 1 for unlocked task ---"

TMPDIR_6="$(setup_paired_repos)"
(cd "$TMPDIR_6/local" && ./aiscripts/aitask_lock.sh --init >/dev/null 2>&1)

assert_exit_nonzero "Check unlocked task exits non-zero" bash -c "cd '$TMPDIR_6/local' && ./aiscripts/aitask_lock.sh --check 99"

rm -rf "$TMPDIR_6"

# --- Test 7: Unlock removes lock file ---
echo "--- Test 7: Unlock removes lock file ---"

TMPDIR_7="$(setup_paired_repos)"
(cd "$TMPDIR_7/local" && ./aiscripts/aitask_lock.sh --init >/dev/null 2>&1)
(cd "$TMPDIR_7/local" && ./aiscripts/aitask_lock.sh --lock 1 --email "user@test.com" >/dev/null 2>&1)
(cd "$TMPDIR_7/local" && ./aiscripts/aitask_lock.sh --unlock 1 >/dev/null 2>&1)

# Verify lock file is gone
lock_gone=$(cd "$TMPDIR_7/local" && git fetch origin aitask-locks --quiet 2>/dev/null && git ls-tree "origin/aitask-locks" 2>/dev/null | grep -c "t1_lock.yaml")
assert_eq "Lock file removed after unlock" "0" "$lock_gone"

rm -rf "$TMPDIR_7"

# --- Test 8: Unlock is idempotent ---
echo "--- Test 8: Unlock is idempotent ---"

TMPDIR_8="$(setup_paired_repos)"
(cd "$TMPDIR_8/local" && ./aiscripts/aitask_lock.sh --init >/dev/null 2>&1)

# Unlock a task that was never locked — should succeed
assert_exit_zero "Unlock never-locked task exits 0" bash -c "cd '$TMPDIR_8/local' && ./aiscripts/aitask_lock.sh --unlock 99"

rm -rf "$TMPDIR_8"

# --- Test 9: Same email re-lock succeeds (refresh) ---
echo "--- Test 9: Same email re-lock succeeds ---"

TMPDIR_9="$(setup_paired_repos)"
(cd "$TMPDIR_9/local" && ./aiscripts/aitask_lock.sh --init >/dev/null 2>&1)
(cd "$TMPDIR_9/local" && ./aiscripts/aitask_lock.sh --lock 1 --email "user@test.com" >/dev/null 2>&1)

# Re-lock with same email should succeed
assert_exit_zero "Re-lock with same email succeeds" bash -c "cd '$TMPDIR_9/local' && ./aiscripts/aitask_lock.sh --lock 1 --email 'user@test.com'"

rm -rf "$TMPDIR_9"

# --- Test 10: Different email lock fails ---
echo "--- Test 10: Different email lock fails ---"

TMPDIR_10="$(setup_paired_repos)"
(cd "$TMPDIR_10/local" && ./aiscripts/aitask_lock.sh --init >/dev/null 2>&1)
(cd "$TMPDIR_10/local" && ./aiscripts/aitask_lock.sh --lock 1 --email "alice@test.com" >/dev/null 2>&1)

# Lock with different email should fail
output10=$(cd "$TMPDIR_10/local" && ./aiscripts/aitask_lock.sh --lock 1 --email "bob@test.com" 2>&1 || true)
assert_exit_nonzero "Different email lock fails" bash -c "cd '$TMPDIR_10/local' && ./aiscripts/aitask_lock.sh --lock 1 --email 'bob@test.com'"
assert_contains "Error mentions existing locker" "alice@test.com" "$output10"

rm -rf "$TMPDIR_10"

# --- Test 11: Race simulation ---
echo "--- Test 11: Race simulation ---"

TMPDIR_11="$(setup_paired_repos)"
(cd "$TMPDIR_11/local" && ./aiscripts/aitask_lock.sh --init >/dev/null 2>&1)

local2_dir=$(clone_second_local "$TMPDIR_11")

# Two PCs try to lock the same task simultaneously
(cd "$TMPDIR_11/local" && ./aiscripts/aitask_lock.sh --lock 1 --email "pc1@test.com" 2>/dev/null) > "$TMPDIR_11/result1" 2>&1 &
pid1=$!
(cd "$local2_dir" && ./aiscripts/aitask_lock.sh --lock 1 --email "pc2@test.com" 2>/dev/null) > "$TMPDIR_11/result2" 2>&1 &
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
(cd "$TMPDIR_12/local" && ./aiscripts/aitask_lock.sh --init >/dev/null 2>&1)

# Lock task 1
(cd "$TMPDIR_12/local" && ./aiscripts/aitask_lock.sh --lock 1 --email "user@test.com" >/dev/null 2>&1)

# Create archived task file to mark it as stale
(
    cd "$TMPDIR_12/local"
    echo "---" > aitasks/archived/t1_test_task.md
    git add -A && git commit -m "Archive task" --quiet && git push --quiet 2>/dev/null
)

# Run cleanup
(cd "$TMPDIR_12/local" && ./aiscripts/aitask_lock.sh --cleanup >/dev/null 2>&1)

# Verify lock was removed
lock_after_cleanup=$(cd "$TMPDIR_12/local" && git fetch origin aitask-locks --quiet 2>/dev/null && git ls-tree "origin/aitask-locks" 2>/dev/null | grep -c "t1_lock.yaml")
assert_eq "Stale lock removed by cleanup" "0" "$lock_after_cleanup"

rm -rf "$TMPDIR_12"

# --- Test 13: List shows all locks ---
echo "--- Test 13: List shows all locks ---"

TMPDIR_13="$(setup_paired_repos)"
(cd "$TMPDIR_13/local" && ./aiscripts/aitask_lock.sh --init >/dev/null 2>&1)
(cd "$TMPDIR_13/local" && ./aiscripts/aitask_lock.sh --lock 1 --email "alice@test.com" >/dev/null 2>&1)
(cd "$TMPDIR_13/local" && ./aiscripts/aitask_lock.sh --lock 2 --email "bob@test.com" >/dev/null 2>&1)

list_output=$(cd "$TMPDIR_13/local" && ./aiscripts/aitask_lock.sh --list 2>/dev/null)
assert_contains "List shows task 1" "t1:" "$list_output"
assert_contains "List shows task 2" "t2:" "$list_output"

rm -rf "$TMPDIR_13"

# --- Test 14: Syntax check ---
echo "--- Test 14: Syntax check ---"

assert_exit_zero "Syntax check passes" bash -n "$PROJECT_DIR/aiscripts/aitask_lock.sh"

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
