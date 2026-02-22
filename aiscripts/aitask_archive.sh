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
#   ./aiscripts/aitask_archive.sh <task_num>              # Archive parent
#   ./aiscripts/aitask_archive.sh <parent>_<child>        # Archive child
#   ./aiscripts/aitask_archive.sh --dry-run <task_num>    # Preview
#   ./aiscripts/aitask_archive.sh --no-commit <task_num>  # Stage only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

# --- Configuration ---
DRY_RUN=false
NO_COMMIT=false
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
  --help, -h      Show this help

Output format (structured lines for skill parsing):
  ARCHIVED_TASK:<path>              Archived task file
  ARCHIVED_PLAN:<path>              Archived plan file
  ISSUE:<task_num>:<issue_url>      Task has linked issue needing user action
  PARENT_ARCHIVED:<path>            Parent task also archived (all children done)
  PARENT_ISSUE:<task_num>:<url>     Parent has linked issue needing user action
  FOLDED_DELETED:<task_num>:<path>  Folded task was deleted
  FOLDED_ISSUE:<task_num>:<url>     Deleted folded task had linked issue
  FOLDED_WARNING:<task_num>:<status> Folded task skipped (active status)
  COMMITTED:<hash>                  Git commit hash

Examples:
  ./aiscripts/aitask_archive.sh 166          # Archive parent task t166
  ./aiscripts/aitask_archive.sh 16_2         # Archive child task t16_2
  ./aiscripts/aitask_archive.sh --dry-run 42 # Preview archival of t42
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

# --- Helper: parse YAML list field to comma-separated ---
read_yaml_list() {
    local file_path="$1"
    local field_name="$2"
    local raw
    raw=$(read_yaml_field "$file_path" "$field_name")
    # Convert [a, b, c] -> a,b,c
    echo "$raw" | tr -d '[]' | tr -d ' '
}

# --- Helper: read status of a folded task ---
read_task_status() {
    local file_path="$1"
    read_yaml_field "$file_path" "status"
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
        git add "$ARCHIVED_DIR/$task_basename"
        if [[ -n "$plan_file" ]]; then
            local plan_basename
            plan_basename=$(basename "$plan_file")
            git add "$ARCHIVED_PLAN_DIR/$plan_basename" 2>/dev/null || true
        fi
        git add -u "$TASK_DIR/" "$PLAN_DIR/" 2>/dev/null || true

        if [[ "$NO_COMMIT" != true ]]; then
            git commit -m "ait: Archive completed t${task_num} task and plan files" --quiet
            local commit_hash
            commit_hash=$(git rev-parse --short HEAD)
            echo "COMMITTED:$commit_hash"
        fi
    fi
}

# --- Handle folded tasks cleanup ---
handle_folded_tasks() {
    local task_num="$1"
    local archived_task_file="$2"

    local folded_raw
    folded_raw=$(read_yaml_list "$archived_task_file" "folded_tasks")

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

        # Resolve the folded task file
        local folded_file
        folded_file=$(ls "$TASK_DIR"/t"${folded_id}"_*.md 2>/dev/null | head -1 || true)

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

        if [[ "$DRY_RUN" == true ]]; then
            info "[dry-run] Would delete folded task: $folded_file"
            continue
        fi

        # Delete folded task file and plan
        git rm "$folded_file" --quiet
        # shellcheck disable=SC2086
        git rm "$PLAN_DIR"/p${folded_id}_*.md --quiet 2>/dev/null || true
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

    info "Archiving child task: $child_task_basename (parent: $parent_task_basename)"

    # Check for linked issue on child
    local child_issue
    child_issue=$(extract_issue_url "$child_task_file")
    if [[ -n "$child_issue" ]]; then
        echo "ISSUE:$task_id:$child_issue"
    fi

    # Update parent's children_to_implement
    if [[ "$DRY_RUN" == true ]]; then
        info "[dry-run] Would remove t${task_id} from parent's children_to_implement"
    else
        "$SCRIPT_DIR/aitask_update.sh" --batch "$parent_num" --remove-child "t${task_id}" --silent
    fi

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

        # Check for linked issue on parent
        local parent_issue
        parent_issue=$(extract_issue_url "$parent_task_file")
        if [[ -n "$parent_issue" ]]; then
            echo "PARENT_ISSUE:$parent_num:$parent_issue"
        fi

        # Remove empty child directories
        if [[ "$DRY_RUN" != true ]]; then
            rmdir "$TASK_DIR/t${parent_num}/" 2>/dev/null || true
            rmdir "$PLAN_DIR/p${parent_num}/" 2>/dev/null || true
        else
            info "[dry-run] Would remove empty child dirs"
        fi

        # Archive parent task
        archive_metadata_update "$parent_task_file"
        archive_move "$parent_task_file" "$ARCHIVED_DIR"
        echo "PARENT_ARCHIVED:$ARCHIVED_DIR/$parent_task_basename"

        # Archive parent plan (if exists)
        local parent_plan_file
        parent_plan_file=$(resolve_plan_file "$parent_num")
        if [[ -n "$parent_plan_file" && -f "$parent_plan_file" ]]; then
            local parent_plan_basename
            parent_plan_basename=$(basename "$parent_plan_file")
            archive_move "$parent_plan_file" "$ARCHIVED_PLAN_DIR"
            echo "ARCHIVED_PLAN:$ARCHIVED_PLAN_DIR/$parent_plan_basename"
        fi

        # Release parent lock
        release_lock "$parent_num"
        parent_archived=true
    fi

    # Git staging and commit
    if [[ "$DRY_RUN" != true ]]; then
        # Stage archived child files
        git add "$child_archive_dir/$child_task_basename"
        if [[ -n "${child_plan_file:-}" ]]; then
            local child_plan_basename
            child_plan_basename=$(basename "$child_plan_file")
            git add "$ARCHIVED_PLAN_DIR/p${parent_num}/$child_plan_basename" 2>/dev/null || true
        fi

        # Stage updates to active directories
        git add -u "$TASK_DIR/t${parent_num}/" 2>/dev/null || true
        git add -u "$PLAN_DIR/p${parent_num}/" 2>/dev/null || true
        git add -u "$TASK_DIR/" "$PLAN_DIR/" 2>/dev/null || true

        # Stage parent archival if applicable
        if [[ "$parent_archived" == true ]]; then
            git add "$ARCHIVED_DIR/$parent_task_basename" 2>/dev/null || true
            local parent_plan_file
            parent_plan_file=$(resolve_plan_file "$parent_num")
            if [[ -n "$parent_plan_file" ]]; then
                local parent_plan_basename
                parent_plan_basename=$(basename "$parent_plan_file")
                git add "$ARCHIVED_PLAN_DIR/$parent_plan_basename" 2>/dev/null || true
            fi
        fi

        if [[ "$NO_COMMIT" != true ]]; then
            local commit_msg="ait: Archive completed t${task_id} task and plan files"
            if [[ "$parent_archived" == true ]]; then
                commit_msg="ait: Archive completed t${task_id} and parent t${parent_num} task and plan files"
            fi
            git commit -m "$commit_msg" --quiet
            local commit_hash
            commit_hash=$(git rev-parse --short HEAD)
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
