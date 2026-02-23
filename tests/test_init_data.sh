#!/usr/bin/env bash
# test_init_data.sh - Tests for aitask_init_data.sh (lightweight data branch initialization)
# Run: bash tests/test_init_data.sh

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
    if echo "$actual" | grep -q "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

assert_symlink() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -L "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc ('$path' is not a symlink)"
    fi
}

assert_not_symlink() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ ! -L "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc ('$path' should not be a symlink)"
    fi
}

assert_dir_exists() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -d "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (directory '$path' does not exist)"
    fi
}

# --- Setup helpers ---

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

# Copy the init_data script and its dependency into a test repo
install_script() {
    local repo_dir="$1"
    mkdir -p "$repo_dir/aiscripts/lib"
    cp "$PROJECT_DIR/aiscripts/aitask_init_data.sh" "$repo_dir/aiscripts/"
    cp "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh" "$repo_dir/aiscripts/lib/"
}

# Create aitask-data branch with content using setup_data_branch from aitask_setup.sh
# This sources setup.sh's function to create a proper data branch setup
create_data_branch_setup() {
    local repo_dir="$1"
    # Copy required scripts for setup
    mkdir -p "$repo_dir/aiscripts/lib"
    cp "$PROJECT_DIR/aiscripts/aitask_setup.sh" "$repo_dir/aiscripts/"
    cp "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh" "$repo_dir/aiscripts/lib/"
    cp -r "$PROJECT_DIR/seed" "$repo_dir/seed" 2>/dev/null || true
    (
        cd "$repo_dir"
        # Source setup.sh to get setup_data_branch function
        SCRIPT_DIR="$repo_dir/aiscripts"
        source "$repo_dir/aiscripts/lib/terminal_compat.sh"
        source "$repo_dir/aiscripts/aitask_setup.sh" --source-only
        setup_data_branch </dev/null >/dev/null 2>&1
    )
}

set +euo pipefail

echo "=== aitask_init_data.sh Tests ==="
echo ""

# --- Test 1: Legacy mode ---
echo "--- Test 1: Legacy mode (real aitasks/ directory) ---"

TMPDIR_1="$(setup_local_repo)"
install_script "$TMPDIR_1"
mkdir -p "$TMPDIR_1/aitasks/metadata"

pushd "$TMPDIR_1" >/dev/null
output=$(bash aiscripts/aitask_init_data.sh 2>/dev/null)
assert_eq "Legacy mode output" "LEGACY_MODE" "$output"
assert_not_symlink "aitasks/ is not a symlink" "aitasks"
popd >/dev/null

rm -rf "$TMPDIR_1"

# --- Test 2: Already initialized ---
echo "--- Test 2: Already initialized (worktree exists) ---"

TMPDIR_2="$(setup_repo_with_remote)"
install_script "$TMPDIR_2/local"
create_data_branch_setup "$TMPDIR_2/local"

pushd "$TMPDIR_2/local" >/dev/null
output=$(bash aiscripts/aitask_init_data.sh 2>/dev/null)
assert_eq "Already init output" "ALREADY_INIT" "$output"
assert_symlink "aitasks/ is a symlink" "aitasks"
assert_symlink "aiplans/ is a symlink" "aiplans"
popd >/dev/null

rm -rf "$TMPDIR_2"

# --- Test 3: No data branch ---
echo "--- Test 3: No data branch (fresh repo) ---"

TMPDIR_3="$(setup_local_repo)"
install_script "$TMPDIR_3"

pushd "$TMPDIR_3" >/dev/null
output=$(bash aiscripts/aitask_init_data.sh 2>/dev/null)
assert_eq "No data branch output" "NO_DATA_BRANCH" "$output"
popd >/dev/null

rm -rf "$TMPDIR_3"

# --- Test 4: Initialize from local branch ---
echo "--- Test 4: Initialize from local branch ---"

TMPDIR_4="$(setup_repo_with_remote)"
install_script "$TMPDIR_4/local"
create_data_branch_setup "$TMPDIR_4/local"

# Remove worktree and symlinks but keep the branch
pushd "$TMPDIR_4/local" >/dev/null
git worktree remove .aitask-data --force 2>/dev/null
rm -f aitasks aiplans

# Verify branch still exists locally
branch_exists=$(git show-ref --verify refs/heads/aitask-data >/dev/null 2>&1 && echo "yes" || echo "no")
assert_eq "aitask-data branch exists locally" "yes" "$branch_exists"

# Run init
output=$(bash aiscripts/aitask_init_data.sh 2>/dev/null)
assert_eq "Initialize from local branch output" "INITIALIZED" "$output"
assert_symlink "aitasks/ is a symlink after init" "aitasks"
assert_symlink "aiplans/ is a symlink after init" "aiplans"
assert_dir_exists ".aitask-data worktree created" ".aitask-data"
popd >/dev/null

