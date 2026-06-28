#!/usr/bin/env bash
# test_install_tarball_download.sh - Tests for install.sh download_tarball()'s
# rate-limit-resilient strategy (t1075):
#   - explicit version (--version / AIT_TARGET_VERSION) -> deterministic
#     release-assets CDN URL, with NO api.github.com call;
#   - no version -> latest resolved via git tags (numeric sort), then CDN URL;
#   - explicit version whose CDN download fails -> die (never silently install
#     "latest");
#   - REST API last resort honors GH_TOKEN / GITHUB_TOKEN;
#   - --local-tarball path unchanged (zero network).
# Run: bash tests/test_install_tarball_download.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# Shared assertion helpers (see tests/lib/asserts.sh)
. "$PROJECT_DIR/tests/lib/asserts.sh"

# Unit under test — load install.sh's functions only (the --source-only guard
# returns before main() runs). See tests/test_install_merge.sh for the pattern.
# shellcheck source=../install.sh
source "$PROJECT_DIR/install.sh" --source-only
set +euo pipefail

# --- scratch + invocation logs ---------------------------------------------
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
CURL_LOG="$WORK/curl.log"
WGET_LOG="$WORK/wget.log"
GIT_LOG="$WORK/git.log"
DEST="$WORK/out.tar.gz"

# --- stub knobs (set per test) ---------------------------------------------
CURL_DOWNLOAD_RC=0   # exit code the curl stub returns for a download (-o) call
WGET_DOWNLOAD_RC=0   # exit code the wget stub returns for a download (-O) call
CURL_API_BODY=''     # JSON body returned for an api.github.com fetch
GIT_TAGS_OUTPUT=''   # canned `git ls-remote` output

