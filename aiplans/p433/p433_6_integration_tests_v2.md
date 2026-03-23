---
Task: t433_6_integration_tests_v2.md
Parent Task: aitasks/t433_refactor_task_archives.md
Sibling Tasks: aitasks/t433/t433_*_*.md
Worktree: (none — current branch)
Branch: (current)
Base branch: main
---

## Implementation Plan: Integration Tests for V2 Archive System

### Goal

Create three self-contained test files exercising the v2 archive libraries end-to-end:
1. `tests/test_resolve_v2.sh` -- resolve functions with numbered archives
2. `tests/test_zip_old_v2.sh` -- zip-old script creating correct bundles
3. `tests/test_archive_scan_v2.sh` -- scanner functions across multiple archives

### Dependencies

- **t433_3** (`task_resolve_v2.sh`) -- resolve functions to test
- **t433_4** (`aitask_zip_old_v2.sh`) -- zip-old script to test
- **t433_5** (`archive_scan_v2.sh`) -- scanner functions to test
- **t433_1** (`archive_utils_v2.sh`) -- foundational library used by all above

### Reference Pattern

All tests follow the pattern from `tests/test_resolve_tar_gz.sh`:
- `set -e` at top
- `PASS`, `FAIL`, `TOTAL` counters
- `assert_eq`, `assert_contains`, `assert_exit_zero`, `assert_exit_nonzero` helpers
- Each test block: setup temp env, run operation, assert, cleanup
- Summary at bottom with exit 1 on any failure

### Step 1: Create shared test helpers

All three test files will reuse these helpers. Define them at the top of each file
(copy-paste pattern, not a shared file, since test files are self-contained):

```bash
#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0; FAIL=0; TOTAL=0

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
    local desc="$1"; shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then PASS=$((PASS + 1))
    else FAIL=$((FAIL + 1)); echo "FAIL: $desc (command exited non-zero)"; fi
}

assert_exit_nonzero() {
    local desc="$1"; shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then
        FAIL=$((FAIL + 1)); echo "FAIL: $desc (expected non-zero exit, got 0)"
    else PASS=$((PASS + 1)); fi
}

setup_test_env() {
    local tmpdir
    tmpdir=$(mktemp -d)
    mkdir -p "$tmpdir/aitasks/archived"
    mkdir -p "$tmpdir/aiplans/archived"
    echo "$tmpdir"
}

create_test_archive() {
    local archive_path="$1"
    local source_dir="$2"
    mkdir -p "$(dirname "$archive_path")"
    tar -czf "$archive_path" -C "$source_dir" .
}

# Create a numbered archive at the correct path for a given task ID
create_numbered_archive() {
    local tmpdir="$1"     # test root dir
    local base="$2"       # e.g., "aitasks/archived" or "aiplans/archived"
    local task_id="$3"    # numeric task ID determining bundle
    local source_dir="$4" # dir containing files to archive
    local bundle dir archive_path
    bundle=$(( task_id / 100 ))
    dir=$(( bundle / 10 ))
    archive_path="$tmpdir/$base/_b${dir}/old${bundle}.tar.gz"
    mkdir -p "$(dirname "$archive_path")"
    tar -czf "$archive_path" -C "$source_dir" .
}
```

### Step 2: Implement `tests/test_resolve_v2.sh`

**File:** `tests/test_resolve_v2.sh`

Source setup:
```bash
source_resolve_v2() {
    local tmpdir="$1"
    export TASK_DIR="$tmpdir/aitasks"
    export ARCHIVED_DIR="$tmpdir/aitasks/archived"
    export PLAN_DIR="$tmpdir/aiplans"
    export ARCHIVED_PLAN_DIR="$tmpdir/aiplans/archived"
    export SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
    unset _AIT_TASK_RESOLVE_V2_LOADED
    unset _AIT_ARCHIVE_UTILS_V2_LOADED
    if [[ -n "${_AIT_ARCHIVE_V2_TMPDIR:-}" && -d "$_AIT_ARCHIVE_V2_TMPDIR" ]]; then
        rm -rf "$_AIT_ARCHIVE_V2_TMPDIR"
    fi
    _AIT_ARCHIVE_V2_TMPDIR=""
    source "$PROJECT_DIR/.aitask-scripts/lib/task_resolve_v2.sh"
}
```

