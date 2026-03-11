#!/usr/bin/env bash

# aitask_contribution_review.sh - Fetch and analyze contribution issues for review
# Sources aitask_contribution_check.sh for platform backends (BASH_SOURCE guarded).
# Provides subcommands: fetch, find-related, fetch-multi
# Used by the aitask-contribution-review Claude Code skill.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

# Source contribution_check for platform backends (BASH_SOURCE guard prevents main() execution)
# shellcheck source=aitask_contribution_check.sh
source "$SCRIPT_DIR/aitask_contribution_check.sh"

# --- Global state ---
REVIEW_SUBCMD=""
REVIEW_ISSUE=""
REVIEW_ISSUES_CSV=""
REVIEW_PLATFORM=""
REVIEW_REPO=""
REVIEW_LIMIT=50

# ============================================================
# HELP
# ============================================================

show_help() {
    cat << 'EOF'
Usage: aitask_contribution_review.sh <subcommand> [OPTIONS]

Fetch and analyze contribution issues for the aitask-contribution-review skill.
Sources aitask_contribution_check.sh for platform backends.

Subcommands:
  fetch <issue_num>          Fetch issue with metadata and comments
  find-related <issue_num>   Find related contribution issues
  fetch-multi <N1,N2,...>    Fetch multiple issues for analysis

Options:
  --platform PLATFORM        Source platform: github, gitlab, bitbucket (auto-detected)
  --repo OWNER/REPO          Repository (for cross-repo operation)
  --limit N                  Max issues to scan for find-related (default: 50)
  --help, -h                 Show this help

Output format (fetch):
  ISSUE_JSON:<json>          Full issue JSON
  HAS_METADATA:true|false    Whether aitask-contribute-metadata is present
  CONTRIBUTOR:<name>         Contributor username
  EMAIL:<email>              Contributor email
  AREAS:<csv>                Affected code areas
  FILE_PATHS:<csv>           Changed file paths
  FILE_DIRS:<csv>            Changed directories
  CHANGE_TYPE:<type>         Type of change

Output format (find-related):
  OVERLAP:<num>:<score>      Issue found via fingerprint overlap (score >= 4)
  LINKED:<num>:<title>       Issue found via #N references
  BOTH:<num>:<score>:<title> Issue found in both sources
  NO_BOT_COMMENT             No overlap analysis comment found
  TOTAL_CANDIDATES:<count>   Total unique candidate issues

Output format (fetch-multi):
  @@@ISSUE:<num>@@@          Issue separator
  TITLE:<title>              Issue title
  CONTRIBUTOR:<name>         Contributor username
  >>>BODY_START              Body content start
  <body content>
  <<<BODY_END                Body content end

Examples:
  # Fetch issue #42 with metadata
  ./aitask_contribution_review.sh fetch 42

  # Find related issues for #42
  ./aitask_contribution_review.sh find-related 42

  # Fetch multiple issues for analysis
  ./aitask_contribution_review.sh fetch-multi 42,38,15
EOF
}

# ============================================================
# ARGUMENT PARSING
# ============================================================

parse_args() {
    if [[ $# -eq 0 ]]; then
        show_help
        exit 0
    fi

    # First argument is the subcommand
    case "$1" in
        fetch|find-related|fetch-multi)
            REVIEW_SUBCMD="$1"
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            die "Unknown subcommand: $1. Use --help for usage."
            ;;
    esac

    # Second positional is the issue number(s)
    if [[ $# -gt 0 && ! "$1" =~ ^-- ]]; then
        if [[ "$REVIEW_SUBCMD" == "fetch-multi" ]]; then
            REVIEW_ISSUES_CSV="$1"
        else
            REVIEW_ISSUE="$1"
        fi
        shift
    fi

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --platform) REVIEW_PLATFORM="$2"; shift 2 ;;
            --repo) REVIEW_REPO="$2"; shift 2 ;;
            --limit) REVIEW_LIMIT="$2"; shift 2 ;;
            --help|-h) show_help; exit 0 ;;
            *) die "Unknown option: $1. Use --help for usage." ;;
        esac
    done

    # Validate required arguments per subcommand
    case "$REVIEW_SUBCMD" in
        fetch|find-related)
            if [[ -z "$REVIEW_ISSUE" ]]; then
                die "$REVIEW_SUBCMD requires an issue number. Use --help for usage."
            fi
            ;;
        fetch-multi)
            if [[ -z "$REVIEW_ISSUES_CSV" ]]; then
                die "fetch-multi requires comma-separated issue numbers. Use --help for usage."
            fi
            ;;
    esac
}

