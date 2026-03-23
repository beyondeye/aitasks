#!/usr/bin/env bash
# test_zip_old_v2.sh - Integration tests for aitask_zip_old_v2.sh (numbered archives)
# Run: bash tests/test_zip_old_v2.sh

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
    if echo "$actual" | grep -q "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -q "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (output should NOT contain '$unexpected', but it does)"
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

# Check if a tar.gz archive contains a file matching a pattern
archive_contains() {
    local archive="$1"
    local pattern="$2"
    tar -tzf "$archive" 2>/dev/null | grep -qE "$pattern"
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

# Create a minimal archived file
create_archived_file() {
    local path="$1"
    mkdir -p "$(dirname "$path")"
    echo "Archived content for $(basename "$path")" > "$path"
}

# Setup a test environment with git repo (needed for zip-old script)
setup_test_env() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    (
        cd "$tmpdir"
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"

        mkdir -p aitasks/archived
        mkdir -p aiplans/archived

        # Copy v2 script and dependencies
        mkdir -p .aitask-scripts/lib
        cp "$PROJECT_DIR/.aitask-scripts/aitask_zip_old_v2.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils_v2.sh" .aitask-scripts/lib/

        git add -A
        git commit -m "Initial setup" --quiet
    )
    echo "$tmpdir"
}

echo "=== test_zip_old_v2.sh ==="
echo ""

# --- Test 1: Single task archived to correct bundle ---
echo "--- Test 1: Single task archived to correct bundle ---"
TMPDIR_1="$(setup_test_env)"
(
    cd "$TMPDIR_1"
    create_archived_file aitasks/archived/t50_old_task.md
    git add -A && git commit -m "Add test file" --quiet
)
(cd "$TMPDIR_1" && bash .aitask-scripts/aitask_zip_old_v2.sh --no-commit >/dev/null 2>&1)
assert_file_exists "Test 1: bundle created" "$TMPDIR_1/aitasks/archived/_b0/old0.tar.gz"
TOTAL=$((TOTAL + 1))
if archive_contains "$TMPDIR_1/aitasks/archived/_b0/old0.tar.gz" "t50_old_task.md"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Test 1: t50 not in _b0/old0.tar.gz"
fi
rm -rf "$TMPDIR_1"

# --- Test 2: Multiple tasks split across bundles ---
echo "--- Test 2: Multiple tasks split across bundles ---"
TMPDIR_2="$(setup_test_env)"
(
    cd "$TMPDIR_2"
    create_archived_file aitasks/archived/t50_first.md
    create_archived_file aitasks/archived/t150_second.md
    git add -A && git commit -m "Add files" --quiet
)
(cd "$TMPDIR_2" && bash .aitask-scripts/aitask_zip_old_v2.sh --no-commit >/dev/null 2>&1)
TOTAL=$((TOTAL + 1))
if archive_contains "$TMPDIR_2/aitasks/archived/_b0/old0.tar.gz" "t50_first.md"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Test 2: t50 not in old0"
fi
TOTAL=$((TOTAL + 1))
if archive_contains "$TMPDIR_2/aitasks/archived/_b0/old1.tar.gz" "t150_second.md"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Test 2: t150 not in old1"
fi
rm -rf "$TMPDIR_2"

# --- Test 3: Child tasks archived with parent bundle ---
echo "--- Test 3: Child tasks archived with parent bundle ---"
TMPDIR_3="$(setup_test_env)"
(
    cd "$TMPDIR_3"
    create_archived_file aitasks/archived/t130/t130_2_child.md
    git add -A && git commit -m "Add child" --quiet
)
(cd "$TMPDIR_3" && bash .aitask-scripts/aitask_zip_old_v2.sh --no-commit >/dev/null 2>&1)
TOTAL=$((TOTAL + 1))
if archive_contains "$TMPDIR_3/aitasks/archived/_b0/old1.tar.gz" "t130_2_child.md"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Test 3: child t130_2 not in old1"
fi
rm -rf "$TMPDIR_3"

# --- Test 4: Plans archived to separate plan bundles ---
echo "--- Test 4: Plans archived to separate plan bundles ---"
TMPDIR_4="$(setup_test_env)"
(
    cd "$TMPDIR_4"
    create_archived_file aiplans/archived/p200_plan.md
    git add -A && git commit -m "Add plan" --quiet
)
(cd "$TMPDIR_4" && bash .aitask-scripts/aitask_zip_old_v2.sh --no-commit >/dev/null 2>&1)
assert_file_exists "Test 4: plan bundle created" "$TMPDIR_4/aiplans/archived/_b0/old2.tar.gz"
TOTAL=$((TOTAL + 1))
if archive_contains "$TMPDIR_4/aiplans/archived/_b0/old2.tar.gz" "p200_plan.md"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Test 4: p200 not in plan _b0/old2"
fi
rm -rf "$TMPDIR_4"

