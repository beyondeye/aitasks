#!/usr/bin/env bash

# aitask_contribution_check.sh - Detect overlapping contribution issues and post analysis comments
# Uses fingerprint metadata from aitask-contribute to find issues touching similar files/areas.
# Supports GitHub (gh CLI), GitLab (glab + curl fallback), and Bitbucket (curl only).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

# --- Global state ---
CHECK_PLATFORM=""
ARG_ISSUE=""
ARG_PLATFORM=""
ARG_REPO=""
ARG_LIMIT=50
ARG_DRY_RUN=false
ARG_SILENT=false
OVERLAP_CHECK_VERSION=1

# --- Help ---

show_help() {
    cat << 'EOF'
Usage: aitask_contribution_check.sh <issue_number> [OPTIONS]

Analyze a contribution issue for overlap with other open contribution issues.
Posts a comment with overlap analysis and suggests labels.

Arguments:
  <issue_number>           Issue number to analyze

Options:
  --platform PLATFORM      Source platform: github, gitlab, bitbucket (auto-detected)
  --repo OWNER/REPO        Repository (for cross-repo operation; GitHub uses -R flag)
  --limit N                Max issues to scan (default: 50)
  --dry-run                Print comment to stdout instead of posting
  --silent                 Suppress informational output
  --help, -h               Show this help

Environment variables:
  GitHub:    $GH_TOKEN or $GITHUB_TOKEN (auto-provided in GitHub Actions)
  GitLab:    $GITLAB_TOKEN (project access token with api scope; CI_JOB_TOKEN is NOT sufficient)
  Bitbucket: $BITBUCKET_USER + $BITBUCKET_TOKEN (API token)

Examples:
  # Analyze issue #42 on auto-detected platform
  ./aitask_contribution_check.sh 42

  # Dry run — print overlap comment without posting
  ./aitask_contribution_check.sh 42 --dry-run

  # Cross-repo check on GitHub
  ./aitask_contribution_check.sh 42 --repo owner/other-repo

  # GitLab with explicit platform
  ./aitask_contribution_check.sh 42 --platform gitlab
EOF
}

# --- Argument Parsing ---

parse_args() {
    if [[ $# -eq 0 ]]; then
        show_help
        exit 0
    fi

    # First positional argument is the issue number
    if [[ "$1" =~ ^[0-9]+$ ]]; then
        ARG_ISSUE="$1"
        shift
    fi

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --platform) ARG_PLATFORM="$2"; shift 2 ;;
            --repo) ARG_REPO="$2"; shift 2 ;;
            --limit) ARG_LIMIT="$2"; shift 2 ;;
            --dry-run) ARG_DRY_RUN=true; shift ;;
            --silent) ARG_SILENT=true; shift ;;
            --help|-h) show_help; exit 0 ;;
            *) die "Unknown option: $1. Use --help for usage." ;;
        esac
    done

    if [[ -z "$ARG_ISSUE" ]]; then
        die "Issue number is required. Use --help for usage."
    fi
}

# ============================================================
# PLATFORM BACKENDS
# ============================================================

# --- GitHub Backend ---

github_check_cli() {
    command -v gh &>/dev/null || die "gh CLI is required for GitHub. Install: https://cli.github.com/"
    command -v jq &>/dev/null || die "jq is required. Install via your package manager."
    if ! gh auth status &>/dev/null; then
        die "gh CLI is not authenticated. Run: gh auth login"
    fi
}

github_fetch_issue() {
    local issue_num="$1"
    local repo_flag=()
    [[ -n "$ARG_REPO" ]] && repo_flag=(-R "$ARG_REPO")
    gh issue view "$issue_num" "${repo_flag[@]}" --json number,title,body,labels,url
}

github_list_contribution_issues() {
    local repo_flag=()
    [[ -n "$ARG_REPO" ]] && repo_flag=(-R "$ARG_REPO")
    gh issue list "${repo_flag[@]}" --state open --label "contribution" --limit "$ARG_LIMIT" --json number,title,body,labels,url
}

