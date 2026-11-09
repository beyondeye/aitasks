#!/usr/bin/env bash
# test_contribution_review.sh - Tests for aitask_contribution_review.sh
# Run: bash tests/test_contribution_review.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# `mktemp_suffixed` (BSD-safe suffixed temp files, t1729) lives here.
source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

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
_mock_file=$(mktemp_suffixed "${TMPDIR:-/tmp}/test_post_comment_XXXXXX.txt")
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

# --- Test 21b: cmd_list_issues through the real GitHub listing (t2235) ---
# Unlabeled metadata issues (GitHub dropped the external author's label) must be
# listed; plain issues must not; labeled issues without metadata stay visible.
echo "--- Test 21b: cmd_list_issues lists unlabeled external contributions ---"
. "$PROJECT_DIR/tests/lib/gh_contribution_stub.sh"
T2235_DIR="$(mktemp -d)"
gh_contribution_stub_install "$T2235_DIR"
_saved_platform="$CHECK_PLATFORM"; _saved_repo="$ARG_REPO"; _saved_limit="$ARG_LIMIT"
CHECK_PLATFORM="github"; ARG_REPO="o/r"; ARG_LIMIT=50

result=$(cmd_list_issues)
assert_contains "unlabeled #100 listed" "@@@ISSUE:100@@@" "$result"
assert_contains "unlabeled #101 listed" "@@@ISSUE:101@@@" "$result"
assert_contains "#100 has metadata" "$(printf '@@@ISSUE:100@@@\nTITLE:[Contribution] external A\nHAS_METADATA:true')" "$result"
assert_contains "labeled #12 listed without metadata" "$(printf '@@@ISSUE:12@@@\nTITLE:Labeled without metadata\nHAS_METADATA:false')" "$result"
assert_not_contains "plain #14 not listed" "@@@ISSUE:14@@@" "$result"
assert_not_contains "PR #300 not listed" "@@@ISSUE:300@@@" "$result"
assert_not_contains "no NO_ISSUES" "NO_ISSUES" "$result"

unset -f gh
rm -rf "$T2235_DIR"
CHECK_PLATFORM="$_saved_platform"; ARG_REPO="$_saved_repo"; ARG_LIMIT="$_saved_limit"
echo ""

# --- Test 21c: cmd_list_issues through the real GitLab listing (t2241) ---
# GitLab drops labels from authors who are not project members: unlabeled
# metadata issues must be listed, plain issues must not.
echo "--- Test 21c: cmd_list_issues lists unlabeled GitLab contributions ---"
. "$PROJECT_DIR/tests/lib/glab_contribution_stub.sh"
T2241_DIR="$(mktemp -d)"
glab_contribution_stub_install "$T2241_DIR"
_saved_platform="$CHECK_PLATFORM"; _saved_repo="$ARG_REPO"; _saved_limit="$ARG_LIMIT"
_saved_path="$PATH"; _saved_token="${GITLAB_TOKEN-}"
PATH="$T2241_DIR/bin:$PATH"; export GITLAB_TOKEN="test-token"
CHECK_PLATFORM="gitlab"; ARG_REPO="o/r"; ARG_LIMIT=50

result=$(cmd_list_issues)
assert_contains "gitlab: unlabeled #100 listed" "@@@ISSUE:100@@@" "$result"
assert_contains "gitlab: unlabeled #101 listed" "@@@ISSUE:101@@@" "$result"
assert_contains "gitlab: #100 has metadata" "$(printf '@@@ISSUE:100@@@\nTITLE:[Contribution] external A\nHAS_METADATA:true')" "$result"
assert_contains "gitlab: labeled #12 listed without metadata" "$(printf '@@@ISSUE:12@@@\nTITLE:Labeled without metadata\nHAS_METADATA:false')" "$result"
assert_not_contains "gitlab: plain #14 not listed" "@@@ISSUE:14@@@" "$result"
assert_not_contains "gitlab: ordinary #299 not listed" "@@@ISSUE:299@@@" "$result"
assert_not_contains "gitlab: no NO_ISSUES" "NO_ISSUES" "$result"

PATH="$_saved_path"
if [[ -n "$_saved_token" ]]; then GITLAB_TOKEN="$_saved_token"; else unset GITLAB_TOKEN; fi
rm -rf "$T2241_DIR"
CHECK_PLATFORM="$_saved_platform"; ARG_REPO="$_saved_repo"; ARG_LIMIT="$_saved_limit"
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

