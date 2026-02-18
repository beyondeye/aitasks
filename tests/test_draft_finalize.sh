#!/bin/bash
# test_draft_finalize.sh - Automated tests for the draft + finalize workflow in aitask_create.sh
# Run: bash tests/test_draft_finalize.sh

set -e

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
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

assert_file_exists() {
    local desc="$1" filepath="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$filepath" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (file '$filepath' does not exist)"
    fi
}

assert_file_not_exists() {
    local desc="$1" filepath="$2"
    TOTAL=$((TOTAL + 1))
    if [[ ! -f "$filepath" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (file '$filepath' should not exist)"
    fi
}

assert_exit_zero() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (command exited non-zero)"
    fi
}

# Setup a git project with remote and aitask-ids branch initialized
setup_draft_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    # Create bare "remote" repo
    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet "$remote_dir"

    # Create local working repo
    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir"
    (
        cd "$local_dir"
        git config user.email "test@test.com"
        git config user.name "Test"

        # Create project structure
        mkdir -p aitasks/archived
        mkdir -p aitasks/metadata
        mkdir -p aitasks/new
        mkdir -p aiscripts/lib

        # Copy scripts
        cp "$PROJECT_DIR/aiscripts/aitask_create.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/aitask_claim_id.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/aitask_update.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/aitask_ls.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh" aiscripts/lib/
        chmod +x aiscripts/aitask_create.sh aiscripts/aitask_claim_id.sh aiscripts/aitask_update.sh aiscripts/aitask_ls.sh

        # Create task types file
        printf 'bug\nchore\ndocumentation\nfeature\nperformance\nrefactor\nstyle\ntest\n' > aitasks/metadata/task_types.txt

        # Add .gitignore for drafts
        echo "aitasks/new/" > .gitignore

        # Create a couple of existing tasks
        cat > aitasks/t1_first_task.md << 'TASK'
---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: []
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

First task
TASK
        cat > aitasks/t2_second_task.md << 'TASK'
---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: []
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Second task
TASK

        git add -A
        git commit -m "Initial setup" --quiet
        git push --quiet 2>/dev/null

        # Initialize the aitask-ids counter branch
        ./aiscripts/aitask_claim_id.sh --init >/dev/null 2>&1
    )

    echo "$tmpdir"
}

# Disable strict mode for test error handling
set +e

echo "=== aitask_create.sh Draft/Finalize Tests ==="
echo ""

# --- Test 1: Batch creates draft ---
echo "--- Test 1: Batch creates draft ---"

TMPDIR_1="$(setup_draft_project)"
output1=$(cd "$TMPDIR_1/local" && ./aiscripts/aitask_create.sh --batch --name "test_task" --desc "A test description" 2>&1)

# Check that a draft file was created in aitasks/new/
draft_files1=$(ls "$TMPDIR_1/local/aitasks/new"/draft_*_test_task.md 2>/dev/null | wc -l)
assert_eq "Draft file created in aitasks/new/" "1" "$draft_files1"

rm -rf "$TMPDIR_1"

# --- Test 2: Draft has correct format ---
echo "--- Test 2: Draft has correct format ---"

TMPDIR_2="$(setup_draft_project)"
(cd "$TMPDIR_2/local" && ./aiscripts/aitask_create.sh --batch --name "format_test" --desc "Test description" \
    --priority high --effort low --type bug --labels "ui,backend" >/dev/null 2>&1)

draft_file2=$(ls "$TMPDIR_2/local/aitasks/new"/draft_*_format_test.md 2>/dev/null | head -1)
assert_file_exists "Draft file exists" "$draft_file2"

# Check YAML content
draft_content2=$(cat "$draft_file2" 2>/dev/null)
assert_contains "Has draft: true" "draft: true" "$draft_content2"
assert_contains "Has priority: high" "priority: high" "$draft_content2"
assert_contains "Has effort: low" "effort: low" "$draft_content2"
assert_contains "Has issue_type: bug" "issue_type: bug" "$draft_content2"
assert_contains "Has labels" "ui, backend" "$draft_content2"

rm -rf "$TMPDIR_2"

