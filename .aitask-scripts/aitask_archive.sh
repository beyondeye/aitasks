#!/usr/bin/env bash
# aitask_archive.sh - Archive completed tasks and their plan files
#
# Handles all non-interactive post-implementation archival:
#   - Task metadata updates (status, timestamps)
#   - File moves to archived directories
#   - Parent children_to_implement updates
#   - Lock releases
#   - Folded task cleanup
#   - Git staging and commit
#
# Outputs structured lines for the calling skill to handle interactive parts
# (issue updates, folded task warnings).
#
# Usage:
#   ./.aitask-scripts/aitask_archive.sh <task_num>              # Archive parent
#   ./.aitask-scripts/aitask_archive.sh <parent>_<child>        # Archive child
#   ./.aitask-scripts/aitask_archive.sh --dry-run <task_num>    # Preview
#   ./.aitask-scripts/aitask_archive.sh --no-commit <task_num>  # Stage only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

# Source agentcrew_utils.sh for read_yaml_list, preserving SCRIPT_DIR
_ARCHIVE_SCRIPT_DIR="$SCRIPT_DIR"
source "$SCRIPT_DIR/lib/agentcrew_utils.sh"
SCRIPT_DIR="$_ARCHIVE_SCRIPT_DIR"
unset _ARCHIVE_SCRIPT_DIR

# --- Configuration ---
DRY_RUN=false
NO_COMMIT=false
SUPERSEDED=false
TASK_NUM=""

# --- Help ---
show_help() {
    cat <<'EOF'
Usage: aitask_archive.sh [options] <task_num>

Archive a completed task and its plan file.

Arguments:
  task_num        Task number: 166 or t166 (parent), 16_2 or t16_2 (child)

Options:
  --dry-run       Preview actions without executing
  --no-commit     Stage changes but don't commit
  --superseded    Mark task as superseded (adds archived_reason: superseded)
  --help, -h      Show this help

Output format (structured lines for skill parsing):
  ARCHIVED_TASK:<path>              Archived task file
  ARCHIVED_PLAN:<path>              Archived plan file
  ISSUE:<task_num>:<issue_url>      Task has linked issue needing user action
  PR:<task_num>:<pr_url>            Task has linked PR needing user action
  PARENT_ARCHIVED:<path>            Parent task also archived (all children done)
  PARENT_ISSUE:<task_num>:<url>     Parent has linked issue needing user action
  PARENT_PR:<task_num>:<url>        Parent has linked PR needing user action
  FOLDED_DELETED:<task_num>:<path>  Folded task was deleted
  FOLDED_ISSUE:<task_num>:<url>     Deleted folded task had linked issue
  FOLDED_PR:<task_num>:<url>        Deleted folded task had linked PR
  FOLDED_WARNING:<task_num>:<status> Folded task skipped (active status)
  COMMITTED:<hash>                  Git commit hash

Examples:
  ./.aitask-scripts/aitask_archive.sh 166          # Archive parent task t166
  ./.aitask-scripts/aitask_archive.sh 16_2         # Archive child task t16_2
  ./.aitask-scripts/aitask_archive.sh --dry-run 42 # Preview archival of t42
EOF
}

# --- Argument Parsing ---
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --no-commit)
                NO_COMMIT=true
                shift
                ;;
            --superseded)
                SUPERSEDED=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            -*)
                die "Unknown option: $1. Use --help for usage."
                ;;
            *)
                if [[ "$1" =~ ^t?[0-9]+(_[0-9]+)?$ ]]; then
                    TASK_NUM="${1#t}"
                    shift
                else
                    die "Invalid task number: $1 (expected format: 166, t166, 16_2, or t16_2)"
                fi
                ;;
        esac
    done

    if [[ -z "$TASK_NUM" ]]; then
        die "Task number is required. Use --help for usage."
    fi
}

