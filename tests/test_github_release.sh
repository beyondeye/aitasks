#!/usr/bin/env bash
# test_github_release.sh - Tests for the shared GitHub-release resolver
# (.aitask-scripts/lib/github_release.sh): API error classification, the
# git-tag fallback, and the combined resolver.
# Run: bash tests/test_github_release.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# Shared assertion helpers (see tests/lib/asserts.sh)
. "$PROJECT_DIR/tests/lib/asserts.sh"

# Unit under test
. "$PROJECT_DIR/.aitask-scripts/lib/github_release.sh"
set +euo pipefail

# --- Test doubles -----------------------------------------------------------
# `curl` stub: emits a body + a trailing "\n<http_code>" line, exactly like the
# real `curl -w '\n%{http_code}'` the helper uses. Behavior is driven by the
# MOCK_CURL_MODE global so each test can pick a response shape.
MOCK_CURL_MODE="ok"
curl() {
    case "$MOCK_CURL_MODE" in
        ok)        printf '%s\n%s' '{"tag_name": "v1.2.3", "name": "Release"}' '200' ;;
        ratelimit) printf '%s\n%s' '{"message":"API rate limit exceeded for 1.2.3.4"}' '403' ;;
        notfound)  printf '%s\n%s' '{"message":"Not Found"}' '404' ;;
        network)   printf '\n%s' '000' ;;   # connection failure: empty body, 000 status
        empty)     printf '' ;;             # curl produced no output at all
    esac
}

# `git` stub: only intercepts `ls-remote`; everything else passes through.
git() {
    if [[ "$1" == "ls-remote" ]]; then
        # Deliberately list 0.9.0 before 0.10.0 to catch lexical-sort regressions.
        printf '%s\t%s\n' \
            'abc123' 'refs/tags/v0.9.0' \
            'def456' 'refs/tags/v0.10.0' \
            'ghi789' 'refs/tags/v0.2.1'
        return 0
    fi
    command git "$@"
}

echo "=== GitHub Release Resolver Tests ==="
echo ""

# --- Test 1: valid release JSON → parsed version, exit 0 ---
echo "--- Test 1: valid release body ---"
MOCK_CURL_MODE="ok"
out="$(github_latest_release_version beyondeye/aitasks 2>/dev/null)"; rc=$?
assert_eq "returns parsed version without leading v" "1.2.3" "$out"
assert_eq "exit 0 on success" "0" "$rc"

# --- Test 2: rate-limited 403 → RATELIMIT / exit 2 ---
echo "--- Test 2: rate-limited response ---"
MOCK_CURL_MODE="ratelimit"
err="$(github_latest_release_version beyondeye/aitasks 2>&1 >/dev/null)"; rc=$?
assert_eq "exit 2 on rate limit" "2" "$rc"
assert_contains "classifies as RATELIMIT" "RATELIMIT" "$err"

# --- Test 3: 404 → NOTFOUND / exit 3 ---
echo "--- Test 3: not-found response ---"
MOCK_CURL_MODE="notfound"
err="$(github_latest_release_version beyondeye/aitasks 2>&1 >/dev/null)"; rc=$?
assert_eq "exit 3 on 404" "3" "$rc"
assert_contains "classifies as NOTFOUND" "NOTFOUND" "$err"

# --- Test 4: empty/unreachable → NETWORK / exit 4 ---
echo "--- Test 4: network failure (empty body, 000 status) ---"
MOCK_CURL_MODE="network"
err="$(github_latest_release_version beyondeye/aitasks 2>&1 >/dev/null)"; rc=$?
assert_eq "exit 4 on 000 status" "4" "$rc"
assert_contains "classifies as NETWORK" "NETWORK" "$err"

echo "--- Test 4b: curl produced no output at all ---"
MOCK_CURL_MODE="empty"
github_latest_release_version beyondeye/aitasks >/dev/null 2>&1; rc=$?
assert_eq "exit 4 on empty output" "4" "$rc"

# --- Test 5: git-tag fallback picks highest version by numeric sort ---
echo "--- Test 5: github_latest_tag_version numeric sort ---"
out="$(github_latest_tag_version beyondeye/aitasks)"
assert_eq "0.10.0 sorts above 0.9.0 (numeric, not lexical)" "0.10.0" "$out"

# --- Test 6: combined resolver falls back to tags when API is rate-limited ---
echo "--- Test 6: github_resolve_latest_version fallback on rate limit ---"
MOCK_CURL_MODE="ratelimit"
out="$(github_resolve_latest_version beyondeye/aitasks 2>/dev/null)"; rc=$?
assert_eq "resolves via git-tag fallback" "0.10.0" "$out"
assert_eq "exit 0 once fallback succeeds" "0" "$rc"

# --- Test 7: combined resolver returns API version on the happy path ---
echo "--- Test 7: github_resolve_latest_version happy path ---"
MOCK_CURL_MODE="ok"
out="$(github_resolve_latest_version beyondeye/aitasks 2>/dev/null)"; rc=$?
assert_eq "returns API version directly" "1.2.3" "$out"
assert_eq "exit 0" "0" "$rc"

# --- Summary ---
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
