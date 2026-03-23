---
priority: high
effort: medium
depends: [t433_1]
issue_type: refactor
status: Implementing
labels: [task-archive]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-23 09:58
updated_at: 2026-03-23 11:57
---

## Context

Parent task t433 is refactoring the task archive system from a single `old.tar.gz` to numbered archives using 0-indexed bundling:

```
bundle = task_id / 100       (integer division)
dir    = bundle / 10          (integer division)
path   = archived/_b{dir}/old{bundle}.tar.gz
```

The current resolve functions in `task_utils.sh` (lines 180-304) implement a three-tier lookup: active directory, archived directory, then a single hardcoded `old.tar.gz`. This task creates v2 resolve functions that replace the hardcoded tar.gz lookup with the multi-archive search primitives from `archive_utils_v2.sh` (t433_1).

The v2 functions are created in a separate file so that the existing resolve functions continue to work during development. The migration task (t433_7) will swap them in.

## Key Files to Modify

- `.aitask-scripts/lib/task_resolve_v2.sh` (new) -- v2 resolve functions using numbered archives

## Reference Files for Patterns

- `.aitask-scripts/lib/task_utils.sh` lines 180-240 -- current `resolve_task_file()` with three-tier lookup
- `.aitask-scripts/lib/task_utils.sh` lines 248-304 -- current `resolve_plan_file()` with three-tier lookup
- `.aitask-scripts/lib/task_utils.sh` lines 141-173 -- current `_search_tar_gz()` and `_extract_from_tar_gz()` (to be replaced by v2 equivalents)
- `.aitask-scripts/lib/archive_utils_v2.sh` (t433_1) -- provides `_find_archive_for_task()`, `_search_legacy_then_v2()`, `_search_tar_gz_v2()`, `_extract_from_tar_gz_v2()`

## Implementation Plan

### Step 1: File skeleton and guard

Create `.aitask-scripts/lib/task_resolve_v2.sh`:

```bash
#!/usr/bin/env bash
# task_resolve_v2.sh - V2 task/plan resolution using numbered archives
# Source this file from aitask scripts; do not execute directly.

# --- Guard against double-sourcing ---
[[ -n "${_AIT_TASK_RESOLVE_V2_LOADED:-}" ]] && return 0
_AIT_TASK_RESOLVE_V2_LOADED=1
```

Source dependencies: `terminal_compat.sh` (for `die`/`warn`/`info`) and `archive_utils_v2.sh` (for archive search primitives). Use the standard `SCRIPT_DIR` pattern. Do NOT source `task_utils.sh` -- the resolve v2 file should be independently sourceable, using the same `TASK_DIR`, `ARCHIVED_DIR`, `PLAN_DIR`, `ARCHIVED_PLAN_DIR` variables that `task_utils.sh` defines.

Set default directory variables (same defaults as task_utils.sh):

```bash
TASK_DIR="${TASK_DIR:-aitasks}"
ARCHIVED_DIR="${ARCHIVED_DIR:-aitasks/archived}"
PLAN_DIR="${PLAN_DIR:-aiplans}"
ARCHIVED_PLAN_DIR="${ARCHIVED_PLAN_DIR:-aiplans/archived}"
```

### Step 2: Implement resolve_task_file_v2()

```bash
# Resolve task number to file path, checking active, archived, and numbered archives.
# Input: task_id (e.g., "53" or "53_6")
# Output: file path (prints to stdout)
# Dies if not found or if multiple matches found.
resolve_task_file_v2() {
    local task_id="$1"
    local files=""

    if [[ "$task_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        # --- Child task ---
        local parent_num="${BASH_REMATCH[1]}"
        local child_num="${BASH_REMATCH[2]}"

        # Tier 1: active directory
        files=$(ls "$TASK_DIR"/t${parent_num}/t${parent_num}_${child_num}_*.md 2>/dev/null || true)

        # Tier 2: archived directory (loose files)
        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_DIR"/t${parent_num}/t${parent_num}_${child_num}_*.md 2>/dev/null || true)
        fi

        # Tier 3: numbered archives via _find_archive_for_task()
        if [[ -z "$files" ]]; then
            local tar_match
            tar_match=$(_find_archive_for_task "$ARCHIVED_DIR" "$parent_num" "(^|/)t${parent_num}/t${parent_num}_${child_num}_.*\\.md$")
            if [[ -n "$tar_match" ]]; then
                _extract_from_tar_gz_v2 "$(_archive_path_containing "$ARCHIVED_DIR" "$parent_num" "$tar_match")" "$tar_match"
                files="$_AIT_EXTRACT_RESULT"
            fi
        fi

        if [[ -z "$files" ]]; then
            die "No task file found for t${parent_num}_${child_num} (checked active, archived, and numbered archives)"
        fi
    else
        # --- Parent task ---
        # Tier 1: active directory
        files=$(ls "$TASK_DIR"/t${task_id}_*.md 2>/dev/null || true)

        # Tier 2: archived directory (loose files)
        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_DIR"/t${task_id}_*.md 2>/dev/null || true)
        fi

        # Tier 3: numbered archives
        if [[ -z "$files" ]]; then
            local tar_match
            tar_match=$(_find_archive_for_task "$ARCHIVED_DIR" "$task_id" "(^|/)t${task_id}_.*\\.md$")
            if [[ -n "$tar_match" ]]; then
                _extract_from_tar_gz_v2 "$(_archive_path_containing "$ARCHIVED_DIR" "$task_id" "$tar_match")" "$tar_match"
                files="$_AIT_EXTRACT_RESULT"
            fi
        fi

        if [[ -z "$files" ]]; then
            die "No task file found for task number $task_id (checked active, archived, and numbered archives)"
        fi
    fi

    local count
    count=$(echo "$files" | wc -l)
    if [[ "$count" -gt 1 ]]; then
        die "Multiple task files found for task $task_id"
    fi

    echo "$files"
}
```

