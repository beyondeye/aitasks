#!/usr/bin/env bash
# test_contribution_check.sh - Tests for aitask_contribution_check.sh
# Run: bash tests/test_contribution_check.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

# Source the script functions without running main (BASH_SOURCE guard)
source "$PROJECT_DIR/.aitask-scripts/aitask_contribution_check.sh"

# Disable strict mode for test error handling
set +e

echo "=== Contribution Check Tests ==="
echo ""

# --- Test 1: compute_overlap_score — exact match ---
echo "--- Test 1: Exact match (file + dir + area + type) ---"
compute_overlap_score \
    "src/main.py" "src" "backend" "bugfix" \
    "src/main.py" "src" "backend" "bugfix"
assert_eq "exact match score" "8" "$OVERLAP_SCORE"
assert_contains "exact match detail has files" "files:" "$OVERLAP_DETAIL"
assert_contains "exact match detail has dirs" "dirs:" "$OVERLAP_DETAIL"
assert_contains "exact match detail has areas" "areas:" "$OVERLAP_DETAIL"
assert_contains "exact match detail has change_type" "change_type:" "$OVERLAP_DETAIL"

# --- Test 2: compute_overlap_score — no overlap ---
echo "--- Test 2: No overlap ---"
compute_overlap_score \
    "src/main.py" "src" "backend" "bugfix" \
    "tests/test_ui.js" "tests" "frontend" "enhancement"
assert_eq "no overlap score" "0" "$OVERLAP_SCORE"
assert_eq "no overlap detail" "" "$OVERLAP_DETAIL"

# --- Test 3: compute_overlap_score — directory-only overlap ---
echo "--- Test 3: Directory-only overlap ---"
compute_overlap_score \
    "src/main.py" "src" "backend" "bugfix" \
    "src/utils.py" "src" "frontend" "enhancement"
assert_eq "dir-only score" "2" "$OVERLAP_SCORE"
assert_contains "dir-only detail has dirs" "dirs:" "$OVERLAP_DETAIL"

# --- Test 4: compute_overlap_score — empty fields ---
echo "--- Test 4: Empty fields ---"
compute_overlap_score "" "" "" "" "" "" "" ""
assert_eq "empty fields score" "0" "$OVERLAP_SCORE"
assert_eq "empty fields detail" "" "$OVERLAP_DETAIL"

# --- Test 5: compute_overlap_score — multiple shared files ---
echo "--- Test 5: Multiple shared files ---"
compute_overlap_score \
    "a.sh,b.sh,c.sh" "scripts" "cli" "feature" \
    "a.sh,b.sh,d.sh" "scripts,lib" "cli,tests" "enhancement"
# 2 files×3=6, 1 dir(scripts)×2=2, 1 area(cli)×2=2, type mismatch=0 → 10
assert_eq "multi-file score" "10" "$OVERLAP_SCORE"
assert_contains "multi-file detail has files" "files:" "$OVERLAP_DETAIL"

# --- Test 6: format_overlap_comment — with scored results ---
echo "--- Test 6: Format comment with results ---"
LABEL_SUGGESTIONS=""
local_results=("9:42:Fix auth:files- src/auth.py (+3); dirs- src (+2); areas- backend (+2):https://example.com/42" "4:55:Update docs:dirs- docs (+2); areas- docs (+2):https://example.com/55")
format_overlap_comment local_results "100"
assert_contains "comment has header" "Contribution Overlap Analysis" "$OVERLAP_COMMENT"
assert_contains "comment has table header" "| Issue | Score |" "$OVERLAP_COMMENT"
assert_contains "comment has issue 42" "#42" "$OVERLAP_COMMENT"
assert_contains "comment has issue 55" "#55" "$OVERLAP_COMMENT"
assert_contains "comment has high severity" "high" "$OVERLAP_COMMENT"
assert_contains "comment has likely severity" "likely" "$OVERLAP_COMMENT"
assert_contains "comment has machine-readable block" "<!-- overlap-results" "$OVERLAP_COMMENT"
assert_contains "comment has version" "overlap_check_version: 1" "$OVERLAP_COMMENT"
assert_contains "comment has top_overlaps" "top_overlaps:" "$OVERLAP_COMMENT"

# --- Test 7: format_overlap_comment — no results ---
echo "--- Test 7: Format comment with no results ---"
LABEL_SUGGESTIONS=""
empty_arr=()
format_overlap_comment empty_arr "100"
assert_contains "no results message" "No overlapping" "$OVERLAP_COMMENT"
assert_contains "no results has version" "overlap_check_version: 1" "$OVERLAP_COMMENT"
assert_not_contains "no results no table" "| Issue |" "$OVERLAP_COMMENT"

