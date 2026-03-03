#!/usr/bin/env bash

# aitask_pr_import.sh - Import GitHub/GitLab/Bitbucket pull requests as AI task files
# Uses gh/glab/bkt CLI to fetch PR data and aitask_create.sh to create tasks
# Can also write structured intermediate data files for Claude Code skills

set -e

TASK_DIR="aitasks"
ARCHIVED_DIR="aitasks/archived"
LABELS_FILE="aitasks/metadata/labels.txt"
PR_DATA_DIR=".aitask-pr-data"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

# Batch mode variables
BATCH_MODE=false
SOURCE=""  # Auto-detected from git remote if not set via --source
REPO_OVERRIDE=""  # GitLab repo override for cross-repo imports (--repo)
BATCH_PR_NUM=""
BATCH_PR_RANGE=""
BATCH_ALL=false
BATCH_LIST=false
BATCH_DATA_ONLY=false
BATCH_PRIORITY="medium"
BATCH_EFFORT="medium"
BATCH_TYPE=""
BATCH_STATUS="Ready"
BATCH_LABELS=""
BATCH_DEPS=""
BATCH_PARENT=""
BATCH_NO_SIBLING_DEP=false
BATCH_COMMIT=false
BATCH_SILENT=false
BATCH_SKIP_DUPLICATES=false
BATCH_NO_DIFF=false
BATCH_NO_REVIEWS=false
BATCH_NO_COMMENTS=false
MAX_DIFF_LINES=5000

# --- Helper Functions ---

sanitize_name() {
    local name="$1"
    echo "$name" | tr '[:upper:]' '[:lower:]' | tr ' ' '_' | tr -cd 'a-z0-9_' | sed 's/__*/_/g' | sed 's/^_//;s/_$//' | cut -c1-60
}

utc_to_local() {
    local utc_ts="$1"
    portable_date -d "$utc_ts" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "$utc_ts"
}

ensure_labels_file() {
    local dir
    dir=$(dirname "$LABELS_FILE")
    mkdir -p "$dir"
    touch "$LABELS_FILE"
}

get_existing_labels() {
    ensure_labels_file
    if [[ -s "$LABELS_FILE" ]]; then
        sort -u "$LABELS_FILE"
    fi
}

ensure_pr_data_dir() {
    mkdir -p "$PR_DATA_DIR"
}

# ============================================================
# PLATFORM BACKENDS
# ============================================================

# --- GitHub Backend ---

github_check_cli() {
    command -v gh &>/dev/null || die "gh CLI is required for GitHub. Install: https://cli.github.com/"
    command -v jq &>/dev/null || die "jq is required. Install via your package manager."
    gh auth status &>/dev/null || die "gh CLI is not authenticated. Run: gh auth login"
}

# Returns JSON with PR metadata
github_fetch_pr() {
    local pr_num="$1"
    gh pr view "$pr_num" --json title,body,author,labels,url,comments,createdAt,updatedAt,headRefName,baseRefName,state,additions,deletions,changedFiles
}

github_fetch_pr_diff() {
    local pr_num="$1"
    gh pr diff "$pr_num" 2>/dev/null || echo ""
}

github_fetch_pr_files() {
    local pr_num="$1"
    gh pr view "$pr_num" --json files --jq '.files[] | "\(.path)\t+\(.additions)\t-\(.deletions)"' 2>/dev/null || echo ""
}

github_fetch_pr_reviews() {
    local pr_num="$1"
    local owner_repo
    owner_repo=$(gh repo view --json nameWithOwner --jq '.nameWithOwner' 2>/dev/null) || { echo "[]"; return; }
    gh api "repos/${owner_repo}/pulls/${pr_num}/reviews" 2>/dev/null || echo "[]"
}

github_fetch_pr_review_comments() {
    local pr_num="$1"
    local owner_repo
    owner_repo=$(gh repo view --json nameWithOwner --jq '.nameWithOwner' 2>/dev/null) || { echo "[]"; return; }
    gh api "repos/${owner_repo}/pulls/${pr_num}/comments" 2>/dev/null || echo "[]"
}

github_list_prs() {
    gh pr list --state open --limit 500 --json number,title,labels,url,author
}

github_extract_pr_author() {
    local pr_json="$1"
    echo "$pr_json" | jq -r '.author.login'
}

github_resolve_contributor_email() {
    local username="$1"
    local user_id
    user_id=$(gh api "users/${username}" --jq '.id' 2>/dev/null || echo "")
    if [[ -n "$user_id" ]]; then
        echo "${user_id}+${username}@users.noreply.github.com"
    else
        echo "${username}@users.noreply.github.com"
    fi
}

github_map_labels() {
    local labels_json="$1"
    local result
    result=$(echo "$labels_json" | jq -r '.[].name' 2>/dev/null | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_-]/_/g' | sed 's/__*/_/g' | sed 's/^_//;s/_$//' | paste -sd ',' 2>/dev/null)
    echo "$result"
}

github_detect_type() {
    local labels_json="$1"
    local label_names
    label_names=$(echo "$labels_json" | jq -r '.[].name' 2>/dev/null)
    if echo "$label_names" | grep -qi "^bug$"; then
        echo "bug"
    elif echo "$label_names" | grep -qiE "^(refactor|refactoring|tech-debt|cleanup)$"; then
        echo "refactor"
    elif echo "$label_names" | grep -qiE "^(test|testing|tests)$"; then
        echo "test"
    elif echo "$label_names" | grep -qiE "^(style|styling|formatting|lint|linting)$"; then
        echo "style"
    elif echo "$label_names" | grep -qiE "^(chore|maintenance|housekeeping|deps|dependencies)$"; then
        echo "chore"
    elif echo "$label_names" | grep -qiE "^(documentation|docs)$"; then
        echo "documentation"
    elif echo "$label_names" | grep -qiE "^(performance|perf|optimization)$"; then
        echo "performance"
    else
        echo "feature"
    fi
}

github_format_comments() {
    local comments_json="$1"
    local count
    count=$(echo "$comments_json" | jq length)
    [[ "$count" -eq 0 ]] && return 0

    echo ""
    echo "## Comments"
    echo ""
    local i last_idx
    last_idx=$((count - 1))
    for ((i=0; i<count; i++)); do
        local author created_at body local_time
        author=$(echo "$comments_json" | jq -r ".[$i].author.login")
        created_at=$(echo "$comments_json" | jq -r ".[$i].createdAt")
        body=$(echo "$comments_json" | jq -r ".[$i].body")
        local_time=$(utc_to_local "$created_at")
        echo "**${author}** (${local_time})"
        echo ""
        echo "$body"
        if [[ $i -lt $last_idx ]]; then
            echo ""
            echo "-------"
            echo ""
        fi
    done
}

