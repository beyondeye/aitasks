#!/usr/bin/env bash
# test_migrate_archives.sh - Automated tests for aitask_migrate_archives.sh
# Run: bash tests/test_migrate_archives.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

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
    if echo "$actual" | grep -Fqi "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

assert_file_exists() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (missing file '$path')"
    fi
}

assert_file_not_exists() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ ! -f "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (unexpected file '$path')"
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

setup_test_env() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    (
        cd "$tmpdir"
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"

        mkdir -p .aitask-scripts/lib aitasks/archived aiplans/archived tests

        cp "$PROJECT_DIR/ait" .
        cp "$PROJECT_DIR/.aitask-scripts/VERSION" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_migrate_archives.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/

        chmod +x ait .aitask-scripts/aitask_migrate_archives.sh
    )

    echo "$tmpdir"
}

create_tar_gz_from_dir() {
    local archive_path="$1"
    local content_dir="$2"
    mkdir -p "$(dirname "$archive_path")"
    tar -czf "$archive_path" -C "$content_dir" .
}

list_tar_zst() {
    local archive_path="$1"
    zstd -dc "$archive_path" 2>/dev/null | tar -tf -
}

make_staging_dir() {
    mktemp -d
}

echo "=== Testing aitask_migrate_archives.sh ==="
echo ""

# --- Test 1: Syntax check ---
echo "--- Test 1: Syntax check ---"
assert_exit_zero "Syntax check passes" bash -n "$PROJECT_DIR/.aitask-scripts/aitask_migrate_archives.sh"

# --- Test 2: Help output ---
echo "--- Test 2: Help output ---"
output_2=$("$PROJECT_DIR/.aitask-scripts/aitask_migrate_archives.sh" --help 2>&1)
assert_contains "Help shows command purpose" "Convert numbered old*.tar.gz archives" "$output_2"

# --- Test 3: Dry-run numbered archives ---
echo "--- Test 3: Dry-run numbered archives ---"
TMPDIR_3="$(setup_test_env)"
(
    cd "$TMPDIR_3"
    stage_task=$(make_staging_dir)
    echo "task 50" > "$stage_task/t50_old.md"
    create_tar_gz_from_dir aitasks/archived/_b0/old0.tar.gz "$stage_task"
    rm -rf "$stage_task"

    stage_plan=$(make_staging_dir)
    echo "plan 50" > "$stage_plan/p50_old.md"
    create_tar_gz_from_dir aiplans/archived/_b0/old0.tar.gz "$stage_plan"
    rm -rf "$stage_plan"
)
output_3=$(cd "$TMPDIR_3" && bash ./.aitask-scripts/aitask_migrate_archives.sh --dry-run 2>&1)
assert_contains "Dry-run shows task numbered conversion" "Would convert numbered archive: aitasks/archived/_b0/old0.tar.gz -> aitasks/archived/_b0/old0.tar.zst" "$output_3"
assert_contains "Dry-run shows plan numbered conversion" "Would convert numbered archive: aiplans/archived/_b0/old0.tar.gz -> aiplans/archived/_b0/old0.tar.zst" "$output_3"
rm -rf "$TMPDIR_3"

# --- Test 4: Numbered archive conversion ---
echo "--- Test 4: Numbered archive conversion ---"
TMPDIR_4="$(setup_test_env)"
(
    cd "$TMPDIR_4"
    stage=$(make_staging_dir)
    echo "task 50" > "$stage/t50_old.md"
    echo "task 51" > "$stage/t51_old.md"
    create_tar_gz_from_dir aitasks/archived/_b0/old0.tar.gz "$stage"
    rm -rf "$stage"
)
(cd "$TMPDIR_4" && bash ./.aitask-scripts/aitask_migrate_archives.sh >/dev/null 2>&1)
assert_file_exists "Numbered conversion creates tar.zst" "$TMPDIR_4/aitasks/archived/_b0/old0.tar.zst"
assert_file_exists "Numbered conversion preserves source by default" "$TMPDIR_4/aitasks/archived/_b0/old0.tar.gz"
contents_4=$(list_tar_zst "$TMPDIR_4/aitasks/archived/_b0/old0.tar.zst")
assert_contains "Converted numbered archive keeps first file" "t50_old.md" "$contents_4"
assert_contains "Converted numbered archive keeps second file" "t51_old.md" "$contents_4"
rm -rf "$TMPDIR_4"

