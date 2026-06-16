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
#   ./.aitask-scripts/aitask_query_files.sh task-file <N>
#   ./.aitask-scripts/aitask_query_files.sh has-children <N>
#   ./.aitask-scripts/aitask_query_files.sh child-file <parent> <child>
#   ./.aitask-scripts/aitask_query_files.sh sibling-context <parent>
#   ./.aitask-scripts/aitask_query_files.sh plan-file <taskid>
#   ./.aitask-scripts/aitask_query_files.sh archived-children <N>
#   ./.aitask-scripts/aitask_query_files.sh archived-task <N|N_M>
#   ./.aitask-scripts/aitask_query_files.sh active-children <N>
#   ./.aitask-scripts/aitask_query_files.sh resolve <N>
#   ./.aitask-scripts/aitask_query_files.sh recent-archived [limit]
#   ./.aitask-scripts/aitask_query_files.sh task-status <N|N_M>
#   ./.aitask-scripts/aitask_query_files.sh inflight
#
# Add `--project <name>` before the subcommand to redirect the call to a
# sibling aitasks project registered in the per-user index. The sibling's
# own aitask_query_files.sh runs in its own root.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/archive_scan.sh
source "$SCRIPT_DIR/lib/archive_scan.sh"
# shellcheck source=lib/cross_repo_reexec.sh
source "$SCRIPT_DIR/lib/cross_repo_reexec.sh"

