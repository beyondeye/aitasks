#!/usr/bin/env bash
# test_resolve_v2.sh - Integration tests for v2 resolve functions (numbered archives)
# Run: bash tests/test_resolve_v2.sh

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

setup_test_env() {
    local tmpdir
    tmpdir=$(mktemp -d)
    mkdir -p "$tmpdir/aitasks/archived"
    mkdir -p "$tmpdir/aiplans/archived"
    echo "$tmpdir"
}

create_test_archive() {
    local archive_path="$1"
    local source_dir="$2"
    mkdir -p "$(dirname "$archive_path")"
    tar -czf "$archive_path" -C "$source_dir" .
}

# Create a numbered archive at the correct path for a given task ID
create_numbered_archive() {
    local tmpdir="$1"     # test root dir
    local base="$2"       # e.g., "aitasks/archived" or "aiplans/archived"
    local task_id="$3"    # numeric task ID determining bundle
    local source_dir="$4" # dir containing files to archive
    local bundle dir archive_path
    bundle=$(( task_id / 100 ))
    dir=$(( bundle / 10 ))
    archive_path="$tmpdir/$base/_b${dir}/old${bundle}.tar.gz"
    mkdir -p "$(dirname "$archive_path")"
    tar -czf "$archive_path" -C "$source_dir" .
}

# Source task_resolve_v2.sh with overridden directories pointing to test env
source_resolve_v2() {
    local tmpdir="$1"
    export TASK_DIR="$tmpdir/aitasks"
    export ARCHIVED_DIR="$tmpdir/aitasks/archived"
    export PLAN_DIR="$tmpdir/aiplans"
    export ARCHIVED_PLAN_DIR="$tmpdir/aiplans/archived"
    export SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"

    # Reset guards so we can re-source with new directories
    unset _AIT_TASK_RESOLVE_V2_LOADED
    unset _AIT_ARCHIVE_UTILS_V2_LOADED

    # Reset temp dir from previous test
    if [[ -n "${_AIT_ARCHIVE_V2_TMPDIR:-}" && -d "$_AIT_ARCHIVE_V2_TMPDIR" ]]; then
        rm -rf "$_AIT_ARCHIVE_V2_TMPDIR"
    fi
    _AIT_ARCHIVE_V2_TMPDIR=""

    source "$PROJECT_DIR/.aitask-scripts/lib/task_resolve_v2.sh"
}

# --- Tests ---

echo "=== test_resolve_v2.sh ==="
echo ""

# --- Test 1: Resolve parent task from active dir ---
echo "--- Test 1: Resolve parent task from active dir ---"
TMPDIR_1=$(setup_test_env)
echo "task 50 content" > "$TMPDIR_1/aitasks/t50_test_feature.md"
source_resolve_v2 "$TMPDIR_1"
result=$(resolve_task_file_v2 "50")
assert_eq "Parent task resolved from active dir" "$TMPDIR_1/aitasks/t50_test_feature.md" "$result"
rm -rf "$TMPDIR_1"

# --- Test 2: Resolve parent task from archived dir ---
echo "--- Test 2: Resolve parent task from archived dir ---"
TMPDIR_2=$(setup_test_env)
echo "archived task 50 content" > "$TMPDIR_2/aitasks/archived/t50_test_feature.md"
source_resolve_v2 "$TMPDIR_2"
result=$(resolve_task_file_v2 "50")
assert_eq "Parent task resolved from archived dir" "$TMPDIR_2/aitasks/archived/t50_test_feature.md" "$result"
rm -rf "$TMPDIR_2"

# --- Test 3: Resolve parent task from numbered archive ---
echo "--- Test 3: Resolve parent task from numbered archive ---"
TMPDIR_3=$(setup_test_env)
staging=$(mktemp -d)
echo "tar task 50 numbered" > "$staging/t50_test_feature.md"
create_numbered_archive "$TMPDIR_3" "aitasks/archived" 50 "$staging"
rm -rf "$staging"
source_resolve_v2 "$TMPDIR_3"
result=$(resolve_task_file_v2 "50")
actual_content=$(cat "$result")
assert_eq "Parent task from numbered archive has correct content" "tar task 50 numbered" "$actual_content"
rm -rf "$TMPDIR_3"

