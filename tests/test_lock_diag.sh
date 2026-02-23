#!/usr/bin/env bash
# test_lock_diag.sh - Tests for aitask_lock_diag.sh diagnostic script
# Run: bash tests/test_lock_diag.sh

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

# Create a paired repo setup
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

        mkdir -p aitasks/archived aiscripts/lib
        cp "$PROJECT_DIR/aiscripts/aitask_lock.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/aitask_lock_diag.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh" aiscripts/lib/
        chmod +x aiscripts/*.sh

        git add -A
        git commit -m "Initial setup" --quiet
        git push --quiet 2>/dev/null
    )

    echo "$tmpdir"
}

# Disable strict mode for test error handling
set +e

echo "=== Lock Diagnostic Tests ==="
echo ""

# --- Test 1: Syntax check ---
echo "--- Test 1: Syntax check ---"

assert_exit_code "aitask_lock_diag.sh syntax ok" 0 bash -n "$PROJECT_DIR/aiscripts/aitask_lock_diag.sh"

# --- Test 2: Run in paired repo with initialized lock branch ---
echo "--- Test 2: All checks pass with initialized lock branch ---"

TMPDIR_2="$(setup_paired_repos)"
(cd "$TMPDIR_2/local" && ./aiscripts/aitask_lock.sh --init >/dev/null 2>&1)

output2=$(cd "$TMPDIR_2/local" && ./aiscripts/aitask_lock_diag.sh 2>&1)
exit2=$?

assert_eq "Diag exits 0 with initialized locks" "0" "$exit2"
assert_contains "Shows ALL CHECKS PASSED" "ALL CHECKS PASSED" "$output2"
assert_contains "Git check passes" "PASS.*Git available" "$output2"
assert_contains "Remote check passes" "PASS.*Origin remote" "$output2"
assert_contains "Lock branch check passes" "PASS.*Lock branch" "$output2"

rm -rf "$TMPDIR_2"

# --- Test 3: Run without lock branch (some checks fail) ---
echo "--- Test 3: Failures without lock branch ---"

TMPDIR_3="$(setup_paired_repos)"
# Do NOT init lock branch

output3=$(cd "$TMPDIR_3/local" && ./aiscripts/aitask_lock_diag.sh 2>&1)
exit3=$?

assert_eq "Diag exits 1 without lock branch" "1" "$exit3"
assert_contains "Shows SOME CHECKS FAILED" "SOME CHECKS FAILED" "$output3"
assert_contains "Lock branch check fails" "FAIL.*Lock branch" "$output3"

rm -rf "$TMPDIR_3"

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