rm -rf "$TMPDIR_4"

# --- Test 5: Initialize from remote branch ---
echo "--- Test 5: Initialize from remote branch (second clone) ---"

TMPDIR_5="$(setup_repo_with_remote)"
install_script "$TMPDIR_5/local"
create_data_branch_setup "$TMPDIR_5/local"

# Create a second clone — aitask-data branch exists on remote but not locally
git clone --quiet "$TMPDIR_5/remote.git" "$TMPDIR_5/clone2" 2>/dev/null
install_script "$TMPDIR_5/clone2"
(cd "$TMPDIR_5/clone2" && git config user.email "test@test.com" && git config user.name "Test")

pushd "$TMPDIR_5/clone2" >/dev/null
# Verify branch is NOT local but IS on remote
local_branch=$(git show-ref --verify refs/heads/aitask-data 2>/dev/null && echo "yes" || echo "no")
remote_branch=$(git ls-remote --heads origin aitask-data 2>/dev/null | grep -q aitask-data && echo "yes" || echo "no")
assert_eq "aitask-data NOT local in clone2" "no" "$local_branch"
assert_eq "aitask-data IS on remote" "yes" "$remote_branch"

# Run init
output=$(bash aiscripts/aitask_init_data.sh 2>/dev/null)
assert_eq "Initialize from remote branch output" "INITIALIZED" "$output"
assert_symlink "aitasks/ is a symlink in clone2" "aitasks"
assert_symlink "aiplans/ is a symlink in clone2" "aiplans"
assert_dir_exists ".aitask-data worktree created in clone2" ".aitask-data"
popd >/dev/null

rm -rf "$TMPDIR_5"

# --- Test 6: Broken symlink repair ---
echo "--- Test 6: Broken symlink repair ---"

TMPDIR_6="$(setup_repo_with_remote)"
install_script "$TMPDIR_6/local"
create_data_branch_setup "$TMPDIR_6/local"

pushd "$TMPDIR_6/local" >/dev/null
# Remove worktree but leave broken symlinks
git worktree remove .aitask-data --force 2>/dev/null

# Verify symlinks are broken
assert_symlink "aitasks/ is still a symlink" "aitasks"
broken="no"
[[ ! -e "aitasks" ]] && broken="yes"
assert_eq "aitasks/ symlink is broken" "yes" "$broken"

# Run init
output=$(bash aiscripts/aitask_init_data.sh 2>/dev/null)
assert_eq "Broken symlink repair output" "INITIALIZED" "$output"
assert_symlink "aitasks/ is a symlink after repair" "aitasks"
# Verify symlinks now work (target exists)
valid="no"
[[ -e "aitasks" ]] && valid="yes"
assert_eq "aitasks/ symlink is valid after repair" "yes" "$valid"
popd >/dev/null

rm -rf "$TMPDIR_6"

# --- Test 7: Idempotency ---
echo "--- Test 7: Idempotency (double run) ---"

TMPDIR_7="$(setup_repo_with_remote)"
install_script "$TMPDIR_7/local"
create_data_branch_setup "$TMPDIR_7/local"

pushd "$TMPDIR_7/local" >/dev/null
output1=$(bash aiscripts/aitask_init_data.sh 2>/dev/null)
output2=$(bash aiscripts/aitask_init_data.sh 2>/dev/null)
assert_eq "First run: ALREADY_INIT" "ALREADY_INIT" "$output1"
assert_eq "Second run: ALREADY_INIT" "ALREADY_INIT" "$output2"
popd >/dev/null

rm -rf "$TMPDIR_7"

# --- Test 8: Missing symlinks with existing worktree ---
echo "--- Test 8: Missing symlinks with existing worktree ---"

TMPDIR_8="$(setup_repo_with_remote)"
install_script "$TMPDIR_8/local"
create_data_branch_setup "$TMPDIR_8/local"

pushd "$TMPDIR_8/local" >/dev/null
# Delete only symlinks, keep worktree
rm -f aitasks aiplans

# Verify worktree still exists
assert_dir_exists "Worktree still exists" ".aitask-data"

# Run init
output=$(bash aiscripts/aitask_init_data.sh 2>/dev/null)
assert_eq "Missing symlinks output" "ALREADY_INIT" "$output"
assert_symlink "aitasks/ symlink recreated" "aitasks"
assert_symlink "aiplans/ symlink recreated" "aiplans"
popd >/dev/null

rm -rf "$TMPDIR_8"

# --- Test 9: Help flag ---
echo "--- Test 9: Help flag ---"

output=$(bash "$PROJECT_DIR/aiscripts/aitask_init_data.sh" --help 2>/dev/null)
assert_contains "Help output mentions INITIALIZED" "INITIALIZED" "$output"
assert_contains "Help output mentions LEGACY_MODE" "LEGACY_MODE" "$output"

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
