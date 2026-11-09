#!/usr/bin/env bash

# aitask_contribution_check.sh - Detect overlapping contribution issues and post analysis comments
# Uses fingerprint metadata from aitask-contribute to find issues touching similar files/areas.
# Supports GitHub (gh CLI) and GitLab (glab + curl fallback). Bitbucket Cloud removed its
# native issue tracker and its API on 2026-08-20, so a Bitbucket run fails with that message.

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

# auto_labels come from the issue body, which the issue AUTHOR controls — and
# the CI workflow runs on issues opened by anyone. They are applied
# automatically only inside the classification namespaces /aitask-contribute
# generates (`area:<name>`, `scope:<type>`), and only when the maintainer has
# already created that label in the repository. Every other suggested label
# stays a non-authoritative suggestion in the analysis comment.
CONTRIBUTION_AUTO_APPLY_PREFIXES=("area:" "scope:")

# --- Help ---

show_help() {
    cat << 'EOF'
Usage: aitask_contribution_check.sh <issue_number> [OPTIONS]

Analyze a contribution issue for overlap with other open contribution issues.
Posts a comment with overlap analysis and suggests labels.

Arguments:
  <issue_number>           Issue number to analyze

Options:
  --platform PLATFORM      Source platform: github, gitlab (auto-detected); bitbucket is
                           not supported (its issue tracker was removed)
  --repo OWNER/REPO        Repository (for cross-repo operation; GitHub uses -R flag)
  --limit N                Max contribution issues to return (default: 50);
                           all open issues are scanned and the limit
                           applies after filtering
  --dry-run                Print comment to stdout instead of posting
  --silent                 Suppress informational output
  --help, -h               Show this help

Environment variables:
  GitHub:    $GH_TOKEN or $GITHUB_TOKEN (auto-provided in GitHub Actions)
  GitLab:    $GITLAB_TOKEN (project access token with api scope; CI_JOB_TOKEN is NOT sufficient)

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
    # GitHub silently drops labels supplied by issue authors without push
    # access, so a contribution issue is one that carries the 'contribution'
    # label OR the aitask-contribute-metadata marker. Scan every open issue
    # (paginated) and apply the limit only AFTER filtering, so newer ordinary
    # issues cannot crowd an older contribution out of the result.
    local repo_flag=()
    [[ -n "$ARG_REPO" ]] && repo_flag=(-R "$ARG_REPO")
    # Resolve host and OWNER/REPO the way the `gh issue` commands do (qualified
    # -R HOST/OWNER/REPO, GH_HOST, the local git remote). A bare `gh api` would
    # default to github.com and miss a GitHub Enterprise repository.
    local repo_url host nwo
    repo_url=$(gh repo view "${repo_flag[@]}" --json url --jq .url) || return 1
    host="${repo_url#*://}"
    host="${host%%/*}"
    nwo="${repo_url#*://"$host"/}"
    if ! [[ "$host" =~ ^[A-Za-z0-9.-]+(:[0-9]+)?$ && "$nwo" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]]; then
        warn "Unexpected repository URL from gh repo view: $repo_url"
        return 1
    fi
    local pages
    pages=$(gh api --hostname "$host" --paginate "repos/$nwo/issues?state=open&per_page=100") || return 1
    # --paginate prints one JSON array per page; -s + add concatenates them.
    # Pages go through stdin, never --argjson: Linux caps one argument at 128 KB.
    printf '%s\n' "$pages" | jq -s --argjson limit "$ARG_LIMIT" '
        [ (add // [])[]
          | select(.pull_request == null)
          | select(any(.labels[]?; .name == "contribution")
                   or ((.body // "") | contains("<!-- aitask-contribute-metadata")))
          | {number, title, body: (.body // ""),
             labels: [.labels[]? | {name}], url: .html_url} ]
        | unique_by(.number) | sort_by(-.number) | .[:$limit]'
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
        local api_base project_id hdr
        api_base=$(_gitlab_api_base)
        project_id=$(_gitlab_project_id)
        hdr=$(_gitlab_token_header) || return 1
        curl -sf --header "$hdr" \
            "$api_base/projects/$project_id/issues/$issue_num" | jq '{
            number: .iid,
            title: .title,
            body: (.description // ""),
            labels: [.labels[] | {name: .}],
            url: .web_url
        }'
    fi
}

# _gitlab_select_contribution_issues — stdin: one or more JSON arrays of raw
# GitLab REST issues (one merged array or one array per page). stdout: the
# contribution issues in the shape github_list_contribution_issues returns,
# newest first, limited to $ARG_LIMIT AFTER filtering. The issues endpoint
# never returns merge requests, so there is no pull-request filter.
_gitlab_select_contribution_issues() {
    jq -s --argjson limit "$ARG_LIMIT" '
        [ (add // [])[]
          | select(any(.labels[]?; . == "contribution")
                   or ((.description // "") | contains("<!-- aitask-contribute-metadata")))
          | {number: .iid, title, body: (.description // ""),
             labels: [.labels[]? | {name: .}], url: .web_url} ]
        | unique_by(.number) | sort_by(-.number) | .[:$limit]'
}

# _gitlab_rest_all_pages <projects/...[?query]> — prints every page of a
# GitLab REST list endpoint (issues, notes, labels), one JSON array per line.
# A page is printed only after it passed the array and repeat checks, so on
# failure — a page fails, is not a JSON array, repeats the previous page, or
# the page cap is reached — it returns non-zero having printed only whole
# pages read before the failure. Callers check the status: a list consumer
# discards that output; a lookup may use it as positive evidence only, never
# as a complete list (t2252).
_gitlab_rest_all_pages() {
    local path="$1" api_base hdr page=1 body count first prev_first="" sep="&"
    local per_page=100 max_pages=1000
    [[ "$path" == *\?* ]] || sep="?"
    api_base=$(_gitlab_api_base)
    hdr=$(_gitlab_token_header) || return 1
    while (( page <= max_pages )); do
        body=$(curl -sf --header "$hdr" \
            "$api_base/$path${sep}per_page=$per_page&page=$page") || return 1
        count=$(printf '%s' "$body" | jq -e 'if type == "array" then length else error("not an array") end' 2>/dev/null) || {
            warn "Unexpected GitLab API response for page $page of $path"
            return 1
        }
        # A page that starts where the previous one did means the server is
        # ignoring 'page': fail now rather than at the page cap. The record's
        # identity is its iid for issues and its id for notes and labels.
        first=$(printf '%s' "$body" | jq -r '.[0] | (.iid // .id) // empty') || return 1
        if [[ -n "$first" && "$first" == "$prev_first" ]]; then
            warn "GitLab listing page $page repeats page $((page - 1)) of $path"
            return 1
        fi
        prev_first="$first"
        printf '%s\n' "$body"
        (( count < per_page )) && return 0
        page=$((page + 1))
    done
    warn "GitLab listing of $path exceeded $max_pages pages; refusing a partial result"
    return 1
}

# _gitlab_issue_notes <issue_iid> — prints every note of an issue as ONE JSON
# array, in GitLab's order (newest first), merged from all pages. Returns 0
# only when every page was read. Otherwise it returns 1 and the array holds
# just the notes of pages read whole before the failure: a caller may treat a
# note found there as present, but never treat a note missing there as absent.
# glab 1.126 prints one array per page under --paginate (seen live in t2248)
# although its --help documents one merged array; this reads either shape.
_gitlab_issue_notes() {
    local issue_num="$1" pages recs all_pages complete=0 project_id
    if _gitlab_has_glab && [[ -z "$ARG_REPO" ]]; then
        pages=$(glab api --paginate "projects/:id/issues/$issue_num/notes?per_page=100") || complete=1
    else
        project_id=$(_gitlab_project_id)
        pages=$(_gitlab_rest_all_pages "projects/$project_id/issues/$issue_num/notes") || complete=1
    fi
    # Tag every value of the response: {page:[…]} for a JSON array, {bad:true}
    # for anything else (an error object, a bare string). jq's exit status
    # cannot be the judge: it carries on past a value that is not an array and
    # still exits 0 when a later page parses; it exits 0 on no input at all; a
    # value cut off mid-JSON stops it with a non-zero status after the values
    # before it. Pages go through stdin, never --argjson (128 KB arg cap).
    recs=$(printf '%s\n' "$pages" \
        | jq -c 'if type == "array" then {page: .} else {bad: true} end' 2>/dev/null) || complete=1
    # Complete only when at least one page came back and every value was a page.
    all_pages=$(printf '%s\n' "$recs" | jq -s 'length > 0 and all(.[]; has("page"))') || return 1
    [[ "$all_pages" == true ]] || complete=1
    # The notes of every page that did parse: positive evidence even when the
    # read is incomplete.
    printf '%s\n' "$recs" | jq -s '[.[] | (.page // empty) | .[]]' || return 1
    return "$complete"
}

gitlab_list_contribution_issues() {
    # GitLab drops labels supplied by authors who are not project members,
    # silently: the issue is created without them and no error is returned
    # (Issuable::Callbacks::Labels skips labels unless the author may
    # set_issue_metadata, which a new issue grants only from the Guest role
    # up). So a contribution issue is one that carries the 'contribution'
    # label OR the aitask-contribute-metadata marker. Scan every open issue
    # (paginated) and apply the limit only AFTER filtering, so newer ordinary
    # issues cannot crowd an older contribution out of the result.
    local pages project_id
    if _gitlab_has_glab && [[ -z "$ARG_REPO" ]]; then
        pages=$(glab api --paginate "projects/:id/issues?state=opened&per_page=100") || return 1
    else
        project_id=$(_gitlab_project_id)
        pages=$(_gitlab_rest_all_pages "projects/$project_id/issues?state=opened") || return 1
    fi
    # Pages go through stdin, never --argjson: Linux caps one argument at 128 KB.
    printf '%s\n' "$pages" | _gitlab_select_contribution_issues
}

gitlab_post_comment() {
    local issue_num="$1"
    local comment_body="$2"
    if _gitlab_has_glab && [[ -z "$ARG_REPO" ]]; then
        echo "$comment_body" | glab issue note "$issue_num" -m -
    else
        local api_base project_id hdr
        api_base=$(_gitlab_api_base)
        project_id=$(_gitlab_project_id)
        hdr=$(_gitlab_token_header) || return 1
        curl -sf --header "$hdr" \
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
        local api_base project_id current_labels new_labels hdr
        api_base=$(_gitlab_api_base)
        project_id=$(_gitlab_project_id)
        hdr=$(_gitlab_token_header) || return 1
        current_labels=$(curl -sf --header "$hdr" \
            "$api_base/projects/$project_id/issues/$issue_num" | jq -r '.labels | join(",")')
        if [[ -n "$current_labels" ]]; then
            new_labels="${current_labels},${label}"
        else
            new_labels="$label"
        fi
        curl -sf --header "$hdr" \
            -X PUT \
            --data-urlencode "labels=$new_labels" \
            "$api_base/projects/$project_id/issues/$issue_num" >/dev/null 2>/dev/null || true
    fi
}

gitlab_list_repo_labels() {
    # Every page: `glab label list` prints one page (30 labels by default), and
    # a label past it would never be auto-applied. All or nothing — the caller
    # maps a failure to "no labels".
    local pages project_id
    if _gitlab_has_glab && [[ -z "$ARG_REPO" ]]; then
        pages=$(glab api --paginate "projects/:id/labels?per_page=100") || return 1
    else
        project_id=$(_gitlab_project_id)
        pages=$(_gitlab_rest_all_pages "projects/$project_id/labels") || return 1
    fi
    printf '%s\n' "$pages" | jq -rs 'add // [] | .[].name'
}

# --- Bitbucket ---

# Bitbucket Cloud removed its native issue tracker, UI and API alike, on
# 2026-08-20 (Atlassian changelog: "Removal of native Bitbucket Cloud Issue
# tracker"); Bitbucket Server/Data Center never had one. Every dispatcher's
# bitbucket arm ends here, so a Bitbucket run says why instead of calling a
# removed endpoint.
_bitbucket_issues_removed() {
    die "Bitbucket Cloud removed its native issue tracker and its API on 2026-08-20, so contribution checks cannot run on Bitbucket. Remove the 'contribution-check' custom pipeline from bitbucket-pipelines.yml."
}

# --- Dispatcher Functions ---

source_check_cli() {
    case "$CHECK_PLATFORM" in
        github) github_check_cli ;;
        gitlab) gitlab_check_cli ;;
        bitbucket) _bitbucket_issues_removed ;;
        *) die "Unknown platform: $CHECK_PLATFORM" ;;
    esac
}

source_fetch_issue() {
    local issue_num="$1"
    case "$CHECK_PLATFORM" in
        github) github_fetch_issue "$issue_num" ;;
        gitlab) gitlab_fetch_issue "$issue_num" ;;
        bitbucket) _bitbucket_issues_removed ;;
        *) die "Unknown platform: $CHECK_PLATFORM" ;;
    esac
}

source_list_contribution_issues() {
    case "$CHECK_PLATFORM" in
        github) github_list_contribution_issues ;;
        gitlab) gitlab_list_contribution_issues ;;
        bitbucket) _bitbucket_issues_removed ;;
        *) die "Unknown platform: $CHECK_PLATFORM" ;;
    esac
}

