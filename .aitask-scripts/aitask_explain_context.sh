#!/usr/bin/env bash
set -euo pipefail

# aitask_explain_context.sh - Gather historical architectural context for planning
# Orchestrates codebrowser cache and calls Python formatter for output.
#
# Usage: ./.aitask-scripts/aitask_explain_context.sh --max-plans N <file1> [file2...]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

# --- Defaults ---
MAX_PLANS=0
INPUT_FILES=()
declare -A INPUT_BY_PROJECT=()
CODEBROWSER_DIR=".aitask-explain/codebrowser"
EXTRACT_SCRIPT="$SCRIPT_DIR/aitask_explain_extract_raw_data.sh"
FORMAT_SCRIPT="$SCRIPT_DIR/aitask_explain_format_context.py"
RESOLVE_SCRIPT="$SCRIPT_DIR/aitask_project_resolve.sh"
LOCAL_PROJECT_KEY="_local_"

PYTHON="$(require_ait_python)"

# --- Functions ---

show_help() {
    cat << 'EOF'
Usage: aitask_explain_context.sh --max-plans N <file_or_token> [...]

Gather historical architectural context from aitask-explain data.

Input tokens (mixable in a single invocation):
  <path>                       Bare file path — resolved against the local project.
  --project <name>:<path>      Resolve <path> against the project registered as <name>.
                               The pair is repeatable.
  <name>#<path>                Short notation equivalent to --project <name>:<path>.

Options:
  --max-plans N    Maximum plans per file for greedy selection (required; 0 = no-op)
  --help, -h       Show help

Output:
  ONE unified markdown document to stdout, spanning all referenced projects.
  Progress messages go to stderr.

Notes:
  Each project's cache lands under its own .aitask-explain/codebrowser/ tree.
  Cross-repo names resolve via aitask_project_resolve.sh (registry +
  AITASKS_PROJECT_<name> env override).

Examples:
  ./.aitask-scripts/aitask_explain_context.sh --max-plans 3 .aitask-scripts/aitask_archive.sh
  ./.aitask-scripts/aitask_explain_context.sh --max-plans 1 src/foo.py src/bar.py
  ./.aitask-scripts/aitask_explain_context.sh --max-plans 1 \
      --project aitasks_mobile:src/foo.kt --project aitasks:.aitask-scripts/aitask_ls.sh
  ./.aitask-scripts/aitask_explain_context.sh --max-plans 1 \
      aitasks_mobile#src/foo.kt aitasks#.aitask-scripts/aitask_ls.sh
EOF
}

add_input_file() {
    local project="$1" file="$2"
    INPUT_FILES+=("$file")
    if [[ -n "${INPUT_BY_PROJECT[$project]:-}" ]]; then
        INPUT_BY_PROJECT["$project"]+=$'\n'"$file"
    else
        INPUT_BY_PROJECT["$project"]="$file"
    fi
}

# Classify a positional token and route it to add_input_file. Tokens matching
# `<name>#<path>` are treated as cross-repo references (mirrors the
# `aitasks#835_3` notation from aidocs/cross_repo_references.md, adapted to
# file paths). Anything else is a local file.
classify_token() {
    local token="$1"
    if [[ "$token" =~ ^([a-z0-9_-]+)#(.+)$ ]]; then
        add_input_file "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
    else
        add_input_file "$LOCAL_PROJECT_KEY" "$token"
    fi
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --max-plans)
                [[ $# -ge 2 ]] || die "--max-plans requires a number"
                MAX_PLANS="$2"
                shift 2
                ;;
            --project)
                [[ $# -ge 2 ]] || die "--project requires a value"
                local arg="$2"
                [[ "$arg" == *:* ]] || die "--project requires <name>:<file>, got '$arg'"
                local pname="${arg%%:*}"
                local pfile="${arg#*:}"
                [[ -n "$pname" && -n "$pfile" ]] || die "--project requires non-empty name and file, got '$arg'"
                add_input_file "$pname" "$pfile"
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            --)
                shift
                while [[ $# -gt 0 ]]; do
                    classify_token "$1"
                    shift
                done
                break
                ;;
            *)
                classify_token "$1"
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

process_directory_in_project() {
    local project_root="$1"
    local dir_key="$2"
    # Subshell so the caller's PWD is preserved. Cache writes happen via the
    # relative CODEBROWSER_DIR, so cd'ing into the project root lands the
    # cache inside that project's own .aitask-explain/codebrowser/ tree.
    # We absolutize the emitted ref:rundir pair so the caller (in a different
    # CWD) can hand it to the Python formatter without path resolution
    # surprises.
    (
        cd "$project_root" || exit 1
        local pair
        pair=$(process_directory "$dir_key") || exit 1
        [[ -n "$pair" ]] || exit 1
        local ref_rel="${pair%%:*}"
        local run_rel="${pair#*:}"
        local abs_root
        abs_root=$(pwd)
        printf '%s:%s\n' "$abs_root/$ref_rel" "$abs_root/$run_rel"
    )
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

resolve_project_root() {
    local name="$1"
    if [[ "$name" == "$LOCAL_PROJECT_KEY" ]]; then
        pwd
        return 0
    fi
    local resolved
    resolved=$("$RESOLVE_SCRIPT" "$name")
    case "$resolved" in
        RESOLVED:*)
            echo "${resolved#RESOLVED:}"
            ;;
        STALE:*)
            die "Project '$name' is registered but its path is stale: ${resolved#STALE:}. Run \`cd /path/to/$name && ait projects add\` to refresh."
            ;;
        NOT_FOUND:*)
            die "Project '$name' is not registered. Run \`cd /path/to/$name && ait projects add\`."
            ;;
        *)
            die "Resolver returned unexpected output for '$name': $resolved"
            ;;
    esac
}

main() {
    parse_args "$@"

    if [[ "$MAX_PLANS" -eq 0 ]]; then
        exit 0
    fi

    if [[ ${#INPUT_FILES[@]} -eq 0 ]]; then
        die "No input files specified. Usage: $0 --max-plans N <file1> [file2...]"
    fi

    # Per project: resolve root, group its files by directory, process each
    # directory inside the project's tree, accumulate ref:rundir pairs.
    local ref_pairs=()
    local project_name files_blob f dir key project_root pair
    for project_name in "${!INPUT_BY_PROJECT[@]}"; do
        project_root=$(resolve_project_root "$project_name")
        files_blob="${INPUT_BY_PROJECT[$project_name]}"
        declare -A dir_groups=()
        while IFS= read -r f; do
            [[ -n "$f" ]] || continue
            dir=$(dirname "$f")
            key=$(dir_to_key "$dir")
            dir_groups["$key"]=1
        done <<< "$files_blob"

        for key in "${!dir_groups[@]}"; do
            pair=$(process_directory_in_project "$project_root" "$key" 2>/dev/null) || continue
            if [[ "$pair" == *"/reference.yaml:"* ]]; then
                ref_pairs+=("$pair")
            fi
        done
        unset dir_groups
    done

    if [[ ${#ref_pairs[@]} -eq 0 ]]; then
        exit 0
    fi

    # Build --ref arguments for the Python formatter
    local ref_args=()
    for pair in "${ref_pairs[@]}"; do
        ref_args+=(--ref "$pair")
    done

    # Call the Python formatter once with all refs. Target files are passed
    # stripped of any project prefix; reference.yaml stores project-relative
    # paths, so the formatter matches them correctly across all refs.
    "$PYTHON" "$FORMAT_SCRIPT" \
        --max-plans "$MAX_PLANS" \
        "${ref_args[@]}" \
        -- "${INPUT_FILES[@]}"
}

main "$@"
