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
# shellcheck source=archive_utils.sh
source "${SCRIPT_DIR}/lib/archive_utils.sh"

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
# Uses --rebase instead of --ff-only so sync succeeds even when local has
# unpushed commits (e.g. from a previous failed push cycle).
task_sync() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git -C "$_AIT_DATA_WORKTREE" pull --rebase --quiet 2>/dev/null || true
    else
        git pull --rebase --quiet 2>/dev/null || true
    fi
}

# Push task data to remote with automatic pull-rebase on conflict.
# Retries up to 3 times. Failures are non-fatal (best-effort push).
task_push() {
    local max_attempts=3
    local attempt
    for (( attempt=1; attempt<=max_attempts; attempt++ )); do
        if _task_push_once 2>/dev/null; then
            return 0
        fi
        # Pull with rebase to incorporate remote changes, then retry
        if [[ $attempt -lt $max_attempts ]]; then
            _task_pull_rebase 2>/dev/null || true
        fi
    done
    # All attempts exhausted — best-effort, don't fail the workflow
    return 0
}

# Internal: single push attempt
_task_push_once() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git -C "$_AIT_DATA_WORKTREE" push --quiet
    else
        git push --quiet
    fi
}

# Internal: pull with rebase to catch up with remote
_task_pull_rebase() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git -C "$_AIT_DATA_WORKTREE" pull --rebase --quiet
    else
        git pull --rebase --quiet
    fi
}

# --- YAML List Parsing ---

# Parse a YAML inline list value to comma-separated string.
# Strips brackets, quotes, and spaces: "['38', t85_2]" -> "38,t85_2"
parse_yaml_list() {
    local value="$1"
    echo "$value" | tr -d "[]'\"" | tr -d ' '
}

# --- Helper: read a YAML field from frontmatter ---
read_yaml_field() {
    local file_path="$1"
    local field_name="$2"
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
        if [[ "$in_yaml" == true && "$line" =~ ^${field_name}:[[:space:]]*(.*) ]]; then
            local value="${BASH_REMATCH[1]}"
            # Trim whitespace
            value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$value"
            return
        fi
    done < "$file_path"

    echo ""
}

# --- Helper: read status of a folded task ---
read_task_status() {
    local file_path="$1"
    read_yaml_field "$file_path" "status"
}