github_post_comment() {
    local issue_num="$1"
    local comment_body="$2"
    local repo_flag=()
    [[ -n "$ARG_REPO" ]] && repo_flag=(-R "$ARG_REPO")
    gh issue comment "$issue_num" "${repo_flag[@]}" --body "$comment_body"
}

github_add_label() {
    local issue_num="$1"
    local label="$2"
    local repo_flag=()
    [[ -n "$ARG_REPO" ]] && repo_flag=(-R "$ARG_REPO")
    gh issue edit "$issue_num" "${repo_flag[@]}" --add-label "$label" 2>/dev/null || true
}

github_list_repo_labels() {
    local repo_flag=()
    [[ -n "$ARG_REPO" ]] && repo_flag=(-R "$ARG_REPO")
    gh label list "${repo_flag[@]}" --limit 200 --json name | jq -r '.[].name'
}

# --- GitLab Backend ---

_gitlab_api_base() {
    echo "${CI_API_V4_URL:-https://gitlab.com/api/v4}"
}

_gitlab_project_id() {
    if [[ -n "${CI_PROJECT_ID:-}" ]]; then
        echo "$CI_PROJECT_ID"
    elif [[ -n "$ARG_REPO" ]]; then
        # URL-encode the project path
        echo "${ARG_REPO//\//%2F}"
    else
        # Try to derive from git remote
        local remote_url
        remote_url=$(git remote get-url origin 2>/dev/null || echo "")
        local project_path
        project_path=$(echo "$remote_url" | sed -E 's|.*[:/]([^:]+/[^.]+)(\.git)?$|\1|')
        echo "${project_path//\//%2F}"
    fi
}

_gitlab_token_header() {
    local token="${GITLAB_TOKEN:-}"
    [[ -z "$token" ]] && die "GITLAB_TOKEN is required for GitLab issue API access. CI_JOB_TOKEN does NOT have sufficient permissions. Create a project access token with 'api' scope."
    echo "PRIVATE-TOKEN: $token"
}

_gitlab_has_glab() {
    command -v glab &>/dev/null && glab auth status &>/dev/null 2>&1
}

gitlab_check_cli() {
    command -v jq &>/dev/null || die "jq is required. Install via your package manager."
    if ! _gitlab_has_glab; then
        [[ -n "${GITLAB_TOKEN:-}" ]] || die "Either glab CLI (authenticated) or GITLAB_TOKEN env var is required for GitLab."
    fi
}

gitlab_fetch_issue() {
    local issue_num="$1"
    if _gitlab_has_glab && [[ -z "$ARG_REPO" ]]; then
        glab issue view "$issue_num" -F json | jq '{
            number: .iid,
            title: .title,
            body: (.description // ""),
            labels: [.labels[] | {name: .}],
            url: .web_url
        }'
    else
        local api_base project_id
        api_base=$(_gitlab_api_base)
        project_id=$(_gitlab_project_id)
        curl -sf --header "$(_gitlab_token_header)" \
            "$api_base/projects/$project_id/issues/$issue_num" | jq '{
            number: .iid,
            title: .title,
            body: (.description // ""),
            labels: [.labels[] | {name: .}],
            url: .web_url
        }'
    fi
}

gitlab_list_contribution_issues() {
    local api_base project_id
    api_base=$(_gitlab_api_base)
    project_id=$(_gitlab_project_id)
    if _gitlab_has_glab && [[ -z "$ARG_REPO" ]]; then
        glab issue list --label "contribution" --all --output json | jq '[.[] | {
            number: .iid,
            title: .title,
            body: (.description // ""),
            labels: [.labels[] | {name: .}],
            url: .web_url
        }]' | jq ".[:$ARG_LIMIT]"
    else
        curl -sf --header "$(_gitlab_token_header)" \
            "$api_base/projects/$project_id/issues?state=opened&labels=contribution&per_page=$ARG_LIMIT" | jq '[.[] | {
            number: .iid,
            title: .title,
            body: (.description // ""),
            labels: [.labels[] | {name: .}],
            url: .web_url
        }]'
    fi
}