# --- Helper: update task metadata for archival ---
# Sets status=Done, updates updated_at, adds completed_at
archive_metadata_update() {
    local file_path="$1"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M')

    if [[ "$DRY_RUN" == true ]]; then
        info "[dry-run] Would update metadata in $file_path (status=Done, timestamps)"
        return
    fi

    sed_inplace "s/^status: .*/status: Done/" "$file_path"
    sed_inplace "s/^updated_at: .*/updated_at: $timestamp/" "$file_path"
    # Add completed_at after updated_at (only if not already present)
    if ! grep -q "^completed_at:" "$file_path"; then
        awk -v ts="$timestamp" '/^updated_at:/{print; print "completed_at: " ts; next}1' "$file_path" > "$file_path.tmp" && mv "$file_path.tmp" "$file_path"
    fi
    # Add archived_reason for superseded tasks
    if [[ "$SUPERSEDED" == true ]]; then
        if ! grep -q "^archived_reason:" "$file_path"; then
            awk '/^status:/{print; print "archived_reason: superseded"; next}1' "$file_path" > "$file_path.tmp" && mv "$file_path.tmp" "$file_path"
        fi
    fi
}

# --- Helper: move file to archive directory ---
archive_move() {
    local src="$1"
    local dest_dir="$2"

    if [[ "$DRY_RUN" == true ]]; then
        info "[dry-run] Would move $src -> $dest_dir/"
        return
    fi

    mkdir -p "$dest_dir"
    mv "$src" "$dest_dir/"
}

# --- Helper: release lock (best-effort, idempotent) ---
release_lock() {
    local task_num="$1"

    if [[ "$DRY_RUN" == true ]]; then
        info "[dry-run] Would release lock for t$task_num"
        return
    fi

    "$SCRIPT_DIR/aitask_lock.sh" --unlock "$task_num" 2>/dev/null || true
}

# --- Archive a parent task ---
archive_parent() {
    local task_num="$1"

    # Resolve files
    local task_file
    task_file=$(resolve_task_file "$task_num")
    local task_basename
    task_basename=$(basename "$task_file")

    local plan_file
    plan_file=$(resolve_plan_file "$task_num")

    info "Archiving parent task: $task_basename"

    # Check for linked issue before archival (output for skill)
    local issue_url
    issue_url=$(extract_issue_url "$task_file")
    if [[ -n "$issue_url" ]]; then
        echo "ISSUE:$task_num:$issue_url"
    fi

    # Check for related issues before archival (output for skill)
    local related_url
    while IFS= read -r related_url; do
        [[ -n "$related_url" ]] && echo "RELATED_ISSUE:$task_num:$related_url"
    done < <(extract_related_issues "$task_file")

    # Check for linked PR before archival (output for skill)
    local pr_url
    pr_url=$(extract_pr_url "$task_file")
    if [[ -n "$pr_url" ]]; then
        echo "PR:$task_num:$pr_url"
    fi

    # Handle folded tasks (before moving, so we can read from original path)
    handle_folded_tasks "$task_num" "$task_file"

    # Update metadata
    archive_metadata_update "$task_file"

    # Move task file to archive
    archive_move "$task_file" "$ARCHIVED_DIR"
    echo "ARCHIVED_TASK:$ARCHIVED_DIR/$task_basename"

    # Move plan file to archive (if exists)
    if [[ -n "$plan_file" && -f "$plan_file" ]]; then
        local plan_basename
        plan_basename=$(basename "$plan_file")
        archive_move "$plan_file" "$ARCHIVED_PLAN_DIR"
        echo "ARCHIVED_PLAN:$ARCHIVED_PLAN_DIR/$plan_basename"
    fi

    # Release lock
    release_lock "$task_num"

    # Git staging and commit
    if [[ "$DRY_RUN" != true ]]; then
        task_git add "$ARCHIVED_DIR/$task_basename"
        if [[ -n "$plan_file" ]]; then
            local plan_basename
            plan_basename=$(basename "$plan_file")
            task_git add "$ARCHIVED_PLAN_DIR/$plan_basename" 2>/dev/null || true
        fi
        # Stage deletion of original task/plan paths (files already moved by archive_move).
        # Narrow to specific paths so we don't sweep in unrelated in-progress edits by sibling agents.
        task_git add -u "$task_file" 2>/dev/null || true
        if [[ -n "$plan_file" ]]; then
            task_git add -u "$plan_file" 2>/dev/null || true
        fi

        if [[ "$NO_COMMIT" != true ]]; then
            task_git commit -m "ait: Archive completed t${task_num} task and plan files" --quiet
            local commit_hash
            commit_hash=$(task_git rev-parse --short HEAD)
            echo "COMMITTED:$commit_hash"
        fi
    fi
}

