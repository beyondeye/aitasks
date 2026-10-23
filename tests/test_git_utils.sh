#!/usr/bin/env bash
# test_git_utils.sh - Tests for .aitask-scripts/lib/git_utils.sh
# Run: bash tests/test_git_utils.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
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
        cd "$dir" || exit 1
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

# Point origin/HEAD at <target> with no remote configured: a bare ref setup is
# enough for detect_primary_branch, which only reads refs.
set_origin_head() {
    local dir="$1" target="$2"
    (
        cd "$dir" || exit 1
        case "$target" in
            refs/remotes/*) git update-ref "$target" HEAD ;;
        esac
        git symbolic-ref refs/remotes/origin/HEAD "$target"
    )
}

# --- Test 5: a local branch named origin/main makes --short ambiguous (t2123) ---
echo "--- Test 5: local origin/main branch beside origin/HEAD ---"
make_repo "$TMPROOT/ambig_main" main
set_origin_head "$TMPROOT/ambig_main" refs/remotes/origin/main
( cd "$TMPROOT/ambig_main" && git branch origin/main )
short=$(cd "$TMPROOT/ambig_main" && git symbolic-ref --quiet --short refs/remotes/origin/HEAD)
assert_eq "fixture: --short is ambiguous here" "remotes/origin/main" "$short"
result=$(cd "$TMPROOT/ambig_main" && detect_primary_branch)
assert_eq "ambiguous --short still resolves main" "main" "$result"

# --- Test 6: the origin/HEAD answer survives the ambiguity (not the probe) ---
# The probe would say main; only the symbolic-ref path can produce trunk.
echo "--- Test 6: local origin/trunk branch, origin/HEAD -> trunk ---"
make_repo "$TMPROOT/ambig_trunk" main
set_origin_head "$TMPROOT/ambig_trunk" refs/remotes/origin/trunk
( cd "$TMPROOT/ambig_trunk" && git branch origin/trunk )
short=$(cd "$TMPROOT/ambig_trunk" && git symbolic-ref --quiet --short refs/remotes/origin/HEAD)
assert_eq "fixture: --short is ambiguous here" "remotes/origin/trunk" "$short"
result=$(cd "$TMPROOT/ambig_trunk" && detect_primary_branch)
assert_eq "ambiguous --short resolves origin/HEAD's trunk" "trunk" "$result"

# --- Test 7: origin/HEAD outside refs/remotes/origin/ is not trusted ---
# The target (trunk) must differ from the probe's answer (main), or the test
# cannot tell a rejected target from an accepted one.
echo "--- Test 7: origin/HEAD -> refs/heads/trunk falls through to the probe ---"
make_repo "$TMPROOT/outside" main
( cd "$TMPROOT/outside" && git branch trunk )
set_origin_head "$TMPROOT/outside" refs/heads/trunk
short=$(cd "$TMPROOT/outside" && git symbolic-ref --quiet --short refs/remotes/origin/HEAD)
assert_eq "fixture: --short names the outside target" "trunk" "$short"
result=$(cd "$TMPROOT/outside" && detect_primary_branch)
assert_eq "outside-prefix origin/HEAD falls through to main" "main" "$result"

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