gitlab_post_comment() {
    local issue_num="$1"
    local comment_body="$2"
    if _gitlab_has_glab && [[ -z "$ARG_REPO" ]]; then
        echo "$comment_body" | glab issue note "$issue_num" -m -
    else
        local api_base project_id
        api_base=$(_gitlab_api_base)
        project_id=$(_gitlab_project_id)
        curl -sf --header "$(_gitlab_token_header)" \
            --header "Content-Type: application/json" \
            --data "$(jq -n --arg body "$comment_body" '{body: $body}')" \
            "$api_base/projects/$project_id/issues/$issue_num/notes" >/dev/null
    fi
}

gitlab_add_label() {
    local issue_num="$1"
    local label="$2"
    if _gitlab_has_glab && [[ -z "$ARG_REPO" ]]; then
        glab issue update "$issue_num" --label "$label" 2>/dev/null || true
    else
        local api_base project_id current_labels new_labels
        api_base=$(_gitlab_api_base)
        project_id=$(_gitlab_project_id)
        current_labels=$(curl -sf --header "$(_gitlab_token_header)" \
            "$api_base/projects/$project_id/issues/$issue_num" | jq -r '.labels | join(",")')
        if [[ -n "$current_labels" ]]; then
            new_labels="${current_labels},${label}"
        else
            new_labels="$label"
        fi
        curl -sf --header "$(_gitlab_token_header)" \
            -X PUT \
            --data-urlencode "labels=$new_labels" \
            "$api_base/projects/$project_id/issues/$issue_num" >/dev/null 2>/dev/null || true
    fi
}

gitlab_list_repo_labels() {
    if _gitlab_has_glab && [[ -z "$ARG_REPO" ]]; then
        glab label list -F json | jq -r '.[].name'
    else
        local api_base project_id
        api_base=$(_gitlab_api_base)
        project_id=$(_gitlab_project_id)
        curl -sf --header "$(_gitlab_token_header)" \
            "$api_base/projects/$project_id/labels?per_page=100" | jq -r '.[].name'
    fi
}

# --- Bitbucket Backend ---

_bitbucket_api_base() {
    echo "https://api.bitbucket.org/2.0"
}

_bitbucket_repo_slug() {
    if [[ -n "$ARG_REPO" ]]; then
        echo "$ARG_REPO"
    elif [[ -n "${BITBUCKET_WORKSPACE:-}" && -n "${BITBUCKET_REPO_SLUG:-}" ]]; then
        echo "${BITBUCKET_WORKSPACE}/${BITBUCKET_REPO_SLUG}"
    else
        # Derive from git remote
        local remote_url
        remote_url=$(git remote get-url origin 2>/dev/null || echo "")
        echo "$remote_url" | sed -E 's|.*bitbucket\.org[:/]([^.]+)(\.git)?$|\1|'
    fi
}

_bitbucket_auth() {
    local user="${BITBUCKET_USER:-}"
    local token="${BITBUCKET_TOKEN:-}"
    [[ -z "$user" || -z "$token" ]] && die "BITBUCKET_USER and BITBUCKET_TOKEN are required for Bitbucket API access."
    echo "${user}:${token}"
}

bitbucket_check_cli() {
    command -v curl &>/dev/null || die "curl is required for Bitbucket API access."
    command -v jq &>/dev/null || die "jq is required. Install via your package manager."
    if [[ -z "${BITBUCKET_USER:-}" || -z "${BITBUCKET_TOKEN:-}" ]]; then
        die "BITBUCKET_USER and BITBUCKET_TOKEN environment variables are required."
    fi
}