# --- Test 8: parse_contribute_metadata — full body with fingerprint ---
echo "--- Test 8: Parse full fingerprint metadata ---"
body_8="# Feature

Some description.

<!-- aitask-contribute-metadata
contributor: fpuser
contributor_email: fp@users.noreply.github.com
based_on_version: 0.10.0
fingerprint_version: 1
areas: scripts,claude-skills
file_paths: .aitask-scripts/foo.sh,.aitask-scripts/bar.sh
file_dirs: .aitask-scripts
change_type: enhancement
auto_labels: area:scripts,scope:enhancement
-->"

parse_contribute_metadata "$body_8"
assert_eq "8 contributor" "fpuser" "$CONTRIBUTE_CONTRIBUTOR"
assert_eq "8 email" "fp@users.noreply.github.com" "$CONTRIBUTE_EMAIL"
assert_eq "8 fingerprint_version" "1" "$CONTRIBUTE_FINGERPRINT_VERSION"
assert_eq "8 areas" "scripts,claude-skills" "$CONTRIBUTE_AREAS"
assert_eq "8 file_paths" ".aitask-scripts/foo.sh,.aitask-scripts/bar.sh" "$CONTRIBUTE_FILE_PATHS"
assert_eq "8 file_dirs" ".aitask-scripts" "$CONTRIBUTE_FILE_DIRS"
assert_eq "8 change_type" "enhancement" "$CONTRIBUTE_CHANGE_TYPE"
assert_eq "8 auto_labels" "area:scripts,scope:enhancement" "$CONTRIBUTE_AUTO_LABELS"

# --- Test 9: parse_contribute_metadata — body without metadata ---
echo "--- Test 9: Body without metadata ---"
body_9="Just a regular issue body.

No metadata here."

parse_contribute_metadata "$body_9"
assert_eq "9 contributor empty" "" "$CONTRIBUTE_CONTRIBUTOR"
assert_eq "9 email empty" "" "$CONTRIBUTE_EMAIL"
assert_eq "9 fingerprint_version empty" "" "$CONTRIBUTE_FINGERPRINT_VERSION"
assert_eq "9 areas empty" "" "$CONTRIBUTE_AREAS"
assert_eq "9 file_paths empty" "" "$CONTRIBUTE_FILE_PATHS"
assert_eq "9 file_dirs empty" "" "$CONTRIBUTE_FILE_DIRS"

# --- Test 10: Threshold classification ---
echo "--- Test 10: Threshold classification ---"
result_high=$(classify_overlap 9)
result_likely=$(classify_overlap 5)
result_low=$(classify_overlap 2)
result_boundary_high=$(classify_overlap 7)
result_boundary_likely=$(classify_overlap 4)
result_zero=$(classify_overlap 0)
assert_eq "score 9 = high" "high" "$result_high"
assert_eq "score 5 = likely" "likely" "$result_likely"
assert_eq "score 2 = low" "low" "$result_low"
assert_eq "score 7 = high" "high" "$result_boundary_high"
assert_eq "score 4 = likely" "likely" "$result_boundary_likely"
assert_eq "score 0 = low" "low" "$result_zero"

# --- Test 11: Syntax check ---
echo "--- Test 11: Syntax check ---"
TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/.aitask-scripts/aitask_contribution_check.sh" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Syntax check failed for aitask_contribution_check.sh"
fi

