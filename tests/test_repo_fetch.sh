#!/usr/bin/env bash
# test_repo_fetch.sh - Automated tests for aiscripts/lib/repo_fetch.sh
# Run: bash tests/test_repo_fetch.sh
# Run offline only: SKIP_NETWORK=1 bash tests/test_repo_fetch.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source the library under test
source "$PROJECT_DIR/aiscripts/lib/repo_fetch.sh"

PASS=0
FAIL=0
SKIP=0
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
    if echo "$actual" | grep -qi "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got '${actual:0:200}')"
    fi
}

assert_gt() {
    local desc="$1" value="$2" threshold="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$value" -gt "$threshold" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected > $threshold, got $value)"
    fi
}

skip_network() {
    local desc="$1"
    TOTAL=$((TOTAL + 1))
    SKIP=$((SKIP + 1))
    echo "SKIP: $desc (network tests disabled)"
}

# ============================================================
# OFFLINE TESTS — Platform detection
# ============================================================

echo "--- Platform Detection ---"

result=$(repo_detect_platform_from_url "https://github.com/cli/cli/blob/trunk/README.md")
assert_eq "detect github" "github" "$result"

result=$(repo_detect_platform_from_url "https://gitlab.com/gitlab-org/gitlab/-/blob/master/README.md")
assert_eq "detect gitlab" "gitlab" "$result"

result=$(repo_detect_platform_from_url "https://bitbucket.org/tutorials/markdowndemo/src/master/README.md")
assert_eq "detect bitbucket" "bitbucket" "$result"

result=$(repo_detect_platform_from_url "https://example.com/foo/bar")
assert_eq "detect unknown" "" "$result"

# ============================================================
# OFFLINE TESTS — URL parsing
# ============================================================

echo "--- URL Parsing ---"

# GitHub file URL
repo_parse_url "https://github.com/cli/cli/blob/trunk/README.md"
assert_eq "github file: platform" "github" "$_RF_PLATFORM"
assert_eq "github file: owner" "cli" "$_RF_OWNER"
assert_eq "github file: repo" "cli" "$_RF_REPO"
assert_eq "github file: branch" "trunk" "$_RF_BRANCH"
assert_eq "github file: path" "README.md" "$_RF_PATH"
assert_eq "github file: type" "file" "$_RF_TYPE"

# GitLab file URL
repo_parse_url "https://gitlab.com/gitlab-org/gitlab/-/blob/master/README.md"
assert_eq "gitlab file: platform" "gitlab" "$_RF_PLATFORM"
assert_eq "gitlab file: owner" "gitlab-org" "$_RF_OWNER"
assert_eq "gitlab file: repo" "gitlab" "$_RF_REPO"
assert_eq "gitlab file: branch" "master" "$_RF_BRANCH"
assert_eq "gitlab file: path" "README.md" "$_RF_PATH"
assert_eq "gitlab file: type" "file" "$_RF_TYPE"

# Bitbucket file URL
repo_parse_url "https://bitbucket.org/tutorials/markdowndemo/src/master/README.md"
assert_eq "bitbucket file: platform" "bitbucket" "$_RF_PLATFORM"
assert_eq "bitbucket file: owner" "tutorials" "$_RF_OWNER"
assert_eq "bitbucket file: repo" "markdowndemo" "$_RF_REPO"
assert_eq "bitbucket file: branch" "master" "$_RF_BRANCH"
assert_eq "bitbucket file: path" "README.md" "$_RF_PATH"
assert_eq "bitbucket file: type" "file" "$_RF_TYPE"

# GitHub directory URL
repo_parse_url "https://github.com/cli/cli/tree/trunk/docs"
assert_eq "github dir: type" "directory" "$_RF_TYPE"
assert_eq "github dir: path" "docs" "$_RF_PATH"