bitbucket_fetch_issue() {
    local issue_num="$1"
    local api_base repo_slug
    api_base=$(_bitbucket_api_base)
    repo_slug=$(_bitbucket_repo_slug)
    curl -sf -u "$(_bitbucket_auth)" \
        "$api_base/repositories/$repo_slug/issues/$issue_num" | jq '{
        number: .id,
        title: .title,
        body: (.content.raw // ""),
        labels: [],
        url: .links.html.href
    }'
}

bitbucket_list_contribution_issues() {
    # Bitbucket has no label-based issue filtering, so fetch all open issues
    # and filter by metadata presence in the main loop
    local api_base repo_slug
    api_base=$(_bitbucket_api_base)
    repo_slug=$(_bitbucket_repo_slug)
    curl -sf -u "$(_bitbucket_auth)" \
        "$api_base/repositories/$repo_slug/issues?state=open&state=new&pagelen=$ARG_LIMIT" | jq '[.values[] | {
        number: .id,
        title: .title,
        body: (.content.raw // ""),
        labels: [],
        url: .links.html.href
    }]'
}

bitbucket_post_comment() {
    local issue_num="$1"
    local comment_body="$2"
    local api_base repo_slug
    api_base=$(_bitbucket_api_base)
    repo_slug=$(_bitbucket_repo_slug)
    curl -sf -u "$(_bitbucket_auth)" \
        --header "Content-Type: application/json" \
        --data "$(jq -n --arg body "$comment_body" '{content: {raw: $body}}')" \
        "$api_base/repositories/$repo_slug/issues/$issue_num/comments" >/dev/null
}

bitbucket_add_label() {
    # Bitbucket issues API does not support labels — silent no-op
    true
}

bitbucket_list_repo_labels() {
    # Bitbucket issues API does not support labels — empty result
    echo ""
}

# --- Dispatcher Functions ---

source_check_cli() {
    case "$CHECK_PLATFORM" in
        github) github_check_cli ;;
        gitlab) gitlab_check_cli ;;
        bitbucket) bitbucket_check_cli ;;
        *) die "Unknown platform: $CHECK_PLATFORM" ;;
    esac
}

source_fetch_issue() {
    local issue_num="$1"
    case "$CHECK_PLATFORM" in
        github) github_fetch_issue "$issue_num" ;;
        gitlab) gitlab_fetch_issue "$issue_num" ;;
        bitbucket) bitbucket_fetch_issue "$issue_num" ;;
        *) die "Unknown platform: $CHECK_PLATFORM" ;;
    esac
}

source_list_contribution_issues() {
    case "$CHECK_PLATFORM" in
        github) github_list_contribution_issues ;;
        gitlab) gitlab_list_contribution_issues ;;
        bitbucket) bitbucket_list_contribution_issues ;;
        *) die "Unknown platform: $CHECK_PLATFORM" ;;
    esac
}

source_post_comment() {
    local issue_num="$1"
    local comment_body="$2"
    case "$CHECK_PLATFORM" in
        github) github_post_comment "$issue_num" "$comment_body" ;;
        gitlab) gitlab_post_comment "$issue_num" "$comment_body" ;;
        bitbucket) bitbucket_post_comment "$issue_num" "$comment_body" ;;
        *) die "Unknown platform: $CHECK_PLATFORM" ;;
    esac
}

source_add_label() {
    local issue_num="$1"
    local label="$2"
    case "$CHECK_PLATFORM" in
        github) github_add_label "$issue_num" "$label" ;;
        gitlab) gitlab_add_label "$issue_num" "$label" ;;
        bitbucket) bitbucket_add_label "$issue_num" "$label" ;;
        *) die "Unknown platform: $CHECK_PLATFORM" ;;
    esac
}

source_list_repo_labels() {
    case "$CHECK_PLATFORM" in
        github) github_list_repo_labels ;;
        gitlab) gitlab_list_repo_labels ;;
        bitbucket) bitbucket_list_repo_labels ;;
        *) die "Unknown platform: $CHECK_PLATFORM" ;;
    esac
}

# --- Idempotency: check for existing overlap comment ---