# --- test doubles -----------------------------------------------------------
# curl stub: a call carrying `-o <dest>` is a file download (writes a fake
# tarball, returns CURL_DOWNLOAD_RC); anything else is an API fetch (echoes
# CURL_API_BODY to stdout). Every invocation is appended to CURL_LOG so tests
# can assert which URLs/headers were used.
curl() {
    printf 'curl %s\n' "$*" >> "$CURL_LOG"
    local i j dest=''
    for ((i = 1; i <= $#; i++)); do
        if [[ "${!i}" == "-o" ]]; then
            j=$((i + 1)); dest="${!j}"
        fi
    done
    if [[ -n "$dest" ]]; then
        [[ "$CURL_DOWNLOAD_RC" -eq 0 ]] && echo "fake-tarball" > "$dest"
        return "$CURL_DOWNLOAD_RC"
    fi
    printf '%s' "$CURL_API_BODY"
    return 0
}

# wget stub: `-O <dest>` is a download; `-qO-` (combined) is an API fetch.
wget() {
    printf 'wget %s\n' "$*" >> "$WGET_LOG"
    local i j dest=''
    for ((i = 1; i <= $#; i++)); do
        if [[ "${!i}" == "-O" ]]; then
            j=$((i + 1)); dest="${!j}"
        fi
    done
    if [[ -n "$dest" ]]; then
        [[ "$WGET_DOWNLOAD_RC" -eq 0 ]] && echo "fake-tarball" > "$dest"
        return "$WGET_DOWNLOAD_RC"
    fi
    printf '%s' "$CURL_API_BODY"
    return 0
}

# git stub: intercept `ls-remote` (returns GIT_TAGS_OUTPUT); pass everything
# else through to real git.
git() {
    printf 'git %s\n' "$*" >> "$GIT_LOG"
    if [[ "${1:-}" == "ls-remote" ]]; then
        printf '%s' "$GIT_TAGS_OUTPUT"
        return 0
    fi
    command git "$@"
}

reset_logs() { : > "$CURL_LOG"; : > "$WGET_LOG"; : > "$GIT_LOG"; rm -f "$DEST"; }

# Shared baseline globals consumed by the sourced download_tarball(). Per-test
# overrides are passed as command-prefix assignments to the subshelled call so
# they never leak between tests. (shellcheck can't see the cross-file use.)
# shellcheck disable=SC2034
DOWNLOAD_CMD=curl
# shellcheck disable=SC2034
LOCAL_TARBALL=''
# shellcheck disable=SC2034
TARGET_VERSION=''

echo "=== install.sh download_tarball() Tests ==="
echo ""

# --- Test 1: explicit version (env) -> deterministic CDN URL, no REST API ---
echo "--- Test 1: explicit version via AIT_TARGET_VERSION ---"
reset_logs
CURL_DOWNLOAD_RC=0
( AIT_TARGET_VERSION="0.26.1" download_tarball "$DEST" ) >/dev/null 2>&1; rc=$?
log="$(cat "$CURL_LOG")"
assert_exit_zero_rc "explicit version downloads successfully" "$rc"
assert_contains "uses deterministic CDN asset URL for the requested version" \
    "releases/download/v0.26.1/aitasks-v0.26.1.tar.gz" "$log"
assert_not_contains "no api.github.com call on the explicit-version happy path" \
    "api.github.com" "$log"
assert_file_exists "tarball written to dest" "$DEST"

# --- Test 1b: --version flag (TARGET_VERSION) wins over the env var ---
echo "--- Test 1b: --version flag precedence over AIT_TARGET_VERSION ---"
reset_logs
( AIT_TARGET_VERSION="1.0.0" TARGET_VERSION="2.0.0" download_tarball "$DEST" ) >/dev/null 2>&1; rc=$?
log="$(cat "$CURL_LOG")"
assert_contains "TARGET_VERSION (--version) takes precedence over the env var" \
    "aitasks-v2.0.0.tar.gz" "$log"
assert_not_contains "env-var version is not used when the flag is set" \
    "aitasks-v1.0.0.tar.gz" "$log"

# --- Test 2: no version -> latest via git tags (numeric sort), no REST API ---
echo "--- Test 2: no version, resolve latest via git tags ---"
reset_logs
# Deliberately list 0.9.0 before 0.10.0 to catch lexical-sort regressions.
GIT_TAGS_OUTPUT="$(printf 'abc\trefs/tags/v0.9.0\ndef\trefs/tags/v0.10.0\nghi\trefs/tags/v0.2.1\n')"
( unset AIT_TARGET_VERSION; download_tarball "$DEST" ) >/dev/null 2>&1; rc=$?
log="$(cat "$CURL_LOG")"
assert_exit_zero_rc "no-version path downloads successfully" "$rc"
assert_contains "resolves latest via git tags (0.10.0 > 0.9.0 numerically) and uses CDN URL" \
    "aitasks-v0.10.0.tar.gz" "$log"
assert_not_contains "no api.github.com call when git-tag resolution succeeds" \
    "api.github.com" "$log"

# --- Test 3: explicit version + CDN failure -> die (never silently latest) ---
echo "--- Test 3: explicit version + CDN download failure ---"
reset_logs
CURL_DOWNLOAD_RC=22   # curl HTTP-error exit (e.g. 404 with -f)
( AIT_TARGET_VERSION="0.26.1" download_tarball "$DEST" ) >/dev/null 2>&1; rc=$?
log="$(cat "$CURL_LOG")"
assert_exit_nonzero_rc "explicit version + CDN failure dies" "$rc"
assert_not_contains "explicit-version failure does NOT fall back to the REST API" \
    "api.github.com" "$log"
assert_file_not_exists "no tarball written when the download fails" "$DEST"
CURL_DOWNLOAD_RC=0

# --- Test 4: REST fallback (no version resolvable) honors GH_TOKEN ---
echo "--- Test 4: REST API last resort honors GH_TOKEN ---"
reset_logs
GIT_TAGS_OUTPUT=''   # git resolution yields nothing -> version stays empty
CURL_API_BODY='{"browser_download_url": "https://github.com/beyondeye/aitasks/releases/download/v9.9.9/aitasks-v9.9.9.tar.gz"}'
( unset AIT_TARGET_VERSION; GH_TOKEN="tok-abc123" download_tarball "$DEST" ) >/dev/null 2>&1; rc=$?
log="$(cat "$CURL_LOG")"
assert_exit_zero_rc "REST fallback completes when no version is resolvable" "$rc"
assert_contains "falls back to api.github.com when git resolution is empty" \
    "api.github.com" "$log"
assert_contains "REST fallback sends Authorization: Bearer with GH_TOKEN" \
    "Authorization: Bearer tok-abc123" "$log"
CURL_API_BODY=''

# --- Test 5: --local-tarball path unchanged (zero network) ---
echo "--- Test 5: --local-tarball path ---"
reset_logs
local_src="$WORK/local.tar.gz"
echo "local-content" > "$local_src"
( LOCAL_TARBALL="$local_src" download_tarball "$DEST" ) >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "--local-tarball path succeeds" "$rc"
assert_eq "local tarball copied verbatim to dest" "local-content" "$(cat "$DEST" 2>/dev/null)"
assert_eq "no curl invoked on the --local-tarball path" "" "$(cat "$CURL_LOG")"
assert_eq "no git invoked on the --local-tarball path" "" "$(cat "$GIT_LOG")"

# --- Test 6: wget downloader branch (explicit version) ---
echo "--- Test 6: wget download branch ---"
reset_logs
WGET_DOWNLOAD_RC=0
( DOWNLOAD_CMD=wget AIT_TARGET_VERSION="0.26.1" download_tarball "$DEST" ) >/dev/null 2>&1; rc=$?
wlog="$(cat "$WGET_LOG")"
assert_exit_zero_rc "wget explicit-version download succeeds" "$rc"
assert_contains "wget path uses the deterministic CDN URL" \
    "aitasks-v0.26.1.tar.gz" "$wlog"
assert_not_contains "wget happy path makes no api.github.com call" \
    "api.github.com" "$wlog"

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