# Normalize child task IDs: ensure entries with underscore have 't' prefix.
# e.g. "85_2,t85_3,16" -> "t85_2,t85_3,16"
normalize_task_ids() {
    local input="$1"
    [[ -z "$input" ]] && return
    local result=""
    IFS=',' read -ra ids <<< "$input"
    for id in "${ids[@]}"; do
        if [[ "$id" =~ ^[0-9]+_[0-9]+$ ]]; then
            id="t${id}"
        fi
        [[ -n "$result" ]] && result="${result},"
        result="${result}${id}"
    done
    echo "$result"
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

# --- Task and Plan Resolution ---
# Archive search/extract primitives provided by archive_utils.sh:
#   _search_archive(), _extract_from_archive(), _find_archive_for_task()
# Temp directory cleanup handled by _AIT_ARCHIVE_TMPDIR in archive_utils.sh

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

        # Tier 3: numbered archives (computed path, then legacy fallback)
        if [[ -z "$files" ]]; then
            local archive_path="" tar_match=""
            archive_path=$(_find_archive_for_task "$parent_num" "$ARCHIVED_DIR")
            if [[ -n "$archive_path" ]]; then
                tar_match=$(_search_archive "$archive_path" "(^|/)t${parent_num}/t${parent_num}_${child_num}_.*\.md$")
            fi
            if [[ -z "$tar_match" ]]; then
                local legacy
                for legacy in "$ARCHIVED_DIR/old.tar.zst" "$ARCHIVED_DIR/old.tar.gz"; do
                    [[ -f "$legacy" ]] || continue
                    archive_path="$legacy"
                    tar_match=$(_search_archive "$archive_path" "(^|/)t${parent_num}/t${parent_num}_${child_num}_.*\.md$")
                    [[ -n "$tar_match" ]] && break
                done
            fi
            if [[ -n "$tar_match" ]]; then
                _extract_from_archive "$archive_path" "$tar_match"
                files="$_AIT_EXTRACT_RESULT"
            fi
        fi

        if [[ -z "$files" ]]; then
            die "No task file found for t${parent_num}_${child_num} (checked active, archived, and numbered archives)"
        fi
    else
        # Parent task
        files=$(ls "$TASK_DIR"/t${task_id}_*.md 2>/dev/null || true)

        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_DIR"/t${task_id}_*.md 2>/dev/null || true)
        fi

        # Tier 3: numbered archives (computed path, then legacy fallback)
        if [[ -z "$files" ]]; then
            local archive_path="" tar_match=""
            archive_path=$(_find_archive_for_task "$task_id" "$ARCHIVED_DIR")
            if [[ -n "$archive_path" ]]; then
                tar_match=$(_search_archive "$archive_path" "(^|/)t${task_id}_.*\.md$")
            fi
            if [[ -z "$tar_match" ]]; then
                local legacy
                for legacy in "$ARCHIVED_DIR/old.tar.zst" "$ARCHIVED_DIR/old.tar.gz"; do
                    [[ -f "$legacy" ]] || continue
                    archive_path="$legacy"
                    tar_match=$(_search_archive "$archive_path" "(^|/)t${task_id}_.*\.md$")
                    [[ -n "$tar_match" ]] && break
                done
            fi
            if [[ -n "$tar_match" ]]; then
                _extract_from_archive "$archive_path" "$tar_match"
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

        # Tier 3: numbered archives (computed path, then legacy fallback)
        if [[ -z "$files" ]]; then
            local archive_path="" tar_match=""
            archive_path=$(_find_archive_for_task "$parent_num" "$ARCHIVED_PLAN_DIR")
            if [[ -n "$archive_path" ]]; then
                tar_match=$(_search_archive "$archive_path" "(^|/)p${parent_num}/p${parent_num}_${child_num}_.*\.md$")
            fi
            if [[ -z "$tar_match" ]]; then
                local legacy
                for legacy in "$ARCHIVED_PLAN_DIR/old.tar.zst" "$ARCHIVED_PLAN_DIR/old.tar.gz"; do
                    [[ -f "$legacy" ]] || continue
                    archive_path="$legacy"
                    tar_match=$(_search_archive "$archive_path" "(^|/)p${parent_num}/p${parent_num}_${child_num}_.*\.md$")
                    [[ -n "$tar_match" ]] && break
                done
            fi
            if [[ -n "$tar_match" ]]; then
                _extract_from_archive "$archive_path" "$tar_match"
                files="$_AIT_EXTRACT_RESULT"
            fi
        fi
    else
        # Parent plan
        files=$(ls "$PLAN_DIR"/p${task_id}_*.md 2>/dev/null || true)

        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_PLAN_DIR"/p${task_id}_*.md 2>/dev/null || true)
        fi

        # Tier 3: numbered archives (computed path, then legacy fallback)
        if [[ -z "$files" ]]; then
            local archive_path="" tar_match=""
            archive_path=$(_find_archive_for_task "$task_id" "$ARCHIVED_PLAN_DIR")
            if [[ -n "$archive_path" ]]; then
                tar_match=$(_search_archive "$archive_path" "(^|/)p${task_id}_.*\.md$")
            fi
            if [[ -z "$tar_match" ]]; then
                local legacy
                for legacy in "$ARCHIVED_PLAN_DIR/old.tar.zst" "$ARCHIVED_PLAN_DIR/old.tar.gz"; do
                    [[ -f "$legacy" ]] || continue
                    archive_path="$legacy"
                    tar_match=$(_search_archive "$archive_path" "(^|/)p${task_id}_.*\.md$")
                    [[ -n "$tar_match" ]] && break
                done
            fi
            if [[ -n "$tar_match" ]]; then
                _extract_from_archive "$archive_path" "$tar_match"
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

# Extract the pull request URL from a task file's YAML frontmatter
# Input: task file path
# Output: pull request URL or empty string
extract_pr_url() {
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
        if [[ "$in_yaml" == true && "$line" =~ ^pull_request:[[:space:]]*(.*) ]]; then
            local url="${BASH_REMATCH[1]}"
            url=$(echo "$url" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$url"
            return
        fi
    done < "$file_path"

    echo ""
}

# Extract related issue URLs from a task file's YAML frontmatter
# Input: task file path
# Output: one URL per line (newline-separated), empty if missing/empty
extract_related_issues() {
    local file_path="$1"
    local in_yaml=false

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then break
            else in_yaml=true; continue; fi
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^related_issues:[[:space:]]*(.*) ]]; then
            local raw="${BASH_REMATCH[1]}"
            # Strip brackets, split on comma, trim quotes/spaces
            raw="${raw#\[}" ; raw="${raw%\]}"
            if [[ -z "$raw" ]]; then return; fi
            while IFS=',' read -ra items; do
                for item in "${items[@]}"; do
                    item=$(echo "$item" | sed 's/^[[:space:]"]*//;s/[[:space:]"]*$//')
                    [[ -n "$item" ]] && echo "$item"
                done
            done <<< "$raw"
            return
        fi
    done < "$file_path"
}

