---
Task: t433_2_tests_core_archive_library.md
Parent Task: aitasks/t433_refactor_task_archives.md
Sibling Tasks: aitasks/t433/t433_1_*.md through t433_7_*.md
Worktree: (none — current branch)
Branch: (current)
Base branch: main
---

## Implementation Plan: Tests for Core Archive Library

### Goal

Create `tests/test_archive_utils_v2.sh` -- a comprehensive, self-contained test script for all functions in `archive_utils_v2.sh`, following the established pattern from `tests/test_resolve_tar_gz.sh`.

### Step 1: File scaffold and test helpers

**File:** `tests/test_archive_utils_v2.sh`

```bash
#!/usr/bin/env bash
# test_archive_utils_v2.sh - Tests for archive_utils_v2.sh numbered archive library
# Run: bash tests/test_archive_utils_v2.sh

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
    if echo "$actual" | grep -q "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
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

assert_exit_nonzero() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected non-zero exit, got 0)"
    else
        PASS=$((PASS + 1))
    fi
}
```

### Step 2: Setup and teardown helpers

```bash
setup_test_env() {
    local tmpdir
    tmpdir=$(mktemp -d)
    mkdir -p "$tmpdir/aitasks/archived"
    mkdir -p "$tmpdir/aiplans/archived"
    echo "$tmpdir"
}

# Create a tar.gz archive from a staging directory.
# Automatically creates parent dirs for the archive path.
# Args: $1=archive_path, $2=source_dir
create_test_archive() {
    local archive_path="$1"
    local source_dir="$2"
    mkdir -p "$(dirname "$archive_path")"
    tar -czf "$archive_path" -C "$source_dir" .
}

# Source archive_utils_v2.sh, resetting guard to allow re-sourcing.
source_archive_utils() {
    export SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
    unset _AIT_ARCHIVE_UTILS_V2_LOADED
    if [[ -n "${_AIT_ARCHIVE_V2_TMPDIR:-}" && -d "$_AIT_ARCHIVE_V2_TMPDIR" ]]; then
        rm -rf "$_AIT_ARCHIVE_V2_TMPDIR"
    fi
    _AIT_ARCHIVE_V2_TMPDIR=""
    source "$PROJECT_DIR/.aitask-scripts/lib/archive_utils_v2.sh"
}
```

### Step 3: Test group A -- `archive_bundle()` boundary cases

```bash
echo "=== test_archive_utils_v2.sh ==="
echo ""
echo "--- Group A: archive_bundle() ---"
source_archive_utils

assert_eq "bundle(0)=0"    "0"  "$(archive_bundle 0)"
assert_eq "bundle(99)=0"   "0"  "$(archive_bundle 99)"
assert_eq "bundle(100)=1"  "1"  "$(archive_bundle 100)"
assert_eq "bundle(199)=1"  "1"  "$(archive_bundle 199)"
assert_eq "bundle(999)=9"  "9"  "$(archive_bundle 999)"
assert_eq "bundle(1000)=10" "10" "$(archive_bundle 1000)"
assert_eq "bundle(1099)=10" "10" "$(archive_bundle 1099)"
assert_eq "bundle(9999)=99" "99" "$(archive_bundle 9999)"
```

### Step 4: Test group B -- `archive_dir()` boundary cases

```bash
echo "--- Group B: archive_dir() ---"
assert_eq "dir(0)=0"    "0"  "$(archive_dir 0)"
assert_eq "dir(9)=0"    "0"  "$(archive_dir 9)"
assert_eq "dir(10)=1"   "1"  "$(archive_dir 10)"
assert_eq "dir(19)=1"   "1"  "$(archive_dir 19)"
assert_eq "dir(99)=9"   "9"  "$(archive_dir 99)"
assert_eq "dir(100)=10" "10" "$(archive_dir 100)"
```

### Step 5: Test group C -- `archive_path_for_id()` full paths