# --- Tests 29-30: missing GitLab token fails closed; Bitbucket retired (t2247) ---
. "$PROJECT_DIR/tests/lib/glab_contribution_stub.sh"
T2247_DIR="$(mktemp -d)"
glab_contribution_stub_install "$T2247_DIR"
_t2247_saved_path="$PATH"
PATH="$T2247_DIR/bin:$PATH"

echo "--- Test 29: review_gitlab_fetch_comments fails closed without GITLAB_TOKEN ---"
CHECK_PLATFORM=gitlab
ARG_REPO="o/r"
err=$(GITLAB_TOKEN="" review_gitlab_fetch_comments 100 2>&1 >/dev/null)
assert_eq "no token: comment fetch returns non-zero" "1" "$?"
assert_contains "no token: names GITLAB_TOKEN" "GITLAB_TOKEN is required" "$err"
assert_eq "no token: no request sent" "" "$(cat "$T2247_DIR/curl_calls")"
: > "$T2247_DIR/curl_auth"
out=$(GITLAB_TOKEN="test-token" review_gitlab_fetch_comments 100 2>/dev/null)
assert_eq "token: comments fetched with the token" "PRIVATE-TOKEN: test-token" "$(cat "$T2247_DIR/curl_auth")"
assert_contains "token: comment bodies returned" "overlap-results" "$out"
ARG_REPO=""
CHECK_PLATFORM=""

echo "--- Test 30: a Bitbucket review stops with the issue-tracker removal ---"
: > "$T2247_DIR/curl_calls"
err=$("$PROJECT_DIR/.aitask-scripts/aitask_contribution_review.sh" list-issues --platform bitbucket --repo ws/repo 2>&1 >/dev/null)
assert_eq "bitbucket: review exits non-zero" "1" "$?"
assert_contains "bitbucket: says the issue tracker was removed" "removed its native issue tracker" "$err"
assert_eq "bitbucket: no request sent" "" "$(cat "$T2247_DIR/curl_calls")"
assert_eq "bitbucket: no review backend left" "" "$(declare -F | awk '{print $3}' | grep -x 'review_bitbucket_fetch_comments')"

# --- Tests 31-35: review comments come from every page, oldest first, of any
# size, and an incomplete read keeps what it read (t2252) ---
. "$PROJECT_DIR/tests/lib/gh_contribution_stub.sh"
T2252_GH="$(mktemp -d)"
gh_contribution_stub_install "$T2252_GH"
_t2252_saved_token="${GITLAB_TOKEN-}"
export GITLAB_TOKEN="test-token"
_t2252_marker="<!-- overlap-results"
_t2252_review="$PROJECT_DIR/.aitask-scripts/aitask_contribution_review.sh"
CHECK_PLATFORM=gitlab

echo "--- Test 31: review_gitlab_fetch_comments reads every page ---"
export GLAB_STUB_NOTES=paged
ARG_REPO="o/r"
out=$(review_gitlab_fetch_comments 100 2>/dev/null)
assert_eq "REST: review reads every note of a 150-note thread" "150" "$(jq length <<< "$out")"
ARG_REPO=""
: > "$T2247_DIR/glab_calls"
out=$(review_gitlab_fetch_comments 100 2>/dev/null)
assert_eq "glab: review reads every note of a 150-note thread" "150" "$(jq length <<< "$out")"
assert_contains "glab: review comments include the analysis" "$_t2252_marker" "$out"
assert_contains "glab: review notes read via api --paginate" "api --paginate projects/:id/issues/100/notes" \
    "$(cat "$T2247_DIR/glab_calls")"
assert_not_contains "glab: review notes not read via glab issue view" "issue view" "$(cat "$T2247_DIR/glab_calls")"
unset GLAB_STUB_NOTES

echo "--- Test 32: GitLab comments come oldest first, so the newest analysis is used ---"
# Newest first, as GitLab serves notes: a newer analysis (id 3), a reply (id 2)
# and an older analysis (id 1), built from the captured notes with the
# single-line marker format_overlap_comment emits.
jq -c '.[0] as $thanks | .[1] as $overlap
    | [ ($overlap | .id = 3 | .body = "## Contribution Overlap Analysis\n\n<!-- overlap-results top_overlaps: 30:7 overlap_check_version: 1 -->"),
        ($thanks | .id = 2),
        ($overlap | .id = 1 | .body = "## Contribution Overlap Analysis\n\n<!-- overlap-results top_overlaps: 10:8 overlap_check_version: 1 -->") ]' \
    "$T2247_DIR/notes_100.json" > "$T2247_DIR/notes_100.twice.json"