source_post_comment() {
    local issue_num="$1"
    local comment_body="$2"
    case "$CHECK_PLATFORM" in
        github) github_post_comment "$issue_num" "$comment_body" ;;
        gitlab) gitlab_post_comment "$issue_num" "$comment_body" ;;
        bitbucket) _bitbucket_issues_removed ;;
        *) die "Unknown platform: $CHECK_PLATFORM" ;;
    esac
}

source_add_label() {
    local issue_num="$1"
    local label="$2"
    case "$CHECK_PLATFORM" in
        github) github_add_label "$issue_num" "$label" ;;
        gitlab) gitlab_add_label "$issue_num" "$label" ;;
        bitbucket) _bitbucket_issues_removed ;;
        *) die "Unknown platform: $CHECK_PLATFORM" ;;
    esac
}

source_list_repo_labels() {
    case "$CHECK_PLATFORM" in
        github) github_list_repo_labels ;;
        gitlab) gitlab_list_repo_labels ;;
        bitbucket) _bitbucket_issues_removed ;;
        *) die "Unknown platform: $CHECK_PLATFORM" ;;
    esac
}

# --- Idempotency: check for existing overlap comment ---
#
# Every *_has_overlap_comment returns one of three verdicts:
#   0  a comment that was read carries the overlap marker
#   1  every comment was read and none carries it
#   2  the read was incomplete and the part read carries none: unknown
# Only 1 licenses posting. An incomplete read is not absence (t2252).