# --- Handle folded tasks cleanup ---
handle_folded_tasks() {
    local task_num="$1"
    local archived_task_file="$2"

    local folded_raw
    folded_raw=$(parse_yaml_list "$(read_yaml_field "$archived_task_file" "folded_tasks")")

    if [[ -z "$folded_raw" ]]; then
        return
    fi

    IFS=',' read -ra folded_ids <<< "$folded_raw"
    for folded_id in "${folded_ids[@]}"; do
        # Strip leading 't' if present
        folded_id="${folded_id#t}"
        if [[ -z "$folded_id" ]]; then
            continue
        fi

        # Extract numeric part for lock release
        local folded_num="$folded_id"

        # Resolve the folded task file (handles both parent and child task IDs)
        local folded_file
        if [[ "$folded_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
            local fp="${BASH_REMATCH[1]}"
            local fc="${BASH_REMATCH[2]}"
            folded_file=$(ls "$TASK_DIR"/t"${fp}"/t"${fp}"_"${fc}"_*.md 2>/dev/null | head -1 || true)
        else
            folded_file=$(ls "$TASK_DIR"/t"${folded_id}"_*.md 2>/dev/null | head -1 || true)
        fi

        if [[ -z "$folded_file" ]]; then
            # Already deleted or archived — skip silently
            continue
        fi

        # Check status
        local folded_status
        folded_status=$(read_task_status "$folded_file")

        if [[ "$folded_status" == "Implementing" || "$folded_status" == "Done" ]]; then
            echo "FOLDED_WARNING:$folded_id:$folded_status"
            continue
        fi

        # Check for linked issue before deletion
        local folded_issue
        folded_issue=$(extract_issue_url "$folded_file")
        if [[ -n "$folded_issue" ]]; then
            echo "FOLDED_ISSUE:$folded_id:$folded_issue"
        fi

        # Check for related issues on folded task before deletion
        local folded_related
        while IFS= read -r folded_related; do
            [[ -n "$folded_related" ]] && echo "FOLDED_RELATED_ISSUE:$folded_id:$folded_related"
        done < <(extract_related_issues "$folded_file")

        # Check for linked PR before deletion
        local folded_pr_url
        folded_pr_url=$(extract_pr_url "$folded_file")
        if [[ -n "$folded_pr_url" ]]; then
            echo "FOLDED_PR:$folded_id:$folded_pr_url"
        fi

        if [[ "$DRY_RUN" == true ]]; then
            info "[dry-run] Would delete folded task: $folded_file"
            continue
        fi

        # If folded task is a child, remove from its parent's children_to_implement
        # (safety-net — normally handled at fold time by Task Fold Marking Procedure)
        if [[ "$folded_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
            local fold_parent="${BASH_REMATCH[1]}"
            "$SCRIPT_DIR/aitask_update.sh" --batch "$fold_parent" --remove-child "t${folded_id}" --silent 2>/dev/null || true
        fi

        # Delete folded task file and plan
        task_git rm "$folded_file" --quiet
        # Delete plan file (handles both parent and child task IDs)
        # shellcheck disable=SC2086
        if [[ "$folded_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
            local fp="${BASH_REMATCH[1]}"
            local fc="${BASH_REMATCH[2]}"
            task_git rm "$PLAN_DIR"/p"${fp}"/p"${fp}"_"${fc}"_*.md --quiet 2>/dev/null || true
        else
            task_git rm "$PLAN_DIR"/p${folded_id}_*.md --quiet 2>/dev/null || true
        fi
        echo "FOLDED_DELETED:$folded_id:$folded_file"

        # Release lock for folded task
        release_lock "$folded_num"
    done
}

# --- Archive a child task ---
archive_child() {
    local parent_num="$1"
    local child_num="$2"
    local task_id="${parent_num}_${child_num}"

    # Resolve child files
    local child_task_file
    child_task_file=$(resolve_task_file "$task_id")
    local child_task_basename
    child_task_basename=$(basename "$child_task_file")

    local child_plan_file
    child_plan_file=$(resolve_plan_file "$task_id")

    # Resolve parent files (needed for potential parent archival)
    local parent_task_file
    parent_task_file=$(resolve_task_file "$parent_num")
    local parent_task_basename
    parent_task_basename=$(basename "$parent_task_file")

    # Function-scoped parent plan paths, populated later if the parent gets auto-archived.
    # Declared here so the commit section can see the original (pre-move) path for staging.
    local parent_plan_file=""
    local parent_plan_basename=""

    info "Archiving child task: $child_task_basename (parent: $parent_task_basename)"

    # Cache parent issue/PR/related_issues BEFORE --remove-child rewrites the file
    # (aitask_update.sh may strip fields it doesn't know about)
    local cached_parent_issue
    cached_parent_issue=$(extract_issue_url "$parent_task_file")
    local cached_parent_related
    cached_parent_related=$(extract_related_issues "$parent_task_file")
    local cached_parent_pr
    cached_parent_pr=$(extract_pr_url "$parent_task_file")

    # Check for linked issue on child
    local child_issue
    child_issue=$(extract_issue_url "$child_task_file")
    if [[ -n "$child_issue" ]]; then
        echo "ISSUE:$task_id:$child_issue"
    fi

    # Check for related issues on child
    local child_related
    while IFS= read -r child_related; do
        [[ -n "$child_related" ]] && echo "RELATED_ISSUE:$task_id:$child_related"
    done < <(extract_related_issues "$child_task_file")

    # Check for linked PR on child
    local child_pr
    child_pr=$(extract_pr_url "$child_task_file")
    if [[ -n "$child_pr" ]]; then
        echo "PR:$task_id:$child_pr"
    fi

    # Update parent's children_to_implement
    if [[ "$DRY_RUN" == true ]]; then
        info "[dry-run] Would remove t${task_id} from parent's children_to_implement"
    else
        "$SCRIPT_DIR/aitask_update.sh" --batch "$parent_num" --remove-child "t${task_id}" --silent
    fi

    # Handle folded tasks for child (if any) — must be before archive_move
    handle_folded_tasks "$task_id" "$child_task_file"

    # Update child metadata
    archive_metadata_update "$child_task_file"

    # Move child task to archive
    local child_archive_dir="$ARCHIVED_DIR/t${parent_num}"
    archive_move "$child_task_file" "$child_archive_dir"
    echo "ARCHIVED_TASK:$child_archive_dir/$child_task_basename"

    # Move child plan to archive (if exists)
    if [[ -n "$child_plan_file" && -f "$child_plan_file" ]]; then
        local child_plan_basename
        child_plan_basename=$(basename "$child_plan_file")
        local child_plan_archive_dir="$ARCHIVED_PLAN_DIR/p${parent_num}"
        archive_move "$child_plan_file" "$child_plan_archive_dir"
        echo "ARCHIVED_PLAN:$child_plan_archive_dir/$child_plan_basename"
    fi

    # Release child lock
    release_lock "$task_id"

    # Check if all children are complete
    local remaining_children
    remaining_children=$(read_yaml_list "$parent_task_file" "children_to_implement")

    local parent_archived=false
    if [[ -z "$remaining_children" ]]; then
        info "All child tasks complete — archiving parent task as well."

        # Emit cached parent issue/related/PR (read before --remove-child)
        if [[ -n "$cached_parent_issue" ]]; then
            echo "PARENT_ISSUE:$parent_num:$cached_parent_issue"
        fi

        local parent_related
        while IFS= read -r parent_related; do
            [[ -n "$parent_related" ]] && echo "PARENT_RELATED_ISSUE:$parent_num:$parent_related"
        done <<< "$cached_parent_related"

        if [[ -n "$cached_parent_pr" ]]; then
            echo "PARENT_PR:$parent_num:$cached_parent_pr"
        fi

        # Remove empty child directories
        if [[ "$DRY_RUN" != true ]]; then
            rmdir "$TASK_DIR/t${parent_num}/" 2>/dev/null || true
            rmdir "$PLAN_DIR/p${parent_num}/" 2>/dev/null || true
        else
            info "[dry-run] Would remove empty child dirs"
        fi

        # Handle folded tasks for parent (if any)
        handle_folded_tasks "$parent_num" "$parent_task_file"

        # Archive parent task
        archive_metadata_update "$parent_task_file"
        archive_move "$parent_task_file" "$ARCHIVED_DIR"
        echo "PARENT_ARCHIVED:$ARCHIVED_DIR/$parent_task_basename"

        # Archive parent plan (if exists). Assigns the function-scoped parent_plan_file
        # and parent_plan_basename so the commit section can reference the original path.
        parent_plan_file=$(resolve_plan_file "$parent_num")
        if [[ -n "$parent_plan_file" && -f "$parent_plan_file" ]]; then
            parent_plan_basename=$(basename "$parent_plan_file")
            archive_move "$parent_plan_file" "$ARCHIVED_PLAN_DIR"
            echo "ARCHIVED_PLAN:$ARCHIVED_PLAN_DIR/$parent_plan_basename"
        else
            parent_plan_file=""
        fi

        # Release parent lock
        release_lock "$parent_num"
        parent_archived=true
    fi

    # Git staging and commit
    if [[ "$DRY_RUN" != true ]]; then
        # Stage archived child files
        task_git add "$child_archive_dir/$child_task_basename"
        if [[ -n "${child_plan_file:-}" ]]; then
            local child_plan_basename
            child_plan_basename=$(basename "$child_plan_file")
            task_git add "$ARCHIVED_PLAN_DIR/p${parent_num}/$child_plan_basename" 2>/dev/null || true
        fi

        # Stage deletion of original child task/plan paths (files already moved by archive_move).
        # Narrowed to specific paths so we don't sweep in unrelated in-progress edits by sibling agents.
        task_git add -u "$child_task_file" 2>/dev/null || true
        if [[ -n "${child_plan_file:-}" ]]; then
            task_git add -u "$child_plan_file" 2>/dev/null || true
        fi
        # Stage parent task file: in-place modification from --remove-child,
        # or deletion if parent was also archived (both cases handled by a single add -u on the original path).
        task_git add -u "$parent_task_file" 2>/dev/null || true

        # Stage parent archival if applicable
        if [[ "$parent_archived" == true ]]; then
            task_git add "$ARCHIVED_DIR/$parent_task_basename" 2>/dev/null || true
            if [[ -n "$parent_plan_basename" ]]; then
                task_git add "$ARCHIVED_PLAN_DIR/$parent_plan_basename" 2>/dev/null || true
                task_git add -u "$parent_plan_file" 2>/dev/null || true
            fi
        fi

        if [[ "$NO_COMMIT" != true ]]; then
            local commit_msg="ait: Archive completed t${task_id} task and plan files"
            if [[ "$parent_archived" == true ]]; then
                commit_msg="ait: Archive completed t${task_id} and parent t${parent_num} task and plan files"
            fi
            task_git commit -m "$commit_msg" --quiet
            local commit_hash
            commit_hash=$(task_git rev-parse --short HEAD)
            echo "COMMITTED:$commit_hash"
        fi
    fi
}

# --- Main ---
main() {
    parse_args "$@"

    if [[ "$TASK_NUM" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local parent_num="${BASH_REMATCH[1]}"
        local child_num="${BASH_REMATCH[2]}"
        archive_child "$parent_num" "$child_num"
    else
        archive_parent "$TASK_NUM"
    fi
}

main "$@"