github_preview_pr() {
    local pr_num="$1"
    gh pr view "$pr_num"
}

# --- GitLab Backend ---

gitlab_check_cli() {
    command -v glab &>/dev/null || die "glab CLI is required for GitLab. Install: https://gitlab.com/gitlab-org/cli"
    command -v jq &>/dev/null || die "jq is required. Install via your package manager."
    glab auth status &>/dev/null || die "glab CLI is not authenticated. Run: glab auth login"
}

# Get -R flag arguments for glab mr commands when REPO_OVERRIDE is set
glab_repo_args() {
    if [[ -n "$REPO_OVERRIDE" ]]; then
        echo "-R $REPO_OVERRIDE"
    fi
}

# Get project path for glab api commands
# Returns URL-encoded REPO_OVERRIDE or :fullpath for auto-detection
glab_api_project_path() {
    if [[ -n "$REPO_OVERRIDE" ]]; then
        echo "${REPO_OVERRIDE//\//%2F}"
    else
        echo ":fullpath"
    fi
}

# Returns JSON normalized to GitHub-compatible format
gitlab_fetch_pr() {
    local mr_num="$1"
    local mr_json notes_json

    mr_json=$(glab mr view "$mr_num" $(glab_repo_args) -F json)
    notes_json=$(glab api "projects/$(glab_api_project_path)/merge_requests/$mr_num/notes?sort=asc&per_page=100" 2>/dev/null || echo "[]")

    # TODO: additions/deletions hardcoded to 0 — GitLab MR API doesn't provide totals
    echo "$mr_json" | jq --argjson notes "$notes_json" '{
        title: .title,
        body: (.description // ""),
        author: {login: .author.username},
        labels: [.labels[] | {name: .}],
        url: .web_url,
        comments: [$notes[] | select(.system != true) | {
            author: {login: .author.username},
            body: .body,
            createdAt: .created_at
        }],
        createdAt: .created_at,
        updatedAt: .updated_at,
        headRefName: .source_branch,
        baseRefName: .target_branch,
        state: .state,
        additions: 0,
        deletions: 0,
        changedFiles: (.changes_count // 0)
    }'
}

gitlab_fetch_pr_diff() {
    local mr_num="$1"
    glab mr diff "$mr_num" $(glab_repo_args) 2>/dev/null || echo ""
}

gitlab_fetch_pr_files() {
    local mr_num="$1"
    local project_path
    project_path=$(glab_api_project_path)
    glab api "projects/$project_path/merge_requests/$mr_num/changes" 2>/dev/null | jq -r '.changes[] | "\(.new_path)\t+\(.diff | split("\n") | map(select(startswith("+"))) | length)\t-\(.diff | split("\n") | map(select(startswith("-"))) | length)"' 2>/dev/null || echo ""
}

gitlab_fetch_pr_reviews() {
    local mr_num="$1"
    local notes_json
    notes_json=$(glab api "projects/$(glab_api_project_path)/merge_requests/$mr_num/notes?sort=asc&per_page=100" 2>/dev/null || echo "[]")
    # Normalize to GitHub review format
    echo "$notes_json" | jq '[.[] | select(.system != true) | {
        user: {login: .author.username},
        state: "COMMENTED",
        body: .body,
        submitted_at: .created_at
    }]'
}

gitlab_fetch_pr_review_comments() {
    local mr_num="$1"
    local discussions_json
    discussions_json=$(glab api "projects/$(glab_api_project_path)/merge_requests/$mr_num/discussions" 2>/dev/null || echo "[]")
    # Extract inline comments from discussions
    echo "$discussions_json" | jq '[.[] | .notes[] | select(.position != null) | {
        user: {login: .author.username},
        body: .body,
        path: .position.new_path,
        line: (.position.new_line // .position.old_line),
        created_at: .created_at
    }]'
}

gitlab_list_prs() {
    glab mr list $(glab_repo_args) --all --output json | jq '[.[] | {
        number: .iid,
        title: .title,
        labels: [.labels[] | {name: .}],
        url: .web_url,
        author: {login: .author.username}
    }]'
}

gitlab_extract_pr_author() {
    local pr_json="$1"
    echo "$pr_json" | jq -r '.author.login'
}

gitlab_resolve_contributor_email() {
    local username="$1"
    local user_id
    user_id=$(glab api "users?username=${username}" 2>/dev/null | jq -r '.[0].id' 2>/dev/null || echo "")
    if [[ -n "$user_id" ]]; then
        echo "${user_id}+${username}@noreply.gitlab.com"
    else
        echo "${username}@noreply.gitlab.com"
    fi
}

gitlab_map_labels() {
    github_map_labels "$@"
}

gitlab_detect_type() {
    github_detect_type "$@"
}

gitlab_format_comments() {
    github_format_comments "$@"
}

gitlab_preview_pr() {
    local mr_num="$1"
    glab mr view "$mr_num" $(glab_repo_args)
}

# --- Bitbucket Backend ---

bitbucket_check_cli() {
    command -v bkt &>/dev/null || die "bkt CLI is required for Bitbucket. Install: https://github.com/avivsinai/bitbucket-cli"
    command -v jq &>/dev/null || die "jq is required. Install via your package manager."
    bkt auth status &>/dev/null || die "bkt CLI is not authenticated. Run: bkt auth login https://bitbucket.org --kind cloud --web"
}