# GitLab directory URL
repo_parse_url "https://gitlab.com/gitlab-org/gitlab/-/tree/master/doc/api"
assert_eq "gitlab dir: type" "directory" "$_RF_TYPE"
assert_eq "gitlab dir: path" "doc/api" "$_RF_PATH"

# Bitbucket directory URL (no extension = directory)
repo_parse_url "https://bitbucket.org/atlassian/aws-s3-deploy/src/master/pipe"
assert_eq "bitbucket dir: type" "directory" "$_RF_TYPE"
assert_eq "bitbucket dir: path" "pipe" "$_RF_PATH"

# Bitbucket root directory URL (empty path = directory)
repo_parse_url "https://bitbucket.org/atlassian/aws-s3-deploy/src/master/"
assert_eq "bitbucket root dir: type" "directory" "$_RF_TYPE"
assert_eq "bitbucket root dir: path" "" "$_RF_PATH"

# Nested path
repo_parse_url "https://gitlab.com/gitlab-org/gitlab/-/blob/master/doc/api/markdown.md"
assert_eq "nested path: owner" "gitlab-org" "$_RF_OWNER"
assert_eq "nested path: repo" "gitlab" "$_RF_REPO"
assert_eq "nested path: branch" "master" "$_RF_BRANCH"
assert_eq "nested path: path" "doc/api/markdown.md" "$_RF_PATH"
assert_eq "nested path: type" "file" "$_RF_TYPE"

# Trailing slash stripped
repo_parse_url "https://github.com/cli/cli/tree/trunk/docs/"
assert_eq "trailing slash: path" "docs" "$_RF_PATH"

# ============================================================
# NETWORK TESTS — File fetching (gated by SKIP_NETWORK)
# ============================================================

echo "--- File Fetching (network) ---"

if [[ "${SKIP_NETWORK:-0}" == "1" ]]; then
    skip_network "fetch github file"
    skip_network "fetch gitlab file"
    skip_network "fetch bitbucket file"
else
    content=$(repo_fetch_file "https://github.com/cli/cli/blob/trunk/README.md" 2>/dev/null || echo "FETCH_FAILED")
    assert_contains "fetch github file" "GitHub CLI" "$content"

    content=$(repo_fetch_file "https://gitlab.com/gitlab-org/gitlab/-/blob/master/README.md" 2>/dev/null || echo "FETCH_FAILED")
    assert_contains "fetch gitlab file" "GitLab" "$content"

    content=$(repo_fetch_file "https://bitbucket.org/tutorials/markdowndemo/src/master/README.md" 2>/dev/null || echo "FETCH_FAILED")
    assert_contains "fetch bitbucket file" "Markdown" "$content"
fi

# ============================================================
# NETWORK TESTS — Directory listing (gated by SKIP_NETWORK)
# ============================================================

echo "--- Directory Listing (network) ---"

if [[ "${SKIP_NETWORK:-0}" == "1" ]]; then
    skip_network "list github md files"
    skip_network "list gitlab md files"
    skip_network "list bitbucket md files"
else
    listing=$(repo_list_md_files "https://github.com/cli/cli/tree/trunk/docs" 2>/dev/null || echo "")
    count=$(echo "$listing" | grep -c '\.md$' || true)
    assert_gt "list github md files (count > 0)" "$count" 0

    listing=$(repo_list_md_files "https://gitlab.com/gitlab-org/gitlab/-/tree/master/doc/api" 2>/dev/null || echo "")
    count=$(echo "$listing" | grep -c '\.md$' || true)
    assert_gt "list gitlab md files (count > 0)" "$count" 0

    listing=$(repo_list_md_files "https://bitbucket.org/atlassian/aws-s3-deploy/src/master/" 2>/dev/null || echo "")
    assert_contains "list bitbucket md files" "README.md" "$listing"
fi

# ============================================================
# SUMMARY
# ============================================================

echo ""
echo "================================"
echo "Results: $PASS passed, $FAIL failed, $SKIP skipped (of $TOTAL total)"
echo "================================"

if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