github_has_overlap_comment() {
    local issue_num="$1"
    local repo_flag=()
    [[ -n "$ARG_REPO" ]] && repo_flag=(-R "$ARG_REPO")
    local comments
    comments=$(gh issue view "$issue_num" "${repo_flag[@]}" --json comments --jq '.comments[].body' 2>/dev/null) || return 1
    echo "$comments" | grep -qF "<!-- overlap-results"
}

gitlab_has_overlap_comment() {
    local issue_num="$1"
    local api_base project_id
    api_base=$(_gitlab_api_base)
    project_id=$(_gitlab_project_id)
    local notes
    notes=$(curl -sf --header "$(_gitlab_token_header)" \
        "$api_base/projects/$project_id/issues/$issue_num/notes?per_page=100" \
        | jq -r '.[].body' 2>/dev/null) || return 1
    echo "$notes" | grep -qF "<!-- overlap-results"
}

bitbucket_has_overlap_comment() {
    local issue_num="$1"
    local api_base repo_slug
    api_base=$(_bitbucket_api_base)
    repo_slug=$(_bitbucket_repo_slug)
    local comments
    comments=$(curl -sf -u "$(_bitbucket_auth)" \
        "$api_base/repositories/$repo_slug/issues/$issue_num/comments?pagelen=100" \
        | jq -r '.values[].content.raw' 2>/dev/null) || return 1
    echo "$comments" | grep -qF "<!-- overlap-results"
}

source_has_overlap_comment() {
    local issue_num="$1"
    case "$CHECK_PLATFORM" in
        github) github_has_overlap_comment "$issue_num" ;;
        gitlab) gitlab_has_overlap_comment "$issue_num" ;;
        bitbucket) bitbucket_has_overlap_comment "$issue_num" ;;
        *) return 1 ;;
    esac
}

# ============================================================
# OVERLAP SCORING
# ============================================================

