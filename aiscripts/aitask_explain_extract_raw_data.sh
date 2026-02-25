#!/usr/bin/env bash
set -euo pipefail

# aitask_explain_extract_raw_data.sh - Extract raw git data for the aitask-explain skill
# Gathers commit history, blame data, and aitask/aiplan files for specified files.
# Outputs structured raw data that is then processed by aitask_explain_process_raw_data.py

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

# --- Defaults ---
MODE=""
MAX_COMMITS=50
CLEANUP_DIR=""
INPUT_PATHS=()
AIEXPLAINS_DIR="${AIEXPLAINS_DIR:-aiexplains}"

# --- Functions ---

# Expand a path to a list of git-tracked files
# If path is a file, output it directly; if a directory, list tracked files
expand_path() {
    local path="$1"
    if [[ -d "$path" ]]; then
        # List all git-tracked files in the directory
        git ls-files "$path" | while IFS= read -r f; do
            # Skip binary files by checking if file contains null bytes
            if file -b --mime-encoding "$f" 2>/dev/null | grep -qv 'binary'; then
                echo "$f"
            fi
        done
    elif [[ -f "$path" ]]; then
        # Verify it's tracked by git
        if git ls-files --error-unmatch "$path" &>/dev/null; then
            echo "$path"
        else
            warn "File not tracked by git: $path"
        fi
    else
        warn "Path does not exist: $path"
    fi
}

# Extract task ID from a commit message (parenthesized pattern only)
# Input: commit message
# Output: task ID (e.g., "16" or "16_2") or empty
extract_task_id_from_message() {
    local msg="$1"
    local match
    match=$(echo "$msg" | grep -oE '\(t[0-9]+(_[0-9]+)?\)' | head -1 || true)
    if [[ -n "$match" ]]; then
        echo "$match" | sed 's/[()]//g; s/^t//'
    fi
}

# Process a single file: gather commit timeline and blame data
process_file() {
    local filepath="$1"
    local raw_data_file="$2"

    echo "=== FILE: ${filepath} ===" >> "$raw_data_file"
    echo "" >> "$raw_data_file"

    # --- Commit Timeline (newest first) ---
    echo "COMMIT_TIMELINE:" >> "$raw_data_file"
    local timeline_num=0
    while IFS='|' read -r full_hash short_hash date author message; do
        [[ -z "$full_hash" ]] && continue
        timeline_num=$((timeline_num + 1))
        local task_id
        task_id=$(extract_task_id_from_message "$message")
        echo "${timeline_num}|${short_hash}|${date}|${author}|${message}|${task_id}" >> "$raw_data_file"
    done < <(git log --follow --format="%H|%h|%as|%an|%s" --max-count="$MAX_COMMITS" -- "$filepath" 2>/dev/null || true)

    echo "" >> "$raw_data_file"

    # --- Blame Lines ---
    echo "BLAME_LINES:" >> "$raw_data_file"
    # Parse git blame porcelain output: extract line_num and commit hash
    local current_hash=""
    while IFS= read -r blame_line; do
        # Boundary lines start with a 40-char hex hash
        if [[ "$blame_line" =~ ^([0-9a-f]{40})[[:space:]]([0-9]+)[[:space:]]([0-9]+) ]]; then
            current_hash="${BASH_REMATCH[1]}"
            local final_line="${BASH_REMATCH[3]}"
            echo "${final_line}|${current_hash}" >> "$raw_data_file"
        fi
    done < <(git blame --porcelain "$filepath" 2>/dev/null || true)

    echo "" >> "$raw_data_file"
    echo "=== END FILE ===" >> "$raw_data_file"
    echo "" >> "$raw_data_file"
}

# --- Main modes ---

