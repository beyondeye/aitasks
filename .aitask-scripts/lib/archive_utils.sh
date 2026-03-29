#!/usr/bin/env bash
# archive_utils.sh - Numbered archive path computation and search/extract primitives
# Source this file from aitask scripts; do not execute directly.
#
# Numbering scheme (0-indexed):
#   bundle = task_id / 100
#   dir    = bundle / 10
#   path   = archived/_b{dir}/old{bundle}.tar.zst
#
# Examples:
#   Task 0..99   -> archived/_b0/old0.tar.zst
#   Task 100..199 -> archived/_b0/old1.tar.zst
#   Task 1000..1099 -> archived/_b1/old10.tar.zst

# --- Guard against double-sourcing ---
[[ -n "${_AIT_ARCHIVE_UTILS_LOADED:-}" ]] && return 0
_AIT_ARCHIVE_UTILS_LOADED=1

# Ensure terminal_compat.sh is loaded (for die/warn helpers)
SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
# shellcheck source=terminal_compat.sh
source "${SCRIPT_DIR}/lib/terminal_compat.sh"

# ============================================================================
# Path computation functions (pure arithmetic, no I/O)
# ============================================================================

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
# Output: path like "aitasks/archived/_b0/old1.tar.zst"
archive_path_for_id() {
    local task_id="$1"
    local archived_dir="$2"
    local bundle dir
    bundle=$(( task_id / 100 ))
    dir=$(( bundle / 10 ))
    echo "${archived_dir}/_b${dir}/old${bundle}.tar.zst"
}

# ============================================================================
# Format-aware archive helpers (auto-detect by extension)
# ============================================================================

_archive_list() {
    local archive="$1"
    if [[ "$archive" == *.tar.zst ]]; then
        zstd -dc "$archive" 2>/dev/null | tar -tf -
    else
        tar -tzf "$archive" 2>/dev/null
    fi
}

_archive_extract_file() {
    local archive="$1" filename="$2"
    if [[ "$archive" == *.tar.zst ]]; then
        zstd -dc "$archive" | tar -xf - -O "$filename"
    else
        tar -xzf "$archive" -O "$filename"
    fi
}

_archive_extract_all() {
    local archive="$1" target_dir="$2"
    if [[ "$archive" == *.tar.zst ]]; then
        zstd -dc "$archive" | tar -xf - -C "$target_dir"
    else
        tar -xzf "$archive" -C "$target_dir"
    fi
}

_archive_create() {
    local archive="$1" source_dir="$2"
    tar -cf - -C "$source_dir" . | zstd -q -o "$archive"
}

_archive_verify() {
    local archive="$1"
    if [[ "$archive" == *.tar.zst ]]; then
        zstd -dc "$archive" | tar -tf - > /dev/null
    else
        tar -tzf "$archive" > /dev/null 2>&1
    fi
}

# ============================================================================
# Temp directory management
# ============================================================================

_AIT_ARCHIVE_TMPDIR=""
_ait_archive_cleanup() {
    if [[ -n "$_AIT_ARCHIVE_TMPDIR" && -d "$_AIT_ARCHIVE_TMPDIR" ]]; then
        rm -rf "$_AIT_ARCHIVE_TMPDIR"
    fi
}
trap _ait_archive_cleanup EXIT

# ============================================================================
# Single-archive primitives (matching task_utils.sh API)
# ============================================================================

# Search for a file matching a pattern inside an archive (tar.zst or tar.gz).
# Args: $1=archive_path, $2=grep_pattern (extended regex)
# Output: matching filename inside the tar (first match), or empty
_search_archive() {
    local archive="$1"
    local pattern="$2"
    [[ -f "$archive" ]] || return 0
    _archive_list "$archive" | grep -E "$pattern" | head -1
}