# Compute overlap score between target issue and a candidate issue
# Uses CONTRIBUTE_* globals for the candidate, and TARGET_* globals for the target
# Sets: OVERLAP_SCORE, OVERLAP_DETAIL
compute_overlap_score() {
    local target_file_paths="$1"
    local target_file_dirs="$2"
    local target_areas="$3"
    local target_change_type="$4"
    local cand_file_paths="$5"
    local cand_file_dirs="$6"
    local cand_areas="$7"
    local cand_change_type="$8"

    OVERLAP_SCORE=0
    OVERLAP_DETAIL=""

    local details=()

    # File paths: shared × 3
    if [[ -n "$target_file_paths" && -n "$cand_file_paths" ]]; then
        declare -A target_files_map=()
        local IFS=','
        for f in $target_file_paths; do
            [[ -n "$f" ]] && target_files_map["$f"]=1
        done
        local shared_files=0
        local shared_file_list=()
        for f in $cand_file_paths; do
            if [[ -n "$f" && -n "${target_files_map[$f]:-}" ]]; then
                shared_files=$((shared_files + 1))
                shared_file_list+=("$f")
            fi
        done
        unset IFS
        if [[ "$shared_files" -gt 0 ]]; then
            local file_score=$((shared_files * 3))
            OVERLAP_SCORE=$((OVERLAP_SCORE + file_score))
            details+=("files: ${shared_file_list[*]} (+${file_score})")
        fi
    fi

    # Directories: shared × 2
    if [[ -n "$target_file_dirs" && -n "$cand_file_dirs" ]]; then
        declare -A target_dirs_map=()
        local IFS=','
        for d in $target_file_dirs; do
            [[ -n "$d" ]] && target_dirs_map["$d"]=1
        done
        local shared_dirs=0
        local shared_dir_list=()
        for d in $cand_file_dirs; do
            if [[ -n "$d" && -n "${target_dirs_map[$d]:-}" ]]; then
                shared_dirs=$((shared_dirs + 1))
                shared_dir_list+=("$d")
            fi
        done
        unset IFS
        if [[ "$shared_dirs" -gt 0 ]]; then
            local dir_score=$((shared_dirs * 2))
            OVERLAP_SCORE=$((OVERLAP_SCORE + dir_score))
            details+=("dirs: ${shared_dir_list[*]} (+${dir_score})")
        fi
    fi

    # Areas: shared × 2
    if [[ -n "$target_areas" && -n "$cand_areas" ]]; then
        declare -A target_areas_map=()
        local IFS=','
        for a in $target_areas; do
            [[ -n "$a" ]] && target_areas_map["$a"]=1
        done
        local shared_areas=0
        local shared_area_list=()
        for a in $cand_areas; do
            if [[ -n "$a" && -n "${target_areas_map[$a]:-}" ]]; then
                shared_areas=$((shared_areas + 1))
                shared_area_list+=("$a")
            fi
        done
        unset IFS
        if [[ "$shared_areas" -gt 0 ]]; then
            local area_score=$((shared_areas * 2))
            OVERLAP_SCORE=$((OVERLAP_SCORE + area_score))
            details+=("areas: ${shared_area_list[*]} (+${area_score})")
        fi
    fi

    # Change type match: +1
    if [[ -n "$target_change_type" && -n "$cand_change_type" && "$target_change_type" == "$cand_change_type" ]]; then
        OVERLAP_SCORE=$((OVERLAP_SCORE + 1))
        details+=("change_type: ${target_change_type} (+1)")
    fi

    if [[ ${#details[@]} -gt 0 ]]; then
        OVERLAP_DETAIL=$(printf "%s; " "${details[@]}")
        # Remove trailing "; "
        OVERLAP_DETAIL="${OVERLAP_DETAIL%; }"
    fi
}

# Classify overlap score into severity
# Input: score number
# Output: "high", "likely", or "low"
classify_overlap() {
    local score="$1"
    if [[ "$score" -ge 7 ]]; then
        echo "high"
    elif [[ "$score" -ge 4 ]]; then
        echo "likely"
    else
        echo "low"
    fi
}

# ============================================================
# COMMENT FORMATTING
# ============================================================

# Format overlap results as a markdown comment
# Input: scored_results array (each element: "SCORE:ISSUE_NUM:TITLE:DETAIL:URL")
# Sets: OVERLAP_COMMENT
format_overlap_comment() {
    local -n results_ref=$1
    local target_num="$2"

    OVERLAP_COMMENT=""

    if [[ ${#results_ref[@]} -eq 0 ]]; then
        OVERLAP_COMMENT="## Contribution Overlap Analysis

No overlapping contribution issues found for #${target_num}.

<!-- overlap-results overlap_check_version: ${OVERLAP_CHECK_VERSION} -->"
        return
    fi

    local comment=""
    comment+="## Contribution Overlap Analysis"$'\n'
    comment+=""$'\n'
    comment+="| Issue | Score | Overlap | Detail |"$'\n'
    comment+="|-------|-------|---------|--------|"$'\n'

    local count=0
    local top_overlaps=""
    for entry in "${results_ref[@]}"; do
        [[ $count -ge 5 ]] && break
        local score issue_num title detail url
        IFS=':' read -r score issue_num title detail url <<< "$entry"
        local severity
        severity=$(classify_overlap "$score")
        comment+="| [#${issue_num}](${url}) | ${score} (${severity}) | ${title} | ${detail} |"$'\n'

        if [[ -n "$top_overlaps" ]]; then
            top_overlaps="${top_overlaps},${issue_num}:${score}"
        else
            top_overlaps="${issue_num}:${score}"
        fi
        count=$((count + 1))
    done

    if [[ -n "${LABEL_SUGGESTIONS:-}" ]]; then
        comment+=""$'\n'
        comment+="### Suggested Labels"$'\n'
        comment+=""$'\n'
        comment+="$LABEL_SUGGESTIONS"$'\n'
    fi

    comment+=""$'\n'
    comment+="<!-- overlap-results top_overlaps: ${top_overlaps} overlap_check_version: ${OVERLAP_CHECK_VERSION} -->"

    OVERLAP_COMMENT="$comment"
}

# ============================================================
# LABEL RESOLUTION
# ============================================================

# Match auto_labels from fingerprint against existing repo labels
# Sets: LABEL_SUGGESTIONS
resolve_label_suggestions() {
    local auto_labels="$1"
    LABEL_SUGGESTIONS=""

    [[ -z "$auto_labels" ]] && return

    local repo_labels
    repo_labels=$(source_list_repo_labels 2>/dev/null || echo "")
    [[ -z "$repo_labels" ]] && return

    # Build a map of existing repo labels
    declare -A repo_label_map=()
    while IFS= read -r lbl; do
        [[ -n "$lbl" ]] && repo_label_map["$lbl"]=1
    done <<< "$repo_labels"

    local matching=()
    local IFS=','
    for label in $auto_labels; do
        [[ -n "$label" ]] || continue
        if [[ -n "${repo_label_map[$label]:-}" ]]; then
            matching+=("$label")
        fi
    done
    unset IFS

    if [[ ${#matching[@]} -gt 0 ]]; then
        local IFS=', '
        LABEL_SUGGESTIONS="Matching repo labels: \`${matching[*]}\`"
        unset IFS
    fi
}

# ============================================================
# MAIN
# ============================================================

main() {
    parse_args "$@"

    # Resolve platform
    if [[ -n "$ARG_PLATFORM" ]]; then
        CHECK_PLATFORM="$ARG_PLATFORM"
    else
        CHECK_PLATFORM=$(detect_platform)
        [[ -z "$CHECK_PLATFORM" ]] && die "Could not auto-detect platform from git remote. Use --platform github|gitlab|bitbucket"
    fi

    case "$CHECK_PLATFORM" in
        github|gitlab|bitbucket) ;;
        *) die "Unknown platform: $CHECK_PLATFORM (supported: github, gitlab, bitbucket)" ;;
    esac

    source_check_cli

    # Fetch target issue
    [[ "$ARG_SILENT" != true ]] && info "Fetching issue #${ARG_ISSUE}..."
    local target_json
    target_json=$(source_fetch_issue "$ARG_ISSUE") || die "Failed to fetch issue #${ARG_ISSUE}"

    local target_body
    target_body=$(echo "$target_json" | jq -r '.body // ""')

    # Parse target fingerprint
    parse_contribute_metadata "$target_body"
    local target_fp_version="$CONTRIBUTE_FINGERPRINT_VERSION"
    local target_file_paths="$CONTRIBUTE_FILE_PATHS"
    local target_file_dirs="$CONTRIBUTE_FILE_DIRS"
    local target_areas="$CONTRIBUTE_AREAS"
    local target_change_type="$CONTRIBUTE_CHANGE_TYPE"
    local target_auto_labels="$CONTRIBUTE_AUTO_LABELS"

    if [[ -z "$target_fp_version" ]]; then
        [[ "$ARG_SILENT" != true ]] && warn "Issue #${ARG_ISSUE} has no fingerprint metadata. Cannot compute overlaps."
        # Still post a comment indicating no fingerprint
        LABEL_SUGGESTIONS=""
        local _no_overlap_results=()
        format_overlap_comment _no_overlap_results "$ARG_ISSUE"
        if [[ "$ARG_DRY_RUN" == true ]]; then
            echo "$OVERLAP_COMMENT"
        else
            if source_has_overlap_comment "$ARG_ISSUE" 2>/dev/null; then
                [[ "$ARG_SILENT" != true ]] && info "Overlap comment already exists on issue #${ARG_ISSUE}. Skipping."
            else
                source_post_comment "$ARG_ISSUE" "$OVERLAP_COMMENT"
                [[ "$ARG_SILENT" != true ]] && info "Posted overlap analysis comment to issue #${ARG_ISSUE}."
            fi
        fi
        return
    fi

    # List contribution issues
    [[ "$ARG_SILENT" != true ]] && info "Scanning contribution issues (limit: ${ARG_LIMIT})..."
    local issues_json
    issues_json=$(source_list_contribution_issues) || die "Failed to list contribution issues"

    local issue_count
    issue_count=$(echo "$issues_json" | jq 'length')

    # Score each issue
    local scored_results=()
    local i
    for ((i = 0; i < issue_count; i++)); do
        local cand_num cand_body cand_title cand_url
        cand_num=$(echo "$issues_json" | jq -r ".[$i].number")
        cand_body=$(echo "$issues_json" | jq -r ".[$i].body // \"\"")
        cand_title=$(echo "$issues_json" | jq -r ".[$i].title")
        cand_url=$(echo "$issues_json" | jq -r ".[$i].url")

        # Skip self
        [[ "$cand_num" == "$ARG_ISSUE" ]] && continue

        # Parse candidate fingerprint
        parse_contribute_metadata "$cand_body"

        # Skip issues without fingerprint
        [[ -z "$CONTRIBUTE_FINGERPRINT_VERSION" ]] && continue

        compute_overlap_score \
            "$target_file_paths" "$target_file_dirs" "$target_areas" "$target_change_type" \
            "$CONTRIBUTE_FILE_PATHS" "$CONTRIBUTE_FILE_DIRS" "$CONTRIBUTE_AREAS" "$CONTRIBUTE_CHANGE_TYPE"

        # Skip zero-score
        [[ "$OVERLAP_SCORE" -eq 0 ]] && continue

        # Sanitize title and detail for storage (replace colons to avoid field separator conflicts)
        local safe_title safe_detail
        safe_title=$(echo "$cand_title" | tr ':' '-')
        safe_detail=$(echo "$OVERLAP_DETAIL" | tr ':' '-')

        scored_results+=("${OVERLAP_SCORE}:${cand_num}:${safe_title}:${safe_detail}:${cand_url}")
    done

    # Sort scored results descending by score
    local sorted_results=()
    if [[ ${#scored_results[@]} -gt 0 ]]; then
        while IFS= read -r line; do
            sorted_results+=("$line")
        done < <(printf '%s\n' "${scored_results[@]}" | sort -t: -k1 -rn)
    fi

    # Resolve label suggestions
    resolve_label_suggestions "$target_auto_labels"

    # Format comment
    format_overlap_comment sorted_results "$ARG_ISSUE"

    if [[ "$ARG_DRY_RUN" == true ]]; then
        echo "$OVERLAP_COMMENT"
    else
        if source_has_overlap_comment "$ARG_ISSUE" 2>/dev/null; then
            [[ "$ARG_SILENT" != true ]] && info "Overlap comment already exists on issue #${ARG_ISSUE}. Skipping."
        else
            source_post_comment "$ARG_ISSUE" "$OVERLAP_COMMENT"
            [[ "$ARG_SILENT" != true ]] && info "Posted overlap analysis comment to issue #${ARG_ISSUE}."
        fi

        # Apply matching labels
        if [[ -n "$target_auto_labels" ]]; then
            local repo_labels
            repo_labels=$(source_list_repo_labels 2>/dev/null || echo "")
            if [[ -n "$repo_labels" ]]; then
                declare -A repo_label_map=()
                while IFS= read -r lbl; do
                    [[ -n "$lbl" ]] && repo_label_map["$lbl"]=1
                done <<< "$repo_labels"

                local IFS=','
                for label in $target_auto_labels; do
                    [[ -n "$label" ]] || continue
                    if [[ -n "${repo_label_map[$label]:-}" ]]; then
                        source_add_label "$ARG_ISSUE" "$label"
                        [[ "$ARG_SILENT" != true ]] && info "Applied label: $label"
                    fi
                done
                unset IFS
            fi
        fi
    fi

    [[ "$ARG_SILENT" != true ]] && success "Overlap analysis complete for issue #${ARG_ISSUE}."
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