# Returns JSON normalized to GitHub-compatible format
bitbucket_fetch_pr() {
    local pr_num="$1"
    local pr_json

    pr_json=$(bkt pr view "$pr_num" --json)

    echo "$pr_json" | jq '{
        title: .title,
        body: (.description // ""),
        author: {login: (.author.display_name // .author.nickname // "unknown")},
        labels: [],
        url: .links.html.href,
        comments: [(.comments // [])[] | {
            author: {login: (.author.display_name // .author.nickname // "unknown")},
            body: (.content.raw // .body // ""),
            createdAt: .created_on
        }],
        createdAt: .created_on,
        updatedAt: .updated_on,
        headRefName: .source.branch.name,
        baseRefName: .destination.branch.name,
        state: .state,
        additions: 0,
        deletions: 0,
        changedFiles: 0
    }'
}

bitbucket_fetch_pr_diff() {
    local pr_num="$1"
    bkt pr diff "$pr_num" 2>/dev/null || echo ""
}

bitbucket_fetch_pr_files() {
    # Bitbucket CLI may not support file listing directly
    echo ""
}

bitbucket_fetch_pr_reviews() {
    # Bitbucket uses a different review model — return empty
    echo "[]"
}

bitbucket_fetch_pr_review_comments() {
    echo "[]"
}

bitbucket_list_prs() {
    bkt pr list --json | jq '[(.values // .[])[] | {
        number: .id,
        title: .title,
        labels: [],
        url: .links.html.href,
        author: {login: (.author.display_name // .author.nickname // "unknown")}
    }]' 2>/dev/null || echo "[]"
}

bitbucket_extract_pr_author() {
    local pr_json="$1"
    echo "$pr_json" | jq -r '.author.login'
}

bitbucket_resolve_contributor_email() {
    local username="$1"
    # Bitbucket has no standard noreply scheme
    echo "${username}@bitbucket.org"
}

bitbucket_map_labels() {
    github_map_labels "$@"
}

bitbucket_detect_type() {
    # Bitbucket PRs don't typically have type labels — default to feature
    echo "feature"
}

bitbucket_format_comments() {
    github_format_comments "$@"
}

bitbucket_preview_pr() {
    local pr_num="$1"
    bkt pr view "$pr_num"
}

# --- Dispatcher Functions ---

source_check_cli() {
    case "$SOURCE" in
        github) github_check_cli ;;
        gitlab) gitlab_check_cli ;;
        bitbucket) bitbucket_check_cli ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_fetch_pr() {
    local pr_num="$1"
    case "$SOURCE" in
        github) github_fetch_pr "$pr_num" ;;
        gitlab) gitlab_fetch_pr "$pr_num" ;;
        bitbucket) bitbucket_fetch_pr "$pr_num" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_fetch_pr_diff() {
    local pr_num="$1"
    case "$SOURCE" in
        github) github_fetch_pr_diff "$pr_num" ;;
        gitlab) gitlab_fetch_pr_diff "$pr_num" ;;
        bitbucket) bitbucket_fetch_pr_diff "$pr_num" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_fetch_pr_files() {
    local pr_num="$1"
    case "$SOURCE" in
        github) github_fetch_pr_files "$pr_num" ;;
        gitlab) gitlab_fetch_pr_files "$pr_num" ;;
        bitbucket) bitbucket_fetch_pr_files "$pr_num" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_fetch_pr_reviews() {
    local pr_num="$1"
    case "$SOURCE" in
        github) github_fetch_pr_reviews "$pr_num" ;;
        gitlab) gitlab_fetch_pr_reviews "$pr_num" ;;
        bitbucket) bitbucket_fetch_pr_reviews "$pr_num" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_fetch_pr_review_comments() {
    local pr_num="$1"
    case "$SOURCE" in
        github) github_fetch_pr_review_comments "$pr_num" ;;
        gitlab) gitlab_fetch_pr_review_comments "$pr_num" ;;
        bitbucket) bitbucket_fetch_pr_review_comments "$pr_num" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_list_prs() {
    case "$SOURCE" in
        github) github_list_prs ;;
        gitlab) gitlab_list_prs ;;
        bitbucket) bitbucket_list_prs ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_extract_pr_author() {
    local pr_json="$1"
    case "$SOURCE" in
        github) github_extract_pr_author "$pr_json" ;;
        gitlab) gitlab_extract_pr_author "$pr_json" ;;
        bitbucket) bitbucket_extract_pr_author "$pr_json" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_resolve_contributor_email() {
    local username="$1"
    case "$SOURCE" in
        github) github_resolve_contributor_email "$username" ;;
        gitlab) gitlab_resolve_contributor_email "$username" ;;
        bitbucket) bitbucket_resolve_contributor_email "$username" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_map_labels() {
    local labels_json="$1"
    case "$SOURCE" in
        github) github_map_labels "$labels_json" ;;
        gitlab) gitlab_map_labels "$labels_json" ;;
        bitbucket) bitbucket_map_labels "$labels_json" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_detect_type() {
    local labels_json="$1"
    case "$SOURCE" in
        github) github_detect_type "$labels_json" ;;
        gitlab) gitlab_detect_type "$labels_json" ;;
        bitbucket) bitbucket_detect_type "$labels_json" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_format_comments() {
    local comments_json="$1"
    case "$SOURCE" in
        github) github_format_comments "$comments_json" ;;
        gitlab) gitlab_format_comments "$comments_json" ;;
        bitbucket) bitbucket_format_comments "$comments_json" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_preview_pr() {
    local pr_num="$1"
    case "$SOURCE" in
        github) github_preview_pr "$pr_num" ;;
        gitlab) gitlab_preview_pr "$pr_num" ;;
        bitbucket) bitbucket_preview_pr "$pr_num" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

# --- Review Formatting ---

format_pr_reviews() {
    local reviews_json="$1"
    local count
    count=$(echo "$reviews_json" | jq length)
    [[ "$count" -eq 0 ]] && return 0

    echo ""
    echo "## Reviews"
    echo ""
    local i last_idx
    last_idx=$((count - 1))
    for ((i=0; i<count; i++)); do
        local user state body submitted_at local_time
        user=$(echo "$reviews_json" | jq -r ".[$i].user.login")
        state=$(echo "$reviews_json" | jq -r ".[$i].state")
        body=$(echo "$reviews_json" | jq -r ".[$i].body // \"\"")
        submitted_at=$(echo "$reviews_json" | jq -r ".[$i].submitted_at // .[$i].created_at // \"\"")
        if [[ -n "$submitted_at" && "$submitted_at" != "null" ]]; then
            local_time=$(utc_to_local "$submitted_at")
        else
            local_time=""
        fi

        local state_label
        case "$state" in
            APPROVED) state_label="APPROVED" ;;
            CHANGES_REQUESTED) state_label="CHANGES REQUESTED" ;;
            COMMENTED) state_label="COMMENTED" ;;
            DISMISSED) state_label="DISMISSED" ;;
            *) state_label="$state" ;;
        esac

        if [[ -n "$local_time" ]]; then
            echo "**${user}** — ${state_label} (${local_time})"
        else
            echo "**${user}** — ${state_label}"
        fi
        if [[ -n "$body" && "$body" != "null" ]]; then
            echo ""
            echo "$body"
        fi
        if [[ $i -lt $last_idx ]]; then
            echo ""
            echo "-------"
            echo ""
        fi
    done
}

