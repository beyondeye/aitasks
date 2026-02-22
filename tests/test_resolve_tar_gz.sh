#!/usr/bin/env bash
# test_resolve_tar_gz.sh - Automated tests for tar.gz fallback in resolve functions
# Run: bash tests/test_resolve_tar_gz.sh

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

# --- Setup helpers ---

# Create a standard test environment with task/plan directory structure
# Returns: path to the temp root directory
setup_test_env() {
    local tmpdir
    tmpdir=$(mktemp -d)

    mkdir -p "$tmpdir/aitasks/archived"
    mkdir -p "$tmpdir/aiplans/archived"

    echo "$tmpdir"
}

# Create a tar.gz archive mimicking aitask_zip_old.sh format (./prefix paths)
# Args: $1=archive_path, $2=source_dir (files to archive, relative structure preserved)
create_test_archive() {
    local archive_path="$1"
    local source_dir="$2"
    tar -czf "$archive_path" -C "$source_dir" .
}

# Source task_utils.sh with overridden directories pointing to test env
# Args: $1=tmpdir
# Must be called in the same shell (not subshell) where resolve functions will be used
source_task_utils() {
    local tmpdir="$1"
    export TASK_DIR="$tmpdir/aitasks"
    export ARCHIVED_DIR="$tmpdir/aitasks/archived"
    export PLAN_DIR="$tmpdir/aiplans"
    export ARCHIVED_PLAN_DIR="$tmpdir/aiplans/archived"
    export SCRIPT_DIR="$PROJECT_DIR/aiscripts"

    # Reset the guard so we can re-source with new directories
    unset _AIT_TASK_UTILS_LOADED
    # Reset temp dir from previous test
    if [[ -n "$_AIT_TASK_UTILS_TMPDIR" && -d "$_AIT_TASK_UTILS_TMPDIR" ]]; then
        rm -rf "$_AIT_TASK_UTILS_TMPDIR"
    fi
    _AIT_TASK_UTILS_TMPDIR=""

    source "$PROJECT_DIR/aiscripts/lib/task_utils.sh"
}

# --- Tests ---

echo "=== test_resolve_tar_gz.sh ==="
echo ""

# --- Test 1: Resolve parent task from active dir ---
echo "--- Test 1: Resolve parent task from active dir ---"
TMPDIR_1=$(setup_test_env)
echo "task 50 content" > "$TMPDIR_1/aitasks/t50_test_feature.md"
source_task_utils "$TMPDIR_1"
result=$(resolve_task_file "50")
assert_eq "Parent task resolved from active dir" "$TMPDIR_1/aitasks/t50_test_feature.md" "$result"
rm -rf "$TMPDIR_1"

# --- Test 2: Resolve parent task from archived dir ---
echo "--- Test 2: Resolve parent task from archived dir ---"
TMPDIR_2=$(setup_test_env)
echo "archived task 50 content" > "$TMPDIR_2/aitasks/archived/t50_test_feature.md"
source_task_utils "$TMPDIR_2"
result=$(resolve_task_file "50")
assert_eq "Parent task resolved from archived dir" "$TMPDIR_2/aitasks/archived/t50_test_feature.md" "$result"
rm -rf "$TMPDIR_2"

# --- Test 3: Resolve parent task from tar.gz ---
echo "--- Test 3: Resolve parent task from tar.gz ---"
TMPDIR_3=$(setup_test_env)
# Create tar.gz with a task file inside
staging=$(mktemp -d)
echo "tar task 50 content" > "$staging/t50_test_feature.md"
create_test_archive "$TMPDIR_3/aitasks/archived/old.tar.gz" "$staging"
rm -rf "$staging"
source_task_utils "$TMPDIR_3"
result=$(resolve_task_file "50")
actual_content=$(cat "$result")
assert_eq "Parent task from tar.gz has correct content" "tar task 50 content" "$actual_content"
rm -rf "$TMPDIR_3"

