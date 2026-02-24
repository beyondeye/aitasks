#!/usr/bin/env bash
# test_web_merge.sh - Automated tests for aitask_web_merge.sh
# Run: bash tests/test_web_merge.sh

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

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qi "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (output should NOT contain '$unexpected', got '$actual')"
    else
        PASS=$((PASS + 1))
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

# --- Setup helpers ---

# Create a paired repo setup: bare "remote" + local clone
setup_paired_repos() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    # Create bare "remote" repo with main as default branch
    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet -b main "$remote_dir"

    # Create local working repo
    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir" 2>/dev/null
    (
        cd "$local_dir"
        git config user.email "test@test.com"
        git config user.name "Test"
        git checkout -b main --quiet 2>/dev/null || true

        # Copy required scripts
        mkdir -p aiscripts/lib
        cp "$PROJECT_DIR/aiscripts/aitask_web_merge.sh" aiscripts/
        cp "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh" aiscripts/lib/
        chmod +x aiscripts/aitask_web_merge.sh

        # Initial commit
        echo "init" > README.md
        git add -A
        git commit -m "Initial setup" --quiet
        git push -u origin main --quiet 2>/dev/null
    )

    echo "$tmpdir"
}

# Create a fake completed web branch with a completion marker
create_web_branch() {
    local repo_dir="$1" branch_name="$2" task_id="$3" task_file="$4"
    local is_child="${5:-false}"
    local parent_id="${6:-null}"
    (
        cd "$repo_dir"
        git checkout -b "$branch_name" --quiet
        mkdir -p .aitask-data-updated

        # Write completion marker JSON
        if [[ "$parent_id" == "null" ]]; then
            local parent_json="null"
        else
            local parent_json="\"$parent_id\""
        fi
        cat > ".aitask-data-updated/completed_t${task_id}.json" <<EOF
{
  "task_id": "$task_id",
  "task_file": "$task_file",
  "plan_file": ".aitask-data-updated/plan_t${task_id}.md",
  "is_child": $is_child,
  "parent_id": $parent_json,
  "issue_type": "feature",
  "completed_at": "2026-02-24 15:30",
  "branch": "$branch_name"
}
EOF
        echo "# Plan for t${task_id}" > ".aitask-data-updated/plan_t${task_id}.md"
        echo "implementation code" > "impl_${task_id}.txt"
        git add -A
        git commit -m "feature: Implement t${task_id}" --quiet
        git push origin "$branch_name" --quiet 2>/dev/null
        git checkout main --quiet
    )
}

# Create a branch without completion markers
create_plain_branch() {
    local repo_dir="$1" branch_name="$2"
    (
        cd "$repo_dir"
        git checkout -b "$branch_name" --quiet
        echo "some work" > work.txt
        git add -A
        git commit -m "some work" --quiet
        git push origin "$branch_name" --quiet 2>/dev/null
        git checkout main --quiet
    )
}

set +e

echo "=== aitask_web_merge.sh Tests ==="
echo ""

# --- Test 1: No completed branches ---
echo "--- Test 1: No completed branches ---"
TMPDIR_1="$(setup_paired_repos)"
output=$(cd "$TMPDIR_1/local" && ./aiscripts/aitask_web_merge.sh 2>&1)
assert_eq "No branches returns NONE" "NONE" "$output"
rm -rf "$TMPDIR_1"

# --- Test 2: Single completed branch ---
echo "--- Test 2: Single completed branch ---"
TMPDIR_2="$(setup_paired_repos)"
create_web_branch "$TMPDIR_2/local" "claude-web/t42" "42" "aitasks/t42_implement_auth.md"
output=$(cd "$TMPDIR_2/local" && ./aiscripts/aitask_web_merge.sh 2>&1)
assert_contains "Detects completed branch" "COMPLETED:claude-web/t42:completed_t42.json" "$output"
rm -rf "$TMPDIR_2"

# --- Test 3: Multiple completed branches ---
echo "--- Test 3: Multiple completed branches ---"
TMPDIR_3="$(setup_paired_repos)"
create_web_branch "$TMPDIR_3/local" "claude-web/t42" "42" "aitasks/t42_implement_auth.md"
create_web_branch "$TMPDIR_3/local" "claude-web/t50" "50" "aitasks/t50_add_logging.md"
output=$(cd "$TMPDIR_3/local" && ./aiscripts/aitask_web_merge.sh 2>&1)
assert_contains "Detects first branch" "COMPLETED:claude-web/t42:completed_t42.json" "$output"
assert_contains "Detects second branch" "COMPLETED:claude-web/t50:completed_t50.json" "$output"
# Count COMPLETED lines
count=$(echo "$output" | grep -c "^COMPLETED:" | tr -d ' ')
assert_eq "Exactly 2 completions found" "2" "$count"
rm -rf "$TMPDIR_3"

# --- Test 4: Branch without marker is not detected ---
echo "--- Test 4: Branch without marker not detected ---"
TMPDIR_4="$(setup_paired_repos)"
create_plain_branch "$TMPDIR_4/local" "feature/no-marker"
create_web_branch "$TMPDIR_4/local" "claude-web/t42" "42" "aitasks/t42_implement_auth.md"
output=$(cd "$TMPDIR_4/local" && ./aiscripts/aitask_web_merge.sh 2>&1)
assert_contains "Detects web branch" "COMPLETED:claude-web/t42" "$output"
assert_not_contains "Does not detect plain branch" "feature/no-marker" "$output"
rm -rf "$TMPDIR_4"

# --- Test 5: Known branches skipped ---
echo "--- Test 5: Known branches are skipped ---"
TMPDIR_5="$(setup_paired_repos)"
# Create an aitask-data branch (which normally exists in the project)
(
    cd "$TMPDIR_5/local"
    git checkout -b aitask-data --quiet
    mkdir -p .aitask-data-updated
    echo '{"task_id":"99"}' > .aitask-data-updated/completed_t99.json
    git add -A
    git commit -m "fake marker on infra branch" --quiet
    git push origin aitask-data --quiet 2>/dev/null
    git checkout main --quiet
)
output=$(cd "$TMPDIR_5/local" && ./aiscripts/aitask_web_merge.sh 2>&1)
assert_eq "Infrastructure branch skipped" "NONE" "$output"
rm -rf "$TMPDIR_5"

# --- Test 6: --fetch flag works ---
echo "--- Test 6: --fetch flag works ---"
TMPDIR_6="$(setup_paired_repos)"
create_web_branch "$TMPDIR_6/local" "claude-web/t42" "42" "aitasks/t42_implement_auth.md"
output=$(cd "$TMPDIR_6/local" && ./aiscripts/aitask_web_merge.sh --fetch 2>&1)
assert_contains "Fetch flag detects branch" "COMPLETED:claude-web/t42:completed_t42.json" "$output"
rm -rf "$TMPDIR_6"

# --- Test 7: Child task marker ---
echo "--- Test 7: Child task marker detected ---"
TMPDIR_7="$(setup_paired_repos)"
create_web_branch "$TMPDIR_7/local" "claude-web/t10_2" "10_2" "aitasks/t10/t10_2_add_login.md" "true" "10"
output=$(cd "$TMPDIR_7/local" && ./aiscripts/aitask_web_merge.sh 2>&1)
assert_contains "Detects child task branch" "COMPLETED:claude-web/t10_2:completed_t10_2.json" "$output"
rm -rf "$TMPDIR_7"

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