# --- Test 12: Help output ---
echo "--- Test 12: Help output ---"
TOTAL=$((TOTAL + 1))
help_output=$("$PROJECT_DIR/.aitask-scripts/aitask_contribution_check.sh" --help 2>&1)
help_exit=$?
if [[ "$help_exit" -eq 0 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: --help did not exit 0 (got $help_exit)"
fi
assert_contains "help shows usage" "Usage:" "$help_output"
assert_contains "help shows platform" "--platform" "$help_output"
assert_contains "help shows dry-run" "--dry-run" "$help_output"

# --- Test 13: compute_overlap_score — area-only overlap ---
echo "--- Test 13: Area-only overlap ---"
compute_overlap_score \
    "src/main.py" "src" "backend,api" "bugfix" \
    "lib/other.py" "lib" "api" "enhancement"
assert_eq "area-only score" "2" "$OVERLAP_SCORE"
assert_contains "area-only detail has areas" "areas:" "$OVERLAP_DETAIL"

# --- Test 14: compute_overlap_score — change_type only match ---
echo "--- Test 14: Change type only match ---"
compute_overlap_score \
    "src/main.py" "src" "backend" "bugfix" \
    "tests/test.py" "tests" "testing" "bugfix"
# No file/dir/area overlap, only change_type match = 1
assert_eq "type-only score" "1" "$OVERLAP_SCORE"
assert_contains "type-only detail" "change_type:" "$OVERLAP_DETAIL"

# --- Test 15: format_overlap_comment — with label suggestions ---
echo "--- Test 15: Format comment with label suggestions ---"
LABEL_SUGGESTIONS="Matching repo labels: \`area:scripts, scope:enhancement\`"
label_results=("5:33:Some fix:dirs- src (+2); areas- backend (+2):https://example.com/33")
format_overlap_comment label_results "100"
assert_contains "comment has label suggestions" "Suggested Labels" "$OVERLAP_COMMENT"
assert_contains "comment has matching labels" "area:scripts" "$OVERLAP_COMMENT"

# --- Test 16: Idempotency — github_has_overlap_comment detects existing comment ---
echo "--- Test 16: Idempotency — existing overlap comment detected ---"
# Mock gh to return comments containing the overlap marker
gh() {
    cat <<'MOCK_EOF'
Some unrelated comment body
---
## Contribution Overlap Analysis

| Issue | Score | Overlap | Detail |
|-------|-------|---------|--------|

<!-- overlap-results top_overlaps: 5:3 overlap_check_version: 1 -->
MOCK_EOF
}
export -f gh
ARG_REPO=""
TOTAL=$((TOTAL + 1))
if github_has_overlap_comment "99"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: github_has_overlap_comment should detect existing overlap comment"
fi

# --- Test 17: Idempotency — no overlap comment present ---
echo "--- Test 17: Idempotency — no overlap comment present ---"
gh() {
    echo "Just a regular comment without any markers"
}
export -f gh
TOTAL=$((TOTAL + 1))
if github_has_overlap_comment "99"; then
    FAIL=$((FAIL + 1))
    echo "FAIL: github_has_overlap_comment should return false when no overlap comment exists"
else
    PASS=$((PASS + 1))
fi

# --- Test 18: Idempotency — empty comments ---
echo "--- Test 18: Idempotency — empty comments ---"
gh() {
    echo ""
}
export -f gh
TOTAL=$((TOTAL + 1))
if github_has_overlap_comment "99"; then
    FAIL=$((FAIL + 1))
    echo "FAIL: github_has_overlap_comment should return false for empty comments"
else
    PASS=$((PASS + 1))
fi

# --- Test 19: Idempotency — source_has_overlap_comment dispatcher ---
echo "--- Test 19: Idempotency — dispatcher routes to correct platform ---"
CHECK_PLATFORM="github"
gh() {
    cat <<'MOCK_EOF'
<!-- overlap-results overlap_check_version: 1 -->
MOCK_EOF
}
export -f gh
TOTAL=$((TOTAL + 1))
if source_has_overlap_comment "99"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: source_has_overlap_comment should detect existing comment via github backend"
fi

# Restore: unset mock
unset -f gh

# --- Tests 20-24: unlabeled external contributions are visible (t2235) ---
# GitHub silently drops labels from authors without push access, so the
# listing must find contribution issues by label OR metadata, across every
# page of open issues, and apply --limit only after filtering.
. "$PROJECT_DIR/tests/lib/gh_contribution_stub.sh"
T2235_DIR="$(mktemp -d)"
gh_contribution_stub_install "$T2235_DIR"
ARG_REPO="o/r"
ARG_LIMIT=50

echo "--- Test 20: listing finds unlabeled metadata issues past newer ordinary ones ---"
listed=$(github_list_contribution_issues)
assert_eq "listing exits 0" "0" "$?"
assert_eq "labeled + unlabeled-metadata issues, newest first; no ordinary issue, PR or plain #14" \
    "101,100,15,12" "$(printf '%s' "$listed" | jq -r '[.[].number] | join(",")')"
assert_eq "output keeps the gh issue list shape (url from html_url)" \
    "https://github.com/o/r/issues/100" \
    "$(printf '%s' "$listed" | jq -r '.[] | select(.number == 100) | .url')"
assert_eq "labels normalised to {name} objects" '[{"name":"contribution"}]' \
    "$(printf '%s' "$listed" | jq -c '.[] | select(.number == 15) | .labels')"
assert_contains "scan is paginated" "--paginate" "$(cat "$T2235_DIR/api_calls")"
assert_contains "scan targets the --repo issues endpoint" "repos/o/r/issues?state=open" \
    "$(cat "$T2235_DIR/api_calls")"

echo "--- Test 21: --limit applies after filtering ---"
ARG_LIMIT=2
assert_eq "limit 2 keeps the two newest contributions" "101,100" \
    "$(github_list_contribution_issues | jq -r '[.[].number] | join(",")')"
ARG_LIMIT=50

echo "--- Test 22: listing failure propagates ---"
GH_STUB_API_FAIL=1 github_list_contribution_issues >/dev/null 2>&1
assert_eq "gh api failure returns non-zero" "1" "$?"

echo "--- Test 23: overlap check reports the unlabeled overlapping contribution ---"
overlap_out=$(main 100 --platform github --repo o/r --dry-run --silent 2>&1)
assert_contains "unlabeled #101 is reported" "[#101]" "$overlap_out"
assert_contains "#101 scores 8 (high)" "| 8 (high) |" "$overlap_out"
assert_contains "labeled control #15 still reported" "[#15]" "$overlap_out"
assert_contains "#15 scores 5 (likely)" "| 5 (likely) |" "$overlap_out"
assert_not_contains "PR #300 never scored" "[#300]" "$overlap_out"

echo "--- Test 24: self-test: the stub hides contributions from a pre-filter limit ---"
# Guards the fixture itself: without --paginate (or with a pre-filter cap) the
# contributions are unreachable, which is the failure Test 20 must catch.
assert_eq "page 1 alone holds no contribution issue" "0" \
    "$(jq '[.[] | select(.pull_request == null) | select((.body | contains("aitask-contribute-metadata")) or any(.labels[]?; .name == "contribution"))] | length' "$T2235_DIR/page1.json")"

echo "--- Test 25: listing resolves the repository host (GitHub Enterprise) ---"
: > "$T2235_DIR/api_calls"; : > "$T2235_DIR/repo_calls"
ARG_REPO="github.example.com/o/r"
GH_STUB_REPO_URL="https://github.example.com/o/r" github_list_contribution_issues >/dev/null
assert_contains "host resolved via gh repo view with the qualified -R" "repo view -R github.example.com/o/r" "$(cat "$T2235_DIR/repo_calls")"
assert_contains "REST scan targets the Enterprise host" "--hostname github.example.com" "$(cat "$T2235_DIR/api_calls")"
assert_contains "REST path uses OWNER/REPO only" "repos/o/r/issues?state=open" "$(cat "$T2235_DIR/api_calls")"
: > "$T2235_DIR/repo_calls"
ARG_REPO=""
github_list_contribution_issues >/dev/null
assert_eq "no --repo: gh repo view resolves from the local remote (no -R)" "repo view --json url --jq .url" "$(cat "$T2235_DIR/repo_calls")"
GH_STUB_REPO_URL="not a url" github_list_contribution_issues >/dev/null 2>&1
assert_eq "unparseable repo URL fails closed" "1" "$?"
ARG_REPO="o/r"

echo "--- Test 26: author-controlled auto_labels apply only area:/scope: labels ---"
# The workflow now runs on issues opened by anyone, with issues:write. A hostile
# body must not get arbitrary existing repo labels applied.
jq --arg al "auto_labels: area:scripts,approved,priority:high,scope:bug,area:,scope:" \
    '.body |= sub("auto_labels: [^\n]*"; $al)' "$T2235_DIR/issue100.json" > "$T2235_DIR/i.json" &&
    mv "$T2235_DIR/i.json" "$T2235_DIR/issue100.json"
: > "$T2235_DIR/edit_calls"
GH_STUB_REPO_LABELS='[{"name":"area:scripts"},{"name":"approved"},{"name":"priority:high"},{"name":"scope:bug"},{"name":"area:"},{"name":"scope:"}]' \
    main 100 --platform github --repo o/r --silent >/dev/null 2>&1
edits=$(cat "$T2235_DIR/edit_calls")
assert_contains "area:scripts applied" "--add-label area:scripts" "$edits"
assert_contains "scope:bug applied" "--add-label scope:bug" "$edits"
assert_not_contains "approved never applied" "--add-label approved" "$edits"
assert_not_contains "priority:high never applied" "--add-label priority:high" "$edits"
assert_not_contains "empty-value area: never applied" "--add-label area: " "$edits "
assert_eq "exactly two labels applied" "2" "$(grep -c -- '--add-label' <<< "$edits")"
assert_eq "_is_auto_applicable_label rejects a bare prefix" "1" "$(_is_auto_applicable_label "scope:"; echo $?)"

unset -f gh
rm -rf "$T2235_DIR"
ARG_REPO=""

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