# --- Test 5: Merge with existing numbered archive ---
echo "--- Test 5: Merge with existing numbered archive ---"
TMPDIR_5="$(setup_test_env)"
(
    cd "$TMPDIR_5"
    # Create a pre-existing archive with t50
    create_archived_file aitasks/archived/t50_existing.md
    git add -A && git commit -m "First batch" --quiet
)
(cd "$TMPDIR_5" && bash .aitask-scripts/aitask_zip_old_v2.sh --no-commit >/dev/null 2>&1)
# Now add another task in the same bundle
(
    cd "$TMPDIR_5"
    create_archived_file aitasks/archived/t80_new.md
)
(cd "$TMPDIR_5" && bash .aitask-scripts/aitask_zip_old_v2.sh --no-commit >/dev/null 2>&1)
TOTAL=$((TOTAL + 1))
if archive_contains "$TMPDIR_5/aitasks/archived/_b0/old0.tar.gz" "t50_existing.md"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Test 5: original t50 lost after merge"
fi
TOTAL=$((TOTAL + 1))
if archive_contains "$TMPDIR_5/aitasks/archived/_b0/old0.tar.gz" "t80_new.md"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Test 5: new t80 not in merged archive"
fi
rm -rf "$TMPDIR_5"

# --- Test 6: Archive verification ---
echo "--- Test 6: Archive verification ---"
TMPDIR_6="$(setup_test_env)"
(
    cd "$TMPDIR_6"
    create_archived_file aitasks/archived/t50_verify.md
    create_archived_file aitasks/archived/t51_verify.md
    git add -A && git commit -m "Add files" --quiet
)
(cd "$TMPDIR_6" && bash .aitask-scripts/aitask_zip_old_v2.sh --no-commit >/dev/null 2>&1)
tar_list=$(tar -tzf "$TMPDIR_6/aitasks/archived/_b0/old0.tar.gz" 2>/dev/null)
assert_contains "Test 6: tar lists t50" "t50_verify.md" "$tar_list"
assert_contains "Test 6: tar lists t51" "t51_verify.md" "$tar_list"
rm -rf "$TMPDIR_6"

# --- Test 7: Original files removed after archiving ---
echo "--- Test 7: Original files removed after archiving ---"
TMPDIR_7="$(setup_test_env)"
(
    cd "$TMPDIR_7"
    create_archived_file aitasks/archived/t50_remove.md
    git add -A && git commit -m "Setup" --quiet
)
(cd "$TMPDIR_7" && bash .aitask-scripts/aitask_zip_old_v2.sh --no-commit >/dev/null 2>&1)
assert_file_not_exists "Test 7: original removed" "$TMPDIR_7/aitasks/archived/t50_remove.md"
assert_file_exists "Test 7: archive exists" "$TMPDIR_7/aitasks/archived/_b0/old0.tar.gz"
rm -rf "$TMPDIR_7"

# --- Test 8: Empty child directories cleaned up ---
echo "--- Test 8: Empty child directories cleaned up ---"
TMPDIR_8="$(setup_test_env)"
(
    cd "$TMPDIR_8"
    create_archived_file aitasks/archived/t130/t130_1_child.md
    git add -A && git commit -m "Setup" --quiet
)
(cd "$TMPDIR_8" && bash .aitask-scripts/aitask_zip_old_v2.sh --no-commit >/dev/null 2>&1)
assert_dir_not_exists "Test 8: empty child dir removed" "$TMPDIR_8/aitasks/archived/t130"
rm -rf "$TMPDIR_8"

