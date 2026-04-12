#!/usr/bin/env bash
# aitask_fold_content.sh - Build merged description body for a folded task set
#
# Prints the merged description to stdout in the structure documented in
# .claude/skills/task-workflow/task-fold-content.md:
#   1. Primary description body (unchanged)
#   2. One "## Merged from t<N>: <name>" section per folded task
#   3. A final "## Folded Tasks" reference section
#
# The primary description can be read from a file (positional argument) or
# piped through stdin (--primary-stdin).
#
# Usage:
#   aitask_fold_content.sh <primary_file> <folded1> [<folded2> ...]
#   aitask_fold_content.sh --primary-stdin <folded1> [<folded2> ...]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

usage() {
    cat <<EOF
Usage: $0 <primary_file> <folded1> [<folded2> ...]
       $0 --primary-stdin <folded1> [<folded2> ...]

Emits a merged description body to stdout. Frontmatter is stripped from all
input files. See task-fold-content.md for the exact output structure.
EOF
    exit 1
}

use_stdin=false
primary_file=""
folded=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --primary-stdin)
            use_stdin=true
            shift
            ;;
        --help|-h)
            usage
            ;;
        -*)
            die "unknown flag: $1"
            ;;
        *)
            if [[ "$use_stdin" == false && -z "$primary_file" ]]; then
                primary_file="$1"
            else
                folded+=("$1")
            fi
            shift
            ;;
    esac
done

if [[ "$use_stdin" == false && -z "$primary_file" ]]; then
    die "need primary file (or --primary-stdin)"
fi
[[ ${#folded[@]} -eq 0 ]] && die "need at least one folded task file"

# Extract the description body (everything after the closing frontmatter ---).
# Uses awk for macOS portability (no GNU sed features).
extract_body() {
    awk '
        BEGIN { in_fm = 0; seen_open = 0 }
        {
            if ($0 == "---") {
                if (seen_open == 0) { seen_open = 1; in_fm = 1; next }
                else if (in_fm == 1) { in_fm = 0; next }
            }
            if (seen_open == 1 && in_fm == 0) print
        }
    ' "$1"
}

if [[ "$use_stdin" == true ]]; then
    primary_body=$(cat)
else
    primary_body=$(extract_body "$primary_file")
fi

# Emit primary body unchanged.
printf '%s\n' "$primary_body"

# Parse each folded file's filename into a numeric ID and a human-readable name,
# emit the "## Merged from t<N>: <name>" section, and collect a reference list.
folded_refs=()
for f in "${folded[@]}"; do
    [[ -f "$f" ]] || die "folded file not found: $f"
    base=$(basename "$f")
    stem="${base#t}"
    stem="${stem%.md}"

    if [[ "$stem" =~ ^([0-9]+)_([0-9]+)_(.+)$ ]]; then
        n="${BASH_REMATCH[1]}_${BASH_REMATCH[2]}"
        name="${BASH_REMATCH[3]}"
    elif [[ "$stem" =~ ^([0-9]+)_(.+)$ ]]; then
        n="${BASH_REMATCH[1]}"
        name="${BASH_REMATCH[2]}"
    else
        die "cannot parse filename: $base"
    fi

    display_name="${name//_/ }"
    printf '\n## Merged from t%s: %s\n\n' "$n" "$display_name"
    extract_body "$f"
    folded_refs+=("- **t${n}** (\`${base}\`)")
done

# Emit the Folded Tasks reference section.
printf '\n## Folded Tasks\n\nThe following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.\n\n'
for ref in "${folded_refs[@]}"; do
    printf '%s\n' "$ref"
done
