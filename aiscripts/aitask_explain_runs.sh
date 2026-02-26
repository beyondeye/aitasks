#!/usr/bin/env bash
set -euo pipefail

# aitask_explain_runs.sh - Manage aiexplain run directories
# Lists, inspects, and deletes existing aitask-explain run data.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

AIEXPLAINS_DIR="aiexplains"
MODE=""
DELETE_TARGET=""

# --- Functions ---

# List all runs with their associated files
list_runs() {
    if [[ ! -d "$AIEXPLAINS_DIR" ]]; then
        info "No aiexplains directory found."
        return
    fi

    local found=false

    # Scan top-level runs (exclude codebrowser subdirectory)
    local has_toplevel=false
    for files_txt in "$AIEXPLAINS_DIR"/*/files.txt; do
        [[ -f "$files_txt" ]] || continue
        local run_dir
        run_dir=$(dirname "$files_txt")
        # Skip codebrowser directory
        [[ "$(basename "$run_dir")" == "codebrowser" ]] && continue
        if [[ "$has_toplevel" == false ]]; then
            echo "=== Top-level runs ==="
            echo ""
            has_toplevel=true
        fi
        found=true
        local run_name
        run_name=$(basename "$run_dir")
        local display_name="$run_name"
        if [[ "$run_name" =~ ^(.+)__([0-9]{8}_[0-9]{6})$ ]]; then
            display_name="${BASH_REMATCH[1]} @ ${BASH_REMATCH[2]}"
        fi
        echo "=== RUN: ${display_name} ==="
        echo "FILES:"
        cat "$files_txt"
        echo "=== END RUN ==="
        echo ""
    done

    # Scan codebrowser runs
    local has_codebrowser=false
    for files_txt in "$AIEXPLAINS_DIR"/codebrowser/*/files.txt; do
        [[ -f "$files_txt" ]] || continue
        if [[ "$has_codebrowser" == false ]]; then
            echo "=== Codebrowser runs ==="
            echo ""
            has_codebrowser=true
        fi
        found=true
        local run_dir
        run_dir=$(dirname "$files_txt")
        local run_name
        run_name=$(basename "$run_dir")
        local display_name="$run_name"
        if [[ "$run_name" =~ ^(.+)__([0-9]{8}_[0-9]{6})$ ]]; then
            display_name="${BASH_REMATCH[1]} @ ${BASH_REMATCH[2]}"
        fi
        echo "=== RUN: ${display_name} ==="
        echo "FILES:"
        cat "$files_txt"
        echo "=== END RUN ==="
        echo ""
    done

    if [[ "$found" == false ]]; then
        info "No runs found in ${AIEXPLAINS_DIR}/"
    fi
}

