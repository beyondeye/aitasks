#!/usr/bin/env bash
# test_zip_old.sh - Automated tests for aitask_zip_old.sh
# Run: bash tests/test_zip_old.sh

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
        echo "FAIL: $desc (output should NOT contain '$unexpected', but it does)"
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

assert_file_not_exists() {
    local desc="$1" file="$2"
    TOTAL=$((TOTAL + 1))
    if [[ ! -f "$file" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (file '$file' should not exist but does)"
    fi
}

assert_dir_not_exists() {
    local desc="$1" dir="$2"
    TOTAL=$((TOTAL + 1))
    if [[ ! -d "$dir" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (directory '$dir' should not exist but does)"
    fi
}

# Create a mock task file with frontmatter
create_task_file() {
    local path="$1"
    local depends="${2:-[]}"
    mkdir -p "$(dirname "$path")"
    cat > "$path" << EOF
---
priority: medium
effort: medium
depends: $depends
status: Ready
---
Task content for $(basename "$path")
EOF
}

# Create a minimal mock task file (for archived files)
create_archived_file() {
    local path="$1"
    mkdir -p "$(dirname "$path")"
    echo "Archived content for $(basename "$path")" > "$path"
}

# Setup a test environment with git repo
setup_test_env() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    # Create a git repo so git operations work
    (
        cd "$tmpdir"
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"

        # Create required directories
        mkdir -p aitasks/archived
        mkdir -p aiplans/archived

        # Copy the script and its dependencies
        mkdir -p .aitask-scripts/lib
        cp "$PROJECT_DIR/.aitask-scripts/aitask_zip_old.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/

        # Initial commit
        git add -A
        git commit -m "Initial setup" --quiet
    )

    echo "$tmpdir"
}

echo "=== Testing aitask_zip_old.sh ==="
echo ""

# --- Test 1: Syntax check ---
echo "--- Test 1: Syntax check ---"
assert_exit_zero "Syntax check passes" bash -n "$PROJECT_DIR/.aitask-scripts/aitask_zip_old.sh"

# --- Test 2: Empty archived dirs — nothing to do ---
echo "--- Test 2: Empty archived dirs ---"
TMPDIR_2="$(setup_test_env)"
output_2=$(cd "$TMPDIR_2" && bash .aitask-scripts/aitask_zip_old.sh --dry-run 2>&1)
assert_contains "Empty dirs: reports no files" "no files to archive" "$output_2"
rm -rf "$TMPDIR_2"

# --- Test 3: All parent tasks archived, no active children — all get archived ---
echo "--- Test 3: All parents archived, no active children ---"
TMPDIR_3="$(setup_test_env)"
(
    cd "$TMPDIR_3"
    create_archived_file aitasks/archived/t50_old_task.md
    create_archived_file aitasks/archived/t51_another_task.md
    create_archived_file aiplans/archived/p50_old_task.md
    create_archived_file aiplans/archived/p51_another_task.md
)
output_3=$(cd "$TMPDIR_3" && bash .aitask-scripts/aitask_zip_old.sh --dry-run 2>&1)
assert_contains "Test 3: t50 listed" "t50_old_task.md" "$output_3"
assert_contains "Test 3: t51 listed" "t51_another_task.md" "$output_3"
assert_contains "Test 3: p50 listed" "p50_old_task.md" "$output_3"
assert_contains "Test 3: p51 listed" "p51_another_task.md" "$output_3"
rm -rf "$TMPDIR_3"

# --- Test 4: Active parent skips its archived children ---
echo "--- Test 4: Active parent skips archived children ---"
TMPDIR_4="$(setup_test_env)"
(
    cd "$TMPDIR_4"
    # Active parent with children
    create_task_file aitasks/t10_parent.md
    create_task_file aitasks/t10/t10_3_active_child.md
    # Archived children of active parent
    create_archived_file aitasks/archived/t10/t10_1_done_child.md
    create_archived_file aitasks/archived/t10/t10_2_done_child.md
    create_archived_file aiplans/archived/p10/p10_1_done_child.md
    create_archived_file aiplans/archived/p10/p10_2_done_child.md
    # Also add an unrelated archived file that SHOULD be archived
    create_archived_file aitasks/archived/t5_unrelated.md
)
output_4=$(cd "$TMPDIR_4" && bash .aitask-scripts/aitask_zip_old.sh --dry-run 2>&1)
assert_not_contains "Test 4: t10_1 NOT listed" "t10_1_done_child" "$output_4"
assert_not_contains "Test 4: t10_2 NOT listed" "t10_2_done_child" "$output_4"
assert_not_contains "Test 4: p10_1 NOT listed" "p10_1_done_child" "$output_4"
assert_not_contains "Test 4: p10_2 NOT listed" "p10_2_done_child" "$output_4"
assert_contains "Test 4: t5 IS listed" "t5_unrelated" "$output_4"
rm -rf "$TMPDIR_4"

# --- Test 5: Archived parent with all children done gets archived ---
echo "--- Test 5: Archived parent, all children done ---"
TMPDIR_5="$(setup_test_env)"
(
    cd "$TMPDIR_5"
    # Parent is archived (no aitasks/t20/ directory)
    create_archived_file aitasks/archived/t20_done_parent.md
    create_archived_file aitasks/archived/t20/t20_1_child.md
    create_archived_file aitasks/archived/t20/t20_2_child.md
)
output_5=$(cd "$TMPDIR_5" && bash .aitask-scripts/aitask_zip_old.sh --dry-run 2>&1)
assert_contains "Test 5: parent listed" "t20_done_parent" "$output_5"
assert_contains "Test 5: child 1 listed" "t20_1_child" "$output_5"
assert_contains "Test 5: child 2 listed" "t20_2_child" "$output_5"
rm -rf "$TMPDIR_5"

# --- Test 6: Inactive parent's children get archived ---
echo "--- Test 6: Inactive parent's children archived ---"
TMPDIR_6="$(setup_test_env)"
(
    cd "$TMPDIR_6"
    # No aitasks/t30/ directory (parent is done)
    create_archived_file aitasks/archived/t30/t30_1_child.md
    create_archived_file aitasks/archived/t30/t30_2_child.md
)
output_6=$(cd "$TMPDIR_6" && bash .aitask-scripts/aitask_zip_old.sh --dry-run 2>&1)
assert_contains "Test 6: child 1 listed" "t30_1_child" "$output_6"
assert_contains "Test 6: child 2 listed" "t30_2_child" "$output_6"
rm -rf "$TMPDIR_6"

# --- Test 7: Plan files follow same logic ---
echo "--- Test 7: Plan files follow same logic ---"
TMPDIR_7="$(setup_test_env)"
(
    cd "$TMPDIR_7"
    # Active parent
    create_task_file aitasks/t15_parent.md
    create_task_file aitasks/t15/t15_2_active.md
    # Archived plan children of active parent
    create_archived_file aiplans/archived/p15/p15_1_done.md
    # Archived plan of inactive parent
    create_archived_file aiplans/archived/p40/p40_1_done.md
)
output_7=$(cd "$TMPDIR_7" && bash .aitask-scripts/aitask_zip_old.sh --dry-run 2>&1)
assert_not_contains "Test 7: p15_1 NOT listed" "p15_1_done" "$output_7"
assert_contains "Test 7: p40_1 IS listed" "p40_1_done" "$output_7"
rm -rf "$TMPDIR_7"

# --- Test 8: Mixed scenario ---
echo "--- Test 8: Mixed scenario ---"
TMPDIR_8="$(setup_test_env)"
(
    cd "$TMPDIR_8"
    # Active parent with children
    create_task_file aitasks/t10_parent.md
    create_task_file aitasks/t10/t10_3_active.md
    # Archived children of active parent (should be KEPT)
    create_archived_file aitasks/archived/t10/t10_1_done.md
    create_archived_file aiplans/archived/p10/p10_1_done.md
    # Inactive parent's children (should be ARCHIVED)
    create_archived_file aitasks/archived/t20/t20_1_done.md
    create_archived_file aiplans/archived/p20/p20_1_done.md
    # Standalone archived files (should be ARCHIVED)
    create_archived_file aitasks/archived/t50_standalone.md
    create_archived_file aiplans/archived/p50_standalone.md
)
output_8=$(cd "$TMPDIR_8" && bash .aitask-scripts/aitask_zip_old.sh --dry-run 2>&1)
assert_not_contains "Test 8: t10_1 NOT listed" "t10_1_done" "$output_8"
assert_not_contains "Test 8: p10_1 NOT listed" "p10_1_done" "$output_8"
assert_contains "Test 8: t20_1 IS listed" "t20_1_done" "$output_8"
assert_contains "Test 8: p20_1 IS listed" "p20_1_done" "$output_8"
assert_contains "Test 8: t50 IS listed" "t50_standalone" "$output_8"
assert_contains "Test 8: p50 IS listed" "p50_standalone" "$output_8"
rm -rf "$TMPDIR_8"

# --- Test 9: Actual archive creation ---
echo "--- Test 9: Actual archive creation ---"
TMPDIR_9="$(setup_test_env)"
(
    cd "$TMPDIR_9"
    create_archived_file aitasks/archived/t50_old.md
    create_archived_file aitasks/archived/t51_old.md
    create_archived_file aiplans/archived/p50_old.md
    git add -A && git commit -m "Add test files" --quiet
)
(cd "$TMPDIR_9" && bash .aitask-scripts/aitask_zip_old.sh --no-commit 2>&1 >/dev/null)
assert_file_exists "Test 9: task tar.gz created" "$TMPDIR_9/aitasks/archived/old.tar.gz"
assert_file_exists "Test 9: plan tar.gz created" "$TMPDIR_9/aiplans/archived/old.tar.gz"
assert_file_not_exists "Test 9: t50 removed" "$TMPDIR_9/aitasks/archived/t50_old.md"
assert_file_not_exists "Test 9: t51 removed" "$TMPDIR_9/aitasks/archived/t51_old.md"
assert_file_not_exists "Test 9: p50 removed" "$TMPDIR_9/aiplans/archived/p50_old.md"
# Verify tar.gz contents
tar_contents_9=$(tar -tzf "$TMPDIR_9/aitasks/archived/old.tar.gz" 2>/dev/null)
assert_contains "Test 9: tar contains t50" "t50_old.md" "$tar_contents_9"
assert_contains "Test 9: tar contains t51" "t51_old.md" "$tar_contents_9"
rm -rf "$TMPDIR_9"

# --- Test 10: Cumulative archiving ---
echo "--- Test 10: Cumulative archiving ---"
TMPDIR_10="$(setup_test_env)"
(
    cd "$TMPDIR_10"
    create_archived_file aitasks/archived/t50_first.md
    git add -A && git commit -m "First batch" --quiet
)
(cd "$TMPDIR_10" && bash .aitask-scripts/aitask_zip_old.sh --no-commit 2>&1 >/dev/null)
(
    cd "$TMPDIR_10"
    create_archived_file aitasks/archived/t51_second.md
)
(cd "$TMPDIR_10" && bash .aitask-scripts/aitask_zip_old.sh --no-commit 2>&1 >/dev/null)
tar_contents_10=$(tar -tzf "$TMPDIR_10/aitasks/archived/old.tar.gz" 2>/dev/null)
assert_contains "Test 10: tar still has first batch" "t50_first.md" "$tar_contents_10"
assert_contains "Test 10: tar has second batch" "t51_second.md" "$tar_contents_10"
rm -rf "$TMPDIR_10"

# --- Test 11: Git commit message ---
echo "--- Test 11: Git commit message ---"
TMPDIR_11="$(setup_test_env)"
(
    cd "$TMPDIR_11"
    # Active parent
    create_task_file aitasks/t10_parent.md
    create_task_file aitasks/t10/t10_2_active.md
    # Archivable file
    create_archived_file aitasks/archived/t50_old.md
    create_archived_file aiplans/archived/p50_old.md
    git add -A && git commit -m "Setup" --quiet
)
(cd "$TMPDIR_11" && bash .aitask-scripts/aitask_zip_old.sh 2>&1 >/dev/null)
commit_msg_11=$(cd "$TMPDIR_11" && git log -1 --pretty=%B)
assert_contains "Test 11: commit mentions archive" "ait: Archive old task and plan files" "$commit_msg_11"
rm -rf "$TMPDIR_11"

# --- Test 12: Empty child dirs cleaned up ---
echo "--- Test 12: Empty child dirs cleaned up ---"
TMPDIR_12="$(setup_test_env)"
(
    cd "$TMPDIR_12"
    # Inactive parent with one child to archive
    create_archived_file aitasks/archived/t30/t30_1_child.md
    git add -A && git commit -m "Setup" --quiet
)
(cd "$TMPDIR_12" && bash .aitask-scripts/aitask_zip_old.sh --no-commit 2>&1 >/dev/null)
assert_dir_not_exists "Test 12: empty child dir removed" "$TMPDIR_12/aitasks/archived/t30"
rm -rf "$TMPDIR_12"

# --- Test 13: No-commit flag ---
echo "--- Test 13: No-commit flag ---"
TMPDIR_13="$(setup_test_env)"
(
    cd "$TMPDIR_13"
    create_archived_file aitasks/archived/t50_old.md
    git add -A && git commit -m "Setup" --quiet
)
(cd "$TMPDIR_13" && bash .aitask-scripts/aitask_zip_old.sh --no-commit 2>&1 >/dev/null)
# Check that there's no new commit (HEAD should still be "Setup")
last_commit_13=$(cd "$TMPDIR_13" && git log -1 --pretty=%s)
assert_eq "Test 13: no git commit made" "Setup" "$last_commit_13"
assert_file_exists "Test 13: archive still created" "$TMPDIR_13/aitasks/archived/old.tar.gz"
rm -rf "$TMPDIR_13"

# --- Test 14: Verbose output ---
echo "--- Test 14: Verbose output ---"
TMPDIR_14="$(setup_test_env)"
(
    cd "$TMPDIR_14"
    create_task_file aitasks/t10_parent.md
    create_task_file aitasks/t10/t10_2_active.md
    create_archived_file aitasks/archived/t10/t10_1_done.md
    create_archived_file aitasks/archived/t50_old.md
)
output_14=$(cd "$TMPDIR_14" && bash .aitask-scripts/aitask_zip_old.sh --dry-run -v 2>&1)
assert_contains "Test 14: shows active parents" "Active parents:" "$output_14"
assert_contains "Test 14: shows skipping msg" "Skipping (active siblings)" "$output_14"
rm -rf "$TMPDIR_14"

# --- Test 15: Dependency keeps archived task ---
echo "--- Test 15: Dependency keeps archived task ---"
TMPDIR_15="$(setup_test_env)"
(
    cd "$TMPDIR_15"
    # Active task depends on archived t30
    create_task_file aitasks/t50_needs_30.md "['30']"
    create_archived_file aitasks/archived/t30_depended_on.md
    create_archived_file aitasks/archived/t31_not_depended.md
)
output_15=$(cd "$TMPDIR_15" && bash .aitask-scripts/aitask_zip_old.sh --dry-run 2>&1)
assert_not_contains "Test 15: t30 NOT listed (kept as dependency)" "t30_depended_on" "$output_15"
assert_contains "Test 15: t31 IS listed" "t31_not_depended" "$output_15"
rm -rf "$TMPDIR_15"

# --- Test 16: Dependency keeps archived plan ---
echo "--- Test 16: Dependency keeps archived plan ---"
TMPDIR_16="$(setup_test_env)"
(
    cd "$TMPDIR_16"
    create_task_file aitasks/t50_needs_30.md "[30]"
    create_archived_file aiplans/archived/p30_depended_on.md
    create_archived_file aiplans/archived/p31_not_depended.md
)
output_16=$(cd "$TMPDIR_16" && bash .aitask-scripts/aitask_zip_old.sh --dry-run 2>&1)
assert_not_contains "Test 16: p30 NOT listed (kept as dependency)" "p30_depended_on" "$output_16"
assert_contains "Test 16: p31 IS listed" "p31_not_depended" "$output_16"
rm -rf "$TMPDIR_16"

# --- Test 17: Dependency keeps archived child task ---
echo "--- Test 17: Dependency keeps archived child ---"
TMPDIR_17="$(setup_test_env)"
(
    cd "$TMPDIR_17"
    # Active task depends on child 30_2
    create_task_file aitasks/t50_needs_child.md "[30_2]"
    # Parent 30 is inactive (no aitasks/t30/)
    create_archived_file aitasks/archived/t30/t30_1_not_dep.md
    create_archived_file aitasks/archived/t30/t30_2_is_dep.md
)
output_17=$(cd "$TMPDIR_17" && bash .aitask-scripts/aitask_zip_old.sh --dry-run 2>&1)
assert_not_contains "Test 17: t30_2 NOT listed (kept as dep)" "t30_2_is_dep" "$output_17"
assert_contains "Test 17: t30_1 IS listed" "t30_1_not_dep" "$output_17"
rm -rf "$TMPDIR_17"

# --- Test 18: No dependency — archived task gets archived ---
echo "--- Test 18: No dependency, task archived ---"
TMPDIR_18="$(setup_test_env)"
(
    cd "$TMPDIR_18"
    create_task_file aitasks/t50_active.md "[]"
    create_archived_file aitasks/archived/t30_no_dep.md
)
output_18=$(cd "$TMPDIR_18" && bash .aitask-scripts/aitask_zip_old.sh --dry-run 2>&1)
assert_contains "Test 18: t30 IS listed" "t30_no_dep" "$output_18"
rm -rf "$TMPDIR_18"

# --- Test 19: Multiple depends formats parsed correctly ---
echo "--- Test 19: Multiple depends formats ---"
TMPDIR_19="$(setup_test_env)"
(
    cd "$TMPDIR_19"
    # Format 1: quoted number
    create_task_file aitasks/t50_fmt1.md "['30']"
    # Format 2: plain number
    create_task_file aitasks/t51_fmt2.md "[31]"
    # Format 3: t-prefixed
    create_task_file aitasks/t52_fmt3.md "[t32]"
    # Format 4: child reference
    create_task_file aitasks/t53_fmt4.md "[33_2]"
    # Format 5: mixed
    create_task_file aitasks/t54_fmt5.md "[t34_1, 35]"
    # Archived files for each dep
    create_archived_file aitasks/archived/t30_dep.md
    create_archived_file aitasks/archived/t31_dep.md
    create_archived_file aitasks/archived/t32_dep.md
    create_archived_file aitasks/archived/t33/t33_2_dep.md
    create_archived_file aitasks/archived/t34/t34_1_dep.md
    create_archived_file aitasks/archived/t35_dep.md
    # Not depended on
    create_archived_file aitasks/archived/t36_nodep.md
)
output_19=$(cd "$TMPDIR_19" && bash .aitask-scripts/aitask_zip_old.sh --dry-run 2>&1)
assert_not_contains "Test 19: t30 kept (quoted)" "t30_dep" "$output_19"
assert_not_contains "Test 19: t31 kept (plain)" "t31_dep" "$output_19"
assert_not_contains "Test 19: t32 kept (t-prefix)" "t32_dep" "$output_19"
assert_not_contains "Test 19: t33_2 kept (child ref)" "t33_2_dep" "$output_19"
assert_not_contains "Test 19: t34_1 kept (mixed t-prefix)" "t34_1_dep" "$output_19"
assert_not_contains "Test 19: t35 kept (mixed plain)" "t35_dep" "$output_19"
assert_contains "Test 19: t36 IS listed (no dep)" "t36_nodep" "$output_19"
rm -rf "$TMPDIR_19"

# ============================================================
# Tests: unpack subcommand
# ============================================================

echo ""
echo "=== Testing unpack subcommand ==="
echo ""

# --- Test 20: Unpack parent task from tar.gz ---
echo "--- Test 20: Unpack parent task from tar.gz ---"
TMPDIR_20="$(setup_test_env)"
(
    cd "$TMPDIR_20"
    # Create tar with a parent task
    staging=$(mktemp -d)
    echo "task 50 content" > "$staging/t50_old_feature.md"
    echo "task 51 content" > "$staging/t51_other.md"
    tar -czf aitasks/archived/old.tar.gz -C "$staging" .
    rm -rf "$staging"
    git add -A && git commit -m "Setup" --quiet
)
output_20=$(cd "$TMPDIR_20" && bash .aitask-scripts/aitask_zip_old.sh unpack 50 2>&1)
assert_contains "Test 20: reports unpacked task" "UNPACKED_TASK:" "$output_20"
assert_contains "Test 20: correct filename" "t50_old_feature.md" "$output_20"
assert_file_exists "Test 20: file extracted to filesystem" "$TMPDIR_20/aitasks/archived/t50_old_feature.md"
# Verify tar.gz still has the other task
tar_contents_20=$(tar -tzf "$TMPDIR_20/aitasks/archived/old.tar.gz" 2>/dev/null)
assert_contains "Test 20: tar still has t51" "t51_other.md" "$tar_contents_20"
assert_not_contains "Test 20: tar no longer has t50" "t50_old_feature" "$tar_contents_20"
rm -rf "$TMPDIR_20"

# --- Test 21: Unpack parent + children ---
echo "--- Test 21: Unpack parent + children ---"
TMPDIR_21="$(setup_test_env)"
(
    cd "$TMPDIR_21"
    staging=$(mktemp -d)
    echo "parent task" > "$staging/t50_parent.md"
    mkdir -p "$staging/t50"
    echo "child 1" > "$staging/t50/t50_1_child.md"
    echo "child 2" > "$staging/t50/t50_2_child.md"
    tar -czf aitasks/archived/old.tar.gz -C "$staging" .
    rm -rf "$staging"
    git add -A && git commit -m "Setup" --quiet
)
output_21=$(cd "$TMPDIR_21" && bash .aitask-scripts/aitask_zip_old.sh unpack 50 2>&1)
assert_file_exists "Test 21: parent extracted" "$TMPDIR_21/aitasks/archived/t50_parent.md"
assert_file_exists "Test 21: child 1 extracted" "$TMPDIR_21/aitasks/archived/t50/t50_1_child.md"
assert_file_exists "Test 21: child 2 extracted" "$TMPDIR_21/aitasks/archived/t50/t50_2_child.md"
rm -rf "$TMPDIR_21"

# --- Test 22: Unpack also extracts plan files ---
echo "--- Test 22: Unpack extracts plan files too ---"
TMPDIR_22="$(setup_test_env)"
(
    cd "$TMPDIR_22"
    # Task archive
    staging_t=$(mktemp -d)
    echo "task 50" > "$staging_t/t50_feature.md"
    tar -czf aitasks/archived/old.tar.gz -C "$staging_t" .
    rm -rf "$staging_t"
    # Plan archive
    staging_p=$(mktemp -d)
    echo "plan 50" > "$staging_p/p50_feature.md"
    tar -czf aiplans/archived/old.tar.gz -C "$staging_p" .
    rm -rf "$staging_p"
    git add -A && git commit -m "Setup" --quiet
)
output_22=$(cd "$TMPDIR_22" && bash .aitask-scripts/aitask_zip_old.sh unpack 50 2>&1)
assert_contains "Test 22: unpacked task" "UNPACKED_TASK:" "$output_22"
assert_contains "Test 22: unpacked plan" "UNPACKED_PLAN:" "$output_22"
assert_file_exists "Test 22: task file extracted" "$TMPDIR_22/aitasks/archived/t50_feature.md"
assert_file_exists "Test 22: plan file extracted" "$TMPDIR_22/aiplans/archived/p50_feature.md"
rm -rf "$TMPDIR_22"

# --- Test 23: No-op when not in archive ---
echo "--- Test 23: No-op when not in archive ---"
TMPDIR_23="$(setup_test_env)"
(
    cd "$TMPDIR_23"
    # Task exists on filesystem, not in tar
    create_archived_file aitasks/archived/t50_on_disk.md
    git add -A && git commit -m "Setup" --quiet
)
output_23=$(cd "$TMPDIR_23" && bash .aitask-scripts/aitask_zip_old.sh unpack 50 2>&1)
assert_eq "Test 23: reports not in archive" "NOT_IN_ARCHIVE" "$output_23"
assert_file_exists "Test 23: filesystem file untouched" "$TMPDIR_23/aitasks/archived/t50_on_disk.md"
rm -rf "$TMPDIR_23"

# --- Test 24: No-op when task doesn't exist anywhere ---
echo "--- Test 24: No-op when task doesn't exist ---"
TMPDIR_24="$(setup_test_env)"
output_24=$(cd "$TMPDIR_24" && bash .aitask-scripts/aitask_zip_old.sh unpack 99999 2>&1)
assert_eq "Test 24: reports not in archive" "NOT_IN_ARCHIVE" "$output_24"
rm -rf "$TMPDIR_24"

# --- Test 25: Tar.gz deleted when emptied ---
echo "--- Test 25: Tar.gz deleted when emptied ---"
TMPDIR_25="$(setup_test_env)"
(
    cd "$TMPDIR_25"
    # Only one task in the archive
    staging=$(mktemp -d)
    echo "only task" > "$staging/t50_only.md"
    tar -czf aitasks/archived/old.tar.gz -C "$staging" .
    rm -rf "$staging"
    git add -A && git commit -m "Setup" --quiet
)
(cd "$TMPDIR_25" && bash .aitask-scripts/aitask_zip_old.sh unpack 50 2>&1 >/dev/null)
assert_file_exists "Test 25: file extracted" "$TMPDIR_25/aitasks/archived/t50_only.md"
assert_file_not_exists "Test 25: tar.gz deleted (was only entry)" "$TMPDIR_25/aitasks/archived/old.tar.gz"
rm -rf "$TMPDIR_25"

# --- Test 26: t prefix accepted ---
echo "--- Test 26: t prefix accepted ---"
TMPDIR_26="$(setup_test_env)"
(
    cd "$TMPDIR_26"
    staging=$(mktemp -d)
    echo "task 50" > "$staging/t50_prefix_test.md"
    tar -czf aitasks/archived/old.tar.gz -C "$staging" .
    rm -rf "$staging"
    git add -A && git commit -m "Setup" --quiet
)
output_26=$(cd "$TMPDIR_26" && bash .aitask-scripts/aitask_zip_old.sh unpack t50 2>&1)
assert_contains "Test 26: t prefix works" "UNPACKED_TASK:" "$output_26"
assert_file_exists "Test 26: file extracted with t prefix" "$TMPDIR_26/aitasks/archived/t50_prefix_test.md"
rm -rf "$TMPDIR_26"

# --- Summary ---
echo ""
echo "======================================="
echo "Results: $PASS passed, $FAIL failed (out of $TOTAL)"
echo "======================================="

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
