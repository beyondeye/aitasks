#!/usr/bin/env bash
# test_lock_force.sh - Tests for --force flag in aitask_own.sh and structured exit codes
# Run: bash tests/test_lock_force.sh

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

assert_exit_code() {
    local desc="$1" expected_code="$2"
    shift 2
    TOTAL=$((TOTAL + 1))
    local actual_code=0
    "$@" >/dev/null 2>&1 || actual_code=$?
    if [[ "$expected_code" == "$actual_code" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected exit code $expected_code, got $actual_code)"
    fi
}

# Create a paired repo setup with full own.sh support
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
        mkdir -p aitasks/archived aitasks/metadata aiplans

        # Create a sample task file
        cat > aitasks/t1_test_task.md <<'TASK'
---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: []
created_at: 2026-01-01 00:00
updated_at: 2026-01-01 00:00
---

Test task for lock force tests.
TASK

        # Create emails file
        echo "alice@test.com" > aitasks/metadata/emails.txt

        # Copy the scripts we need
        mkdir -p aiscripts/lib
        cp "$PROJECT_DIR/aiscripts/aitask_lock.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/aitask_own.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/aitask_update.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh" aiscripts/lib/
        cp "$PROJECT_DIR/aiscripts/lib/task_utils.sh" aiscripts/lib/
        # Copy the ait dispatcher for task_git support
        cp "$PROJECT_DIR/ait" . 2>/dev/null || true
        chmod +x aiscripts/*.sh ait 2>/dev/null || true

        git add -A
        git commit -m "Initial setup" --quiet
        git push --quiet 2>/dev/null
    )

    echo "$tmpdir"
}

# Disable strict mode for test error handling
set +e

echo "=== Lock Force Tests ==="
echo ""

# --- Test 1: Force-lock when locked by another user ---
echo "--- Test 1: Force-lock when locked by another user ---"

TMPDIR_1="$(setup_paired_repos)"
(cd "$TMPDIR_1/local" && ./aiscripts/aitask_lock.sh --init >/dev/null 2>&1)
# Lock as alice
(cd "$TMPDIR_1/local" && ./aiscripts/aitask_lock.sh --lock 1 --email "alice@test.com" >/dev/null 2>&1)

# Force-own as bob
output1=$(cd "$TMPDIR_1/local" && ./aiscripts/aitask_own.sh 1 --force --email "bob@test.com" 2>&1)
exit1=$?

assert_eq "Force-lock exits 0" "0" "$exit1"
assert_contains "Output has FORCE_UNLOCKED" "FORCE_UNLOCKED:alice@test.com" "$output1"
assert_contains "Output has OWNED" "OWNED:1" "$output1"

rm -rf "$TMPDIR_1"

# --- Test 2: No force when locked ---
echo "--- Test 2: No force when locked (LOCK_FAILED) ---"

TMPDIR_2="$(setup_paired_repos)"
(cd "$TMPDIR_2/local" && ./aiscripts/aitask_lock.sh --init >/dev/null 2>&1)
# Lock as alice
(cd "$TMPDIR_2/local" && ./aiscripts/aitask_lock.sh --lock 1 --email "alice@test.com" >/dev/null 2>&1)

# Try to own as bob without --force
output2=$(cd "$TMPDIR_2/local" && ./aiscripts/aitask_own.sh 1 --email "bob@test.com" 2>&1)
exit2=$?

assert_eq "No-force exits non-zero" "1" "$exit2"
assert_contains "Output has LOCK_FAILED" "LOCK_FAILED:alice@test.com" "$output2"

rm -rf "$TMPDIR_2"

# --- Test 3: Force when not locked (no FORCE_UNLOCKED) ---
echo "--- Test 3: Force when not locked ---"

TMPDIR_3="$(setup_paired_repos)"
(cd "$TMPDIR_3/local" && ./aiscripts/aitask_lock.sh --init >/dev/null 2>&1)

# Force-own on unlocked task
output3=$(cd "$TMPDIR_3/local" && ./aiscripts/aitask_own.sh 1 --force --email "bob@test.com" 2>&1)
exit3=$?

assert_eq "Force on unlocked exits 0" "0" "$exit3"
assert_contains "Output has OWNED" "OWNED:1" "$output3"

# Should NOT have FORCE_UNLOCKED since lock was not held
TOTAL=$((TOTAL + 1))
if echo "$output3" | grep -q "FORCE_UNLOCKED"; then
    FAIL=$((FAIL + 1))
    echo "FAIL: Force on unlocked should not have FORCE_UNLOCKED"
else
    PASS=$((PASS + 1))
fi

rm -rf "$TMPDIR_3"

# --- Test 4: Exit code 10 (no remote) ---
echo "--- Test 4: Exit code 10 (no remote) ---"

TMPDIR_4="$(setup_paired_repos)"
(cd "$TMPDIR_4/local" && ./aiscripts/aitask_lock.sh --init >/dev/null 2>&1)
# Remove origin remote
(cd "$TMPDIR_4/local" && git remote remove origin)

assert_exit_code "Lock without remote exits 10" 10 bash -c "cd '$TMPDIR_4/local' && ./aiscripts/aitask_lock.sh --lock 1 --email 'user@test.com'"

rm -rf "$TMPDIR_4"

# --- Test 5: LOCK_ERROR classification from aitask_own.sh ---
echo "--- Test 5: LOCK_ERROR classification ---"

# We test this indirectly by removing the remote after init
# so fetch fails (exit 11) which aitask_own.sh should classify as LOCK_ERROR
TMPDIR_5="$(setup_paired_repos)"
(cd "$TMPDIR_5/local" && ./aiscripts/aitask_lock.sh --init >/dev/null 2>&1)

# Point origin to a non-existent remote to cause fetch failure
(cd "$TMPDIR_5/local" && git remote set-url origin /nonexistent/path.git)

output5=$(cd "$TMPDIR_5/local" && ./aiscripts/aitask_own.sh 1 --email "bob@test.com" 2>&1)
exit5=$?

assert_eq "LOCK_ERROR exits non-zero" "1" "$exit5"
assert_contains "Output has LOCK_ERROR" "LOCK_ERROR" "$output5"

rm -rf "$TMPDIR_5"

# --- Test 6: die_code exit codes in aitask_lock.sh ---
echo "--- Test 6: die_code structured exit codes ---"

TMPDIR_6="$(setup_paired_repos)"
(cd "$TMPDIR_6/local" && ./aiscripts/aitask_lock.sh --init >/dev/null 2>&1)

# Exit 10: remove remote
(cd "$TMPDIR_6/local" && git remote remove origin)
assert_exit_code "require_remote gives exit 10" 10 bash -c "cd '$TMPDIR_6/local' && ./aiscripts/aitask_lock.sh --lock 1 --email 'user@test.com'"
assert_exit_code "unlock require_remote gives exit 10" 10 bash -c "cd '$TMPDIR_6/local' && ./aiscripts/aitask_lock.sh --unlock 1"

rm -rf "$TMPDIR_6"

# --- Test 7: Syntax check ---
echo "--- Test 7: Syntax checks ---"

assert_exit_code "aitask_lock.sh syntax ok" 0 bash -n "$PROJECT_DIR/aiscripts/aitask_lock.sh"
assert_exit_code "aitask_own.sh syntax ok" 0 bash -n "$PROJECT_DIR/aiscripts/aitask_own.sh"
assert_exit_code "terminal_compat.sh syntax ok" 0 bash -n "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh"

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
