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

# --- Tests 27-32: unlabeled external contributions are visible on GitLab (t2241) ---
# GitLab silently drops labels supplied by authors who are not project members,
# so the GitLab listing must find contribution issues by label OR metadata,
# across every page of open issues, on both the glab and the curl path.
. "$PROJECT_DIR/tests/lib/glab_contribution_stub.sh"
T2241_DIR="$(mktemp -d)"
glab_contribution_stub_install "$T2241_DIR"
_t2241_saved_path="$PATH"
PATH="$T2241_DIR/bin:$PATH"
_t2241_saved_token="${GITLAB_TOKEN-}"
export GITLAB_TOKEN="test-token"
ARG_LIMIT=50
_t2241_numbers() { jq -r '[.[].number] | join(",")'; }

echo "--- Test 27: curl path finds unlabeled metadata issues past newer ordinary ones ---"
ARG_REPO="o/r"
: > "$T2241_DIR/curl_calls"
listed=$(gitlab_list_contribution_issues)
assert_eq "curl listing exits 0" "0" "$?"
assert_eq "curl: labeled + unlabeled-metadata issues, newest first; no ordinary or plain #14" \
    "101,100,15,12" "$(printf '%s' "$listed" | _t2241_numbers)"
assert_eq "curl: output keeps the listing shape (url from web_url)" \
    "https://gitlab.example/o/r/-/issues/100" \
    "$(printf '%s' "$listed" | jq -r '.[] | select(.number == 100) | .url')"
assert_eq "curl: body from description" "true" \
    "$(printf '%s' "$listed" | jq '.[] | select(.number == 100) | .body | contains("aitask-contribute-metadata")')"
assert_eq "curl: labels normalised to {name} objects" '[{"name":"contribution"}]' \
    "$(printf '%s' "$listed" | jq -c '.[] | select(.number == 15) | .labels')"
curl_calls=$(cat "$T2241_DIR/curl_calls")
assert_contains "curl: second page requested" "page=2" "$curl_calls"
assert_contains "curl: scans open issues of --repo" "projects/o%2Fr/issues?state=opened" "$curl_calls"
assert_not_contains "curl: no server-side label filter" "labels=" "$curl_calls"

echo "--- Test 28: glab path finds the same issues ---"
ARG_REPO=""
: > "$T2241_DIR/glab_calls"
listed=$(gitlab_list_contribution_issues)
assert_eq "glab listing exits 0" "0" "$?"
assert_eq "glab: same contribution set" "101,100,15,12" "$(printf '%s' "$listed" | _t2241_numbers)"
glab_calls=$(cat "$T2241_DIR/glab_calls")
assert_contains "glab: paginated REST scan of open issues" "api --paginate projects/:id/issues?state=opened" "$glab_calls"
assert_not_contains "glab: label-filtered issue list not used" "issue list" "$glab_calls"
listed=$(GLAB_STUB_PAGINATE_FORMAT=concat gitlab_list_contribution_issues)
assert_eq "glab: one-array-per-page output parsed too" "101,100,15,12" "$(printf '%s' "$listed" | _t2241_numbers)"

echo "--- Test 29: --limit applies after filtering (both paths) ---"
ARG_LIMIT=2
ARG_REPO="o/r"
assert_eq "curl: limit 2 keeps the two newest contributions" "101,100" \
    "$(gitlab_list_contribution_issues | _t2241_numbers)"
ARG_REPO=""
assert_eq "glab: limit 2 keeps the two newest contributions" "101,100" \
    "$(gitlab_list_contribution_issues | _t2241_numbers)"
ARG_LIMIT=50