# Extract the contributor username from a task file's YAML frontmatter
# Input: task file path
# Output: contributor username or empty string
extract_contributor() {
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
        if [[ "$in_yaml" == true && "$line" =~ ^contributor:[[:space:]]*(.*) ]]; then
            local val="${BASH_REMATCH[1]}"
            val=$(echo "$val" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$val"
            return
        fi
    done < "$file_path"

    echo ""
}

# Extract the contributor email from a task file's YAML frontmatter
# Input: task file path
# Output: contributor email or empty string
extract_contributor_email() {
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
        if [[ "$in_yaml" == true && "$line" =~ ^contributor_email:[[:space:]]*(.*) ]]; then
            local val="${BASH_REMATCH[1]}"
            val=$(echo "$val" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$val"
            return
        fi
    done < "$file_path"

    echo ""
}

# Extract the implemented_with agent string from a task file's YAML frontmatter
# Input: task file path
# Output: implemented_with value or empty string
extract_implemented_with() {
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
        if [[ "$in_yaml" == true && "$line" =~ ^implemented_with:[[:space:]]*(.*) ]]; then
            local val="${BASH_REMATCH[1]}"
            val=$(echo "$val" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$val"
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

# --- Contribute Metadata Parsing ---

# Parse aitask-contribute metadata from issue body HTML comment
# Sets global: CONTRIBUTE_CONTRIBUTOR, CONTRIBUTE_EMAIL, CONTRIBUTE_FINGERPRINT_VERSION,
#              CONTRIBUTE_AREAS, CONTRIBUTE_FILE_PATHS, CONTRIBUTE_FILE_DIRS,
#              CONTRIBUTE_CHANGE_TYPE, CONTRIBUTE_AUTO_LABELS
parse_contribute_metadata() {
    local body="$1"
    CONTRIBUTE_CONTRIBUTOR=""
    CONTRIBUTE_EMAIL=""
    CONTRIBUTE_FINGERPRINT_VERSION=""
    CONTRIBUTE_AREAS=""
    CONTRIBUTE_FILE_PATHS=""
    CONTRIBUTE_FILE_DIRS=""
    CONTRIBUTE_CHANGE_TYPE=""
    CONTRIBUTE_AUTO_LABELS=""

    local in_block=false
    while IFS= read -r line; do
        if [[ "$line" == *"<!-- aitask-contribute-metadata"* ]]; then
            in_block=true
            continue
        fi
        if [[ "$in_block" == true ]]; then
            if [[ "$line" == *"-->"* ]]; then
                break
            fi
            case "$line" in
                *contributor_email:*)
                    CONTRIBUTE_EMAIL=$(echo "$line" | sed 's/.*contributor_email:[[:space:]]*//' | tr -d '[:space:]')
                    ;;
                *contributor:*)
                    CONTRIBUTE_CONTRIBUTOR=$(echo "$line" | sed 's/.*contributor:[[:space:]]*//' | tr -d '[:space:]')
                    ;;
                *fingerprint_version:*)
                    CONTRIBUTE_FINGERPRINT_VERSION=$(echo "$line" | sed 's/.*fingerprint_version:[[:space:]]*//' | tr -d '[:space:]')
                    ;;
                *file_paths:*)
                    CONTRIBUTE_FILE_PATHS=$(echo "$line" | sed 's/.*file_paths:[[:space:]]*//' | sed 's/[[:space:]]*$//')
                    ;;
                *file_dirs:*)
                    CONTRIBUTE_FILE_DIRS=$(echo "$line" | sed 's/.*file_dirs:[[:space:]]*//' | sed 's/[[:space:]]*$//')
                    ;;
                *change_type:*)
                    CONTRIBUTE_CHANGE_TYPE=$(echo "$line" | sed 's/.*change_type:[[:space:]]*//' | tr -d '[:space:]')
                    ;;
                *auto_labels:*)
                    CONTRIBUTE_AUTO_LABELS=$(echo "$line" | sed 's/.*auto_labels:[[:space:]]*//' | sed 's/[[:space:]]*$//')
                    ;;
                *areas:*)
                    CONTRIBUTE_AREAS=$(echo "$line" | sed 's/.*areas:[[:space:]]*//' | sed 's/[[:space:]]*$//')
                    ;;
            esac
        fi
    done <<< "$body"
}
