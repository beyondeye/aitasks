#!/usr/bin/env bash
set -euo pipefail

# aitask_find_files.sh - Search project files by keyword content or fuzzy name matching
# Returns ranked, pipe-delimited results for the user-file-select skill.
#
# Usage:
#   aitask_find_files.sh --keywords "term1 term2" [--max-results N]
#   aitask_find_files.sh --names "partial1 partial2" [--max-results N]
#
# Output format (one line per result, pipe-delimited):
#   <rank>|<score>|<file_path>
#
# Called by:
#   .claude/skills/user-file-select/SKILL.md

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

# --- Defaults ---
MODE=""
SEARCH_TERMS=""
MAX_RESULTS=20

# --- Functions ---

show_help() {
    cat << 'EOF'
Usage: aitask_find_files.sh [OPTIONS]

Search git-tracked project files by keyword content or fuzzy name matching.

Modes:
  --keywords "term1 term2 ..."    Search inside file contents for keywords
  --names "partial1 partial2 ..." Fuzzy-match filenames and paths (uses fzf)

Options:
  --max-results N                 Maximum results to return (default: 20)
  --help, -h                      Show this help

Output format (pipe-delimited, one per line):
  <rank>|<score>|<file_path>

Examples:
  aitask_find_files.sh --keywords "resolve task archive"
  aitask_find_files.sh --names "task_utils terminal_compat"
  aitask_find_files.sh --keywords "git commit" --max-results 10
EOF
}

search_keywords() {
    local terms_string="$1"
    local max="$2"

    # Split search terms into array
    local -a terms
    read -ra terms <<< "$terms_string"

    if [[ ${#terms[@]} -eq 0 ]]; then
        die "No keywords provided"
    fi

    # Use a temp file to accumulate per-file scores
    local score_file
    score_file=$(mktemp)

    # For each keyword, get match count per file using grep -ciI
    for term in "${terms[@]}"; do
        # grep -c outputs file:count, -i case insensitive, -I skip binary
        # || true prevents set -e from killing us when grep finds no matches (exit 1)
        git ls-files -z | xargs -0 grep -ciI -- "$term" 2>/dev/null || true
    done >> "$score_file"

    if [[ ! -s "$score_file" ]]; then
        rm -f "$score_file"
        exit 0
    fi

    # Parse "file:count" lines, sum per file, sort, rank
    # Handle filenames with colons: last field after : is the count
    awk -F: '{
        count = $NF + 0
        if (count <= 0) next
        # Reconstruct filename from all fields except the last
        file = $1
        for (i = 2; i < NF; i++) file = file ":" $i
        scores[file] += count
    } END {
        for (f in scores) print scores[f], f
    }' "$score_file" \
        | sort -rn -k1,1 \
        | head -n "$max" \
        | awk '{rank++; printf "%d|%d|%s\n", rank, $1, $2}'

    rm -f "$score_file"
}

search_names() {
    local terms_string="$1"
    local max="$2"

    # Check fzf is available
    if ! command -v fzf &>/dev/null; then
        die "fzf is required for name search but not found. Install fzf first."
    fi

    # Split search terms into array
    local -a terms
    read -ra terms <<< "$terms_string"

    if [[ ${#terms[@]} -eq 0 ]]; then
        die "No search names provided"
    fi

    # Get all git-tracked files
    local files_list
    files_list=$(git ls-files)

    if [[ -z "$files_list" ]]; then
        die "No git-tracked files found"
    fi

    # Score cap for position-based ranking
    local score_cap="$max"

    # Use a temp file to accumulate per-file scores across terms
    local score_file
    score_file=$(mktemp)

    for term in "${terms[@]}"; do
        # fzf --filter outputs matches ranked by best match first
        local matches
        matches=$(echo "$files_list" | fzf --filter="$term" 2>/dev/null | head -n "$score_cap" || true)

        if [[ -z "$matches" ]]; then
            continue
        fi

        # Assign position-based scores: first result gets score_cap points, second gets score_cap-1, etc.
        local rank=0
        while IFS= read -r file; do
            local points=$(( score_cap - rank ))
            if [[ $points -le 0 ]]; then
                break
            fi
            echo "${points} ${file}"
            (( rank++ )) || true
        done <<< "$matches"
    done >> "$score_file"

    if [[ ! -s "$score_file" ]]; then
        rm -f "$score_file"
        exit 0
    fi

    # Aggregate scores per file, sort, rank, output
    awk '{
        scores[$2] += $1
    } END {
        for (f in scores) print scores[f], f
    }' "$score_file" \
        | sort -rn -k1,1 \
        | head -n "$max" \
        | awk '{rank++; printf "%d|%d|%s\n", rank, $1, $2}'

    rm -f "$score_file"
}

# --- Argument Parsing ---

while [[ $# -gt 0 ]]; do
    case "$1" in
        --keywords)
            MODE="keywords"
            SEARCH_TERMS="${2:?--keywords requires a quoted string of terms}"
            shift 2
            ;;
        --names)
            MODE="names"
            SEARCH_TERMS="${2:?--names requires a quoted string of terms}"
            shift 2
            ;;
        --max-results)
            MAX_RESULTS="${2:?--max-results requires a number}"
            shift 2
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            die "Unknown argument: $1. Use --help for usage."
            ;;
    esac
done

if [[ -z "$MODE" ]]; then
    die "Mode required: --keywords or --names. Use --help for usage."
fi

# Validate we're in a git repo
if ! git rev-parse --is-inside-work-tree &>/dev/null; then
    die "Not a git repository"
fi

# --- Main ---

case "$MODE" in
    keywords) search_keywords "$SEARCH_TERMS" "$MAX_RESULTS" ;;
    names)    search_names "$SEARCH_TERMS" "$MAX_RESULTS" ;;
esac
