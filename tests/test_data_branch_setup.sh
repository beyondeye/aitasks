#!/usr/bin/env bash
# test_data_branch_setup.sh - Automated tests for setup_data_branch and update_claudemd_git_section
# Run: bash tests/test_data_branch_setup.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

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

assert_dir_exists() {
    local desc="$1" dir="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -d "$dir" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (directory '$dir' does not exist)"
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

# Create a repo with remote for testing
setup_repo_with_remote() {
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
        # Need at least one commit for the repo to be usable
        echo "# Test Project" > README.md
        git add README.md
        git commit -m "init" --quiet
        git push --quiet 2>/dev/null
    )
    echo "$tmpdir"
}

# Create a local-only repo (no remote)
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

# Source the setup script to get access to functions
source "$PROJECT_DIR/aiscripts/aitask_setup.sh" --source-only
set +euo pipefail

echo "=== setup_data_branch + update_claudemd_git_section Tests ==="
echo ""

# --- Test 1: Fresh setup with remote ---
echo "--- Test 1: Fresh setup with remote ---"

TMPDIR_1="$(setup_repo_with_remote)"
SCRIPT_DIR="$TMPDIR_1/local/aiscripts"
mkdir -p "$SCRIPT_DIR"

(cd "$TMPDIR_1/local" && setup_data_branch </dev/null >/dev/null 2>&1)

# Check branch exists on remote
branch_on_remote=$(git -C "$TMPDIR_1/local" ls-remote --heads origin aitask-data 2>/dev/null | grep -c "aitask-data")
assert_eq "aitask-data branch on remote" "1" "$branch_on_remote"

