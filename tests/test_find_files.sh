#!/bin/bash
# test_find_files.sh - Automated tests for aitask_find_files.sh
# Run: bash tests/test_find_files.sh
#
# Creates temporary git repos with known file structures and content,
# then verifies keyword search, name search, output format, and error handling.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
FIND_SCRIPT="$PROJECT_DIR/aiscripts/aitask_find_files.sh"

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
        echo "FAIL: $desc"
        echo "  Expected: $expected"
        echo "  Actual:   $actual"
    fi
}

assert_contains() {
    local desc="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$haystack" | grep -qi "$needle"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected to contain '$needle')"
        echo "  Got: $haystack"
    fi
}

assert_not_contains() {
    local desc="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$haystack" | grep -qi "$needle"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected NOT to contain '$needle')"
        echo "  Got: $haystack"
    else
        PASS=$((PASS + 1))
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
        echo "FAIL: $desc (expected exit 0, got $?)"
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

assert_line_count() {
    local desc="$1" expected="$2" output="$3"
    TOTAL=$((TOTAL + 1))
    local actual
    if [[ -z "$output" ]]; then
        actual=0
    else
        actual=$(echo "$output" | wc -l | tr -d ' ')
    fi
    if [[ "$actual" -eq "$expected" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected $expected lines, got $actual)"
        echo "  Output: $output"
    fi
}

assert_line_count_lte() {
    local desc="$1" max="$2" output="$3"
    TOTAL=$((TOTAL + 1))
    local actual
    if [[ -z "$output" ]]; then
        actual=0
    else
        actual=$(echo "$output" | wc -l | tr -d ' ')
    fi
    if [[ "$actual" -le "$max" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected <= $max lines, got $actual)"
    fi
}

# --- Fixture setup ---

TMPDIR_BASE=""

setup_test_repo() {
    TMPDIR_BASE=$(mktemp -d)
    local repo="$TMPDIR_BASE/repo"
    mkdir -p "$repo"

    (
        cd "$repo"
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"

        # Create files with known content
        mkdir -p src docs config

        cat > src/task_utils.sh << 'FILEEOF'
#!/bin/bash
# Task utilities for resolving task files
resolve_task() {
    local task_id="$1"
    echo "Resolving task $task_id"
}
archive_task() {
    local task_id="$1"
    echo "Archiving task $task_id"
}
FILEEOF

        cat > src/terminal_compat.sh << 'FILEEOF'
#!/bin/bash
# Terminal compatibility detection
detect_terminal() {
    echo "Detecting terminal capabilities"
}
warn() {
    echo "WARNING: $1" >&2
}
FILEEOF

        cat > src/changelog.sh << 'FILEEOF'
#!/bin/bash
# Changelog generation from task commits
generate_changelog() {
    echo "Generating changelog from commits"
}
parse_task_commits() {
    echo "Parsing task-related commits"
}
FILEEOF

        cat > docs/README.md << 'FILEEOF'
# Project Documentation
This is the project documentation.
Describes the overall architecture.
FILEEOF

        cat > config/settings.json << 'FILEEOF'
{
    "max_results": 20,
    "settings": {
        "theme": "dark"
    }
}
FILEEOF

        # Copy the script under test and its dependencies
        mkdir -p aiscripts/lib
        cp "$FIND_SCRIPT" aiscripts/aitask_find_files.sh
        cp "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh" aiscripts/lib/

        git add -A
        git commit -m "Initial commit" --quiet
    )

    echo "$repo"
}

teardown_test_repo() {
    [[ -n "$TMPDIR_BASE" && -d "$TMPDIR_BASE" ]] && rm -rf "$TMPDIR_BASE"
    TMPDIR_BASE=""
}

# Helper to run the script in a test repo
run_in_repo() {
    local repo="$1"
    shift
    (cd "$repo" && bash aiscripts/aitask_find_files.sh "$@" 2>/dev/null)
}

run_in_repo_stderr() {
    local repo="$1"
    shift
    (cd "$repo" && bash aiscripts/aitask_find_files.sh "$@" 2>&1)
}

# =========================================================================
echo "=== test_find_files.sh ==="
echo ""

# --- Test 1: Syntax check ---
echo "--- Test 1: Syntax check ---"
set +e
assert_exit_zero "Script syntax is valid" bash -n "$FIND_SCRIPT"
set -e

# --- Test 2: No arguments → error ---
echo "--- Test 2: No arguments → error ---"
REPO=$(setup_test_repo)
set +e
output=$(run_in_repo_stderr "$REPO" 2>&1)
exit_code=$?
set -e
assert_eq "No args exits non-zero" 1 "$((exit_code > 0 ? 1 : 0))"
assert_contains "No args shows mode required" "mode required" "$output"
teardown_test_repo

# --- Test 3: --help → usage text ---
echo "--- Test 3: --help → usage text ---"
REPO=$(setup_test_repo)
set +e
output=$(run_in_repo "$REPO" --help 2>&1)
exit_code=$?
set -e
assert_eq "--help exits zero" 0 "$exit_code"
assert_contains "--help shows usage" "usage:" "$output"
assert_contains "--help shows --keywords" "keywords" "$output"
assert_contains "--help shows --names" "names" "$output"
teardown_test_repo

# --- Test 4: Unknown flag → error ---
echo "--- Test 4: Unknown flag → error ---"
REPO=$(setup_test_repo)
set +e
output=$(run_in_repo_stderr "$REPO" --invalid 2>&1)
exit_code=$?
set -e
assert_eq "Unknown flag exits non-zero" 1 "$((exit_code > 0 ? 1 : 0))"
assert_contains "Unknown flag mentions the flag" "invalid" "$output"
teardown_test_repo

# --- Test 5: Keyword search - single term ---
echo "--- Test 5: Keyword search - single term ---"
REPO=$(setup_test_repo)
set +e
output=$(run_in_repo "$REPO" --keywords "resolve")
exit_code=$?
set -e
assert_eq "Keyword single term exits zero" 0 "$exit_code"
assert_contains "Keyword 'resolve' finds task_utils.sh" "task_utils.sh" "$output"
teardown_test_repo

# --- Test 6: Keyword search - multiple terms ---
echo "--- Test 6: Keyword search - multiple terms ---"
REPO=$(setup_test_repo)
set +e
output=$(run_in_repo "$REPO" --keywords "resolve task")
exit_code=$?
set -e
assert_eq "Keyword multi-term exits zero" 0 "$exit_code"
assert_contains "Multi-term finds task_utils.sh" "task_utils.sh" "$output"
# task_utils.sh should rank higher than changelog.sh (matches both "resolve" and "task" vs just "task")
first_line=$(echo "$output" | head -1)
assert_contains "task_utils.sh ranks first" "task_utils.sh" "$first_line"
teardown_test_repo

# --- Test 7: Keyword search - no matches ---
echo "--- Test 7: Keyword search - no matches ---"
REPO=$(setup_test_repo)
set +e
output=$(run_in_repo "$REPO" --keywords "xyznonexistent")
exit_code=$?
set -e
assert_eq "No matches exits zero" 0 "$exit_code"
assert_eq "No matches produces empty output" "" "$output"
teardown_test_repo

# --- Test 8: Keyword search - --max-results ---
echo "--- Test 8: Keyword search - --max-results ---"
REPO=$(setup_test_repo)
set +e
output=$(run_in_repo "$REPO" --keywords "task" --max-results 2)
exit_code=$?
set -e
assert_eq "Max results exits zero" 0 "$exit_code"
assert_line_count_lte "Max results limits to 2" 2 "$output"
teardown_test_repo

# --- Test 9: Name search - single term ---
echo "--- Test 9: Name search - single term ---"
REPO=$(setup_test_repo)
set +e
output=$(run_in_repo "$REPO" --names "task_utils")
exit_code=$?
set -e
assert_eq "Name single term exits zero" 0 "$exit_code"
assert_contains "Name 'task_utils' finds task_utils.sh" "task_utils.sh" "$output"
teardown_test_repo

# --- Test 10: Name search - multiple terms ---
echo "--- Test 10: Name search - multiple terms ---"
REPO=$(setup_test_repo)
set +e
output=$(run_in_repo "$REPO" --names "task_utils terminal")
exit_code=$?
set -e
assert_eq "Name multi-term exits zero" 0 "$exit_code"
assert_contains "Multi-term finds task_utils.sh" "task_utils.sh" "$output"
assert_contains "Multi-term finds terminal_compat.sh" "terminal_compat.sh" "$output"
teardown_test_repo

# --- Test 11: Name search - fuzzy match ---
echo "--- Test 11: Name search - fuzzy match ---"
REPO=$(setup_test_repo)
set +e
output=$(run_in_repo "$REPO" --names "tsk_utl")
exit_code=$?
set -e
assert_eq "Fuzzy name exits zero" 0 "$exit_code"
assert_contains "Fuzzy 'tsk_utl' matches task_utils.sh" "task_utils.sh" "$output"
teardown_test_repo

# --- Test 12: Name search - no matches ---
echo "--- Test 12: Name search - no matches ---"
REPO=$(setup_test_repo)
set +e
output=$(run_in_repo "$REPO" --names "xyznonexistent")
exit_code=$?
set -e
assert_eq "Name no matches exits zero" 0 "$exit_code"
assert_eq "Name no matches produces empty output" "" "$output"
teardown_test_repo

# --- Test 13: Name search - --max-results ---
echo "--- Test 13: Name search - --max-results ---"
REPO=$(setup_test_repo)
set +e
output=$(run_in_repo "$REPO" --names "sh" --max-results 1)
exit_code=$?
set -e
assert_eq "Name max results exits zero" 0 "$exit_code"
assert_line_count "Name max results limits to 1" 1 "$output"
teardown_test_repo

# --- Test 14: Output format validation ---
echo "--- Test 14: Output format validation ---"
REPO=$(setup_test_repo)
set +e
output=$(run_in_repo "$REPO" --keywords "resolve")
set -e
# Every line should match pattern: number|number|path
all_valid=true
while IFS= read -r line; do
    if [[ -z "$line" ]]; then
        continue
    fi
    if ! echo "$line" | grep -qE '^[0-9]+\|[0-9]+\|.+$'; then
        all_valid=false
        break
    fi
done <<< "$output"
TOTAL=$((TOTAL + 1))
if [[ "$all_valid" == "true" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Output format validation (expected rank|score|path)"
    echo "  Got: $output"
fi

# Validate name search output format too
set +e
output=$(run_in_repo "$REPO" --names "task_utils")
set -e
all_valid=true
while IFS= read -r line; do
    if [[ -z "$line" ]]; then
        continue
    fi
    if ! echo "$line" | grep -qE '^[0-9]+\|[0-9]+\|.+$'; then
        all_valid=false
        break
    fi
done <<< "$output"
TOTAL=$((TOTAL + 1))
if [[ "$all_valid" == "true" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Name output format validation (expected rank|score|path)"
    echo "  Got: $output"
fi
teardown_test_repo

# --- Test 15: Rank ordering - keywords ---
echo "--- Test 15: Rank ordering ---"
REPO=$(setup_test_repo)
set +e
output=$(run_in_repo "$REPO" --keywords "task")
set -e
# Verify ranks are sequential starting from 1
rank=1
rank_valid=true
while IFS='|' read -r r score path; do
    if [[ "$r" -ne "$rank" ]]; then
        rank_valid=false
        break
    fi
    rank=$((rank + 1))
done <<< "$output"
TOTAL=$((TOTAL + 1))
if [[ "$rank_valid" == "true" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Ranks should be sequential from 1"
    echo "  Got: $output"
fi
teardown_test_repo

# =========================================================================
echo ""
echo "=== Results ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "TOTAL: $TOTAL"

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