# --- Test 4: Resolve child task from active dir ---
echo "--- Test 4: Resolve child task from active dir ---"
TMPDIR_4=$(setup_test_env)
mkdir -p "$TMPDIR_4/aitasks/t10"
echo "child 10_2 content" > "$TMPDIR_4/aitasks/t10/t10_2_add_login.md"
source_task_utils "$TMPDIR_4"
result=$(resolve_task_file "10_2")
assert_eq "Child task resolved from active dir" "$TMPDIR_4/aitasks/t10/t10_2_add_login.md" "$result"
rm -rf "$TMPDIR_4"

# --- Test 5: Resolve child task from archived dir ---
echo "--- Test 5: Resolve child task from archived dir ---"
TMPDIR_5=$(setup_test_env)
mkdir -p "$TMPDIR_5/aitasks/archived/t10"
echo "archived child 10_2 content" > "$TMPDIR_5/aitasks/archived/t10/t10_2_add_login.md"
source_task_utils "$TMPDIR_5"
result=$(resolve_task_file "10_2")
assert_eq "Child task resolved from archived dir" "$TMPDIR_5/aitasks/archived/t10/t10_2_add_login.md" "$result"
rm -rf "$TMPDIR_5"

# --- Test 6: Resolve child task from tar.gz ---
echo "--- Test 6: Resolve child task from tar.gz ---"
TMPDIR_6=$(setup_test_env)
staging=$(mktemp -d)
mkdir -p "$staging/t10"
echo "tar child 10_2 content" > "$staging/t10/t10_2_add_login.md"
create_test_archive "$TMPDIR_6/aitasks/archived/old.tar.gz" "$staging"
rm -rf "$staging"
source_task_utils "$TMPDIR_6"
result=$(resolve_task_file "10_2")
actual_content=$(cat "$result")
assert_eq "Child task from tar.gz has correct content" "tar child 10_2 content" "$actual_content"
rm -rf "$TMPDIR_6"

# --- Test 7: Resolve parent plan from tar.gz ---
echo "--- Test 7: Resolve parent plan from tar.gz ---"
TMPDIR_7=$(setup_test_env)
staging=$(mktemp -d)
echo "tar plan 50 content" > "$staging/p50_test_feature.md"
create_test_archive "$TMPDIR_7/aiplans/archived/old.tar.gz" "$staging"
rm -rf "$staging"
source_task_utils "$TMPDIR_7"
result=$(resolve_plan_file "50")
actual_content=$(cat "$result")
assert_eq "Parent plan from tar.gz has correct content" "tar plan 50 content" "$actual_content"
rm -rf "$TMPDIR_7"

# --- Test 8: Resolve child plan from tar.gz ---
echo "--- Test 8: Resolve child plan from tar.gz ---"
TMPDIR_8=$(setup_test_env)
staging=$(mktemp -d)
mkdir -p "$staging/p10"
echo "tar child plan 10_2 content" > "$staging/p10/p10_2_add_login.md"
create_test_archive "$TMPDIR_8/aiplans/archived/old.tar.gz" "$staging"
rm -rf "$staging"
source_task_utils "$TMPDIR_8"
result=$(resolve_plan_file "10_2")
actual_content=$(cat "$result")
assert_eq "Child plan from tar.gz has correct content" "tar child plan 10_2 content" "$actual_content"
rm -rf "$TMPDIR_8"

# --- Test 9: Priority - active dir wins over tar.gz ---
echo "--- Test 9: Priority - active dir wins over tar.gz ---"
TMPDIR_9=$(setup_test_env)
echo "active task 50" > "$TMPDIR_9/aitasks/t50_test_feature.md"
staging=$(mktemp -d)
echo "tar task 50" > "$staging/t50_test_feature.md"
create_test_archive "$TMPDIR_9/aitasks/archived/old.tar.gz" "$staging"
rm -rf "$staging"
source_task_utils "$TMPDIR_9"
result=$(resolve_task_file "50")
assert_eq "Active dir wins over tar.gz" "$TMPDIR_9/aitasks/t50_test_feature.md" "$result"
rm -rf "$TMPDIR_9"

