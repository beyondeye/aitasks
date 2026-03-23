#!/usr/bin/env bash
# archive_scan_v2.sh - Archive scanning functions for numbered archives
# Source this file from aitask scripts; do not execute directly.
#
# Provides:
#   scan_max_task_id_v2()       - find highest task ID across all locations
#   search_archived_task_v2()   - find a specific task in archives
#   iter_all_archived_files_v2() - iterate all files in all archives

# --- Guard against double-sourcing ---
[[ -n "${_AIT_ARCHIVE_SCAN_V2_LOADED:-}" ]] && return 0
_AIT_ARCHIVE_SCAN_V2_LOADED=1

SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
# shellcheck source=terminal_compat.sh
source "${SCRIPT_DIR}/lib/terminal_compat.sh"
# shellcheck source=archive_utils_v2.sh
source "${SCRIPT_DIR}/lib/archive_utils_v2.sh"

# ============================================================================
# scan_max_task_id_v2 - Find the highest task number across all locations
# ============================================================================

# Find the highest task number across all task locations.
# Args: $1=task_dir, $2=archived_dir
# Output: integer (max task ID, or 0 if no tasks found)
scan_max_task_id_v2() {
    local task_dir="$1"
    local archived_dir="$2"
    local max_num=0
    local num

    # Active tasks (parents)
    if ls "$task_dir"/t*_*.md &>/dev/null; then
        for f in "$task_dir"/t*_*.md; do
            num=$(basename "$f" | grep -oE '^t[0-9]+' | sed 's/t//')
            [[ -n "$num" && "$num" -gt "$max_num" ]] && max_num="$num"
        done
    fi

    # Active child tasks
    if ls "$task_dir"/t*/t*_*.md &>/dev/null; then
        for f in "$task_dir"/t*/t*_*.md; do
            num=$(basename "$f" | grep -oE '^t[0-9]+' | sed 's/t//')
            [[ -n "$num" && "$num" -gt "$max_num" ]] && max_num="$num"
        done
    fi

    # Archived loose tasks (parents)
    if ls "$archived_dir"/t*_*.md &>/dev/null; then
        for f in "$archived_dir"/t*_*.md; do
            num=$(basename "$f" | grep -oE '^t[0-9]+' | sed 's/t//')
            [[ -n "$num" && "$num" -gt "$max_num" ]] && max_num="$num"
        done
    fi

    # Archived loose tasks (children)
    if ls "$archived_dir"/t*/t*_*.md &>/dev/null; then
        for f in "$archived_dir"/t*/t*_*.md; do
            num=$(basename "$f" | grep -oE '^t[0-9]+' | sed 's/t//')
            [[ -n "$num" && "$num" -gt "$max_num" ]] && max_num="$num"
        done
    fi

    # Numbered archives (_bN/oldM.tar.gz)
    for archive in "$archived_dir"/_b*/old*.tar.gz; do
        [[ -f "$archive" ]] || continue
        while IFS= read -r line; do
            num=$(echo "$line" | grep -oE 't[0-9]+' | head -1 | sed 's/t//')
            [[ -n "$num" && "$num" -gt "$max_num" ]] && max_num="$num"
        done < <(tar -tzf "$archive" 2>/dev/null | grep -E 't[0-9]+')
    done

    # Legacy old.tar.gz fallback
    if [[ -f "$archived_dir/old.tar.gz" ]]; then
        while IFS= read -r line; do
            num=$(echo "$line" | grep -oE 't[0-9]+' | head -1 | sed 's/t//')
            [[ -n "$num" && "$num" -gt "$max_num" ]] && max_num="$num"
        done < <(tar -tzf "$archived_dir/old.tar.gz" 2>/dev/null | grep -E 't[0-9]+')
    fi

    echo "$max_num"
}

# ============================================================================
# search_archived_task_v2 - O(1) lookup for a specific task in archives
# ============================================================================

# Search for a specific task number in archives (numbered then legacy fallback).
# Uses O(1) lookup via archive_path_for_id when task number is known.
# Args: $1=task_num (numeric, e.g., "150"), $2=archived_dir
# Output: "ARCHIVED_TASK_TAR_GZ:<archive_path>:<match>" or "NOT_FOUND"
search_archived_task_v2() {
    local num="$1"
    local archived_dir="$2"
    local pattern="(^|/)t${num}_.*\.md$"

    # O(1) lookup: compute the exact archive for this task number
    local archive_path
    archive_path=$(archive_path_for_id "$num" "$archived_dir")
    if [[ -f "$archive_path" ]]; then
        local tar_match
        tar_match=$(_search_tar_gz_v2 "$archive_path" "$pattern")
        if [[ -n "$tar_match" ]]; then
            echo "ARCHIVED_TASK_TAR_GZ:${archive_path}:${tar_match}"
            return
        fi
    fi

    # Fallback: legacy old.tar.gz
    local legacy_path="${archived_dir}/old.tar.gz"
    if [[ -f "$legacy_path" ]]; then
        local tar_match
        tar_match=$(_search_tar_gz_v2 "$legacy_path" "$pattern")
        if [[ -n "$tar_match" ]]; then
            echo "ARCHIVED_TASK_TAR_GZ:${legacy_path}:${tar_match}"
            return
        fi
    fi

    echo "NOT_FOUND"
}

# ============================================================================
# iter_all_archived_files_v2 - Iterate all files in all archives
# ============================================================================

# Iterate all files across all numbered archives and legacy archive.
# Args: $1=archived_dir, $2=callback_cmd
#   callback_cmd is invoked as: $callback_cmd "$archive_path" "$filename_in_tar"
# Returns: 0 on success
iter_all_archived_files_v2() {
    local archived_dir="$1"
    local callback_cmd="$2"

    # Numbered archives (sorted for deterministic order)
    local archive
    for archive in "$archived_dir"/_b*/old*.tar.gz; do
        [[ -f "$archive" ]] || continue
        while IFS= read -r entry; do
            [[ -z "$entry" || "$entry" == "." || "$entry" == "./" ]] && continue
            # Skip directory entries
            [[ "$entry" == */ ]] && continue
            "$callback_cmd" "$archive" "$entry"
        done < <(tar -tzf "$archive" 2>/dev/null)
    done

    # Legacy archive
    if [[ -f "$archived_dir/old.tar.gz" ]]; then
        while IFS= read -r entry; do
            [[ -z "$entry" || "$entry" == "." || "$entry" == "./" ]] && continue
            [[ "$entry" == */ ]] && continue
            "$callback_cmd" "$archived_dir/old.tar.gz" "$entry"
        done < <(tar -tzf "$archived_dir/old.tar.gz" 2>/dev/null)
    fi
}
