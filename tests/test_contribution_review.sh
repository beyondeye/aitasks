#!/usr/bin/env bash
# test_contribution_review.sh - Tests for aitask_contribution_review.sh
# Run: bash tests/test_contribution_review.sh

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
    if echo "$actual" | grep -F -q -- "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected')"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -F -q -- "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (output should NOT contain '$unexpected')"
    else
        PASS=$((PASS + 1))
    fi
}

# Source the script functions without running main (BASH_SOURCE guard)
source "$PROJECT_DIR/.aitask-scripts/aitask_contribution_review.sh"

# Disable strict mode for test error handling
set +e

echo "=== Contribution Review Tests ==="
echo ""

# --- Test 1: Syntax check ---
echo "--- Test 1: Syntax check ---"
output=$(bash -n "$PROJECT_DIR/.aitask-scripts/aitask_contribution_review.sh" 2>&1)
assert_eq "Script has valid syntax" "" "$output"
echo ""

# --- Test 2: Help output ---
echo "--- Test 2: Help output ---"
output=$("$PROJECT_DIR/.aitask-scripts/aitask_contribution_review.sh" --help 2>&1)
exit_code=$?
assert_eq "Help exits with 0" "0" "$exit_code"
assert_contains "Help shows fetch subcommand" "fetch <issue_num>" "$output"
assert_contains "Help shows find-related subcommand" "find-related <issue_num>" "$output"
assert_contains "Help shows fetch-multi subcommand" "fetch-multi <N1,N2,...>" "$output"
assert_contains "Help shows --platform option" "--platform" "$output"
assert_contains "Help shows output format" "ISSUE_JSON" "$output"
echo ""

# --- Test 3: Parse overlap results from bot comment ---
echo "--- Test 3: Parse overlap from bot comment ---"

# Mock comments JSON with overlap-results marker
mock_comments='[
    {"author": "bot", "body": "## Contribution Overlap Analysis\n\n| Issue | Score |\n<!-- overlap-results top_overlaps: 42:7,38:4,15:2 overlap_check_version: 1 -->", "createdAt": "2026-01-01"}
]'

result=$(parse_overlap_from_comments "$mock_comments" "99")
assert_contains "Parses high-score overlap (42:7)" "OVERLAP:42:7" "$result"
assert_contains "Parses threshold overlap (38:4)" "OVERLAP:38:4" "$result"
assert_not_contains "Filters out low-score overlap (15:2)" "OVERLAP:15" "$result"
echo ""

# --- Test 4: Parse overlap - no bot comment ---
echo "--- Test 4: No bot comment ---"

mock_comments_no_bot='[
    {"author": "user1", "body": "This looks good!", "createdAt": "2026-01-01"},
    {"author": "user2", "body": "I agree, nice work.", "createdAt": "2026-01-02"}
]'

result=$(parse_overlap_from_comments "$mock_comments_no_bot" "99")
assert_contains "Reports no bot comment" "NO_BOT_COMMENT" "$result"
echo ""

# --- Test 5: Parse overlap - empty top_overlaps ---
echo "--- Test 5: Empty overlap results ---"

mock_comments_empty='[
    {"author": "bot", "body": "## No overlapping\n\n<!-- overlap-results overlap_check_version: 1 -->", "createdAt": "2026-01-01"}
]'

result=$(parse_overlap_from_comments "$mock_comments_empty" "99")
# No OVERLAP lines should be present, no NO_BOT_COMMENT either
assert_not_contains "No OVERLAP lines for empty results" "OVERLAP:" "$result"
assert_not_contains "Bot comment exists (no NO_BOT_COMMENT)" "NO_BOT_COMMENT" "$result"
echo ""

# --- Test 6: Parse overlap - self-reference excluded ---
echo "--- Test 6: Self-reference excluded ---"

mock_comments_self='[
    {"author": "bot", "body": "<!-- overlap-results top_overlaps: 99:8,42:5 overlap_check_version: 1 -->", "createdAt": "2026-01-01"}
]'

result=$(parse_overlap_from_comments "$mock_comments_self" "99")
assert_not_contains "Self-reference #99 excluded" "OVERLAP:99" "$result"
assert_contains "Other issue #42 included" "OVERLAP:42:5" "$result"
echo ""

# --- Test 7: Multiple overlap comments - uses last one ---
echo "--- Test 7: Multiple overlap comments (uses last) ---"

mock_comments_multi='[
    {"author": "bot", "body": "<!-- overlap-results top_overlaps: 10:8,20:5 overlap_check_version: 1 -->", "createdAt": "2026-01-01"},
    {"author": "user1", "body": "Thanks for the analysis!", "createdAt": "2026-01-02"},
    {"author": "bot", "body": "<!-- overlap-results top_overlaps: 30:7,40:4 overlap_check_version: 2 -->", "createdAt": "2026-01-03"}
]'

