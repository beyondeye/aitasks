#!/usr/bin/env bash
# test_pr_contributor_metadata.sh - Tests for pull_request, contributor, contributor_email metadata fields
# Run: bash tests/test_pr_contributor_metadata.sh

set -e

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
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

assert_not_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qi "$expected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (output should NOT contain '$expected')"
    else
        PASS=$((PASS + 1))
    fi
}

# Setup a git project with remote and aitask-ids branch initialized
setup_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet "$remote_dir"

    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir"
    (
        cd "$local_dir"
        git config user.email "test@test.com"
        git config user.name "Test"

        mkdir -p aitasks/archived aitasks/metadata aitasks/new aiscripts/lib

        cp "$PROJECT_DIR/aiscripts/aitask_create.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/aitask_claim_id.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/aitask_update.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/aitask_ls.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh" aiscripts/lib/
        cp "$PROJECT_DIR/aiscripts/lib/task_utils.sh" aiscripts/lib/
        chmod +x aiscripts/aitask_create.sh aiscripts/aitask_claim_id.sh aiscripts/aitask_update.sh aiscripts/aitask_ls.sh

        printf 'bug\nchore\ndocumentation\nfeature\nperformance\nrefactor\nstyle\ntest\n' > aitasks/metadata/task_types.txt
        echo "aitasks/new/" > .gitignore

        git add -A
        git commit -m "Initial setup" --quiet
        git push --quiet 2>/dev/null

        ./aiscripts/aitask_claim_id.sh --init >/dev/null 2>&1
    )

    echo "$tmpdir"
}

# Disable strict mode for test error handling
set +e

echo "=== PR/Contributor Metadata Field Tests ==="
echo ""

# --- Test 1: Create draft with all three new fields ---
echo "--- Test 1: Create draft with PR metadata ---"
TMPDIR_1="$(setup_project)"

(cd "$TMPDIR_1/local" && echo "PR task desc" | bash aiscripts/aitask_create.sh --batch --name "pr_test" \
    --pull-request "https://github.com/owner/repo/pull/42" \
    --contributor "octocat" \
    --contributor-email "12345+octocat@users.noreply.github.com" \
    --desc-file - >/dev/null 2>&1)

draft_file_1=$(ls "$TMPDIR_1/local/aitasks/new"/draft_*_pr_test.md 2>/dev/null | head -1)
content_1=$(cat "$draft_file_1" 2>/dev/null)
assert_contains "pull_request in YAML" "pull_request: https://github.com/owner/repo/pull/42" "$content_1"
assert_contains "contributor in YAML" "contributor: octocat" "$content_1"
assert_contains "contributor_email in YAML" "contributor_email: 12345+octocat@users.noreply.github.com" "$content_1"

rm -rf "$TMPDIR_1"

# --- Test 2: Create and finalize with PR metadata ---
echo "--- Test 2: Create+commit with PR metadata ---"
TMPDIR_2="$(setup_project)"

(cd "$TMPDIR_2/local" && echo "PR task desc" | bash aiscripts/aitask_create.sh --batch --name "pr_committed" \
    --pull-request "https://github.com/owner/repo/pull/99" \
    --contributor "contributor1" \
    --contributor-email "789+contributor1@users.noreply.github.com" \
    --desc-file - --commit >/dev/null 2>&1)

task_file_2=$(ls "$TMPDIR_2/local/aitasks"/t*_pr_committed.md 2>/dev/null | head -1)
content_2=$(cat "$task_file_2" 2>/dev/null)
assert_contains "pull_request in committed task" "pull_request: https://github.com/owner/repo/pull/99" "$content_2"
assert_contains "contributor in committed task" "contributor: contributor1" "$content_2"
assert_contains "contributor_email in committed task" "contributor_email: 789+contributor1@users.noreply.github.com" "$content_2"

rm -rf "$TMPDIR_2"

# --- Test 3: No PR fields when not specified ---
echo "--- Test 3: No PR fields when not specified ---"
TMPDIR_3="$(setup_project)"

(cd "$TMPDIR_3/local" && echo "Normal task" | bash aiscripts/aitask_create.sh --batch --name "no_pr" --desc-file - >/dev/null 2>&1)

draft_file_3=$(ls "$TMPDIR_3/local/aitasks/new"/draft_*_no_pr.md 2>/dev/null | head -1)
content_3=$(cat "$draft_file_3" 2>/dev/null)
assert_not_contains "No pull_request field" "pull_request:" "$content_3"
assert_not_contains "No contributor field" "^contributor:" "$content_3"
assert_not_contains "No contributor_email field" "contributor_email:" "$content_3"

rm -rf "$TMPDIR_3"

# --- Test 4: Update task with new PR fields ---
echo "--- Test 4: Update task with PR fields ---"
TMPDIR_4="$(setup_project)"