Key differences from v1:
- Tier 3 calls `_find_archive_for_task()` (from archive_utils_v2.sh) which computes the correct numbered archive path using `archive_path_for_id()`, falling back to legacy `old.tar.gz` via `_search_legacy_then_v2()`.
- Error messages mention "numbered archives" instead of "tar.gz".

**Implementation note:** The exact API of `_find_archive_for_task()` from t433_1 determines how the archive path and internal filename are obtained. The function should return the internal filename, and we need a way to get back to the archive path. Two options:
1. `_find_archive_for_task()` sets both `_AIT_FOUND_ARCHIVE` (path) and returns the match.
2. Use `archive_path_for_id()` directly to compute the path, then search it.

Prefer option 2 for simplicity: compute the archive path with `archive_path_for_id()`, call `_search_tar_gz_v2()` on it, and if empty, fall back to legacy. This avoids coupling to internal variables.

Revised Tier 3 approach:

```bash
# Tier 3: numbered archives (v2 path, then legacy fallback)
if [[ -z "$files" ]]; then
    local archive_path tar_match
    archive_path=$(archive_path_for_id "$ARCHIVED_DIR" "$task_id")
    tar_match=$(_search_tar_gz_v2 "$archive_path" "(^|/)t${task_id}_.*\\.md$")
    # Legacy fallback: check old.tar.gz
    if [[ -z "$tar_match" && -f "$ARCHIVED_DIR/old.tar.gz" ]]; then
        archive_path="$ARCHIVED_DIR/old.tar.gz"
        tar_match=$(_search_tar_gz_v2 "$archive_path" "(^|/)t${task_id}_.*\\.md$")
    fi
    if [[ -n "$tar_match" ]]; then
        _extract_from_tar_gz_v2 "$archive_path" "$tar_match"
        files="$_AIT_EXTRACT_RESULT"
    fi
fi
```

### Step 3: Implement resolve_plan_file_v2()

Same structure as `resolve_task_file_v2()` but for plan files:

```bash
# Resolve plan file from task number, checking active, archived, and numbered archives.
# Plan naming convention:
#   Parent task t53_name.md -> plan p53_name.md
#   Child task t53/t53_1_name.md -> plan p53/p53_1_name.md
# Input: task_id (e.g., "53" or "53_6")
# Output: file path or empty string if not found
resolve_plan_file_v2() {
    local task_id="$1"
    local files=""

    if [[ "$task_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local parent_num="${BASH_REMATCH[1]}"
        local child_num="${BASH_REMATCH[2]}"

        # Tier 1: active plan directory
        files=$(ls "$PLAN_DIR"/p${parent_num}/p${parent_num}_${child_num}_*.md 2>/dev/null || true)

        # Tier 2: archived plan directory
        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_PLAN_DIR"/p${parent_num}/p${parent_num}_${child_num}_*.md 2>/dev/null || true)
        fi

        # Tier 3: numbered archives
        if [[ -z "$files" ]]; then
            local archive_path tar_match
            archive_path=$(archive_path_for_id "$ARCHIVED_PLAN_DIR" "$parent_num")
            tar_match=$(_search_tar_gz_v2 "$archive_path" "(^|/)p${parent_num}/p${parent_num}_${child_num}_.*\\.md$")
            if [[ -z "$tar_match" && -f "$ARCHIVED_PLAN_DIR/old.tar.gz" ]]; then
                archive_path="$ARCHIVED_PLAN_DIR/old.tar.gz"
                tar_match=$(_search_tar_gz_v2 "$archive_path" "(^|/)p${parent_num}/p${parent_num}_${child_num}_.*\\.md$")
            fi
            if [[ -n "$tar_match" ]]; then
                _extract_from_tar_gz_v2 "$archive_path" "$tar_match"
                files="$_AIT_EXTRACT_RESULT"
            fi
        fi
    else
        # Parent plan
        files=$(ls "$PLAN_DIR"/p${task_id}_*.md 2>/dev/null || true)

        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_PLAN_DIR"/p${task_id}_*.md 2>/dev/null || true)
        fi

        # Tier 3: numbered archives
        if [[ -z "$files" ]]; then
            local archive_path tar_match
            archive_path=$(archive_path_for_id "$ARCHIVED_PLAN_DIR" "$task_id")
            tar_match=$(_search_tar_gz_v2 "$archive_path" "(^|/)p${task_id}_.*\\.md$")
            if [[ -z "$tar_match" && -f "$ARCHIVED_PLAN_DIR/old.tar.gz" ]]; then
                archive_path="$ARCHIVED_PLAN_DIR/old.tar.gz"
                tar_match=$(_search_tar_gz_v2 "$archive_path" "(^|/)p${task_id}_.*\\.md$")
            fi
            if [[ -n "$tar_match" ]]; then
                _extract_from_tar_gz_v2 "$archive_path" "$tar_match"
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

Key differences from v1:
- Uses `archive_path_for_id()` + `_search_tar_gz_v2()` with legacy `old.tar.gz` fallback.
- Returns empty string (not die) when not found -- same behavior as v1 `resolve_plan_file()`.

### Step 4: Temp directory management

Reuse the same cleanup pattern as current `task_utils.sh`:

```bash
_AIT_TASK_RESOLVE_V2_TMPDIR=""
_ait_task_resolve_v2_cleanup() {
    if [[ -n "$_AIT_TASK_RESOLVE_V2_TMPDIR" && -d "$_AIT_TASK_RESOLVE_V2_TMPDIR" ]]; then
        rm -rf "$_AIT_TASK_RESOLVE_V2_TMPDIR"
    fi
}
trap _ait_task_resolve_v2_cleanup EXIT
```

Note: If `archive_utils_v2.sh` already manages its own temp directory and cleanup via `_extract_from_tar_gz_v2`, this step may be unnecessary. Coordinate with t433_1 to confirm whether `_extract_from_tar_gz_v2` uses a shared global tmpdir or requires callers to manage it. If `_extract_from_tar_gz_v2` sets `_AIT_EXTRACT_RESULT` and manages its own temp, skip this step.

### Step 5: Extract shared helper for archive fallback pattern

Both resolve functions repeat the same "try v2 path, fall back to legacy" pattern. Extract a helper:

```bash
# Search for a file in numbered archives, falling back to legacy old.tar.gz
# Args: $1=base_archived_dir, $2=task_or_parent_id, $3=grep_pattern
# Sets: _AIT_RESOLVE_V2_ARCHIVE (path of archive containing the match)
# Output: matching filename inside the archive, or empty
_resolve_v2_search_archives() {
    local base_dir="$1"
    local id="$2"
    local pattern="$3"
    local archive_path tar_match

    archive_path=$(archive_path_for_id "$base_dir" "$id")
    tar_match=$(_search_tar_gz_v2 "$archive_path" "$pattern")

    if [[ -z "$tar_match" && -f "$base_dir/old.tar.gz" ]]; then
        archive_path="$base_dir/old.tar.gz"
        tar_match=$(_search_tar_gz_v2 "$archive_path" "$pattern")
    fi

    _AIT_RESOLVE_V2_ARCHIVE="$archive_path"
    echo "$tar_match"
}
```

Then in each resolve function, Tier 3 becomes:

```bash
if [[ -z "$files" ]]; then
    local tar_match
    tar_match=$(_resolve_v2_search_archives "$ARCHIVED_DIR" "$task_id" "(^|/)t${task_id}_.*\\.md$")
    if [[ -n "$tar_match" ]]; then
        _extract_from_tar_gz_v2 "$_AIT_RESOLVE_V2_ARCHIVE" "$tar_match"
        files="$_AIT_EXTRACT_RESULT"
    fi
fi
```

This reduces duplication and keeps the resolve functions clean.

## Verification Steps

1. **Shellcheck passes:** `shellcheck .aitask-scripts/lib/task_resolve_v2.sh`
2. **Source test:** Source the file in a subshell and verify no errors:
   ```bash
   ( source .aitask-scripts/lib/task_resolve_v2.sh && echo "OK" )
   ```
3. **Active task resolution:** Verify `resolve_task_file_v2 <N>` returns same result as `resolve_task_file <N>` for an active task
4. **Archived task resolution:** Verify for a task that exists as a loose file in `archived/`
5. **Archive resolution:** Create a test numbered archive with a known task file, verify resolve finds it
6. **Legacy fallback:** Verify that tasks in `old.tar.gz` are still found when no numbered archive matches
7. **Plan resolution:** Same checks for `resolve_plan_file_v2`
8. **Not-found behavior:** Verify `resolve_task_file_v2` dies for nonexistent task; `resolve_plan_file_v2` returns empty string
9. **Integration with t433_2 test suite** -- coordinate to ensure test coverage