result=$(parse_overlap_from_comments "$mock_comments_multi" "99")
assert_not_contains "First (stale) comment ignored (10:8)" "OVERLAP:10" "$result"
assert_not_contains "First (stale) comment ignored (20:5)" "OVERLAP:20" "$result"
assert_contains "Last comment used (30:7)" "OVERLAP:30:7" "$result"
assert_contains "Last comment used (40:4)" "OVERLAP:40:4" "$result"
echo ""

# --- Test 8: Parse linked issues from text ---
echo "--- Test 8: Parse linked issues ---"

mock_text="This relates to #42 and also #38. See #42 again for details. Issue #15 is unrelated."
result=$(parse_linked_issues "$mock_text" "99")
assert_contains "Finds #42" "42" "$result"
assert_contains "Finds #38" "38" "$result"
assert_contains "Finds #15" "15" "$result"
# Count unique entries (should be 3)
count=$(echo "$result" | grep -c '[0-9]')
assert_eq "Deduplicates #42 (3 unique issues)" "3" "$count"
echo ""

# --- Test 9: Parse linked issues - self excluded ---
echo "--- Test 9: Linked issues self-exclusion ---"

mock_text_self="See #99 and #42"
result=$(parse_linked_issues "$mock_text_self" "99")
assert_not_contains "Self-reference #99 excluded" "99" "$result"
assert_contains "Other issue #42 included" "42" "$result"
echo ""

# --- Test 10: Parse linked issues - no references ---
echo "--- Test 10: No linked issues ---"

mock_text_none="This is a standalone contribution with no references."
result=$(parse_linked_issues "$mock_text_none" "99")
if [[ -z "$result" ]]; then
    count="0"
else
    count=$(echo "$result" | grep -c '[0-9]' || true)
fi
assert_eq "No issues found in text without references" "0" "$count"
echo ""

# --- Test 11: Argument parsing - fetch subcommand ---
echo "--- Test 11: Argument parsing ---"

# Reset globals
REVIEW_SUBCMD=""
REVIEW_ISSUE=""
REVIEW_ISSUES_CSV=""
REVIEW_PLATFORM=""
REVIEW_REPO=""
REVIEW_LIMIT=50

parse_args fetch 42 --platform github --repo "owner/repo" --limit 25
assert_eq "Subcommand parsed" "fetch" "$REVIEW_SUBCMD"
assert_eq "Issue number parsed" "42" "$REVIEW_ISSUE"
assert_eq "Platform parsed" "github" "$REVIEW_PLATFORM"
assert_eq "Repo parsed" "owner/repo" "$REVIEW_REPO"
assert_eq "Limit parsed" "25" "$REVIEW_LIMIT"
echo ""

# --- Test 12: Argument parsing - fetch-multi subcommand ---
echo "--- Test 12: Argument parsing fetch-multi ---"

REVIEW_SUBCMD=""
REVIEW_ISSUE=""
REVIEW_ISSUES_CSV=""
REVIEW_PLATFORM=""
REVIEW_REPO=""
REVIEW_LIMIT=50

parse_args fetch-multi 42,38,15 --platform gitlab
assert_eq "Subcommand parsed" "fetch-multi" "$REVIEW_SUBCMD"
assert_eq "Issues CSV parsed" "42,38,15" "$REVIEW_ISSUES_CSV"
assert_eq "Platform parsed" "gitlab" "$REVIEW_PLATFORM"
echo ""

# --- Test 13: Argument parsing - missing issue number ---
echo "--- Test 13: Missing issue number validation ---"

REVIEW_SUBCMD=""
REVIEW_ISSUE=""
REVIEW_ISSUES_CSV=""
REVIEW_PLATFORM=""
REVIEW_REPO=""
REVIEW_LIMIT=50

result=$(parse_args fetch 2>&1 || true)
# die() should have been called — check for error message
assert_contains "Error for missing issue" "requires an issue number" "$result"
echo ""

# --- Test 14: Unknown subcommand ---
echo "--- Test 14: Unknown subcommand ---"

result=$("$PROJECT_DIR/.aitask-scripts/aitask_contribution_review.sh" invalid 2>&1 || true)
assert_contains "Error for unknown subcommand" "Unknown subcommand" "$result"
echo ""

# --- Test 15: Help output includes post-comment ---
echo "--- Test 15: Help includes post-comment ---"
output=$("$PROJECT_DIR/.aitask-scripts/aitask_contribution_review.sh" --help 2>&1)
assert_contains "Help shows post-comment subcommand" "post-comment" "$output"
echo ""

# --- Test 16: Argument parsing - post-comment subcommand ---
echo "--- Test 16: Argument parsing post-comment ---"