(cd "$TMPDIR_4/local" && echo "Test task" | bash aiscripts/aitask_create.sh --batch --name "update_pr_test" --desc-file - --commit >/dev/null 2>&1)

task_file_4=$(ls "$TMPDIR_4/local/aitasks"/t*_update_pr_test.md 2>/dev/null | head -1)
task_num_4=$(basename "$task_file_4" | sed 's/^t\([0-9]*\)_.*/\1/')

(cd "$TMPDIR_4/local" && bash aiscripts/aitask_update.sh --batch "$task_num_4" \
    --pull-request "https://gitlab.com/group/project/-/merge_requests/5" \
    --contributor "gitlab_user" \
    --contributor-email "gitlab_user@example.com" --silent >/dev/null 2>&1)

content_4=$(cat "$task_file_4" 2>/dev/null)
assert_contains "pull_request after update" "pull_request: https://gitlab.com/group/project/-/merge_requests/5" "$content_4"
assert_contains "contributor after update" "contributor: gitlab_user" "$content_4"
assert_contains "contributor_email after update" "contributor_email: gitlab_user@example.com" "$content_4"

rm -rf "$TMPDIR_4"

# --- Test 5: Update preserves existing PR fields when updating other fields ---
echo "--- Test 5: Update preserves PR fields ---"
TMPDIR_5="$(setup_project)"

(cd "$TMPDIR_5/local" && echo "Test task" | bash aiscripts/aitask_create.sh --batch --name "preserve_pr" \
    --pull-request "https://github.com/o/r/pull/1" \
    --contributor "user1" \
    --desc-file - --commit >/dev/null 2>&1)

task_file_5=$(ls "$TMPDIR_5/local/aitasks"/t*_preserve_pr.md 2>/dev/null | head -1)
task_num_5=$(basename "$task_file_5" | sed 's/^t\([0-9]*\)_.*/\1/')

# Update priority only - PR fields should be preserved
(cd "$TMPDIR_5/local" && bash aiscripts/aitask_update.sh --batch "$task_num_5" --priority high --silent >/dev/null 2>&1)

content_5=$(cat "$task_file_5" 2>/dev/null)
assert_contains "PR preserved after priority update" "pull_request: https://github.com/o/r/pull/1" "$content_5"
assert_contains "Contributor preserved after priority update" "contributor: user1" "$content_5"

rm -rf "$TMPDIR_5"

# --- Test 6: Clear PR field by updating with empty string ---
echo "--- Test 6: Clear PR field with empty string ---"
TMPDIR_6="$(setup_project)"

(cd "$TMPDIR_6/local" && echo "Test task" | bash aiscripts/aitask_create.sh --batch --name "clear_pr" \
    --pull-request "https://github.com/o/r/pull/1" \
    --contributor "user1" \
    --desc-file - --commit >/dev/null 2>&1)

task_file_6=$(ls "$TMPDIR_6/local/aitasks"/t*_clear_pr.md 2>/dev/null | head -1)
task_num_6=$(basename "$task_file_6" | sed 's/^t\([0-9]*\)_.*/\1/')

# Clear pull_request by setting empty
(cd "$TMPDIR_6/local" && bash aiscripts/aitask_update.sh --batch "$task_num_6" --pull-request "" --silent >/dev/null 2>&1)

content_6=$(cat "$task_file_6" 2>/dev/null)
assert_not_contains "PR cleared" "pull_request:" "$content_6"
assert_contains "Contributor still present" "contributor: user1" "$content_6"

rm -rf "$TMPDIR_6"

# --- Test 7: Extraction functions ---
echo "--- Test 7: Extraction functions ---"
TMPDIR_7="$(setup_project)"

tmpfile_7=$(mktemp)
cat > "$tmpfile_7" << 'EOF'
---
priority: high
issue: https://github.com/o/r/issues/10
pull_request: https://github.com/owner/repo/pull/42
contributor: octocat
contributor_email: 12345+octocat@users.noreply.github.com
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Description here
EOF

pr_7=$(cd "$TMPDIR_7/local" && unset SCRIPT_DIR && source aiscripts/lib/task_utils.sh && extract_pr_url "$tmpfile_7")
contrib_7=$(cd "$TMPDIR_7/local" && unset SCRIPT_DIR && source aiscripts/lib/task_utils.sh && extract_contributor "$tmpfile_7")
email_7=$(cd "$TMPDIR_7/local" && unset SCRIPT_DIR && source aiscripts/lib/task_utils.sh && extract_contributor_email "$tmpfile_7")

assert_eq "extract_pr_url" "https://github.com/owner/repo/pull/42" "$pr_7"
assert_eq "extract_contributor" "octocat" "$contrib_7"
assert_eq "extract_contributor_email" "12345+octocat@users.noreply.github.com" "$email_7"

