#!/usr/bin/env bash
# task_utils.sh - Shared task/plan resolution and extraction utilities
# Source this file from aitask scripts; do not execute directly.

# --- Guard against double-sourcing ---
[[ -n "${_AIT_TASK_UTILS_LOADED:-}" ]] && return 0
_AIT_TASK_UTILS_LOADED=1

# Ensure terminal_compat.sh is loaded (for die/warn helpers)
SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
# shellcheck source=terminal_compat.sh
source "${SCRIPT_DIR}/lib/terminal_compat.sh"

# --- Default directory variables (override before sourcing if needed) ---
TASK_DIR="${TASK_DIR:-aitasks}"
ARCHIVED_DIR="${ARCHIVED_DIR:-aitasks/archived}"
PLAN_DIR="${PLAN_DIR:-aiplans}"
ARCHIVED_PLAN_DIR="${ARCHIVED_PLAN_DIR:-aiplans/archived}"

# --- Task Data Worktree Detection ---
# Detects if task data lives in a separate worktree (.aitask-data/)
# or on the current branch (legacy mode). All scripts use task_git()
# for git operations on task/plan files.

_AIT_DATA_WORKTREE=""

# Detect whether task data lives in a separate worktree
# Sets _AIT_DATA_WORKTREE to ".aitask-data" (branch mode) or "." (legacy mode)
_ait_detect_data_worktree() {
    if [[ -n "$_AIT_DATA_WORKTREE" ]]; then return; fi
    if [[ -d ".aitask-data/.git" || -f ".aitask-data/.git" ]]; then
        _AIT_DATA_WORKTREE=".aitask-data"
    else
        _AIT_DATA_WORKTREE="."
    fi
}

# Run git commands targeting the task data worktree
# In branch mode: git -C .aitask-data <args>
# In legacy mode: git <args>
task_git() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git -C "$_AIT_DATA_WORKTREE" "$@"
    else
        git "$@"
    fi
}

# Sync task data from remote (independent of code sync in branch mode)
task_sync() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git -C "$_AIT_DATA_WORKTREE" pull --ff-only --quiet 2>/dev/null || true
    else
        git pull --ff-only --quiet 2>/dev/null || true
    fi
}

# Push task data to remote (independent of code push in branch mode)
task_push() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git -C "$_AIT_DATA_WORKTREE" push --quiet 2>/dev/null || true
    else
        git push --quiet 2>/dev/null || true
    fi
}

# --- Per-user Config ---

# Read the current user's email from the local (gitignored) userconfig.yaml
# Output: email string, or empty if file missing / field not found
get_user_email() {
    local config="${TASK_DIR:-aitasks}/metadata/userconfig.yaml"
    if [[ -f "$config" ]]; then
        grep '^email:' "$config" | sed 's/^email: *//'
    fi
}

# --- Platform Detection ---

# Detect git remote platform from origin URL
# Output: "github", "gitlab", "bitbucket", or "" (unknown)
detect_platform() {
    local remote_url
    remote_url=$(git remote get-url origin 2>/dev/null || echo "")
    if [[ "$remote_url" == *"gitlab"* ]]; then
        echo "gitlab"
    elif [[ "$remote_url" == *"bitbucket"* ]]; then
        echo "bitbucket"
    elif [[ "$remote_url" == *"github"* ]]; then
        echo "github"
    else
        echo ""
    fi
}

# Detect platform from an issue/web URL
# Input: URL string
# Output: "github", "gitlab", "bitbucket", or "" (unknown)
detect_platform_from_url() {
    local url="$1"
    if [[ "$url" == *"gitlab"* ]]; then
        echo "gitlab"
    elif [[ "$url" == *"bitbucket"* ]]; then
        echo "bitbucket"
    elif [[ "$url" == *"github"* ]]; then
        echo "github"
    else
        echo ""
    fi
}

# --- Temp directory for tar.gz extraction ---
_AIT_TASK_UTILS_TMPDIR=""
_ait_task_utils_cleanup() {
    if [[ -n "$_AIT_TASK_UTILS_TMPDIR" && -d "$_AIT_TASK_UTILS_TMPDIR" ]]; then
        rm -rf "$_AIT_TASK_UTILS_TMPDIR"
    fi
}
trap _ait_task_utils_cleanup EXIT

# Search for a file matching a pattern inside a tar.gz archive
# Args: $1=archive_path, $2=grep_pattern
# Output: matching filename inside the tar (first match), or empty
_search_tar_gz() {
    local archive="$1"
    local pattern="$2"
    [[ -f "$archive" ]] || return 0
    tar -tzf "$archive" 2>/dev/null | grep -E "$pattern" | head -1
}

# Extract a file from tar.gz to a temp location
# Args: $1=archive_path, $2=filename_inside_tar
# Sets: _AIT_EXTRACT_RESULT to the path of the extracted temp file
# Note: Must be called WITHOUT command substitution $() to preserve
# _AIT_TASK_UTILS_TMPDIR in the caller's shell for EXIT trap cleanup
_extract_from_tar_gz() {
    local archive="$1"
    local filename="$2"
    if [[ -z "$_AIT_TASK_UTILS_TMPDIR" ]]; then
        _AIT_TASK_UTILS_TMPDIR=$(mktemp -d)
    fi
    _AIT_EXTRACT_RESULT="$_AIT_TASK_UTILS_TMPDIR/$(basename "$filename")"
    tar -xzf "$archive" -O "$filename" > "$_AIT_EXTRACT_RESULT" 2>/dev/null
}

# --- Task and Plan Resolution ---