# Delete a specific run directory
delete_run() {
    local dir="$1"

    # Safety: only delete directories under aiexplains/
    if [[ ! -d "$AIEXPLAINS_DIR" ]]; then
        die "No ${AIEXPLAINS_DIR}/ directory exists"
    fi

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

# Delete all run directories
delete_all() {
    if [[ ! -d "$AIEXPLAINS_DIR" ]]; then
        info "No ${AIEXPLAINS_DIR}/ directory exists"
        return
    fi

    local count=0
    for run_dir in "$AIEXPLAINS_DIR"/*/; do
        [[ -d "$run_dir" ]] || continue
        rm -rf "$run_dir"
        count=$((count + 1))
    done

    # Remove parent if empty
    rmdir "$AIEXPLAINS_DIR" 2>/dev/null || true

    if [[ $count -gt 0 ]]; then
        info "Removed $count run(s)"
    else
        info "No runs to remove"
    fi
}

# Interactive mode using fzf
interactive() {
    if [[ ! -d "$AIEXPLAINS_DIR" ]]; then
        info "No ${AIEXPLAINS_DIR}/ directory exists"
        return
    fi

    # Build list of runs with file summaries
    local runs=()
    for files_txt in "$AIEXPLAINS_DIR"/*/files.txt "$AIEXPLAINS_DIR"/codebrowser/*/files.txt; do
        [[ -f "$files_txt" ]] || continue
        local run_dir
        run_dir=$(dirname "$files_txt")
        # Skip codebrowser directory itself (not a run)
        [[ "$(basename "$run_dir")" == "codebrowser" ]] && continue
        local run_name
        run_name=$(basename "$run_dir")
        local display_name="$run_name"
        if [[ "$run_name" =~ ^(.+)__([0-9]{8}_[0-9]{6})$ ]]; then
            display_name="${BASH_REMATCH[1]} @ ${BASH_REMATCH[2]}"
        fi
        local file_count
        file_count=$(wc -l < "$files_txt")
        local first_files
        first_files=$(head -3 "$files_txt" | tr '\n' ', ' | sed 's/,$//')
        # Include relative path for disambiguation
        local rel_path
        rel_path=$(dirname "$files_txt")
        rel_path="${rel_path#"$AIEXPLAINS_DIR"/}"
        runs+=("${rel_path} | ${display_name} (${file_count} files: ${first_files})")
    done

    if [[ ${#runs[@]} -eq 0 ]]; then
        info "No runs found in ${AIEXPLAINS_DIR}/"
        return
    fi

    # Add "Delete all" option
    runs+=("--- Delete ALL runs ---")

    local selected
    selected=$(printf '%s\n' "${runs[@]}" | fzf --prompt="Select run to delete: " --height=40%) || {
        info "No selection made"
        return
    }

    if [[ "$selected" == "--- Delete ALL runs ---" ]]; then
        echo -n "Delete ALL runs? [y/N] "
        read -r confirm
        if [[ "$confirm" =~ ^[Yy] ]]; then
            delete_all
        else
            info "Cancelled"
        fi
    else
        # Extract rel_path (before " | ") to reconstruct full path
        local rel_path
        rel_path="${selected%% | *}"
        local run_path="${AIEXPLAINS_DIR}/${rel_path}"
        local display
        display=$(echo "$selected" | sed 's/^[^ ]* | //' | cut -d' ' -f1-3)
        echo -n "Delete run ${display}? [y/N] "
        read -r confirm
        if [[ "$confirm" =~ ^[Yy] ]]; then
            delete_run "$run_path"
        else
            info "Cancelled"
        fi
    fi
}

# --- Argument Parsing ---

show_help() {
    cat << 'EOF'
Usage: aitask_explain_runs.sh [OPTIONS]

Manage aiexplain run directories.

Modes:
  (no flags)                 Interactive mode using fzf
  --list                     List all runs with their files
  --delete RUN_DIR           Delete a specific run directory
  --delete-all               Delete all runs
  --cleanup-stale            Remove stale runs (keeps newest per source directory)

Options:
  --help, -h                 Show help

Examples:
  # List all runs (top-level and codebrowser)
  ./aiscripts/aitask_explain_runs.sh --list

  # Delete a specific run
  ./aiscripts/aitask_explain_runs.sh --delete aiexplains/aiscripts__lib__20260226_155403

  # Delete all runs
  ./aiscripts/aitask_explain_runs.sh --delete-all

  # Remove stale runs (delegates to aitask_explain_cleanup.sh --all)
  ./aiscripts/aitask_explain_runs.sh --cleanup-stale

  # Interactive selection
  ./aiscripts/aitask_explain_runs.sh
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --list)
                MODE="list"
                shift
                ;;
            --delete)
                MODE="delete"
                [[ $# -ge 2 ]] || die "--delete requires a directory argument"
                DELETE_TARGET="$2"
                shift 2
                ;;
            --delete-all)
                MODE="delete-all"
                shift
                ;;
            --cleanup-stale)
                MODE="cleanup-stale"
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                die "Unknown option: $1. Use --help for usage."
                ;;
        esac
    done

    # Default to interactive mode
    if [[ -z "$MODE" ]]; then
        MODE="interactive"
    fi
}

main() {
    parse_args "$@"
    case "$MODE" in
        list) list_runs ;;
        delete) delete_run "$DELETE_TARGET" ;;
        delete-all) delete_all ;;
        cleanup-stale) exec "$SCRIPT_DIR/aitask_explain_cleanup.sh" --all ;;
        interactive) interactive ;;
    esac
}

main "$@"
