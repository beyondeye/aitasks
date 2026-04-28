#!/usr/bin/env bash
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
    # Trim leading/trailing whitespace (macOS wc -l pads with spaces)
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
    mkdir -p "$tmpdir/.aitask-scripts"
    mkdir -p "$tmpdir/aitasks/metadata"
    mkdir -p "$tmpdir/.claude/skills"
    echo "#!/bin/bash" > "$tmpdir/ait"
    echo "0.2.0" > "$tmpdir/.aitask-scripts/VERSION"
    echo "#!/bin/bash" > "$tmpdir/install.sh"
    # Create a minimal placeholder in aiscripts so git add works
    echo "# placeholder" > "$tmpdir/.aitask-scripts/placeholder.sh"
    echo "# placeholder" > "$tmpdir/aitasks/metadata/placeholder.txt"
    echo "# placeholder" > "$tmpdir/.claude/skills/placeholder.txt"
    echo "$tmpdir"
}

# Source the setup script to get access to ensure_git_repo, commit_framework_files (and helpers)
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
# Disable strict mode from sourced script — tests need to handle errors explicitly
set +euo pipefail

echo "=== ensure_git_repo + commit_framework_files Tests ==="
echo ""

# --- Test 1: Already-initialized repo with files committed ---
echo "--- Test 1: Already-initialized repo (files committed) ---"