# Resolve task number to file path, checking both active and archived directories
# Input: task_id (e.g., "53" or "53_6")
# Output: file path
resolve_task_file() {
    local task_id="$1"
    local files=""

    if [[ "$task_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local parent_num="${BASH_REMATCH[1]}"
        local child_num="${BASH_REMATCH[2]}"

        # Check active directory first
        files=$(ls "$TASK_DIR"/t${parent_num}/t${parent_num}_${child_num}_*.md 2>/dev/null || true)

        # Check archived directory
        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_DIR"/t${parent_num}/t${parent_num}_${child_num}_*.md 2>/dev/null || true)
        fi

        # Check tar.gz archive
        if [[ -z "$files" ]]; then
            local tar_match
            tar_match=$(_search_tar_gz "$ARCHIVED_DIR/old.tar.gz" "(^|/)t${parent_num}/t${parent_num}_${child_num}_.*\.md$")
            if [[ -n "$tar_match" ]]; then
                _extract_from_tar_gz "$ARCHIVED_DIR/old.tar.gz" "$tar_match"
                files="$_AIT_EXTRACT_RESULT"
            fi
        fi

        if [[ -z "$files" ]]; then
            die "No task file found for t${parent_num}_${child_num} (checked active, archived, and tar.gz)"
        fi
    else
        # Parent task
        files=$(ls "$TASK_DIR"/t${task_id}_*.md 2>/dev/null || true)

        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_DIR"/t${task_id}_*.md 2>/dev/null || true)
        fi

        # Check tar.gz archive
        if [[ -z "$files" ]]; then
            local tar_match
            tar_match=$(_search_tar_gz "$ARCHIVED_DIR/old.tar.gz" "(^|/)t${task_id}_.*\.md$")
            if [[ -n "$tar_match" ]]; then
                _extract_from_tar_gz "$ARCHIVED_DIR/old.tar.gz" "$tar_match"
                files="$_AIT_EXTRACT_RESULT"
            fi
        fi

        if [[ -z "$files" ]]; then
            die "No task file found for task number $task_id (checked active, archived, and tar.gz)"
        fi
    fi

    local count
    count=$(echo "$files" | wc -l)

    if [[ "$count" -gt 1 ]]; then
        die "Multiple task files found for task $task_id"
    fi

    echo "$files"
}

# Resolve plan file from task number, checking both active and archived
# Plan naming convention:
#   Parent task t53_name.md -> plan p53_name.md
#   Child task t53/t53_1_name.md -> plan p53/p53_1_name.md
# Input: task_id (e.g., "53" or "53_6")
# Output: file path or empty string if not found
resolve_plan_file() {
    local task_id="$1"
    local files=""

    if [[ "$task_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local parent_num="${BASH_REMATCH[1]}"
        local child_num="${BASH_REMATCH[2]}"

        # Check active plan directory
        files=$(ls "$PLAN_DIR"/p${parent_num}/p${parent_num}_${child_num}_*.md 2>/dev/null || true)

        # Check archived plan directory
        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_PLAN_DIR"/p${parent_num}/p${parent_num}_${child_num}_*.md 2>/dev/null || true)
        fi

        # Check tar.gz archive
        if [[ -z "$files" ]]; then
            local tar_match
            tar_match=$(_search_tar_gz "$ARCHIVED_PLAN_DIR/old.tar.gz" "(^|/)p${parent_num}/p${parent_num}_${child_num}_.*\.md$")
            if [[ -n "$tar_match" ]]; then
                _extract_from_tar_gz "$ARCHIVED_PLAN_DIR/old.tar.gz" "$tar_match"
                files="$_AIT_EXTRACT_RESULT"
            fi
        fi
    else
        # Parent plan
        files=$(ls "$PLAN_DIR"/p${task_id}_*.md 2>/dev/null || true)

        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_PLAN_DIR"/p${task_id}_*.md 2>/dev/null || true)
        fi

        # Check tar.gz archive
        if [[ -z "$files" ]]; then
            local tar_match
            tar_match=$(_search_tar_gz "$ARCHIVED_PLAN_DIR/old.tar.gz" "(^|/)p${task_id}_.*\.md$")
            if [[ -n "$tar_match" ]]; then
                _extract_from_tar_gz "$ARCHIVED_PLAN_DIR/old.tar.gz" "$tar_match"
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

# Extract the issue URL from a task file's YAML frontmatter
# Input: task file path
# Output: issue URL or empty string
extract_issue_url() {
    local file_path="$1"
    local in_yaml=false

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then
                break
            else
                in_yaml=true
                continue
            fi
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^issue:[[:space:]]*(.*) ]]; then
            local url="${BASH_REMATCH[1]}"
            url=$(echo "$url" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$url"
            return
        fi
    done < "$file_path"

    echo ""
}

# Extract "Final Implementation Notes" section from a plan file
# Input: plan file path
# Output: the section content
extract_final_implementation_notes() {
    local plan_path="$1"
    local in_section=false
    local content=""

    while IFS= read -r line; do
        if [[ "$line" =~ ^##[[:space:]]+Final[[:space:]]+Implementation[[:space:]]+Notes ]]; then
            in_section=true
            continue
        fi

        if [[ "$in_section" == true ]]; then
            # Stop at next level-2 heading
            if [[ "$line" =~ ^##[[:space:]] ]]; then
                break
            fi
            if [[ -n "$content" ]]; then
                content="${content}"$'\n'"${line}"
            else
                content="$line"
            fi
        fi
    done < "$plan_path"

    # Trim leading/trailing blank lines (awk for portability — BSD sed can't handle grouped multi-line commands)
    echo "$content" | sed '/./,$!d' | awk '{lines[NR]=$0} /[^[:space:]]/{last=NR} END{for(i=1;i<=last;i++) print lines[i]}'
}
