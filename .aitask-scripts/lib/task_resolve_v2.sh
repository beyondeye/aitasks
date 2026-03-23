#!/usr/bin/env bash
# task_resolve_v2.sh - V2 task/plan resolution using numbered archives
# Source this file from aitask scripts; do not execute directly.
#
# Provides resolve_task_file_v2() and resolve_plan_file_v2() which use
# the numbered archive scheme (_bN/oldM.tar.gz) from archive_utils_v2.sh
# instead of the hardcoded old.tar.gz path. Falls back to legacy old.tar.gz
# during the transition period.

# --- Guard against double-sourcing ---
[[ -n "${_AIT_TASK_RESOLVE_V2_LOADED:-}" ]] && return 0
_AIT_TASK_RESOLVE_V2_LOADED=1

SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
# shellcheck source=terminal_compat.sh
source "${SCRIPT_DIR}/lib/terminal_compat.sh"
# shellcheck source=archive_utils_v2.sh
source "${SCRIPT_DIR}/lib/archive_utils_v2.sh"

# --- Default directory variables (same defaults as task_utils.sh) ---
TASK_DIR="${TASK_DIR:-aitasks}"
ARCHIVED_DIR="${ARCHIVED_DIR:-aitasks/archived}"
PLAN_DIR="${PLAN_DIR:-aiplans}"
ARCHIVED_PLAN_DIR="${ARCHIVED_PLAN_DIR:-aiplans/archived}"

# ============================================================================
# Private helper: search numbered archives with legacy fallback
# ============================================================================

# Search for a file in numbered archives, falling back to legacy old.tar.gz
# Args: $1=base_archived_dir, $2=task_or_parent_id (numeric), $3=grep_pattern
# Sets: _AIT_RESOLVE_V2_ARCHIVE (path of archive containing the match)
# Sets: _AIT_RESOLVE_V2_MATCH (matching filename inside archive, or empty)
# Note: Must be called WITHOUT command substitution $() to preserve globals.
_resolve_v2_search_archives() {
    local base_dir="$1"
    local id="$2"
    local pattern="$3"
    local archive_path

    _AIT_RESOLVE_V2_MATCH=""
    _AIT_RESOLVE_V2_ARCHIVE=""

    # Try computed numbered archive path first
    archive_path=$(archive_path_for_id "$id" "$base_dir")
    _AIT_RESOLVE_V2_MATCH=$(_search_tar_gz_v2 "$archive_path" "$pattern")

    # Fall back to legacy old.tar.gz
    if [[ -z "$_AIT_RESOLVE_V2_MATCH" && -f "$base_dir/old.tar.gz" ]]; then
        archive_path="$base_dir/old.tar.gz"
        _AIT_RESOLVE_V2_MATCH=$(_search_tar_gz_v2 "$archive_path" "$pattern")
    fi

    _AIT_RESOLVE_V2_ARCHIVE="$archive_path"
}

# ============================================================================
# Public API
# ============================================================================

# Resolve task number to file path, checking active, archived, and numbered archives.
# Input: task_id (e.g., "53" or "53_6")
# Output: file path (prints to stdout)
# Dies if not found or if multiple matches found.
resolve_task_file_v2() {
    local task_id="$1"
    local files=""

    if [[ "$task_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local parent_num="${BASH_REMATCH[1]}"
        local child_num="${BASH_REMATCH[2]}"

        # Tier 1: active directory
        files=$(ls "$TASK_DIR"/t${parent_num}/t${parent_num}_${child_num}_*.md 2>/dev/null || true)

        # Tier 2: archived directory (loose files)
        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_DIR"/t${parent_num}/t${parent_num}_${child_num}_*.md 2>/dev/null || true)
        fi

        # Tier 3: numbered archives (v2 path, then legacy fallback)
        if [[ -z "$files" ]]; then
            _resolve_v2_search_archives "$ARCHIVED_DIR" "$parent_num" \
                "(^|/)t${parent_num}/t${parent_num}_${child_num}_.*\\.md$"
            if [[ -n "$_AIT_RESOLVE_V2_MATCH" ]]; then
                _extract_from_tar_gz_v2 "$_AIT_RESOLVE_V2_ARCHIVE" "$_AIT_RESOLVE_V2_MATCH"
                files="$_AIT_V2_EXTRACT_RESULT"
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

        # Tier 3: numbered archives (v2 path, then legacy fallback)
        if [[ -z "$files" ]]; then
            _resolve_v2_search_archives "$ARCHIVED_DIR" "$task_id" \
                "(^|/)t${task_id}_.*\\.md$"
            if [[ -n "$_AIT_RESOLVE_V2_MATCH" ]]; then
                _extract_from_tar_gz_v2 "$_AIT_RESOLVE_V2_ARCHIVE" "$_AIT_RESOLVE_V2_MATCH"
                files="$_AIT_V2_EXTRACT_RESULT"
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

        # Tier 3: numbered archives (v2 path, then legacy fallback)
        if [[ -z "$files" ]]; then
            _resolve_v2_search_archives "$ARCHIVED_PLAN_DIR" "$parent_num" \
                "(^|/)p${parent_num}/p${parent_num}_${child_num}_.*\\.md$"
            if [[ -n "$_AIT_RESOLVE_V2_MATCH" ]]; then
                _extract_from_tar_gz_v2 "$_AIT_RESOLVE_V2_ARCHIVE" "$_AIT_RESOLVE_V2_MATCH"
                files="$_AIT_V2_EXTRACT_RESULT"
            fi
        fi
    else
        # --- Parent plan ---
        # Tier 1: active plan directory
        files=$(ls "$PLAN_DIR"/p${task_id}_*.md 2>/dev/null || true)

        # Tier 2: archived plan directory
        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_PLAN_DIR"/p${task_id}_*.md 2>/dev/null || true)
        fi

        # Tier 3: numbered archives (v2 path, then legacy fallback)
        if [[ -z "$files" ]]; then
            _resolve_v2_search_archives "$ARCHIVED_PLAN_DIR" "$task_id" \
                "(^|/)p${task_id}_.*\\.md$"
            if [[ -n "$_AIT_RESOLVE_V2_MATCH" ]]; then
                _extract_from_tar_gz_v2 "$_AIT_RESOLVE_V2_ARCHIVE" "$_AIT_RESOLVE_V2_MATCH"
                files="$_AIT_V2_EXTRACT_RESULT"
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
