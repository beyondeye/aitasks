#!/usr/bin/env bash
# aitask_query_files.sh - Query task and plan file locations
#
# Consolidates file/directory lookup operations that skills previously
# performed via raw `ls` commands. One whitelisted script replaces
# multiple ad-hoc queries that could trigger permission prompts.
#
# All subcommands exit 0. Use output lines (not exit codes) for status.
#
# Usage:
#   ./aiscripts/aitask_query_files.sh task-file <N>
#   ./aiscripts/aitask_query_files.sh has-children <N>
#   ./aiscripts/aitask_query_files.sh child-file <parent> <child>
#   ./aiscripts/aitask_query_files.sh sibling-context <parent>
#   ./aiscripts/aitask_query_files.sh plan-file <taskid>
#   ./aiscripts/aitask_query_files.sh archived-children <N>
#   ./aiscripts/aitask_query_files.sh active-children <N>
#   ./aiscripts/aitask_query_files.sh resolve <N>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

# --- Help ---
show_help() {
    cat <<'EOF'
Usage: aitask_query_files.sh <subcommand> [arguments]

Query task and plan file locations. Returns structured output for
skill-based automation (no interactive prompts, no side effects).

Subcommands:
  task-file <N>                Find active task file for number N
  has-children <N>             Check if task N has child task files
  child-file <parent> <child>  Find a specific child task file
  active-children <N>          List active (pending) child task files with paths
  all-children <N>             List all children (active + archived) with paths
  sibling-context <parent>     List all sibling context files (archived + pending)
  plan-file <taskid>           Find active plan file (supports "16" or "16_2")
  archived-children <N>        List archived children of task N
  resolve <N>                  Combined: task-file + has-children in one call

Output format (structured lines):
  TASK_FILE:<path>           Active task file found
  HAS_CHILDREN:<count>       Task has <count> child files
  NO_CHILDREN                Task has no children directory/files
  CHILD_FILE:<path>          Child task file found
  CHILD:<path>               Active child task file (from active-children)
  CHILD:<path>               Child task file (from all-children, active)
  ARCHIVED_CHILD:<path>      Child task file (from all-children, archived)
  NOT_FOUND                  No matching file found
  ARCHIVED_PLAN:<path>       Archived sibling plan file
  ARCHIVED_TASK:<path>       Archived sibling task file
  PENDING_SIBLING:<path>     Pending sibling task file
  PENDING_PLAN:<path>        Pending sibling plan file
  NO_CONTEXT                 No sibling context files found
  PLAN_FILE:<path>           Active plan file found
  ARCHIVED_CHILD:<path>      Archived child task file
  NO_ARCHIVED_CHILDREN       No archived children found

All subcommands exit 0. Use output lines (not exit codes) for status.

Examples:
  ./aiscripts/aitask_query_files.sh task-file 16
  ./aiscripts/aitask_query_files.sh resolve 16
  ./aiscripts/aitask_query_files.sh child-file 16 2
  ./aiscripts/aitask_query_files.sh active-children 16
  ./aiscripts/aitask_query_files.sh all-children 16
  ./aiscripts/aitask_query_files.sh sibling-context 16
  ./aiscripts/aitask_query_files.sh plan-file 16_2
  ./aiscripts/aitask_query_files.sh archived-children 16
EOF
}

# --- Helpers ---

# Strip optional leading "t" or "p" prefix from a task/plan number
strip_prefix() {
    local val="$1"
    val="${val#t}"
    val="${val#p}"
    echo "$val"
}

# Validate that a string is a positive integer
validate_num() {
    local val="$1"
    local label="${2:-argument}"
    if [[ ! "$val" =~ ^[0-9]+$ ]]; then
        die "Invalid $label: '$val' (expected a number like 16 or t16)"
    fi
}

# --- Subcommands ---

