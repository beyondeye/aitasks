#!/bin/bash
# test_setup_git.sh - Automated tests for setup_git_repo function
# Run: bash tests/test_setup_git.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
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
        echo "FAIL: $desc (expected output containing '$expected')"
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

assert_dir_not_exists() {
    local desc="$1" dir="$2"
    TOTAL=$((TOTAL + 1))
    if [[ ! -d "$dir" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (directory '$dir' should not exist)"
    fi
}

# Create a minimal fake aitask project structure in a temp directory
setup_fake_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    mkdir -p "$tmpdir/aiscripts"
    mkdir -p "$tmpdir/aitasks/metadata"
    mkdir -p "$tmpdir/.claude/skills"
    echo "#!/bin/bash" > "$tmpdir/ait"
    echo "0.2.0" > "$tmpdir/aiscripts/VERSION"
    echo "#!/bin/bash" > "$tmpdir/install.sh"
    # Create a minimal placeholder in aiscripts so git add works
    echo "# placeholder" > "$tmpdir/aiscripts/placeholder.sh"
    echo "# placeholder" > "$tmpdir/aitasks/metadata/placeholder.txt"
    echo "# placeholder" > "$tmpdir/.claude/skills/placeholder.txt"
    echo "$tmpdir"
}

# Source the setup script to get access to setup_git_repo (and helpers)
source "$PROJECT_DIR/aiscripts/aitask_setup.sh" --source-only
# Disable strict mode from sourced script — tests need to handle errors explicitly
set +euo pipefail

echo "=== setup_git_repo Tests ==="
echo ""

# --- Test 1: Already-initialized repo with files committed ---
echo "--- Test 1: Already-initialized repo (files committed) ---"

TMPDIR_1="$(setup_fake_project)"
(cd "$TMPDIR_1" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" && git add -A && git commit -m "init" --quiet)

# Override SCRIPT_DIR so setup_git_repo uses our temp project
SCRIPT_DIR="$TMPDIR_1/aiscripts"
output=$(setup_git_repo 2>&1 </dev/null)

assert_contains "Already initialized prints success" "already initialized" "$output"

# Verify no extra commits were created (files already committed)
commit_count=$(git -C "$TMPDIR_1" log --oneline 2>/dev/null | wc -l || echo 0)
assert_eq "No new commits when files already committed" "1" "$commit_count"

rm -rf "$TMPDIR_1"

# --- Test 1b: Already-initialized repo with untracked framework files ---
echo "--- Test 1b: Existing repo with untracked framework files ---"

TMPDIR_1b="$(setup_fake_project)"
(cd "$TMPDIR_1b" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" && echo "init" > "$TMPDIR_1b/readme.txt" && git add readme.txt && git commit -m "init" --quiet)

SCRIPT_DIR="$TMPDIR_1b/aiscripts"
output=$(setup_git_repo 2>&1 </dev/null)

assert_contains "Detects untracked framework files" "not yet committed" "$output"

# Non-interactive mode auto-accepts, so files should be committed
commit_count=$(git -C "$TMPDIR_1b" log --oneline 2>/dev/null | wc -l)
assert_eq "Framework files auto-committed (non-interactive)" "2" "$commit_count"

commit_msg=$(git -C "$TMPDIR_1b" log --format='%s' -1 2>/dev/null)
assert_eq "Commit message correct" "Add aitask framework" "$commit_msg"

rm -rf "$TMPDIR_1b"

# --- Test 2: Accept git init + accept commit ---
echo "--- Test 2: Accept init + accept commit ---"

TMPDIR_2="$(setup_fake_project)"
SCRIPT_DIR="$TMPDIR_2/aiscripts"

output=$(printf 'y\ny\n' | setup_git_repo 2>&1)

assert_dir_exists "Git dir created" "$TMPDIR_2/.git"
assert_contains "Output mentions initialized" "initialized" "$output"

commit_count=$(git -C "$TMPDIR_2" log --oneline 2>/dev/null | wc -l)
assert_eq "Exactly 1 commit" "1" "$commit_count"

commit_msg=$(git -C "$TMPDIR_2" log --format='%s' -1 2>/dev/null)
assert_eq "Commit message correct" "Add aitask framework" "$commit_msg"

# Verify committed files include key directories
committed_files=$(git -C "$TMPDIR_2" show --name-only --format='' HEAD 2>/dev/null)
assert_contains "aiscripts/ committed" "aiscripts/" "$committed_files"
assert_contains "aitasks/metadata/ committed" "aitasks/metadata/" "$committed_files"

rm -rf "$TMPDIR_2"

# --- Test 3: Non-interactive auto-init + auto-commit ---
# Note: With -t 0 checks, piped input is ignored and non-interactive defaults apply.
# Interactive refusal scenarios (refuse commit, refuse init) require a real terminal.
echo "--- Test 3: Non-interactive auto-init + auto-commit ---"

TMPDIR_3="$(setup_fake_project)"
SCRIPT_DIR="$TMPDIR_3/aiscripts"

output=$(setup_git_repo 2>&1 </dev/null)

assert_dir_exists "Git dir created" "$TMPDIR_3/.git"

commit_count=$(git -C "$TMPDIR_3" log --oneline 2>/dev/null | wc -l || echo 0)
assert_eq "1 commit (non-interactive auto-accept)" "1" "$commit_count"

assert_contains "Output mentions auto-accepting" "auto-accepting" "$output"

rm -rf "$TMPDIR_3"

# --- Test 4: Removed (was interactive-only, now covered by Test 3) ---
echo "--- Test 4: (skipped — merged into Test 3 non-interactive) ---"

# --- Test 5: Non-interactive auto-inits git ---
# Note: With -t 0 checks, non-interactive mode auto-accepts git init.
# Refusing git init requires a real terminal.
echo "--- Test 5: Non-interactive auto-inits git ---"

TMPDIR_5="$(setup_fake_project)"
SCRIPT_DIR="$TMPDIR_5/aiscripts"

output=$(setup_git_repo 2>&1 </dev/null)

assert_dir_exists ".git dir created (non-interactive auto-accept)" "$TMPDIR_5/.git"
assert_contains "Output mentions auto-accepting" "auto-accepting" "$output"

rm -rf "$TMPDIR_5"

# --- Test 6: Syntax check ---
echo "--- Test 6: Syntax check ---"

TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/aiscripts/aitask_setup.sh" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: bash -n aitask_setup.sh (syntax error)"
fi

# --- Test 7: setup_draft_directory creates dir and gitignore ---
echo "--- Test 7: setup_draft_directory ---"

TMPDIR_7="$(setup_fake_project)"
(cd "$TMPDIR_7" && git init --quiet && git config user.email "t@t.com" && git config user.name "T")
SCRIPT_DIR="$TMPDIR_7/aiscripts"

# Run setup_draft_directory
setup_draft_directory </dev/null >/dev/null 2>&1

assert_dir_exists "Draft dir created" "$TMPDIR_7/aitasks/new"

# Check .gitignore has the entry
TOTAL=$((TOTAL + 1))
if [[ -f "$TMPDIR_7/.gitignore" ]] && grep -qxF "aitasks/new/" "$TMPDIR_7/.gitignore"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: .gitignore should contain 'aitasks/new/'"
fi

rm -rf "$TMPDIR_7"

# --- Test 8: setup_draft_directory is idempotent ---
echo "--- Test 8: setup_draft_directory idempotent ---"

TMPDIR_8="$(setup_fake_project)"
(cd "$TMPDIR_8" && git init --quiet && git config user.email "t@t.com" && git config user.name "T")
SCRIPT_DIR="$TMPDIR_8/aiscripts"

# Run twice
setup_draft_directory </dev/null >/dev/null 2>&1
setup_draft_directory </dev/null >/dev/null 2>&1

# Should only have one 'aitasks/new/' entry in .gitignore
entry_count=$(grep -cxF "aitasks/new/" "$TMPDIR_8/.gitignore" 2>/dev/null || echo "0")
assert_eq "Gitignore entry not duplicated" "1" "$entry_count"

rm -rf "$TMPDIR_8"

# --- Test 9: setup_id_counter creates branch on remote ---
echo "--- Test 9: setup_id_counter creates branch ---"

TMPDIR_9="$(mktemp -d)"
# Create bare remote
git init --bare --quiet "$TMPDIR_9/remote.git"
# Create local clone
git clone --quiet "$TMPDIR_9/remote.git" "$TMPDIR_9/local"
(
    cd "$TMPDIR_9/local"
    git config user.email "t@t.com"
    git config user.name "T"
    mkdir -p aiscripts/lib aitasks
    cp "$PROJECT_DIR/aiscripts/aitask_claim_id.sh" aiscripts/
    cp "$PROJECT_DIR/aiscripts/aitask_setup.sh" aiscripts/
    cp "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh" aiscripts/lib/
    chmod +x aiscripts/aitask_claim_id.sh aiscripts/aitask_setup.sh
    echo "---" > aitasks/t1_test.md
    git add -A && git commit -m "init" --quiet && git push --quiet 2>/dev/null
)

# Source setup from the temp project to get functions
source "$TMPDIR_9/local/aiscripts/aitask_setup.sh" --source-only 2>/dev/null || true
SCRIPT_DIR="$TMPDIR_9/local/aiscripts"

# Run setup_id_counter (auto-accept)
(cd "$TMPDIR_9/local" && printf 'y\n' | setup_id_counter >/dev/null 2>&1)

# Check branch exists on remote
branch_exists=$(git -C "$TMPDIR_9/local" ls-remote --heads origin aitask-ids 2>/dev/null | grep -c "aitask-ids")
assert_eq "ID counter branch created" "1" "$branch_exists"

rm -rf "$TMPDIR_9"

# Re-source the project's setup script to restore SCRIPT_DIR for remaining tests
SCRIPT_DIR="$PROJECT_DIR/aiscripts"

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
