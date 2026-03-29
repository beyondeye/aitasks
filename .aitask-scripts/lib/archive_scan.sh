#!/usr/bin/env bash
# archive_scan.sh - Archive scanning functions for numbered archives
# Source this file from aitask scripts; do not execute directly.
#
# Provides:
#   scan_max_task_id()       - find highest task ID across all locations
#   search_archived_task()   - find a specific task in archives
#   iter_all_archived_files() - iterate all files in all archives

# --- Guard against double-sourcing ---
[[ -n "${_AIT_ARCHIVE_SCAN_LOADED:-}" ]] && return 0
_AIT_ARCHIVE_SCAN_LOADED=1

SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
# shellcheck source=terminal_compat.sh
source "${SCRIPT_DIR}/lib/terminal_compat.sh"
# shellcheck source=archive_utils.sh
source "${SCRIPT_DIR}/lib/archive_utils.sh"

# ============================================================================
# scan_max_task_id - Find the highest task number across all locations
# ============================================================================

# Find the highest task number across all task locations.
# Args: $1=task_dir, $2=archived_dir
# Output: integer (max task ID, or 0 if no tasks found)
scan_max_task_id() {
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

    # Numbered archives (_bN/oldM.tar.zst and .tar.gz fallback)
    for archive in "$archived_dir"/_b*/old*.tar.zst "$archived_dir"/_b*/old*.tar.gz; do
        [[ -f "$archive" ]] || continue
        # Skip .tar.gz if corresponding .tar.zst exists
        if [[ "$archive" == *.tar.gz ]]; then
            local zst_variant="${archive%.tar.gz}.tar.zst"
            [[ -f "$zst_variant" ]] && continue
        fi
        while IFS= read -r line; do
            num=$(echo "$line" | grep -oE 't[0-9]+' | head -1 | sed 's/t//')
            [[ -n "$num" && "$num" -gt "$max_num" ]] && max_num="$num"
        done < <(_archive_list "$archive" | grep -E 't[0-9]+')
    done

    # Legacy archive fallback (.tar.zst then .tar.gz)
    local legacy
    for legacy in "$archived_dir/old.tar.zst" "$archived_dir/old.tar.gz"; do
        [[ -f "$legacy" ]] || continue
        while IFS= read -r line; do
            num=$(echo "$line" | grep -oE 't[0-9]+' | head -1 | sed 's/t//')
            [[ -n "$num" && "$num" -gt "$max_num" ]] && max_num="$num"
        done < <(_archive_list "$legacy" | grep -E 't[0-9]+')
        break  # Only process the first existing legacy archive
    done

    echo "$max_num"
}

# ============================================================================
# search_archived_task - O(1) lookup for a specific task in archives
# ============================================================================

# Search for a specific task number in archives (numbered then legacy fallback).
# Uses O(1) lookup via archive_path_for_id when task number is known.
# Tries .tar.zst first, falls back to .tar.gz for backward compatibility.
# Args: $1=task_num (numeric, e.g., "150"), $2=archived_dir
# Output: "ARCHIVED_TASK_ARCHIVE:<archive_path>:<match>" or "NOT_FOUND"
search_archived_task() {
    local id="$1"
    local archived_dir="$2"

    # Parse child task format (e.g., "465_2") vs parent (e.g., "465")
    local bucket_id pattern
    if [[ "$id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        bucket_id="${BASH_REMATCH[1]}"
        pattern="(^|/)t${BASH_REMATCH[1]}/t${BASH_REMATCH[1]}_${BASH_REMATCH[2]}_.*\.md$"
    else
        bucket_id="$id"
        pattern="(^|/)t${id}_.*\.md$"
    fi

    # O(1) lookup: try .tar.zst first, then .tar.gz
    local zst_path gz_path tar_match
    zst_path=$(archive_path_for_id "$bucket_id" "$archived_dir")
    if [[ -f "$zst_path" ]]; then
        tar_match=$(_search_archive "$zst_path" "$pattern")
        if [[ -n "$tar_match" ]]; then
            echo "ARCHIVED_TASK_ARCHIVE:${zst_path}:${tar_match}"
            return
        fi
    fi
    gz_path="${zst_path%.tar.zst}.tar.gz"
    if [[ -f "$gz_path" ]]; then
        tar_match=$(_search_archive "$gz_path" "$pattern")
        if [[ -n "$tar_match" ]]; then
            echo "ARCHIVED_TASK_ARCHIVE:${gz_path}:${tar_match}"
            return
        fi
    fi

    # Fallback: legacy archives (.tar.zst then .tar.gz)
    local legacy
    for legacy in "$archived_dir/old.tar.zst" "$archived_dir/old.tar.gz"; do
        if [[ -f "$legacy" ]]; then
            tar_match=$(_search_archive "$legacy" "$pattern")
            if [[ -n "$tar_match" ]]; then
                echo "ARCHIVED_TASK_ARCHIVE:${legacy}:${tar_match}"
                return
            fi
        fi
    done

    echo "NOT_FOUND"
}

# ============================================================================
# iter_all_archived_files - Iterate all files in all archives
# ============================================================================

# Iterate all files across all numbered archives and legacy archive.
# Searches .tar.zst first, then .tar.gz (skipping .tar.gz if .tar.zst exists).
# Args: $1=archived_dir, $2=callback_cmd
#   callback_cmd is invoked as: $callback_cmd "$archive_path" "$filename_in_tar"
# Returns: 0 on success
iter_all_archived_files() {
    local archived_dir="$1"
    local callback_cmd="$2"

    # Numbered archives (sorted for deterministic order)
    local archive
    for archive in "$archived_dir"/_b*/old*.tar.zst "$archived_dir"/_b*/old*.tar.gz; do
        [[ -f "$archive" ]] || continue
        # Skip .tar.gz if corresponding .tar.zst exists
        if [[ "$archive" == *.tar.gz ]]; then
            local zst_variant="${archive%.tar.gz}.tar.zst"
            [[ -f "$zst_variant" ]] && continue
        fi
        while IFS= read -r entry; do
            [[ -z "$entry" || "$entry" == "." || "$entry" == "./" ]] && continue
            # Skip directory entries
            [[ "$entry" == */ ]] && continue
            "$callback_cmd" "$archive" "$entry"
        done < <(_archive_list "$archive")
    done

    # Legacy archive (.tar.zst then .tar.gz)
    local legacy
    for legacy in "$archived_dir/old.tar.zst" "$archived_dir/old.tar.gz"; do
        [[ -f "$legacy" ]] || continue
        while IFS= read -r entry; do
            [[ -z "$entry" || "$entry" == "." || "$entry" == "./" ]] && continue
            [[ "$entry" == */ ]] && continue
            "$callback_cmd" "$legacy" "$entry"
        done < <(_archive_list "$legacy")
        break  # Only process the first existing legacy archive
    done
}
