#!/usr/bin/env bash
# test_git_utils.sh - Tests for .aitask-scripts/lib/git_utils.sh
# Run: bash tests/test_git_utils.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=../.aitask-scripts/lib/git_utils.sh
. "$PROJECT_DIR/.aitask-scripts/lib/git_utils.sh"

PASS=0
FAIL=0
TOTAL=0

TMPROOT="$(mktemp -d)"
cleanup() { [[ -n "$TMPROOT" && -d "$TMPROOT" ]] && rm -rf "$TMPROOT"; }
trap cleanup EXIT

# Disable strict mode for assertion-driven flow
set +e

# Init a git repo with <default_branch> as its only branch, one commit.
make_repo() {
    local dir="$1" branch="$2"
    mkdir -p "$dir"
    (
        cd "$dir"
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"
        echo "x" > file.txt
        git add -A
        git commit -m "initial" --quiet
        git branch -M "$branch"
    )
}

echo "=== test_git_utils.sh ==="
echo ""

# --- Test 1: main-default repo (local probe path) ---
echo "--- Test 1: main-default repo ---"
make_repo "$TMPROOT/main_repo" main
result=$(cd "$TMPROOT/main_repo" && detect_primary_branch)
assert_eq "main-default repo resolves main" "main" "$result"

# --- Test 2: master-default repo, no remote (local probe path) ---
echo "--- Test 2: master-default repo (no remote) ---"
make_repo "$TMPROOT/master_repo" master
result=$(cd "$TMPROOT/master_repo" && detect_primary_branch)
assert_eq "master-default repo resolves master" "master" "$result"

# --- Test 3: master-default via origin/HEAD (symbolic-ref path) ---
echo "--- Test 3: master-default via origin/HEAD ---"
make_repo "$TMPROOT/upstream" master
( cd "$TMPROOT/upstream" && git config receive.denyCurrentBranch ignore )
git clone --quiet "$TMPROOT/upstream" "$TMPROOT/clone"
( cd "$TMPROOT/clone" && git remote set-head origin master )
result=$(cd "$TMPROOT/clone" && detect_primary_branch)
assert_eq "clone with origin/HEAD->master resolves master" "master" "$result"

# --- Test 4: non-git directory falls back to main ---
echo "--- Test 4: non-git directory ---"
mkdir -p "$TMPROOT/plain"
result=$(cd "$TMPROOT/plain" && detect_primary_branch)
assert_eq "non-git dir falls back to main" "main" "$result"

# --- Results ---
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
