#!/usr/bin/env bash
# test_task_git.sh - Tests for task_git(), task_sync(), task_push() and ait git command
# Run: bash tests/test_task_git.sh

set -e

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    expected="$(echo "$expected" | xargs)"
    actual="$(echo "$actual" | xargs)"
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
        echo "FAIL: $desc (expected output containing '$expected')"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qi "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (output should NOT contain '$unexpected')"
    else
        PASS=$((PASS + 1))
    fi
}

assert_file_exists() {
    local desc="$1" file="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$file" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (file '$file' does not exist)"
    fi
}

# --- Setup helpers ---

# Get default branch name for the system
DEFAULT_BRANCH="$(git config --global init.defaultBranch 2>/dev/null || echo "master")"

setup_repo_with_remote() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    git init --bare --quiet "$tmpdir/remote.git"
    git clone --quiet "$tmpdir/remote.git" "$tmpdir/local" 2>/dev/null
    (
        cd "$tmpdir/local"
        git config user.email "test@test.com"
        git config user.name "Test"
        echo "# Test Project" > README.md
        git add README.md
        git commit -m "init" --quiet
        git push --quiet 2>/dev/null
    )
    echo "$tmpdir"
}

setup_local_repo() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    (
        cd "$tmpdir"
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"
        echo "# Test Project" > README.md
        git add README.md
        git commit -m "init" --quiet
    )
    echo "$tmpdir"
}

# Source libraries for direct function testing
# aitask_setup.sh sets SCRIPT_DIR from BASH_SOURCE — we override it after sourcing
SCRIPT_DIR="$PROJECT_DIR/aiscripts"
source "$PROJECT_DIR/aiscripts/lib/task_utils.sh"
source "$PROJECT_DIR/aiscripts/aitask_setup.sh" --source-only
# Restore SCRIPT_DIR — each test that needs setup_data_branch will set it explicitly
SCRIPT_DIR="$TEST_SCRIPT_DIR"
set +euo pipefail

echo "=== task_git / ait git Tests ==="
echo ""

# --- Test 1: Legacy mode detection ---
echo "--- Test 1: Legacy mode detection ---"

TMPDIR_1="$(setup_local_repo)"

_AIT_DATA_WORKTREE=""
pushd "$TMPDIR_1" >/dev/null
_ait_detect_data_worktree
assert_eq "Legacy mode: _AIT_DATA_WORKTREE is '.'" "." "$_AIT_DATA_WORKTREE"
popd >/dev/null

rm -rf "$TMPDIR_1"

# --- Test 2: Branch mode detection (.git file) ---
echo "--- Test 2: Branch mode detection (.git file) ---"

TMPDIR_2="$(setup_local_repo)"

mkdir -p "$TMPDIR_2/.aitask-data"
echo "gitdir: ../.git/worktrees/.aitask-data" > "$TMPDIR_2/.aitask-data/.git"

_AIT_DATA_WORKTREE=""
pushd "$TMPDIR_2" >/dev/null
_ait_detect_data_worktree
assert_eq "Branch mode (.git file): _AIT_DATA_WORKTREE is '.aitask-data'" ".aitask-data" "$_AIT_DATA_WORKTREE"
popd >/dev/null

rm -rf "$TMPDIR_2"

# --- Test 3: Branch mode detection (.git directory) ---
echo "--- Test 3: Branch mode detection (.git directory) ---"

TMPDIR_3="$(setup_local_repo)"

mkdir -p "$TMPDIR_3/.aitask-data/.git"

_AIT_DATA_WORKTREE=""
pushd "$TMPDIR_3" >/dev/null
_ait_detect_data_worktree
assert_eq "Branch mode (.git dir): _AIT_DATA_WORKTREE is '.aitask-data'" ".aitask-data" "$_AIT_DATA_WORKTREE"
popd >/dev/null

rm -rf "$TMPDIR_3"

# --- Test 4: task_git passthrough in legacy mode ---
echo "--- Test 4: task_git passthrough (legacy) ---"

TMPDIR_4="$(setup_local_repo)"

_AIT_DATA_WORKTREE=""
pushd "$TMPDIR_4" >/dev/null
tg_toplevel=$(task_git rev-parse --show-toplevel 2>/dev/null)
g_toplevel=$(git rev-parse --show-toplevel 2>/dev/null)
assert_eq "task_git toplevel matches git toplevel" "$g_toplevel" "$tg_toplevel"
popd >/dev/null

rm -rf "$TMPDIR_4"

# --- Test 5: task_git targets worktree in branch mode ---
echo "--- Test 5: task_git targets worktree (branch mode) ---"

TMPDIR_5="$(setup_repo_with_remote)"
SCRIPT_DIR="$TMPDIR_5/local/aiscripts"
mkdir -p "$SCRIPT_DIR"

(cd "$TMPDIR_5/local" && setup_data_branch </dev/null >/dev/null 2>&1)

_AIT_DATA_WORKTREE=""
pushd "$TMPDIR_5/local" >/dev/null
tg_branch=$(task_git branch --show-current 2>/dev/null)
g_branch=$(git branch --show-current 2>/dev/null)
assert_eq "task_git on aitask-data branch" "aitask-data" "$tg_branch"
assert_eq "git on default branch" "$DEFAULT_BRANCH" "$g_branch"
popd >/dev/null

rm -rf "$TMPDIR_5"

# --- Test 6: ait git in legacy mode ---
echo "--- Test 6: ait git in legacy mode ---"

TMPDIR_6="$(setup_repo_with_remote)"

# Copy ait and aiscripts to test repo
cp "$PROJECT_DIR/ait" "$TMPDIR_6/local/ait"
cp -r "$PROJECT_DIR/aiscripts" "$TMPDIR_6/local/aiscripts"
chmod +x "$TMPDIR_6/local/ait"

