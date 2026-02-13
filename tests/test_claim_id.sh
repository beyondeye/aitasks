#!/bin/bash
# test_claim_id.sh - Automated tests for aitask_claim_id.sh
# Run: bash tests/test_claim_id.sh

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

        # Create task directory structure with some tasks
        mkdir -p aitasks/archived
        echo "---" > aitasks/t1_first_task.md
        echo "---" > aitasks/t2_second_task.md
        echo "---" > aitasks/t3_third_task.md
        echo "---" > aitasks/t4_fourth_task.md
        echo "---" > aitasks/t5_fifth_task.md

        # Copy the scripts we need
        mkdir -p aiscripts/lib
        cp "$PROJECT_DIR/aiscripts/aitask_claim_id.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh" aiscripts/lib/
        chmod +x aiscripts/aitask_claim_id.sh

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
        cp "$PROJECT_DIR/aiscripts/aitask_claim_id.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh" aiscripts/lib/
        chmod +x aiscripts/aitask_claim_id.sh
    )

    echo "$local2_dir"
}

# Disable strict mode for test error handling
set +e

echo "=== aitask_claim_id.sh Tests ==="
echo ""

# --- Test 1: Init creates branch ---
echo "--- Test 1: Init creates branch ---"

TMPDIR_1="$(setup_paired_repos)"
output=$(cd "$TMPDIR_1/local" && ./aiscripts/aitask_claim_id.sh --init 2>&1)

# Branch should exist on remote
branch_exists=$(git -C "$TMPDIR_1/local" ls-remote --heads origin aitask-ids 2>/dev/null | grep -c "aitask-ids")
assert_eq "Branch exists on remote" "1" "$branch_exists"

# Counter should be max(5) + 10 = 15
counter_val=$(cd "$TMPDIR_1/local" && git fetch origin aitask-ids --quiet 2>/dev/null && git show origin/aitask-ids:next_id.txt 2>/dev/null | tr -d '[:space:]')
assert_eq "Counter initialized to max+10" "15" "$counter_val"

assert_contains "Output mentions counter value" "15" "$output"

rm -rf "$TMPDIR_1"

# --- Test 2: Init is idempotent ---
echo "--- Test 2: Init is idempotent ---"

TMPDIR_2="$(setup_paired_repos)"
(cd "$TMPDIR_2/local" && ./aiscripts/aitask_claim_id.sh --init >/dev/null 2>&1)
output2=$(cd "$TMPDIR_2/local" && ./aiscripts/aitask_claim_id.sh --init 2>&1)

assert_contains "Idempotent init says already exists" "already exists" "$output2"

rm -rf "$TMPDIR_2"

# --- Test 3: Claim returns correct ID ---
echo "--- Test 3: Claim returns correct ID ---"

TMPDIR_3="$(setup_paired_repos)"
(cd "$TMPDIR_3/local" && ./aiscripts/aitask_claim_id.sh --init >/dev/null 2>&1)
claimed=$(cd "$TMPDIR_3/local" && ./aiscripts/aitask_claim_id.sh --claim 2>/dev/null)
assert_eq "First claim returns 15" "15" "$claimed"

rm -rf "$TMPDIR_3"

# --- Test 4: Sequential claims ---
echo "--- Test 4: Sequential claims ---"

TMPDIR_4="$(setup_paired_repos)"
(cd "$TMPDIR_4/local" && ./aiscripts/aitask_claim_id.sh --init >/dev/null 2>&1)
c1=$(cd "$TMPDIR_4/local" && ./aiscripts/aitask_claim_id.sh --claim 2>/dev/null)
c2=$(cd "$TMPDIR_4/local" && ./aiscripts/aitask_claim_id.sh --claim 2>/dev/null)
c3=$(cd "$TMPDIR_4/local" && ./aiscripts/aitask_claim_id.sh --claim 2>/dev/null)
assert_eq "First sequential claim" "15" "$c1"
assert_eq "Second sequential claim" "16" "$c2"
assert_eq "Third sequential claim" "17" "$c3"

rm -rf "$TMPDIR_4"

# --- Test 5: Counter file integrity ---
echo "--- Test 5: Counter file integrity ---"

TMPDIR_5="$(setup_paired_repos)"
(cd "$TMPDIR_5/local" && ./aiscripts/aitask_claim_id.sh --init >/dev/null 2>&1)
(cd "$TMPDIR_5/local" && ./aiscripts/aitask_claim_id.sh --claim >/dev/null 2>&1)
(cd "$TMPDIR_5/local" && ./aiscripts/aitask_claim_id.sh --claim >/dev/null 2>&1)