# --- Test 3: Draft not in git ---
echo "--- Test 3: Draft not in git ---"

TMPDIR_3="$(setup_draft_project)"
(cd "$TMPDIR_3/local" && ./aiscripts/aitask_create.sh --batch --name "git_test" --desc "Not tracked" >/dev/null 2>&1)

# git status should NOT show aitasks/new/ (because it's gitignored)
git_status3=$(cd "$TMPDIR_3/local" && git status --porcelain 2>/dev/null)
TOTAL=$((TOTAL + 1))
if echo "$git_status3" | grep -q "aitasks/new/"; then
    FAIL=$((FAIL + 1))
    echo "FAIL: Draft not in git (aitasks/new/ shows in git status)"
else
    PASS=$((PASS + 1))
fi

rm -rf "$TMPDIR_3"

# --- Test 4: Finalize single draft ---
echo "--- Test 4: Finalize single draft ---"

TMPDIR_4="$(setup_draft_project)"
(cd "$TMPDIR_4/local" && ./aiscripts/aitask_create.sh --batch --name "finalize_me" --desc "Will be finalized" >/dev/null 2>&1)

draft_name4=$(ls "$TMPDIR_4/local/aitasks/new"/ 2>/dev/null | head -1)
(cd "$TMPDIR_4/local" && ./aiscripts/aitask_create.sh --batch --finalize "$draft_name4" >/dev/null 2>&1)

# Draft should be gone from aitasks/new/
draft_remaining4=$(ls "$TMPDIR_4/local/aitasks/new"/draft_*.md 2>/dev/null | wc -l)
assert_eq "Draft removed after finalize" "0" "$draft_remaining4"

# Task file should exist in aitasks/
final_files4=$(ls "$TMPDIR_4/local/aitasks"/t*_finalize_me.md 2>/dev/null | wc -l)
assert_eq "Finalized file in aitasks/" "1" "$final_files4"

# Check draft: true was removed
final_file4=$(ls "$TMPDIR_4/local/aitasks"/t*_finalize_me.md 2>/dev/null | head -1)
TOTAL=$((TOTAL + 1))
if grep -q "^draft: true$" "$final_file4" 2>/dev/null; then
    FAIL=$((FAIL + 1))
    echo "FAIL: draft: true should be removed from finalized file"
else
    PASS=$((PASS + 1))
fi

rm -rf "$TMPDIR_4"

# --- Test 5: Finalize claims real ID ---
echo "--- Test 5: Finalize claims real ID ---"

TMPDIR_5="$(setup_draft_project)"
# Counter should be at 12 (max(2) + 10 = 12)
(cd "$TMPDIR_5/local" && ./aiscripts/aitask_create.sh --batch --name "claim_test" --desc "Test claiming" >/dev/null 2>&1)

draft_name5=$(ls "$TMPDIR_5/local/aitasks/new"/ 2>/dev/null | head -1)
(cd "$TMPDIR_5/local" && ./aiscripts/aitask_create.sh --batch --finalize "$draft_name5" >/dev/null 2>&1)

# The finalized file should be t12_claim_test.md (first claim from counter starting at 12)
assert_file_exists "Finalized as t12" "$TMPDIR_5/local/aitasks/t12_claim_test.md"

rm -rf "$TMPDIR_5"

# --- Test 6: Finalize commits to git ---
echo "--- Test 6: Finalize commits to git ---"

TMPDIR_6="$(setup_draft_project)"
(cd "$TMPDIR_6/local" && ./aiscripts/aitask_create.sh --batch --name "commit_test" --desc "Will be committed" >/dev/null 2>&1)

draft_name6=$(ls "$TMPDIR_6/local/aitasks/new"/ 2>/dev/null | head -1)
(cd "$TMPDIR_6/local" && ./aiscripts/aitask_create.sh --batch --finalize "$draft_name6" >/dev/null 2>&1)

# Check that git log shows the commit
last_commit6=$(cd "$TMPDIR_6/local" && git log -1 --format='%s' 2>/dev/null)
assert_contains "Commit message has task ID" "t12" "$last_commit6"
assert_contains "Commit message mentions task" "commit test" "$last_commit6"

