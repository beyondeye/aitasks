#!/usr/bin/env bash
# test_task_push.sh - Automated tests for task_push/task_sync retry-rebase logic
# Run: bash tests/test_task_push.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

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

assert_success() {
    local desc="$1" exit_code="$2"
    TOTAL=$((TOTAL + 1))
    if [[ "$exit_code" -eq 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected exit 0, got $exit_code)"
    fi
}

cleanup() {
    for d in "${CLEANUP_DIRS[@]}"; do
        rm -rf "$d" 2>/dev/null
    done
}
trap cleanup EXIT

# --- Git setup helpers ---

# Create a bare "remote" repo and a "local" clone.
# Sets: TEST_REMOTE, TEST_LOCAL, TEST_TMPDIR
setup_remote_and_clone() {
    TEST_TMPDIR="$(mktemp -d "${TMPDIR:-/tmp}/ait_push_test_XXXXXX")"
    CLEANUP_DIRS+=("$TEST_TMPDIR")
    TEST_REMOTE="$TEST_TMPDIR/remote.git"
    TEST_LOCAL="$TEST_TMPDIR/local"

    git init --bare --quiet "$TEST_REMOTE"
    git clone --quiet "$TEST_REMOTE" "$TEST_LOCAL" 2>/dev/null
    git -C "$TEST_LOCAL" config user.email "test@test.com"
    git -C "$TEST_LOCAL" config user.name "Test"

    # Initial commit so we have a branch
    echo "init" > "$TEST_LOCAL/init.txt"
    git -C "$TEST_LOCAL" add init.txt
    git -C "$TEST_LOCAL" commit -m "init" --quiet
    git -C "$TEST_LOCAL" push --quiet 2>/dev/null
}

# Advance the remote via a second clone (simulates another user pushing)
advance_remote() {
    local filename="${1:-other_user_file.txt}"
    local other_tmpdir
    other_tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ait_push_other_XXXXXX")"
    local other_dir="$other_tmpdir/other"

    git clone --quiet "$TEST_REMOTE" "$other_dir" 2>/dev/null
    git -C "$other_dir" config user.email "other@test.com"
    git -C "$other_dir" config user.name "Other"
    echo "other user change" > "$other_dir/$filename"
    git -C "$other_dir" add "$filename"
    git -C "$other_dir" commit -m "other user commit" --quiet
    git -C "$other_dir" push --quiet 2>/dev/null

    rm -rf "$other_tmpdir"
}

# Setup branch mode: move TEST_LOCAL into a .aitask-data subdirectory
# Sets: TEST_MAIN_DIR (the parent directory to cd into)
setup_branch_mode() {
    TEST_MAIN_DIR="$TEST_TMPDIR/main_repo"
    mkdir -p "$TEST_MAIN_DIR"
    mv "$TEST_LOCAL" "$TEST_MAIN_DIR/.aitask-data"
    TEST_LOCAL="$TEST_MAIN_DIR/.aitask-data"
}

# Source task_utils.sh functions, resetting state
reload_task_utils() {
    unset _AIT_TASK_UTILS_LOADED
    _AIT_DATA_WORKTREE=""
    SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
    source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"
    set +euo pipefail
}

# --- Setup ---
reload_task_utils

echo "=== task_push / task_sync Retry-Rebase Tests ==="
echo ""

# --- Test 1: task_push clean push (legacy mode) ---
echo "--- Test 1: task_push clean push (legacy mode) ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

echo "local change" > local_file.txt
git add local_file.txt
git commit -m "local commit" --quiet

task_push
push_rc=$?

assert_success "task_push returns 0" "$push_rc"
remote_count=$(git -C "$TEST_REMOTE" rev-list --count HEAD)
assert_eq "Remote has 2 commits" "2" "$remote_count"

popd > /dev/null || exit 1

# --- Test 2: task_push clean push (branch mode) ---
echo "--- Test 2: task_push clean push (branch mode) ---"

setup_remote_and_clone
setup_branch_mode
pushd "$TEST_MAIN_DIR" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE=".aitask-data"

echo "branch mode change" > .aitask-data/branch_file.txt
git -C .aitask-data add branch_file.txt
git -C .aitask-data commit -m "branch mode commit" --quiet

task_push
push_rc=$?

assert_success "task_push returns 0 (branch mode)" "$push_rc"
remote_count=$(git -C "$TEST_REMOTE" rev-list --count HEAD)
assert_eq "Remote has 2 commits (branch mode)" "2" "$remote_count"

popd > /dev/null || exit 1

# --- Test 3: task_push auto-rebases on conflict (legacy mode) ---
echo "--- Test 3: task_push auto-rebases on conflict (legacy mode) ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

echo "local change" > my_file.txt
git add my_file.txt
git commit -m "local commit" --quiet

advance_remote "remote_file.txt"

task_push
push_rc=$?

assert_success "task_push returns 0 after rebase" "$push_rc"
remote_count=$(git -C "$TEST_REMOTE" rev-list --count HEAD)
assert_eq "Remote has 3 commits after rebase" "3" "$remote_count"

popd > /dev/null || exit 1

# --- Test 4: task_push auto-rebases on conflict (branch mode) ---
echo "--- Test 4: task_push auto-rebases on conflict (branch mode) ---"

setup_remote_and_clone
setup_branch_mode
pushd "$TEST_MAIN_DIR" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE=".aitask-data"

echo "local branch change" > .aitask-data/my_file.txt
git -C .aitask-data add my_file.txt
git -C .aitask-data commit -m "branch mode local commit" --quiet

advance_remote "remote_file.txt"

task_push
push_rc=$?

assert_success "task_push returns 0 after rebase (branch mode)" "$push_rc"
remote_count=$(git -C "$TEST_REMOTE" rev-list --count HEAD)
assert_eq "Remote has 3 commits after rebase (branch mode)" "3" "$remote_count"

popd > /dev/null || exit 1

# --- Test 5: task_push returns 0 even when all retries fail ---
echo "--- Test 5: task_push returns 0 when all retries fail ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

echo "will not push" > orphan.txt
git add orphan.txt
git commit -m "orphan commit" --quiet

git remote set-url origin /nonexistent/path/repo.git

task_push
push_rc=$?

assert_success "task_push returns 0 even on total failure" "$push_rc"

popd > /dev/null || exit 1

# --- Test 6: task_sync uses rebase (legacy mode) ---
echo "--- Test 6: task_sync uses rebase (legacy mode) ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE="."

echo "local unpushed" > local_sync.txt
git add local_sync.txt
git commit -m "local unpushed commit" --quiet

advance_remote "remote_sync.txt"

task_sync

local_count=$(git rev-list --count HEAD)
assert_eq "Local has 3 commits after sync rebase" "3" "$local_count"

top_msg=$(git log --format='%s' -1)
assert_eq "Local commit is on top after rebase" "local unpushed commit" "$top_msg"

popd > /dev/null || exit 1

# --- Test 7: task_sync uses rebase (branch mode) ---
echo "--- Test 7: task_sync uses rebase (branch mode) ---"

setup_remote_and_clone
setup_branch_mode
pushd "$TEST_MAIN_DIR" > /dev/null || exit 1
reload_task_utils
_AIT_DATA_WORKTREE=".aitask-data"

echo "local unpushed branch" > .aitask-data/local_sync.txt
git -C .aitask-data add local_sync.txt
git -C .aitask-data commit -m "local unpushed commit" --quiet

advance_remote "remote_sync.txt"

task_sync

local_count=$(git -C .aitask-data rev-list --count HEAD)
assert_eq "Local has 3 commits after sync rebase (branch mode)" "3" "$local_count"

top_msg=$(git -C .aitask-data log --format='%s' -1)
assert_eq "Local commit on top after rebase (branch mode)" "local unpushed commit" "$top_msg"

popd > /dev/null || exit 1

# --- Test 8: ait git push dispatcher intercept ---
echo "--- Test 8: ait git push dispatcher intercept ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1

# Create minimal ait dispatcher structure pointing to real scripts
mkdir -p .aitask-scripts/lib
cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/aitask_path.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/ait" ./ait
chmod +x ./ait

echo "local for ait push" > ait_push_file.txt
git add ait_push_file.txt .aitask-scripts/ ait
git commit -m "local with ait" --quiet

advance_remote "remote_ait.txt"

./ait git push
ait_rc=$?

assert_success "ait git push returns 0 after conflict" "$ait_rc"
remote_count=$(git -C "$TEST_REMOTE" rev-list --count HEAD)
assert_eq "Remote has 3 commits via ait git push" "3" "$remote_count"

popd > /dev/null || exit 1

# --- Test 9: ait git <other> passes through ---
echo "--- Test 9: ait git <other> passes through ---"

setup_remote_and_clone
pushd "$TEST_LOCAL" > /dev/null || exit 1

mkdir -p .aitask-scripts/lib
cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/aitask_path.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/ait" ./ait
chmod +x ./ait
git add .aitask-scripts/ ait
git commit -m "add ait scripts" --quiet
git push --quiet 2>/dev/null

status_output=$(./ait git status 2>&1)
status_rc=$?
assert_success "ait git status returns 0" "$status_rc"

log_output=$(./ait git log --oneline -1 2>&1)
log_rc=$?
assert_success "ait git log returns 0" "$log_rc"
assert_contains "ait git log shows commit" "add ait scripts" "$log_output"

popd > /dev/null || exit 1

# --- Summary ---
echo ""
echo "=== Results: $PASS passed, $FAIL failed, $TOTAL total ==="
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