# ============================================================
# PLATFORM SETUP
# ============================================================

# Set up contribution_check globals from review globals
setup_platform() {
    if [[ -n "$REVIEW_PLATFORM" ]]; then
        CHECK_PLATFORM="$REVIEW_PLATFORM"
    else
        CHECK_PLATFORM=$(detect_platform)
        if [[ -z "$CHECK_PLATFORM" ]]; then
            die "Could not auto-detect platform from git remote. Use --platform github|gitlab|bitbucket"
        fi
    fi

    case "$CHECK_PLATFORM" in
        github|gitlab|bitbucket) ;;
        *) die "Unknown platform: $CHECK_PLATFORM (supported: github, gitlab, bitbucket)" ;;
    esac

    # Set contribution_check globals used by its backends (SC2034: used by sourced scripts)
    # shellcheck disable=SC2034
    ARG_REPO="$REVIEW_REPO"
    # shellcheck disable=SC2034
    ARG_LIMIT="$REVIEW_LIMIT"

    source_check_cli
}

# ============================================================
# COMMENT FETCHING (extends contribution_check backends)
# ============================================================

# Fetch issue comments as JSON array
# Returns: JSON array of {author, body, createdAt} objects
review_fetch_comments() {
    local issue_num="$1"
    case "$CHECK_PLATFORM" in
        github) review_github_fetch_comments "$issue_num" ;;
        gitlab) review_gitlab_fetch_comments "$issue_num" ;;
        bitbucket) review_bitbucket_fetch_comments "$issue_num" ;;
        *) die "Unknown platform: $CHECK_PLATFORM" ;;
    esac
}

review_github_fetch_comments() {
    local issue_num="$1"
    local repo_flag=()
    [[ -n "$ARG_REPO" ]] && repo_flag=(-R "$ARG_REPO")
    gh issue view "$issue_num" "${repo_flag[@]}" --json comments | jq '.comments'
}

review_gitlab_fetch_comments() {
    local issue_num="$1"
    if _gitlab_has_glab && [[ -z "$ARG_REPO" ]]; then
        # glab does not have a direct comments-only JSON output; fetch full issue
        glab issue view "$issue_num" -F json | jq '[.notes[] | {
            author: .author.username,
            body: .body,
            createdAt: .created_at
        }]'
    else
        local api_base project_id
        api_base=$(_gitlab_api_base)
        project_id=$(_gitlab_project_id)
        curl -sf --header "$(_gitlab_token_header)" \
            "$api_base/projects/$project_id/issues/$issue_num/notes?per_page=100" | jq '[.[] | {
            author: .author.username,
            body: .body,
            createdAt: .created_at
        }]'
    fi
}

review_bitbucket_fetch_comments() {
    local issue_num="$1"
    local api_base repo_slug
    api_base=$(_bitbucket_api_base)
    repo_slug=$(_bitbucket_repo_slug)
    curl -sf -u "$(_bitbucket_auth)" \
        "$api_base/repositories/$repo_slug/issues/$issue_num/comments?pagelen=100" | jq '[.values[] | {
        author: (.user.display_name // .user.nickname // "unknown"),
        body: (.content.raw // ""),
        createdAt: .created_on
    }]'
}

# ============================================================
# SUBCOMMAND: fetch
# ============================================================