(
    cd "$TMPDIR_6/local"
    git add -A && git commit -m "add scripts" --quiet
)

TOTAL=$((TOTAL + 1))
if ait_status_output=$(cd "$TMPDIR_6/local" && ./ait git status 2>/dev/null); then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: ait git status in legacy mode failed"
fi

output=$(cd "$TMPDIR_6/local" && ./ait git branch --show-current 2>/dev/null)
assert_eq "ait git shows default branch (legacy)" "$DEFAULT_BRANCH" "$output"

rm -rf "$TMPDIR_6"

# --- Test 7: ait git in branch mode ---
echo "--- Test 7: ait git in branch mode ---"

TMPDIR_7="$(setup_repo_with_remote)"

# Copy ait and aiscripts
cp "$PROJECT_DIR/ait" "$TMPDIR_7/local/ait"
cp -r "$PROJECT_DIR/aiscripts" "$TMPDIR_7/local/aiscripts"
chmod +x "$TMPDIR_7/local/ait"

(cd "$TMPDIR_7/local" && git add -A && git commit -m "add scripts" --quiet && git push --quiet 2>/dev/null)

# setup_data_branch uses SCRIPT_DIR/.. to find the project root
SCRIPT_DIR="$TMPDIR_7/local/aiscripts"
(cd "$TMPDIR_7/local" && setup_data_branch </dev/null >/dev/null 2>&1)

# Create a test file in the data worktree
mkdir -p "$TMPDIR_7/local/.aitask-data/aitasks"
echo "test content" > "$TMPDIR_7/local/.aitask-data/aitasks/test_untracked.md"

# ait git should see changes in the data worktree
ait_output=$(cd "$TMPDIR_7/local" && ./ait git status --porcelain 2>/dev/null)
assert_contains "ait git sees data worktree changes" "aitasks" "$ait_output"

# plain git should NOT see it (gitignored)
git_output=$(cd "$TMPDIR_7/local" && git status --porcelain 2>/dev/null)
assert_not_contains "plain git does NOT see data worktree file" "test_untracked" "$git_output"

# ait git branch should show data branch
ait_branch=$(cd "$TMPDIR_7/local" && ./ait git branch --show-current 2>/dev/null)
assert_eq "ait git on aitask-data branch" "aitask-data" "$ait_branch"

rm -rf "$TMPDIR_7"

# --- Test 8: task_sync pulls remote changes ---
echo "--- Test 8: task_sync pulls remote changes ---"

TMPDIR_8="$(setup_repo_with_remote)"

# Push a change from a second clone
git clone --quiet "$TMPDIR_8/remote.git" "$TMPDIR_8/pc2" 2>/dev/null
(
    cd "$TMPDIR_8/pc2"
    git config user.email "test@test.com"
    git config user.name "Test"
    echo "synced content" > synced_file.txt
    git add synced_file.txt
    git commit -m "add synced file" --quiet
    git push --quiet 2>/dev/null
)

# Sync in the original clone
_AIT_DATA_WORKTREE=""
pushd "$TMPDIR_8/local" >/dev/null
task_sync
assert_file_exists "task_sync pulled synced_file.txt" "$TMPDIR_8/local/synced_file.txt"
popd >/dev/null

rm -rf "$TMPDIR_8"

# --- Test 9: task_push sends changes ---
echo "--- Test 9: task_push sends changes ---"

TMPDIR_9="$(setup_repo_with_remote)"

(
    cd "$TMPDIR_9/local"
    echo "pushed content" > pushed_file.txt
    git add pushed_file.txt
    git commit -m "add pushed file" --quiet
)

_AIT_DATA_WORKTREE=""
pushd "$TMPDIR_9/local" >/dev/null
task_push
popd >/dev/null

# Verify by cloning and checking
git clone --quiet "$TMPDIR_9/remote.git" "$TMPDIR_9/verify" 2>/dev/null
assert_file_exists "task_push sent pushed_file.txt to remote" "$TMPDIR_9/verify/pushed_file.txt"

rm -rf "$TMPDIR_9"

# --- Test 10: Caching behavior ---
echo "--- Test 10: Caching behavior ---"

TMPDIR_10="$(setup_local_repo)"

_AIT_DATA_WORKTREE=""
pushd "$TMPDIR_10" >/dev/null

# First detection: no .aitask-data, should be legacy
_ait_detect_data_worktree
assert_eq "First detect: legacy mode" "." "$_AIT_DATA_WORKTREE"

# Now create .aitask-data/.git (would trigger branch mode on fresh detection)
mkdir -p ".aitask-data"
echo "gitdir: fake" > ".aitask-data/.git"

# Second detection: should still return cached "." value
_ait_detect_data_worktree
assert_eq "Second detect: still cached as legacy" "." "$_AIT_DATA_WORKTREE"

popd >/dev/null

rm -rf "$TMPDIR_10"

# --- Test 11: Syntax check + shellcheck ---
echo "--- Test 11: Syntax check ---"

TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/aiscripts/lib/task_utils.sh" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: bash -n task_utils.sh (syntax error)"
fi

if command -v shellcheck &>/dev/null; then
    TOTAL=$((TOTAL + 1))
    sc_errors=$(shellcheck --severity=error "$PROJECT_DIR/aiscripts/lib/task_utils.sh" 2>&1 | wc -l | tr -d ' ')
    if [[ "$sc_errors" -eq 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: shellcheck found errors in task_utils.sh"
        shellcheck --severity=error "$PROJECT_DIR/aiscripts/lib/task_utils.sh" 2>&1 | head -20
    fi
fi

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