# --- Test 5: Delete-old removes converted numbered source ---
echo "--- Test 5: Delete-old removes converted numbered source ---"
TMPDIR_5="$(setup_test_env)"
(
    cd "$TMPDIR_5"
    stage=$(make_staging_dir)
    echo "task 50" > "$stage/t50_old.md"
    create_tar_gz_from_dir aitasks/archived/_b0/old0.tar.gz "$stage"
    rm -rf "$stage"
)
(cd "$TMPDIR_5" && bash ./.aitask-scripts/aitask_migrate_archives.sh --delete-old >/dev/null 2>&1)
assert_file_exists "Delete-old still creates tar.zst" "$TMPDIR_5/aitasks/archived/_b0/old0.tar.zst"
assert_file_not_exists "Delete-old removes numbered tar.gz" "$TMPDIR_5/aitasks/archived/_b0/old0.tar.gz"
rm -rf "$TMPDIR_5"

# --- Test 6: Legacy task archive rebucketing ---
echo "--- Test 6: Legacy task archive rebucketing ---"
TMPDIR_6="$(setup_test_env)"
(
    cd "$TMPDIR_6"
    stage=$(make_staging_dir)
    echo "task 50" > "$stage/t50_parent.md"
    echo "task 150" > "$stage/t150_parent.md"
    mkdir -p "$stage/t150"
    echo "child 150_2" > "$stage/t150/t150_2_child.md"
    create_tar_gz_from_dir aitasks/archived/old.tar.gz "$stage"
    rm -rf "$stage"
)
(cd "$TMPDIR_6" && bash ./.aitask-scripts/aitask_migrate_archives.sh >/dev/null 2>&1)
assert_file_exists "Legacy rebucketing creates bundle 0" "$TMPDIR_6/aitasks/archived/_b0/old0.tar.zst"
assert_file_exists "Legacy rebucketing creates bundle 1" "$TMPDIR_6/aitasks/archived/_b0/old1.tar.zst"
assert_file_exists "Legacy source preserved by default" "$TMPDIR_6/aitasks/archived/old.tar.gz"
assert_file_not_exists "Legacy rebucketing does not create root tar.zst" "$TMPDIR_6/aitasks/archived/old.tar.zst"
contents_6a=$(list_tar_zst "$TMPDIR_6/aitasks/archived/_b0/old0.tar.zst")
contents_6b=$(list_tar_zst "$TMPDIR_6/aitasks/archived/_b0/old1.tar.zst")
assert_contains "Legacy task 50 moved to bundle 0" "t50_parent.md" "$contents_6a"
assert_contains "Legacy task 150 moved to bundle 1" "t150_parent.md" "$contents_6b"
assert_contains "Legacy child preserved under parent dir" "t150/t150_2_child.md" "$contents_6b"
rm -rf "$TMPDIR_6"

# --- Test 7: Legacy plan archive rebucketing ---
echo "--- Test 7: Legacy plan archive rebucketing ---"
TMPDIR_7="$(setup_test_env)"
(
    cd "$TMPDIR_7"
    stage=$(make_staging_dir)
    echo "plan 50" > "$stage/p50_parent.md"
    mkdir -p "$stage/p150"
    echo "plan child 150_1" > "$stage/p150/p150_1_child.md"
    create_tar_gz_from_dir aiplans/archived/old.tar.gz "$stage"
    rm -rf "$stage"
)
(cd "$TMPDIR_7" && bash ./.aitask-scripts/aitask_migrate_archives.sh >/dev/null 2>&1)
assert_file_exists "Legacy plan rebucketing creates bundle 0" "$TMPDIR_7/aiplans/archived/_b0/old0.tar.zst"
assert_file_exists "Legacy plan rebucketing creates bundle 1" "$TMPDIR_7/aiplans/archived/_b0/old1.tar.zst"
contents_7a=$(list_tar_zst "$TMPDIR_7/aiplans/archived/_b0/old0.tar.zst")
contents_7b=$(list_tar_zst "$TMPDIR_7/aiplans/archived/_b0/old1.tar.zst")
assert_contains "Legacy plan 50 moved to bundle 0" "p50_parent.md" "$contents_7a"
assert_contains "Legacy plan child preserved under parent dir" "p150/p150_1_child.md" "$contents_7b"
rm -rf "$TMPDIR_7"