export GLAB_STUB_NOTES=twice
for _t2252_path in rest glab; do
    if [[ "$_t2252_path" == rest ]]; then ARG_REPO="o/r"; else ARG_REPO=""; fi
    result=$(parse_overlap_from_comments "$(review_gitlab_fetch_comments 100 2>/dev/null)" "99")
    assert_eq "$_t2252_path: exactly the newest analysis's overlaps are used" "OVERLAP:30:7" "$result"
done
unset GLAB_STUB_NOTES

echo "--- Test 33: fetch keeps a comment set larger than one argument (128 KB) ---"
# Run as a process: under this file's set +e a crashed --argjson would not
# abort the sourced cmd_fetch, and its exit status would prove nothing.
_t2252_fetch_count() {  # fetch output -> .comments | length of its ISSUE_JSON
    sed -n '/^ISSUE_JSON:/,/^HAS_METADATA:/p' | sed '1s/^ISSUE_JSON://; $d' | jq '.comments | length'
}
export -f gh _gh_stub_log
for _t2252_case in "gitlab REST|GLAB_STUB_NOTES=large|--platform gitlab --repo o/r" \
                   "gitlab glab|GLAB_STUB_NOTES=large|--platform gitlab" \
                   "github|GH_STUB_COMMENTS=large|--platform github --repo o/r"; do
    IFS='|' read -r _t2252_name _t2252_knob _t2252_args <<< "$_t2252_case"
    rc=0
    # shellcheck disable=SC2086  # the platform arguments split on purpose
    out=$(env "$_t2252_knob" bash "$_t2252_review" fetch 100 $_t2252_args 2>/dev/null) || rc=$?
    assert_eq "$_t2252_name: fetch exits 0 on an 800 KB thread" "0" "$rc"
    assert_eq "$_t2252_name: fetch keeps all 41 comments" "41" "$(_t2252_fetch_count <<< "$out")"
done
export -fn gh _gh_stub_log

echo "--- Test 34: an incomplete read keeps the comments that were read ---"
CHECK_PLATFORM=gitlab
ARG_REPO="o/r"
rc=0
out=$(GLAB_STUB_NOTES=long GLAB_STUB_CURL_FAIL_PAGE=2 review_gitlab_fetch_comments 100 2>/dev/null) || rc=$?
assert_eq "REST: review reports a failed notes page 2 (returns 1)" "1" "$rc"
assert_contains "REST: the page-1 analysis is still among the comments read" "$_t2252_marker" "$out"
rc=0
err=$(GLAB_STUB_NOTES=long GLAB_STUB_CURL_FAIL_PAGE=2 cmd_fetch 100 2>&1 >/dev/null) || rc=$?
assert_contains "REST: fetch warns that the comments are incomplete" "Could not read every comment on issue #100" "$err"
assert_eq "REST: fetch still succeeds on an incomplete comment read" "0" "$rc"

echo "--- Test 35: a malformed glab notes response is incomplete, its pages still read ---"
ARG_REPO=""
{ cat "$T2247_DIR/notes_100.json"; printf '{"message":"500 Internal Server Error"}\n'; } \
    > "$T2247_DIR/raw_mixed_found.json"
rc=0
out=$(GLAB_STUB_API_RAW="$T2247_DIR/raw_mixed_found.json" review_gitlab_fetch_comments 100 2>/dev/null) || rc=$?
assert_eq "glab: an error object in the notes response is reported (returns 1)" "1" "$rc"
assert_eq "glab: the notes of the page before it are kept" "2" "$(jq length <<< "$out")"

unset -f gh
rm -rf "$T2252_GH"
if [[ -n "$_t2252_saved_token" ]]; then GITLAB_TOKEN="$_t2252_saved_token"; else unset GITLAB_TOKEN; fi
ARG_REPO=""
CHECK_PLATFORM=""

PATH="$_t2247_saved_path"
rm -rf "$T2247_DIR"
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