```bash
echo "--- Group C: archive_path_for_id() ---"
assert_eq "path(0)"    "archived/_b0/old0.tar.gz"             "$(archive_path_for_id 0 "archived")"
assert_eq "path(99)"   "archived/_b0/old0.tar.gz"             "$(archive_path_for_id 99 "archived")"
assert_eq "path(100)"  "archived/_b0/old1.tar.gz"             "$(archive_path_for_id 100 "archived")"
assert_eq "path(999)"  "archived/_b0/old9.tar.gz"             "$(archive_path_for_id 999 "archived")"
assert_eq "path(1000)" "archived/_b1/old10.tar.gz"            "$(archive_path_for_id 1000 "archived")"
assert_eq "path(5432)" "aitasks/archived/_b5/old54.tar.gz"    "$(archive_path_for_id 5432 "aitasks/archived")"
```

### Step 6: Test group D -- `_search_tar_gz_v2()`

```bash
echo "--- Group D: _search_tar_gz_v2() ---"
TMPDIR_D=$(setup_test_env)
staging=$(mktemp -d)
echo "task 50 content" > "$staging/t50_test_feature.md"
create_test_archive "$TMPDIR_D/aitasks/archived/_b0/old0.tar.gz" "$staging"
rm -rf "$staging"
source_archive_utils

result=$(_search_tar_gz_v2 "$TMPDIR_D/aitasks/archived/_b0/old0.tar.gz" "t50_.*\.md$")
assert_contains "search finds t50 in old0" "t50_test_feature.md" "$result"

result=$(_search_tar_gz_v2 "$TMPDIR_D/aitasks/archived/_b0/old0.tar.gz" "t999_.*\.md$")
assert_eq "search for non-existent returns empty" "" "$result"

result=$(_search_tar_gz_v2 "$TMPDIR_D/aitasks/archived/nonexistent.tar.gz" "t50_.*\.md$")
assert_eq "search on missing archive returns empty" "" "$result"
rm -rf "$TMPDIR_D"
```

### Step 7: Test group E -- `_extract_from_tar_gz_v2()`

```bash
echo "--- Group E: _extract_from_tar_gz_v2() ---"
TMPDIR_E=$(setup_test_env)
staging=$(mktemp -d)
echo "extracted content here" > "$staging/t75_some_task.md"
create_test_archive "$TMPDIR_E/aitasks/archived/_b0/old0.tar.gz" "$staging"
rm -rf "$staging"
source_archive_utils

filename=$(_search_tar_gz_v2 "$TMPDIR_E/aitasks/archived/_b0/old0.tar.gz" "t75_.*\.md$")
_extract_from_tar_gz_v2 "$TMPDIR_E/aitasks/archived/_b0/old0.tar.gz" "$filename"
actual_content=$(cat "$_AIT_V2_EXTRACT_RESULT")
assert_eq "extract content matches" "extracted content here" "$actual_content"
assert_contains "extract result path set" "t75_some_task.md" "$_AIT_V2_EXTRACT_RESULT"
rm -rf "$TMPDIR_E"
```

### Step 8: Test group F -- `_find_archive_for_task()`

```bash
echo "--- Group F: _find_archive_for_task() ---"
TMPDIR_F=$(setup_test_env)
staging=$(mktemp -d)
echo "task 150" > "$staging/t150_feature.md"
create_test_archive "$TMPDIR_F/aitasks/archived/_b0/old1.tar.gz" "$staging"
rm -rf "$staging"
source_archive_utils

result=$(_find_archive_for_task 150 "$TMPDIR_F/aitasks/archived")
assert_eq "find archive for task 150" "$TMPDIR_F/aitasks/archived/_b0/old1.tar.gz" "$result"

result=$(_find_archive_for_task 9999 "$TMPDIR_F/aitasks/archived")
assert_eq "find archive for nonexistent returns empty" "" "$result"
rm -rf "$TMPDIR_F"
```

### Step 9: Test group G -- `_search_all_archives()`