gather() {
    if [[ ${#INPUT_PATHS[@]} -eq 0 ]]; then
        die "No input files or directories specified. Usage: $0 --gather PATH [PATH...]"
    fi

    # Expand all paths to individual files
    local all_files=()
    for path in "${INPUT_PATHS[@]}"; do
        while IFS= read -r f; do
            [[ -n "$f" ]] && all_files+=("$f")
        done < <(expand_path "$path")
    done

    if [[ ${#all_files[@]} -eq 0 ]]; then
        die "No git-tracked files found in the specified paths"
    fi

    # Create run directory with timestamp
    local run_id
    run_id=$(date +"%Y%m%d_%H%M%S")
    local run_dir="${AIEXPLAINS_DIR}/${run_id}"
    mkdir -p "${run_dir}/tasks" "${run_dir}/plans"

    # Write files.txt
    printf '%s\n' "${all_files[@]}" > "${run_dir}/files.txt"

    local raw_data_file="${run_dir}/raw_data.txt"
    : > "$raw_data_file"

    # Collect all unique task IDs across all files
    local -A all_task_ids

    # Process each file
    for filepath in "${all_files[@]}"; do
        info "Processing: $filepath"
        process_file "$filepath" "$raw_data_file"

        # Collect task IDs from this file's commit timeline
        while IFS='|' read -r _ _ _ _ _ message; do
            local tid
            tid=$(extract_task_id_from_message "$message")
            if [[ -n "$tid" ]]; then
                all_task_ids["$tid"]=1
            fi
        done < <(git log --follow --format="|%H|%h|%as|%an|%s" --max-count="$MAX_COMMITS" -- "$filepath" 2>/dev/null || true)
    done

    # Extract task and plan files for all unique task IDs
    echo "=== TASK_INDEX ===" >> "$raw_data_file"

    for task_id in $(echo "${!all_task_ids[@]}" | tr ' ' '\n' | sort -t'_' -k1,1n -k2,2n); do
        local task_file_path=""
        local plan_file_path=""

        # Resolve and copy task file
        local resolved_task
        resolved_task=$(resolve_task_file "$task_id" 2>/dev/null || echo "")
        if [[ -n "$resolved_task" && -f "$resolved_task" ]]; then
            local task_dest="${run_dir}/tasks/t${task_id}.md"
            cp "$resolved_task" "$task_dest"
            task_file_path="tasks/t${task_id}.md"
        fi

        # Resolve and copy plan file
        local resolved_plan
        resolved_plan=$(resolve_plan_file "$task_id" 2>/dev/null || echo "")
        if [[ -n "$resolved_plan" && -f "$resolved_plan" ]]; then
            local plan_dest="${run_dir}/plans/p${task_id}.md"
            cp "$resolved_plan" "$plan_dest"
            plan_file_path="plans/p${task_id}.md"
        fi

        echo "${task_id}|${task_file_path}|${plan_file_path}" >> "$raw_data_file"
    done

    echo "=== END TASK_INDEX ===" >> "$raw_data_file"

    # Call Python processor to generate reference.yaml
    local reference_yaml="${run_dir}/reference.yaml"
    info "Processing raw data into YAML..."
    python3 "${SCRIPT_DIR}/aitask_explain_process_raw_data.py" "$raw_data_file" "$reference_yaml"

    echo "RUN_DIR: ${run_dir}"
}

cleanup() {
    local dir="$1"

    # Safety: only delete directories under aiexplains/
    local canonical
    canonical=$(realpath "$dir" 2>/dev/null || echo "$dir")
    local base
    base=$(realpath "$AIEXPLAINS_DIR" 2>/dev/null || echo "$AIEXPLAINS_DIR")

    if [[ "$canonical" != "$base"/* ]]; then
        die "Refusing to delete directory outside ${AIEXPLAINS_DIR}/: $dir"
    fi

    if [[ -d "$dir" ]]; then
        rm -rf "$dir"
        info "Removed: $dir"
        # Remove parent if empty
        rmdir "$AIEXPLAINS_DIR" 2>/dev/null || true
    else
        warn "Directory does not exist: $dir"
    fi
}

# --- Argument Parsing ---

show_help() {
    cat << 'EOF'
Usage: aitask_explain_extract_raw_data.sh [OPTIONS] MODE

Extract raw git data for the aitask-explain skill.

Modes:
  --gather PATH [PATH...]    Analyze files/directories and produce reference data
  --cleanup RUN_DIR          Remove a specific run directory

Options:
  --max-commits N            Limit commits per file (default: 50)
  --help, -h                 Show help

Output:
  Creates a run-specific directory under aiexplains/ with:
  - files.txt       List of analyzed files
  - raw_data.txt    Intermediate pipe-delimited data
  - reference.yaml  Final YAML reference (produced by Python)
  - tasks/          Extracted aitask files (ID-only names)
  - plans/          Extracted aiplan files (ID-only names)

  Prints "RUN_DIR: <path>" to stdout for the skill to capture.

Examples:
  # Analyze a single file
  ./aiscripts/aitask_explain_extract_raw_data.sh --gather aiscripts/lib/task_utils.sh

  # Analyze a directory
  ./aiscripts/aitask_explain_extract_raw_data.sh --gather aiscripts/lib/

  # Analyze with commit limit
  ./aiscripts/aitask_explain_extract_raw_data.sh --gather aiscripts/ --max-commits 20

  # Clean up a run
  ./aiscripts/aitask_explain_extract_raw_data.sh --cleanup aiexplains/20260221_143052
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --gather)
                MODE="gather"
                shift
                # Collect all subsequent non-flag arguments as input paths
                while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do
                    INPUT_PATHS+=("$1")
                    shift
                done
                ;;
            --cleanup)
                MODE="cleanup"
                [[ $# -ge 2 ]] || die "--cleanup requires a directory argument"
                CLEANUP_DIR="$2"
                shift 2
                ;;
            --max-commits)
                [[ $# -ge 2 ]] || die "--max-commits requires a number"
                MAX_COMMITS="$2"
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                # If in gather mode, treat as additional path
                if [[ "$MODE" == "gather" ]]; then
                    INPUT_PATHS+=("$1")
                    shift
                else
                    die "Unknown option: $1. Use --help for usage."
                fi
                ;;
        esac
    done

    if [[ -z "$MODE" ]]; then
        die "Mode required: --gather or --cleanup. Use --help for usage."
    fi
}

main() {
    parse_args "$@"
    case "$MODE" in
        gather) gather ;;
        cleanup) cleanup "$CLEANUP_DIR" ;;
    esac
}

main "$@"