# --- Test 9: Dry run produces no changes ---
echo "--- Test 9: Dry run produces no changes ---"
TMPDIR_9="$(setup_test_env)"
(
    cd "$TMPDIR_9"
    create_archived_file aitasks/archived/t50_dryrun.md
)
(cd "$TMPDIR_9" && bash .aitask-scripts/aitask_zip_old_v2.sh --dry-run >/dev/null 2>&1)
assert_file_exists "Test 9: original still exists" "$TMPDIR_9/aitasks/archived/t50_dryrun.md"
TOTAL=$((TOTAL + 1))
if [[ ! -d "$TMPDIR_9/aitasks/archived/_b0" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Test 9: _b0 dir should not exist after dry run"
fi
rm -rf "$TMPDIR_9"

# --- Test 10: Unpack from numbered archive ---
echo "--- Test 10: Unpack from numbered archive ---"
TMPDIR_10="$(setup_test_env)"
(
    cd "$TMPDIR_10"
    create_archived_file aitasks/archived/t50_unpack.md
    git add -A && git commit -m "Setup" --quiet
)
(cd "$TMPDIR_10" && bash .aitask-scripts/aitask_zip_old_v2.sh --no-commit >/dev/null 2>&1)
assert_file_not_exists "Test 10 pre: file archived" "$TMPDIR_10/aitasks/archived/t50_unpack.md"
output_10=$(cd "$TMPDIR_10" && bash .aitask-scripts/aitask_zip_old_v2.sh unpack 50 2>&1)
assert_contains "Test 10: reports unpacked" "UNPACKED_TASK:" "$output_10"
assert_file_exists "Test 10: file restored" "$TMPDIR_10/aitasks/archived/t50_unpack.md"
rm -rf "$TMPDIR_10"

# --- Test 11: Unpack from legacy archive ---
echo "--- Test 11: Unpack from legacy archive ---"
TMPDIR_11="$(setup_test_env)"
(
    cd "$TMPDIR_11"
    staging=$(mktemp -d)
    echo "legacy task 50" > "$staging/t50_legacy.md"
    tar -czf aitasks/archived/old.tar.gz -C "$staging" .
    rm -rf "$staging"
    git add -A && git commit -m "Setup" --quiet
)
output_11=$(cd "$TMPDIR_11" && bash .aitask-scripts/aitask_zip_old_v2.sh unpack 50 2>&1)
assert_contains "Test 11: reports unpacked from legacy" "UNPACKED_TASK:" "$output_11"
assert_file_exists "Test 11: file restored from legacy" "$TMPDIR_11/aitasks/archived/t50_legacy.md"
rm -rf "$TMPDIR_11"

# --- Test 12: Unpack removes file from archive ---
echo "--- Test 12: Unpack removes file from archive ---"
TMPDIR_12="$(setup_test_env)"
(
    cd "$TMPDIR_12"
    create_archived_file aitasks/archived/t50_stay.md
    create_archived_file aitasks/archived/t51_remove.md
    git add -A && git commit -m "Setup" --quiet
)
(cd "$TMPDIR_12" && bash .aitask-scripts/aitask_zip_old_v2.sh --no-commit >/dev/null 2>&1)
(cd "$TMPDIR_12" && bash .aitask-scripts/aitask_zip_old_v2.sh unpack 51 >/dev/null 2>&1)
# Archive should still exist with t50 but not t51
TOTAL=$((TOTAL + 1))
if archive_contains "$TMPDIR_12/aitasks/archived/_b0/old0.tar.gz" "t50_stay.md"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Test 12: t50 should remain in archive"
fi
TOTAL=$((TOTAL + 1))
if ! archive_contains "$TMPDIR_12/aitasks/archived/_b0/old0.tar.gz" "t51_remove.md"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Test 12: t51 should be removed from archive"
fi
rm -rf "$TMPDIR_12"

# --- Test 13: High task IDs ---
echo "--- Test 13: High task IDs ---"
TMPDIR_13="$(setup_test_env)"
(
    cd "$TMPDIR_13"
    create_archived_file aitasks/archived/t1050_high_id.md
    git add -A && git commit -m "Setup" --quiet
)
(cd "$TMPDIR_13" && bash .aitask-scripts/aitask_zip_old_v2.sh --no-commit >/dev/null 2>&1)
# t1050: bundle=10, dir=1 -> _b1/old10.tar.gz
assert_file_exists "Test 13: high ID bundle created" "$TMPDIR_13/aitasks/archived/_b1/old10.tar.gz"
TOTAL=$((TOTAL + 1))
if archive_contains "$TMPDIR_13/aitasks/archived/_b1/old10.tar.gz" "t1050_high_id.md"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Test 13: t1050 not in _b1/old10"
fi
rm -rf "$TMPDIR_13"

# --- Test 14: Corrupted archive backup ---
echo "--- Test 14: Corrupted archive backup ---"
TMPDIR_14="$(setup_test_env)"
(
    cd "$TMPDIR_14"
    # Create a corrupted archive at the expected path
    mkdir -p aitasks/archived/_b0
    echo "not a real tar" > aitasks/archived/_b0/old0.tar.gz
    # Add a file to archive into the same bundle
    create_archived_file aitasks/archived/t50_after_corrupt.md
    git add -A && git commit -m "Setup" --quiet
)
(cd "$TMPDIR_14" && bash .aitask-scripts/aitask_zip_old_v2.sh --no-commit >/dev/null 2>&1)
assert_file_exists "Test 14: backup created" "$TMPDIR_14/aitasks/archived/_b0/old0.tar.gz.bak"
assert_file_exists "Test 14: new archive created" "$TMPDIR_14/aitasks/archived/_b0/old0.tar.gz"
TOTAL=$((TOTAL + 1))
if archive_contains "$TMPDIR_14/aitasks/archived/_b0/old0.tar.gz" "t50_after_corrupt.md"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Test 14: t50 not in new archive after corrupt recovery"
fi
rm -rf "$TMPDIR_14"

# --- Results ---
echo ""
echo "======================================="
echo "Results: $PASS passed, $FAIL failed (out of $TOTAL)"
echo "======================================="

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