**14 test cases** (as specified in the task):

| # | Test | Setup | Assert |
|---|------|-------|--------|
| 1 | Parent from active dir | `t50_test.md` in TASK_DIR | Path matches active |
| 2 | Parent from archived dir | `t50_test.md` in ARCHIVED_DIR | Path matches archived |
| 3 | Parent from numbered archive | `t50_test.md` in `_b0/old0.tar.gz` | Content matches "tar task 50" |
| 4 | Child from numbered archive | `t130/t130_2_sub.md` in `_b0/old1.tar.gz` | Content matches |
| 5 | Legacy fallback | `t50_test.md` in `old.tar.gz` only | Content matches |
| 6 | Active wins over archive | Both active + archive | Path is active dir |
| 7 | Loose archived wins over archive | Both loose + archive | Path is archived dir |
| 8 | Numbered wins over legacy | Both numbered + legacy | Content from numbered |
| 9 | Plan from numbered archive | `p200_plan.md` in plan `_b0/old2.tar.gz` | Content matches |
| 10 | Plan from legacy | `p200_plan.md` in plan `old.tar.gz` | Content matches |
| 11 | Parent not found -- dies | Empty env | Non-zero exit |
| 12 | Plan not found -- empty | Empty env | Empty string returned |
| 13 | Temp cleanup | Extract from archive in subshell | Temp dir removed |
| 14 | Cross-bundle boundary | t99 in old0, t100 in old1 | Both resolve correctly |

Each test block follows the pattern:
```bash
echo "--- Test N: description ---"
TMPDIR_N=$(setup_test_env)
# ... setup ...
source_resolve_v2 "$TMPDIR_N"
result=$(resolve_task_file_v2 "50")
assert_eq "description" "expected" "$result"
rm -rf "$TMPDIR_N"
```

### Step 3: Implement `tests/test_zip_old_v2.sh`

**File:** `tests/test_zip_old_v2.sh`

This test file runs the actual `aitask_zip_old_v2.sh` script with overridden directory
variables. It uses `--no-commit` flag since tests run outside a git repo.

**Important:** The v2 zip-old script reads `TASK_ARCHIVED_DIR` and `PLAN_ARCHIVED_DIR`.
Override these before invoking:

```bash
run_zip_old_v2() {
    local tmpdir="$1"
    shift
    TASK_DIR="$tmpdir/aitasks" \
    TASK_ARCHIVED_DIR="$tmpdir/aitasks/archived" \
    PLAN_ARCHIVED_DIR="$tmpdir/aiplans/archived" \
    ARCHIVED_DIR="$tmpdir/aitasks/archived" \
    ARCHIVED_PLAN_DIR="$tmpdir/aiplans/archived" \
    bash "$PROJECT_DIR/.aitask-scripts/aitask_zip_old_v2.sh" --no-commit "$@"
}
```

**14 test cases:**

| # | Test | Setup | Verify |
|---|------|-------|--------|
| 1 | Single task to correct bundle | `t50_old.md` in archived | `_b0/old0.tar.gz` contains it |
| 2 | Multi-bundle split | `t50_old.md` + `t150_old.md` | old0 has t50, old1 has t150 |
| 3 | Child tasks | `t130/t130_2_sub.md` in archived | old1 contains child |
| 4 | Plans separate | `p200_plan.md` in plan archived | Plan `_b0/old2.tar.gz` |
| 5 | Merge existing | Pre-existing `old0` + new t80 | old0 has both files |
| 6 | Archive integrity | After archiving | `tar -tzf` lists all expected |
| 7 | Originals removed | After archiving | Source `.md` files gone |
| 8 | Empty dirs cleaned | After archiving children | `t130/` dir gone |
| 9 | Dry run no changes | `--dry-run` flag | No `_bN` dirs created |
| 10 | Unpack numbered | Archive t50, then unpack | `t50_old.md` restored |
| 11 | Unpack legacy | t50 in legacy `old.tar.gz` | `t50_old.md` restored |
| 12 | Unpack removes from archive | Unpack from 2-file archive | Archive rebuilt sans file |
| 13 | High task IDs | `t1050_old.md` | `_b1/old10.tar.gz` |
| 14 | Corrupted archive | Write garbage to old0 | `.bak` file created |

