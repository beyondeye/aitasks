#!/usr/bin/env bash
# test_query.sh - Automated tests for aitask_query_files.sh
# Run: bash tests/test_query.sh

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
    if echo "$actual" | grep -q "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -q "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output NOT containing '$unexpected', got '$actual')"
    else
        PASS=$((PASS + 1))
    fi
}

assert_line_count() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    local count
    count=$(echo "$actual" | wc -l | tr -d ' ')
    if [[ "$count" -eq "$expected" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected $expected lines, got $count)"
    fi
}

# --- Setup mock directory structure ---

TMPDIR_BASE=$(mktemp -d "${TMPDIR:-/tmp}/test_query_XXXXXX")
trap 'rm -rf "$TMPDIR_BASE"' EXIT

setup_mock() {
    local base="$TMPDIR_BASE/repo"
    rm -rf "$base"
    mkdir -p "$base"

    # Active tasks
    mkdir -p "$base/aitasks"
    echo "---\nstatus: Ready\n---\nParent task 16" > "$base/aitasks/t16_implement_auth.md"
    echo "---\nstatus: Ready\n---\nTask 42" > "$base/aitasks/t42_fix_bug.md"

    # Parent with children
    mkdir -p "$base/aitasks/t16"
    echo "---\nstatus: Ready\n---\nChild 1" > "$base/aitasks/t16/t16_1_setup_oauth.md"
    echo "---\nstatus: Ready\n---\nChild 2" > "$base/aitasks/t16/t16_2_add_login.md"
    echo "---\nstatus: Ready\n---\nChild 3" > "$base/aitasks/t16/t16_3_add_logout.md"

    # Active plans
    mkdir -p "$base/aiplans"
    echo "---\nTask: t16_implement_auth.md\n---\nPlan" > "$base/aiplans/p16_implement_auth.md"
    mkdir -p "$base/aiplans/p16"
    echo "---\nPlan child 1\n---" > "$base/aiplans/p16/p16_1_setup_oauth.md"

    # Archived tasks
    mkdir -p "$base/aitasks/archived/t10"
    echo "---\nstatus: Done\n---\nArchived child" > "$base/aitasks/archived/t10/t10_1_first_task.md"
    echo "---\nstatus: Done\n---\nArchived child 2" > "$base/aitasks/archived/t10/t10_2_second_task.md"

    # Archived plans
    mkdir -p "$base/aiplans/archived/p10"
    echo "---\nPlan\n---" > "$base/aiplans/archived/p10/p10_1_first_task.md"

    # Parent with children for sibling-context testing
    mkdir -p "$base/aitasks/t10"
    echo "---\nstatus: Ready\n---\nPending sibling" > "$base/aitasks/t10/t10_3_third_task.md"
    mkdir -p "$base/aiplans/p10"
    echo "---\nPlan\n---" > "$base/aiplans/p10/p10_3_third_task.md"

    echo "$base"
}

BASE=$(setup_mock)
QUERY="$PROJECT_DIR/aiscripts/aitask_query_files.sh"

# Override directory variables for testing
export TASK_DIR="$BASE/aitasks"
export PLAN_DIR="$BASE/aiplans"
export ARCHIVED_DIR="$BASE/aitasks/archived"
export ARCHIVED_PLAN_DIR="$BASE/aiplans/archived"

# ============================================================
# Tests: task-file
# ============================================================

echo "--- task-file ---"

out=$("$QUERY" task-file 16)
assert_contains "task-file 16 found" "TASK_FILE:" "$out"
assert_contains "task-file 16 path" "t16_implement_auth.md" "$out"

out=$("$QUERY" task-file t42)
assert_contains "task-file t42 with prefix" "TASK_FILE:" "$out"
assert_contains "task-file t42 path" "t42_fix_bug.md" "$out"

out=$("$QUERY" task-file 999)
assert_eq "task-file 999 not found" "NOT_FOUND" "$out"

# ============================================================
# Tests: has-children
# ============================================================

echo "--- has-children ---"

out=$("$QUERY" has-children 16)
assert_contains "has-children 16" "HAS_CHILDREN:3" "$out"

out=$("$QUERY" has-children 42)
assert_eq "has-children 42 no children" "NO_CHILDREN" "$out"

out=$("$QUERY" has-children 999)
assert_eq "has-children 999 no dir" "NO_CHILDREN" "$out"

# Edge case: empty children directory (dir exists but no matching .md files)
mkdir -p "$BASE/aitasks/t99"
out=$("$QUERY" has-children 99)
assert_eq "has-children 99 empty dir" "NO_CHILDREN" "$out"

# ============================================================
# Tests: child-file
# ============================================================

echo "--- child-file ---"

out=$("$QUERY" child-file 16 2)
assert_contains "child-file 16 2 found" "CHILD_FILE:" "$out"
assert_contains "child-file 16 2 path" "t16_2_add_login.md" "$out"

out=$("$QUERY" child-file 16 99)
assert_eq "child-file 16 99 not found" "NOT_FOUND" "$out"

out=$("$QUERY" child-file t16 t2)
assert_contains "child-file with t prefix" "CHILD_FILE:" "$out"

# ============================================================
# Tests: sibling-context
# ============================================================

echo "--- sibling-context ---"