```bash
echo "--- Group G: _search_all_archives() ---"
TMPDIR_G=$(setup_test_env)

# Create two archives in different bundles
staging1=$(mktemp -d)
echo "task 50" > "$staging1/t50_alpha.md"
create_test_archive "$TMPDIR_G/aitasks/archived/_b0/old0.tar.gz" "$staging1"
rm -rf "$staging1"

staging2=$(mktemp -d)
echo "task 150" > "$staging2/t150_beta.md"
create_test_archive "$TMPDIR_G/aitasks/archived/_b0/old1.tar.gz" "$staging2"
rm -rf "$staging2"

source_archive_utils

# Search pattern that matches one archive
result=$(_search_all_archives "$TMPDIR_G/aitasks/archived" "t50_.*\.md$")
assert_contains "search_all finds t50" "t50_alpha.md" "$result"

# Search pattern that matches the other archive
result=$(_search_all_archives "$TMPDIR_G/aitasks/archived" "t150_.*\.md$")
assert_contains "search_all finds t150" "t150_beta.md" "$result"

# Search pattern that matches nothing
result=$(_search_all_archives "$TMPDIR_G/aitasks/archived" "t999_.*\.md$")
assert_eq "search_all no match returns empty" "" "$result"

# No archives at all
TMPDIR_G2=$(setup_test_env)
source_archive_utils
result=$(_search_all_archives "$TMPDIR_G2/aitasks/archived" "t50_.*\.md$")
assert_eq "search_all empty dir returns empty" "" "$result"
rm -rf "$TMPDIR_G" "$TMPDIR_G2"
```

### Step 10: Test group H -- `_search_legacy_then_v2()`

```bash
echo "--- Group H: _search_legacy_then_v2() ---"

# H1: Only v2 archive exists
TMPDIR_H1=$(setup_test_env)
staging=$(mktemp -d)
echo "v2 task 200" > "$staging/t200_v2only.md"
create_test_archive "$TMPDIR_H1/aitasks/archived/_b0/old2.tar.gz" "$staging"
rm -rf "$staging"
source_archive_utils
result=$(_search_legacy_then_v2 200 "$TMPDIR_H1/aitasks/archived" "t200_.*\.md$")
assert_contains "v2-only: finds via v2" "t200_v2only.md" "$result"
assert_contains "v2-only: correct archive path" "old2.tar.gz" "$result"
rm -rf "$TMPDIR_H1"

# H2: Only legacy old.tar.gz exists
TMPDIR_H2=$(setup_test_env)
staging=$(mktemp -d)
echo "legacy task 200" > "$staging/t200_legacy.md"
create_test_archive "$TMPDIR_H2/aitasks/archived/old.tar.gz" "$staging"
rm -rf "$staging"
source_archive_utils
result=$(_search_legacy_then_v2 200 "$TMPDIR_H2/aitasks/archived" "t200_.*\.md$")
assert_contains "legacy-only: finds via fallback" "t200_legacy.md" "$result"
assert_contains "legacy-only: legacy archive path" "old.tar.gz" "$result"
rm -rf "$TMPDIR_H2"

# H3: Both exist -- v2 wins
TMPDIR_H3=$(setup_test_env)
staging_v2=$(mktemp -d)
echo "v2 task 200" > "$staging_v2/t200_v2.md"
create_test_archive "$TMPDIR_H3/aitasks/archived/_b0/old2.tar.gz" "$staging_v2"
rm -rf "$staging_v2"
staging_leg=$(mktemp -d)
echo "legacy task 200" > "$staging_leg/t200_legacy.md"
create_test_archive "$TMPDIR_H3/aitasks/archived/old.tar.gz" "$staging_leg"
rm -rf "$staging_leg"
source_archive_utils
result=$(_search_legacy_then_v2 200 "$TMPDIR_H3/aitasks/archived" "t200_.*\.md$")
assert_contains "both: v2 takes priority" "old2.tar.gz" "$result"
rm -rf "$TMPDIR_H3"

# H4: Neither exists
TMPDIR_H4=$(setup_test_env)
source_archive_utils
result=$(_search_legacy_then_v2 200 "$TMPDIR_H4/aitasks/archived" "t200_.*\.md$")
assert_eq "neither: returns empty" "" "$result"
rm -rf "$TMPDIR_H4"
```

### Step 11: Test group I -- child task resolution through archive

