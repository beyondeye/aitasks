#!/usr/bin/env bash
# test_setup_git.sh - Automated tests for setup_git_repo function
# Run: bash tests/test_setup_git.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

# Shared assertion helpers (see tests/lib/asserts.sh)
. "$PROJECT_DIR/tests/lib/asserts.sh"
# run_bounded, for the cases that could hang (see tests/lib/proc_fixtures.sh)
. "$PROJECT_DIR/tests/lib/proc_fixtures.sh"





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

assert_contains_ci "Already initialized prints success" "already initialized" "$output"

# Verify no extra commits were created (files already committed)
commit_count=$(git -C "$TMPDIR_1" log --oneline 2>/dev/null | wc -l || echo 0)
assert_eq_trim "No new commits when files already committed" "1" "$commit_count"

# commit_framework_files should also detect they're already committed
output2=$(commit_framework_files 2>&1 </dev/null)
assert_contains_ci "commit_framework_files says already committed" "already committed" "$output2"

rm -rf "$TMPDIR_1"

# --- Test 1b: Already-initialized repo with untracked framework files ---
echo "--- Test 1b: Existing repo with untracked framework files ---"

TMPDIR_1b="$(setup_fake_project)"
(cd "$TMPDIR_1b" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" && echo "init" > "$TMPDIR_1b/readme.txt" && git add readme.txt && git commit -m "init" --quiet)

SCRIPT_DIR="$TMPDIR_1b/.aitask-scripts"
# ensure_git_repo should just report "already initialized" (no commit)
output=$(ensure_git_repo 2>&1 </dev/null)
assert_contains_ci "Detects existing repo" "already initialized" "$output"

# commit_framework_files should detect and commit untracked files
output2=$(commit_framework_files 2>&1 </dev/null)
assert_contains_ci "Detects untracked framework files" "READY TO COMMIT" "$output2"

# Non-interactive mode auto-accepts, so files should be committed
commit_count=$(git -C "$TMPDIR_1b" log --oneline 2>/dev/null | wc -l)
assert_eq_trim "Framework files auto-committed (non-interactive)" "2" "$commit_count"

commit_msg=$(git -C "$TMPDIR_1b" log --format='%s' -1 2>/dev/null)
assert_eq_trim "Commit message correct" "ait: Add aitask framework" "$commit_msg"

rm -rf "$TMPDIR_1b"

# --- Test 2: Accept git init + commit ---
echo "--- Test 2: Accept init + commit ---"

TMPDIR_2="$(setup_fake_project)"
SCRIPT_DIR="$TMPDIR_2/.aitask-scripts"

output=$(printf 'y\n' | ensure_git_repo 2>&1)
assert_dir_exists "Git dir created" "$TMPDIR_2/.git"
assert_contains_ci "Output mentions initialized" "initialized" "$output"

# Need git config for commit
(cd "$TMPDIR_2" && git config user.email "t@t.com" && git config user.name "T")

output2=$(printf 'y\n' | commit_framework_files 2>&1)

commit_count=$(git -C "$TMPDIR_2" log --oneline 2>/dev/null | wc -l)
assert_eq_trim "Exactly 1 commit" "1" "$commit_count"

commit_msg=$(git -C "$TMPDIR_2" log --format='%s' -1 2>/dev/null)
assert_eq_trim "Commit message correct" "ait: Add aitask framework" "$commit_msg"

# Verify committed files include key directories
committed_files=$(git -C "$TMPDIR_2" show --name-only --format='' HEAD 2>/dev/null)
assert_contains_ci ".aitask-scripts/ committed" ".aitask-scripts/" "$committed_files"
assert_contains_ci "aitasks/metadata/ committed" "aitasks/metadata/" "$committed_files"

rm -rf "$TMPDIR_2"

# --- Test 3: Non-interactive auto-init + auto-commit ---
# Note: With -t 0 checks, piped input is ignored and non-interactive defaults apply.
# Interactive refusal scenarios (refuse commit, refuse init) require a real terminal.
echo "--- Test 3: Non-interactive auto-init + auto-commit ---"

TMPDIR_3="$(setup_fake_project)"
SCRIPT_DIR="$TMPDIR_3/.aitask-scripts"

output=$(ensure_git_repo 2>&1 </dev/null)
assert_dir_exists "Git dir created" "$TMPDIR_3/.git"
assert_contains_ci "Output mentions auto-accepting" "auto-accepting" "$output"

# Need git config for commit
(cd "$TMPDIR_3" && git config user.email "t@t.com" && git config user.name "T")

output2=$(commit_framework_files 2>&1 </dev/null)

commit_count=$(git -C "$TMPDIR_3" log --oneline 2>/dev/null | wc -l || echo 0)
assert_eq_trim "1 commit (non-interactive auto-accept)" "1" "$commit_count"

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
assert_contains_ci "Output mentions auto-accepting" "auto-accepting" "$output"

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
assert_eq_trim "Gitignore entry not duplicated" "1" "$entry_count"

rm -rf "$TMPDIR_8"

# --- Test 9: setup_id_counter creates branch on remote ---
echo "--- Test 9: setup_id_counter creates branch ---"

TMPDIR_9="$(mktemp -d)"
# Create bare remote
git init --bare --quiet "$TMPDIR_9/remote.git"
# Create local clone
git clone --quiet "$TMPDIR_9/remote.git" "$TMPDIR_9/local"
(
    cd "$TMPDIR_9/local" || exit 1
    git config user.email "t@t.com"
    git config user.name "T"
    mkdir -p aitasks
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" .aitask-scripts/
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
assert_eq_trim "ID counter branch created" "1" "$branch_exists"

rm -rf "$TMPDIR_9"

# --- Test 9b: setup_id_counter resyncs existing branch against archived drift ---
echo "--- Test 9b: setup_id_counter resyncs existing branch ---"

TMPDIR_9b="$(mktemp -d)"
git init --bare --quiet "$TMPDIR_9b/remote.git"
git clone --quiet "$TMPDIR_9b/remote.git" "$TMPDIR_9b/local"
(
    cd "$TMPDIR_9b/local" || exit 1
    git config user.email "t@t.com"
    git config user.name "T"
    mkdir -p aitasks/archived
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/aitask_claim_id.sh .aitask-scripts/aitask_setup.sh
    echo "---" > aitasks/t1_test.md
    git add -A && git commit -m "init" --quiet && git push --quiet 2>/dev/null
    ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1
    echo "---" > aitasks/archived/t50_archived_drift.md
    git add aitasks/archived/t50_archived_drift.md && git commit -m "archived drift" --quiet && git push --quiet 2>/dev/null
    git fetch origin aitask-ids --quiet 2>/dev/null
    parent=$(git rev-parse origin/aitask-ids)
    blob=$(echo "2" | git hash-object -w --stdin)
    tree=$(printf "100644 blob %s\tnext_id.txt\n" "$blob" | git mktree)
    commit=$(echo "test: drift counter" | git commit-tree "$tree" -p "$parent")
    git push --quiet origin "$commit:refs/heads/aitask-ids"
    git update-ref refs/remotes/origin/aitask-ids "$commit"
)

source "$TMPDIR_9b/local/.aitask-scripts/aitask_setup.sh" --source-only 2>/dev/null || true
set +euo pipefail
SCRIPT_DIR="$TMPDIR_9b/local/.aitask-scripts"

(cd "$TMPDIR_9b/local" && setup_id_counter >/dev/null 2>&1 </dev/null)

counter9b=$(git -C "$TMPDIR_9b/local" fetch origin aitask-ids --quiet 2>/dev/null \
    && git -C "$TMPDIR_9b/local" show origin/aitask-ids:next_id.txt 2>/dev/null \
    | tr -d '[:space:]')
assert_eq_trim "Setup resync repairs archived drift" "51" "$counter9b"

rm -rf "$TMPDIR_9b"

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
assert_contains_ci "Review guides committed" "aireviewguides/test_mode.md" "$committed_files"
assert_contains_ci ".gitignore committed" ".gitignore" "$committed_files"

commit_msg=$(git -C "$TMPDIR_10" log --format='%s' -1 2>/dev/null)
assert_eq_trim "Commit message for late-stage files" "ait: Add aitask framework" "$commit_msg"

rm -rf "$TMPDIR_10"

# --- Test 11: commit_framework_files is idempotent ---
echo "--- Test 11: commit_framework_files is idempotent ---"

TMPDIR_11="$(setup_fake_project)"
(cd "$TMPDIR_11" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" && git add -A && git commit -m "init" --quiet)

SCRIPT_DIR="$TMPDIR_11/.aitask-scripts"
commit_count_before=$(git -C "$TMPDIR_11" log --oneline 2>/dev/null | wc -l)
output=$(commit_framework_files 2>&1 </dev/null)
commit_count_after=$(git -C "$TMPDIR_11" log --oneline 2>/dev/null | wc -l)

assert_eq_trim "No new commit on idempotent run" "$commit_count_before" "$commit_count_after"
assert_contains_ci "Says already committed" "already committed" "$output"

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
assert_eq_trim "Framework files committed without install.sh" "2" "$commit_count"

committed_files=$(git -C "$TMPDIR_12" show --name-only --format='' HEAD 2>/dev/null)
assert_contains_ci ".aitask-scripts/ committed without install.sh" ".aitask-scripts/" "$committed_files"

rm -rf "$TMPDIR_12"

# --- Test 13: ensure_git_repo only initializes, does NOT commit ---
echo "--- Test 13: ensure_git_repo does NOT commit ---"

TMPDIR_13="$(setup_fake_project)"
SCRIPT_DIR="$TMPDIR_13/.aitask-scripts"

ensure_git_repo </dev/null >/dev/null 2>&1
assert_dir_exists ".git created" "$TMPDIR_13/.git"

# Verify NO commits exist (ensure_git_repo does not commit)
commit_count=$(git -C "$TMPDIR_13" log --oneline 2>/dev/null | wc -l || echo 0)
assert_eq_trim "No commits from ensure_git_repo" "0" "$commit_count"

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

assert_not_contains_ci "Pycache not shown in pending framework list" "__pycache__" "$output"
assert_not_contains_ci "PYC not shown in pending framework list" ".pyc" "$output"

committed_files=$(git -C "$TMPDIR_14" show --name-only --format='' HEAD 2>/dev/null)
assert_contains_ci "Codex skills directory committed" ".agents/skills/aitask-pick/SKILL.md" "$committed_files"
assert_contains_ci "Codex config committed" ".codex/config.toml" "$committed_files"
assert_not_contains_ci "Pycache not committed" "__pycache__" "$committed_files"

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

assert_contains_ci "Warns about missing remote" "No git remote 'origin' configured" "$output"
assert_contains_ci "Tells user the fix command" "git remote add origin" "$output"
assert_contains_ci "Auto-accepts non-interactively" "auto-accepting acknowledgment" "$output"
assert_eq_trim "Module-level flag is set after ack" "1" "$_AIT_SETUP_NO_REMOTE_ACKED"

# --- Test 16: warn_missing_remote_for_branch is idempotent within one run ---
echo "--- Test 16: warn_missing_remote_for_branch is idempotent ---"

# _AIT_SETUP_NO_REMOTE_ACKED is still 1 from Test 15 (parent shell preserved it)
output_file_16="$(mktemp "${TMPDIR:-/tmp}/ait_test16_XXXXXX")"
warn_missing_remote_for_branch "aitask-ids" "Other purpose" >"$output_file_16" 2>&1 </dev/null
output2=$(cat "$output_file_16")
rm -f "$output_file_16"

assert_contains_ci "Second call mentions already acknowledged" "already acknowledged" "$output2"
assert_not_contains_ci "Second call does not re-prompt" "git remote add origin" "$output2"

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

assert_eq_trim "setup_lock_branch returns 0 after acknowledgment" "0" "$rc"
assert_contains_ci "Warning fires for missing remote" "No git remote 'origin' configured" "$output"

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
    cd "$TMPDIR_18" || exit 1
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
assert_eq_trim "git status is clean after setup_python_cache_gitignore" "" "$porcelain"

# Commit message matches the new pattern
last_msg="$(git -C "$TMPDIR_18" log -1 --format=%s)"
assert_contains_ci "Last commit message announces the python cache rule" "Add __pycache__/ to .gitignore" "$last_msg"

rm -rf "$TMPDIR_18"

# --- Test 19: setup_python_cache_gitignore is idempotent (t687) ---
echo "--- Test 19: setup_python_cache_gitignore idempotent ---"

TMPDIR_19="$(setup_fake_project)"
(
    cd "$TMPDIR_19" || exit 1
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
assert_eq_trim "Python cache entry not duplicated" "1" "$entry_count"

# Second call must NOT create a new commit
assert_eq_trim "No second commit on idempotent re-run" "$commits_after_first" "$commits_after_second"

rm -rf "$TMPDIR_19"

# --- Test 20: baseline armed on bootstrap — setup's own files committed ---
echo "--- Test 20: baseline armed (bootstrap) commits setup's files ---"

TMPDIR_20="$(setup_fake_project)"
(cd "$TMPDIR_20" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" \
    && echo "init" > readme.txt && git add readme.txt && git commit -m "init" --quiet)
SCRIPT_DIR="$TMPDIR_20/.aitask-scripts"

# Snapshot BEFORE the framework file is "written by setup". VERSION is
# untracked → bootstrap → empty baseline.
snapshot_pre_setup_dirty
mkdir -p "$TMPDIR_20/aireviewguides"
echo "guide" > "$TMPDIR_20/aireviewguides/x.md"

output=$(commit_framework_files 2>&1 </dev/null)

committed_files=$(git -C "$TMPDIR_20" show --name-only --format='' HEAD 2>/dev/null)
assert_contains "Setup-written file committed (bootstrap, armed)" "aireviewguides/x.md" "$committed_files"
assert_contains_ci "Bootstrap blast-radius warning shown (non-interactive)" "first-time framework tracking" "$output"
assert_not_contains_ci "No unarmed-baseline warning when armed" "baseline not armed" "$output"

AIT_SETUP_BASELINE_ARMED=0
rm -rf "$TMPDIR_20"

# --- Test 21: NEGATIVE CONTROL — foreign dirty/staged work is never swept ---
echo "--- Test 21: negative control — foreign work not swept ---"

TMPDIR_21="$(setup_fake_project)"
echo "# staged victim" > "$TMPDIR_21/.aitask-scripts/staged.sh"
(cd "$TMPDIR_21" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" \
    && echo "init" > readme.txt && git add -A && git commit -m "init" --quiet)
SCRIPT_DIR="$TMPDIR_21/.aitask-scripts"

# Three foreign-work fixtures, all pre-existing when the snapshot runs:
# 1. unstaged edit to a tracked framework file (concurrent worktree edit)
echo "concurrent edit" >> "$TMPDIR_21/.aitask-scripts/placeholder.sh"
# 2. fully STAGED edit to a tracked framework file (invisible to
#    ls-files --others/--modified; exercises the diff --cached term)
echo "staged edit" >> "$TMPDIR_21/.aitask-scripts/staged.sh"
(cd "$TMPDIR_21" && git add .aitask-scripts/staged.sh)
# 3. pre-staged non-framework file (exercises the path-scoped commit)
echo "foreign" >> "$TMPDIR_21/readme.txt"
(cd "$TMPDIR_21" && git add readme.txt)

snapshot_pre_setup_dirty

# Setup now legitimately writes a new framework file
echo "# new helper" > "$TMPDIR_21/.aitask-scripts/newly_installed.sh"

output=$(commit_framework_files 2>&1 </dev/null)

committed_files=$(git -C "$TMPDIR_21" show --name-only --format='' HEAD 2>/dev/null)
assert_contains "Setup-written file committed" "newly_installed.sh" "$committed_files"
assert_not_contains "Concurrent unstaged framework edit NOT swept" "placeholder.sh" "$committed_files"
assert_not_contains "Pre-staged framework edit NOT swept" "staged.sh" "$committed_files"
assert_not_contains "Pre-staged foreign file NOT swept" "readme.txt" "$committed_files"
assert_contains_ci "Excluded paths reported to the user" "left alone" "$output"

status_out=$(git -C "$TMPDIR_21" status --porcelain 2>/dev/null)
assert_contains_re "Staged framework edit still staged after commit" "^MM? +\.aitask-scripts/staged\.sh" "$status_out"
assert_contains_re "Foreign staged file still staged after commit" "^M  readme\.txt" "$status_out"

AIT_SETUP_BASELINE_ARMED=0
rm -rf "$TMPDIR_21"

# --- Test 22: structural ordering — snapshot armed before data-branch setup ---
echo "--- Test 22: main() arms baseline before setup_data_branch ---"

main_body="$(declare -f main)"
snap_line=$(printf '%s\n' "$main_body" | grep -n "snapshot_pre_setup_dirty" | head -1 | cut -d: -f1)
data_line=$(printf '%s\n' "$main_body" | grep -n "setup_data_branch" | head -1 | cut -d: -f1)
assert_contains "main() calls snapshot_pre_setup_dirty" "snapshot_pre_setup_dirty" "$main_body"
assert_contains "main() calls setup_data_branch" "setup_data_branch" "$main_body"
snap_before_data="no"
if [[ -n "$snap_line" && -n "$data_line" && "$snap_line" -lt "$data_line" ]]; then
    snap_before_data="yes"
fi
assert_eq "snapshot_pre_setup_dirty precedes setup_data_branch in main()" "yes" "$snap_before_data"

# --- Test 23: data-branch twin — foreign work in the data worktree not swept ---
echo "--- Test 23: data-branch twin negative control ---"

TMPDIR_23="$(setup_fake_project)"
(cd "$TMPDIR_23" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" \
    && git add -A && git commit -m "init" --quiet)
# Standalone data worktree stand-in (its own repo; the function only needs
# .aitask-data/.git to exist and be a work tree)
mkdir -p "$TMPDIR_23/.aitask-data/aitasks/metadata"
(cd "$TMPDIR_23/.aitask-data" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" \
    && echo "cfg" > aitasks/metadata/tracked.txt && git add -A && git commit -m "init" --quiet)
SCRIPT_DIR="$TMPDIR_23/.aitask-scripts"

# Foreign work in the data worktree, pre-existing at snapshot time:
# dirty tracked metadata file + pre-staged task file (outside data paths)
echo "concurrent edit" >> "$TMPDIR_23/.aitask-data/aitasks/metadata/tracked.txt"
echo "task" > "$TMPDIR_23/.aitask-data/aitasks/t9999_foreign.md"
(cd "$TMPDIR_23/.aitask-data" && git add aitasks/t9999_foreign.md)

snapshot_pre_setup_dirty

# Setup now legitimately writes a new metadata file into the data worktree
echo "new" > "$TMPDIR_23/.aitask-data/aitasks/metadata/new_config.yaml"

output=$(commit_framework_data_files 2>&1 </dev/null)

data_committed=$(git -C "$TMPDIR_23/.aitask-data" show --name-only --format='' HEAD 2>/dev/null)
assert_contains "Setup-written data file committed" "new_config.yaml" "$data_committed"
assert_not_contains "Dirty metadata file NOT swept (data twin)" "tracked.txt" "$data_committed"
assert_not_contains "Pre-staged task file NOT swept (data twin)" "t9999_foreign.md" "$data_committed"

data_status=$(git -C "$TMPDIR_23/.aitask-data" status --porcelain 2>/dev/null)
assert_contains_re "Pre-staged task file still staged (data twin)" "^A  aitasks/t9999_foreign\.md" "$data_status"

AIT_SETUP_BASELINE_ARMED=0
rm -rf "$TMPDIR_23"

# ============================================================
# CLAUDE.md commit ownership + main() wiring (t1612)
# ============================================================
# t1612 moved update_claudemd_git_section out of setup_data_branch Step 8 (which
# also committed CLAUDE.md itself, unscoped) into setup_code_agents (which commits
# nothing). CLAUDE.md's commit is therefore now owned by commit_framework_files --
# path-scoped and baseline-protected -- and correctness depends on a cross-function
# ordering invariant in main() that nothing else pins. Tests 24-26 pin both.
#
# Fixture note: setup_fake_project creates aitasks/metadata/ but NO instructions
# seed and no seed/ dir, so assemble_aitasks_instructions returns 1 and
# update_claudemd_git_section writes nothing. Both drives below MUST copy the real
# shared seed in first or they pass vacuously.

# Drive the real setup_code_agents against <project_dir>. Only _is_agent_installed
# is stubbed, and only for determinism (it is `command -v codex/opencode`, a
# property of the developer's machine). setup_claude_code and prune_retired_skills
# self-no-op in this fixture. Assertions stay outside the subshell.
run_setup_code_agents() {
    local project_dir="$1"
    (
        SCRIPT_DIR="$project_dir/.aitask-scripts"
        mkdir -p "$SCRIPT_DIR"
        # Overrides the sourced aitask_setup.sh definition that setup_code_agents
        # calls; shellcheck cannot see that indirect invocation.
        # shellcheck disable=SC2329
        _is_agent_installed() { return 1; }
        setup_code_agents </dev/null
    )
}

# --- Test 24: generated CLAUDE.md is committed, exactly once ---
echo "--- Test 24: generated CLAUDE.md committed exactly once (t1612) ---"

TMPDIR_24="$(setup_fake_project)"
cp "$PROJECT_DIR/seed/aitasks_agent_instructions.seed.md" "$TMPDIR_24/aitasks/metadata/"
(cd "$TMPDIR_24" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" \
    && git add -A && git commit -m "init" --quiet)
SCRIPT_DIR="$TMPDIR_24/.aitask-scripts"

snapshot_pre_setup_dirty
run_setup_code_agents "$TMPDIR_24" >/dev/null 2>&1
commit_framework_files </dev/null >/dev/null 2>&1

head_claudemd=$(git -C "$TMPDIR_24" show HEAD:CLAUDE.md 2>/dev/null || true)
assert_contains "T24: generated CLAUDE.md is in HEAD" "## Git Operations on Task/Plan Files" "$head_claudemd"
status_24=$(git -C "$TMPDIR_24" status --porcelain -- CLAUDE.md 2>/dev/null || true)
assert_eq "T24: CLAUDE.md clean after commit_framework_files" "" "$status_24"
# "Committed exactly once" — the task's own scope note. Also fails if a future
# edit reintroduces a second writer (e.g. restores Step 9's files_to_add clause).
claudemd_commits=$(git -C "$TMPDIR_24" log --oneline -- CLAUDE.md 2>/dev/null | wc -l | tr -d ' ')
assert_eq "T24: CLAUDE.md touched by exactly one commit" "1" "${claudemd_commits:-0}"

AIT_SETUP_BASELINE_ARMED=0
rm -rf "$TMPDIR_24"

# --- Test 25: NEGATIVE CONTROL — a pre-dirty CLAUDE.md is reported, not committed ---
echo "--- Test 25: pre-dirty CLAUDE.md reported, not committed (t1612) ---"

# The replacement half of the guarantee. Step 9's unscoped `git add CLAUDE.md`
# used to force-commit a user's in-progress edits; commit_framework_files must
# instead subtract them via the pre-setup baseline and report them. The fixture
# CLAUDE.md carries NO sentinel, so the t1607 guard does not fire and the block
# really is appended on top of the dirty file — the strong version of the claim.
TMPDIR_25="$(setup_fake_project)"
cp "$PROJECT_DIR/seed/aitasks_agent_instructions.seed.md" "$TMPDIR_25/aitasks/metadata/"
printf '# My Project\n\n## Build\n\nRun make.\n' > "$TMPDIR_25/CLAUDE.md"
(cd "$TMPDIR_25" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" \
    && git add -A && git commit -m "init" --quiet)
SCRIPT_DIR="$TMPDIR_25/.aitask-scripts"

# The user's in-progress edit, pre-existing when the snapshot runs
printf '\nUSER EDIT t1612\n' >> "$TMPDIR_25/CLAUDE.md"

snapshot_pre_setup_dirty
run_setup_code_agents "$TMPDIR_25" >/dev/null 2>&1
output=$(commit_framework_files 2>&1 </dev/null)

head_claudemd=$(git -C "$TMPDIR_25" show HEAD:CLAUDE.md 2>/dev/null || true)
assert_not_contains "T25: pre-dirty CLAUDE.md edit NOT committed" "USER EDIT t1612" "$head_claudemd"
assert_not_contains "T25: generated block NOT committed over the dirty file" ">>>aitasks" "$head_claudemd"
assert_contains_ci "T25: excluded CLAUDE.md reported to the user" "left alone" "$output"
status_25=$(git -C "$TMPDIR_25" status --porcelain -- CLAUDE.md 2>/dev/null || true)
assert_contains "T25: CLAUDE.md still dirty in the worktree" "CLAUDE.md" "$status_25"

AIT_SETUP_BASELINE_ARMED=0
rm -rf "$TMPDIR_25"

# --- Test 26: structural ordering — main() wires the new call site correctly ---
echo "--- Test 26: main() orders setup_code_agents between data-branch and commit ---"

# Every behavioral test above drives setup_code_agents DIRECTLY, so they all stay
# green if main() stopped calling it or called it after commit_framework_files —
# which would break the real `ait setup` lifecycle and the commit guarantee.
main_body="$(declare -f main)"
assert_contains "T26: main() calls setup_code_agents" "setup_code_agents" "$main_body"
assert_contains "T26: main() calls commit_framework_files" "commit_framework_files" "$main_body"
data_line=$(printf '%s\n' "$main_body" | grep -n "setup_data_branch" | head -1 | cut -d: -f1)
agents_line=$(printf '%s\n' "$main_body" | grep -n "setup_code_agents" | head -1 | cut -d: -f1)
commit_line=$(printf '%s\n' "$main_body" | grep -n "commit_framework_files" | head -1 | cut -d: -f1)
# setup_data_branch first: it creates the aitasks/ symlink and populates the seed
# metadata that assemble_aitasks_instructions resolves. Without it the resolver
# falls back to seed/, which exists in a dev checkout but is deleted by install.sh
# in a real installation — so the ordering is load-bearing only off this box.
data_before_agents="no"
if [[ -n "$data_line" && -n "$agents_line" && "$data_line" -lt "$agents_line" ]]; then
    data_before_agents="yes"
fi
assert_eq "T26: setup_data_branch precedes setup_code_agents in main()" "yes" "$data_before_agents"
# setup_code_agents before commit_framework_files: it writes CLAUDE.md but commits
# nothing, so the reverse order would never commit the generated block.
agents_before_commit="no"
if [[ -n "$agents_line" && -n "$commit_line" && "$agents_line" -lt "$commit_line" ]]; then
    agents_before_commit="yes"
fi
assert_eq "T26: setup_code_agents precedes commit_framework_files in main()" "yes" "$agents_before_commit"

# --- Test 27: .gitignore helpers commit path-scoped and honour the baseline (t1959) ---
# Every .gitignore helper commits through _ait_commit_gitignore_rule. With a
# real armed baseline (tracked VERSION): a .gitignore already dirty before setup
# — edited, or deleted staged/unstaged — is never committed by a helper, and a
# helper commit never carries another file someone else staged.
echo "--- Test 27: .gitignore helpers: path-scoped, baseline-aware commits ---"

# A committed project whose .gitignore lacks every helper rule.
new_gitignore_repo() {
    local d
    d="$(setup_fake_project)"
    echo "base-rule" > "$d/.gitignore"
    (cd "$d" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" \
        && git add -A && git commit -m "init" --quiet)
    echo "$d"
}
commit_count() { git -C "$1" rev-list --count HEAD 2>/dev/null; }

while IFS='|' read -r helper rule; do
    # (a) pre-setup .gitignore edit: rule added on disk, nothing committed.
    d="$(new_gitignore_repo)"
    SCRIPT_DIR="$d/.aitask-scripts"
    echo "user-edit" >> "$d/.gitignore"
    before="$(commit_count "$d")"
    snapshot_pre_setup_dirty
    "$helper" </dev/null >/dev/null 2>&1
    head_gi="$(git -C "$d" show HEAD:.gitignore)"
    assert_eq "27a $helper: no commit over a dirty .gitignore" "$before" "$(commit_count "$d")"
    assert_not_contains "27a $helper: rule not in HEAD" "$rule" "$head_gi"
    assert_not_contains "27a $helper: user edit not in HEAD" "user-edit" "$head_gi"
    assert_eq "27a $helper: rule and user edit both on disk" "yes" \
        "$(grep -qxF "$rule" "$d/.gitignore" && grep -qxF "user-edit" "$d/.gitignore" && echo yes)"
    rm -rf "$d"

    # (b) clean .gitignore, foreign file staged: one commit, .gitignore only.
    d="$(new_gitignore_repo)"
    SCRIPT_DIR="$d/.aitask-scripts"
    echo "foreign" > "$d/foreign.txt"
    git -C "$d" add foreign.txt
    before="$(commit_count "$d")"
    snapshot_pre_setup_dirty
    "$helper" </dev/null >/dev/null 2>&1
    assert_eq "27b $helper: exactly one new commit" "$((before + 1))" "$(commit_count "$d")"
    assert_eq "27b $helper: the commit names only .gitignore" ".gitignore" \
        "$(git -C "$d" show --name-only --format='' HEAD)"
    assert_eq "27b $helper: rule committed" "yes" \
        "$(git -C "$d" show HEAD:.gitignore | grep -xF "$rule" >/dev/null && echo yes)"
    assert_eq "27b $helper: foreign file still staged" "foreign.txt" \
        "$(git -C "$d" diff --cached --name-only)"
    rm -rf "$d"
done <<'HELPERS'
setup_draft_directory|aitasks/new/
setup_python_cache_gitignore|__pycache__/
setup_gate_logs_gitignore|.aitask-gates/
setup_testmap_gitignore|.aitask-testmap/
setup_shadow_store_gitignore|.aitask-shadow/
setup_scratchpad_gitignore|.aitask-scratchpad/
setup_sitrep_store_gitignore|.aitask-sitrep/
setup_cache_gitignore|.aitask-cache/
setup_worktree_dirs_gitignore|aiwork/
HELPERS

# (c)/(d) a deleted .gitignore is a pre-existing change too. The gap was in the
# shared baseline capture (absent paths were never scanned), so one helper
# stands for all nine.
for mode in unstaged staged; do
    d="$(new_gitignore_repo)"
    SCRIPT_DIR="$d/.aitask-scripts"
    if [[ "$mode" == "staged" ]]; then
        git -C "$d" rm -q .gitignore
    else
        rm "$d/.gitignore"
    fi
    before="$(commit_count "$d")"
    snapshot_pre_setup_dirty
    assert_eq "27 $mode deletion: .gitignore in the baseline" "yes" \
        "$(grep -qxF ".gitignore" <<<"$AIT_SETUP_DIRTY_BASELINE" && echo yes)"
    setup_python_cache_gitignore </dev/null >/dev/null 2>&1
    assert_eq "27 $mode deletion: no commit over the deletion" "$before" "$(commit_count "$d")"
    assert_eq "27 $mode deletion: HEAD .gitignore unchanged" "base-rule" \
        "$(git -C "$d" show HEAD:.gitignore)"
    assert_eq "27 $mode deletion: recreated rule on disk" "yes" \
        "$(grep -qxF "__pycache__/" "$d/.gitignore" && echo yes)"
    if [[ "$mode" == "staged" ]]; then
        assert_contains_re "27 staged deletion: still staged" "^D[[:space:]]+\.gitignore$" \
            "$(git -C "$d" diff --cached --name-status -- .gitignore)"
    else
        assert_eq "27 unstaged deletion: left modified" " M .gitignore" \
            "$(git -C "$d" status --porcelain -- .gitignore)"
    fi
    rm -rf "$d"
done

# (e) the deletion-aware capture is shared: commit_framework_files does not
# commit a regenerated framework file over a pre-setup deletion either.
d="$(new_gitignore_repo)"
SCRIPT_DIR="$d/.aitask-scripts"
echo "original" > "$d/CLAUDE.md"
(cd "$d" && git add CLAUDE.md && git commit -m "claude" --quiet)
rm "$d/CLAUDE.md"
snapshot_pre_setup_dirty
echo "regenerated" > "$d/CLAUDE.md"
output=$(commit_framework_files 2>&1 </dev/null)
assert_eq "27e: HEAD CLAUDE.md keeps the original" "original" "$(git -C "$d" show HEAD:CLAUDE.md)"
assert_contains_ci "27e: deleted-then-regenerated file reported" "left alone" "$output"
rm -rf "$d"

# (f) every .gitignore helper — setup's (t2178), the discovery-cache rule
# (t2173_1) and the upgrade-path store rules (t2177) — reports a write it could
# not make: it warns, stays non-fatal, writes nothing and commits nothing, and
# none claims a rule was added. A directory in place of .gitignore stands in
# where root would ignore a read-only mode. <reported> is what the failure line
# names (every rule of the group).
#
# Each case also runs in a child shell under the errexit `ait setup`'s main()
# has: this shell dropped it after sourcing, so an unchecked write that would
# abort setup is invisible to the in-process call. ERREXIT_ON is the control.
#
# The fifo fault puts a FIFO where .gitignore should be: opening it blocks until
# a peer appears, for read (grep) and for write (>>) alike. Nothing unbounded may
# touch it, so that case runs only in the bounded child — and skips
# snapshot_pre_setup_dirty too: its `git ls-files --others --exclude-standard`
# reads .gitignore (git 2.56 does not block on a FIFO there, but the fixture
# should not depend on that). An unarmed baseline is the direct-call default,
# and the failure path never reaches the commit.
errexit_helper_log="$(mktemp)"
# errexit_helper_run <dir> <helper> -> status (124 = did not return in time);
# output in $errexit_helper_log.
errexit_helper_run() {
    run_bounded 15 "$errexit_helper_log" env HOME="$1/home-scratch" bash -c '
        source "$1" --source-only
        [[ $- == *e* ]] && echo ERREXIT_ON
        SCRIPT_DIR="$2/.aitask-scripts"
        "$3"
        echo SURVIVED' _ "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" "$1" "$2"
}
while IFS='|' read -r helper reported; do
    for fault in readonly directory fifo; do
        d="$(new_gitignore_repo)"
        SCRIPT_DIR="$d/.aitask-scripts"
        case "$fault" in
            readonly)
                chmod 444 "$d/.gitignore"
                if [[ -w "$d/.gitignore" ]]; then
                    echo "SKIP: 27f $helper readonly (mode ignored for this user)"
                    rm -rf "$d"
                    continue
                fi ;;
            directory) rm "$d/.gitignore"; mkdir "$d/.gitignore" ;;
            fifo) rm "$d/.gitignore"; mkfifo "$d/.gitignore" ;;
        esac
        before="$(commit_count "$d")"
        if [[ "$fault" != fifo ]]; then
            snapshot_pre_setup_dirty
            rc=0
            out="$("$helper" </dev/null 2>&1)" || rc=$?
            assert_eq "27f $helper $fault: non-fatal" "0" "$rc"
        fi
        rc=0
        errexit_helper_run "$d" "$helper" || rc=$?
        child_out="$(cat "$errexit_helper_log")"
        assert_eq "27f $helper $fault: child returns 0 within 15s (124 = hung)" "0" "$rc"
        assert_contains "27f $helper $fault: child shell has errexit" "ERREXIT_ON" "$child_out"
        assert_contains "27f $helper $fault: survives setup's errexit" "SURVIVED" "$child_out"
        [[ "$fault" == fifo ]] && out="$child_out"
        assert_contains "27f $helper $fault: reports the failure" \
            "Could not add $reported to .gitignore" "$out"
        # Nothing was written, so the warning may say so (27l: one that did write).
        assert_contains "27f $helper $fault: says unchanged" \
            "Could not add $reported to .gitignore — left unchanged" "$out"
        assert_not_contains "27f $helper $fault: no 'added' claim" "Added " "$out"
        assert_not_contains "27f $helper $fault: no 'rule added' claim" "rule added" "$out"
        assert_not_contains "27f $helper $fault: no 'already' claim" "already in .gitignore" "$out"
        assert_eq "27f $helper $fault: no commit" "$before" "$(commit_count "$d")"
        case "$fault" in
            readonly) assert_eq "27f $helper readonly: file unchanged" "base-rule" "$(cat "$d/.gitignore")" ;;
            fifo) assert_eq "27f $helper fifo: still a FIFO" "yes" "$([[ -p "$d/.gitignore" ]] && echo yes)" ;;
        esac
        chmod -R u+w "$d"
        rm -rf "$d"
    done
done <<'FAILING'
setup_draft_directory|aitasks/new/
setup_python_cache_gitignore|__pycache__/
setup_gate_logs_gitignore|.aitask-gates/
setup_testmap_gitignore|.aitask-testmap/
setup_shadow_store_gitignore|.aitask-shadow/
setup_scratchpad_gitignore|.aitask-scratchpad/
setup_sitrep_store_gitignore|.aitask-sitrep/
setup_cache_gitignore|.aitask-cache/
setup_worktree_dirs_gitignore|aiwork/ .aitask-crews/
upgrade_cache_gitignore|.aitask-cache/
upgrade_store_gitignore_rules|.aitask-gates/
FAILING
rm -f "$errexit_helper_log"

# (g) the upgrade wrapper's success paths: it writes, never commits (install.sh
# commits under its own baseline), and is idempotent.
d="$(new_gitignore_repo)"
SCRIPT_DIR="$d/.aitask-scripts"
before="$(commit_count "$d")"
out="$(upgrade_cache_gitignore </dev/null 2>&1)"
assert_contains "27g upgrade_cache_gitignore: reports the add" "Added .aitask-cache/" "$out"
assert_eq "27g upgrade_cache_gitignore: rule on disk" "1" "$(grep -cxF ".aitask-cache/" "$d/.gitignore")"
assert_eq "27g upgrade_cache_gitignore: no commit" "$before" "$(commit_count "$d")"
out="$(upgrade_cache_gitignore </dev/null 2>&1)"
assert_contains "27g upgrade_cache_gitignore: second run is a no-op" "already in .gitignore" "$out"
assert_eq "27g upgrade_cache_gitignore: not duplicated" "1" "$(grep -cxF ".aitask-cache/" "$d/.gitignore")"
rm -rf "$d"

# (g2) the same for the upgrade-path store and worktree rules (t2177).
STORE_RULES=(.aitask-gates/ .aitask-testmap/ .aitask-shadow/ .aitask-scratchpad/ .aitask-sitrep/ aiwork/ .aitask-crews/)
d="$(new_gitignore_repo)"
SCRIPT_DIR="$d/.aitask-scripts"
before="$(commit_count "$d")"
out="$(upgrade_store_gitignore_rules </dev/null 2>&1)"
for rule in "${STORE_RULES[@]}"; do
    assert_contains "27g2 upgrade_store_gitignore_rules: reports adding $rule" "$rule" "$out"
    assert_eq "27g2 upgrade_store_gitignore_rules: $rule on disk" "1" "$(grep -cxF -- "$rule" "$d/.gitignore")"
done
assert_eq "27g2 upgrade_store_gitignore_rules: no commit" "$before" "$(commit_count "$d")"
out="$(upgrade_store_gitignore_rules </dev/null 2>&1)"
assert_not_contains "27g2 upgrade_store_gitignore_rules: second run adds nothing" "Added " "$out"
for rule in "${STORE_RULES[@]}"; do
    assert_eq "27g2 upgrade_store_gitignore_rules: $rule not duplicated" "1" "$(grep -cxF -- "$rule" "$d/.gitignore")"
done
rm -rf "$d"

# (g3) each rule is guarded on its own: a hand-added .aitask-crews/ (this repo
# carried one for a long time) gains only aiwork/.
d="$(new_gitignore_repo)"
SCRIPT_DIR="$d/.aitask-scripts"
echo ".aitask-crews/" >> "$d/.gitignore"
out="$(upgrade_store_gitignore_rules </dev/null 2>&1)"
assert_contains "27g3 reports adding only aiwork/" "Added aiwork/ to .gitignore" "$out"
assert_eq "27g3 aiwork/ added" "1" "$(grep -cxF "aiwork/" "$d/.gitignore")"
assert_eq "27g3 .aitask-crews/ not duplicated" "1" "$(grep -cxF ".aitask-crews/" "$d/.gitignore")"
rm -rf "$d"

# (h) parity: the upgrade route writes exactly what setup writes — same rules,
# same comments, same order — so the two routes cannot drift apart.
UPGRADE_COVERED=(setup_gate_logs_gitignore setup_testmap_gitignore
    setup_shadow_store_gitignore setup_scratchpad_gitignore setup_sitrep_store_gitignore
    setup_worktree_dirs_gitignore)
d_setup="$(new_gitignore_repo)"
SCRIPT_DIR="$d_setup/.aitask-scripts"
snapshot_pre_setup_dirty
for helper in "${UPGRADE_COVERED[@]}"; do "$helper" </dev/null >/dev/null 2>&1; done
d_up="$(new_gitignore_repo)"
SCRIPT_DIR="$d_up/.aitask-scripts"
upgrade_store_gitignore_rules </dev/null >/dev/null 2>&1
assert_eq "27h upgrade .gitignore is byte-identical to setup's" \
    "$(cat "$d_setup/.gitignore")" "$(cat "$d_up/.gitignore")"
assert_eq "27h ... and setup's carries every store rule" "7" \
    "$(grep -cxF -e .aitask-gates/ -e .aitask-testmap/ -e .aitask-shadow/ \
        -e .aitask-scratchpad/ -e .aitask-sitrep/ -e aiwork/ -e .aitask-crews/ "$d_setup/.gitignore")"
rm -rf "$d_setup" "$d_up"

# (i) drift guard: every .gitignore rule setup's main() writes has an upgrade
# route (or an explicit exclusion), so a new setup-only rule fails here until
# one is decided. __pycache__/ is excluded: install.sh installs the scoped
# .aitask-scripts/.gitignore, which covers the framework's own caches.
main_helpers="$(sed -n '/^main() {/,/^}/p' "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" \
    | grep -oE '\bsetup_[a-z_]*gitignore\b' | sort -u)"
assert_contains "27i the main() scan found the helpers" "setup_cache_gitignore" "$main_helpers"
while IFS= read -r helper; do
    [[ -n "$helper" ]] || continue
    case " ${UPGRADE_COVERED[*]} setup_cache_gitignore setup_python_cache_gitignore " in
        *" $helper "*) covered=yes ;;
        *) covered=no ;;
    esac
    assert_eq "27i $helper has an upgrade route or an explicit exclusion" "yes" "$covered"
done <<<"$main_helpers"

# (k) literal pins for every string the shared rule table moves (t2178). Once
# setup and upgrade both read one table, 27h compares that table with itself, so
# it can no longer catch a mis-copied comment or rule. These literals are the
# independent oracle: the exact block each setup helper writes, its commit
# subject, its added and already lines, and upgrade's per-group labels and
# failure lines. Written green against the pre-table helpers. The "<rules> to
# .gitignore (<note>)" substring is what both the old "Adding ..." and the new
# "Added ..." line carry.
while IFS='|' read -r helper comment rules note commit added already; do
    d="$(new_gitignore_repo)"
    SCRIPT_DIR="$d/.aitask-scripts"
    snapshot_pre_setup_dirty
    before="$(commit_count "$d")"
    out="$("$helper" </dev/null 2>&1)"
    assert_eq "27k $helper: exact block written" \
        "$(printf 'base-rule\n\n# %s\n%s\n' "$comment" "${rules// /$'\n'}"; echo .)" \
        "$(cat "$d/.gitignore"; echo .)"
    assert_eq "27k $helper: one commit" "$((before + 1))" "$(commit_count "$d")"
    assert_eq "27k $helper: commit subject" "$commit" "$(git -C "$d" log -1 --format=%s)"
    assert_contains "27k $helper: names the note" "$rules to .gitignore ($note)" "$out"
    assert_contains "27k $helper: added line" "$added" "$out"
    before="$(commit_count "$d")"
    out="$("$helper" </dev/null 2>&1)"
    assert_contains "27k $helper: already line" "$already" "$out"
    assert_eq "27k $helper: re-run commits nothing" "$before" "$(commit_count "$d")"
    rm -rf "$d"
done <<'PINS'
setup_draft_directory|Draft tasks (local, not committed)|aitasks/new/|draft tasks are local-only|ait: Add aitasks/new/ to .gitignore (draft tasks)|Draft directory configured (aitasks/new/ in .gitignore)|Draft directory already in .gitignore
setup_python_cache_gitignore|Python cache artifacts (generated by aitasks Python TUIs)|__pycache__/|Python cache artifacts|ait: Add __pycache__/ to .gitignore (Python cache artifacts)|Python cache rule added to .gitignore|Python cache rule already in .gitignore
setup_gate_logs_gitignore|Gate sidecar logs (per-task verifier output; in-body summary is committed)|.aitask-gates/|gate sidecar logs|ait: Add .aitask-gates/ to .gitignore (gate sidecar logs)|Gate sidecar-log rule added to .gitignore|Gate sidecar-log rule already in .gitignore
setup_testmap_gitignore|Test map runs, ledger and onboarding scratch (per-checkout)|.aitask-testmap/|test map runs and ledger|ait: Add .aitask-testmap/ to .gitignore (test map scratch)|Test map scratch rule added to .gitignore|Test map scratch rule already in .gitignore
setup_shadow_store_gitignore|Shadow concern-rejection store (per-task, local-only; pruned at archive)|.aitask-shadow/|shadow concern-rejection store|ait: Add .aitask-shadow/ to .gitignore (shadow rejection store)|Shadow rejection-store rule added to .gitignore|Shadow rejection-store rule already in .gitignore
setup_scratchpad_gitignore|Scratchpad notes (per-task, local-only; pruned at archive)|.aitask-scratchpad/|scratchpad notes store|ait: Add .aitask-scratchpad/ to .gitignore (scratchpad notes)|Scratchpad notes rule added to .gitignore|Scratchpad notes rule already in .gitignore
setup_sitrep_store_gitignore|Sitrep todo store (per-repo, local-only; not rebuildable)|.aitask-sitrep/|sitrep todo store|ait: Add .aitask-sitrep/ to .gitignore (sitrep todo store)|Sitrep store rule added to .gitignore|Sitrep store rule already in .gitignore
setup_cache_gitignore|Discovery caches (per-checkout, content-keyed, safe to delete)|.aitask-cache/|discovery caches|ait: Add .aitask-cache/ to .gitignore (discovery caches)|Discovery-cache rule added to .gitignore|Discovery-cache rule already in .gitignore
setup_worktree_dirs_gitignore|Framework worktrees (local, per-task and per-crew branches)|aiwork/ .aitask-crews/|framework worktree directories|ait: Add worktree directories to .gitignore|Worktree directory rules added to .gitignore (aiwork/ .aitask-crews/)|Worktree directory rules already in .gitignore
PINS

# Upgrade route: each group's added, already and failure lines.
d="$(new_gitignore_repo)"
SCRIPT_DIR="$d/.aitask-scripts"
out_added="$(upgrade_store_gitignore_rules </dev/null 2>&1)"
out_again="$(upgrade_store_gitignore_rules </dev/null 2>&1)"
rm -rf "$d"
d="$(new_gitignore_repo)"
SCRIPT_DIR="$d/.aitask-scripts"
rm "$d/.gitignore"
mkdir "$d/.gitignore"
out_failed="$(upgrade_store_gitignore_rules </dev/null 2>&1)"
rm -rf "$d"
while IFS='|' read -r rules label what; do
    assert_contains "27k upgrade $rules: added line" "Added $rules to .gitignore ($label)" "$out_added"
    assert_contains "27k upgrade $rules: already line" "$rules already in .gitignore" "$out_again"
    assert_contains "27k upgrade $rules: failure line" \
        "  $what will show as untracked in 'git status'." "$out_failed"
done <<'UPGRADE_PINS'
.aitask-gates/|gate sidecar logs|Gate sidecar logs
.aitask-testmap/|test map scratch|Test map runs
.aitask-shadow/|shadow rejection store|The shadow rejection store
.aitask-scratchpad/|scratchpad notes|Scratchpad notes
.aitask-sitrep/|sitrep store|The sitrep todo store
aiwork/ .aitask-crews/|framework worktree directories|Task and crew worktrees
UPGRADE_PINS

d="$(new_gitignore_repo)"
SCRIPT_DIR="$d/.aitask-scripts"
out="$(upgrade_cache_gitignore </dev/null 2>&1)"
assert_contains "27k upgrade_cache_gitignore: added line" \
    "Added .aitask-cache/ to .gitignore (discovery caches)" "$out"
assert_eq "27k upgrade_cache_gitignore: exact block written" \
    "$(printf 'base-rule\n\n# %s\n%s\n' 'Discovery caches (per-checkout, content-keyed, safe to delete)' '.aitask-cache/'; echo .)" \
    "$(cat "$d/.gitignore"; echo .)"
out="$(upgrade_cache_gitignore </dev/null 2>&1)"
assert_contains "27k upgrade_cache_gitignore: already line" \
    "Discovery-cache rule already in .gitignore" "$out"
rm -rf "$d"

# (l) a write that stops part-way (t2178): the append is several write()s, so a
# failure after the first leaves bytes behind, and the warning must not claim
# the file was left unchanged. A 1 KiB file-size limit on a 1016-byte .gitignore
# cuts the append inside its comment line; SIGXFSZ is ignored so the write fails
# with EFBIG instead of killing the shell. Control: the file must have grown,
# but by less than a whole block — otherwise the probe did not cut a write.
partial_log="$(mktemp)"
partial_fixture() {
    local d
    d="$(new_gitignore_repo)"
    { printf 'base-rule\n'; printf '%01005d\n' 0; } > "$d/.gitignore"
    git -C "$d" commit -q -m "1016-byte .gitignore" -- .gitignore
    echo "$d"
}
# partial_run <dir> <helper> -> status; output in $partial_log. The limit is set
# only in the pipeline's left stage, which writes to a pipe: the log file is
# written by `cat`, forked outside the limit, so a long warning cannot hit it.
partial_run() {
    run_bounded 15 "$partial_log" env HOME="$1/home-scratch" bash -c '
        source "$1" --source-only
        SCRIPT_DIR="$2/.aitask-scripts"
        { trap "" XFSZ; ulimit -f 1; "$3"; echo SURVIVED; } 2>&1 | cat' \
        _ "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" "$1" "$2"
}
gates_block_bytes=$(( $(printf '\n# %s\n%s\n' \
    'Gate sidecar logs (per-task verifier output; in-body summary is committed)' \
    '.aitask-gates/' | wc -c) ))
for helper in setup_gate_logs_gitignore upgrade_store_gitignore_rules; do
    d="$(partial_fixture)"
    assert_eq "27l $helper: fixture is 1016 bytes" "1016" "$(( $(wc -c < "$d/.gitignore") ))"
    before="$(commit_count "$d")"
    rc=0
    partial_run "$d" "$helper" || rc=$?
    out="$(cat "$partial_log")"
    size=$(( $(wc -c < "$d/.gitignore") ))
    assert_eq "27l $helper: the write was cut part-way (control)" "yes" \
        "$([[ "$size" -gt 1016 && "$size" -lt $((1016 + gates_block_bytes)) ]] && echo yes)"
    assert_eq "27l $helper: returns 0 within 15s" "0" "$rc"
    assert_contains "27l $helper: survives" "SURVIVED" "$out"
    assert_contains "27l $helper: says the write stopped part-way" \
        "Could not add .aitask-gates/ to .gitignore — the write stopped part-way" "$out"
    assert_not_contains "27l $helper: no unchanged claim for .aitask-gates/" \
        "Could not add .aitask-gates/ to .gitignore — left unchanged" "$out"
    assert_not_contains "27l $helper: no 'added' claim" "Added " "$out"
    assert_not_contains "27l $helper: no 'rule added' claim" "rule added" "$out"
    assert_eq "27l $helper: no commit" "$before" "$(commit_count "$d")"
    if [[ "$helper" == upgrade_store_gitignore_rules ]]; then
        # The next group's first write fails outright at the limit: unchanged.
        assert_contains "27l $helper: a group that wrote nothing says unchanged" \
            "Could not add .aitask-testmap/ to .gitignore — left unchanged" "$out"
    fi
    rm -rf "$d"
done
rm -f "$partial_log"

# --- Test 28: each baseline is gated on its own committer's predicate (t1972) ---
# The data committer has no main-repo guard and the main committer needs no
# HEAD, so neither baseline may hide behind the main bootstrap check; and a
# staged rename must be baselined on both sides.
echo "--- Test 28: baseline gates match the committers; staged renames (t1972) ---"

# A here-string, not `printf | grep -q`: no writer to SIGPIPE under pipefail (t2056).
has_line() { grep -qxF -- "$2" <<<"$1" && echo yes || echo no; }

# A standalone data worktree stand-in (same shape as Test 23).
new_data_repo() {
    local d="$1"
    mkdir -p "$d/.aitask-data/aitasks/metadata" "$d/.aitask-data/aireviewguides"
    (cd "$d/.aitask-data" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" \
        && echo "cfg" > aitasks/metadata/tracked.txt && echo "guide" > aireviewguides/g.md \
        && git add -A && git commit -m "init" --quiet)
}

# (a) VERSION untracked in the main repo: the data baseline is still captured.
d="$(setup_fake_project)"
(cd "$d" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" \
    && echo "init" > readme.txt && git add readme.txt && git commit -m "init" --quiet)
new_data_repo "$d"
SCRIPT_DIR="$d/.aitask-scripts"
echo "concurrent edit" >> "$d/.aitask-data/aitasks/metadata/tracked.txt"
snapshot_pre_setup_dirty
assert_eq "28a: dirty data metadata in the baseline (VERSION untracked)" "yes" \
    "$(has_line "$AIT_SETUP_DATA_DIRTY_BASELINE" "aitasks/metadata/tracked.txt")"
echo "new" > "$d/.aitask-data/aitasks/metadata/new_config.yaml"
commit_framework_data_files </dev/null >/dev/null 2>&1
data_committed="$(git -C "$d/.aitask-data" show --name-only --format='' HEAD)"
assert_eq "28a: setup-written data file committed" "yes" \
    "$(has_line "$data_committed" "aitasks/metadata/new_config.yaml")"
assert_eq "28a: dirty data metadata NOT committed" "no" \
    "$(has_line "$data_committed" "aitasks/metadata/tracked.txt")"
assert_eq "28a: dirty data metadata still modified" " M aitasks/metadata/tracked.txt" \
    "$(git -C "$d/.aitask-data" status --porcelain -- aitasks/metadata/tracked.txt)"
AIT_SETUP_BASELINE_ARMED=0
rm -rf "$d"

# (a2) a whole data framework dir deleted (staged): absent paths are scanned.
d="$(setup_fake_project)"
(cd "$d" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" \
    && git add -A && git commit -m "init" --quiet)
new_data_repo "$d"
SCRIPT_DIR="$d/.aitask-scripts"
git -C "$d/.aitask-data" rm -r -q aireviewguides
before="$(commit_count "$d/.aitask-data")"
snapshot_pre_setup_dirty
mkdir -p "$d/.aitask-data/aireviewguides"
echo "regenerated" > "$d/.aitask-data/aireviewguides/g.md"
commit_framework_data_files </dev/null >/dev/null 2>&1
assert_eq "28a2: no data commit over the deleted dir" "$before" "$(commit_count "$d/.aitask-data")"
assert_eq "28a2: staged deletion still staged" "D	aireviewguides/g.md" \
    "$(git -C "$d/.aitask-data" diff --cached --name-status -- aireviewguides)"
AIT_SETUP_BASELINE_ARMED=0
rm -rf "$d"

# (b) no HEAD, VERSION staged, user .gitignore staged: the main baseline runs.
d="$(setup_fake_project)"
(cd "$d" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" \
    && git add .aitask-scripts/VERSION && printf 'user-rule.log\n' > .gitignore && git add .gitignore)
SCRIPT_DIR="$d/.aitask-scripts"
snapshot_pre_setup_dirty
printf 'aiwork/\n' >> "$d/.gitignore"
mkdir -p "$d/aireviewguides"
echo "guide" > "$d/aireviewguides/x.md"
output=$(commit_framework_files 2>&1 </dev/null)
committed="$(git -C "$d" show --name-only --format='' HEAD 2>/dev/null)"
assert_eq "28b: setup-written file committed" "yes" "$(has_line "$committed" "aireviewguides/x.md")"
assert_eq "28b: staged user .gitignore NOT committed" "no" "$(has_line "$committed" ".gitignore")"
assert_eq "28b: index .gitignore is the user's" "user-rule.log" "$(git -C "$d" show :.gitignore)"
assert_contains_ci "28b: pre-existing changes reported" "left alone" "$output"
AIT_SETUP_BASELINE_ARMED=0
rm -rf "$d"

# (c) staged rename whose source setup recreates. diff.renames is pinned
# repo-locally: an inherited diff.renames=false would list both sides even
# without --no-renames and void this case's negative control.
d="$(setup_fake_project)"
(cd "$d" && git init --quiet && git config user.email "t@t.com" && git config user.name "T" \
    && git config diff.renames true && git add -A && git commit -m "init" --quiet \
    && git mv .aitask-scripts/placeholder.sh .aitask-scripts/renamed.sh)
SCRIPT_DIR="$d/.aitask-scripts"
snapshot_pre_setup_dirty
echo "# recreated" > "$d/.aitask-scripts/placeholder.sh"
echo "# new helper" > "$d/.aitask-scripts/newly_installed.sh"
commit_framework_files </dev/null >/dev/null 2>&1
committed="$(git -C "$d" show --name-only --format='' HEAD)"
assert_eq "28c: setup-written file committed" "yes" \
    "$(has_line "$committed" ".aitask-scripts/newly_installed.sh")"
assert_eq "28c: rename source NOT committed" "no" "$(has_line "$committed" ".aitask-scripts/placeholder.sh")"
assert_eq "28c: rename destination NOT committed" "no" "$(has_line "$committed" ".aitask-scripts/renamed.sh")"
staged="$(git -C "$d" diff --cached --name-status --no-renames)"
assert_eq "28c: source deletion still staged" "yes" "$(has_line "$staged" "D	.aitask-scripts/placeholder.sh")"
assert_eq "28c: destination addition still staged" "yes" "$(has_line "$staged" "A	.aitask-scripts/renamed.sh")"
AIT_SETUP_BASELINE_ARMED=0
rm -rf "$d"

# Disarm the baseline for anything later; the sourced setup functions read these.
# shellcheck disable=SC2034
{
    AIT_SETUP_BASELINE_ARMED=0
    AIT_SETUP_DIRTY_BASELINE=""
    AIT_SETUP_DATA_DIRTY_BASELINE=""
}

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
