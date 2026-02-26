#!/usr/bin/env bash
# test_explain_cleanup.sh - Automated tests for aitask_explain_cleanup.sh
# Run: bash tests/test_explain_cleanup.sh

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

assert_dir_exists() {
    local desc="$1" dir="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -d "$dir" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (directory '$dir' does not exist)"
    fi
}

assert_dir_not_exists() {
    local desc="$1" dir="$2"
    TOTAL=$((TOTAL + 1))
    if [[ ! -d "$dir" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (directory '$dir' still exists)"
    fi
}

# --- Setup / Teardown ---

setup_test_env() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    # Copy script and dependencies
    mkdir -p "$tmpdir/aiscripts/lib"
    cp "$PROJECT_DIR/aiscripts/aitask_explain_cleanup.sh" "$tmpdir/aiscripts/"
    cp "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh" "$tmpdir/aiscripts/lib/"
    chmod +x "$tmpdir/aiscripts/aitask_explain_cleanup.sh"

    echo "$tmpdir"
}

# Create a standard test fixture with aiexplains directories
create_fixture() {
    local tmpdir="$1"

    # Top-level aiexplains runs (bare timestamps - aitask-explain style)
    mkdir -p "$tmpdir/aiexplains/20260225_100000"
    echo "file1.py" > "$tmpdir/aiexplains/20260225_100000/files.txt"

    mkdir -p "$tmpdir/aiexplains/20260225_120000"
    echo "file1.py" > "$tmpdir/aiexplains/20260225_120000/files.txt"

    mkdir -p "$tmpdir/aiexplains/20260226_080000"
    echo "file1.py" > "$tmpdir/aiexplains/20260226_080000/files.txt"

    # Codebrowser runs (keyed style)
    mkdir -p "$tmpdir/aiexplains/codebrowser/aiscripts__20260226_100000"
    echo "script1.sh" > "$tmpdir/aiexplains/codebrowser/aiscripts__20260226_100000/files.txt"

    mkdir -p "$tmpdir/aiexplains/codebrowser/aiscripts__20260226_110000"
    echo "script1.sh" > "$tmpdir/aiexplains/codebrowser/aiscripts__20260226_110000/files.txt"

    mkdir -p "$tmpdir/aiexplains/codebrowser/aiscripts__20260226_120000"
    echo "script1.sh" > "$tmpdir/aiexplains/codebrowser/aiscripts__20260226_120000/files.txt"

    # Different key - should be independent group
    mkdir -p "$tmpdir/aiexplains/codebrowser/tests__20260226_090000"
    echo "test1.sh" > "$tmpdir/aiexplains/codebrowser/tests__20260226_090000/files.txt"

    mkdir -p "$tmpdir/aiexplains/codebrowser/tests__20260226_100000"
    echo "test1.sh" > "$tmpdir/aiexplains/codebrowser/tests__20260226_100000/files.txt"

    # Single entry key - should not be removed
    mkdir -p "$tmpdir/aiexplains/codebrowser/imgs__20260226_120000"
    echo "logo.png" > "$tmpdir/aiexplains/codebrowser/imgs__20260226_120000/files.txt"
}

cleanup_test_env() {
    local tmpdir="$1"
    rm -rf "$tmpdir"
}

# --- Tests ---

test_help_flag() {
    local tmpdir
    tmpdir=$(setup_test_env)
    cd "$tmpdir"

    local output
    output=$(./aiscripts/aitask_explain_cleanup.sh --help 2>&1)

    assert_contains "help shows usage" "Usage:" "$output"
    assert_contains "help shows --dry-run" "dry-run" "$output"
    assert_contains "help shows --all" "[-][-]all" "$output"

    cleanup_test_env "$tmpdir"
}

test_no_aiexplains_dir() {
    local tmpdir
    tmpdir=$(setup_test_env)
    cd "$tmpdir"

    local output
    output=$(./aiscripts/aitask_explain_cleanup.sh 2>&1)

    assert_contains "missing dir reports not found" "not found\|CLEANED: 0" "$output"
    assert_contains "reports zero cleaned" "CLEANED: 0" "$output"

    cleanup_test_env "$tmpdir"
}

test_empty_aiexplains_dir() {
    local tmpdir
    tmpdir=$(setup_test_env)
    cd "$tmpdir"
    mkdir -p aiexplains

    local output
    output=$(./aiscripts/aitask_explain_cleanup.sh 2>&1)

    assert_contains "empty dir cleans nothing" "CLEANED: 0" "$output"

    cleanup_test_env "$tmpdir"
}

test_dry_run_no_deletion() {
    local tmpdir
    tmpdir=$(setup_test_env)
    cd "$tmpdir"
    create_fixture "$tmpdir"

    local output
    output=$(./aiscripts/aitask_explain_cleanup.sh --dry-run --all 2>&1)

    assert_contains "dry run shows Would remove" "Would remove" "$output"
    assert_contains "dry run reports count" "CLEANED:" "$output"

    # Verify nothing was actually deleted
    assert_dir_exists "dry run preserves old aiscripts dir" \
        "$tmpdir/aiexplains/codebrowser/aiscripts__20260226_100000"
    assert_dir_exists "dry run preserves old tests dir" \
        "$tmpdir/aiexplains/codebrowser/tests__20260226_090000"

    cleanup_test_env "$tmpdir"
}

test_cleanup_codebrowser_keeps_newest() {
    local tmpdir
    tmpdir=$(setup_test_env)
    cd "$tmpdir"
    create_fixture "$tmpdir"

    local output
    output=$(./aiscripts/aitask_explain_cleanup.sh --target aiexplains/codebrowser 2>&1)

    # Newest aiscripts dir kept
    assert_dir_exists "newest aiscripts dir kept" \
        "$tmpdir/aiexplains/codebrowser/aiscripts__20260226_120000"

    # Older aiscripts dirs removed
    assert_dir_not_exists "older aiscripts dir 1 removed" \
        "$tmpdir/aiexplains/codebrowser/aiscripts__20260226_100000"
    assert_dir_not_exists "older aiscripts dir 2 removed" \
        "$tmpdir/aiexplains/codebrowser/aiscripts__20260226_110000"

    # Newest tests dir kept
    assert_dir_exists "newest tests dir kept" \
        "$tmpdir/aiexplains/codebrowser/tests__20260226_100000"

    # Older tests dir removed
    assert_dir_not_exists "older tests dir removed" \
        "$tmpdir/aiexplains/codebrowser/tests__20260226_090000"

    # Single entry key untouched
    assert_dir_exists "single entry key untouched" \
        "$tmpdir/aiexplains/codebrowser/imgs__20260226_120000"

    # Should have cleaned 3 dirs (2 aiscripts + 1 tests)
    assert_contains "cleaned 3 dirs" "CLEANED: 3" "$output"

    cleanup_test_env "$tmpdir"
}

test_cleanup_all_mode() {
    local tmpdir
    tmpdir=$(setup_test_env)
    cd "$tmpdir"
    create_fixture "$tmpdir"

    local output
    output=$(./aiscripts/aitask_explain_cleanup.sh --all 2>&1)

    # Top-level: bare timestamps grouped under _bare_timestamp_
    # Newest: 20260226_080000, older: 20260225_100000, 20260225_120000
    assert_dir_exists "newest bare timestamp kept" \
        "$tmpdir/aiexplains/20260226_080000"
    assert_dir_not_exists "older bare timestamp 1 removed" \
        "$tmpdir/aiexplains/20260225_100000"
    assert_dir_not_exists "older bare timestamp 2 removed" \
        "$tmpdir/aiexplains/20260225_120000"

    # Codebrowser dirs cleaned too
    assert_dir_exists "newest aiscripts kept in all mode" \
        "$tmpdir/aiexplains/codebrowser/aiscripts__20260226_120000"
    assert_dir_not_exists "older aiscripts removed in all mode" \
        "$tmpdir/aiexplains/codebrowser/aiscripts__20260226_100000"

    # Total: 2 bare + 2 aiscripts + 1 tests = 5
    assert_contains "all mode cleaned 5 dirs" "CLEANED: 5" "$output"

    cleanup_test_env "$tmpdir"
}

test_all_mode_skips_codebrowser_subdir() {
    local tmpdir
    tmpdir=$(setup_test_env)
    cd "$tmpdir"
    create_fixture "$tmpdir"

    ./aiscripts/aitask_explain_cleanup.sh --all --quiet 2>&1 > /dev/null

    # Codebrowser directory itself should still exist
    assert_dir_exists "codebrowser subdir not deleted" \
        "$tmpdir/aiexplains/codebrowser"

    cleanup_test_env "$tmpdir"
}

test_quiet_mode() {
    local tmpdir
    tmpdir=$(setup_test_env)
    cd "$tmpdir"
    create_fixture "$tmpdir"

    local output
    output=$(./aiscripts/aitask_explain_cleanup.sh --all --quiet 2>&1)

    # Quiet mode should only output the CLEANED line
    local line_count
    line_count=$(echo "$output" | wc -l | tr -d ' ')

    assert_eq "quiet mode minimal output" "1" "$line_count"
    assert_contains "quiet mode still shows CLEANED" "CLEANED:" "$output"

    cleanup_test_env "$tmpdir"
}

test_skips_dirs_without_marker_files() {
    local tmpdir
    tmpdir=$(setup_test_env)
    cd "$tmpdir"

    # Create dirs without files.txt or raw_data.txt
    mkdir -p aiexplains/codebrowser/aiscripts__20260226_100000
    echo "has marker" > aiexplains/codebrowser/aiscripts__20260226_100000/files.txt

    mkdir -p aiexplains/codebrowser/aiscripts__20260226_090000
    # No files.txt or raw_data.txt — should be skipped

    local output
    output=$(./aiscripts/aitask_explain_cleanup.sh --target aiexplains/codebrowser 2>&1)

    # The dir without marker should still exist (skipped)
    assert_dir_exists "dir without marker skipped" \
        "$tmpdir/aiexplains/codebrowser/aiscripts__20260226_090000"
    assert_contains "zero cleaned when no valid stale dirs" "CLEANED: 0" "$output"

    cleanup_test_env "$tmpdir"
}

test_raw_data_txt_accepted() {
    local tmpdir
    tmpdir=$(setup_test_env)
    cd "$tmpdir"

    mkdir -p aiexplains/codebrowser/src__20260226_100000
    echo "data" > aiexplains/codebrowser/src__20260226_100000/raw_data.txt

    mkdir -p aiexplains/codebrowser/src__20260226_090000
    echo "data" > aiexplains/codebrowser/src__20260226_090000/raw_data.txt

    local output
    output=$(./aiscripts/aitask_explain_cleanup.sh --target aiexplains/codebrowser 2>&1)

    assert_dir_exists "newest with raw_data.txt kept" \
        "$tmpdir/aiexplains/codebrowser/src__20260226_100000"
    assert_dir_not_exists "older with raw_data.txt removed" \
        "$tmpdir/aiexplains/codebrowser/src__20260226_090000"
    assert_contains "cleaned 1 with raw_data.txt" "CLEANED: 1" "$output"

    cleanup_test_env "$tmpdir"
}

test_unrecognized_dir_skipped() {
    local tmpdir
    tmpdir=$(setup_test_env)
    cd "$tmpdir"

    mkdir -p aiexplains/codebrowser/some_random_dir
    echo "stuff" > aiexplains/codebrowser/some_random_dir/files.txt

    mkdir -p aiexplains/codebrowser/aiscripts__20260226_100000
    echo "stuff" > aiexplains/codebrowser/aiscripts__20260226_100000/files.txt

    local output
    output=$(./aiscripts/aitask_explain_cleanup.sh --target aiexplains/codebrowser 2>&1)

    assert_dir_exists "unrecognized dir not deleted" \
        "$tmpdir/aiexplains/codebrowser/some_random_dir"
    assert_contains "cleaned 0 (no duplicates)" "CLEANED: 0" "$output"

    cleanup_test_env "$tmpdir"
}

test_nested_key_with_double_underscore() {
    local tmpdir
    tmpdir=$(setup_test_env)
    cd "$tmpdir"

    # Key with nested path: aiscripts__board -> key "aiscripts__board"
    mkdir -p aiexplains/codebrowser/aiscripts__board__20260226_100000
    echo "files" > aiexplains/codebrowser/aiscripts__board__20260226_100000/files.txt

    mkdir -p aiexplains/codebrowser/aiscripts__board__20260226_090000
    echo "files" > aiexplains/codebrowser/aiscripts__board__20260226_090000/files.txt

    local output
    output=$(./aiscripts/aitask_explain_cleanup.sh --target aiexplains/codebrowser 2>&1)

    assert_dir_exists "nested key newest kept" \
        "$tmpdir/aiexplains/codebrowser/aiscripts__board__20260226_100000"
    assert_dir_not_exists "nested key older removed" \
        "$tmpdir/aiexplains/codebrowser/aiscripts__board__20260226_090000"
    assert_contains "cleaned 1 nested key" "CLEANED: 1" "$output"

    cleanup_test_env "$tmpdir"
}

test_single_entry_per_key_no_deletion() {
    local tmpdir
    tmpdir=$(setup_test_env)
    cd "$tmpdir"

    mkdir -p aiexplains/codebrowser/aiscripts__20260226_100000
    echo "files" > aiexplains/codebrowser/aiscripts__20260226_100000/files.txt

    mkdir -p aiexplains/codebrowser/tests__20260226_090000
    echo "files" > aiexplains/codebrowser/tests__20260226_090000/files.txt

    local output
    output=$(./aiscripts/aitask_explain_cleanup.sh --target aiexplains/codebrowser 2>&1)

    assert_dir_exists "single aiscripts entry kept" \
        "$tmpdir/aiexplains/codebrowser/aiscripts__20260226_100000"
    assert_dir_exists "single tests entry kept" \
        "$tmpdir/aiexplains/codebrowser/tests__20260226_090000"
    assert_contains "zero cleaned with single entries" "CLEANED: 0" "$output"

    cleanup_test_env "$tmpdir"
}

test_unknown_option_fails() {
    local tmpdir
    tmpdir=$(setup_test_env)
    cd "$tmpdir"

    TOTAL=$((TOTAL + 1))
    if ./aiscripts/aitask_explain_cleanup.sh --invalid 2>/dev/null; then
        FAIL=$((FAIL + 1))
        echo "FAIL: unknown option should exit non-zero"
    else
        PASS=$((PASS + 1))
    fi

    cleanup_test_env "$tmpdir"
}

# --- Run all tests ---

echo "Running aitask_explain_cleanup.sh tests..."
echo ""

test_help_flag
test_no_aiexplains_dir
test_empty_aiexplains_dir
test_dry_run_no_deletion
test_cleanup_codebrowser_keeps_newest
test_cleanup_all_mode
test_all_mode_skips_codebrowser_subdir
test_quiet_mode
test_skips_dirs_without_marker_files
test_raw_data_txt_accepted
test_unrecognized_dir_skipped
test_nested_key_with_double_underscore
test_single_entry_per_key_no_deletion
test_unknown_option_fails

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