# _overlap_lookup_verdict <bodies> <complete:true|false> — the verdict for the
# comment bodies that were read.
_overlap_lookup_verdict() {
    # A shell substring test, never `echo | grep -q`: under pipefail, grep -q
    # exits on an early match, echo dies of SIGPIPE (141) on a long body, and
    # the lookup reads as "absent" (t2252).
    [[ "$1" == *"<!-- overlap-results"* ]] && return 0
    [[ "$2" == true ]] && return 1
    return 2
}

github_has_overlap_comment() {
    local issue_num="$1"
    local repo_flag=()
    [[ -n "$ARG_REPO" ]] && repo_flag=(-R "$ARG_REPO")
    local comments complete=true
    # gh reads every page of comments itself (preloadIssueComments, gh 2.102.1).
    comments=$(gh issue view "$issue_num" "${repo_flag[@]}" --json comments --jq '.comments[].body' 2>/dev/null) || complete=false
    _overlap_lookup_verdict "$comments" "$complete"
}

gitlab_has_overlap_comment() {
    local issue_num="$1"
    local notes bodies complete=true
    notes=$(_gitlab_issue_notes "$issue_num") || complete=false
    bodies=$(printf '%s\n' "$notes" | jq -r '.[].body // empty' 2>/dev/null) || return 2
    _overlap_lookup_verdict "$bodies" "$complete"
}