echo "--- Test 30: listing failures fail closed ---"
ARG_REPO="o/r"
out=$(GLAB_STUB_CURL_FAIL_PAGE=2 gitlab_list_contribution_issues 2>/dev/null)
assert_eq "curl: page-2 failure returns non-zero" "1" "$?"
assert_eq "curl: page-2 failure prints no partial list" "" "$out"
: > "$T2241_DIR/curl_calls"
out=$(GLAB_STUB_CURL_REPEAT_PAGE=1 gitlab_list_contribution_issues 2>/dev/null)
assert_eq "curl: a server repeating page 1 returns non-zero" "1" "$?"
assert_eq "curl: repeated page prints no partial list" "" "$out"
assert_eq "curl: repeated page detected on the second request" "2" "$(wc -l < "$T2241_DIR/curl_calls" | tr -d ' ')"
out=$(GITLAB_TOKEN="" gitlab_list_contribution_issues 2>/dev/null)
assert_eq "curl: missing GITLAB_TOKEN returns non-zero" "1" "$?"
assert_eq "curl: missing GITLAB_TOKEN prints nothing" "" "$out"
ARG_REPO=""
out=$(GLAB_STUB_API_FAIL=1 gitlab_list_contribution_issues 2>/dev/null)
assert_eq "glab: api failure returns non-zero" "1" "$?"
assert_eq "glab: api failure prints nothing" "" "$out"

echo "--- Test 31: overlap check reports the unlabeled overlapping contribution ---"
overlap_out=$(main 100 --platform gitlab --repo o/r --dry-run --silent 2>&1)
assert_contains "gitlab: unlabeled #101 is reported" "[#101]" "$overlap_out"
assert_contains "gitlab: #101 scores 8 (high)" "| 8 (high) |" "$overlap_out"
assert_contains "gitlab: labeled control #15 still reported" "[#15]" "$overlap_out"
assert_contains "gitlab: #15 scores 5 (likely)" "| 5 (likely) |" "$overlap_out"

echo "--- Test 32: self-test: the stub models the dropped label ---"
# Guards the fixture itself: page 1 holds no contribution, and the server-side
# label filter returns only the labeled issues — the pre-t2241 view.
assert_eq "page 1 holds no contribution issue" "0" \
    "$(jq '.[0:100] | [.[] | select((.description | contains("aitask-contribute-metadata")) or any(.labels[]; . == "contribution"))] | length' "$T2241_DIR/all.json")"
assert_eq "labels=contribution returns only #15 and #12" "15,12" \
    "$(curl -sf "https://gitlab.example/api/v4/projects/o%2Fr/issues?state=opened&labels=contribution&per_page=100" | jq -r '[.[].iid] | join(",")')"

# --- Tests 33-37: a missing GITLAB_TOKEN fails closed; Bitbucket is retired (t2247) ---
# `curl --header "$(_gitlab_token_header)"` ran curl with an EMPTY header when
# GITLAB_TOKEN was unset: die only exits the command substitution.
echo "--- Test 33: every GitLab REST call fails closed without GITLAB_TOKEN ---"
ARG_REPO="o/r"
_t2247_rest_calls=(
    "gitlab_fetch_issue 100"
    "gitlab_post_comment 100 hello"
    "gitlab_add_label 100 area:scripts"
    "gitlab_list_repo_labels"
    "gitlab_has_overlap_comment 100"
)
for _t2247_call in "${_t2247_rest_calls[@]}"; do
    : > "$T2241_DIR/curl_calls"
    # shellcheck disable=SC2086  # the call string is split into argv on purpose
    _t2247_err=$(GITLAB_TOKEN="" $_t2247_call 2>&1 >/dev/null)
    _t2247_rc=$?
    assert_eq "no token: '$_t2247_call' returns non-zero" "1" "$_t2247_rc"
    assert_contains "no token: '$_t2247_call' names GITLAB_TOKEN" "GITLAB_TOKEN is required" "$_t2247_err"
    assert_eq "no token: '$_t2247_call' sends no request" "" "$(cat "$T2241_DIR/curl_calls")"
done