format_inline_review_comments() {
    local comments_json="$1"
    local count
    count=$(echo "$comments_json" | jq length)
    [[ "$count" -eq 0 ]] && return 0

    echo ""
    echo "## Inline Review Comments"
    echo ""
    local i last_idx
    last_idx=$((count - 1))
    for ((i=0; i<count; i++)); do
        local user body path line created_at local_time
        user=$(echo "$comments_json" | jq -r ".[$i].user.login")
        body=$(echo "$comments_json" | jq -r ".[$i].body")
        path=$(echo "$comments_json" | jq -r ".[$i].path")
        line=$(echo "$comments_json" | jq -r ".[$i].line // .[$i].original_line // .[$i].position // \"\"")
        created_at=$(echo "$comments_json" | jq -r ".[$i].created_at // .[$i].createdAt // \"\"")
        if [[ -n "$created_at" && "$created_at" != "null" ]]; then
            local_time=$(utc_to_local "$created_at")
        else
            local_time=""
        fi

        echo "**${user}** on \`${path}\`"
        if [[ -n "$line" && "$line" != "null" && "$line" != "" ]]; then
            echo "Line: ${line}"
        fi
        if [[ -n "$local_time" ]]; then
            echo "Time: ${local_time}"
        fi
        echo ""
        echo "$body"
        if [[ $i -lt $last_idx ]]; then
            echo ""
            echo "-------"
            echo ""
        fi
    done
}

# --- Duplicate Detection ---

check_duplicate_pr_import() {
    local pr_num="$1"
    local found=""
    # Build URL pattern based on platform
    local url_pattern
    case "$SOURCE" in
        github) url_pattern="/pull/${pr_num}" ;;
        gitlab) url_pattern="/merge_requests/${pr_num}" ;;
        bitbucket) url_pattern="/pull-requests/${pr_num}" ;;
        *) url_pattern="/${pr_num}" ;;
    esac
    # Search active tasks
    found=$(grep -rl "^pull_request:.*${url_pattern}$" "$TASK_DIR"/ 2>/dev/null | head -1)
    if [[ -z "$found" ]]; then
        # Search archived tasks
        found=$(grep -rl "^pull_request:.*${url_pattern}$" "$ARCHIVED_DIR"/ 2>/dev/null | head -1)
    fi
    echo "$found"
}

# --- Intermediate Data File ---

write_pr_data_file() {
    local pr_num="$1"
    local pr_json="$2"
    local diff_text="$3"
    local reviews_json="$4"
    local review_comments_json="$5"
    local files_text="$6"

    ensure_pr_data_dir

    local title body author url pr_created pr_updated
    local head_branch base_branch state additions deletions changed_files
    local labels_json comments_json

    title=$(echo "$pr_json" | jq -r '.title')
    body=$(echo "$pr_json" | jq -r '.body // ""')
    author=$(source_extract_pr_author "$pr_json")
    url=$(echo "$pr_json" | jq -r '.url')
    pr_created=$(echo "$pr_json" | jq -r '.createdAt // ""')
    pr_updated=$(echo "$pr_json" | jq -r '.updatedAt // ""')
    head_branch=$(echo "$pr_json" | jq -r '.headRefName // ""')
    base_branch=$(echo "$pr_json" | jq -r '.baseRefName // ""')
    state=$(echo "$pr_json" | jq -r '.state // ""')
    additions=$(echo "$pr_json" | jq -r '.additions // 0')
    deletions=$(echo "$pr_json" | jq -r '.deletions // 0')
    changed_files=$(echo "$pr_json" | jq -r '.changedFiles // 0')
    labels_json=$(echo "$pr_json" | jq -c '.labels // []')
    comments_json=$(echo "$pr_json" | jq -c '.comments // []')

    local contributor_email
    contributor_email=$(source_resolve_contributor_email "$author")

    local now
    now=$(portable_date '+%Y-%m-%d %H:%M' 2>/dev/null || date '+%Y-%m-%d %H:%M')

    local data_file="${PR_DATA_DIR}/${pr_num}.md"
    {
        echo "---"
        echo "pr_number: ${pr_num}"
        echo "pr_url: ${url}"
        echo "contributor: ${author}"
        echo "contributor_email: ${contributor_email}"
        echo "platform: ${SOURCE}"
        echo "title: \"${title}\""
        echo "state: ${state}"
        echo "base_branch: ${base_branch}"
        echo "head_branch: ${head_branch}"
        echo "additions: ${additions}"
        echo "deletions: ${deletions}"
        echo "changed_files: ${changed_files}"
        echo "fetched_at: ${now}"
        echo "---"
        echo ""
        echo "## Description"
        echo ""
        if [[ -n "$body" && "$body" != "null" ]]; then
            echo "$body"
        else
            echo "(No description provided)"
        fi

        # Comments
        if [[ "$BATCH_NO_COMMENTS" != true ]]; then
            local comments_text
            comments_text=$(source_format_comments "$comments_json")
            if [[ -n "$comments_text" ]]; then
                echo "$comments_text"
            fi
        fi

        # Reviews
        if [[ "$BATCH_NO_REVIEWS" != true ]]; then
            local reviews_text
            reviews_text=$(format_pr_reviews "$reviews_json")
            if [[ -n "$reviews_text" ]]; then
                echo "$reviews_text"
            fi

            local inline_text
            inline_text=$(format_inline_review_comments "$review_comments_json")
            if [[ -n "$inline_text" ]]; then
                echo "$inline_text"
            fi
        fi

        # Changed files
        if [[ -n "$files_text" ]]; then
            echo ""
            echo "## Changed Files"
            echo ""
            echo "$files_text"
        fi

        # Diff
        if [[ "$BATCH_NO_DIFF" != true && -n "$diff_text" ]]; then
            echo ""
            echo "## Diff"
            echo ""
            local diff_lines
            diff_lines=$(echo "$diff_text" | wc -l | tr -d ' ')
            if [[ "$diff_lines" -gt "$MAX_DIFF_LINES" ]]; then
                echo "$diff_text" | head -n "$MAX_DIFF_LINES"
                echo ""
                echo "[Diff truncated at $MAX_DIFF_LINES lines (total: $diff_lines lines)]"
            else
                echo "$diff_text"
            fi
        fi
    } > "$data_file"

    echo "$data_file"
}

# --- Core Import Function ---

