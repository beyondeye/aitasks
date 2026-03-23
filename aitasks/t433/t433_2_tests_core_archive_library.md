---
priority: high
effort: low
depends: [t433_1, t433_1]
issue_type: test
status: Implementing
labels: [task-archive]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-23 09:58
updated_at: 2026-03-23 11:25
---

## Tests for Core Archive Library

Create `tests/test_archive_utils_v2.sh` -- comprehensive tests for the path computation, search/extract primitives, and multi-archive operations in `archive_utils_v2.sh`.

### Context

This test file validates all functions from t433_1's `archive_utils_v2.sh`. It follows the exact pattern established in `tests/test_resolve_tar_gz.sh`: self-contained bash script with `assert_eq`/`assert_contains` helpers, temp directory setup, and PASS/FAIL summary.

### Key Files to Modify

- **NEW:** `tests/test_archive_utils_v2.sh` -- the entire deliverable

### Reference Files for Patterns

- `tests/test_resolve_tar_gz.sh` -- test structure to follow (helpers, setup, cleanup, summary)
- `.aitask-scripts/lib/archive_utils_v2.sh` -- the library under test (from t433_1)
- `.aitask-scripts/lib/task_utils.sh` lines 141-173 -- existing functions for comparison

### Implementation Plan

#### 1. Test scaffold (matching test_resolve_tar_gz.sh pattern)

```bash
#!/usr/bin/env bash
# test_archive_utils_v2.sh - Tests for archive_utils_v2.sh
# Run: bash tests/test_archive_utils_v2.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers (same as test_resolve_tar_gz.sh) ---
assert_eq() { ... }
assert_contains() { ... }
assert_exit_zero() { ... }
assert_exit_nonzero() { ... }
```

#### 2. Setup helpers

```bash
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

source_archive_utils() {
    export SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
    unset _AIT_ARCHIVE_UTILS_V2_LOADED
    # Reset temp dir from previous test
    if [[ -n "${_AIT_ARCHIVE_V2_TMPDIR:-}" && -d "$_AIT_ARCHIVE_V2_TMPDIR" ]]; then
        rm -rf "$_AIT_ARCHIVE_V2_TMPDIR"
    fi
    _AIT_ARCHIVE_V2_TMPDIR=""
    source "$PROJECT_DIR/.aitask-scripts/lib/archive_utils_v2.sh"
}
```

#### 3. Test categories

**A. Path computation -- `archive_bundle()`**

Test boundary values:
- Task 0 -> bundle 0
- Task 99 -> bundle 0
- Task 100 -> bundle 1
- Task 199 -> bundle 1
- Task 999 -> bundle 9
- Task 1000 -> bundle 10
- Task 1099 -> bundle 10
- Task 9999 -> bundle 99

**B. Path computation -- `archive_dir()`**

- Bundle 0 -> dir 0
- Bundle 9 -> dir 0
- Bundle 10 -> dir 1
- Bundle 19 -> dir 1
- Bundle 99 -> dir 9
- Bundle 100 -> dir 10

**C. Full path computation -- `archive_path_for_id()`**

- Task 0, base "archived" -> `archived/_b0/old0.tar.gz`
- Task 99, base "archived" -> `archived/_b0/old0.tar.gz`
- Task 100, base "archived" -> `archived/_b0/old1.tar.gz`
- Task 999, base "archived" -> `archived/_b0/old9.tar.gz`
- Task 1000, base "archived" -> `archived/_b1/old10.tar.gz`
- Task 5432, base "aitasks/archived" -> `aitasks/archived/_b5/old54.tar.gz`

**D. Single-archive search -- `_search_tar_gz_v2()`**

- Search existing archive for matching pattern -> returns filename
- Search existing archive for non-matching pattern -> returns empty
- Search non-existent archive -> returns empty (no error)

**E. Single-archive extract -- `_extract_from_tar_gz_v2()`**

- Extract file from archive -> file content matches original
- Temp dir is created and used for extraction
- Extracted path is set in `_AIT_V2_EXTRACT_RESULT`

**F. Multi-archive find -- `_find_archive_for_task()`**

- Archive exists at computed path -> returns path
- Archive does not exist -> returns empty

**G. Search all archives -- `_search_all_archives()`**

- Multiple archives with different tasks -> finds correct archive
- Pattern matches in multiple archives -> returns all matches
- No archives exist -> returns empty

**H. Legacy fallback -- `_search_legacy_then_v2()`**

- Only v2 archive exists -> finds via v2
- Only legacy old.tar.gz exists -> finds via legacy fallback
- Both exist -> v2 takes priority
- Neither exists -> returns empty

**I. Child task resolution**

- Task 130_2 -> parent ID 130 -> bundle 1 -> `_b0/old1.tar.gz`
- Search for `t130/t130_2_*.md` pattern within the correct archive
- Verify content after extraction

**J. Temp dir cleanup**

- After subshell exits, `_AIT_ARCHIVE_V2_TMPDIR` is cleaned up (same pattern as test_resolve_tar_gz.sh test 13)

### Verification Steps

1. **All tests pass:**
   ```bash
   bash tests/test_archive_utils_v2.sh
   ```
   Expected output ends with `ALL TESTS PASSED`.

2. **ShellCheck passes:**
   ```bash
   shellcheck tests/test_archive_utils_v2.sh
   ```

3. **Tests are self-contained:** can run from any directory, clean up temp dirs, no side effects.
