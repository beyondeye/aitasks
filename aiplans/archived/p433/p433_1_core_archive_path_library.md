---
Task: t433_1_core_archive_path_library.md
Parent Task: aitasks/t433_refactor_task_archives.md
Sibling Tasks: aitasks/t433/t433_2_*.md through t433_7_*.md
Worktree: (none — current branch)
Branch: (current)
Base branch: main
---

## Implementation Plan: Core Archive Path Library

### Goal

Create `.aitask-scripts/lib/archive_utils_v2.sh` -- a standalone shell library providing:
1. Pure arithmetic path computation (bundle, dir, full path)
2. Single-archive search/extract primitives (matching existing `_search_tar_gz`/`_extract_from_tar_gz` API)
3. Multi-archive operations (O(1) lookup, scan-all, legacy fallback)

This is the foundation for all subsequent t433 sibling tasks.

### Step 1: Create file scaffold

**File:** `.aitask-scripts/lib/archive_utils_v2.sh`

```bash
#!/usr/bin/env bash
# archive_utils_v2.sh - Numbered archive path computation and search/extract primitives
# Source this file from aitask scripts; do not execute directly.
#
# Numbering scheme (0-indexed):
#   bundle = task_id / 100
#   dir    = bundle / 10
#   path   = archived/_b{dir}/old{bundle}.tar.gz
#
# Examples:
#   Task 0..99   -> archived/_b0/old0.tar.gz
#   Task 100..199 -> archived/_b0/old1.tar.gz
#   Task 1000..1099 -> archived/_b1/old10.tar.gz

# --- Guard against double-sourcing ---
[[ -n "${_AIT_ARCHIVE_UTILS_V2_LOADED:-}" ]] && return 0
_AIT_ARCHIVE_UTILS_V2_LOADED=1

# Ensure terminal_compat.sh is loaded (for die/warn helpers)
SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
# shellcheck source=terminal_compat.sh
source "${SCRIPT_DIR}/lib/terminal_compat.sh"
```

### Step 2: Path computation functions

These are pure arithmetic -- no filesystem I/O. They form the addressing scheme used by every other function and by sibling tasks.

```bash
# Compute which bundle (0-indexed) a task belongs to.
# Bundle N holds tasks N*100..(N*100+99).
# Args: $1=task_id (numeric)
# Output: bundle number (integer)
archive_bundle() {
    local task_id="$1"
    echo $(( task_id / 100 ))
}

# Compute which directory (0-indexed) a bundle belongs to.
# Directory D holds bundles D*10..(D*10+9), i.e., tasks D*1000..(D*1000+999).
# Args: $1=bundle (numeric)
# Output: directory number (integer)
archive_dir() {
    local bundle="$1"
    echo $(( bundle / 10 ))
}

# Compute the full archive path for a given task ID.
# Args: $1=task_id (numeric), $2=archived_dir (base path, e.g. "aitasks/archived")
# Output: path like "aitasks/archived/_b0/old1.tar.gz"
archive_path_for_id() {
    local task_id="$1"
    local archived_dir="$2"
    local bundle dir
    bundle=$(( task_id / 100 ))
    dir=$(( bundle / 10 ))
    echo "${archived_dir}/_b${dir}/old${bundle}.tar.gz"
}
```

**Key design decisions:**
- Functions use `echo` for output (composable with command substitution)
- `archive_path_for_id` inlines the arithmetic rather than calling the other two functions, avoiding subshell overhead in hot paths
- The `_b` prefix on directory names avoids collision with any existing `t*` or `old*` names in the archived directory

### Step 3: Temp directory management

Follows the same pattern as `task_utils.sh` lines 141-148 but with a separate variable name to avoid conflicts when both libraries are sourced.

```bash
# --- Temp directory for v2 tar.gz extraction ---
_AIT_ARCHIVE_V2_TMPDIR=""
_ait_archive_v2_cleanup() {
    if [[ -n "$_AIT_ARCHIVE_V2_TMPDIR" && -d "$_AIT_ARCHIVE_V2_TMPDIR" ]]; then
        rm -rf "$_AIT_ARCHIVE_V2_TMPDIR"
    fi
}
trap _ait_archive_v2_cleanup EXIT
```

### Step 4: Single-archive primitives

Mirror the API of `_search_tar_gz` and `_extract_from_tar_gz` from `task_utils.sh`, but with `_v2` suffix and the separate temp dir variable.

```bash
# Search for a file matching a pattern inside a tar.gz archive.
# Args: $1=archive_path, $2=grep_pattern (extended regex)
# Output: matching filename inside the tar (first match), or empty
_search_tar_gz_v2() {
    local archive="$1"
    local pattern="$2"
    [[ -f "$archive" ]] || return 0
    tar -tzf "$archive" 2>/dev/null | grep -E "$pattern" | head -1
}

# Extract a file from tar.gz to a temp location.
# Args: $1=archive_path, $2=filename_inside_tar
# Sets: _AIT_V2_EXTRACT_RESULT to the path of the extracted temp file
# Note: Must be called WITHOUT command substitution $() to preserve
# _AIT_ARCHIVE_V2_TMPDIR in the caller's shell for EXIT trap cleanup.
_extract_from_tar_gz_v2() {
    local archive="$1"
    local filename="$2"
    if [[ -z "$_AIT_ARCHIVE_V2_TMPDIR" ]]; then
        _AIT_ARCHIVE_V2_TMPDIR=$(mktemp -d)
    fi
    _AIT_V2_EXTRACT_RESULT="$_AIT_ARCHIVE_V2_TMPDIR/$(basename "$filename")"
    tar -xzf "$archive" -O "$filename" > "$_AIT_V2_EXTRACT_RESULT" 2>/dev/null
}
```