import_single_pr() {
    local pr_num="$1"

    # Check for duplicate
    local existing
    existing=$(check_duplicate_pr_import "$pr_num")
    if [[ -n "$existing" ]]; then
        if [[ "$BATCH_SKIP_DUPLICATES" == true ]]; then
            [[ "$BATCH_SILENT" == true ]] || warn "PR #$pr_num already imported as: $existing (skipping)"
            return 0
        else
            warn "PR #$pr_num already imported as: $existing"
        fi
    fi

    # Fetch PR data
    local pr_json
    pr_json=$(source_fetch_pr "$pr_num") || die "Failed to fetch PR #$pr_num"

    local title body url labels_json comments_json pr_created pr_updated
    local head_branch base_branch state additions deletions changed_files
    title=$(echo "$pr_json" | jq -r '.title')
    body=$(echo "$pr_json" | jq -r '.body // ""')
    url=$(echo "$pr_json" | jq -r '.url')
    labels_json=$(echo "$pr_json" | jq -c '.labels // []')
    comments_json=$(echo "$pr_json" | jq -c '.comments // []')
    pr_created=$(echo "$pr_json" | jq -r '.createdAt // ""')
    pr_updated=$(echo "$pr_json" | jq -r '.updatedAt // ""')
    head_branch=$(echo "$pr_json" | jq -r '.headRefName // ""')
    base_branch=$(echo "$pr_json" | jq -r '.baseRefName // ""')
    state=$(echo "$pr_json" | jq -r '.state // ""')
    additions=$(echo "$pr_json" | jq -r '.additions // 0')
    deletions=$(echo "$pr_json" | jq -r '.deletions // 0')
    changed_files=$(echo "$pr_json" | jq -r '.changedFiles // 0')

    local pr_author contributor_email
    pr_author=$(source_extract_pr_author "$pr_json")
    contributor_email=$(source_resolve_contributor_email "$pr_author")

    # Fetch additional data
    local diff_text="" reviews_json="[]" review_comments_json="[]" files_text=""

    if [[ "$BATCH_NO_DIFF" != true ]]; then
        diff_text=$(source_fetch_pr_diff "$pr_num")
    fi
    if [[ "$BATCH_NO_REVIEWS" != true ]]; then
        reviews_json=$(source_fetch_pr_reviews "$pr_num")
        review_comments_json=$(source_fetch_pr_review_comments "$pr_num")
    fi
    files_text=$(source_fetch_pr_files "$pr_num")

    # Data-only mode: write intermediate file and return
    if [[ "$BATCH_DATA_ONLY" == true ]]; then
        local data_file
        data_file=$(write_pr_data_file "$pr_num" "$pr_json" "$diff_text" "$reviews_json" "$review_comments_json" "$files_text")
        if [[ "$BATCH_SILENT" == true ]]; then
            echo "$data_file"
        else
            success "Data file written: $data_file"
        fi
        return 0
    fi

    # Task creation mode
    local task_name aitask_labels issue_type
    task_name=$(sanitize_name "$title")
    [[ -z "$task_name" ]] && task_name="pr_${pr_num}"

    if [[ -n "$BATCH_LABELS" ]]; then
        aitask_labels="$BATCH_LABELS"
    else
        aitask_labels=$(source_map_labels "$labels_json")
    fi

    if [[ -n "$BATCH_TYPE" ]]; then
        issue_type="$BATCH_TYPE"
    else
        issue_type=$(source_detect_type "$labels_json")
    fi

    # Build description
    local ts_line=""
    if [[ -n "$pr_created" ]]; then
        ts_line="PR created: $(utc_to_local "$pr_created")"
        if [[ -n "$pr_updated" && "$pr_updated" != "$pr_created" ]]; then
            ts_line="${ts_line}, last updated: $(utc_to_local "$pr_updated")"
        fi
    fi

    local branch_info=""
    if [[ -n "$head_branch" && -n "$base_branch" ]]; then
        branch_info="Branch: ${head_branch} → ${base_branch}"
    fi

    local stats_info=""
    if [[ "$additions" != "0" || "$deletions" != "0" ]]; then
        stats_info="Changes: +${additions} -${deletions} (${changed_files} files)"
    fi

    local description=""
    [[ -n "$ts_line" ]] && description="${ts_line}"
    if [[ -n "$branch_info" ]]; then
        [[ -n "$description" ]] && description="${description}"$'\n'
        description="${description}${branch_info}"
    fi
    if [[ -n "$stats_info" ]]; then
        [[ -n "$description" ]] && description="${description}"$'\n'
        description="${description}${stats_info}"
    fi
    [[ -n "$description" ]] && description="${description}"$'\n'
    description="${description}"$'\n'"## ${title}"$'\n'
    if [[ -n "$body" && "$body" != "null" ]]; then
        description="${description}"$'\n'"${body}"
    fi

    # Append comments if not disabled
    if [[ "$BATCH_NO_COMMENTS" != true ]]; then
        local comments_text
        comments_text=$(source_format_comments "$comments_json")
        if [[ -n "$comments_text" ]]; then
            description="${description}${comments_text}"
        fi
    fi

    # Append reviews if not disabled
    if [[ "$BATCH_NO_REVIEWS" != true ]]; then
        local reviews_text
        reviews_text=$(format_pr_reviews "$reviews_json")
        if [[ -n "$reviews_text" ]]; then
            description="${description}${reviews_text}"
        fi
    fi

    # Build aitask_create.sh arguments
    local create_args=(--batch --name "$task_name"
        --desc-file -
        --priority "$BATCH_PRIORITY" --effort "$BATCH_EFFORT"
        --type "$issue_type" --status "$BATCH_STATUS"
        --pull-request "$url"
        --contributor "$pr_author"
        --contributor-email "$contributor_email")

    [[ -n "$aitask_labels" ]] && create_args+=(--labels "$aitask_labels")
    [[ -n "$BATCH_DEPS" ]] && create_args+=(--deps "$BATCH_DEPS")
    [[ -n "$BATCH_PARENT" ]] && create_args+=(--parent "$BATCH_PARENT")
    [[ "$BATCH_NO_SIBLING_DEP" == true ]] && create_args+=(--no-sibling-dep)
    [[ "$BATCH_COMMIT" == true ]] && create_args+=(--commit)
    [[ "$BATCH_SILENT" == true ]] && create_args+=(--silent)

    echo "$description" | "$SCRIPT_DIR/aitask_create.sh" "${create_args[@]}"
}

# --- Batch Mode ---

