---
priority: high
effort: medium
depends: []
issue_type: refactor
status: Done
labels: [task-archive]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-23 09:58
updated_at: 2026-03-23 11:15
completed_at: 2026-03-23 11:15
---

## Core Archive Path Library

Create `.aitask-scripts/lib/archive_utils_v2.sh` -- a standalone library providing path computation, single-archive primitives, and multi-archive search/extract operations for the numbered archive scheme.

### Context

The current archive system uses a single `archived/old.tar.gz` for all archived tasks. The v2 scheme splits archives by task ID using 0-indexed numbering:

```
bundle = task_id / 100       (integer division)
dir    = bundle / 10         (integer division)
path   = archived/_b{dir}/old{bundle}.tar.gz
```

Examples:
- Task 0-99 -> bundle 0, dir 0 -> `archived/_b0/old0.tar.gz`
- Task 100-199 -> bundle 1, dir 0 -> `archived/_b0/old1.tar.gz`
- Task 999 -> bundle 9, dir 0 -> `archived/_b0/old9.tar.gz`
- Task 1000-1099 -> bundle 10, dir 1 -> `archived/_b1/old10.tar.gz`

This library is the foundation for all subsequent sibling tasks (t433_3 through t433_7). It must be developed as a NEW file alongside the existing `task_utils.sh`, not replacing it, so existing functionality remains intact during the transition.

### Key Files to Modify

- **NEW:** `.aitask-scripts/lib/archive_utils_v2.sh` -- the entire deliverable

### Reference Files for Patterns

- `.aitask-scripts/lib/task_utils.sh` lines 141-173 -- existing `_search_tar_gz`, `_extract_from_tar_gz` (API to match)
- `.aitask-scripts/lib/task_utils.sh` lines 1-18 -- guard variable pattern, sourcing `terminal_compat.sh`
- `.aitask-scripts/lib/terminal_compat.sh` -- `die()`, `warn()`, `info()` helpers
- `tests/test_resolve_tar_gz.sh` -- test patterns showing how the current tar functions are used

### Implementation Plan

#### 1. File scaffold with guard and dependencies

```bash
#!/usr/bin/env bash
# archive_utils_v2.sh - Numbered archive path computation and search/extract primitives
# Source this file from aitask scripts; do not execute directly.

# --- Guard against double-sourcing ---
[[ -n "${_AIT_ARCHIVE_UTILS_V2_LOADED:-}" ]] && return 0
_AIT_ARCHIVE_UTILS_V2_LOADED=1

# Ensure terminal_compat.sh is loaded (for die/warn helpers)
SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
# shellcheck source=terminal_compat.sh
source "${SCRIPT_DIR}/lib/terminal_compat.sh"
```

#### 2. Path computation functions (pure arithmetic, no I/O)

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
# Directory D holds bundles D*10..(D*10+9).
# Args: $1=bundle (numeric)
# Output: directory number (integer)
archive_dir() {
    local bundle="$1"
    echo $(( bundle / 10 ))
}

# Compute the full relative archive path for a given task ID.
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

#### 3. Single-archive primitives (matching current API)

```bash
# Temp directory management for v2 extractions
_AIT_ARCHIVE_V2_TMPDIR=""
_ait_archive_v2_cleanup() {
    if [[ -n "$_AIT_ARCHIVE_V2_TMPDIR" && -d "$_AIT_ARCHIVE_V2_TMPDIR" ]]; then
        rm -rf "$_AIT_ARCHIVE_V2_TMPDIR"
    fi
}
trap _ait_archive_v2_cleanup EXIT

# Search for a file matching a pattern inside a tar.gz archive.
# Same API as _search_tar_gz in task_utils.sh.
# Args: $1=archive_path, $2=grep_pattern
# Output: matching filename inside the tar (first match), or empty
_search_tar_gz_v2() {
    local archive="$1"
    local pattern="$2"
    [[ -f "$archive" ]] || return 0
    tar -tzf "$archive" 2>/dev/null | grep -E "$pattern" | head -1
}

# Extract a file from tar.gz to a temp location.
# Same API as _extract_from_tar_gz in task_utils.sh.
# Args: $1=archive_path, $2=filename_inside_tar
# Sets: _AIT_V2_EXTRACT_RESULT to the path of the extracted temp file
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

#### 4. Multi-archive operations

```bash
# O(1) lookup: find the archive path for a given task ID.
# Returns the path if the archive file exists, empty otherwise.
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
# Args: $1=archived_dir, $2=grep_pattern
# Output: "archive_path:matched_filename" for all matches (one per line)
_search_all_archives() {
    local archived_dir="$1"
    local pattern="$2"
    local archive match
    # Use glob; no results is not an error
    for archive in "$archived_dir"/_b*/old*.tar.gz; do
        [[ -f "$archive" ]] || continue
        match=$(_search_tar_gz_v2 "$archive" "$pattern")
        if [[ -n "$match" ]]; then
            echo "${archive}:${match}"
        fi
    done
}

# Search v2 numbered archive first, then fall back to legacy old.tar.gz.
# For task-ID-based lookups where the parent task ID is known.
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

### Verification Steps

1. **Sourcing works without error:**
   ```bash
   bash -c 'SCRIPT_DIR=.aitask-scripts; source .aitask-scripts/lib/archive_utils_v2.sh; echo OK'
   ```

2. **Path computation spot checks:**
   ```bash
   source .aitask-scripts/lib/archive_utils_v2.sh
   archive_bundle 0     # expect: 0
   archive_bundle 99    # expect: 0
   archive_bundle 100   # expect: 1
   archive_bundle 999   # expect: 9
   archive_bundle 1000  # expect: 10
   archive_dir 0        # expect: 0
   archive_dir 9        # expect: 0
   archive_dir 10       # expect: 1
   archive_path_for_id 0 "aitasks/archived"     # expect: aitasks/archived/_b0/old0.tar.gz
   archive_path_for_id 150 "aitasks/archived"    # expect: aitasks/archived/_b0/old1.tar.gz
   archive_path_for_id 1050 "aitasks/archived"   # expect: aitasks/archived/_b1/old10.tar.gz
   ```

3. **Run sibling test task t433_2** -- `bash tests/test_archive_utils_v2.sh`

4. **ShellCheck passes:**
   ```bash
   shellcheck .aitask-scripts/lib/archive_utils_v2.sh
   ```