echo "--- Test 34: with the token, every GitLab REST call authenticates ---"
for _t2247_call in "${_t2247_rest_calls[@]}"; do
    : > "$T2241_DIR/curl_calls"
    : > "$T2241_DIR/curl_auth"
    # shellcheck disable=SC2086
    $_t2247_call >/dev/null 2>&1
    _t2247_n=$(grep -c . "$T2241_DIR/curl_calls")
    assert_eq "token: '$_t2247_call' made a request" "true" "$([[ "$_t2247_n" -ge 1 ]] && echo true || echo false)"
    assert_eq "token: '$_t2247_call' sends the token on every request" "$_t2247_n" \
        "$(grep -c 'PRIVATE-TOKEN: test-token' "$T2241_DIR/curl_auth")"
done
assert_eq "token: overlap lookup finds the existing comment on #100" "0" \
    "$(gitlab_has_overlap_comment 100 >/dev/null 2>&1; echo $?)"
assert_eq "token: overlap lookup finds none on #101" "1" \
    "$(gitlab_has_overlap_comment 101 >/dev/null 2>&1; echo $?)"

echo "--- Test 35: glab-only auth: the overlap lookup goes through glab ---"
# glab authenticated, no GITLAB_TOKEN, no --repo, private project (anonymous
# REST refused). Before t2247 the lookup was REST-only, so it always failed
# here and main() posted a duplicate comment on every run.
ARG_REPO=""
export GLAB_STUB_CURL_REQUIRE_TOKEN=1
: > "$T2241_DIR/curl_calls"
: > "$T2241_DIR/glab_calls"
assert_eq "glab-only: #100 has the overlap comment" "0" \
    "$(GITLAB_TOKEN="" gitlab_has_overlap_comment 100 >/dev/null 2>&1; echo $?)"
assert_eq "glab-only: #101 has none" "1" \
    "$(GITLAB_TOKEN="" gitlab_has_overlap_comment 101 >/dev/null 2>&1; echo $?)"
assert_contains "glab-only: notes read via glab api" "api projects/:id/issues/100/notes" "$(cat "$T2241_DIR/glab_calls")"
assert_eq "glab-only: no REST request" "" "$(cat "$T2241_DIR/curl_calls")"

echo "--- Test 36: glab-only main() does not post a second overlap comment ---"
: > "$T2241_DIR/curl_calls"
: > "$T2241_DIR/glab_calls"
# parse_args only sets flags, so reset the ones Test 31's --dry-run --silent left on:
# a dry run never posts, and would make "posts nothing" pass vacuously.
ARG_DRY_RUN=false
ARG_SILENT=false
_t2247_out=$(GITLAB_TOKEN="" main 100 --platform gitlab 2>&1)
assert_eq "glab-only main exits 0" "0" "$?"
assert_contains "glab-only main sees the existing comment" "Overlap comment already exists on issue #100" "$_t2247_out"
assert_not_contains "glab-only main posts nothing" "issue note" "$(cat "$T2241_DIR/glab_calls")"
assert_eq "glab-only main sends no REST request" "" "$(cat "$T2241_DIR/curl_calls")"
unset GLAB_STUB_CURL_REQUIRE_TOKEN

echo "--- Test 37: Bitbucket runs stop with the issue-tracker removal ---"
: > "$T2241_DIR/curl_calls"
_t2247_err=$( (main 42 --platform bitbucket --repo ws/repo) 2>&1 >/dev/null)
assert_eq "bitbucket: main exits non-zero" "1" "$?"
assert_contains "bitbucket: says the issue tracker was removed" "removed its native issue tracker" "$_t2247_err"
assert_eq "bitbucket: no request sent" "" "$(cat "$T2241_DIR/curl_calls")"
assert_eq "bitbucket: no backend function left" "" \
    "$(declare -F | awk '{print $3}' | grep -E '^(_?bitbucket_)' | grep -vx '_bitbucket_issues_removed')"
ARG_REPO=""

PATH="$_t2241_saved_path"
if [[ -n "$_t2241_saved_token" ]]; then GITLAB_TOKEN="$_t2241_saved_token"; else unset GITLAB_TOKEN; fi
rm -rf "$T2241_DIR"
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