out=$("$QUERY" sibling-context 10)
assert_contains "sibling-context 10 has archived plan" "ARCHIVED_PLAN:" "$out"
assert_contains "sibling-context 10 archived plan file" "p10_1_first_task.md" "$out"
assert_contains "sibling-context 10 has archived task" "ARCHIVED_TASK:" "$out"
assert_contains "sibling-context 10 has pending sibling" "PENDING_SIBLING:" "$out"
assert_contains "sibling-context 10 has pending plan" "PENDING_PLAN:" "$out"

out=$("$QUERY" sibling-context 999)
assert_eq "sibling-context 999 no context" "NO_CONTEXT" "$out"

# ============================================================
# Tests: plan-file
# ============================================================

echo "--- plan-file ---"

out=$("$QUERY" plan-file 16)
assert_contains "plan-file 16 found" "PLAN_FILE:" "$out"
assert_contains "plan-file 16 path" "p16_implement_auth.md" "$out"

out=$("$QUERY" plan-file 16_1)
assert_contains "plan-file 16_1 child found" "PLAN_FILE:" "$out"
assert_contains "plan-file 16_1 child path" "p16_1_setup_oauth.md" "$out"

out=$("$QUERY" plan-file 999)
assert_eq "plan-file 999 not found" "NOT_FOUND" "$out"

out=$("$QUERY" plan-file 16_99)
assert_eq "plan-file 16_99 not found" "NOT_FOUND" "$out"

# ============================================================
# Tests: archived-children
# ============================================================

echo "--- archived-children ---"

out=$("$QUERY" archived-children 10)
assert_contains "archived-children 10 has children" "ARCHIVED_CHILD:" "$out"
assert_contains "archived-children 10 first child" "t10_1_first_task.md" "$out"
assert_contains "archived-children 10 second child" "t10_2_second_task.md" "$out"

out=$("$QUERY" archived-children 999)
assert_eq "archived-children 999 none" "NO_ARCHIVED_CHILDREN" "$out"

# ============================================================
# Tests: resolve
# ============================================================

echo "--- resolve ---"

out=$("$QUERY" resolve 16)
assert_contains "resolve 16 task file" "TASK_FILE:" "$out"
assert_contains "resolve 16 has children" "HAS_CHILDREN:3" "$out"

out=$("$QUERY" resolve 42)
assert_contains "resolve 42 task file" "TASK_FILE:" "$out"
assert_contains "resolve 42 no children" "NO_CHILDREN" "$out"

out=$("$QUERY" resolve 999)
assert_eq "resolve 999 not found" "NOT_FOUND" "$out"

# ============================================================
# Tests: active-children
# ============================================================

echo "--- active-children ---"

out=$("$QUERY" active-children 16)
assert_contains "active-children 16 has child 1" "CHILD:" "$out"
assert_contains "active-children 16 child 1 path" "t16_1_setup_oauth.md" "$out"
assert_contains "active-children 16 child 2 path" "t16_2_add_login.md" "$out"
assert_contains "active-children 16 child 3 path" "t16_3_add_logout.md" "$out"
assert_line_count "active-children 16 returns 3 lines" 3 "$out"

out=$("$QUERY" active-children 42)
assert_eq "active-children 42 no children" "NO_CHILDREN" "$out"

out=$("$QUERY" active-children 999)
assert_eq "active-children 999 no dir" "NO_CHILDREN" "$out"

out=$("$QUERY" active-children 99)
assert_eq "active-children 99 empty dir" "NO_CHILDREN" "$out"

# ============================================================
# Tests: all-children
# ============================================================

echo "--- all-children ---"

# Task 10 has archived children (t10_1, t10_2) and active child (t10_3)
out=$("$QUERY" all-children 10)
assert_contains "all-children 10 has active child" "CHILD:" "$out"
assert_contains "all-children 10 active child path" "t10_3_third_task.md" "$out"
assert_contains "all-children 10 has archived child" "ARCHIVED_CHILD:" "$out"
assert_contains "all-children 10 archived child 1" "t10_1_first_task.md" "$out"
assert_contains "all-children 10 archived child 2" "t10_2_second_task.md" "$out"
assert_line_count "all-children 10 returns 3 lines" 3 "$out"

# Task 16 has only active children
out=$("$QUERY" all-children 16)
assert_contains "all-children 16 has active children" "CHILD:" "$out"
assert_not_contains "all-children 16 no archived" "ARCHIVED_CHILD:" "$out"
assert_line_count "all-children 16 returns 3 lines" 3 "$out"

# Task with no children at all
out=$("$QUERY" all-children 42)
assert_eq "all-children 42 no children" "NO_CHILDREN" "$out"

out=$("$QUERY" all-children 999)
assert_eq "all-children 999 no dir" "NO_CHILDREN" "$out"

# ============================================================
# Tests: input validation
# ============================================================

echo "--- input validation ---"

out=$("$QUERY" task-file abc 2>&1 || true)
assert_contains "invalid input rejected" "Invalid" "$out"

out=$("$QUERY" --help 2>&1)
assert_contains "help shows usage" "Usage:" "$out"
assert_contains "help shows active-children" "active-children" "$out"
assert_contains "help shows all-children" "all-children" "$out"

# ============================================================
# Summary
# ============================================================

echo ""
echo "=============================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=============================="

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