# --- Test 8: Rebucketing merges into existing tar.zst bundle ---
echo "--- Test 8: Rebucketing merges into existing tar.zst bundle ---"
TMPDIR_8="$(setup_test_env)"
(
    cd "$TMPDIR_8"
    existing=$(make_staging_dir)
    echo "existing 150" > "$existing/t150_existing.md"
    mkdir -p aitasks/archived/_b0
    tar -cf - -C "$existing" . | zstd -q -f -o aitasks/archived/_b0/old1.tar.zst
    rm -rf "$existing"

    legacy=$(make_staging_dir)
    echo "new 151" > "$legacy/t151_new.md"
    create_tar_gz_from_dir aitasks/archived/old.tar.gz "$legacy"
    rm -rf "$legacy"
)
(cd "$TMPDIR_8" && bash ./.aitask-scripts/aitask_migrate_archives.sh >/dev/null 2>&1)
contents_8=$(list_tar_zst "$TMPDIR_8/aitasks/archived/_b0/old1.tar.zst")
assert_contains "Merge keeps existing bundle content" "t150_existing.md" "$contents_8"
assert_contains "Merge adds rebucketed legacy content" "t151_new.md" "$contents_8"
rm -rf "$TMPDIR_8"

# --- Test 9: Delete-old removes rebucketed legacy source ---
echo "--- Test 9: Delete-old removes rebucketed legacy source ---"
TMPDIR_9="$(setup_test_env)"
(
    cd "$TMPDIR_9"
    legacy=$(make_staging_dir)
    echo "task 50" > "$legacy/t50_parent.md"
    create_tar_gz_from_dir aitasks/archived/old.tar.gz "$legacy"
    rm -rf "$legacy"
)
(cd "$TMPDIR_9" && bash ./.aitask-scripts/aitask_migrate_archives.sh --delete-old >/dev/null 2>&1)
assert_file_exists "Delete-old creates rebucketed target" "$TMPDIR_9/aitasks/archived/_b0/old0.tar.zst"
assert_file_not_exists "Delete-old removes legacy source" "$TMPDIR_9/aitasks/archived/old.tar.gz"
rm -rf "$TMPDIR_9"

# --- Test 10: Existing target causes skip and cleanup with delete-old ---
echo "--- Test 10: Existing target causes skip and cleanup with delete-old ---"
TMPDIR_10="$(setup_test_env)"
(
    cd "$TMPDIR_10"
    stage=$(make_staging_dir)
    echo "converted already" > "$stage/t50_done.md"
    create_tar_gz_from_dir aitasks/archived/_b0/old0.tar.gz "$stage"
    tar -cf - -C "$stage" . | zstd -q -f -o aitasks/archived/_b0/old0.tar.zst
    rm -rf "$stage"
)
output_10=$(cd "$TMPDIR_10" && bash ./.aitask-scripts/aitask_migrate_archives.sh --delete-old 2>&1)
assert_contains "Skip message emitted when tar.zst exists" "Skipping numbered archive (target exists)" "$output_10"
assert_file_not_exists "Delete-old removes already-migrated tar.gz" "$TMPDIR_10/aitasks/archived/_b0/old0.tar.gz"
rm -rf "$TMPDIR_10"

# --- Test 11: Dispatcher path ---
echo "--- Test 11: Dispatcher path ---"
TMPDIR_11="$(setup_test_env)"
(
    cd "$TMPDIR_11"
    stage=$(make_staging_dir)
    echo "task 50" > "$stage/t50_old.md"
    create_tar_gz_from_dir aitasks/archived/_b0/old0.tar.gz "$stage"
    rm -rf "$stage"
)
output_11=$(cd "$TMPDIR_11" && bash ./ait migrate-archives --dry-run 2>&1)
assert_contains "Dispatcher routes to migrate-archives command" "Would convert numbered archive: aitasks/archived/_b0/old0.tar.gz -> aitasks/archived/_b0/old0.tar.zst" "$output_11"
rm -rf "$TMPDIR_11"

echo ""
echo "Passed: $PASS / $TOTAL"

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
