#!/usr/bin/env bash
# aitask_web_merge.sh - Detect branches with completed Claude Web task executions
#
# Scans remote branches for .aitask-data-updated/completed_*.json markers.
# Outputs structured lines for the calling skill to parse and handle interactively.
#
# Usage:
#   ./aiscripts/aitask_web_merge.sh              # Scan using cached remote data
#   ./aiscripts/aitask_web_merge.sh --fetch      # Fetch first, then scan
#
# Output format (one line per completed branch):
#   COMPLETED:<branch>:<completed_filename>
#
# If no completions found:
#   NONE

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

# --- Configuration ---
DO_FETCH=false

# --- Help ---
show_help() {
    cat <<'EOF'
Usage: aitask_web_merge.sh [options]

Scan remote branches for completed Claude Web task executions.

Options:
  --fetch       Run git fetch --all --prune before scanning
  --help, -h    Show this help

Output format:
  COMPLETED:<branch>:<completed_filename>    For each detected branch
  NONE                                       If no completions found

Examples:
  ./aiscripts/aitask_web_merge.sh --fetch    # Fetch and scan
  ./aiscripts/aitask_web_merge.sh            # Scan cached data only
EOF
}

# --- Argument Parsing ---
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --fetch)
                DO_FETCH=true
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
                die "Unexpected argument: $1. Use --help for usage."
                ;;
        esac
    done
}

# --- Known branches to skip ---
is_skip_branch() {
    local branch="$1"
    case "$branch" in
        main|master|aitask-data|aitask-locks|aitask-ids)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# --- Main ---
main() {
    parse_args "$@"

    if [[ "$DO_FETCH" == true ]]; then
        git fetch --all --prune --quiet 2>/dev/null || warn "Fetch failed, using cached remote data"
    fi

    local found=0

    # Iterate over remote-tracking branches
    while IFS= read -r ref; do
        # Strip leading whitespace and "origin/" prefix
        ref="${ref#"${ref%%[![:space:]]*}"}"
        local branch="${ref#origin/}"

        # Skip known infrastructure branches
        if is_skip_branch "$branch"; then
            continue
        fi

        # Check for completion markers in .aitask-data-updated/
        local markers
        markers=$(git ls-tree --name-only "origin/${branch}:.aitask-data-updated/" 2>/dev/null | grep '^completed_' || true)

        if [[ -z "$markers" ]]; then
            continue
        fi

        # Output one line per marker found
        while IFS= read -r marker; do
            if [[ -n "$marker" ]]; then
                echo "COMPLETED:${branch}:${marker}"
                found=$((found + 1))
            fi
        done <<< "$markers"
    done < <(git branch -r --no-color 2>/dev/null | grep '^[[:space:]]*origin/' | grep -v 'HEAD')

    if [[ "$found" -eq 0 ]]; then
        echo "NONE"
    fi
}

main "$@"