# --- Test 4: Resolve child task from numbered archive ---
echo "--- Test 4: Resolve child task from numbered archive ---"
TMPDIR_4=$(setup_test_env)
staging=$(mktemp -d)
mkdir -p "$staging/t130"
echo "tar child 130_2 content" > "$staging/t130/t130_2_subtask.md"
create_numbered_archive "$TMPDIR_4" "aitasks/archived" 130 "$staging"
rm -rf "$staging"
source_resolve_v2 "$TMPDIR_4"
result=$(resolve_task_file_v2 "130_2")
actual_content=$(cat "$result")
assert_eq "Child task from numbered archive has correct content" "tar child 130_2 content" "$actual_content"
rm -rf "$TMPDIR_4"

# --- Test 5: Resolve task from legacy old.tar.gz ---
echo "--- Test 5: Resolve task from legacy old.tar.gz ---"
TMPDIR_5=$(setup_test_env)
staging=$(mktemp -d)
echo "legacy task 50 content" > "$staging/t50_test_feature.md"
create_test_archive "$TMPDIR_5/aitasks/archived/old.tar.gz" "$staging"
rm -rf "$staging"
source_resolve_v2 "$TMPDIR_5"
result=$(resolve_task_file_v2 "50")
actual_content=$(cat "$result")
assert_eq "Task from legacy old.tar.gz has correct content" "legacy task 50 content" "$actual_content"
rm -rf "$TMPDIR_5"

# --- Test 6: Priority - active wins over numbered archive ---
echo "--- Test 6: Priority - active wins over numbered archive ---"
TMPDIR_6=$(setup_test_env)
echo "active task 50" > "$TMPDIR_6/aitasks/t50_test_feature.md"
staging=$(mktemp -d)
echo "archive task 50" > "$staging/t50_test_feature.md"
create_numbered_archive "$TMPDIR_6" "aitasks/archived" 50 "$staging"
rm -rf "$staging"
source_resolve_v2 "$TMPDIR_6"
result=$(resolve_task_file_v2 "50")
assert_eq "Active dir wins over numbered archive" "$TMPDIR_6/aitasks/t50_test_feature.md" "$result"
rm -rf "$TMPDIR_6"

# --- Test 7: Priority - archived loose wins over archive ---
echo "--- Test 7: Priority - archived loose wins over archive ---"
TMPDIR_7=$(setup_test_env)
echo "archived loose task 50" > "$TMPDIR_7/aitasks/archived/t50_test_feature.md"
staging=$(mktemp -d)
echo "archive task 50" > "$staging/t50_test_feature.md"
create_numbered_archive "$TMPDIR_7" "aitasks/archived" 50 "$staging"
rm -rf "$staging"
source_resolve_v2 "$TMPDIR_7"
result=$(resolve_task_file_v2 "50")
assert_eq "Archived loose wins over archive" "$TMPDIR_7/aitasks/archived/t50_test_feature.md" "$result"
rm -rf "$TMPDIR_7"

# --- Test 8: Priority - numbered archive wins over legacy ---
echo "--- Test 8: Priority - numbered archive wins over legacy ---"
TMPDIR_8=$(setup_test_env)
staging_numbered=$(mktemp -d)
echo "numbered task 50" > "$staging_numbered/t50_test_feature.md"
create_numbered_archive "$TMPDIR_8" "aitasks/archived" 50 "$staging_numbered"
rm -rf "$staging_numbered"
staging_legacy=$(mktemp -d)
echo "legacy task 50" > "$staging_legacy/t50_test_feature.md"
create_test_archive "$TMPDIR_8/aitasks/archived/old.tar.gz" "$staging_legacy"
rm -rf "$staging_legacy"
source_resolve_v2 "$TMPDIR_8"
result=$(resolve_task_file_v2 "50")
actual_content=$(cat "$result")
assert_eq "Numbered archive wins over legacy" "numbered task 50" "$actual_content"
rm -rf "$TMPDIR_8"

# --- Test 9: Resolve plan from numbered archive ---
echo "--- Test 9: Resolve plan from numbered archive ---"
TMPDIR_9=$(setup_test_env)
staging=$(mktemp -d)
echo "plan 200 content" > "$staging/p200_test_plan.md"
create_numbered_archive "$TMPDIR_9" "aiplans/archived" 200 "$staging"
rm -rf "$staging"
source_resolve_v2 "$TMPDIR_9"
result=$(resolve_plan_file_v2 "200")
actual_content=$(cat "$result")
assert_eq "Plan from numbered archive has correct content" "plan 200 content" "$actual_content"
rm -rf "$TMPDIR_9"

