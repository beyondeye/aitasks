---
Task: t433_3_v2_resolve_functions.md
Parent Task: aitasks/t433_refactor_task_archives.md
Sibling Tasks: aitasks/t433/t433_*_*.md
Worktree: (none -- current branch)
Branch: (current)
Base branch: main
---

## Context

Create `.aitask-scripts/lib/task_resolve_v2.sh` containing v2 resolve functions that use the numbered archive system (from t433_1's `archive_utils_v2.sh`) instead of the hardcoded `old.tar.gz` path. The existing `resolve_task_file()` and `resolve_plan_file()` in `task_utils.sh` remain untouched -- the v2 versions run in parallel during development.

## Dependencies

- **t433_1** (archive_utils_v2.sh) must be complete -- provides `archive_path_for_id()`, `_search_tar_gz_v2()`, `_extract_from_tar_gz_v2()`

## Implementation

### Step 1: Create file with guard and source dependencies

Create `.aitask-scripts/lib/task_resolve_v2.sh`:

```bash
#!/usr/bin/env bash
# task_resolve_v2.sh - V2 task/plan resolution using numbered archives
# Source this file from aitask scripts; do not execute directly.

# --- Guard against double-sourcing ---
[[ -n "${_AIT_TASK_RESOLVE_V2_LOADED:-}" ]] && return 0
_AIT_TASK_RESOLVE_V2_LOADED=1

SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
source "${SCRIPT_DIR}/lib/terminal_compat.sh"
source "${SCRIPT_DIR}/lib/archive_utils_v2.sh"

TASK_DIR="${TASK_DIR:-aitasks}"
ARCHIVED_DIR="${ARCHIVED_DIR:-aitasks/archived}"
PLAN_DIR="${PLAN_DIR:-aiplans}"
ARCHIVED_PLAN_DIR="${ARCHIVED_PLAN_DIR:-aiplans/archived}"
```

### Step 2: Implement _resolve_v2_search_archives() helper

This private helper encapsulates the "try numbered archive, fall back to legacy" pattern:

```bash
# Search for a file in numbered archives, falling back to legacy old.tar.gz
# Args: $1=base_archived_dir, $2=task_or_parent_id (numeric), $3=grep_pattern
# Sets: _AIT_RESOLVE_V2_ARCHIVE (path of archive containing the match)
# Output: matching filename inside the archive (first match), or empty
_resolve_v2_search_archives() {
    local base_dir="$1"
    local id="$2"
    local pattern="$3"
    local archive_path tar_match

    # Try computed numbered archive path first
    archive_path=$(archive_path_for_id "$base_dir" "$id")
    tar_match=$(_search_tar_gz_v2 "$archive_path" "$pattern")

    # Fall back to legacy old.tar.gz
    if [[ -z "$tar_match" && -f "$base_dir/old.tar.gz" ]]; then
        archive_path="$base_dir/old.tar.gz"
        tar_match=$(_search_tar_gz_v2 "$archive_path" "$pattern")
    fi

    _AIT_RESOLVE_V2_ARCHIVE="$archive_path"
    echo "$tar_match"
}
```

### Step 3: Implement resolve_task_file_v2()

Three-tier resolution: active -> archived loose -> numbered archives.

```bash
resolve_task_file_v2() {
    local task_id="$1"
    local files=""

    if [[ "$task_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local parent_num="${BASH_REMATCH[1]}"
        local child_num="${BASH_REMATCH[2]}"

        # Tier 1: active
        files=$(ls "$TASK_DIR"/t${parent_num}/t${parent_num}_${child_num}_*.md 2>/dev/null || true)
        # Tier 2: archived loose
        [[ -z "$files" ]] && files=$(ls "$ARCHIVED_DIR"/t${parent_num}/t${parent_num}_${child_num}_*.md 2>/dev/null || true)
        # Tier 3: numbered archives
        if [[ -z "$files" ]]; then
            local tar_match
            tar_match=$(_resolve_v2_search_archives "$ARCHIVED_DIR" "$parent_num" \
                "(^|/)t${parent_num}/t${parent_num}_${child_num}_.*\\.md$")
            if [[ -n "$tar_match" ]]; then
                _extract_from_tar_gz_v2 "$_AIT_RESOLVE_V2_ARCHIVE" "$tar_match"
                files="$_AIT_EXTRACT_RESULT"
            fi
        fi
        [[ -z "$files" ]] && die "No task file found for t${parent_num}_${child_num} (checked active, archived, and numbered archives)"
    else
        # Parent task
        files=$(ls "$TASK_DIR"/t${task_id}_*.md 2>/dev/null || true)
        [[ -z "$files" ]] && files=$(ls "$ARCHIVED_DIR"/t${task_id}_*.md 2>/dev/null || true)
        if [[ -z "$files" ]]; then
            local tar_match
            tar_match=$(_resolve_v2_search_archives "$ARCHIVED_DIR" "$task_id" \
                "(^|/)t${task_id}_.*\\.md$")
            if [[ -n "$tar_match" ]]; then
                _extract_from_tar_gz_v2 "$_AIT_RESOLVE_V2_ARCHIVE" "$tar_match"
                files="$_AIT_EXTRACT_RESULT"
            fi
        fi
        [[ -z "$files" ]] && die "No task file found for task number $task_id (checked active, archived, and numbered archives)"
    fi

    local count
    count=$(echo "$files" | wc -l)
    [[ "$count" -gt 1 ]] && die "Multiple task files found for task $task_id"
    echo "$files"
}
```

### Step 4: Implement resolve_plan_file_v2()

Same structure, but returns empty string instead of dying when not found (matching v1 behavior):

```bash
resolve_plan_file_v2() {
    local task_id="$1"
    local files=""

    if [[ "$task_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local parent_num="${BASH_REMATCH[1]}"
        local child_num="${BASH_REMATCH[2]}"

        files=$(ls "$PLAN_DIR"/p${parent_num}/p${parent_num}_${child_num}_*.md 2>/dev/null || true)
        [[ -z "$files" ]] && files=$(ls "$ARCHIVED_PLAN_DIR"/p${parent_num}/p${parent_num}_${child_num}_*.md 2>/dev/null || true)
        if [[ -z "$files" ]]; then
            local tar_match
            tar_match=$(_resolve_v2_search_archives "$ARCHIVED_PLAN_DIR" "$parent_num" \
                "(^|/)p${parent_num}/p${parent_num}_${child_num}_.*\\.md$")
            if [[ -n "$tar_match" ]]; then
                _extract_from_tar_gz_v2 "$_AIT_RESOLVE_V2_ARCHIVE" "$tar_match"
                files="$_AIT_EXTRACT_RESULT"
            fi
        fi
    else
        files=$(ls "$PLAN_DIR"/p${task_id}_*.md 2>/dev/null || true)
        [[ -z "$files" ]] && files=$(ls "$ARCHIVED_PLAN_DIR"/p${task_id}_*.md 2>/dev/null || true)
        if [[ -z "$files" ]]; then
            local tar_match
            tar_match=$(_resolve_v2_search_archives "$ARCHIVED_PLAN_DIR" "$task_id" \
                "(^|/)p${task_id}_.*\\.md$")
            if [[ -n "$tar_match" ]]; then
                _extract_from_tar_gz_v2 "$_AIT_RESOLVE_V2_ARCHIVE" "$tar_match"
                files="$_AIT_EXTRACT_RESULT"
            fi
        fi
    fi

    if [[ -z "$files" ]]; then
        echo ""
        return
    fi

    local count
    count=$(echo "$files" | wc -l)
    if [[ "$count" -gt 1 ]]; then
        echo "$files" | head -1
    else
        echo "$files"
    fi
}
```

### Step 5: Shellcheck and manual testing

1. Run `shellcheck .aitask-scripts/lib/task_resolve_v2.sh`
2. Fix any issues (quoting, unused vars, etc.)
3. Manual source test: `( source .aitask-scripts/lib/task_resolve_v2.sh && echo OK )`

### Step 6: Equivalence testing with v1

For each active and archived task, verify v2 returns the same result as v1:

```bash
# Quick equivalence check
for id in 50 130 433; do
    v1=$(resolve_task_file "$id" 2>/dev/null || echo "NOT_FOUND")
    v2=$(resolve_task_file_v2 "$id" 2>/dev/null || echo "NOT_FOUND")
    [[ "$v1" == "$v2" ]] || echo "MISMATCH: $id v1=$v1 v2=$v2"
done
```

### Step 7: Coordinate with t433_1 API

Confirm the exact function signatures from `archive_utils_v2.sh`:

- `archive_path_for_id(base_dir, task_id)` -> echoes path string
- `_search_tar_gz_v2(archive_path, pattern)` -> echoes match or empty
- `_extract_from_tar_gz_v2(archive_path, filename)` -> sets `_AIT_EXTRACT_RESULT`

If t433_1 changes any signatures, update the resolve functions accordingly.

## Final Implementation Notes

- **Actual work done:** Created `.aitask-scripts/lib/task_resolve_v2.sh` (178 lines) with guard variable, dependency sourcing, directory defaults, `_resolve_v2_search_archives()` helper, `resolve_task_file_v2()`, and `resolve_plan_file_v2()`. All functions mirror the v1 API from `task_utils.sh` but use numbered archive lookup via `archive_utils_v2.sh`.
- **Deviations from plan:** Two bugs in the plan were corrected during implementation:
  1. `archive_path_for_id` argument order was reversed in the plan — plan said `(base_dir, id)` but actual API is `(task_id, archived_dir)`. Fixed to `archive_path_for_id "$id" "$base_dir"`.
  2. Extract result variable was wrong — plan used `$_AIT_EXTRACT_RESULT` (v1) but actual v2 API sets `$_AIT_V2_EXTRACT_RESULT`. Fixed throughout.
- **Issues encountered:** None. ShellCheck clean (SC1091/SC2086 info-level only, same as v1). Source test passes. All 42 existing archive_utils_v2 tests pass.
- **Key decisions:** Used `_AIT_RESOLVE_V2_ARCHIVE` as a "return" variable from the helper to avoid subshell overhead. Kept the same glob pattern style as v1 (unquoted `${parent_num}` in path globs) for consistency.
- **Notes for sibling tasks:** The library is ready to source via `source "${SCRIPT_DIR}/lib/task_resolve_v2.sh"`. Sibling tasks (t433_4 zip-old, t433_5 scanners) can use it for resolve operations. The `_resolve_v2_search_archives()` helper encapsulates the "try numbered, fall back to legacy" pattern and can serve as a reference for similar patterns in other scripts. The correct `archive_path_for_id` argument order is `(task_id, archived_dir)` — NOT what the original task description suggests. Also use `_AIT_V2_EXTRACT_RESULT` (not `_AIT_EXTRACT_RESULT`) after calling `_extract_from_tar_gz_v2`.
