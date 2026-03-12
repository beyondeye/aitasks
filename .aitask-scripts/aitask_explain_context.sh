#!/usr/bin/env bash
set -euo pipefail

# aitask_explain_context.sh - Gather historical architectural context for planning
# Orchestrates codebrowser cache and calls Python formatter for output.
#
# Usage: ./.aitask-scripts/aitask_explain_context.sh --max-plans N <file1> [file2...]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

# --- Defaults ---
MAX_PLANS=0
INPUT_FILES=()
CODEBROWSER_DIR=".aitask-explain/codebrowser"
EXTRACT_SCRIPT="$SCRIPT_DIR/aitask_explain_extract_raw_data.sh"
FORMAT_SCRIPT="$SCRIPT_DIR/aitask_explain_format_context.py"

# --- Functions ---

show_help() {
    cat << 'EOF'
Usage: aitask_explain_context.sh --max-plans N <file1> [file2...]

Gather historical architectural context from aitask-explain data.

Options:
  --max-plans N    Maximum plans per file for greedy selection (required; 0 = no-op)
  --help, -h       Show help

Output:
  Formatted markdown to stdout with historical plan content.
  Progress messages go to stderr.

Examples:
  ./.aitask-scripts/aitask_explain_context.sh --max-plans 3 .aitask-scripts/aitask_archive.sh
  ./.aitask-scripts/aitask_explain_context.sh --max-plans 1 src/foo.py src/bar.py
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --max-plans)
                [[ $# -ge 2 ]] || die "--max-plans requires a number"
                MAX_PLANS="$2"
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            --)
                shift
                INPUT_FILES+=("$@")
                break
                ;;
            *)
                INPUT_FILES+=("$1")
                shift
                ;;
        esac
    done
}

dir_to_key() {
    local dir="$1"
    if [[ "$dir" == "." || -z "$dir" ]]; then
        echo "_root_"
    else
        local trimmed="${dir%/}"
        echo "${trimmed//\//__}"
    fi
}

find_run_dir() {
    local dir_key="$1"
    local pattern="${CODEBROWSER_DIR}/${dir_key}__"
    local latest=""
    for d in "${pattern}"[0-9]*; do
        [[ -d "$d" ]] || continue
        latest="$d"
    done
    echo "$latest"
}

parse_run_timestamp() {
    local run_dir="$1"
    local dir_name
    dir_name=$(basename "$run_dir")

    # Timestamp is last 15 chars: YYYYMMDD_HHMMSS
    local ts_str="${dir_name: -15}"
    if [[ ${#ts_str} -ne 15 || "${ts_str:8:1}" != "_" ]]; then
        echo "0"
        return
    fi

    local year="${ts_str:0:4}"
    local month="${ts_str:4:2}"
    local day="${ts_str:6:2}"
    local hour="${ts_str:9:2}"
    local min="${ts_str:11:2}"
    local sec="${ts_str:13:2}"

    local ts
    if date --version &>/dev/null; then
        # GNU date (Linux)
        ts=$(date -d "${year}-${month}-${day} ${hour}:${min}:${sec}" +%s 2>/dev/null || echo "0")
    else
        # BSD date (macOS)
        ts=$(date -j -f "%Y%m%d_%H%M%S" "$ts_str" +%s 2>/dev/null || echo "0")
    fi
    echo "$ts"
}

check_stale() {
    local dir_key="$1"
    local run_dir="$2"

    local run_ts
    run_ts=$(parse_run_timestamp "$run_dir")
    if [[ "$run_ts" -eq 0 ]]; then
        echo "false"
        return
    fi

    # Convert dir_key back to path
    local dir_path
    if [[ "$dir_key" == "_root_" ]]; then
        dir_path="."
    else
        dir_path="${dir_key//__//}"
    fi

    local git_ts
    git_ts=$(git log -1 --format=%ct -- "$dir_path" 2>/dev/null || echo "0")
    git_ts="${git_ts:-0}"

    if [[ "$git_ts" -gt "$run_ts" ]]; then
        echo "true"
    else
        echo "false"
    fi
}

process_directory() {
    local dir_key="$1"

    local run_dir
    run_dir=$(find_run_dir "$dir_key")

    if [[ -n "$run_dir" ]]; then
        local stale
        stale=$(check_stale "$dir_key" "$run_dir")
        if [[ "$stale" == "true" ]]; then
            info "Cache stale for $dir_key, regenerating..." >&2
            rm -rf "$run_dir"
            run_dir=""
        fi
    fi

    if [[ -z "$run_dir" ]]; then
        info "Generating explain data for $dir_key..." >&2

        # Convert dir_key back to path for the extract script
        local dir_path
        if [[ "$dir_key" == "_root_" ]]; then
            dir_path="."
        else
            dir_path="${dir_key//__//}"
        fi

        # Run the extract pipeline (capture stdout+stderr to parse RUN_DIR)
        local extract_output
        extract_output=$(AITASK_EXPLAIN_DIR="$CODEBROWSER_DIR" \
            "$EXTRACT_SCRIPT" --no-recurse --gather \
            --source-key "$dir_key" "$dir_path" 2>&1) || {
            warn "Extract pipeline failed for $dir_key, skipping" >&2
            return 1
        }

        # Parse RUN_DIR from output
        run_dir=$(echo "$extract_output" | grep '^RUN_DIR: ' | sed 's/^RUN_DIR: //')
        if [[ -z "$run_dir" ]]; then
            warn "No RUN_DIR in extract output for $dir_key" >&2
            return 1
        fi
    fi

    # Verify reference.yaml exists
    local ref_yaml="${run_dir}/reference.yaml"
    if [[ ! -f "$ref_yaml" ]]; then
        warn "No reference.yaml in $run_dir" >&2
        return 1
    fi

    # Output ref:rundir pair (only stdout output from this function)
    echo "${ref_yaml}:${run_dir}"
}

main() {
    parse_args "$@"

    if [[ "$MAX_PLANS" -eq 0 ]]; then
        exit 0
    fi

    if [[ ${#INPUT_FILES[@]} -eq 0 ]]; then
        die "No input files specified. Usage: $0 --max-plans N <file1> [file2...]"
    fi

    # Group files by directory (collect unique dir keys)
    declare -A dir_groups
    for f in "${INPUT_FILES[@]}"; do
        local dir
        dir=$(dirname "$f")
        local key
        key=$(dir_to_key "$dir")
        dir_groups["$key"]=1
    done

    # Process each directory and collect ref:rundir pairs
    local ref_pairs=()
    for dir_key in "${!dir_groups[@]}"; do
        local pair
        pair=$(process_directory "$dir_key" 2>/dev/null) || continue
        if [[ "$pair" == *"/reference.yaml:"* ]]; then
            ref_pairs+=("$pair")
        fi
    done

    if [[ ${#ref_pairs[@]} -eq 0 ]]; then
        exit 0
    fi

    # Build --ref arguments for the Python formatter
    local ref_args=()
    for pair in "${ref_pairs[@]}"; do
        ref_args+=(--ref "$pair")
    done

    # Call the Python formatter
    python3 "$FORMAT_SCRIPT" \
        --max-plans "$MAX_PLANS" \
        "${ref_args[@]}" \
        -- "${INPUT_FILES[@]}"
}

main "$@"