### Step 5: Multi-archive operations

```bash
# O(1) lookup: find the archive path for a given task ID.
# Returns the path if the archive file exists on disk, empty otherwise.
# Args: $1=task_id (numeric parent ID), $2=archived_dir
# Output: archive path or empty string
_find_archive_for_task() {
    local task_id="$1"
    local archived_dir="$2"
    local path
    path=$(archive_path_for_id "$task_id" "$archived_dir")
    if [[ -f "$path" ]]; then
        echo "$path"
    fi
}

# Iterate all v2 archives (_bN/oldM.tar.gz) searching for a pattern.
# Useful for queries where the task ID is unknown (e.g., text search).
# Args: $1=archived_dir, $2=grep_pattern
# Output: "archive_path:matched_filename" for each match (one per line)
_search_all_archives() {
    local archived_dir="$1"
    local pattern="$2"
    local archive match
    for archive in "$archived_dir"/_b*/old*.tar.gz; do
        [[ -f "$archive" ]] || continue
        match=$(_search_tar_gz_v2 "$archive" "$pattern")
        if [[ -n "$match" ]]; then
            echo "${archive}:${match}"
        fi
    done
}

# Search v2 numbered archive first, then fall back to legacy old.tar.gz.
# Designed for the transition period when both formats may coexist.
# Args: $1=task_id (numeric parent ID), $2=archived_dir, $3=grep_pattern
# Output: "archive_path:matched_filename" or empty
_search_legacy_then_v2() {
    local task_id="$1"
    local archived_dir="$2"
    local pattern="$3"

    # Try v2 numbered archive first (O(1) lookup)
    local v2_path match
    v2_path=$(archive_path_for_id "$task_id" "$archived_dir")
    if [[ -f "$v2_path" ]]; then
        match=$(_search_tar_gz_v2 "$v2_path" "$pattern")
        if [[ -n "$match" ]]; then
            echo "${v2_path}:${match}"
            return
        fi
    fi

    # Fall back to legacy single old.tar.gz
    local legacy_path="${archived_dir}/old.tar.gz"
    if [[ -f "$legacy_path" ]]; then
        match=$(_search_tar_gz_v2 "$legacy_path" "$pattern")
        if [[ -n "$match" ]]; then
            echo "${legacy_path}:${match}"
            return
        fi
    fi
}
```

### Step 6: ShellCheck and manual validation

```bash
shellcheck .aitask-scripts/lib/archive_utils_v2.sh
```

Fix any issues. Common things to watch for:
- SC2155 (declare and assign separately) -- already handled by splitting `local` and assignment
- SC2086 (double-quote variables) -- ensure all variable expansions are quoted

### Step 7: Spot-check in interactive shell

```bash
bash -c '
  SCRIPT_DIR=.aitask-scripts
  source .aitask-scripts/lib/archive_utils_v2.sh
  echo "bundle(0)=$(archive_bundle 0)"       # 0
  echo "bundle(99)=$(archive_bundle 99)"     # 0
  echo "bundle(100)=$(archive_bundle 100)"   # 1
  echo "bundle(1000)=$(archive_bundle 1000)" # 10
  echo "dir(0)=$(archive_dir 0)"             # 0
  echo "dir(9)=$(archive_dir 9)"             # 0
  echo "dir(10)=$(archive_dir 10)"           # 1
  echo "path(150)=$(archive_path_for_id 150 "aitasks/archived")"  # aitasks/archived/_b0/old1.tar.gz
  echo "path(1050)=$(archive_path_for_id 1050 "aitasks/archived")" # aitasks/archived/_b1/old10.tar.gz
'
```

### Step 8: Run sibling tests

After t433_2 is implemented:
```bash
bash tests/test_archive_utils_v2.sh
```

All tests must pass.

## Final Implementation Notes

- **Actual work done:** Created `.aitask-scripts/lib/archive_utils_v2.sh` (154 lines) exactly as planned — guard variable, path computation functions (`archive_bundle`, `archive_dir`, `archive_path_for_id`), temp dir management, single-archive primitives (`_search_tar_gz_v2`, `_extract_from_tar_gz_v2`), and multi-archive operations (`_find_archive_for_task`, `_search_all_archives`, `_search_legacy_then_v2`).
- **Deviations from plan:** None. Implementation matched the plan exactly.
- **Issues encountered:** None. ShellCheck clean (only SC1091 info for sourced file, same as task_utils.sh). All spot-check values match expected output.
- **Key decisions:** Used `_b` prefix on directory names to avoid collision with existing `t*` or `old*` names. Inlined arithmetic in `archive_path_for_id` to avoid subshell overhead.
- **Notes for sibling tasks:** The library is ready to source. Sibling tasks (t433_3 through t433_7) can use `source "${SCRIPT_DIR}/lib/archive_utils_v2.sh"` and call all public functions. The `_v2` suffix on internal functions ensures no collision when both old and new libraries are sourced simultaneously during the transition period. The `_search_legacy_then_v2` function provides the fallback pattern for the migration period.
