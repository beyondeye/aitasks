---
Task: t144_2_tar_gz_fallback_resolve_functions.md
Parent Task: aitasks/t144_ait_clear_old_rewrite.md
Sibling Tasks: aitasks/t144/t144_3_rewrite_selection_logic.md
Archived Sibling Plans: aiplans/archived/p144/p144_1_rename_clear_old_to_zip_old.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

The `resolve_task_file()` and `resolve_plan_file()` functions in `aiscripts/lib/task_utils.sh` only search active and archived directories. Files that have been compressed into `old.tar.gz` by `aitask_zip_old.sh` are invisible to these functions, breaking `aitask_changelog.sh` and `aitask_issue_update.sh` for zipped tasks.

This plan adds tar.gz fallback search to both resolve functions and creates comprehensive tests.

## Files to Modify

- **`aiscripts/lib/task_utils.sh`** — Add tar.gz helpers and fallback logic

## Files to Create

- **`tests/test_resolve_tar_gz.sh`** — 14 automated test cases

## Implementation Steps

### Step 1: Add temp directory management (task_utils.sh, after line 18)

```bash
_AIT_TASK_UTILS_TMPDIR=""
_ait_task_utils_cleanup() {
    [[ -n "$_AIT_TASK_UTILS_TMPDIR" && -d "$_AIT_TASK_UTILS_TMPDIR" ]] && rm -rf "$_AIT_TASK_UTILS_TMPDIR"
}
trap _ait_task_utils_cleanup EXIT
```

Currently sourced by `aitask_changelog.sh` and `aitask_issue_update.sh` — neither has an EXIT trap, so no conflict.

### Step 2: Add helper functions (after temp dir management)

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

### Step 3: Add tar.gz fallback to `resolve_task_file()`

After the archived directory check and before each `die` call, add:

**For child tasks** (after line 38, before line 41):
```bash
# Check tar.gz archive
if [[ -z "$files" ]]; then
    local tar_match
    tar_match=$(_search_tar_gz "$ARCHIVED_DIR/old.tar.gz" "(^|/)t${parent_num}/t${parent_num}_${child_num}_.*\.md$")
    if [[ -n "$tar_match" ]]; then
        files=$(_extract_from_tar_gz "$ARCHIVED_DIR/old.tar.gz" "$tar_match")
    fi
fi
```

**For parent tasks** (after line 49, before line 52):
```bash
# Check tar.gz archive
if [[ -z "$files" ]]; then
    local tar_match
    tar_match=$(_search_tar_gz "$ARCHIVED_DIR/old.tar.gz" "(^|/)t${task_id}_.*\.md$")
    if [[ -n "$tar_match" ]]; then
        files=$(_extract_from_tar_gz "$ARCHIVED_DIR/old.tar.gz" "$tar_match")
    fi
fi
```

**Note:** Patterns use `(^|/)` prefix to handle both `./t50_test.md` and `t50_test.md` formats (the archive uses `tar -czf ... -C "$temp_dir" .` which creates `./` prefixed paths).

### Step 4: Add tar.gz fallback to `resolve_plan_file()`

Same pattern as step 3 but using `$ARCHIVED_PLAN_DIR/old.tar.gz` and `p` prefix patterns.

**For child plans** (after line 86, before line 88):
```bash
# Check tar.gz archive
if [[ -z "$files" ]]; then
    local tar_match
    tar_match=$(_search_tar_gz "$ARCHIVED_PLAN_DIR/old.tar.gz" "(^|/)p${parent_num}/p${parent_num}_${child_num}_.*\.md$")
    if [[ -n "$tar_match" ]]; then
        files=$(_extract_from_tar_gz "$ARCHIVED_PLAN_DIR/old.tar.gz" "$tar_match")
    fi
fi
```

**For parent plans** (after line 93, before line 95):
```bash
if [[ -z "$files" ]]; then
    local tar_match
    tar_match=$(_search_tar_gz "$ARCHIVED_PLAN_DIR/old.tar.gz" "(^|/)p${task_id}_.*\.md$")
    if [[ -n "$tar_match" ]]; then
        files=$(_extract_from_tar_gz "$ARCHIVED_PLAN_DIR/old.tar.gz" "$tar_match")
    fi
fi
```

### Step 5: Create `tests/test_resolve_tar_gz.sh`

14 test cases following the pattern from `tests/test_task_lock.sh`:

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
14. `extract_final_implementation_notes` works on tar.gz-extracted file

**Test setup helper** creates:
- Temp dir with `aitasks/`, `aitasks/archived/`, `aiplans/`, `aiplans/archived/` structure
- Populates active/archived dirs with test .md files
- Creates `old.tar.gz` archives using same method as `archive_files()` (`tar -czf ... -C "$temp_dir" .`)
- Sources `task_utils.sh` with overridden `TASK_DIR`, `ARCHIVED_DIR`, `PLAN_DIR`, `ARCHIVED_PLAN_DIR`

## Verification

- `bash -n aiscripts/lib/task_utils.sh` (syntax check)
- `bash tests/test_resolve_tar_gz.sh` (run all 14 tests)
- `bash tests/test_terminal_compat.sh` (no regressions)

## Final Implementation Notes

- **Actual work done:** All 5 steps completed. Added temp dir management, `_search_tar_gz()` and `_extract_from_tar_gz()` helpers, tar.gz fallback to both `resolve_task_file()` and `resolve_plan_file()`, and 14 comprehensive test cases.
- **Deviations from plan:** Changed `_extract_from_tar_gz()` from returning via `echo` (command substitution) to setting a global `_AIT_EXTRACT_RESULT` variable. This was necessary because `files=$(_extract_from_tar_gz ...)` runs in a subshell, so `_AIT_TASK_UTILS_TMPDIR` would never be set in the parent shell, breaking EXIT trap cleanup. The fix avoids the subshell entirely.
- **Issues encountered:** Test 13 (temp cleanup) initially failed because of the subshell issue described above. Fixed by redesigning `_extract_from_tar_gz` to use a global result variable.
- **Key decisions:** Patterns use `(^|/)` prefix to handle both `./t50_test.md` and `t50_test.md` formats inside tar.gz archives. Error messages updated to mention "tar.gz" in the checked locations.
- **Notes for sibling tasks:** The `_search_tar_gz()` and `_extract_from_tar_gz()` helpers in `task_utils.sh` are available for reuse by t144_3 if needed. The tar.gz archives use `./` path prefix (created by `tar -czf ... -C "$temp_dir" .`). `_extract_from_tar_gz` must be called WITHOUT `$()` command substitution to preserve tmpdir variable in caller shell.

## Step 9 (Post-Implementation)

Archive child task, update parent's children_to_implement, check if all children done.