rm -f "$tmpfile_7"
rm -rf "$TMPDIR_7"

# --- Test 8: Extraction functions return empty for missing fields ---
echo "--- Test 8: Extraction returns empty for missing fields ---"
TMPDIR_8="$(setup_project)"

tmpfile_8=$(mktemp)
cat > "$tmpfile_8" << 'EOF'
---
priority: medium
status: Ready
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

No PR fields
EOF

pr_8=$(cd "$TMPDIR_8/local" && unset SCRIPT_DIR && source aiscripts/lib/task_utils.sh && extract_pr_url "$tmpfile_8")
contrib_8=$(cd "$TMPDIR_8/local" && unset SCRIPT_DIR && source aiscripts/lib/task_utils.sh && extract_contributor "$tmpfile_8")
email_8=$(cd "$TMPDIR_8/local" && unset SCRIPT_DIR && source aiscripts/lib/task_utils.sh && extract_contributor_email "$tmpfile_8")

assert_eq "extract_pr_url empty" "" "$pr_8"
assert_eq "extract_contributor empty" "" "$contrib_8"
assert_eq "extract_contributor_email empty" "" "$email_8"

rm -f "$tmpfile_8"
rm -rf "$TMPDIR_8"

# --- Test 9: Child task with PR metadata ---
echo "--- Test 9: Child task with PR metadata ---"
TMPDIR_9="$(setup_project)"

(cd "$TMPDIR_9/local" && echo "Parent task" | bash aiscripts/aitask_create.sh --batch --name "parent_pr" --desc-file - --commit >/dev/null 2>&1)
parent_file_9=$(ls "$TMPDIR_9/local/aitasks"/t*_parent_pr.md 2>/dev/null | head -1)
parent_num_9=$(basename "$parent_file_9" | sed 's/^t\([0-9]*\)_.*/\1/')

(cd "$TMPDIR_9/local" && echo "Child from PR" | bash aiscripts/aitask_create.sh --batch --name "child_pr" \
    --parent "$parent_num_9" \
    --pull-request "https://github.com/o/r/pull/55" \
    --contributor "ext_user" \
    --contributor-email "ext@users.noreply.github.com" \
    --desc-file - --commit >/dev/null 2>&1)

child_file_9=$(ls "$TMPDIR_9/local/aitasks/t${parent_num_9}"/t${parent_num_9}_*_child_pr.md 2>/dev/null | head -1)
content_9=$(cat "$child_file_9" 2>/dev/null)
assert_contains "child pull_request" "pull_request: https://github.com/o/r/pull/55" "$content_9"
assert_contains "child contributor" "contributor: ext_user" "$content_9"
assert_contains "child contributor_email" "contributor_email: ext@users.noreply.github.com" "$content_9"

rm -rf "$TMPDIR_9"

# --- Test 10: ls -v shows PR and contributor ---
echo "--- Test 10: ls -v shows PR and contributor ---"
TMPDIR_10="$(setup_project)"

(cd "$TMPDIR_10/local" && echo "PR visible task" | bash aiscripts/aitask_create.sh --batch --name "ls_pr_test" \
    --pull-request "https://github.com/o/r/pull/77" \
    --contributor "visible_user" \
    --desc-file - --commit >/dev/null 2>&1)

output_10=$(cd "$TMPDIR_10/local" && bash aiscripts/aitask_ls.sh -v 99 2>&1)
assert_contains "ls shows PR" "PR: https://github.com/o/r/pull/77" "$output_10"
assert_contains "ls shows Contributor" "Contributor: visible_user" "$output_10"

rm -rf "$TMPDIR_10"

# --- Test 11: ls -v hides PR fields when not set ---
echo "--- Test 11: ls -v hides PR fields when not set ---"
TMPDIR_11="$(setup_project)"

(cd "$TMPDIR_11/local" && echo "Normal task" | bash aiscripts/aitask_create.sh --batch --name "ls_no_pr" --desc-file - --commit >/dev/null 2>&1)

output_11=$(cd "$TMPDIR_11/local" && bash aiscripts/aitask_ls.sh -v 99 2>&1)
assert_not_contains "no PR in output" "PR:" "$output_11"
assert_not_contains "no Contributor in output" "Contributor:" "$output_11"

rm -rf "$TMPDIR_11"

# --- Test 12: Syntax check ---
echo "--- Test 12: Syntax check ---"
TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/aiscripts/aitask_create.sh" 2>/dev/null &&
   bash -n "$PROJECT_DIR/aiscripts/aitask_update.sh" 2>/dev/null &&
   bash -n "$PROJECT_DIR/aiscripts/aitask_ls.sh" 2>/dev/null &&
   bash -n "$PROJECT_DIR/aiscripts/lib/task_utils.sh" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Syntax check failed"
fi

# --- Summary ---
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