Verification helper:
```bash
archive_contains() {
    local archive="$1"
    local pattern="$2"
    tar -tzf "$archive" 2>/dev/null | grep -qE "$pattern"
}
```

### Step 4: Implement `tests/test_archive_scan_v2.sh`

**File:** `tests/test_archive_scan_v2.sh`

Source setup:
```bash
source_scan_v2() {
    local tmpdir="$1"
    export SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
    unset _AIT_ARCHIVE_SCAN_V2_LOADED
    unset _AIT_ARCHIVE_UTILS_V2_LOADED
    source "$PROJECT_DIR/.aitask-scripts/lib/archive_scan_v2.sh"
}
```

**12 test cases:**

| # | Test | Setup | Assert |
|---|------|-------|--------|
| 1 | Max ID -- active only | `t200_test.md` in TASK_DIR | max = 200 |
| 2 | Max ID -- archived loose | `t300_test.md` in ARCHIVED_DIR | max = 300 |
| 3 | Max ID -- single numbered | old3 with t350 | max = 350 |
| 4 | Max ID -- multiple numbered | old0(t90), old1(t180), old2(t250) | max = 250 |
| 5 | Max ID -- legacy fallback | old.tar.gz with t400 | max = 400 |
| 6 | Max ID -- mixed sources | active t500 + archive t350 + legacy t200 | max = 500 |
| 7 | Max ID -- empty | No tasks anywhere | max = 0 |
| 8 | Search -- found numbered | t150 in old1 | `ARCHIVED_TASK_TAR_GZ:...old1...:...t150...` |
| 9 | Search -- found legacy | t150 in old.tar.gz | `ARCHIVED_TASK_TAR_GZ:...old.tar.gz:...` |
| 10 | Search -- not found | Empty archives | `NOT_FOUND` |
| 11 | Search -- O(1) correctness | t150 in old1, no old0 exists | Does not fail on missing old0 |
| 12 | Iter -- collects all | 3 numbered + legacy | Callback count matches total |

For test 12 (iter callback), use a simple counting function:
```bash
_test_iter_count=0
_test_iter_callback() {
    ((_test_iter_count++))
}
```

### Step 5: Run all tests and verify

```bash
bash tests/test_resolve_v2.sh
bash tests/test_zip_old_v2.sh
bash tests/test_archive_scan_v2.sh
```

All must show `ALL TESTS PASSED` and exit 0.

### Step 6: Cross-check with existing tests

Run the existing test suite to make sure v2 libraries don't break anything:

```bash
bash tests/test_resolve_tar_gz.sh
bash tests/test_claim_id.sh
```

Existing tests must still pass since v2 functions are additive (don't modify v1).

### Step 7: ShellCheck all test files

```bash
shellcheck tests/test_resolve_v2.sh
shellcheck tests/test_zip_old_v2.sh
shellcheck tests/test_archive_scan_v2.sh
```

Common test-file shellcheck issues:
- SC2034 (unused variables like PASS/FAIL) -- suppress with `# shellcheck disable=SC2034`
  if needed, or they'll be used in the summary block
- SC2030/SC2031 (modification in subshell) -- be careful with subshell tests

### Step 8: Update CLAUDE.md test list

Add the three new test files to the Testing section in `CLAUDE.md`:

```
bash tests/test_resolve_v2.sh
bash tests/test_zip_old_v2.sh
bash tests/test_archive_scan_v2.sh
```

Note: These will be renamed/merged during t433_7 (migration), but must be listed
while they exist as separate files.

### Step 9: Final Implementation Notes

_(To be filled in after implementation)_

- **Actual files created/modified:**
- **Issues encountered:**
- **Deviations from plan:**
- **ShellCheck result:**
- **Test results (all three files):**