cmd_task_file() {
    [[ $# -lt 1 ]] && die "task-file requires a task number argument"
    local num
    num=$(strip_prefix "$1")
    validate_num "$num" "task number"

    local files
    files=$(ls "$TASK_DIR"/t"${num}"_*.md 2>/dev/null || true)
    if [[ -n "$files" ]]; then
        echo "TASK_FILE:$files"
    else
        echo "NOT_FOUND"
    fi
}

cmd_has_children() {
    [[ $# -lt 1 ]] && die "has-children requires a task number argument"
    local num
    num=$(strip_prefix "$1")
    validate_num "$num" "task number"

    local child_dir="$TASK_DIR/t${num}"
    if [[ -d "$child_dir" ]]; then
        local count=0
        local f
        for f in "$child_dir"/t"${num}"_*_*.md; do
            [[ -e "$f" ]] || continue
            count=$((count + 1))
        done
        if [[ "$count" -gt 0 ]]; then
            echo "HAS_CHILDREN:$count"
        else
            echo "NO_CHILDREN"
        fi
    else
        echo "NO_CHILDREN"
    fi
}

cmd_child_file() {
    [[ $# -lt 2 ]] && die "child-file requires <parent> and <child> arguments"
    local parent child
    parent=$(strip_prefix "$1")
    child=$(strip_prefix "$2")
    validate_num "$parent" "parent number"
    validate_num "$child" "child number"

    local files
    files=$(ls "$TASK_DIR"/t"${parent}"/t"${parent}"_"${child}"_*.md 2>/dev/null || true)
    if [[ -n "$files" ]]; then
        echo "CHILD_FILE:$files"
    else
        echo "NOT_FOUND"
    fi
}

cmd_active_children() {
    [[ $# -lt 1 ]] && die "active-children requires a task number argument"
    local num
    num=$(strip_prefix "$1")
    validate_num "$num" "task number"

    local child_dir="$TASK_DIR/t${num}"
    if [[ -d "$child_dir" ]]; then
        local found=false
        local f
        for f in "$child_dir"/t"${num}"_*_*.md; do
            [[ -e "$f" ]] || continue
            echo "CHILD:$f"
            found=true
        done
        if [[ "$found" == false ]]; then
            echo "NO_CHILDREN"
        fi
    else
        echo "NO_CHILDREN"
    fi
}

cmd_all_children() {
    [[ $# -lt 1 ]] && die "all-children requires a task number argument"
    local num
    num=$(strip_prefix "$1")
    validate_num "$num" "task number"

    local found=false

    # Active children
    local child_dir="$TASK_DIR/t${num}"
    if [[ -d "$child_dir" ]]; then
        local f
        for f in "$child_dir"/t"${num}"_*_*.md; do
            [[ -e "$f" ]] || continue
            echo "CHILD:$f"
            found=true
        done
    fi

    # Archived children
    local archive_dir="$ARCHIVED_DIR/t${num}"
    if [[ -d "$archive_dir" ]]; then
        local f
        for f in "$archive_dir"/t"${num}"_*_*.md; do
            [[ -e "$f" ]] || continue
            echo "ARCHIVED_CHILD:$f"
            found=true
        done
    fi

    if [[ "$found" == false ]]; then
        echo "NO_CHILDREN"
    fi
}

cmd_sibling_context() {
    [[ $# -lt 1 ]] && die "sibling-context requires a parent number argument"
    local parent
    parent=$(strip_prefix "$1")
    validate_num "$parent" "parent number"

    local found=false

    # Archived plan files (primary reference for completed siblings)
    local f
    for f in "$ARCHIVED_PLAN_DIR"/p"${parent}"/p"${parent}"_*_*.md; do
        [[ -e "$f" ]] || continue
        echo "ARCHIVED_PLAN:$f"
        found=true
    done

    # Archived task files (fallback for siblings without archived plans)
    for f in "$ARCHIVED_DIR"/t"${parent}"/t"${parent}"_*_*.md; do
        [[ -e "$f" ]] || continue
        echo "ARCHIVED_TASK:$f"
        found=true
    done

    # Pending sibling task files
    for f in "$TASK_DIR"/t"${parent}"/t"${parent}"_*_*.md; do
        [[ -e "$f" ]] || continue
        echo "PENDING_SIBLING:$f"
        found=true
    done

    # Pending sibling plan files
    for f in "$PLAN_DIR"/p"${parent}"/p"${parent}"_*_*.md; do
        [[ -e "$f" ]] || continue
        echo "PENDING_PLAN:$f"
        found=true
    done

    if [[ "$found" == false ]]; then
        echo "NO_CONTEXT"
    fi
}

cmd_plan_file() {
    [[ $# -lt 1 ]] && die "plan-file requires a task ID argument"
    local taskid
    taskid=$(strip_prefix "$1")

    local files
    if [[ "$taskid" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local parent="${BASH_REMATCH[1]}"
        local child="${BASH_REMATCH[2]}"
        files=$(ls "$PLAN_DIR"/p"${parent}"/p"${parent}"_"${child}"_*.md 2>/dev/null || true)
    elif [[ "$taskid" =~ ^[0-9]+$ ]]; then
        files=$(ls "$PLAN_DIR"/p"${taskid}"_*.md 2>/dev/null || true)
    else
        die "Invalid task ID: '$1' (expected a number like 16, t16, or 16_2)"
    fi

    if [[ -n "$files" ]]; then
        echo "PLAN_FILE:$files"
    else
        echo "NOT_FOUND"
    fi
}

cmd_archived_children() {
    [[ $# -lt 1 ]] && die "archived-children requires a task number argument"
    local num
    num=$(strip_prefix "$1")
    validate_num "$num" "task number"

    local archive_dir="$ARCHIVED_DIR/t${num}"
    if [[ -d "$archive_dir" ]]; then
        local found=false
        local f
        for f in "$archive_dir"/t"${num}"_*_*.md; do
            [[ -e "$f" ]] || continue
            echo "ARCHIVED_CHILD:$f"
            found=true
        done
        if [[ "$found" == false ]]; then
            echo "NO_ARCHIVED_CHILDREN"
        fi
    else
        echo "NO_ARCHIVED_CHILDREN"
    fi
}

cmd_resolve() {
    [[ $# -lt 1 ]] && die "resolve requires a task number argument"
    local num
    num=$(strip_prefix "$1")
    validate_num "$num" "task number"

    # Find task file
    local files
    files=$(ls "$TASK_DIR"/t"${num}"_*.md 2>/dev/null || true)
    if [[ -z "$files" ]]; then
        echo "NOT_FOUND"
        return
    fi
    echo "TASK_FILE:$files"

    # Check for children
    local child_dir="$TASK_DIR/t${num}"
    if [[ -d "$child_dir" ]]; then
        local count=0
        local f
        for f in "$child_dir"/t"${num}"_*_*.md; do
            [[ -e "$f" ]] || continue
            count=$((count + 1))
        done
        if [[ "$count" -gt 0 ]]; then
            echo "HAS_CHILDREN:$count"
        else
            echo "NO_CHILDREN"
        fi
    else
        echo "NO_CHILDREN"
    fi
}

# --- Main dispatch ---
main() {
    if [[ $# -eq 0 ]]; then
        show_help
        exit 0
    fi

    case "$1" in
        --help|-h)
            show_help
            exit 0
            ;;
        task-file)
            shift
            cmd_task_file "$@"
            ;;
        has-children)
            shift
            cmd_has_children "$@"
            ;;
        child-file)
            shift
            cmd_child_file "$@"
            ;;
        active-children)
            shift
            cmd_active_children "$@"
            ;;
        all-children)
            shift
            cmd_all_children "$@"
            ;;
        sibling-context)
            shift
            cmd_sibling_context "$@"
            ;;
        plan-file)
            shift
            cmd_plan_file "$@"
            ;;
        archived-children)
            shift
            cmd_archived_children "$@"
            ;;
        resolve)
            shift
            cmd_resolve "$@"
            ;;
        *)
            die "Unknown subcommand: '$1'. Use --help for usage."
            ;;
    esac
}

main "$@"