# Extract a file from an archive (tar.zst or tar.gz) to a temp location.
# Args: $1=archive_path, $2=filename_inside_tar
# Sets: _AIT_EXTRACT_RESULT to the path of the extracted temp file
# Note: Must be called WITHOUT command substitution $() to preserve
# _AIT_ARCHIVE_TMPDIR in the caller's shell for EXIT trap cleanup.
_extract_from_archive() {
    local archive="$1"
    local filename="$2"
    if [[ -z "$_AIT_ARCHIVE_TMPDIR" ]]; then
        _AIT_ARCHIVE_TMPDIR=$(mktemp -d)
    fi
    _AIT_EXTRACT_RESULT="$_AIT_ARCHIVE_TMPDIR/$(basename "$filename")"
    _archive_extract_file "$archive" "$filename" > "$_AIT_EXTRACT_RESULT" 2>/dev/null
}

# ============================================================================
# Multi-archive operations
# ============================================================================

# O(1) lookup: find the archive path for a given task ID.
# Returns the path if the archive file exists on disk, empty otherwise.
# Tries .tar.zst first, falls back to .tar.gz for backward compatibility.
# Args: $1=task_id (numeric parent ID), $2=archived_dir
# Output: archive path or empty string
_find_archive_for_task() {
    local task_id="$1"
    local archived_dir="$2"
    local zst_path gz_path
    zst_path=$(archive_path_for_id "$task_id" "$archived_dir")
    if [[ -f "$zst_path" ]]; then
        echo "$zst_path"
        return
    fi
    gz_path="${zst_path%.tar.zst}.tar.gz"
    if [[ -f "$gz_path" ]]; then
        echo "$gz_path"
    fi
}

# Iterate all numbered archives searching for a pattern.
# Searches .tar.zst first, then .tar.gz (skipping .tar.gz if .tar.zst exists).
# Args: $1=archived_dir, $2=grep_pattern
# Output: "archive_path:matched_filename" for each match (one per line)
_search_all_archives() {
    local archived_dir="$1"
    local pattern="$2"
    local archive match
    for archive in "$archived_dir"/_b*/old*.tar.zst "$archived_dir"/_b*/old*.tar.gz; do
        [[ -f "$archive" ]] || continue
        # Skip .tar.gz if corresponding .tar.zst exists
        if [[ "$archive" == *.tar.gz ]]; then
            local zst_variant="${archive%.tar.gz}.tar.zst"
            [[ -f "$zst_variant" ]] && continue
        fi
        match=$(_search_archive "$archive" "$pattern")
        if [[ -n "$match" ]]; then
            echo "${archive}:${match}"
        fi
    done
}

# Search numbered archive first, then fall back to legacy archives.
# Tries .tar.zst first at each location, then .tar.gz for backward compat.
# Args: $1=task_id (numeric parent ID), $2=archived_dir, $3=grep_pattern
# Output: "archive_path:matched_filename" or empty
_search_numbered_then_legacy() {
    local task_id="$1"
    local archived_dir="$2"
    local pattern="$3"

    # Try numbered archive first (O(1) lookup): .tar.zst then .tar.gz
    local zst_path gz_path match
    zst_path=$(archive_path_for_id "$task_id" "$archived_dir")
    if [[ -f "$zst_path" ]]; then
        match=$(_search_archive "$zst_path" "$pattern")
        if [[ -n "$match" ]]; then
            echo "${zst_path}:${match}"
            return
        fi
    fi
    gz_path="${zst_path%.tar.zst}.tar.gz"
    if [[ -f "$gz_path" ]]; then
        match=$(_search_archive "$gz_path" "$pattern")
        if [[ -n "$match" ]]; then
            echo "${gz_path}:${match}"
            return
        fi
    fi

    # Fall back to legacy archives: .tar.zst then .tar.gz
    local legacy
    for legacy in "$archived_dir/old.tar.zst" "$archived_dir/old.tar.gz"; do
        if [[ -f "$legacy" ]]; then
            match=$(_search_archive "$legacy" "$pattern")
            if [[ -n "$match" ]]; then
                echo "${legacy}:${match}"
                return
            fi
        fi
    done
}
