#!/usr/bin/env bash
# test_no_recurse.sh - Tests for --no-recurse flag in aitask_explain_extract_raw_data.sh (t195_11)
# Run: bash tests/test_no_recurse.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
EXTRACT_SCRIPT="$PROJECT_DIR/aiscripts/aitask_explain_extract_raw_data.sh"

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
    if echo "$actual" | grep -qF -- "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected to contain '$expected')"
        echo "  actual: $(echo "$actual" | head -5)"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF -- "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected NOT to contain '$unexpected')"
        echo "  actual: $(echo "$actual" | head -5)"
    else
        PASS=$((PASS + 1))
    fi
}

assert_match() {
    local desc="$1" pattern="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qE "$pattern"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected match for '$pattern', got '$actual')"
    fi
}

# --- Setup ---

TMPDIR_BASE=$(mktemp -d "${TMPDIR:-/tmp}/test_no_recurse_XXXXXX")
trap 'rm -rf "$TMPDIR_BASE"' EXIT

cd "$PROJECT_DIR"

echo "=== --no-recurse flag tests (t195_11) ==="
echo ""

# ====================================================================
# Test 1: --no-recurse on directory with subdirs
# ====================================================================
echo "--- Test 1: --no-recurse on directory with subdirs ---"

TEST_DIR="$TMPDIR_BASE/test1"
mkdir -p "$TEST_DIR"

output=$(AIEXPLAINS_DIR="$TEST_DIR" "$EXTRACT_SCRIPT" --no-recurse --gather aiscripts/ --max-commits 3 2>/dev/null)
run_dir=$(echo "$output" | grep '^RUN_DIR:' | sed 's/^RUN_DIR: //')
files_content=$(cat "$run_dir/files.txt")

# Assert at least one file is present
file_count=$(echo "$files_content" | wc -l | tr -d ' ')
TOTAL=$((TOTAL + 1))
if [[ "$file_count" -gt 0 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: --no-recurse should still return files ($file_count found)"
fi

# Assert no file has a path separator after 'aiscripts/'
# (i.e., no files from aiscripts/board/, aiscripts/lib/, etc.)
subdirs_found=$(echo "$files_content" | grep -c 'aiscripts/.*/' || true)
assert_eq "--no-recurse: no subdirectory files" "0" "$subdirs_found"

# ====================================================================
# Test 2: Without --no-recurse (backward compat, recursive)
# ====================================================================
echo "--- Test 2: without --no-recurse (recursive, backward compat) ---"

TEST_DIR="$TMPDIR_BASE/test2"
mkdir -p "$TEST_DIR"

output=$(AIEXPLAINS_DIR="$TEST_DIR" "$EXTRACT_SCRIPT" --gather aiscripts/ --max-commits 3 2>/dev/null)
run_dir=$(echo "$output" | grep '^RUN_DIR:' | sed 's/^RUN_DIR: //')
files_content=$(cat "$run_dir/files.txt")

# Assert some files DO have subdirectory paths
subdirs_found=$(echo "$files_content" | grep -c 'aiscripts/.*/' || true)
TOTAL=$((TOTAL + 1))
if [[ "$subdirs_found" -gt 0 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: without --no-recurse, should include subdirectory files ($subdirs_found found)"
fi

# ====================================================================
# Test 3: --no-recurse on root directory
# ====================================================================
echo "--- Test 3: --no-recurse on root directory ---"

TEST_DIR="$TMPDIR_BASE/test3"
mkdir -p "$TEST_DIR"

output=$(AIEXPLAINS_DIR="$TEST_DIR" "$EXTRACT_SCRIPT" --no-recurse --gather . --max-commits 3 2>/dev/null)
run_dir=$(echo "$output" | grep '^RUN_DIR:' | sed 's/^RUN_DIR: //')
files_content=$(cat "$run_dir/files.txt")

# Assert at least one file is present
file_count=$(echo "$files_content" | wc -l | tr -d ' ')
TOTAL=$((TOTAL + 1))
if [[ "$file_count" -gt 0 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: --no-recurse on root should return files ($file_count found)"
fi

# Assert no file contains / (top-level only)
nested_found=$(echo "$files_content" | grep -c '/' || true)
assert_eq "--no-recurse root: no nested files" "0" "$nested_found"

# ====================================================================
# Test 4: --no-recurse with --source-key
# ====================================================================
echo "--- Test 4: --no-recurse with --source-key ---"

TEST_DIR="$TMPDIR_BASE/test4"
mkdir -p "$TEST_DIR"

output=$(AIEXPLAINS_DIR="$TEST_DIR" "$EXTRACT_SCRIPT" --no-recurse --gather --source-key test_nr_key aiscripts/ --max-commits 3 2>/dev/null)
run_dir=$(echo "$output" | grep '^RUN_DIR:' | sed 's/^RUN_DIR: //')
dir_name=$(basename "$run_dir")

# Assert directory name matches expected pattern
assert_match "--no-recurse with source-key: correct naming" "^test_nr_key__[0-9]{8}_[0-9]{6}$" "$dir_name"

# Assert files are non-recursive
files_content=$(cat "$run_dir/files.txt")
subdirs_found=$(echo "$files_content" | grep -c 'aiscripts/.*/' || true)
assert_eq "--no-recurse with source-key: no subdirectory files" "0" "$subdirs_found"

# ====================================================================
# Test 5: --no-recurse on single file (no effect)
# ====================================================================
echo "--- Test 5: --no-recurse on single file (no effect) ---"

TEST_DIR="$TMPDIR_BASE/test5"
mkdir -p "$TEST_DIR"

output=$(AIEXPLAINS_DIR="$TEST_DIR" "$EXTRACT_SCRIPT" --no-recurse --gather aiscripts/lib/task_utils.sh --max-commits 3 2>/dev/null)
run_dir=$(echo "$output" | grep '^RUN_DIR:' | sed 's/^RUN_DIR: //')
files_content=$(cat "$run_dir/files.txt")

# Assert exactly one file present and it's the right one
file_count=$(echo "$files_content" | wc -l | tr -d ' ')
assert_eq "--no-recurse single file: exactly 1 file" "1" "$file_count"
assert_contains "--no-recurse single file: correct file" "aiscripts/lib/task_utils.sh" "$files_content"

# ====================================================================
# Summary
# ====================================================================

echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