# --- Test 10: Resolve plan from legacy fallback ---
echo "--- Test 10: Resolve plan from legacy fallback ---"
TMPDIR_10=$(setup_test_env)
staging=$(mktemp -d)
echo "legacy plan 200 content" > "$staging/p200_test_plan.md"
create_test_archive "$TMPDIR_10/aiplans/archived/old.tar.gz" "$staging"
rm -rf "$staging"
source_resolve_v2 "$TMPDIR_10"
result=$(resolve_plan_file_v2 "200")
actual_content=$(cat "$result")
assert_eq "Plan from legacy fallback has correct content" "legacy plan 200 content" "$actual_content"
rm -rf "$TMPDIR_10"

# --- Test 11: Not found - parent task dies ---
echo "--- Test 11: Not found - parent task dies ---"
TMPDIR_11=$(setup_test_env)
assert_exit_nonzero "Parent task not found exits non-zero" bash -c "
    export TASK_DIR='$TMPDIR_11/aitasks'
    export ARCHIVED_DIR='$TMPDIR_11/aitasks/archived'
    export SCRIPT_DIR='$PROJECT_DIR/.aitask-scripts'
    source '$PROJECT_DIR/.aitask-scripts/lib/task_resolve_v2.sh'
    resolve_task_file_v2 '999'
"
rm -rf "$TMPDIR_11"

# --- Test 12: Not found - plan returns empty ---
echo "--- Test 12: Not found - plan returns empty ---"
TMPDIR_12=$(setup_test_env)
source_resolve_v2 "$TMPDIR_12"
result=$(resolve_plan_file_v2 "999")
assert_eq "Plan not found returns empty string" "" "$result"
rm -rf "$TMPDIR_12"

# --- Test 13: Temp file cleanup ---
echo "--- Test 13: Temp file cleanup ---"
TMPDIR_13=$(setup_test_env)
staging=$(mktemp -d)
echo "tar task 77 content" > "$staging/t77_cleanup_test.md"
create_numbered_archive "$TMPDIR_13" "aitasks/archived" 77 "$staging"
rm -rf "$staging"
# Run in a subshell that will exit, triggering the EXIT trap
marker_file=$(mktemp)
bash -c "
    export TASK_DIR='$TMPDIR_13/aitasks'
    export ARCHIVED_DIR='$TMPDIR_13/aitasks/archived'
    export SCRIPT_DIR='$PROJECT_DIR/.aitask-scripts'
    source '$PROJECT_DIR/.aitask-scripts/lib/task_resolve_v2.sh'
    resolve_task_file_v2 '77' >/dev/null
    echo \"\$_AIT_ARCHIVE_V2_TMPDIR\" > '$marker_file'
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

# --- Test 14: Cross-bundle boundary ---
echo "--- Test 14: Cross-bundle boundary ---"
TMPDIR_14=$(setup_test_env)
# Task 99 goes in old0.tar.gz (_b0/old0.tar.gz)
staging99=$(mktemp -d)
echo "task 99 content" > "$staging99/t99_boundary_low.md"
create_numbered_archive "$TMPDIR_14" "aitasks/archived" 99 "$staging99"
rm -rf "$staging99"
# Task 100 goes in old1.tar.gz (_b0/old1.tar.gz)
staging100=$(mktemp -d)
echo "task 100 content" > "$staging100/t100_boundary_high.md"
create_numbered_archive "$TMPDIR_14" "aitasks/archived" 100 "$staging100"
rm -rf "$staging100"
source_resolve_v2 "$TMPDIR_14"
result99=$(resolve_task_file_v2 "99")
content99=$(cat "$result99")
assert_eq "Cross-bundle: task 99 resolves from old0" "task 99 content" "$content99"
# Need to re-source because the temp dir may have been reused
source_resolve_v2 "$TMPDIR_14"
result100=$(resolve_task_file_v2 "100")
content100=$(cat "$result100")
assert_eq "Cross-bundle: task 100 resolves from old1" "task 100 content" "$content100"
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