REVIEW_SUBCMD=""
REVIEW_ISSUE=""
REVIEW_ISSUES_CSV=""
REVIEW_COMMENT=""
REVIEW_PLATFORM=""
REVIEW_REPO=""
REVIEW_LIMIT=50

parse_args post-comment 42 "Test comment body" --platform github
assert_eq "Subcommand parsed" "post-comment" "$REVIEW_SUBCMD"
assert_eq "Issue number parsed" "42" "$REVIEW_ISSUE"
assert_eq "Comment body parsed" "Test comment body" "$REVIEW_COMMENT"
assert_eq "Platform parsed" "github" "$REVIEW_PLATFORM"
echo ""

# --- Test 17: Argument parsing - post-comment missing comment body ---
echo "--- Test 17: post-comment missing comment ---"

REVIEW_SUBCMD=""
REVIEW_ISSUE=""
REVIEW_ISSUES_CSV=""
REVIEW_COMMENT=""
REVIEW_PLATFORM=""
REVIEW_REPO=""
REVIEW_LIMIT=50

result=$(parse_args post-comment 42 2>&1 || true)
assert_contains "Error for missing comment" "requires a message" "$result"
echo ""

# --- Test 18: Argument parsing - post-comment missing issue number ---
echo "--- Test 18: post-comment missing issue ---"

REVIEW_SUBCMD=""
REVIEW_ISSUE=""
REVIEW_ISSUES_CSV=""
REVIEW_COMMENT=""
REVIEW_PLATFORM=""
REVIEW_REPO=""
REVIEW_LIMIT=50

result=$(parse_args post-comment 2>&1 || true)
assert_contains "Error for missing issue" "requires an issue number" "$result"
echo ""

# --- Test 19: cmd_post_comment with mocked source_post_comment ---
echo "--- Test 19: cmd_post_comment mocked ---"

# Mock source_post_comment to capture args via temp file
_mock_file="${TMPDIR:-/tmp}/test_post_comment_XXXXXX"
_mock_file=$(mktemp "${TMPDIR:-/tmp}/test_post_comment_XXXXXX.txt")
source_post_comment() {
    echo "ISSUE=$1" > "$_mock_file"
    echo "BODY=$2" >> "$_mock_file"
}

result=$(cmd_post_comment "42" "Test comment text")
assert_contains "Output contains POSTED" "POSTED:42" "$result"

_mock_issue=$(grep '^ISSUE=' "$_mock_file" | sed 's/^ISSUE=//')
_mock_body=$(grep '^BODY=' "$_mock_file" | sed 's/^BODY=//')
assert_eq "Mock received issue number" "42" "$_mock_issue"
assert_eq "Mock received comment body" "Test comment text" "$_mock_body"
rm -f "$_mock_file"
echo ""

# --- Test 20: Argument parsing - list-issues subcommand ---
echo "--- Test 20: Argument parsing list-issues ---"

REVIEW_SUBCMD=""
REVIEW_ISSUE=""
REVIEW_ISSUES_CSV=""
REVIEW_PLATFORM=""
REVIEW_REPO=""
REVIEW_LIMIT=50

parse_args list-issues --platform github
assert_eq "Subcommand parsed" "list-issues" "$REVIEW_SUBCMD"
assert_eq "No issue needed for list-issues" "" "$REVIEW_ISSUE"
assert_eq "Platform parsed" "github" "$REVIEW_PLATFORM"
echo ""

# --- Test 21: cmd_list_issues with mocked source_list_contribution_issues ---
echo "--- Test 21: cmd_list_issues mocked (multiple issues) ---"

# Save original function
_orig_source_list_contribution_issues=$(declare -f source_list_contribution_issues)

# Mock source_list_contribution_issues to return JSON with 2 issues
source_list_contribution_issues() {
    cat <<'MOCK_JSON'
[
  {"number": 10, "title": "Fix bug in auth", "body": "<!-- aitask-contribute-metadata\nfingerprint_version: 1\n-->", "labels": [], "url": "https://example.com/10"},
  {"number": 11, "title": "Add logging", "body": "No metadata here", "labels": [], "url": "https://example.com/11"}
]
MOCK_JSON
}

result=$(cmd_list_issues)
assert_contains "Issue 10 separator" "@@@ISSUE:10@@@" "$result"
assert_contains "Issue 10 title" "TITLE:Fix bug in auth" "$result"
assert_contains "Issue 11 separator" "@@@ISSUE:11@@@" "$result"
assert_contains "Issue 11 title" "TITLE:Add logging" "$result"

# Restore original
eval "$_orig_source_list_contribution_issues"
echo ""

# --- Test 22: cmd_list_issues - empty result ---
echo "--- Test 22: cmd_list_issues empty ---"

_orig_source_list_contribution_issues=$(declare -f source_list_contribution_issues)

source_list_contribution_issues() {
    echo "[]"
}

result=$(cmd_list_issues)
assert_eq "Empty issues returns NO_ISSUES" "NO_ISSUES" "$result"