run_batch_mode() {
    source_check_cli

    # List mode: output PR listing for skill parsing
    if [[ "$BATCH_LIST" == true ]]; then
        local prs_json
        prs_json=$(source_list_prs)
        if [[ "$BATCH_SILENT" == true ]]; then
            echo "$prs_json" | jq -r '.[] | "\(.number)\t\(.title)"'
        else
            echo "$prs_json" | jq -r '.[] | "#\(.number) - \(.title) [@\(.author.login)]"'
        fi
        return 0
    fi

    if [[ "$BATCH_ALL" == true ]]; then
        local prs
        prs=$(source_list_prs | jq -r '.[].number' | sort -n)
        if [[ -z "$prs" ]]; then
            info "No open PRs found."
            return 0
        fi
        local count=0
        while IFS= read -r num; do
            [[ -z "$num" ]] && continue
            import_single_pr "$num"
            count=$((count + 1))
        done <<< "$prs"
        [[ "$BATCH_SILENT" == true ]] || success "Imported $count PR(s)."
    elif [[ -n "$BATCH_PR_RANGE" ]]; then
        local start end
        IFS='-' read -r start end <<< "$BATCH_PR_RANGE"
        [[ -z "$start" || -z "$end" ]] && die "Invalid range format. Use: START-END (e.g., 5-10)"
        [[ "$start" -gt "$end" ]] && die "Invalid range: start ($start) > end ($end)"
        local count=0
        for ((num=start; num<=end; num++)); do
            import_single_pr "$num"
            count=$((count + 1))
        done
        [[ "$BATCH_SILENT" == true ]] || success "Imported $count PR(s)."
    elif [[ -n "$BATCH_PR_NUM" ]]; then
        import_single_pr "$BATCH_PR_NUM"
    else
        die "Batch mode requires --pr, --range, --all, or --list"
    fi
}

# --- Interactive Mode ---

