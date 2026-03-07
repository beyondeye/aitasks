#!/usr/bin/env bash
set -euo pipefail

# aitask_changelog.sh - Gather changelog data from commits and archived plans
# Used by the aitask-changelog Claude Code skill to generate CHANGELOG.md entries.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

# --- Options ---
MODE=""
FROM_TAG=""
CHECK_VERSION=""

# --- Changelog-specific functions ---

# Get the latest release tag (highest semver with v prefix)
get_latest_tag() {
    git tag --list 'v*' --sort=-version:refname | head -1
}

# Extract unique task IDs from commit messages (parenthesized pattern only)
# Input: commit lines from stdin
# Output: one task ID per line (e.g., "89", "85_10"), sorted and unique
extract_task_ids_from_commits() {
    grep -oE '\(t[0-9]+(_[0-9]+)?\)' | sed 's/[()]//g; s/^t//' | sort -u -t'_' -k1,1n -k2,2n
}

# Extract issue_type from a task file's YAML frontmatter
# Input: task file path
# Output: issue type string (defaults to "feature")
extract_issue_type() {
    local file_path="$1"
    local in_yaml=false

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then break; else in_yaml=true; continue; fi
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^issue_type:[[:space:]]*(.*) ]]; then
            local val="${BASH_REMATCH[1]}"
            val=$(echo "$val" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$val"
            return
        fi
    done < "$file_path"

    echo "feature"
}

# Extract a human-readable title from a task filename
# Input: task file path (e.g., "aitasks/archived/t89_detect_capable_terminal_on_windows.md")
# Output: "detect capable terminal on windows"
extract_task_title() {
    local file_path="$1"
    local basename
    basename=$(basename "$file_path" .md)
    # Remove the tNN_ or tNN_MM_ prefix
    local title
    title=$(echo "$basename" | sed -E 's/^t[0-9]+(_[0-9]+)?_//')
    # Replace underscores with spaces
    echo "$title" | tr '_' ' '
}

# Check if CHANGELOG.md has a section for the given version
# Input: version string (without v prefix, e.g., "0.2.0")
# Returns: 0 if found, 1 if not
check_changelog_version() {
    local version="$1"
    if [[ ! -f CHANGELOG.md ]]; then
        return 1
    fi
    grep -qE "^## v${version}[[:space:]]*$" CHANGELOG.md
}

# --- Main modes ---

gather() {
    local tag="${FROM_TAG:-$(get_latest_tag)}"
    if [[ -z "$tag" ]]; then
        die "No release tags found. Cannot determine base for changelog."
    fi
    echo "BASE_TAG: $tag"
    echo ""

    local commits
    commits=$(git log "${tag}..HEAD" --oneline 2>/dev/null || true)
    if [[ -z "$commits" ]]; then
        info "No commits found since $tag"
        exit 0
    fi

    local task_ids
    task_ids=$(echo "$commits" | extract_task_ids_from_commits || true)
    if [[ -z "$task_ids" ]]; then
        info "No task IDs found in commits since $tag"
        echo "COMMITS_ONLY:"
        echo "$commits"
        exit 0
    fi

    while IFS= read -r task_id; do
        [[ -z "$task_id" ]] && continue

        echo "=== TASK t${task_id} ==="

        # Resolve task file for issue_type and title
        local task_file
        task_file=$(resolve_task_file "$task_id" 2>/dev/null || echo "")
        if [[ -n "$task_file" ]]; then
            echo "ISSUE_TYPE: $(extract_issue_type "$task_file")"
            echo "TITLE: $(extract_task_title "$task_file")"
        else
            echo "ISSUE_TYPE: feature"
            echo "TITLE: t${task_id}"
        fi

        # Resolve plan file and extract notes
        local plan_file
        plan_file=$(resolve_plan_file "$task_id" 2>/dev/null || echo "")
        if [[ -n "$plan_file" && -f "$plan_file" ]]; then
            echo "PLAN_FILE: $plan_file"
            echo "NOTES:"
            extract_final_implementation_notes "$plan_file"
        else
            echo "PLAN_FILE:"
            echo "NOTES:"
        fi

        # Commits for this specific task
        echo "COMMITS:"
        echo "$commits" | grep "(t${task_id})" || true

        echo "=== END ==="
        echo ""
    done <<< "$task_ids"
}

# --- Argument Parsing ---

show_help() {
    cat << 'EOF'
Usage: aitask_changelog.sh [OPTIONS] MODE

Gather changelog data from git commits and archived task plans.

Modes:
  --gather                 Output structured data for all tasks since last tag
  --check-version VERSION  Check if CHANGELOG.md has a section for vVERSION
                           Returns exit code 0 if found, 1 if not

Options:
  --from-tag TAG           Override the base tag (default: auto-detect latest)
  --help, -h               Show help

Output format for --gather:
  BASE_TAG: v0.1.2

  === TASK t89 ===
  ISSUE_TYPE: feature
  TITLE: detect capable terminal on windows
  PLAN_FILE: aiplans/archived/p89_detect_capable_terminal_on_windows.md
  COMMITS:
  1c7aac4 Add terminal capability detection (t89)
  NOTES:
  - **Actual work done:** ...
  === END ===

Examples:
  # Gather all task data since last release
  ./aiscripts/aitask_changelog.sh --gather

  # Check if changelog has entry for v0.2.0
  ./aiscripts/aitask_changelog.sh --check-version 0.2.0

  # Gather from a specific tag
  ./aiscripts/aitask_changelog.sh --gather --from-tag v0.1.1
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --gather)
                MODE="gather"
                shift
                ;;
            --check-version)
                MODE="check-version"
                [[ $# -ge 2 ]] || die "--check-version requires a version argument"
                CHECK_VERSION="$2"
                shift 2
                ;;
            --from-tag)
                [[ $# -ge 2 ]] || die "--from-tag requires a tag argument"
                FROM_TAG="$2"
                shift 2
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

    if [[ -z "$MODE" ]]; then
        die "Mode required: --gather or --check-version VERSION. Use --help for usage."
    fi
}

main() {
    parse_args "$@"
    case "$MODE" in
        gather) gather ;;
        check-version) check_changelog_version "$CHECK_VERSION" ;;
    esac
}

main "$@"