```bash
echo "--- Group I: Child task resolution ---"
TMPDIR_I=$(setup_test_env)
staging=$(mktemp -d)
mkdir -p "$staging/t130"
echo "child 130_2 content" > "$staging/t130/t130_2_add_login.md"
# Task 130 -> bundle 1 -> dir 0 -> _b0/old1.tar.gz
create_test_archive "$TMPDIR_I/aitasks/archived/_b0/old1.tar.gz" "$staging"
rm -rf "$staging"
source_archive_utils

# Verify path computation for child's parent
assert_eq "child parent 130 bundle" "1" "$(archive_bundle 130)"
assert_eq "child parent 130 path" "$TMPDIR_I/aitasks/archived/_b0/old1.tar.gz" \
    "$(archive_path_for_id 130 "$TMPDIR_I/aitasks/archived")"

# Search for child pattern in correct archive
archive_path=$(archive_path_for_id 130 "$TMPDIR_I/aitasks/archived")
result=$(_search_tar_gz_v2 "$archive_path" "(^|/)t130/t130_2_.*\.md$")
assert_contains "child search finds t130_2" "t130_2_add_login.md" "$result"

# Extract and verify content
_extract_from_tar_gz_v2 "$archive_path" "$result"
actual_content=$(cat "$_AIT_V2_EXTRACT_RESULT")
assert_eq "child extract content" "child 130_2 content" "$actual_content"
rm -rf "$TMPDIR_I"
```

### Step 12: Test group J -- temp dir cleanup

```bash
echo "--- Group J: Temp dir cleanup ---"
TMPDIR_J=$(setup_test_env)
staging=$(mktemp -d)
echo "cleanup test" > "$staging/t88_cleanup.md"
create_test_archive "$TMPDIR_J/aitasks/archived/_b0/old0.tar.gz" "$staging"
rm -rf "$staging"

marker_file=$(mktemp)
bash -c "
    export SCRIPT_DIR='$PROJECT_DIR/.aitask-scripts'
    source '$PROJECT_DIR/.aitask-scripts/lib/archive_utils_v2.sh'
    filename=\$(_search_tar_gz_v2 '$TMPDIR_J/aitasks/archived/_b0/old0.tar.gz' 't88_.*\.md$')
    _extract_from_tar_gz_v2 '$TMPDIR_J/aitasks/archived/_b0/old0.tar.gz' \"\$filename\"
    echo \"\$_AIT_ARCHIVE_V2_TMPDIR\" > '$marker_file'
"
tmpdir_path=$(cat "$marker_file")
rm -f "$marker_file"
TOTAL=$((TOTAL + 1))
if [[ -n "$tmpdir_path" && ! -d "$tmpdir_path" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: v2 temp dir should be cleaned up after shell exit"
fi
rm -rf "$TMPDIR_J"
```

### Step 13: Results summary

```bash
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
```

### Step 14: Validate

1. Run the test file:
   ```bash
   bash tests/test_archive_utils_v2.sh
   ```
   All tests must pass.

2. ShellCheck the test file:
   ```bash
   shellcheck tests/test_archive_utils_v2.sh
   ```

3. Verify no leftover temp dirs after test run (spot check with `ls /tmp/` before/after).

### Step 9: Final Implementation Notes

- **Actual work done:** Created `tests/test_archive_utils_v2.sh` (254 lines) with 42 assertions across 10 test groups (A–J), covering all functions in `archive_utils_v2.sh`: path computation (`archive_bundle`, `archive_dir`, `archive_path_for_id`), single-archive primitives (`_search_tar_gz_v2`, `_extract_from_tar_gz_v2`), multi-archive operations (`_find_archive_for_task`, `_search_all_archives`, `_search_legacy_then_v2`), child task resolution, and temp dir cleanup.
- **Deviations from plan:** None. Implementation matched the plan exactly.
- **Issues encountered:** None. All 42 tests pass. ShellCheck clean (only SC1091 info for sourced file, same as existing tests).
- **Test count and results:** 42 passed, 0 failed, 42 total — ALL TESTS PASSED.
- **Notes for sibling tasks:** The test file validates all functions from t433_1's library. Sibling tasks (t433_3+) that add new functions to the library or modify existing ones should add corresponding tests to this file or create new test files as appropriate. The test pattern (setup_test_env, create_test_archive, source_archive_utils with guard reset) is reusable.
