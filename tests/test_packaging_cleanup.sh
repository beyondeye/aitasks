#!/usr/bin/env bash
# test_packaging_cleanup.sh - Tests install.sh cleanup_packaging_leftover() (t938)
# Run: bash tests/test_packaging_cleanup.sh
#
# Verifies the post-install removal of the framework-release packaging/ directory
# and its blast-radius guard: an UNTRACKED packaging/ (consumer project) is
# removed, but a git-TRACKED packaging/ (the aitasks framework source repo, where
# `ait upgrade` runs install.sh over the working tree) is preserved.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# Shared assertion helpers (see tests/lib/asserts.sh)
. "$PROJECT_DIR/tests/lib/asserts.sh"

# Source install.sh to get cleanup_packaging_leftover() without running main.
# shellcheck source=../install.sh
source "$PROJECT_DIR/install.sh" --source-only
set +euo pipefail

# git_init_quiet <dir> — init a repo with a throwaway identity so commits work.
git_init_quiet() {
    git -C "$1" init -q
    git -C "$1" config user.email "test@example.com"
    git -C "$1" config user.name "Test"
}

echo "=== Packaging Leftover Cleanup Tests ==="
echo ""

# --- Test 1: Source-only guard did not run the installer ---
echo "--- Test 1: source-only guard exposes the function ---"
TOTAL=$((TOTAL + 1))
if declare -F cleanup_packaging_leftover >/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: cleanup_packaging_leftover not defined after source --source-only"
fi

# --- Test 2: Untracked packaging/ in a non-git dir → removed ---
echo "--- Test 2: Untracked packaging (no git repo) → removed ---"
T2="$(mktemp -d)"
mkdir -p "$T2/packaging/shim"
touch "$T2/packaging/shim/ait"
cleanup_packaging_leftover "$T2" >/dev/null 2>&1
assert_dir_not_exists "Untracked packaging removed (no git repo)" "$T2/packaging"
rm -rf "$T2"

# --- Test 3: Untracked packaging/ inside a git repo (not tracked) → removed ---
echo "--- Test 3: Untracked packaging in git repo → removed ---"
T3="$(mktemp -d)"
git_init_quiet "$T3"
mkdir -p "$T3/packaging/shim"
touch "$T3/packaging/shim/ait"
# Commit something unrelated so the repo has a HEAD; packaging stays untracked.
touch "$T3/README"
git -C "$T3" add README
git -C "$T3" commit -qm init
cleanup_packaging_leftover "$T3" >/dev/null 2>&1
assert_dir_not_exists "Untracked packaging removed (git repo, not tracked)" "$T3/packaging"
rm -rf "$T3"

# --- Test 4: Git-tracked packaging/ → preserved (framework-repo guard) ---
echo "--- Test 4: Tracked packaging → preserved ---"
T4="$(mktemp -d)"
git_init_quiet "$T4"
mkdir -p "$T4/packaging/shim"
printf '#!/usr/bin/env bash\n' > "$T4/packaging/shim/ait"
git -C "$T4" add packaging
git -C "$T4" commit -qm "add packaging"
out_4=$(cleanup_packaging_leftover "$T4" 2>&1)
assert_dir_exists "Tracked packaging preserved" "$T4/packaging"
assert_contains_ci "Reports tracked packaging left in place" "git-tracked" "$out_4"
rm -rf "$T4"

# --- Test 5: No packaging/ dir → no-op, rc 0 ---
echo "--- Test 5: Missing packaging → no-op ---"
T5="$(mktemp -d)"
cleanup_packaging_leftover "$T5"
rc_5=$?
assert_exit_zero_rc "Missing packaging is a no-op (rc 0)" "$rc_5"
rm -rf "$T5"

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