rm -rf "$TMPDIR_6"

# --- Test 7: Finalize-all ---
echo "--- Test 7: Finalize-all ---"

TMPDIR_7="$(setup_draft_project)"
(cd "$TMPDIR_7/local" && ./aiscripts/aitask_create.sh --batch --name "draft_a" --desc "Draft A" >/dev/null 2>&1)
sleep 1  # Ensure different timestamps
(cd "$TMPDIR_7/local" && ./aiscripts/aitask_create.sh --batch --name "draft_b" --desc "Draft B" >/dev/null 2>&1)
sleep 1
(cd "$TMPDIR_7/local" && ./aiscripts/aitask_create.sh --batch --name "draft_c" --desc "Draft C" >/dev/null 2>&1)

# All should be drafts
draft_count7_before=$(ls "$TMPDIR_7/local/aitasks/new"/draft_*.md 2>/dev/null | wc -l)
assert_eq "3 drafts created" "3" "$draft_count7_before"

# Finalize all
(cd "$TMPDIR_7/local" && ./aiscripts/aitask_create.sh --batch --finalize-all >/dev/null 2>&1)

# Drafts should be gone
draft_count7_after=$(ls "$TMPDIR_7/local/aitasks/new"/draft_*.md 2>/dev/null | wc -l)
assert_eq "No drafts remaining" "0" "$draft_count7_after"

# 3 new task files should exist (t12, t13, t14)
new_task_count7=$(ls "$TMPDIR_7/local/aitasks"/t1[234]_*.md 2>/dev/null | wc -l)
assert_eq "3 finalized tasks exist" "3" "$new_task_count7"

# All should have unique IDs
ids7=$(ls "$TMPDIR_7/local/aitasks"/t*_*.md 2>/dev/null | grep -oE 't[0-9]+' | sort -u | wc -l)
total_tasks7=$(ls "$TMPDIR_7/local/aitasks"/t*_*.md 2>/dev/null | wc -l)
assert_eq "All task IDs are unique" "$total_tasks7" "$ids7"

rm -rf "$TMPDIR_7"

# --- Test 8: Batch --commit auto-finalizes ---
echo "--- Test 8: Batch --commit auto-finalizes ---"

TMPDIR_8="$(setup_draft_project)"
output8=$(cd "$TMPDIR_8/local" && ./aiscripts/aitask_create.sh --batch --name "auto_final" --desc "Auto finalized" --commit 2>&1)

# Should NOT create a draft
draft_count8=$(ls "$TMPDIR_8/local/aitasks/new"/draft_*.md 2>/dev/null | wc -l)
assert_eq "No draft created with --commit" "0" "$draft_count8"

# Should create task directly in aitasks/
final_count8=$(ls "$TMPDIR_8/local/aitasks"/t*_auto_final.md 2>/dev/null | wc -l)
assert_eq "Task created directly in aitasks/" "1" "$final_count8"