interactive_import_pr() {
    local pr_num="$1"

    # Check for duplicate
    local existing
    existing=$(check_duplicate_pr_import "$pr_num")
    if [[ -n "$existing" ]]; then
        warn "PR #$pr_num already imported as: $(basename "$existing")"
        local skip
        skip=$(printf "Skip\nImport anyway" | fzf --prompt="Already imported: " --height=8 --no-info)
        [[ "$skip" == "Skip" || -z "$skip" ]] && return 0
    fi

    # Fetch full PR data
    info "Fetching PR #$pr_num..."
    local pr_json
    pr_json=$(source_fetch_pr "$pr_num") || die "Failed to fetch PR #$pr_num"

    local title body url labels_json comments_json pr_created pr_updated
    local head_branch base_branch state additions deletions changed_files
    title=$(echo "$pr_json" | jq -r '.title')
    body=$(echo "$pr_json" | jq -r '.body // ""')
    url=$(echo "$pr_json" | jq -r '.url')
    labels_json=$(echo "$pr_json" | jq -c '.labels // []')
    comments_json=$(echo "$pr_json" | jq -c '.comments // []')
    pr_created=$(echo "$pr_json" | jq -r '.createdAt // ""')
    pr_updated=$(echo "$pr_json" | jq -r '.updatedAt // ""')
    head_branch=$(echo "$pr_json" | jq -r '.headRefName // ""')
    base_branch=$(echo "$pr_json" | jq -r '.baseRefName // ""')
    state=$(echo "$pr_json" | jq -r '.state // ""')
    additions=$(echo "$pr_json" | jq -r '.additions // 0')
    deletions=$(echo "$pr_json" | jq -r '.deletions // 0')
    changed_files=$(echo "$pr_json" | jq -r '.changedFiles // 0')

    local pr_author
    pr_author=$(source_extract_pr_author "$pr_json")

    # Show preview
    echo ""
    echo -e "${BLUE}━━━ PR #$pr_num: $title ━━━${NC}"
    echo "Author: @${pr_author} | Branch: ${head_branch} → ${base_branch}"
    echo "State: ${state} | Changes: +${additions} -${deletions} (${changed_files} files)"
    echo ""
    echo "$body" | head -30
    local body_lines
    body_lines=$(echo "$body" | wc -l)
    if [[ "$body_lines" -gt 30 ]]; then
        warn "(truncated -- full text will be in task file)"
    fi
    echo ""

    # Confirm import
    local confirm
    confirm=$(printf "Import as task (basic — title, body, metadata only)\nExtract PR data only (for /aitask-pr-review skill)\nSkip" | \
        fzf --prompt="Import this PR? " --height=10 --no-info \
        --header="Data-only extracts to .aitask-pr-data/ for use with /aitask-pr-review")
    [[ "$confirm" == "Skip" || -z "$confirm" ]] && return 0

    local data_only=false
    [[ "$confirm" == "Extract PR data"* ]] && data_only=true

    if [[ "$data_only" == true ]]; then
        # Data-only mode: write intermediate file
        local diff_text="" reviews_json="[]" review_comments_json="[]" files_text=""
        info "Fetching PR diff and reviews..."
        diff_text=$(source_fetch_pr_diff "$pr_num")
        reviews_json=$(source_fetch_pr_reviews "$pr_num")
        review_comments_json=$(source_fetch_pr_review_comments "$pr_num")
        files_text=$(source_fetch_pr_files "$pr_num")

        local data_file
        data_file=$(write_pr_data_file "$pr_num" "$pr_json" "$diff_text" "$reviews_json" "$review_comments_json" "$files_text")
        success "Data file written: $data_file"
        return 0
    fi

    info ""
    info "Note: The /aitask-pr-review code agent skill provides additional features:"
    info "  - AI analysis of PR purpose, quality, and concerns"
    info "  - Implementation approach recommendations"
    info "  - Codebase alignment checks and testing requirements"
    info "  - Related task discovery and folding"
    info ""

    # Task name: auto-generate, let user edit
    local auto_name
    auto_name=$(sanitize_name "$title")
    read -erp "Task name [$auto_name]: " user_name < /dev/tty
    local task_name="${user_name:-$auto_name}"
    task_name=$(sanitize_name "$task_name")

    # Labels: interactive selection
    set +e

    local selected_labels=()

    local auto_labels
    auto_labels=$(source_map_labels "$labels_json")
    if [[ -n "$auto_labels" ]]; then
        info "PR labels:"
        IFS=',' read -ra issue_label_arr <<< "$auto_labels"
        for lbl in "${issue_label_arr[@]}"; do
            lbl=$(echo "$lbl" | xargs)
            [[ -z "$lbl" ]] && continue
            local keep
            keep=$(printf "Yes\nNo" | fzf --prompt="Keep label '$lbl'? " --height=8 --no-info)
            if [[ "$keep" == "Yes" ]]; then
                selected_labels+=("$lbl")
                success "  Kept: $lbl"
            fi
        done
    fi

    while true; do
        local existing_labels
        existing_labels=$(get_existing_labels)

        local available_labels=""
        if [[ -n "$existing_labels" ]]; then
            while IFS= read -r lbl; do
                local is_selected=false
                for sel in "${selected_labels[@]}"; do
                    if [[ "$sel" == "$lbl" ]]; then
                        is_selected=true
                        break
                    fi
                done
                if [[ "$is_selected" == "false" ]]; then
                    if [[ -n "$available_labels" ]]; then
                        available_labels="${available_labels}"$'\n'"${lbl}"
                    else
                        available_labels="$lbl"
                    fi
                fi
            done <<< "$existing_labels"
        fi

        local options
        if [[ -n "$available_labels" ]]; then
            options=">> Done adding labels"$'\n'">> Add new label"$'\n'"$available_labels"
        else
            options=">> Done adding labels"$'\n'">> Add new label"
        fi

        local selected
        selected=$(printf "%s" "$options" | fzf --prompt="Select label: " --height=15 --no-info --header="Add more labels or finish")

        if [[ -z "$selected" || "$selected" == ">> Done adding labels" ]]; then
            break
        elif [[ "$selected" == ">> Add new label" ]]; then
            local new_label
            read -erp "Enter new label: " new_label < /dev/tty
            if [[ -n "$new_label" ]]; then
                local label
                label=$(echo "$new_label" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_-]//g') || true
                if [[ -n "$label" ]]; then
                    ensure_labels_file
                    if ! grep -qFx "$label" "$LABELS_FILE" 2>/dev/null; then
                        echo "$label" >> "$LABELS_FILE"
                        sort -u "$LABELS_FILE" -o "$LABELS_FILE"
                    fi
                    selected_labels+=("$label")
                    success "  Added: $label"
                fi
            fi
        else
            selected_labels+=("$selected")
            success "  Added: $selected"
        fi

        if [[ ${#selected_labels[@]} -gt 0 ]]; then
            info "Current labels: ${selected_labels[*]}"
        fi

        local continue_choice
        continue_choice=$(printf "Add another label\nDone with labels" | fzf --prompt="Continue? " --height=8 --no-info)
        if [[ "$continue_choice" == "Done with labels" || -z "$continue_choice" ]]; then
            break
        fi
    done

    local labels=""
    if [[ ${#selected_labels[@]} -gt 0 ]]; then
        local IFS=','
        labels="${selected_labels[*]}"
    fi

    set -e

    # Priority selection
    local priority
    priority=$(printf "medium\nhigh\nlow" | fzf --prompt="Priority: " --height=10 --no-info --header="Select priority")
    priority="${priority:-medium}"

    # Effort selection
    local effort
    effort=$(printf "medium\nlow\nhigh" | fzf --prompt="Effort: " --height=10 --no-info --header="Select effort")
    effort="${effort:-medium}"

    # Auto-detect issue type from labels
    local issue_type
    issue_type=$(source_detect_type "$labels_json")

    # Resolve contributor email
    local contributor_email
    contributor_email=$(source_resolve_contributor_email "$pr_author")

    # Build description
    local ts_line=""
    if [[ -n "$pr_created" ]]; then
        ts_line="PR created: $(utc_to_local "$pr_created")"
        if [[ -n "$pr_updated" && "$pr_updated" != "$pr_created" ]]; then
            ts_line="${ts_line}, last updated: $(utc_to_local "$pr_updated")"
        fi
    fi
    local description
    if [[ -n "$ts_line" ]]; then
        description=$(printf "%s\nBranch: %s → %s\nChanges: +%s -%s (%s files)\n\n## %s\n\n%s" \
            "$ts_line" "$head_branch" "$base_branch" "$additions" "$deletions" "$changed_files" "$title" "$body")
    else
        description=$(printf "## %s\n\n%s" "$title" "$body")
    fi

    # Append comments
    local comments_text
    comments_text=$(source_format_comments "$comments_json")
    if [[ -n "$comments_text" ]]; then
        description="${description}${comments_text}"
    fi

    local create_args=(--batch --name "$task_name"
        --desc-file -
        --priority "$priority" --effort "$effort"
        --type "$issue_type" --status "Ready"
        --pull-request "$url"
        --contributor "$pr_author"
        --contributor-email "$contributor_email")

    [[ -n "$labels" ]] && create_args+=(--labels "$labels")

    # Ask how to save before creating
    local save_action
    save_action=$(printf "Finalize and commit (assign real task ID and commit)\nSave as draft (keep in aitasks/new/ for later finalization)" | \
        fzf --prompt="How to save? " --height=8 --no-info \
        --header="Finalize claims a real task ID and commits to git")

    [[ -z "$save_action" ]] && save_action="Save as draft"

    if [[ "$save_action" == "Finalize and commit"* ]]; then
        create_args+=(--commit)
    fi

    local result
    result=$(echo "$description" | "$SCRIPT_DIR/aitask_create.sh" "${create_args[@]}")
    local created_file
    created_file="${result#Created: }"

    if [[ "$save_action" == "Finalize and commit"* ]]; then
        success "Finalized and committed: $created_file"
    else
        success "Draft saved: $created_file"
        info "Finalize later with: ait create (interactive) or --batch --finalize <file>"
    fi
}

interactive_specific_pr() {
    local pr_num
    read -rp "Enter PR/MR number: " pr_num < /dev/tty
    [[ -z "$pr_num" ]] && die "No PR number entered"
    [[ "$pr_num" =~ ^[0-9]+$ ]] || die "Invalid PR number: $pr_num"
    interactive_import_pr "$pr_num"
}

interactive_fetch_and_choose() {
    info "Fetching open PRs..."
    local prs_json
    prs_json=$(source_list_prs)

    local pr_count
    pr_count=$(echo "$prs_json" | jq length)
    [[ "$pr_count" -eq 0 ]] && die "No open PRs found"

    local pr_list
    pr_list=$(echo "$prs_json" | jq -r '.[] | "#\(.number) - \(.title) [@\(.author.login)]"')

    local selected
    selected=$(echo "$pr_list" | fzf --multi --prompt="Select PRs: " --height=20 --no-info \
        --header="Tab to select multiple, Enter to confirm" \
        --preview="echo {} | grep -oE '^#[0-9]+' | tr -d '#' | xargs -I{} gh pr view {}" \
        --preview-window=right:50%:wrap)

    [[ -z "$selected" ]] && die "No PRs selected"

    while IFS= read -r line; do
        local num
        num=$(echo "$line" | grep -oE '^#[0-9]+' | tr -d '#')
        [[ -n "$num" ]] && interactive_import_pr "$num"
    done <<< "$selected"
}

interactive_range() {
    local start end
    read -rp "Start PR number: " start < /dev/tty
    read -rp "End PR number: " end < /dev/tty
    [[ -z "$start" || -z "$end" ]] && die "Both start and end are required"
    [[ "$start" =~ ^[0-9]+$ && "$end" =~ ^[0-9]+$ ]] || die "Invalid numbers"
    [[ "$start" -gt "$end" ]] && die "Invalid range: start ($start) > end ($end)"

    info "Importing PRs #$start to #$end..."
    for ((num=start; num<=end; num++)); do
        interactive_import_pr "$num"
    done
}

interactive_all_open() {
    info "Fetching all open PRs..."
    local prs_json
    prs_json=$(source_list_prs)
    local count
    count=$(echo "$prs_json" | jq length)

    [[ "$count" -eq 0 ]] && die "No open PRs found"

    local confirm
    confirm=$(printf "Yes - import %s PRs\nNo - cancel" "$count" | fzf --prompt="Confirm? " --height=8 --no-info)
    [[ "$confirm" == "Yes"* ]] || die "Cancelled"

    echo "$prs_json" | jq -r '.[].number' | sort -n | while IFS= read -r num; do
        [[ -z "$num" ]] && continue
        interactive_import_pr "$num"
    done
}

run_interactive_mode() {
    ait_warn_if_incapable_terminal
    command -v fzf &>/dev/null || die "fzf is required for interactive mode. Install via your package manager."
    source_check_cli

    info "Tip: For AI-enriched PR import with analysis, implementation planning,"
    info "and codebase alignment, use the code agent skill: /aitask-pr-review"
    info "This bash script provides basic metadata import only."
    echo ""

    local mode
    mode=$(printf "Specific PR number\nFetch open PRs and choose\nPR number range\nAll open PRs" | \
        fzf --prompt="Import mode: " --height=10 --no-info --header="Select import mode")

    case "$mode" in
        "Specific PR number") interactive_specific_pr ;;
        "Fetch open PRs and choose") interactive_fetch_and_choose ;;
        "PR number range") interactive_range ;;
        "All open PRs") interactive_all_open ;;
        *) die "No mode selected" ;;
    esac
}

# --- Argument Parsing ---

show_help() {
    cat << 'EOF'
Usage: aitask_pr_import.sh [--batch OPTIONS]

Import GitHub/GitLab/Bitbucket pull requests as AI task files.
Can also generate intermediate data files for Claude Code skills.

Modes:
  Without --batch:  Interactive mode (uses fzf for selection and editing)
  With --batch:     Batch mode (non-interactive, all options via flags)

Interactive mode (no arguments):
  ./aitask_pr_import.sh
  Presents a menu to choose: specific PR, fetch & choose, range, or all.
  Each PR can be previewed, and metadata can be edited before import.

Batch mode required flags (one of):
  --pr NUM               PR/MR number to import
  --range START-END      Import PRs in a number range (e.g., 5-10)
  --all                  Import all open PRs
  --list                 List open PRs (for skill parsing)

Batch mode options:
  --batch                Enable batch mode (required for non-interactive)
  --source, -S PLATFORM  Source platform: github, gitlab, bitbucket (auto-detected)
  --repo OWNER/REPO      GitLab repo override for cross-repo imports
  --data-only            Only write intermediate data file, don't create task
  --priority, -p LEVEL   Override priority: high, medium (default), low
  --effort, -e LEVEL     Override effort: low, medium (default), high
  --type, -t TYPE        Override issue type (default: auto-detect from labels)
  --status, -s STATUS    Override status (default: Ready)
  --labels, -l LABELS    Override labels (default: from PR labels)
  --deps DEPS            Set dependencies (comma-separated task numbers)
  --parent, -P NUM       Create as child of parent task
  --no-sibling-dep       Don't add dependency on previous sibling
  --commit               Auto git commit after creation
  --silent               Output only created filename(s)
  --skip-duplicates      Skip already-imported PRs silently
  --no-comments          Don't include PR comments in output
  --no-diff              Skip diff extraction entirely
  --no-reviews           Skip review comment extraction
  --max-diff-lines N     Truncate diff at N lines (default: 5000)
  --help, -h             Show this help

Examples:
  # Interactive mode
  ./aitask_pr_import.sh

  # Import a single PR (batch)
  ./aitask_pr_import.sh --batch --pr 42

  # Write intermediate data file only
  ./aitask_pr_import.sh --batch --pr 42 --data-only

  # Import all open PRs, skip duplicates
  ./aitask_pr_import.sh --batch --all --skip-duplicates --commit

  # List open PRs for skill parsing
  ./aitask_pr_import.sh --batch --list --silent

  # Import PR without diff (faster)
  ./aitask_pr_import.sh --batch --pr 42 --no-diff --no-reviews
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --batch) BATCH_MODE=true; shift ;;
            --source|-S) SOURCE="$2"; shift 2 ;;
            --repo) REPO_OVERRIDE="$2"; shift 2 ;;
            --pr) BATCH_PR_NUM="$2"; shift 2 ;;
            --range) BATCH_PR_RANGE="$2"; shift 2 ;;
            --all) BATCH_ALL=true; shift ;;
            --list) BATCH_LIST=true; shift ;;
            --data-only) BATCH_DATA_ONLY=true; shift ;;
            --priority|-p) BATCH_PRIORITY="$2"; shift 2 ;;
            --effort|-e) BATCH_EFFORT="$2"; shift 2 ;;
            --type|-t) BATCH_TYPE="$2"; shift 2 ;;
            --status|-s) BATCH_STATUS="$2"; shift 2 ;;
            --labels|-l) BATCH_LABELS="$2"; shift 2 ;;
            --deps) BATCH_DEPS="$2"; shift 2 ;;
            --parent|-P) BATCH_PARENT="$2"; shift 2 ;;
            --no-sibling-dep) BATCH_NO_SIBLING_DEP=true; shift ;;
            --commit) BATCH_COMMIT=true; shift ;;
            --silent) BATCH_SILENT=true; shift ;;
            --skip-duplicates) BATCH_SKIP_DUPLICATES=true; shift ;;
            --no-comments) BATCH_NO_COMMENTS=true; shift ;;
            --no-diff) BATCH_NO_DIFF=true; shift ;;
            --no-reviews) BATCH_NO_REVIEWS=true; shift ;;
            --max-diff-lines) MAX_DIFF_LINES="$2"; shift 2 ;;
            --help|-h) show_help; exit 0 ;;
            *) die "Unknown option: $1. Use --help for usage." ;;
        esac
    done

    # Auto-detect source platform if not explicitly set
    if [[ -z "$SOURCE" ]]; then
        SOURCE=$(detect_platform)
        if [[ -z "$SOURCE" ]]; then
            die "Could not auto-detect source platform from git remote. Use --source github|gitlab|bitbucket"
        fi
    fi

    # Validate source platform
    case "$SOURCE" in
        github) ;;
        gitlab) ;;
        bitbucket) ;;
        *) die "Unknown source platform: $SOURCE (supported: github, gitlab, bitbucket)" ;;
    esac
}

# --- Main ---

main() {
    parse_args "$@"

    if [[ "$BATCH_MODE" == true ]]; then
        run_batch_mode
    else
        run_interactive_mode
    fi
}

main "$@"
