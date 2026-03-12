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