TMPDIR_1="$(setup_fake_project)"
(cd "$TMPDIR_1" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" && git add -A && git commit -m "init" --quiet)

# Override SCRIPT_DIR so ensure_git_repo/commit_framework_files use our temp project
SCRIPT_DIR="$TMPDIR_1/.aitask-scripts"
output=$(ensure_git_repo 2>&1 </dev/null)

assert_contains "Already initialized prints success" "already initialized" "$output"

# Verify no extra commits were created (files already committed)
commit_count=$(git -C "$TMPDIR_1" log --oneline 2>/dev/null | wc -l || echo 0)
assert_eq "No new commits when files already committed" "1" "$commit_count"

# commit_framework_files should also detect they're already committed
output2=$(commit_framework_files 2>&1 </dev/null)
assert_contains "commit_framework_files says already committed" "already committed" "$output2"

rm -rf "$TMPDIR_1"

# --- Test 1b: Already-initialized repo with untracked framework files ---
echo "--- Test 1b: Existing repo with untracked framework files ---"

TMPDIR_1b="$(setup_fake_project)"
(cd "$TMPDIR_1b" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" && echo "init" > "$TMPDIR_1b/readme.txt" && git add readme.txt && git commit -m "init" --quiet)

SCRIPT_DIR="$TMPDIR_1b/.aitask-scripts"
# ensure_git_repo should just report "already initialized" (no commit)
output=$(ensure_git_repo 2>&1 </dev/null)
assert_contains "Detects existing repo" "already initialized" "$output"

# commit_framework_files should detect and commit untracked files
output2=$(commit_framework_files 2>&1 </dev/null)
assert_contains "Detects untracked framework files" "READY TO COMMIT" "$output2"

# Non-interactive mode auto-accepts, so files should be committed
commit_count=$(git -C "$TMPDIR_1b" log --oneline 2>/dev/null | wc -l)
assert_eq "Framework files auto-committed (non-interactive)" "2" "$commit_count"

commit_msg=$(git -C "$TMPDIR_1b" log --format='%s' -1 2>/dev/null)
assert_eq "Commit message correct" "ait: Add aitask framework" "$commit_msg"

rm -rf "$TMPDIR_1b"

# --- Test 2: Accept git init + commit ---
echo "--- Test 2: Accept init + commit ---"

TMPDIR_2="$(setup_fake_project)"
SCRIPT_DIR="$TMPDIR_2/.aitask-scripts"

output=$(printf 'y\n' | ensure_git_repo 2>&1)
assert_dir_exists "Git dir created" "$TMPDIR_2/.git"
assert_contains "Output mentions initialized" "initialized" "$output"

# Need git config for commit
(cd "$TMPDIR_2" && git config user.email "t@t.com" && git config user.name "T")

output2=$(printf 'y\n' | commit_framework_files 2>&1)

commit_count=$(git -C "$TMPDIR_2" log --oneline 2>/dev/null | wc -l)
assert_eq "Exactly 1 commit" "1" "$commit_count"

commit_msg=$(git -C "$TMPDIR_2" log --format='%s' -1 2>/dev/null)
assert_eq "Commit message correct" "ait: Add aitask framework" "$commit_msg"

# Verify committed files include key directories
committed_files=$(git -C "$TMPDIR_2" show --name-only --format='' HEAD 2>/dev/null)
assert_contains ".aitask-scripts/ committed" ".aitask-scripts/" "$committed_files"
assert_contains "aitasks/metadata/ committed" "aitasks/metadata/" "$committed_files"

rm -rf "$TMPDIR_2"

# --- Test 3: Non-interactive auto-init + auto-commit ---
# Note: With -t 0 checks, piped input is ignored and non-interactive defaults apply.
# Interactive refusal scenarios (refuse commit, refuse init) require a real terminal.
echo "--- Test 3: Non-interactive auto-init + auto-commit ---"

TMPDIR_3="$(setup_fake_project)"
SCRIPT_DIR="$TMPDIR_3/.aitask-scripts"

output=$(ensure_git_repo 2>&1 </dev/null)
assert_dir_exists "Git dir created" "$TMPDIR_3/.git"
assert_contains "Output mentions auto-accepting" "auto-accepting" "$output"

# Need git config for commit
(cd "$TMPDIR_3" && git config user.email "t@t.com" && git config user.name "T")

output2=$(commit_framework_files 2>&1 </dev/null)

commit_count=$(git -C "$TMPDIR_3" log --oneline 2>/dev/null | wc -l || echo 0)
assert_eq "1 commit (non-interactive auto-accept)" "1" "$commit_count"

rm -rf "$TMPDIR_3"

# --- Test 4: Removed (was interactive-only, now covered by Test 3) ---
echo "--- Test 4: (skipped — merged into Test 3 non-interactive) ---"

# --- Test 5: Non-interactive auto-inits git ---
# Note: With -t 0 checks, non-interactive mode auto-accepts git init.
# Refusing git init requires a real terminal.
echo "--- Test 5: Non-interactive auto-inits git ---"

TMPDIR_5="$(setup_fake_project)"
SCRIPT_DIR="$TMPDIR_5/.aitask-scripts"

output=$(ensure_git_repo 2>&1 </dev/null)

assert_dir_exists ".git dir created (non-interactive auto-accept)" "$TMPDIR_5/.git"
assert_contains "Output mentions auto-accepting" "auto-accepting" "$output"

rm -rf "$TMPDIR_5"

# --- Test 6: Syntax check ---
echo "--- Test 6: Syntax check ---"

TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: bash -n aitask_setup.sh (syntax error)"
fi

# --- Test 7: setup_draft_directory creates dir and gitignore ---
echo "--- Test 7: setup_draft_directory ---"

TMPDIR_7="$(setup_fake_project)"
(cd "$TMPDIR_7" && git init --quiet && git config user.email "t@t.com" && git config user.name "T")
SCRIPT_DIR="$TMPDIR_7/.aitask-scripts"

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
SCRIPT_DIR="$TMPDIR_8/.aitask-scripts"

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
    mkdir -p .aitask-scripts/lib aitasks
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/aitask_claim_id.sh .aitask-scripts/aitask_setup.sh
    echo "---" > aitasks/t1_test.md
    git add -A && git commit -m "init" --quiet && git push --quiet 2>/dev/null
)

# Source setup from the temp project to get functions
source "$TMPDIR_9/local/.aitask-scripts/aitask_setup.sh" --source-only 2>/dev/null || true
SCRIPT_DIR="$TMPDIR_9/local/.aitask-scripts"

# Run setup_id_counter (auto-accept)
(cd "$TMPDIR_9/local" && printf 'y\n' | setup_id_counter >/dev/null 2>&1)

# Check branch exists on remote
branch_exists=$(git -C "$TMPDIR_9/local" ls-remote --heads origin aitask-ids 2>/dev/null | grep -c "aitask-ids")
assert_eq "ID counter branch created" "1" "$branch_exists"

rm -rf "$TMPDIR_9"

# Re-source the project's setup script to restore SCRIPT_DIR for remaining tests
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
set +euo pipefail
SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"

# --- Test 10: commit_framework_files includes late-stage files ---
echo "--- Test 10: commit_framework_files includes late-stage files ---"

TMPDIR_10="$(setup_fake_project)"
(cd "$TMPDIR_10" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" \
    && echo "init" > "$TMPDIR_10/readme.txt" && git add readme.txt && git commit -m "init" --quiet)

# Simulate late-stage files (review guides, .gitignore)
mkdir -p "$TMPDIR_10/aireviewguides"
echo "# review guide" > "$TMPDIR_10/aireviewguides/test_mode.md"
echo "aitasks/new/" > "$TMPDIR_10/.gitignore"

SCRIPT_DIR="$TMPDIR_10/.aitask-scripts"
commit_framework_files </dev/null >/dev/null 2>&1

# Verify review guides are committed
committed_files=$(git -C "$TMPDIR_10" show --name-only --format='' HEAD 2>/dev/null)
assert_contains "Review guides committed" "aireviewguides/test_mode.md" "$committed_files"
assert_contains ".gitignore committed" ".gitignore" "$committed_files"

commit_msg=$(git -C "$TMPDIR_10" log --format='%s' -1 2>/dev/null)
assert_eq "Commit message for late-stage files" "ait: Add aitask framework" "$commit_msg"

rm -rf "$TMPDIR_10"

# --- Test 11: commit_framework_files is idempotent ---
echo "--- Test 11: commit_framework_files is idempotent ---"

TMPDIR_11="$(setup_fake_project)"
(cd "$TMPDIR_11" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" && git add -A && git commit -m "init" --quiet)

SCRIPT_DIR="$TMPDIR_11/.aitask-scripts"
commit_count_before=$(git -C "$TMPDIR_11" log --oneline 2>/dev/null | wc -l)
output=$(commit_framework_files 2>&1 </dev/null)
commit_count_after=$(git -C "$TMPDIR_11" log --oneline 2>/dev/null | wc -l)

assert_eq "No new commit on idempotent run" "$commit_count_before" "$commit_count_after"
assert_contains "Says already committed" "already committed" "$output"

rm -rf "$TMPDIR_11"

# --- Test 12: commit_framework_files handles missing install.sh gracefully ---
echo "--- Test 12: Handles missing install.sh gracefully ---"

TMPDIR_12="$(setup_fake_project)"
# Remove install.sh before init
rm -f "$TMPDIR_12/install.sh"
(cd "$TMPDIR_12" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" \
    && echo "init" > "$TMPDIR_12/readme.txt" && git add readme.txt && git commit -m "init" --quiet)

SCRIPT_DIR="$TMPDIR_12/.aitask-scripts"
output=$(commit_framework_files 2>&1 </dev/null)

# Other framework files should still be committed
commit_count=$(git -C "$TMPDIR_12" log --oneline 2>/dev/null | wc -l)
assert_eq "Framework files committed without install.sh" "2" "$commit_count"

committed_files=$(git -C "$TMPDIR_12" show --name-only --format='' HEAD 2>/dev/null)
assert_contains ".aitask-scripts/ committed without install.sh" ".aitask-scripts/" "$committed_files"

rm -rf "$TMPDIR_12"

# --- Test 13: ensure_git_repo only initializes, does NOT commit ---
echo "--- Test 13: ensure_git_repo does NOT commit ---"

TMPDIR_13="$(setup_fake_project)"
SCRIPT_DIR="$TMPDIR_13/.aitask-scripts"

ensure_git_repo </dev/null >/dev/null 2>&1
assert_dir_exists ".git created" "$TMPDIR_13/.git"

# Verify NO commits exist (ensure_git_repo does not commit)
commit_count=$(git -C "$TMPDIR_13" log --oneline 2>/dev/null | wc -l || echo 0)
assert_eq "No commits from ensure_git_repo" "0" "$commit_count"

# Verify framework files are still untracked
untracked=$(cd "$TMPDIR_13" && git ls-files --others --exclude-standard .aitask-scripts/ ait 2>/dev/null)
TOTAL=$((TOTAL + 1))
if [[ -n "$untracked" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Framework files should still be untracked after ensure_git_repo"
fi

rm -rf "$TMPDIR_13"

# Re-source to restore SCRIPT_DIR
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
set +euo pipefail
SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"

# --- Test 14: commit_framework_files skips pycache and includes codex paths ---
echo "--- Test 14: Skips pycache and includes Codex files ---"

TMPDIR_14="$(setup_fake_project)"
(cd "$TMPDIR_14" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" \
    && echo "init" > "$TMPDIR_14/readme.txt" && git add readme.txt && git commit -m "init" --quiet)

# Create codex-related framework files and python cache artifacts.
mkdir -p "$TMPDIR_14/.agents/skills/aitask-pick"
echo "# wrapper" > "$TMPDIR_14/.agents/skills/aitask-pick/SKILL.md"
mkdir -p "$TMPDIR_14/.codex"
echo "sandbox_mode = \"workspace-write\"" > "$TMPDIR_14/.codex/config.toml"
mkdir -p "$TMPDIR_14/.aitask-scripts/__pycache__"
echo "bytecode" > "$TMPDIR_14/.aitask-scripts/__pycache__/test.cpython-314.pyc"

SCRIPT_DIR="$TMPDIR_14/.aitask-scripts"
output=$(commit_framework_files 2>&1 </dev/null)

assert_not_contains "Pycache not shown in pending framework list" "__pycache__" "$output"
assert_not_contains "PYC not shown in pending framework list" ".pyc" "$output"

committed_files=$(git -C "$TMPDIR_14" show --name-only --format='' HEAD 2>/dev/null)
assert_contains "Codex skills directory committed" ".agents/skills/aitask-pick/SKILL.md" "$committed_files"
assert_contains "Codex config committed" ".codex/config.toml" "$committed_files"
assert_not_contains "Pycache not committed" "__pycache__" "$committed_files"

rm -rf "$TMPDIR_14"

# --- Test 15: warn_missing_remote_for_branch non-interactive auto-acks ---
echo "--- Test 15: warn_missing_remote_for_branch auto-acks (non-interactive) ---"

# Capture output via a temp file so the helper runs in the parent shell
# (the module-level flag mutation would be lost in a subshell `output=$(...)`).
_AIT_SETUP_NO_REMOTE_ACKED=""
output_file_15="$(mktemp "${TMPDIR:-/tmp}/ait_test15_XXXXXX")"
warn_missing_remote_for_branch "aitask-locks" "Test purpose" >"$output_file_15" 2>&1 </dev/null
output=$(cat "$output_file_15")
rm -f "$output_file_15"

assert_contains "Warns about missing remote" "No git remote 'origin' configured" "$output"
assert_contains "Tells user the fix command" "git remote add origin" "$output"
assert_contains "Auto-accepts non-interactively" "auto-accepting acknowledgment" "$output"
assert_eq "Module-level flag is set after ack" "1" "$_AIT_SETUP_NO_REMOTE_ACKED"

# --- Test 16: warn_missing_remote_for_branch is idempotent within one run ---
echo "--- Test 16: warn_missing_remote_for_branch is idempotent ---"

# _AIT_SETUP_NO_REMOTE_ACKED is still 1 from Test 15 (parent shell preserved it)
output_file_16="$(mktemp "${TMPDIR:-/tmp}/ait_test16_XXXXXX")"
warn_missing_remote_for_branch "aitask-ids" "Other purpose" >"$output_file_16" 2>&1 </dev/null
output2=$(cat "$output_file_16")
rm -f "$output_file_16"

assert_contains "Second call mentions already acknowledged" "already acknowledged" "$output2"
assert_not_contains "Second call does not re-prompt" "git remote add origin" "$output2"

# --- Test 17: setup_lock_branch warns + skips cleanly with no remote ---
echo "--- Test 17: setup_lock_branch with no remote configured ---"

TMPDIR_17="$(setup_fake_project)"
(cd "$TMPDIR_17" && git init --quiet && git config user.email "t@t.com" && git config user.name "T")

# Reset the module-level flag so the warning fires fresh in this test
_AIT_SETUP_NO_REMOTE_ACKED=""

SCRIPT_DIR="$TMPDIR_17/.aitask-scripts"
output_file_17="$(mktemp "${TMPDIR:-/tmp}/ait_test17_XXXXXX")"
setup_lock_branch >"$output_file_17" 2>&1 </dev/null
rc=$?
output=$(cat "$output_file_17")
rm -f "$output_file_17"

assert_eq "setup_lock_branch returns 0 after acknowledgment" "0" "$rc"
assert_contains "Warning fires for missing remote" "No git remote 'origin' configured" "$output"

# Verify no aitask-locks ref was created locally
TOTAL=$((TOTAL + 1))
if git -C "$TMPDIR_17" rev-parse refs/heads/aitask-locks &>/dev/null; then
    FAIL=$((FAIL + 1))
    echo "FAIL: aitask-locks branch should NOT be created when no remote is configured"
else
    PASS=$((PASS + 1))
fi

rm -rf "$TMPDIR_17"

# Re-source to restore SCRIPT_DIR for any later additions
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
set +euo pipefail
SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"

# --- Test 18: setup_python_cache_gitignore commits the change (t687) ---
echo "--- Test 18: setup_python_cache_gitignore commits the change ---"

TMPDIR_18="$(setup_fake_project)"
(
    cd "$TMPDIR_18"
    git init --quiet
    git config user.email "t@t.com"
    git config user.name "T"
    # Pre-existing baseline .gitignore (committed) — simulates a clone of an
    # aitasks-using repo where the python_cache rule was never installed.
    echo "aitasks/new/" > .gitignore
    git add -A && git commit --quiet -m "init"
)
SCRIPT_DIR="$TMPDIR_18/.aitask-scripts"

setup_python_cache_gitignore </dev/null >/dev/null 2>&1

# Rule was added
TOTAL=$((TOTAL + 1))
if [[ -f "$TMPDIR_18/.gitignore" ]] && grep -qxF "__pycache__/" "$TMPDIR_18/.gitignore"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: .gitignore should contain '__pycache__/'"
fi

# Working tree is clean (the bug — t687)
porcelain="$(git -C "$TMPDIR_18" status --porcelain)"
assert_eq "git status is clean after setup_python_cache_gitignore" "" "$porcelain"

# Commit message matches the new pattern
last_msg="$(git -C "$TMPDIR_18" log -1 --format=%s)"
assert_contains "Last commit message announces the python cache rule" "Add __pycache__/ to .gitignore" "$last_msg"

rm -rf "$TMPDIR_18"

# --- Test 19: setup_python_cache_gitignore is idempotent (t687) ---
echo "--- Test 19: setup_python_cache_gitignore idempotent ---"

TMPDIR_19="$(setup_fake_project)"
(
    cd "$TMPDIR_19"
    git init --quiet
    git config user.email "t@t.com"
    git config user.name "T"
    echo "aitasks/new/" > .gitignore
    git add -A && git commit --quiet -m "init"
)
SCRIPT_DIR="$TMPDIR_19/.aitask-scripts"

setup_python_cache_gitignore </dev/null >/dev/null 2>&1
commits_after_first="$(git -C "$TMPDIR_19" rev-list --count HEAD)"

setup_python_cache_gitignore </dev/null >/dev/null 2>&1
commits_after_second="$(git -C "$TMPDIR_19" rev-list --count HEAD)"

# Should only have one '__pycache__/' entry
entry_count=$(grep -cxF "__pycache__/" "$TMPDIR_19/.gitignore" 2>/dev/null || echo "0")
assert_eq "Python cache entry not duplicated" "1" "$entry_count"

# Second call must NOT create a new commit
assert_eq "No second commit on idempotent re-run" "$commits_after_first" "$commits_after_second"

rm -rf "$TMPDIR_19"

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
