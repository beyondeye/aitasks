#!/usr/bin/env bash
# test_archive_scan_v2.sh - Integration tests for v2 archive scanner functions
# Run: bash tests/test_archive_scan_v2.sh

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
    local tmpdir="$1"
    local base="$2"
    local task_id="$3"
    local source_dir="$4"
    local bundle dir archive_path
    bundle=$(( task_id / 100 ))
    dir=$(( bundle / 10 ))
    archive_path="$tmpdir/$base/_b${dir}/old${bundle}.tar.gz"
    mkdir -p "$(dirname "$archive_path")"
    tar -czf "$archive_path" -C "$source_dir" .
}

# Source archive_scan_v2.sh
source_scan_v2() {
    export SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
    unset _AIT_ARCHIVE_SCAN_V2_LOADED
    unset _AIT_ARCHIVE_UTILS_V2_LOADED
    source "$PROJECT_DIR/.aitask-scripts/lib/archive_scan_v2.sh"
}

# --- Tests ---

echo "=== test_archive_scan_v2.sh ==="
echo ""

# --- Test 1: scan_max_task_id_v2 -- active only ---
echo "--- Test 1: scan_max -- active only ---"
TMPDIR_1=$(setup_test_env)
echo "task" > "$TMPDIR_1/aitasks/t200_test.md"
source_scan_v2
result=$(scan_max_task_id_v2 "$TMPDIR_1/aitasks" "$TMPDIR_1/aitasks/archived")
assert_eq "Max ID from active only" "200" "$result"
rm -rf "$TMPDIR_1"

# --- Test 2: scan_max_task_id_v2 -- archived loose ---
echo "--- Test 2: scan_max -- archived loose ---"
TMPDIR_2=$(setup_test_env)
echo "task" > "$TMPDIR_2/aitasks/archived/t300_test.md"
source_scan_v2
result=$(scan_max_task_id_v2 "$TMPDIR_2/aitasks" "$TMPDIR_2/aitasks/archived")
assert_eq "Max ID from archived loose" "300" "$result"
rm -rf "$TMPDIR_2"

# --- Test 3: scan_max_task_id_v2 -- single numbered archive ---
echo "--- Test 3: scan_max -- single numbered archive ---"
TMPDIR_3=$(setup_test_env)
staging=$(mktemp -d)
echo "task" > "$staging/t350_archived.md"
create_numbered_archive "$TMPDIR_3" "aitasks/archived" 350 "$staging"
rm -rf "$staging"
source_scan_v2
result=$(scan_max_task_id_v2 "$TMPDIR_3/aitasks" "$TMPDIR_3/aitasks/archived")
assert_eq "Max ID from single numbered archive" "350" "$result"
rm -rf "$TMPDIR_3"

# --- Test 4: scan_max_task_id_v2 -- multiple numbered archives ---
echo "--- Test 4: scan_max -- multiple numbered archives ---"
TMPDIR_4=$(setup_test_env)
staging0=$(mktemp -d)
echo "task" > "$staging0/t90_first.md"
create_numbered_archive "$TMPDIR_4" "aitasks/archived" 90 "$staging0"
rm -rf "$staging0"
staging1=$(mktemp -d)
echo "task" > "$staging1/t180_second.md"
create_numbered_archive "$TMPDIR_4" "aitasks/archived" 180 "$staging1"
rm -rf "$staging1"
staging2=$(mktemp -d)
echo "task" > "$staging2/t250_third.md"
create_numbered_archive "$TMPDIR_4" "aitasks/archived" 250 "$staging2"
rm -rf "$staging2"
source_scan_v2
result=$(scan_max_task_id_v2 "$TMPDIR_4/aitasks" "$TMPDIR_4/aitasks/archived")
assert_eq "Max ID from multiple archives" "250" "$result"
rm -rf "$TMPDIR_4"

# --- Test 5: scan_max_task_id_v2 -- legacy fallback ---
echo "--- Test 5: scan_max -- legacy fallback ---"
TMPDIR_5=$(setup_test_env)
staging=$(mktemp -d)
echo "task" > "$staging/t400_legacy.md"
create_test_archive "$TMPDIR_5/aitasks/archived/old.tar.gz" "$staging"
rm -rf "$staging"
source_scan_v2
result=$(scan_max_task_id_v2 "$TMPDIR_5/aitasks" "$TMPDIR_5/aitasks/archived")
assert_eq "Max ID from legacy archive" "400" "$result"
rm -rf "$TMPDIR_5"

# --- Test 6: scan_max_task_id_v2 -- mixed sources ---
echo "--- Test 6: scan_max -- mixed sources ---"
TMPDIR_6=$(setup_test_env)
# Active: t500
echo "task" > "$TMPDIR_6/aitasks/t500_active.md"
# Numbered: t350
staging_n=$(mktemp -d)
echo "task" > "$staging_n/t350_numbered.md"
create_numbered_archive "$TMPDIR_6" "aitasks/archived" 350 "$staging_n"
rm -rf "$staging_n"
# Legacy: t200
staging_l=$(mktemp -d)
echo "task" > "$staging_l/t200_legacy.md"
create_test_archive "$TMPDIR_6/aitasks/archived/old.tar.gz" "$staging_l"
rm -rf "$staging_l"
source_scan_v2
result=$(scan_max_task_id_v2 "$TMPDIR_6/aitasks" "$TMPDIR_6/aitasks/archived")
assert_eq "Max ID from mixed sources" "500" "$result"
rm -rf "$TMPDIR_6"