cmd_fetch() {
    local issue_num="$1"

    # Fetch issue JSON via contribution_check backend
    local issue_json
    issue_json=$(source_fetch_issue "$issue_num") || die "Failed to fetch issue #${issue_num}"

    # Fetch comments separately
    local comments_json
    comments_json=$(review_fetch_comments "$issue_num" 2>/dev/null || echo "[]")

    # Merge comments into issue JSON
    local full_json
    full_json=$(echo "$issue_json" | jq --argjson comments "$comments_json" '. + {comments: $comments}')

    # Extract body for metadata parsing
    local body
    body=$(echo "$issue_json" | jq -r '.body // ""')

    # Parse contribute metadata
    parse_contribute_metadata "$body"

    local has_metadata="false"
    if [[ -n "${CONTRIBUTE_FINGERPRINT_VERSION:-}" ]]; then
        has_metadata="true"
    fi

    # Output structured lines
    echo "ISSUE_JSON:$full_json"
    echo "HAS_METADATA:$has_metadata"
    echo "CONTRIBUTOR:${CONTRIBUTE_CONTRIBUTOR:-}"
    echo "EMAIL:${CONTRIBUTE_EMAIL:-}"
    echo "AREAS:${CONTRIBUTE_AREAS:-}"
    echo "FILE_PATHS:${CONTRIBUTE_FILE_PATHS:-}"
    echo "FILE_DIRS:${CONTRIBUTE_FILE_DIRS:-}"
    echo "CHANGE_TYPE:${CONTRIBUTE_CHANGE_TYPE:-}"
}

# ============================================================
# SUBCOMMAND: find-related
# ============================================================

# Parse overlap results from bot comment
# Input: comments JSON array
# Output: OVERLAP:<num>:<score> lines
parse_overlap_from_comments() {
    local comments_json="$1"
    local target_num="$2"

    # Search for the overlap-results marker in comments
    local overlap_comment
    overlap_comment=$(echo "$comments_json" | jq -r '.[].body' | grep -o '<!-- overlap-results[^>]*-->' | head -1 || echo "")

    if [[ -z "$overlap_comment" ]]; then
        echo "NO_BOT_COMMENT"
        return
    fi

    # Extract top_overlaps field
    local top_overlaps
    top_overlaps=$(echo "$overlap_comment" | grep -o 'top_overlaps: [^ ]*' | sed 's/top_overlaps: //' || echo "")

    if [[ -z "$top_overlaps" ]]; then
        return
    fi

    # Parse N:S pairs, filter score >= 4
    local IFS=','
    for pair in $top_overlaps; do
        local num score
        num="${pair%%:*}"
        score="${pair##*:}"
        # Skip self
        if [[ "$num" == "$target_num" ]]; then
            continue
        fi
        # Filter by score threshold
        if [[ "$score" -ge 4 ]] 2>/dev/null; then
            echo "OVERLAP:${num}:${score}"
        fi
    done
    unset IFS
}

# Parse linked issue references from text
# Input: text content, target issue number
# Output: unique issue numbers (one per line)
parse_linked_issues() {
    local text="$1"
    local target_num="$2"

    # Extract #N patterns, deduplicate, exclude self
    echo "$text" | grep -oE '#[0-9]+' | sed 's/^#//' | sort -un | while read -r num; do
        if [[ "$num" != "$target_num" && "$num" -gt 0 ]] 2>/dev/null; then
            echo "$num"
        fi
    done
}

