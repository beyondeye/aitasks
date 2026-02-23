#!/usr/bin/env bash
# test_data_branch_migration.sh - End-to-end migration tests: scripts work after migration to branch mode
# Run: bash tests/test_data_branch_migration.sh

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

assert_file_contains() {
    local desc="$1" file="$2" pattern="$3"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$file" ]] && grep -qF "$pattern" "$file"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (file '$file' does not contain '$pattern')"
    fi
}

# --- Setup: create a complete migrated project ---

setup_migrated_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    # Create bare remote
    git init --bare --quiet "$tmpdir/remote.git"

    # Create local clone
    git clone --quiet "$tmpdir/remote.git" "$tmpdir/local" 2>/dev/null
    (
        cd "$tmpdir/local"
        git config user.email "test@test.com"
        git config user.name "Test"

        # Create project structure with task data on main
        mkdir -p aitasks/metadata aitasks/archived aitasks/new
        mkdir -p aiplans/archived
        mkdir -p aiscripts/lib

        # Copy scripts from project
        cp "$PROJECT_DIR/ait" ait
        chmod +x ait
        cp "$PROJECT_DIR/aiscripts/aitask_create.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/aitask_ls.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/aitask_update.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/aitask_claim_id.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/aitask_setup.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh" aiscripts/lib/
        cp "$PROJECT_DIR/aiscripts/lib/task_utils.sh" aiscripts/lib/
        chmod +x aiscripts/aitask_create.sh aiscripts/aitask_ls.sh aiscripts/aitask_update.sh
        chmod +x aiscripts/aitask_claim_id.sh aiscripts/aitask_setup.sh

        # Create VERSION file (needed by ait dispatcher)
        echo "0.0.0-test" > aiscripts/VERSION

        # Create task types and labels
        printf 'bug\nchore\ndocumentation\nfeature\nperformance\nrefactor\nstyle\ntest\n' > aitasks/metadata/task_types.txt
        echo "backend" > aitasks/metadata/labels.txt

        # Create sample tasks
        cat > aitasks/t1_existing_task.md << 'TASK'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [backend]
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Existing task for migration test
TASK

        cat > aitasks/t2_second_task.md << 'TASK'
---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: []
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Second task for migration test
TASK

        # Create sample plan
        cat > aiplans/p1_existing_plan.md << 'PLAN'
---
Task: t1_existing_task.md
---

# Plan for t1

Plan content for migration test
PLAN

        # Add .gitignore for drafts
        echo "aitasks/new/" > .gitignore

        git add -A
        git commit -m "Initial setup with tasks" --quiet
        git push --quiet 2>/dev/null

        # Initialize aitask-ids counter
        ./aiscripts/aitask_claim_id.sh --init >/dev/null 2>&1
    )

    # Source setup script for setup_data_branch function
    # aitask_setup.sh sets SCRIPT_DIR from BASH_SOURCE — override after sourcing
    source "$PROJECT_DIR/aiscripts/aitask_setup.sh" --source-only
    set +euo pipefail

    # Run migration (SCRIPT_DIR must point to test repo's aiscripts for project_dir resolution)
    SCRIPT_DIR="$tmpdir/local/aiscripts"
    (cd "$tmpdir/local" && setup_data_branch </dev/null >/dev/null 2>&1)

    echo "$tmpdir"
}

# Get default branch name for the system
DEFAULT_BRANCH="$(git config --global init.defaultBranch 2>/dev/null || echo "master")"

echo "=== Data Branch Migration End-to-End Tests ==="
echo ""

TMPDIR="$(setup_migrated_project)"
LOCAL="$TMPDIR/local"

# --- Test 1: Files accessible via symlinks ---
echo "--- Test 1: Files accessible via symlinks ---"

assert_symlink "aitasks is symlink" "$LOCAL/aitasks"
assert_symlink "aiplans is symlink" "$LOCAL/aiplans"
assert_file_exists "Task t1 accessible via symlink" "$LOCAL/aitasks/t1_existing_task.md"
assert_file_exists "Task t2 accessible via symlink" "$LOCAL/aitasks/t2_second_task.md"
assert_file_exists "Plan p1 accessible via symlink" "$LOCAL/aiplans/p1_existing_plan.md"
assert_file_contains "Task t1 content preserved" "$LOCAL/aitasks/t1_existing_task.md" "Existing task for migration test"
assert_file_contains "Plan p1 content preserved" "$LOCAL/aiplans/p1_existing_plan.md" "Plan content for migration test"