source_has_overlap_comment() {
    local issue_num="$1"
    case "$CHECK_PLATFORM" in
        github) github_has_overlap_comment "$issue_num" ;;
        gitlab) gitlab_has_overlap_comment "$issue_num" ;;
        bitbucket) _bitbucket_issues_removed ;;
        *) return 2 ;;
    esac
}

# _post_overlap_comment_once — posts OVERLAP_COMMENT on ARG_ISSUE unless the
# issue already carries an overlap analysis. Returns 0 when posted or already
# present; 1, posting nothing, when the lookup could not read every comment;
# 2 when the post itself failed.
#
# Callers invoke it as `_post_overlap_comment_once || …`, and bash turns
# errexit off inside a function called that way, for everything it calls.
# Every failure that matters is therefore checked explicitly here (t2252).
_post_overlap_comment_once() {
    local lookup_rc=0
    source_has_overlap_comment "$ARG_ISSUE" || lookup_rc=$?
    case "$lookup_rc" in
        0)
            [[ "$ARG_SILENT" != true ]] && info "Overlap comment already exists on issue #${ARG_ISSUE}. Skipping."
            ;;
        1)
            if ! source_post_comment "$ARG_ISSUE" "$OVERLAP_COMMENT"; then
                warn "Failed to post the overlap analysis comment to issue #${ARG_ISSUE}."
                return 2
            fi
            [[ "$ARG_SILENT" != true ]] && info "Posted overlap analysis comment to issue #${ARG_ISSUE}."
            ;;
        *)
            warn "Could not read every comment on issue #${ARG_ISSUE}, so it is unknown whether it already has an overlap analysis. Not posting, to avoid a duplicate; re-run the check."
            return 1
            ;;
    esac
    return 0
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