cmd_find_related() {
    local issue_num="$1"

    # Fetch target issue with comments
    local issue_json
    issue_json=$(source_fetch_issue "$issue_num") || die "Failed to fetch issue #${issue_num}"

    local comments_json
    comments_json=$(review_fetch_comments "$issue_num" 2>/dev/null || echo "[]")

    local body
    body=$(echo "$issue_json" | jq -r '.body // ""')

    # Verify it's a contribution issue
    parse_contribute_metadata "$body"
    if [[ -z "${CONTRIBUTE_FINGERPRINT_VERSION:-}" ]]; then
        die "Issue #${issue_num} is not a contribution issue (no aitask-contribute-metadata found)"
    fi

    # --- Source A: Bot comment overlap results ---
    local -a overlap_issues=()
    declare -A overlap_scores=()
    local bot_comment_found=true

    local overlap_output
    overlap_output=$(parse_overlap_from_comments "$comments_json" "$issue_num")

    if echo "$overlap_output" | grep -q "^NO_BOT_COMMENT$"; then
        bot_comment_found=false
    else
        while IFS= read -r line; do
            if [[ "$line" =~ ^OVERLAP:([0-9]+):([0-9]+)$ ]]; then
                local onum="${BASH_REMATCH[1]}"
                local oscore="${BASH_REMATCH[2]}"
                overlap_issues+=("$onum")
                overlap_scores["$onum"]="$oscore"
            fi
        done <<< "$overlap_output"
    fi

    # --- Source B: Linked issues from body and comments ---
    local all_text="$body"
    local comments_text
    comments_text=$(echo "$comments_json" | jq -r '.[].body // ""' 2>/dev/null || echo "")
    all_text+=$'\n'"$comments_text"

    local -a linked_issues=()
    declare -A linked_titles=()

    local candidate_nums
    candidate_nums=$(parse_linked_issues "$all_text" "$issue_num")

    while IFS= read -r cnum; do
        [[ -z "$cnum" ]] && continue
        # Fetch candidate and check if it's a contribution issue
        local cand_json
        cand_json=$(source_fetch_issue "$cnum" 2>/dev/null || echo "")
        if [[ -z "$cand_json" ]]; then
            continue
        fi
        local cand_body cand_title
        cand_body=$(echo "$cand_json" | jq -r '.body // ""')
        cand_title=$(echo "$cand_json" | jq -r '.title // ""')

        # Check for metadata
        parse_contribute_metadata "$cand_body"
        if [[ -n "${CONTRIBUTE_FINGERPRINT_VERSION:-}" ]]; then
            linked_issues+=("$cnum")
            linked_titles["$cnum"]="$cand_title"
        fi
    done <<< "$candidate_nums"

    # --- Deduplicate and output ---
    declare -A seen=()
    local total=0

    # Output overlaps (may also be linked)
    for onum in "${overlap_issues[@]}"; do
        seen["$onum"]=1
        if [[ -n "${linked_titles[$onum]:-}" ]]; then
            echo "BOTH:${onum}:${overlap_scores[$onum]}:${linked_titles[$onum]}"
        else
            echo "OVERLAP:${onum}:${overlap_scores[$onum]}"
        fi
        total=$((total + 1))
    done

    # Output linked-only (not already in overlaps)
    for lnum in "${linked_issues[@]}"; do
        if [[ -z "${seen[$lnum]:-}" ]]; then
            seen["$lnum"]=1
            echo "LINKED:${lnum}:${linked_titles[$lnum]}"
            total=$((total + 1))
        fi
    done

    if [[ "$bot_comment_found" == false ]]; then
        echo "NO_BOT_COMMENT"
    fi

    echo "TOTAL_CANDIDATES:${total}"
}

# ============================================================
# SUBCOMMAND: fetch-multi
# ============================================================

cmd_fetch_multi() {
    local issues_csv="$1"
    local -a issue_nums
    IFS=',' read -ra issue_nums <<< "$issues_csv"

    for num in "${issue_nums[@]}"; do
        local issue_json
        issue_json=$(source_fetch_issue "$num") || {
            warn "Failed to fetch issue #${num}, skipping"
            continue
        }

        local title body contributor
        title=$(echo "$issue_json" | jq -r '.title // ""')
        body=$(echo "$issue_json" | jq -r '.body // ""')

        parse_contribute_metadata "$body"
        contributor="${CONTRIBUTE_CONTRIBUTOR:-unknown}"

        echo "@@@ISSUE:${num}@@@"
        echo "TITLE:${title}"
        echo "CONTRIBUTOR:${contributor}"
        echo ">>>BODY_START"
        echo "$body"
        echo "<<<BODY_END"
    done
}

# ============================================================
# MAIN
# ============================================================

main() {
    parse_args "$@"
    setup_platform

    case "$REVIEW_SUBCMD" in
        fetch) cmd_fetch "$REVIEW_ISSUE" ;;
        find-related) cmd_find_related "$REVIEW_ISSUE" ;;
        fetch-multi) cmd_fetch_multi "$REVIEW_ISSUES_CSV" ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
