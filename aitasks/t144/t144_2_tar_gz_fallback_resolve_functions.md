---
priority: medium
effort: medium
depends: [t144_1, t144_1]
issue_type: feature
status: Implementing
labels: [aitasks, bash]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-17 10:48
updated_at: 2026-02-17 11:18
---

## Context

This is child 2 of t144 (ait clear_old rewrite). The resolve functions `resolve_task_file()` and `resolve_plan_file()` in `aiscripts/lib/task_utils.sh` currently only check active and uncompressed archived directories. They cannot find files inside `old.tar.gz`. This means `aitask_changelog.sh` and `aitask_issue_update.sh` break for tasks that have been zipped.

This child adds a tar.gz fallback to both resolve functions and creates comprehensive automated tests.

## Key Files to Modify

1. **`aiscripts/lib/task_utils.sh`** — Add tar.gz search/extract helpers and fallback logic to `resolve_task_file()` and `resolve_plan_file()`

## New Files to Create

1. **`tests/test_resolve_tar_gz.sh`** — Automated test file (see test cases below)

## Reference Files for Patterns

- `aiscripts/aitask_stats.sh` (line 418-431): Example of `tar -xzf ... -O` extraction pattern
- `tests/test_task_lock.sh`: Test file structure pattern (assert helpers, isolated temp dirs, setup/teardown)
- `aiscripts/aitask_claim_id.sh` (lines 36-65): `scan_max_task_id()` already searches inside tar.gz

## Implementation Plan

### Step 1: Add temp directory management to task_utils.sh

Add near the top (after guard and source lines):
```bash
_AIT_TASK_UTILS_TMPDIR=""
_ait_task_utils_cleanup() {
    [[ -n "$_AIT_TASK_UTILS_TMPDIR" && -d "$_AIT_TASK_UTILS_TMPDIR" ]] && rm -rf "$_AIT_TASK_UTILS_TMPDIR"
}
trap _ait_task_utils_cleanup EXIT
```

### Step 2: Add helper functions

```bash
# Search for a file matching a pattern inside a tar.gz archive
# Args: $1=archive_path, $2=grep_pattern
# Output: matching filename inside the tar (first match), or empty
_search_tar_gz() {
    local archive="$1"
    local pattern="$2"
    [[ -f "$archive" ]] || return 0
    tar -tzf "$archive" 2>/dev/null | grep -E "$pattern" | head -1
}

# Extract a file from tar.gz to a temp location and echo the temp path
# Args: $1=archive_path, $2=filename_inside_tar
# Output: path to extracted temp file
_extract_from_tar_gz() {
    local archive="$1"
    local filename="$2"
    if [[ -z "$_AIT_TASK_UTILS_TMPDIR" ]]; then
        _AIT_TASK_UTILS_TMPDIR=$(mktemp -d)
    fi
    local dest="$_AIT_TASK_UTILS_TMPDIR/$(basename "$filename")"
    tar -xzf "$archive" -O "$filename" > "$dest" 2>/dev/null
    echo "$dest"
}
```

### Step 3: Add tar.gz fallback to resolve_task_file()

After checking archived dir, before the `die` call:
- For child tasks: search `$ARCHIVED_DIR/old.tar.gz` for pattern `(^|/)t${parent_num}/t${parent_num}_${child_num}_.*\.md$`
- For parent tasks: search for pattern `(^|/)t${task_id}_.*\.md$`
- If found, extract and return temp path

**IMPORTANT:** Files in tar.gz have `./` prefix (from `tar -czf ... -C "$temp_dir" .`). Patterns must handle both `./t50_test.md` and `t50_test.md`.

### Step 4: Add tar.gz fallback to resolve_plan_file()

Same pattern as step 3 but using `$ARCHIVED_PLAN_DIR/old.tar.gz` and `p` prefix.

### Step 5: Create tests/test_resolve_tar_gz.sh

Test cases (14 total):
1. Resolve parent task from active dir
2. Resolve parent task from archived dir
3. Resolve parent task from tar.gz — verify content matches
4. Resolve child task from active dir
5. Resolve child task from archived dir
6. Resolve child task from tar.gz — verify content
7. Resolve parent plan from tar.gz
8. Resolve child plan from tar.gz
9. Priority: active dir wins over tar.gz
10. Priority: archived dir wins over tar.gz
11. Not found anywhere: parent task dies (non-zero exit)
12. Not found anywhere: plan returns empty string
13. Temp file cleanup after shell exits
14. extract_final_implementation_notes works on tar.gz-extracted file

## Verification Steps

- `bash -n aiscripts/lib/task_utils.sh` (syntax check)
- `bash tests/test_resolve_tar_gz.sh` (run all 14 tests)
- `bash tests/test_terminal_compat.sh` (no regressions)