eval "$_orig_source_list_contribution_issues"
echo ""

# --- Test 23: Argument parsing - check-imported requires issue number ---
echo "--- Test 23: check-imported missing issue ---"

REVIEW_SUBCMD=""
REVIEW_ISSUE=""
REVIEW_ISSUES_CSV=""
REVIEW_PLATFORM=""
REVIEW_REPO=""
REVIEW_LIMIT=50

result=$(parse_args check-imported 2>&1 || true)
assert_contains "Error for missing issue" "requires an issue number" "$result"
echo ""

# --- Test 24: Argument parsing - check-imported parses issue number ---
echo "--- Test 24: Argument parsing check-imported ---"

REVIEW_SUBCMD=""
REVIEW_ISSUE=""
REVIEW_ISSUES_CSV=""
REVIEW_PLATFORM=""
REVIEW_REPO=""
REVIEW_LIMIT=50

parse_args check-imported 42
assert_eq "Subcommand parsed" "check-imported" "$REVIEW_SUBCMD"
assert_eq "Issue parsed" "42" "$REVIEW_ISSUE"
echo ""

# --- Test 25: cmd_check_imported - finds imported task ---
echo "--- Test 25: check-imported finds task ---"

_check_tmpdir=$(mktemp -d "${TMPDIR:-/tmp}/test_check_imported_XXXXXX")
mkdir -p "$_check_tmpdir/active" "$_check_tmpdir/archived"

# Create a mock task file with issue frontmatter
cat > "$_check_tmpdir/active/t100_some_task.md" <<'TASK_EOF'
---
priority: medium
issue: https://github.com/owner/repo/issues/42
status: Implementing
---
Test task
TASK_EOF

# Temporarily override TASK_DIR and ARCHIVED_DIR
_orig_task_dir="$TASK_DIR"
_orig_archived_dir="$ARCHIVED_DIR"
TASK_DIR="$_check_tmpdir/active"
ARCHIVED_DIR="$_check_tmpdir/archived"

result=$(cmd_check_imported 42)
assert_contains "Found imported task" "IMPORTED:" "$result"
assert_contains "Points to correct file" "t100_some_task.md" "$result"

TASK_DIR="$_orig_task_dir"
ARCHIVED_DIR="$_orig_archived_dir"
rm -rf "$_check_tmpdir"
echo ""

# --- Test 26: cmd_check_imported - NOT_IMPORTED for unknown issue ---
echo "--- Test 26: check-imported not found ---"

_check_tmpdir=$(mktemp -d "${TMPDIR:-/tmp}/test_check_imported_XXXXXX")
mkdir -p "$_check_tmpdir/active" "$_check_tmpdir/archived"

_orig_task_dir="$TASK_DIR"
_orig_archived_dir="$ARCHIVED_DIR"
TASK_DIR="$_check_tmpdir/active"
ARCHIVED_DIR="$_check_tmpdir/archived"

result=$(cmd_check_imported 99999)
assert_eq "Unknown issue returns NOT_IMPORTED" "NOT_IMPORTED" "$result"

TASK_DIR="$_orig_task_dir"
ARCHIVED_DIR="$_orig_archived_dir"
rm -rf "$_check_tmpdir"
echo ""

# --- Test 27: cmd_check_imported - finds in archived dir ---
echo "--- Test 27: check-imported finds archived task ---"

_check_tmpdir=$(mktemp -d "${TMPDIR:-/tmp}/test_check_imported_XXXXXX")
mkdir -p "$_check_tmpdir/active" "$_check_tmpdir/archived"

# Create archived task with issue frontmatter
cat > "$_check_tmpdir/archived/t200_old_task.md" <<'TASK_EOF'
---
priority: low
issue: https://github.com/owner/repo/issues/55
status: Done
---
Old archived task
TASK_EOF

_orig_task_dir="$TASK_DIR"
_orig_archived_dir="$ARCHIVED_DIR"
TASK_DIR="$_check_tmpdir/active"
ARCHIVED_DIR="$_check_tmpdir/archived"

result=$(cmd_check_imported 55)
assert_contains "Found archived import" "IMPORTED:" "$result"
assert_contains "Points to archived file" "t200_old_task.md" "$result"

TASK_DIR="$_orig_task_dir"
ARCHIVED_DIR="$_orig_archived_dir"
rm -rf "$_check_tmpdir"
echo ""

# --- Test 28: Help output includes list-issues and check-imported ---
echo "--- Test 28: Help includes new subcommands ---"
output=$("$PROJECT_DIR/.aitask-scripts/aitask_contribution_review.sh" --help 2>&1)
assert_contains "Help shows list-issues" "list-issues" "$output"
assert_contains "Help shows check-imported" "check-imported" "$output"
echo ""

# --- Summary ---
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