# --- Test 10: Priority - archived dir wins over tar.gz ---
echo "--- Test 10: Priority - archived dir wins over tar.gz ---"
TMPDIR_10=$(setup_test_env)
echo "archived task 50" > "$TMPDIR_10/aitasks/archived/t50_test_feature.md"
staging=$(mktemp -d)
echo "tar task 50" > "$staging/t50_test_feature.md"
create_test_archive "$TMPDIR_10/aitasks/archived/old.tar.gz" "$staging"
rm -rf "$staging"
source_task_utils "$TMPDIR_10"
result=$(resolve_task_file "50")
assert_eq "Archived dir wins over tar.gz" "$TMPDIR_10/aitasks/archived/t50_test_feature.md" "$result"
rm -rf "$TMPDIR_10"

# --- Test 11: Not found anywhere - parent task dies ---
echo "--- Test 11: Not found anywhere - parent task dies ---"
TMPDIR_11=$(setup_test_env)
source_task_utils "$TMPDIR_11"
assert_exit_nonzero "Parent task not found exits non-zero" bash -c "
    export TASK_DIR='$TMPDIR_11/aitasks'
    export ARCHIVED_DIR='$TMPDIR_11/aitasks/archived'
    export SCRIPT_DIR='$PROJECT_DIR/aiscripts'
    source '$PROJECT_DIR/aiscripts/lib/task_utils.sh'
    resolve_task_file '999'
"
rm -rf "$TMPDIR_11"

# --- Test 12: Not found anywhere - plan returns empty string ---
echo "--- Test 12: Not found anywhere - plan returns empty string ---"
TMPDIR_12=$(setup_test_env)
source_task_utils "$TMPDIR_12"
result=$(resolve_plan_file "999")
assert_eq "Plan not found returns empty string" "" "$result"
rm -rf "$TMPDIR_12"

# --- Test 13: Temp file cleanup after shell exits ---
echo "--- Test 13: Temp file cleanup after shell exits ---"
TMPDIR_13=$(setup_test_env)
staging=$(mktemp -d)
echo "tar task 77 content" > "$staging/t77_cleanup_test.md"
create_test_archive "$TMPDIR_13/aitasks/archived/old.tar.gz" "$staging"
rm -rf "$staging"
# Run in a subshell that will exit, triggering the EXIT trap.
# The subshell writes _AIT_TASK_UTILS_TMPDIR to a file so the parent can check it.
marker_file=$(mktemp)
bash -c "
    export TASK_DIR='$TMPDIR_13/aitasks'
    export ARCHIVED_DIR='$TMPDIR_13/aitasks/archived'
    export SCRIPT_DIR='$PROJECT_DIR/aiscripts'
    source '$PROJECT_DIR/aiscripts/lib/task_utils.sh'
    resolve_task_file '77' >/dev/null
    echo \"\$_AIT_TASK_UTILS_TMPDIR\" > '$marker_file'
"
tmpdir_path=$(cat "$marker_file")
rm -f "$marker_file"
TOTAL=$((TOTAL + 1))
if [[ -n "$tmpdir_path" && ! -d "$tmpdir_path" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Temp dir should be cleaned up after shell exit (dir: '$tmpdir_path', exists: $(test -d "$tmpdir_path" && echo yes || echo no))"
fi
rm -rf "$TMPDIR_13"

# --- Test 14: extract_final_implementation_notes works on tar.gz-extracted file ---
echo "--- Test 14: extract_final_implementation_notes works on tar.gz-extracted file ---"
TMPDIR_14=$(setup_test_env)
staging=$(mktemp -d)
cat > "$staging/p30_some_plan.md" << 'PLANEOF'
---
Task: t30_some_plan.md
---

## Implementation Steps

Step 1: Do something

## Final Implementation Notes

- **Actual work done:** Completed all steps
- **Issues encountered:** None
PLANEOF
create_test_archive "$TMPDIR_14/aiplans/archived/old.tar.gz" "$staging"
rm -rf "$staging"
source_task_utils "$TMPDIR_14"
plan_path=$(resolve_plan_file "30")
notes=$(extract_final_implementation_notes "$plan_path")
assert_contains "extract_final_implementation_notes finds content from tar.gz file" "Completed all steps" "$notes"
rm -rf "$TMPDIR_14"

# --- Results ---

echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
