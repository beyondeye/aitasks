#!/usr/bin/env bash
# test_parallel_child_create.sh - Tests for parallel child task creation locking
# Run: bash tests/test_parallel_child_create.sh
#
# Verifies that concurrent aitask_create.sh --batch --parent N --commit calls
# produce unique child numbers without race conditions.

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
    if echo "$actual" | grep -qF "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

# Set up a local git repo with the aitask scripts and a parent task
setup_test_repo() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    (
        cd "$tmpdir"
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"

        # Create task directory structure
        mkdir -p aitasks/metadata
        echo "ui" > aitasks/metadata/labels.txt

        # Create a parent task file
        cat > aitasks/t100_test_parent.md << 'TASK'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [ui]
created_at: 2026-03-22 10:00
updated_at: 2026-03-22 10:00
---

Test parent task for parallel child creation.
TASK

        # Copy all scripts needed by aitask_create.sh
        mkdir -p .aitask-scripts/lib
        cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_ls.sh" .aitask-scripts/ 2>/dev/null || true
        cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
        chmod +x .aitask-scripts/*.sh

        git add -A
        git commit -m "Initial setup" --quiet
    )

    echo "$tmpdir"
}

# Clean up stale locks that might interfere with tests
cleanup_locks() {
    rmdir /tmp/aitask_child_lock_100 2>/dev/null || true
}

# Disable strict mode for test error handling
set +e

echo "=== Parallel Child Task Creation Tests ==="
echo ""

# --- Test 1: Sequential child creation works ---
echo "--- Test 1: Sequential child creation (baseline) ---"

cleanup_locks
TMPDIR_1="$(setup_test_repo)"

# Create 3 children sequentially
for i in 1 2 3; do
    output=$(cd "$TMPDIR_1" && ./.aitask-scripts/aitask_create.sh --batch --parent 100 \
        --name "child_task_$i" --type feature --priority medium --effort low \
        --desc "Child task $i" --commit 2>&1)
done

# Check that all 3 unique child files exist
child_count=$(ls "$TMPDIR_1/aitasks/t100/"t100_*_*.md 2>/dev/null | wc -l | tr -d ' ')
assert_eq "Sequential: 3 child files created" "3" "$child_count"

# Check unique numbering
assert_eq "Sequential: child 1 exists" "1" "$(ls "$TMPDIR_1/aitasks/t100/"t100_1_*.md 2>/dev/null | wc -l | tr -d ' ')"
assert_eq "Sequential: child 2 exists" "1" "$(ls "$TMPDIR_1/aitasks/t100/"t100_2_*.md 2>/dev/null | wc -l | tr -d ' ')"
assert_eq "Sequential: child 3 exists" "1" "$(ls "$TMPDIR_1/aitasks/t100/"t100_3_*.md 2>/dev/null | wc -l | tr -d ' ')"

# Check parent has all children in children_to_implement
parent_content=$(cat "$TMPDIR_1/aitasks/t100_test_parent.md")
assert_contains "Sequential: parent has t100_1" "t100_1" "$parent_content"
assert_contains "Sequential: parent has t100_2" "t100_2" "$parent_content"
assert_contains "Sequential: parent has t100_3" "t100_3" "$parent_content"

rm -rf "$TMPDIR_1"
echo ""

# --- Test 2: Parallel child creation produces unique IDs ---
echo "--- Test 2: Parallel child creation (5 concurrent) ---"

cleanup_locks
TMPDIR_2="$(setup_test_repo)"

# Launch 5 parallel child creations
pids=()
for i in 1 2 3 4 5; do
    (cd "$TMPDIR_2" && ./.aitask-scripts/aitask_create.sh --batch --parent 100 \
        --name "parallel_task_$i" --type feature --priority medium --effort low \
        --desc "Parallel child task $i" --commit 2>/dev/null) &
    pids+=($!)
done

# Wait for all to complete, track failures
failures=0
for pid in "${pids[@]}"; do
    if ! wait "$pid"; then
        failures=$((failures + 1))
    fi
done

assert_eq "Parallel: no process failures" "0" "$failures"

# Count unique child files
child_count=$(ls "$TMPDIR_2/aitasks/t100/"t100_*_*.md 2>/dev/null | wc -l | tr -d ' ')
assert_eq "Parallel: 5 child files created" "5" "$child_count"

# Extract all child numbers and check uniqueness
child_numbers=$(ls "$TMPDIR_2/aitasks/t100/"t100_*_*.md 2>/dev/null \
    | xargs -I{} basename {} | grep -oE "^t100_[0-9]+" | sed 's/t100_//' | sort -n)
unique_count=$(echo "$child_numbers" | sort -u | wc -l | tr -d ' ')
assert_eq "Parallel: all child numbers unique" "5" "$unique_count"

# Check sequential numbering (1 through 5)
expected_nums="1
2
3
4
5"
assert_eq "Parallel: child numbers are 1-5" "$expected_nums" "$child_numbers"

# Check parent has all children
parent_content=$(cat "$TMPDIR_2/aitasks/t100_test_parent.md")
for i in 1 2 3 4 5; do
    assert_contains "Parallel: parent has t100_$i" "t100_$i" "$parent_content"
done

# Check git log has 5 child commits (plus initial)
commit_count=$(cd "$TMPDIR_2" && git log --oneline | grep -c "Add child task")
assert_eq "Parallel: 5 child commits in git log" "5" "$commit_count"

rm -rf "$TMPDIR_2"
echo ""

# --- Test 3: Stale lock is cleaned up ---
echo "--- Test 3: Stale lock cleanup ---"

cleanup_locks
TMPDIR_3="$(setup_test_repo)"

# Create a stale lock (set modification time to 200 seconds ago)
mkdir -p /tmp/aitask_child_lock_100
touch -d "200 seconds ago" /tmp/aitask_child_lock_100 2>/dev/null || \
    touch -t "$(date -d '200 seconds ago' '+%Y%m%d%H%M.%S' 2>/dev/null || date -v-200S '+%Y%m%d%H%M.%S')" /tmp/aitask_child_lock_100

# Child creation should succeed despite stale lock
output=$(cd "$TMPDIR_3" && ./.aitask-scripts/aitask_create.sh --batch --parent 100 \
    --name "after_stale_lock" --type feature --priority medium --effort low \
    --desc "Created after stale lock cleanup" --commit 2>&1)
exit_code=$?

assert_eq "Stale lock: creation succeeded" "0" "$exit_code"
child_exists=$(ls "$TMPDIR_3/aitasks/t100/"t100_1_*.md 2>/dev/null | wc -l | tr -d ' ')
assert_eq "Stale lock: child file created" "1" "$child_exists"

cleanup_locks
rm -rf "$TMPDIR_3"
echo ""

# --- Test 4: Lock contention with delay ---
echo "--- Test 4: Lock contention (staggered start) ---"

cleanup_locks
TMPDIR_4="$(setup_test_repo)"

# Launch 3 children with slight stagger to ensure lock contention
(cd "$TMPDIR_4" && ./.aitask-scripts/aitask_create.sh --batch --parent 100 \
    --name "staggered_a" --type feature --priority medium --effort low \
    --desc "Staggered A" --commit 2>/dev/null) &
pid1=$!

sleep 0.1

(cd "$TMPDIR_4" && ./.aitask-scripts/aitask_create.sh --batch --parent 100 \
    --name "staggered_b" --type feature --priority medium --effort low \
    --desc "Staggered B" --commit 2>/dev/null) &
pid2=$!

sleep 0.1

(cd "$TMPDIR_4" && ./.aitask-scripts/aitask_create.sh --batch --parent 100 \
    --name "staggered_c" --type feature --priority medium --effort low \
    --desc "Staggered C" --commit 2>/dev/null) &
pid3=$!

wait "$pid1" "$pid2" "$pid3"

child_count=$(ls "$TMPDIR_4/aitasks/t100/"t100_*_*.md 2>/dev/null | wc -l | tr -d ' ')
assert_eq "Staggered: 3 child files created" "3" "$child_count"

child_numbers=$(ls "$TMPDIR_4/aitasks/t100/"t100_*_*.md 2>/dev/null \
    | xargs -I{} basename {} | grep -oE "^t100_[0-9]+" | sed 's/t100_//' | sort -n)
unique_count=$(echo "$child_numbers" | sort -u | wc -l | tr -d ' ')
assert_eq "Staggered: all child numbers unique" "3" "$unique_count"

cleanup_locks
rm -rf "$TMPDIR_4"
echo ""

# --- Summary ---
echo "=== Results: $PASS passed, $FAIL failed, $TOTAL total ==="

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
