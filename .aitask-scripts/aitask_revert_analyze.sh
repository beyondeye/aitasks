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

Options:
  --limit N               Max results for --recent-tasks (default: 20)
  --help, -h              Show this help

Output formats:
  TASK|<id>|<title>|<date>|<commit_count>
  COMMIT|<hash>|<date>|<message>|<insertions>|<deletions>|<task_id>
  AREA|<dir>|<file_count>|<insertions>|<deletions>|<file1,file2,...>
  FILE|<path>|<insertions>|<deletions>
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

# Collect commit hashes for a set of search IDs
collect_commit_hashes() {
    local task_id="$1"
    local -a search_ids
    build_search_ids "$task_id" search_ids

    for sid in "${search_ids[@]}"; do
        local pattern="(t${sid})"
        git log --all --format="%H" --fixed-strings --grep="$pattern" 2>/dev/null || true
    done | sort -u
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

    # Collect per-file stats from all commits
    declare -A area_ins area_del area_files

    for h in "${hashes[@]}"; do
        while IFS=$'\t' read -r ins del filepath; do
            [[ -z "$filepath" ]] && continue
            # Skip binary files (shown as "-" in numstat)
            [[ "$ins" == "-" ]] && ins=0
            [[ "$del" == "-" ]] && del=0

            local dir
            dir=$(dirname "$filepath")
            [[ "$dir" == "." ]] && dir="(root)"
            dir="${dir}/"

            area_ins[$dir]=$(( ${area_ins[$dir]:-0} + ins ))
            area_del[$dir]=$(( ${area_del[$dir]:-0} + del ))

            # Track unique files per area (comma-separated)
            local existing="${area_files[$dir]:-}"
            if [[ -z "$existing" ]]; then
                area_files[$dir]="$filepath"
            elif [[ ",$existing," != *",$filepath,"* ]]; then
                area_files[$dir]="${existing},${filepath}"
            fi
        done < <(git diff-tree --no-commit-id -r --numstat "$h" 2>/dev/null)
    done

    # Output sorted by directory
    for dir in $(echo "${!area_ins[@]}" | tr ' ' '\n' | sort); do
        local files="${area_files[$dir]}"
        local file_count
        file_count=$(echo "$files" | tr ',' '\n' | wc -l | tr -d ' ')
        echo "AREA|${dir}|${file_count}|${area_ins[$dir]}|${area_del[$dir]}|${files}"
    done
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

# --- Main ---

main() {
    parse_args "$@"
    case "$MODE" in
        recent_tasks) cmd_recent_tasks ;;
        task_commits) find_task_commits "$TASK_ID" ;;
        task_areas)   cmd_task_areas "$TASK_ID" ;;
        task_files)   cmd_task_files "$TASK_ID" ;;
        *) show_help; exit 1 ;;
    esac
}

main "$@"