counter_after=$(cd "$TMPDIR_5/local" && git fetch origin aitask-ids --quiet 2>/dev/null && git show origin/aitask-ids:next_id.txt 2>/dev/null | tr -d '[:space:]')
assert_eq "Counter is 17 after 2 claims from 15" "17" "$counter_after"

rm -rf "$TMPDIR_5"

# --- Test 6: Race simulation ---
echo "--- Test 6: Race simulation ---"

TMPDIR_6="$(setup_paired_repos)"
(cd "$TMPDIR_6/local" && ./aiscripts/aitask_claim_id.sh --init >/dev/null 2>&1)

local2_dir=$(clone_second_local "$TMPDIR_6")

# Run claims simultaneously from two "PCs"
(cd "$TMPDIR_6/local" && ./aiscripts/aitask_claim_id.sh --claim 2>/dev/null) > "$TMPDIR_6/result1" &
pid1=$!
(cd "$local2_dir" && ./aiscripts/aitask_claim_id.sh --claim 2>/dev/null) > "$TMPDIR_6/result2" &
pid2=$!

wait $pid1
wait $pid2

r1=$(cat "$TMPDIR_6/result1" | tr -d '[:space:]')
r2=$(cat "$TMPDIR_6/result2" | tr -d '[:space:]')

TOTAL=$((TOTAL + 1))
if [[ -n "$r1" && -n "$r2" && "$r1" != "$r2" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Race simulation - expected unique IDs, got '$r1' and '$r2'"
fi

rm -rf "$TMPDIR_6"

# --- Test 7: No remote = error ---
echo "--- Test 7: No remote = error ---"

TMPDIR_7="$(mktemp -d)"
(
    cd "$TMPDIR_7"
    git init --quiet
    git config user.email "test@test.com"
    git config user.name "Test"
    mkdir -p aiscripts/lib
    cp "$PROJECT_DIR/aiscripts/aitask_claim_id.sh" aiscripts/
    cp "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh" aiscripts/lib/
    chmod +x aiscripts/aitask_claim_id.sh
    echo "init" > dummy.txt && git add dummy.txt && git commit -m "init" --quiet
)
output7=$(cd "$TMPDIR_7" && ./aiscripts/aitask_claim_id.sh --claim 2>&1 || true)
assert_contains "No remote gives error" "remote" "$output7"

rm -rf "$TMPDIR_7"

# --- Test 8: Init scans archived tasks ---
echo "--- Test 8: Init scans archived tasks ---"

TMPDIR_8="$(setup_paired_repos)"
(
    cd "$TMPDIR_8/local"
    echo "---" > aitasks/archived/t50_archived_task.md
    git add -A && git commit -m "Add archived" --quiet && git push --quiet 2>/dev/null
)
output8=$(cd "$TMPDIR_8/local" && ./aiscripts/aitask_claim_id.sh --init 2>&1)
counter8=$(cd "$TMPDIR_8/local" && git fetch origin aitask-ids --quiet 2>/dev/null && git show origin/aitask-ids:next_id.txt 2>/dev/null | tr -d '[:space:]')
assert_eq "Counter scans archived: max(50)+10=60" "60" "$counter8"

rm -rf "$TMPDIR_8"

# --- Test 9: Init scans tar archive ---
echo "--- Test 9: Init scans tar archive ---"

TMPDIR_9="$(setup_paired_repos)"
(
    cd "$TMPDIR_9/local"
    mkdir -p /tmp/tartest_$$
    echo "---" > "/tmp/tartest_$$/t100_old_task.md"
    tar -czf aitasks/archived/old.tar.gz -C "/tmp/tartest_$$" t100_old_task.md
    rm -rf "/tmp/tartest_$$"
    git add -A && git commit -m "Add tar" --quiet && git push --quiet 2>/dev/null
)
output9=$(cd "$TMPDIR_9/local" && ./aiscripts/aitask_claim_id.sh --init 2>&1)
counter9=$(cd "$TMPDIR_9/local" && git fetch origin aitask-ids --quiet 2>/dev/null && git show origin/aitask-ids:next_id.txt 2>/dev/null | tr -d '[:space:]')
assert_eq "Counter scans tar: max(100)+10=110" "110" "$counter9"

rm -rf "$TMPDIR_9"

# --- Test 10: Syntax check ---
echo "--- Test 10: Syntax check ---"

assert_exit_zero "Syntax check passes" bash -n "$PROJECT_DIR/aiscripts/aitask_claim_id.sh"

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