# Check worktree exists
assert_dir_exists "Worktree directory exists" "$TMPDIR_1/local/.aitask-data"
TOTAL=$((TOTAL + 1))
if [[ -f "$TMPDIR_1/local/.aitask-data/.git" || -d "$TMPDIR_1/local/.aitask-data/.git" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Worktree .git marker not found"
fi

# Check symlinks
assert_symlink "aitasks is symlink" "$TMPDIR_1/local/aitasks"
assert_symlink "aiplans is symlink" "$TMPDIR_1/local/aiplans"

# Check .gitignore
assert_file_contains ".gitignore has aitasks/" "$TMPDIR_1/local/.gitignore" "aitasks/"
assert_file_contains ".gitignore has aiplans/" "$TMPDIR_1/local/.gitignore" "aiplans/"
assert_file_contains ".gitignore has .aitask-data/" "$TMPDIR_1/local/.gitignore" ".aitask-data/"

# Check skeleton directories
assert_dir_exists "aitasks/metadata skeleton" "$TMPDIR_1/local/.aitask-data/aitasks/metadata"
assert_dir_exists "aitasks/archived skeleton" "$TMPDIR_1/local/.aitask-data/aitasks/archived"
assert_dir_exists "aiplans/archived skeleton" "$TMPDIR_1/local/.aitask-data/aiplans/archived"

# Check data branch .gitignore has aitasks/new/
assert_file_contains "Data .gitignore has aitasks/new/" "$TMPDIR_1/local/.aitask-data/.gitignore" "aitasks/new/"

# Check CLAUDE.md was created
assert_file_contains "CLAUDE.md has git operations section" "$TMPDIR_1/local/CLAUDE.md" "## Git Operations on Task/Plan Files"
assert_file_contains "CLAUDE.md mentions ait git" "$TMPDIR_1/local/CLAUDE.md" "./ait git"

rm -rf "$TMPDIR_1"

# --- Test 2: Migration from legacy mode ---
echo "--- Test 2: Migration from legacy mode ---"

TMPDIR_2="$(setup_repo_with_remote)"
SCRIPT_DIR="$TMPDIR_2/local/aiscripts"
mkdir -p "$SCRIPT_DIR"

# Create existing task/plan data on main
(
    cd "$TMPDIR_2/local"
    mkdir -p aitasks/metadata aitasks/archived aiplans/archived aitasks/new
    echo "---" > aitasks/t1_test.md
    echo "priority: high" >> aitasks/t1_test.md
    echo "---" >> aitasks/t1_test.md
    echo "Test task content" >> aitasks/t1_test.md
    echo "---" > aiplans/p1_test.md
    echo "Test plan" >> aiplans/p1_test.md
    echo "label1" > aitasks/metadata/labels.txt
    echo "Draft content" > aitasks/new/draft.md
    git add aitasks/ aiplans/
    git commit -m "ait: Add initial tasks" --quiet
    git push --quiet 2>/dev/null
)

(cd "$TMPDIR_2/local" && setup_data_branch </dev/null >/dev/null 2>&1)

# Check task accessible via symlink
assert_symlink "aitasks is symlink after migration" "$TMPDIR_2/local/aitasks"
assert_symlink "aiplans is symlink after migration" "$TMPDIR_2/local/aiplans"

# Check data accessible through symlinks
TOTAL=$((TOTAL + 1))
if [[ -f "$TMPDIR_2/local/aitasks/t1_test.md" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Task file not accessible via symlink"
fi

task_content=$(cat "$TMPDIR_2/local/aitasks/t1_test.md" 2>/dev/null)
assert_contains "Task content preserved" "Test task content" "$task_content"

TOTAL=$((TOTAL + 1))
if [[ -f "$TMPDIR_2/local/aiplans/p1_test.md" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Plan file not accessible via symlink"
fi

# Check draft preserved
TOTAL=$((TOTAL + 1))
if [[ -f "$TMPDIR_2/local/aitasks/new/draft.md" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Draft file not preserved after migration"
fi

# Check metadata preserved
assert_file_exists "Labels.txt preserved" "$TMPDIR_2/local/aitasks/metadata/labels.txt"

# Check data branch has the file
data_branch_has_file=$(git -C "$TMPDIR_2/local/.aitask-data" show HEAD:aitasks/t1_test.md 2>/dev/null | grep -c "Test task content")
assert_eq "Data branch has task file" "1" "$data_branch_has_file"

# Check main no longer tracks aitasks/
main_tracks_aitasks=$(git -C "$TMPDIR_2/local" ls-tree HEAD -- aitasks/ 2>/dev/null | wc -l | tr -d ' ')
assert_eq "Main no longer tracks aitasks/" "0" "$main_tracks_aitasks"

rm -rf "$TMPDIR_2"

# --- Test 3: Idempotent — second run skips ---
echo "--- Test 3: Idempotent — second run skips ---"

TMPDIR_3="$(setup_repo_with_remote)"
SCRIPT_DIR="$TMPDIR_3/local/aiscripts"
mkdir -p "$SCRIPT_DIR"

(cd "$TMPDIR_3/local" && setup_data_branch </dev/null >/dev/null 2>&1)

# Count commits before second run
commits_before=$(git -C "$TMPDIR_3/local" log --oneline 2>/dev/null | wc -l | tr -d ' ')
data_commits_before=$(git -C "$TMPDIR_3/local/.aitask-data" log --oneline 2>/dev/null | wc -l | tr -d ' ')

# Second run
output=$(cd "$TMPDIR_3/local" && setup_data_branch </dev/null 2>&1)

commits_after=$(git -C "$TMPDIR_3/local" log --oneline 2>/dev/null | wc -l | tr -d ' ')
data_commits_after=$(git -C "$TMPDIR_3/local/.aitask-data" log --oneline 2>/dev/null | wc -l | tr -d ' ')

assert_contains "Second run says already configured" "already configured" "$output"
assert_eq "No extra commits on main" "$commits_before" "$commits_after"
assert_eq "No extra commits on data branch" "$data_commits_before" "$data_commits_after"

rm -rf "$TMPDIR_3"

# --- Test 4: Clone on new PC (branch exists, no worktree) ---
echo "--- Test 4: Clone on new PC ---"

TMPDIR_4="$(setup_repo_with_remote)"
SCRIPT_DIR="$TMPDIR_4/local/aiscripts"
mkdir -p "$SCRIPT_DIR"

# First: set up data branch on "PC 1"
(cd "$TMPDIR_4/local" && setup_data_branch </dev/null >/dev/null 2>&1)

# Create some task data
(
    cd "$TMPDIR_4/local/.aitask-data"
    mkdir -p aitasks
    echo "---" > aitasks/t5_remote_task.md
    echo "Remote task" >> aitasks/t5_remote_task.md
    git add . && git commit -m "ait: Add remote task" --quiet && git push --quiet 2>/dev/null
)

# Simulate "PC 2": fresh clone, no worktree
git clone --quiet "$TMPDIR_4/remote.git" "$TMPDIR_4/pc2" 2>/dev/null
(cd "$TMPDIR_4/pc2" && git config user.email "test@test.com" && git config user.name "Test")

SCRIPT_DIR="$TMPDIR_4/pc2/aiscripts"
mkdir -p "$SCRIPT_DIR"

(cd "$TMPDIR_4/pc2" && setup_data_branch </dev/null >/dev/null 2>&1)

# Check worktree created
assert_dir_exists "PC2 worktree created" "$TMPDIR_4/pc2/.aitask-data"
assert_symlink "PC2 aitasks symlink" "$TMPDIR_4/pc2/aitasks"
assert_symlink "PC2 aiplans symlink" "$TMPDIR_4/pc2/aiplans"

# Check data is accessible (the task we added on PC1)
TOTAL=$((TOTAL + 1))
if [[ -f "$TMPDIR_4/pc2/aitasks/t5_remote_task.md" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Remote task not accessible on PC2 via symlink"
fi

rm -rf "$TMPDIR_4"

# --- Test 5: No remote (local-only repo) ---
echo "--- Test 5: No remote (local-only) ---"

TMPDIR_5="$(setup_local_repo)"
SCRIPT_DIR="$TMPDIR_5/aiscripts"
mkdir -p "$SCRIPT_DIR"

(cd "$TMPDIR_5" && setup_data_branch </dev/null >/dev/null 2>&1)

# Check local branch exists
TOTAL=$((TOTAL + 1))
if git -C "$TMPDIR_5" show-ref --verify refs/heads/aitask-data &>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: aitask-data branch not created locally"
fi

assert_dir_exists "Local worktree created" "$TMPDIR_5/.aitask-data"
assert_symlink "Local aitasks symlink" "$TMPDIR_5/aitasks"
assert_symlink "Local aiplans symlink" "$TMPDIR_5/aiplans"

# Verify symlinks work (can list directories)
TOTAL=$((TOTAL + 1))
if [[ -d "$TMPDIR_5/aitasks" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: aitasks symlink not functional"
fi

rm -rf "$TMPDIR_5"

# --- Test 6: CLAUDE.md creates file when missing ---
echo "--- Test 6: CLAUDE.md creates when missing ---"

TMPDIR_6="$(mktemp -d)"

update_claudemd_git_section "$TMPDIR_6"

assert_file_exists "CLAUDE.md created" "$TMPDIR_6/CLAUDE.md"
assert_file_contains "Has section header" "$TMPDIR_6/CLAUDE.md" "## Git Operations on Task/Plan Files"
assert_file_contains "Has ait git reference" "$TMPDIR_6/CLAUDE.md" "./ait git"

rm -rf "$TMPDIR_6"

# --- Test 7: CLAUDE.md appends to existing ---
echo "--- Test 7: CLAUDE.md appends to existing ---"

TMPDIR_7="$(mktemp -d)"
echo "# My Project" > "$TMPDIR_7/CLAUDE.md"
echo "" >> "$TMPDIR_7/CLAUDE.md"
echo "Some existing content." >> "$TMPDIR_7/CLAUDE.md"

update_claudemd_git_section "$TMPDIR_7" 2>/dev/null

assert_file_contains "Original content preserved" "$TMPDIR_7/CLAUDE.md" "# My Project"
assert_file_contains "Original detail preserved" "$TMPDIR_7/CLAUDE.md" "Some existing content."
assert_file_contains "Section appended" "$TMPDIR_7/CLAUDE.md" "## Git Operations on Task/Plan Files"

rm -rf "$TMPDIR_7"

# --- Test 8: CLAUDE.md idempotent ---
echo "--- Test 8: CLAUDE.md idempotent ---"

TMPDIR_8="$(mktemp -d)"
echo "# Project" > "$TMPDIR_8/CLAUDE.md"

update_claudemd_git_section "$TMPDIR_8" 2>/dev/null
update_claudemd_git_section "$TMPDIR_8" 2>/dev/null

section_count=$(grep -c "## Git Operations on Task/Plan Files" "$TMPDIR_8/CLAUDE.md" 2>/dev/null || echo "0")
assert_eq "Section appears exactly once" "1" "$section_count"

rm -rf "$TMPDIR_8"

# --- Test 9: Syntax check + shellcheck ---
echo "--- Test 9: Syntax check ---"

TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/aiscripts/aitask_setup.sh" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: bash -n aitask_setup.sh (syntax error)"
fi

# Shellcheck (if available) — only check for actual errors, not info/warning/style
if command -v shellcheck &>/dev/null; then
    TOTAL=$((TOTAL + 1))
    sc_errors=$(shellcheck --severity=error "$PROJECT_DIR/aiscripts/aitask_setup.sh" 2>&1 | wc -l | tr -d ' ')
    if [[ "$sc_errors" -eq 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: shellcheck found errors in aitask_setup.sh"
        shellcheck --severity=error "$PROJECT_DIR/aiscripts/aitask_setup.sh" 2>&1 | head -20
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