# Should be committed
git_clean8=$(cd "$TMPDIR_8/local" && git status --porcelain 2>/dev/null)
TOTAL=$((TOTAL + 1))
if [[ -z "$git_clean8" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Working tree not clean after --commit (got: '$git_clean8')"
fi

rm -rf "$TMPDIR_8"

# --- Test 9: Child task draft ---
echo "--- Test 9: Child task draft ---"

TMPDIR_9="$(setup_draft_project)"
(cd "$TMPDIR_9/local" && ./aiscripts/aitask_create.sh --batch --parent 1 --name "child_task" --desc "A child task" >/dev/null 2>&1)

# Draft should exist in aitasks/new/
draft_count9=$(ls "$TMPDIR_9/local/aitasks/new"/draft_*_child_task.md 2>/dev/null | wc -l)
assert_eq "Child draft created" "1" "$draft_count9"

# Draft should have parent field
draft_file9=$(ls "$TMPDIR_9/local/aitasks/new"/draft_*_child_task.md 2>/dev/null | head -1)
draft_content9=$(cat "$draft_file9" 2>/dev/null)
assert_contains "Draft has parent field" "parent: 1" "$draft_content9"
assert_contains "Draft has draft: true" "draft: true" "$draft_content9"

rm -rf "$TMPDIR_9"

# --- Test 10: Child task finalize ---
echo "--- Test 10: Child task finalize ---"

TMPDIR_10="$(setup_draft_project)"
(cd "$TMPDIR_10/local" && ./aiscripts/aitask_create.sh --batch --parent 1 --name "child_fin" --desc "A child to finalize" >/dev/null 2>&1)

draft_name10=$(ls "$TMPDIR_10/local/aitasks/new"/ 2>/dev/null | head -1)
(cd "$TMPDIR_10/local" && ./aiscripts/aitask_create.sh --batch --finalize "$draft_name10" >/dev/null 2>&1)

# Child should be in aitasks/t1/
child_files10=$(ls "$TMPDIR_10/local/aitasks/t1"/t1_*_child_fin.md 2>/dev/null | wc -l)
assert_eq "Child task finalized to aitasks/t1/" "1" "$child_files10"

# Draft should be gone
draft_remaining10=$(ls "$TMPDIR_10/local/aitasks/new"/draft_*.md 2>/dev/null | wc -l)
assert_eq "Draft removed after child finalize" "0" "$draft_remaining10"

# Parent file should have children_to_implement updated
parent_content10=$(cat "$TMPDIR_10/local/aitasks/t1_first_task.md" 2>/dev/null)
assert_contains "Parent updated with child ref" "t1_1" "$parent_content10"

rm -rf "$TMPDIR_10"

# --- Test 11: Finalize without network fails in batch mode ---
echo "--- Test 11: Finalize without network fails in batch mode ---"

TMPDIR_11="$(setup_draft_project)"
(cd "$TMPDIR_11/local" && ./aiscripts/aitask_create.sh --batch --name "no_net" --desc "No network test" >/dev/null 2>&1)

# Remove the remote to simulate no network
(cd "$TMPDIR_11/local" && git remote remove origin)

draft_name11=$(ls "$TMPDIR_11/local/aitasks/new"/ 2>/dev/null | head -1)

# Finalize should FAIL (no silent fallback in non-interactive mode)
output11=$(cd "$TMPDIR_11/local" && ./aiscripts/aitask_create.sh --batch --finalize "$draft_name11" 2>&1)
exit_code11=$?

assert_eq "Finalize fails without network" "1" "$exit_code11"
assert_contains "Error mentions ait setup" "ait setup" "$output11"

# Draft should still exist (finalization failed)
draft_remaining11=$(ls "$TMPDIR_11/local/aitasks/new"/draft_*.md 2>/dev/null | wc -l)
assert_eq "Draft preserved on failure" "1" "$draft_remaining11"

rm -rf "$TMPDIR_11"

# --- Test 12: Multiple drafts coexist ---
echo "--- Test 12: Multiple drafts coexist ---"

TMPDIR_12="$(setup_draft_project)"
(cd "$TMPDIR_12/local" && ./aiscripts/aitask_create.sh --batch --name "multi_a" --desc "Draft A" >/dev/null 2>&1)
sleep 1
(cd "$TMPDIR_12/local" && ./aiscripts/aitask_create.sh --batch --name "multi_b" --desc "Draft B" >/dev/null 2>&1)
sleep 1
(cd "$TMPDIR_12/local" && ./aiscripts/aitask_create.sh --batch --name "multi_c" --desc "Draft C" >/dev/null 2>&1)

draft_count12=$(ls "$TMPDIR_12/local/aitasks/new"/draft_*.md 2>/dev/null | wc -l)
assert_eq "3 drafts coexist" "3" "$draft_count12"

# Each has a different name suffix
for name in multi_a multi_b multi_c; do
    count=$(ls "$TMPDIR_12/local/aitasks/new"/draft_*_${name}.md 2>/dev/null | wc -l)
    assert_eq "Draft $name exists" "1" "$count"
done

rm -rf "$TMPDIR_12"

# --- Test 13: Syntax check ---
echo "--- Test 13: Syntax check ---"

assert_exit_zero "Syntax check passes" bash -n "$PROJECT_DIR/aiscripts/aitask_create.sh"

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