# --- Help ---
show_help() {
    cat <<'EOF'
Usage: aitask_query_files.sh [--project <name>] <subcommand> [arguments]

Query task and plan file locations. Returns structured output for
skill-based automation (no interactive prompts, no side effects).

Cross-repo:
  --project <name>             Re-exec the call inside the sibling aitasks
                               project <name> (resolved via the per-user
                               registry at ~/.config/aitasks/projects.yaml).
                               Must appear before the subcommand.

Subcommands:
  task-file <N>                Find active task file for number N
  has-children <N>             Check if task N has child task files
  child-file <parent> <child>  Find a specific child task file
  active-children <N>          List active (pending) child task files with paths
  all-children <N>             List all children (active + archived) with paths
  sibling-context <parent>     List all sibling context files (archived + pending)
  plan-file <taskid>           Find active plan file (supports "16" or "16_2")
  archived-children <N>        List archived children of task N
  archived-task <N|N_M>        Find archived task file (parent N or child N_M)
  resolve <N>                  Combined: task-file + has-children in one call
  recent-archived [limit]      List recently archived tasks (default: 15)
  task-status <N|N_M>          Emit STATUS:<value> for task N (or child N_M);
                               value is Ready/Editing/Implementing/Postponed/
                               Done/Folded/NOT_FOUND. Archived tasks → Done.
  inflight                     List in-flight gated tasks (status Implementing
                               with a recorded "## Gate Runs" ledger), parents
                               and children, with derived re-entry state. Used
                               by aitask-pick's in-flight resume section.

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
  ARCHIVED_TASK_ARCHIVE:<entry> Archived task found in archive
  NO_ARCHIVED_CHILDREN       No archived children found
  RECENT_ARCHIVED:<path>|<completed_at>|<issue_type>|<task_name>
  NO_RECENT_ARCHIVED         No recently archived tasks found
  INFLIGHT:<id>|<path>|<resume_point>|<archive_status>
                             In-flight gated task. <resume_point> is
                             PLAN|IMPLEMENT|POSTIMPL (aitask_gate.sh
                             resume-point); <archive_status> is
                             NO_GATES|ALL_PASS|BLOCKED:<csv> (archive-ready).
  NO_INFLIGHT                No in-flight gated tasks found

All subcommands exit 0. Use output lines (not exit codes) for status.

Examples:
  ./.aitask-scripts/aitask_query_files.sh task-file 16
  ./.aitask-scripts/aitask_query_files.sh resolve 16
  ./.aitask-scripts/aitask_query_files.sh child-file 16 2
  ./.aitask-scripts/aitask_query_files.sh active-children 16
  ./.aitask-scripts/aitask_query_files.sh all-children 16
  ./.aitask-scripts/aitask_query_files.sh sibling-context 16
  ./.aitask-scripts/aitask_query_files.sh plan-file 16_2
  ./.aitask-scripts/aitask_query_files.sh archived-children 16
  ./.aitask-scripts/aitask_query_files.sh archived-task 16
  ./.aitask-scripts/aitask_query_files.sh recent-archived 5
  ./.aitask-scripts/aitask_query_files.sh task-status 16_2
  ./.aitask-scripts/aitask_query_files.sh inflight
  ./.aitask-scripts/aitask_query_files.sh --project sibling task-file 16
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

cmd_archived_task() {
    [[ $# -lt 1 ]] && die "archived-task requires a task number argument"
    local num
    num=$(strip_prefix "$1")

    # Handle child task format (e.g., "465_2")
    if [[ "$num" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local parent="${BASH_REMATCH[1]}"
        local child="${BASH_REMATCH[2]}"

        # Check archived child directory on filesystem
        local files
        files=$(ls "$ARCHIVED_DIR"/t"${parent}"/t"${parent}"_"${child}"_*.md 2>/dev/null || true)
        if [[ -n "$files" ]]; then
            echo "ARCHIVED_TASK:$files"
            return
        fi

        # Check numbered archives (search_archived_task now handles N_M format)
        local scan_result
        scan_result=$(search_archived_task "${parent}_${child}" "$ARCHIVED_DIR")
        if [[ "$scan_result" != "NOT_FOUND" ]]; then
            echo "$scan_result"
            return
        fi

        echo "NOT_FOUND"
        return
    fi

    validate_num "$num" "task number"

    # Check filesystem first
    local files
    files=$(ls "$ARCHIVED_DIR"/t"${num}"_*.md 2>/dev/null || true)
    if [[ -n "$files" ]]; then
        echo "ARCHIVED_TASK:$files"
        return
    fi

    # Check numbered archives (O(1) lookup, then legacy fallback)
    local scan_result
    scan_result=$(search_archived_task "$num" "$ARCHIVED_DIR")
    if [[ "$scan_result" != "NOT_FOUND" ]]; then
        echo "$scan_result"
        return
    fi

    echo "NOT_FOUND"
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

# cmd_recent_archived [limit]
# List recently archived tasks sorted by completed_at descending.
cmd_recent_archived() {
    local limit="${1:-15}"
    local entries=()
    local completed_at issue_type basename_f f

    # Scan parent archived tasks
    for f in "$ARCHIVED_DIR"/t*_*.md; do
        [[ -e "$f" ]] || continue
        completed_at=$({ grep "^completed_at:" "$f" 2>/dev/null || true; } | sed 's/^completed_at:[[:space:]]*//' | head -n 1) || true
        [[ -z "$completed_at" ]] && completed_at="0000-00-00 00:00"
        issue_type=$({ grep "^issue_type:" "$f" 2>/dev/null || true; } | sed 's/^issue_type:[[:space:]]*//' | head -n 1) || true
        basename_f=$(basename "$f" .md)
        entries+=("${completed_at}|${f}|${issue_type}|${basename_f}")
    done

    # Scan child archived tasks
    for d in "$ARCHIVED_DIR"/t*/; do
        [[ -d "$d" ]] || continue
        for f in "$d"t*_*.md; do
            [[ -e "$f" ]] || continue
            completed_at=$({ grep "^completed_at:" "$f" 2>/dev/null || true; } | sed 's/^completed_at:[[:space:]]*//' | head -n 1) || true
            [[ -z "$completed_at" ]] && completed_at="0000-00-00 00:00"
            issue_type=$({ grep "^issue_type:" "$f" 2>/dev/null || true; } | sed 's/^issue_type:[[:space:]]*//' | head -n 1) || true
            basename_f=$(basename "$f" .md)
            entries+=("${completed_at}|${f}|${issue_type}|${basename_f}")
        done
    done

    if [[ ${#entries[@]} -eq 0 ]]; then
        echo "NO_RECENT_ARCHIVED"
        return
    fi

    local sorted
    sorted=$(printf '%s\n' "${entries[@]}" | sort -t'|' -k1 -r | head -n "$limit") || true
    while IFS='|' read -r ca path itype tname; do
        echo "RECENT_ARCHIVED:${path}|${ca}|${itype}|${tname}"
    done <<< "$sorted"
}

cmd_task_status() {
    [[ $# -lt 1 ]] && die "task-status requires a task id argument (N or N_M)"
    local id
    id=$(strip_prefix "$1")

    local file=""
    if [[ "$id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local parent="${BASH_REMATCH[1]}"
        local child="${BASH_REMATCH[2]}"
        file=$(ls "$TASK_DIR"/t"${parent}"/t"${parent}"_"${child}"_*.md 2>/dev/null || true)
    elif [[ "$id" =~ ^[0-9]+$ ]]; then
        file=$(ls "$TASK_DIR"/t"${id}"_*.md 2>/dev/null || true)
    else
        die "Invalid task id: '$1' (expected a number like 16, t16, or 16_2)"
    fi

    if [[ -n "$file" ]]; then
        local status
        status=$(read_task_status "$file")
        echo "STATUS:${status:-NOT_FOUND}"
        return
    fi

    # Not active — try archived. Archived tasks are always Done.
    local archived
    archived=$(cmd_archived_task "$id" | head -n 1)
    if [[ "$archived" == ARCHIVED_TASK:* || "$archived" == ARCHIVED_TASK_ARCHIVE:* ]]; then
        echo "STATUS:Done"
        return
    fi

    echo "STATUS:NOT_FOUND"
}

# cmd_inflight
# List in-flight gated tasks: status Implementing AND a recorded "## Gate Runs"
# ledger (a prior session deferred archival, crashed, or spanned days). Scans
# both active parents and active children — aitask_ls.sh defaults to Ready and
# lists parents only, so it cannot surface in-flight children. The derived
# re-entry state is NOT re-implemented here: it delegates to the already-built
# aitask_gate.sh deriver (resume-point / archive-ready), the single source of
# truth (t635_5). Consumed by aitask-pick's in-flight resume section (t635_7).
cmd_inflight() {
    local entries=()
    local f status id base

    # Active parent task files (directly under TASK_DIR; children live in subdirs)
    for f in "$TASK_DIR"/t*_*.md; do
        [[ -e "$f" ]] || continue
        status=$(read_task_status "$f")
        [[ "$status" == "Implementing" ]] || continue
        grep -qE '^##[[:space:]]+Gate Runs[[:space:]]*$' "$f" || continue
        base=$(basename "$f" .md)   # tN_name
        base="${base#t}"            # N_name
        id="${base%%_*}"            # N
        entries+=("${id}|${f}")
    done

    # Active child task files (one level down: TASK_DIR/tN/tN_M_name.md)
    for f in "$TASK_DIR"/t*/t*_*.md; do
        [[ -e "$f" ]] || continue
        status=$(read_task_status "$f")
        [[ "$status" == "Implementing" ]] || continue
        grep -qE '^##[[:space:]]+Gate Runs[[:space:]]*$' "$f" || continue
        base=$(basename "$f" .md)   # tP_C_name
        base="${base#t}"            # P_C_name
        if [[ "$base" =~ ^([0-9]+)_([0-9]+)_ ]]; then
            id="${BASH_REMATCH[1]}_${BASH_REMATCH[2]}"
            entries+=("${id}|${f}")
        fi
    done

    if [[ ${#entries[@]} -eq 0 ]]; then
        echo "NO_INFLIGHT"
        return
    fi

    # Deterministic order (lexical by id|path; portable — no GNU `sort -V`).
    local sorted rp as
    sorted=$(printf '%s\n' "${entries[@]}" | sort)
    while IFS='|' read -r id f; do
        [[ -z "$id" ]] && continue
        rp=$("$SCRIPT_DIR/aitask_gate.sh" resume-point "$id" 2>/dev/null | head -n1)
        [[ -z "$rp" ]] && rp="PLAN"
        as=$("$SCRIPT_DIR/aitask_gate.sh" archive-ready "$id" 2>/dev/null | head -n1)
        [[ -z "$as" ]] && as="NO_GATES"
        echo "INFLIGHT:${id}|${f}|${rp}|${as}"
    done <<< "$sorted"
}

# --- Main dispatch ---
main() {
    # Cross-repo redirect (t832_1): if `--project <name>` appears anywhere
    # in argv, resolve <name> to a sibling aitasks project root and re-exec
    # the sibling's own aitask_query_files.sh with `--project <name>`
    # stripped. The forwarded argv keeps the subcommand and its arguments
    # intact.
    cross_repo_reexec_or_continue "aitask_query_files.sh" "$@"
    if [[ ${#CROSS_REPO_FORWARDED_ARGV[@]} -gt 0 ]]; then
        set -- "${CROSS_REPO_FORWARDED_ARGV[@]}"
    else
        set --
    fi

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
        archived-task)
            shift
            cmd_archived_task "$@"
            ;;
        resolve)
            shift
            cmd_resolve "$@"
            ;;
        recent-archived)
            shift
            cmd_recent_archived "$@"
            ;;
        task-status)
            shift
            cmd_task_status "$@"
            ;;
        inflight)
            shift
            cmd_inflight "$@"
            ;;
        *)
            die "Unknown subcommand: '$1'. Use --help for usage."
            ;;
    esac
}

main "$@"
