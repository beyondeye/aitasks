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