# _is_auto_applicable_label <label> — 0 when the label lies in one of
# CONTRIBUTION_AUTO_APPLY_PREFIXES with a non-empty value (see that constant
# for why author-supplied labels are otherwise never applied).
_is_auto_applicable_label() {
    local label="$1" prefix
    for prefix in "${CONTRIBUTION_AUTO_APPLY_PREFIXES[@]}"; do
        if [[ "$label" == "$prefix"?* ]]; then
            return 0
        fi
    done
    return 1
}

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
        [[ -z "$CHECK_PLATFORM" ]] && die "Could not auto-detect platform from git remote. Use --platform github|gitlab"
    fi

    case "$CHECK_PLATFORM" in
        github|gitlab|bitbucket) ;;
        *) die "Unknown platform: $CHECK_PLATFORM (supported: github, gitlab)" ;;
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
            _post_overlap_comment_once || return 1
        fi
        return 0
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

    local post_rc=0
    if [[ "$ARG_DRY_RUN" == true ]]; then
        echo "$OVERLAP_COMMENT"
    else
        _post_overlap_comment_once || post_rc=$?
        # A failed post stops here, as the inline post did under errexit. An
        # unknown lookup (post_rc 1) still applies labels — they are not
        # duplicated — and fails the run below.
        [[ "$post_rc" -eq 2 ]] && return 1

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
                    _is_auto_applicable_label "$label" || continue
                    if [[ -n "${repo_label_map[$label]:-}" ]]; then
                        source_add_label "$ARG_ISSUE" "$label"
                        [[ "$ARG_SILENT" != true ]] && info "Applied label: $label"
                    fi
                done
                unset IFS
            fi
        fi
    fi

    # The comment lookup was incomplete: nothing was posted, so the run fails.
    [[ "$post_rc" -eq 0 ]] || return 1

    if [[ "$ARG_SILENT" != true ]]; then
        success "Overlap analysis complete for issue #${ARG_ISSUE}."
    fi
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