# --- Test 2: ait git targets data branch ---
echo "--- Test 2: ait git targets data branch ---"

ait_branch=$(cd "$LOCAL" && ./ait git branch --show-current 2>/dev/null)
git_branch=$(cd "$LOCAL" && git branch --show-current 2>/dev/null)
assert_eq "ait git on aitask-data branch" "aitask-data" "$ait_branch"
assert_eq "git on default branch" "$DEFAULT_BRANCH" "$git_branch"

# --- Test 3: Modify task + ait git add/commit ---
echo "--- Test 3: Modify task + ait git commit ---"

echo "Modified by test" >> "$LOCAL/aitasks/t1_existing_task.md"

(
    cd "$LOCAL"
    ./ait git add aitasks/t1_existing_task.md
    ./ait git commit -m "test: Modify task t1" --quiet
)

data_log=$(git -C "$LOCAL/.aitask-data" log --oneline -1 2>/dev/null)
main_log=$(git -C "$LOCAL" log --oneline 2>/dev/null)

assert_contains "Commit on data branch" "test: Modify task t1" "$data_log"
assert_not_contains "Commit NOT on main" "test: Modify task t1" "$main_log"

# --- Test 4: aitask_ls.sh works after migration ---
echo "--- Test 4: aitask_ls.sh works ---"

ls_output=$(cd "$LOCAL" && ./aiscripts/aitask_ls.sh -s all 10 2>/dev/null)
assert_contains "ls shows t1_existing_task" "t1_existing_task" "$ls_output"
assert_contains "ls shows t2_second_task" "t2_second_task" "$ls_output"

# --- Test 5: aitask_create.sh --batch --commit in branch mode ---
echo "--- Test 5: aitask_create.sh --batch --commit ---"

(
    cd "$LOCAL"
    ./aiscripts/aitask_create.sh --batch --name "branch_mode_task" --desc "Created in branch mode" --commit --silent 2>/dev/null
)

# Find the newly created task file (ID is dynamic)
new_task=$(cd "$LOCAL" && ls aitasks/t*_branch_mode_task.md 2>/dev/null | head -1)

TOTAL=$((TOTAL + 1))
if [[ -n "$new_task" && -f "$LOCAL/$new_task" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: New task file not found after create --batch --commit"
fi

# Verify commit is on data branch, not main
data_log_create=$(git -C "$LOCAL/.aitask-data" log --oneline -1 2>/dev/null)
main_log_create=$(git -C "$LOCAL" log --oneline 2>/dev/null)

assert_contains "Create commit on data branch" "branch mode task" "$data_log_create"
assert_not_contains "Create commit NOT on main" "branch mode task" "$main_log_create"

# --- Test 6: aitask_update.sh --batch --commit in branch mode ---
echo "--- Test 6: aitask_update.sh --batch --commit ---"

(
    cd "$LOCAL"
    ./aiscripts/aitask_update.sh --batch 1 --status Implementing --commit 2>/dev/null
)

assert_file_contains "Task t1 status updated" "$LOCAL/aitasks/t1_existing_task.md" "status: Implementing"

data_log_update=$(git -C "$LOCAL/.aitask-data" log --oneline -1 2>/dev/null)
main_log_update=$(git -C "$LOCAL" log --oneline 2>/dev/null)

assert_contains "Update commit on data branch" "Update task t1" "$data_log_update"
assert_not_contains "Update commit NOT on main" "Update task t1" "$main_log_update"

# --- Test 7: Syntax check on both new test files ---
echo "--- Test 7: Syntax check ---"

TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/tests/test_task_git.sh" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: bash -n test_task_git.sh (syntax error)"
fi

TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/tests/test_data_branch_migration.sh" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: bash -n test_data_branch_migration.sh (syntax error)"
fi

# --- Cleanup ---
rm -rf "$TMPDIR"

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