# --- Test 7: scan_max_task_id_v2 -- empty ---
echo "--- Test 7: scan_max -- empty ---"
TMPDIR_7=$(setup_test_env)
source_scan_v2
result=$(scan_max_task_id_v2 "$TMPDIR_7/aitasks" "$TMPDIR_7/aitasks/archived")
assert_eq "Max ID from empty" "0" "$result"
rm -rf "$TMPDIR_7"

# --- Test 8: search_archived_task_v2 -- found in numbered archive ---
echo "--- Test 8: search -- found in numbered ---"
TMPDIR_8=$(setup_test_env)
staging=$(mktemp -d)
echo "task" > "$staging/t150_searchable.md"
create_numbered_archive "$TMPDIR_8" "aitasks/archived" 150 "$staging"
rm -rf "$staging"
source_scan_v2
result=$(search_archived_task_v2 "150" "$TMPDIR_8/aitasks/archived")
assert_contains "Search found in numbered" "ARCHIVED_TASK_TAR_GZ:" "$result"
assert_contains "Search result has old1" "old1.tar.gz" "$result"
assert_contains "Search result has t150" "t150_searchable.md" "$result"
rm -rf "$TMPDIR_8"

# --- Test 9: search_archived_task_v2 -- found in legacy ---
echo "--- Test 9: search -- found in legacy ---"
TMPDIR_9=$(setup_test_env)
staging=$(mktemp -d)
echo "task" > "$staging/t150_legacy_search.md"
create_test_archive "$TMPDIR_9/aitasks/archived/old.tar.gz" "$staging"
rm -rf "$staging"
source_scan_v2
result=$(search_archived_task_v2 "150" "$TMPDIR_9/aitasks/archived")
assert_contains "Search found in legacy" "ARCHIVED_TASK_TAR_GZ:" "$result"
assert_contains "Search result has old.tar.gz" "old.tar.gz" "$result"
assert_contains "Search result has t150" "t150_legacy_search.md" "$result"
rm -rf "$TMPDIR_9"

# --- Test 10: search_archived_task_v2 -- not found ---
echo "--- Test 10: search -- not found ---"
TMPDIR_10=$(setup_test_env)
source_scan_v2
result=$(search_archived_task_v2 "150" "$TMPDIR_10/aitasks/archived")
assert_eq "Search not found" "NOT_FOUND" "$result"
rm -rf "$TMPDIR_10"

# --- Test 11: search_archived_task_v2 -- O(1) lookup correctness ---
echo "--- Test 11: search -- O(1) correctness ---"
TMPDIR_11=$(setup_test_env)
# Only create old1 (for t100-199), NOT old0
staging=$(mktemp -d)
echo "task" > "$staging/t150_o1_test.md"
create_numbered_archive "$TMPDIR_11" "aitasks/archived" 150 "$staging"
rm -rf "$staging"
# Verify old0 does not exist
TOTAL=$((TOTAL + 1))
if [[ ! -f "$TMPDIR_11/aitasks/archived/_b0/old0.tar.gz" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Test 11 precondition: old0 should not exist"
fi
source_scan_v2
# Search should succeed without old0 existing (O(1) direct lookup)
result=$(search_archived_task_v2 "150" "$TMPDIR_11/aitasks/archived")
assert_contains "O(1) lookup succeeds without old0" "ARCHIVED_TASK_TAR_GZ:" "$result"
assert_contains "O(1) lookup finds t150" "t150_o1_test.md" "$result"
rm -rf "$TMPDIR_11"

# --- Test 12: iter_all_archived_files_v2 -- collects from multiple archives ---
echo "--- Test 12: iter -- collects all ---"
TMPDIR_12=$(setup_test_env)
# 3 numbered archives
staging0=$(mktemp -d)
echo "task" > "$staging0/t50_iter1.md"
echo "task" > "$staging0/t51_iter2.md"
create_numbered_archive "$TMPDIR_12" "aitasks/archived" 50 "$staging0"
rm -rf "$staging0"
staging1=$(mktemp -d)
echo "task" > "$staging1/t150_iter3.md"
create_numbered_archive "$TMPDIR_12" "aitasks/archived" 150 "$staging1"
rm -rf "$staging1"
staging2=$(mktemp -d)
echo "task" > "$staging2/t250_iter4.md"
create_numbered_archive "$TMPDIR_12" "aitasks/archived" 250 "$staging2"
rm -rf "$staging2"
# Legacy archive
staging_l=$(mktemp -d)
echo "task" > "$staging_l/t400_iter5.md"
create_test_archive "$TMPDIR_12/aitasks/archived/old.tar.gz" "$staging_l"
rm -rf "$staging_l"

source_scan_v2
_test_iter_count=0
_test_iter_files=""
_test_iter_callback() {
    _test_iter_count=$((_test_iter_count + 1))
    _test_iter_files="${_test_iter_files} $(basename "$2")"
}
iter_all_archived_files_v2 "$TMPDIR_12/aitasks/archived" _test_iter_callback
# 5 files total across all archives
assert_eq "Iter collected correct count" "5" "$_test_iter_count"
assert_contains "Iter has t50" "t50_iter1.md" "$_test_iter_files"
assert_contains "Iter has t51" "t51_iter2.md" "$_test_iter_files"
assert_contains "Iter has t150" "t150_iter3.md" "$_test_iter_files"
assert_contains "Iter has t250" "t250_iter4.md" "$_test_iter_files"
assert_contains "Iter has t400" "t400_iter5.md" "$_test_iter_files"
rm -rf "$TMPDIR_12"

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
