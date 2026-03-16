#!/usr/bin/env bash
# aitask_revert_analyze.sh — Backend data layer for revert operations.
# Analyzes commits, files, and code areas associated with a given task.
# Called by the aitask-revert skill (not user-facing via ait dispatcher).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/terminal_compat.sh"
source "$SCRIPT_DIR/lib/task_utils.sh"

# --- Defaults ---
MODE=""
TASK_ID=""
LIMIT=20

# --- Helpers ---

show_help() {
    cat <<'EOF'
Usage: aitask_revert_analyze.sh <subcommand> [options]

Subcommands:
  --recent-tasks          List recently completed tasks from git log
  --task-commits <id>     Find all commits associated with a task
  --task-areas <id>       Group changed files by directory (area)
  --task-files <id>       Flat list of all changed files
  --find-task <id>        Locate task and plan files across all storage
  --task-children-areas <id>  Group areas by child task (parent tasks only)

Options:
  --limit N               Max results for --recent-tasks (default: 20)
  --help, -h              Show this help

Output formats:
  TASK|<id>|<title>|<date>|<commit_count>
  COMMIT|<hash>|<date>|<message>|<insertions>|<deletions>|<task_id>
  AREA|<dir>|<file_count>|<insertions>|<deletions>|<file1,file2,...>
  FILE|<path>|<insertions>|<deletions>
  TASK_LOCATION|<active|archived|tar_gz|not_found>|<path>
  PLAN_LOCATION|<active|archived|tar_gz|not_found>|<path>
  CHILD_HEADER|<child_id>|<child_name>|<commit_count>
  CHILD_AREA|<child_id>|<dir>|<file_count>|<insertions>|<deletions>|<file_list>
  PARENT_HEADER|<parent_id>|<commit_count>
  PARENT_AREA|<parent_id>|<dir>|<file_count>|<insertions>|<deletions>|<file_list>
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --recent-tasks) MODE="recent_tasks"; shift ;;
            --task-commits)
                MODE="task_commits"
                [[ $# -lt 2 ]] && die "--task-commits requires a task ID"
                TASK_ID="$2"; shift 2 ;;
            --task-areas)
                MODE="task_areas"
                [[ $# -lt 2 ]] && die "--task-areas requires a task ID"
                TASK_ID="$2"; shift 2 ;;
            --task-files)
                MODE="task_files"
                [[ $# -lt 2 ]] && die "--task-files requires a task ID"
                TASK_ID="$2"; shift 2 ;;
            --find-task)
                MODE="find_task"
                [[ $# -lt 2 ]] && die "--find-task requires a task ID"
                TASK_ID="$2"; shift 2 ;;
            --task-children-areas)
                MODE="task_children_areas"
                [[ $# -lt 2 ]] && die "--task-children-areas requires a task ID"
                TASK_ID="$2"; shift 2 ;;
            --limit)
                [[ $# -lt 2 ]] && die "--limit requires a number"
                LIMIT="$2"; shift 2 ;;
            --help|-h) show_help; exit 0 ;;
            *) die "Unknown argument: $1" ;;
        esac
    done

    if [[ -z "$MODE" ]]; then
        show_help
        exit 1
    fi
}

# Extract task ID from commit message: "(t16)" -> "16", "(t16_2)" -> "16_2"
extract_task_id() {
    local msg="$1"
    local match
    match=$(echo "$msg" | grep -oE '\(t[0-9]+(_[0-9]+)?\)' | head -1 || true)
    if [[ -n "$match" ]]; then
        echo "$match" | sed 's/[()]//g; s/^t//'
    fi
}

# Parse git diff --shortstat output into _INS and _DEL variables
parse_shortstat() {
    local stat_line="$1"
    _INS=0; _DEL=0
    if [[ "$stat_line" =~ ([0-9]+)\ insertion ]]; then _INS="${BASH_REMATCH[1]}"; fi
    if [[ "$stat_line" =~ ([0-9]+)\ deletion ]]; then _DEL="${BASH_REMATCH[1]}"; fi
}

# Get all child task IDs for a parent task
get_child_ids() {
    local task_id="$1"
    local output
    output=$("$SCRIPT_DIR/aitask_query_files.sh" all-children "$task_id" 2>/dev/null) || return 0
    echo "$output" | grep -E '^(CHILD|ARCHIVED_CHILD):' | \
        grep -oE 't[0-9]+_[0-9]+' | sed 's/^t//' | sort -u || true
}

# Build the list of task IDs to search (task + its children if parent)
build_search_ids() {
    local task_id="$1"
    local -n _ids=$2
    _ids=("$task_id")

    local children
    children=$(get_child_ids "$task_id")
    if [[ -n "$children" ]]; then
        while IFS= read -r cid; do
            [[ -n "$cid" ]] && _ids+=("$cid")
        done <<< "$children"
    fi
}

# Collect commit hashes for a single task ID (no children expansion)
_collect_hashes_for_id() {
    local sid="$1"
    local pattern="(t${sid})"
    git log --all --format="%H" --fixed-strings --grep="$pattern" 2>/dev/null || true
}

# Collect commit hashes for a set of search IDs
collect_commit_hashes() {
    local task_id="$1"
    local -a search_ids
    build_search_ids "$task_id" search_ids

    for sid in "${search_ids[@]}"; do
        _collect_hashes_for_id "$sid"
    done | sort -u
}

# Aggregate area stats from a list of commit hashes.
# Outputs AREA-like lines with a configurable prefix and optional ID column.
# Args: $1=prefix (AREA|CHILD_AREA|PARENT_AREA), $2=id (child_id or parent_id), $3..=hashes
_aggregate_areas() {
    local prefix="$1"
    local id="$2"
    shift 2
    local -a hashes=("$@")

    if [[ ${#hashes[@]} -eq 0 ]]; then
        return 0
    fi

    declare -A area_ins area_del area_files

    for h in "${hashes[@]}"; do
        while IFS=$'\t' read -r ins del filepath; do
            [[ -z "$filepath" ]] && continue
            [[ "$ins" == "-" ]] && ins=0
            [[ "$del" == "-" ]] && del=0

            local dir
            dir=$(dirname "$filepath")
            [[ "$dir" == "." ]] && dir="(root)"
            dir="${dir}/"

            area_ins[$dir]=$(( ${area_ins[$dir]:-0} + ins ))
            area_del[$dir]=$(( ${area_del[$dir]:-0} + del ))

            local existing="${area_files[$dir]:-}"
            if [[ -z "$existing" ]]; then
                area_files[$dir]="$filepath"
            elif [[ ",$existing," != *",$filepath,"* ]]; then
                area_files[$dir]="${existing},${filepath}"
            fi
        done < <(git diff-tree --no-commit-id -r --numstat "$h" 2>/dev/null)
    done

    for dir in $(echo "${!area_ins[@]}" | tr ' ' '\n' | sort); do
        local files="${area_files[$dir]}"
        local file_count
        file_count=$(echo "$files" | tr ',' '\n' | wc -l | tr -d ' ')
        echo "${prefix}|${id}|${dir}|${file_count}|${area_ins[$dir]}|${area_del[$dir]}|${files}"
    done
}

# --- Subcommands ---

find_task_commits() {
    local task_id="$1"
    local -a search_ids
    build_search_ids "$task_id" search_ids

    for sid in "${search_ids[@]}"; do
        local pattern="(t${sid})"
        while IFS='|' read -r hash date msg; do
            [[ -z "$hash" ]] && continue
            local stat_line
            stat_line=$(git diff --shortstat "${hash}^..${hash}" 2>/dev/null || echo "")
            parse_shortstat "$stat_line"
            echo "COMMIT|${hash:0:12}|${date}|${msg}|${_INS}|${_DEL}|${sid}"
        done < <(git log --all --format="%H|%as|%s" --fixed-strings --grep="$pattern")
    done
}

cmd_recent_tasks() {
    local limit="${LIMIT:-20}"
    declare -A seen
    declare -a order=()

    while IFS='|' read -r date msg; do
        [[ -z "$msg" ]] && continue
        # Skip ait: administrative commits
        [[ "$msg" =~ ^ait: ]] && continue
        local tid
        tid=$(extract_task_id "$msg")
        [[ -z "$tid" ]] && continue

        if [[ -z "${seen[$tid]:-}" ]]; then
            seen[$tid]="1|${date}|${msg}"
            order+=("$tid")
        else
            local prev_count
            prev_count="${seen[$tid]%%|*}"
            local rest="${seen[$tid]#*|}"
            seen[$tid]="$((prev_count + 1))|${rest}"
        fi
    done < <(git log --all --format="%as|%s" -500)

    local printed=0
    for tid in "${order[@]}"; do
        local entry="${seen[$tid]}"
        local commit_count="${entry%%|*}"
        local rest="${entry#*|}"
        local first_date="${rest%%|*}"
        local title="${rest#*|}"
        echo "TASK|${tid}|${title}|${first_date}|${commit_count}"
        printed=$((printed + 1))
        [[ $printed -ge $limit ]] && break
    done
}

cmd_task_areas() {
    local task_id="$1"
    local -a hashes=()

    while IFS= read -r h; do
        [[ -n "$h" ]] && hashes+=("$h")
    done < <(collect_commit_hashes "$task_id")

    if [[ ${#hashes[@]} -eq 0 ]]; then
        warn "No commits found for task $task_id"
        return 0
    fi

    # Use _aggregate_areas with AREA prefix, stripping the id column
    _aggregate_areas "AREA" "" "${hashes[@]}" | sed 's/^AREA||/AREA|/'
}

cmd_task_children_areas() {
    local task_id="$1"

    # Get child IDs
    local children
    children=$(get_child_ids "$task_id")
    if [[ -z "$children" ]]; then
        echo "NO_CHILDREN"
        return 0
    fi

    # Get all children info (paths + names) from all-children
    local all_children_output
    all_children_output=$("$SCRIPT_DIR/aitask_query_files.sh" all-children "$task_id" 2>/dev/null) || true

    # Process each child
    while IFS= read -r cid; do
        [[ -z "$cid" ]] && continue

        # Resolve child name from all-children output
        local child_name=""
        local child_line
        child_line=$(echo "$all_children_output" | grep -E "t${task_id}_${cid##*_}_" | head -1 || true)
        if [[ -n "$child_line" ]]; then
            # Extract name: CHILD:aitasks/t50/t50_1_login.md → login
            local basename_part
            basename_part=$(basename "${child_line#*:}" .md)
            # Strip the t<parent>_<child>_ prefix to get the name
            child_name="${basename_part#t"${task_id}"_"${cid##*_}"_}"
        fi

        # Collect hashes for this child only
        local -a child_hashes=()
        while IFS= read -r h; do
            [[ -n "$h" ]] && child_hashes+=("$h")
        done < <(_collect_hashes_for_id "$cid")

        local commit_count=${#child_hashes[@]}

        echo "CHILD_HEADER|${cid}|${child_name}|${commit_count}"

        if [[ $commit_count -gt 0 ]]; then
            _aggregate_areas "CHILD_AREA" "$cid" "${child_hashes[@]}"
        fi
    done <<< "$children"

    # Parent-level commits (tagged with parent ID, not any child)
    local -a parent_hashes=()
    while IFS= read -r h; do
        [[ -n "$h" ]] && parent_hashes+=("$h")
    done < <(_collect_hashes_for_id "$task_id")

    local parent_count=${#parent_hashes[@]}
    if [[ $parent_count -gt 0 ]]; then
        echo "PARENT_HEADER|${task_id}|${parent_count}"
        _aggregate_areas "PARENT_AREA" "$task_id" "${parent_hashes[@]}"
    fi
}

cmd_task_files() {
    local task_id="$1"
    local -a hashes=()

    while IFS= read -r h; do
        [[ -n "$h" ]] && hashes+=("$h")
    done < <(collect_commit_hashes "$task_id")

    if [[ ${#hashes[@]} -eq 0 ]]; then
        warn "No commits found for task $task_id"
        return 0
    fi

    declare -A file_ins file_del

    for h in "${hashes[@]}"; do
        while IFS=$'\t' read -r ins del filepath; do
            [[ -z "$filepath" ]] && continue
            [[ "$ins" == "-" ]] && ins=0
            [[ "$del" == "-" ]] && del=0
            file_ins[$filepath]=$(( ${file_ins[$filepath]:-0} + ins ))
            file_del[$filepath]=$(( ${file_del[$filepath]:-0} + del ))
        done < <(git diff-tree --no-commit-id -r --numstat "$h" 2>/dev/null)
    done

    for filepath in $(echo "${!file_ins[@]}" | tr ' ' '\n' | sort); do
        echo "FILE|${filepath}|${file_ins[$filepath]}|${file_del[$filepath]}"
    done
}

# Locate a file by trying active, archived, then tar.gz locations.
# Args: $1=type ("task" or "plan"), $2=task_id
# Output: prints TASK_LOCATION|... or PLAN_LOCATION|... line
_find_file_location() {
    local file_type="$1"
    local task_id="$2"
    local prefix label active_dir archived_dir tar_path

    if [[ "$file_type" == "task" ]]; then
        prefix="t"; label="TASK_LOCATION"
        active_dir="$TASK_DIR"; archived_dir="$ARCHIVED_DIR"
        tar_path="$ARCHIVED_DIR/old.tar.gz"
    else
        prefix="p"; label="PLAN_LOCATION"
        active_dir="$PLAN_DIR"; archived_dir="$ARCHIVED_PLAN_DIR"
        tar_path="$ARCHIVED_PLAN_DIR/old.tar.gz"
    fi

    local files=""

    if [[ "$task_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local parent_num="${BASH_REMATCH[1]}"
        local child_num="${BASH_REMATCH[2]}"
        local pat="${prefix}${parent_num}/${prefix}${parent_num}_${child_num}_"

        # Active
        files=$(ls "${active_dir}/${prefix}${parent_num}/${prefix}${parent_num}_${child_num}_"*.md 2>/dev/null || true)
        if [[ -n "$files" ]]; then
            echo "${label}|active|${files}"
            return
        fi

        # Archived
        files=$(ls "${archived_dir}/${prefix}${parent_num}/${prefix}${parent_num}_${child_num}_"*.md 2>/dev/null || true)
        if [[ -n "$files" ]]; then
            echo "${label}|archived|${files}"
            return
        fi

        # Deep archive
        local tar_match
        tar_match=$(_search_tar_gz "$tar_path" "(^|/)${pat}.*\.md$" || true)
        if [[ -n "$tar_match" ]]; then
            echo "${label}|tar_gz|${tar_match}"
            return
        fi
    else
        # Parent
        files=$(ls "${active_dir}/${prefix}${task_id}_"*.md 2>/dev/null || true)
        if [[ -n "$files" ]]; then
            echo "${label}|active|${files}"
            return
        fi

        files=$(ls "${archived_dir}/${prefix}${task_id}_"*.md 2>/dev/null || true)
        if [[ -n "$files" ]]; then
            echo "${label}|archived|${files}"
            return
        fi

        local tar_match
        tar_match=$(_search_tar_gz "$tar_path" "(^|/)${prefix}${task_id}_.*\.md$" || true)
        if [[ -n "$tar_match" ]]; then
            echo "${label}|tar_gz|${tar_match}"
            return
        fi
    fi

    echo "${label}|not_found|"
}

cmd_find_task() {
    local task_id="$1"
    _find_file_location "task" "$task_id"
    _find_file_location "plan" "$task_id"
}

# --- Main ---

main() {
    parse_args "$@"
    case "$MODE" in
        recent_tasks)        cmd_recent_tasks ;;
        task_commits)        find_task_commits "$TASK_ID" ;;
        task_areas)          cmd_task_areas "$TASK_ID" ;;
        task_files)          cmd_task_files "$TASK_ID" ;;
        find_task)           cmd_find_task "$TASK_ID" ;;
        task_children_areas) cmd_task_children_areas "$TASK_ID" ;;
        *) show_help; exit 1 ;;
    esac
}

main "$@"
