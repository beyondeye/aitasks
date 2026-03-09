#!/usr/bin/env bash

# aitask_codemap.sh - Structural scanning for project code areas
# Internal-only script (NOT an ait subcommand).
# Scans the repo structure and generates code_areas.yaml skeleton.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

# Framework directories to exclude from scanning
EXCLUDE_DIRS=(
    ".aitask-scripts"
    "aitasks"
    "aiplans"
    "aireviewguides"
    ".claude"
    ".gemini"
    ".agents"
    ".opencode"
    "seed"
    "node_modules"
    "__pycache__"
    ".git"
    "aiwork"
    "aidocs"
)

ARG_SCAN=false
ARG_EXISTING=""
ARG_WRITE=false
ARG_HELP=false

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --scan) ARG_SCAN=true; shift ;;
            --existing) ARG_EXISTING="$2"; shift 2 ;;
            --write) ARG_WRITE=true; shift ;;
            --help|-h) ARG_HELP=true; shift ;;
            *) die "Unknown argument: $1" ;;
        esac
    done
}

show_help() {
    cat <<'HELP'
Usage: aitask_codemap.sh [OPTIONS]

Scan repository structure and generate code_areas.yaml skeleton.

Options:
  --scan                   Scan repo and output YAML to stdout
  --scan --existing <path> Scan and output only areas not in existing file
  --write                  Write skeleton to aitasks/metadata/code_areas.yaml
  --help                   Show this help

Examples:
  ./.aitask-scripts/aitask_codemap.sh --scan
  ./.aitask-scripts/aitask_codemap.sh --scan --existing aitasks/metadata/code_areas.yaml
  ./.aitask-scripts/aitask_codemap.sh --write
HELP
}

is_excluded() {
    local dir="$1"
    for excl in "${EXCLUDE_DIRS[@]}"; do
        if [[ "$dir" == "$excl" ]]; then
            return 0
        fi
    done
    return 1
}

# Clean up directory name into a human-readable description
clean_description() {
    local name="$1"
    # Replace hyphens and underscores with spaces
    name="${name//-/ }"
    name="${name//_/ }"
    echo "$name"
}

# Get immediate subdirectories of a path from git-tracked files
get_subdirs() {
    local parent="$1"
    git ls-files -- "$parent" 2>/dev/null \
        | sed -n "s|^${parent}/\([^/]*\)/.*|\1|p" \
        | sort -u
}

# Extract existing area paths from a code_areas.yaml file
extract_existing_paths() {
    local file="$1"
    if [[ ! -f "$file" ]]; then
        return
    fi
    grep -E '^\s+path:' "$file" 2>/dev/null \
        | sed 's/^[[:space:]]*path:[[:space:]]*//' \
        | sed 's/[[:space:]]*$//'
}

scan_and_output() {
    local existing_file="$1"
    local -a existing_paths=()

    if [[ -n "$existing_file" ]]; then
        while IFS= read -r p; do
            [[ -n "$p" ]] && existing_paths+=("$p")
        done < <(extract_existing_paths "$existing_file")
    fi

    # Get top-level directories from git-tracked files
    local -a top_dirs=()
    while IFS= read -r dir; do
        [[ -z "$dir" ]] && continue
        is_excluded "$dir" && continue
        top_dirs+=("$dir")
    done < <(git ls-files 2>/dev/null | sed -n 's|^\([^/]*\)/.*|\1|p' | sort -u)

    if [[ ${#top_dirs[@]} -eq 0 ]]; then
        warn "No directories found in git-tracked files"
        echo "version: 1"
        echo ""
        echo "areas: []"
        return
    fi

    # Check if a path is already mapped
    is_mapped() {
        local path="$1"
        for ep in "${existing_paths[@]+"${existing_paths[@]}"}"; do
            if [[ "$ep" == "$path" ]]; then
                return 0
            fi
        done
        return 1
    }

    echo "version: 1"
    echo ""
    echo "areas:"

    local has_areas=false
    for dir in "${top_dirs[@]}"; do
        local dir_path="${dir}/"

        # Skip if already mapped (when --existing is used)
        if [[ ${#existing_paths[@]} -gt 0 ]] && is_mapped "$dir_path"; then
            continue
        fi

        has_areas=true
        local desc
        desc=$(clean_description "$dir")
        echo "  - name: $dir"
        echo "    path: $dir_path"
        echo "    description: $desc"

        # Check for subdirectories — if >2, generate children
        local -a subdirs=()
        while IFS= read -r sub; do
            [[ -z "$sub" ]] && continue
            is_excluded "$sub" && continue
            subdirs+=("$sub")
        done < <(get_subdirs "$dir")

        if [[ ${#subdirs[@]} -gt 2 ]]; then
            echo "    children:"
            for sub in "${subdirs[@]}"; do
                local sub_path="${dir}/${sub}/"
                if [[ ${#existing_paths[@]} -gt 0 ]] && is_mapped "$sub_path"; then
                    continue
                fi
                local sub_desc
                sub_desc=$(clean_description "$sub")
                echo "      - name: $sub"
                echo "        path: $sub_path"
                echo "        description: $sub_desc"
            done
        fi
    done

    if [[ "$has_areas" == false ]]; then
        # All areas already mapped
        echo "  []"
    fi
}

main() {
    parse_args "$@"

    if [[ "$ARG_HELP" == true ]]; then
        show_help
        exit 0
    fi

    if [[ "$ARG_WRITE" == true ]]; then
        local target="$TASK_DIR/metadata/code_areas.yaml"
        if [[ -f "$target" ]]; then
            die "code_areas.yaml already exists at $target. Use --scan --existing to find unmapped areas."
        fi
        mkdir -p "$TASK_DIR/metadata"
        scan_and_output "" > "$target"
        info "Written to $target"
        exit 0
    fi

    if [[ "$ARG_SCAN" == true ]]; then
        scan_and_output "$ARG_EXISTING"
        exit 0
    fi

    die "No action specified. Use --scan, --write, or --help."
}

main "$@"
