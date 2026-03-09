#!/usr/bin/env bash

# aitask_contribute.sh - Contribute local framework changes to upstream aitasks repo
# Generates structured diffs and creates GitHub/GitLab/Bitbucket issues for contributions
# Batch-only: all user interaction goes through the aitask-contribute skill

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/repo_fetch.sh
source "$SCRIPT_DIR/lib/repo_fetch.sh"

DEFAULT_UPSTREAM_REPO="beyondeye/aitasks"
DEFAULT_DIFF_PREVIEW_LINES=50
VERSION_FILE="$SCRIPT_DIR/VERSION"

# --- Batch mode variables ---
ARG_AREA=""
ARG_AREA_PATH=""
ARG_FILES=""
ARG_TITLE=""
ARG_MOTIVATION=""
ARG_SCOPE="enhancement"
ARG_MERGE_APPROACH=""
ARG_DRY_RUN=false
ARG_SILENT=false
ARG_REPO=""
ARG_DIFF_PREVIEW_LINES=""
ARG_SOURCE=""
ARG_LIST_AREAS=false
ARG_LIST_CHANGES=false
ARG_HELP=false

# --- Platform state (resolved in main) ---
CONTRIBUTE_PLATFORM=""

# --- Area definitions ---
# Format: "name|directories|description"
AREAS=(
    "scripts|.aitask-scripts/|Core scripts (shell and Python)"
    "claude-skills|.claude/skills/|Claude Code skills"
    "gemini|.gemini/skills/,.gemini/commands/|Gemini CLI skills and commands"
    "codex|.agents/skills/|Codex CLI skills"
    "opencode|.opencode/skills/,.opencode/commands/|OpenCode skills and commands"
    "website|website/|Website documentation (clone/fork mode only)"
)

# ============================================================
# PLATFORM BACKENDS
# To add a new platform:
#   1. Implement all <platform>_* functions below
#   2. Add to --source validation in parse_args()
#   3. Add case to each source_* dispatcher function
# ============================================================

# --- GitHub Backend ---

github_check_cli() {
    command -v gh &>/dev/null || die "gh CLI is required for GitHub. Install: https://cli.github.com/"
    gh auth status &>/dev/null || die "gh CLI is not authenticated. Run: gh auth login"
}

github_upstream_url() {
    local repo="$1" filepath="$2"
    echo "https://github.com/$repo/blob/main/$filepath"
}

github_resolve_contributor() {
    if command -v gh &>/dev/null; then
        local gh_output
        gh_output=$(gh api user --jq '.login,.id' 2>/dev/null || echo "")
        if [[ -n "$gh_output" ]]; then
            local login user_id
            login=$(echo "$gh_output" | head -1)
            user_id=$(echo "$gh_output" | tail -1)
            if [[ -n "$login" && -n "$user_id" ]]; then
                echo "$login"
                echo "${user_id}+${login}@users.noreply.github.com"
                return 0
            fi
        fi
    fi
    return 1
}

github_create_issue() {
    local repo="$1" title="$2" body="$3"
    gh issue create -R "$repo" --title "$title" --body "$body" --label "contribution" 2>&1
}

# --- GitLab Backend ---

gitlab_check_cli() {
    command -v glab &>/dev/null || die "glab CLI is required for GitLab. Install: https://gitlab.com/gitlab-org/cli"
    glab auth status &>/dev/null || die "glab CLI is not authenticated. Run: glab auth login"
}

gitlab_upstream_url() {
    local repo="$1" filepath="$2"
    echo "https://gitlab.com/$repo/-/blob/main/$filepath"
}

gitlab_resolve_contributor() {
    if command -v glab &>/dev/null; then
        local glab_output
        glab_output=$(glab api user --jq '.username,.id' 2>/dev/null || echo "")
        if [[ -n "$glab_output" ]]; then
            local username user_id
            username=$(echo "$glab_output" | head -1)
            user_id=$(echo "$glab_output" | tail -1)
            if [[ -n "$username" && -n "$user_id" ]]; then
                echo "$username"
                echo "${username}@users.noreply.gitlab.com"
                return 0
            fi
        fi
    fi
    return 1
}

gitlab_create_issue() {
    local repo="$1" title="$2" body="$3"
    glab issue create -R "$repo" --title "$title" --description "$body" -l "contribution" 2>&1
}

# --- Bitbucket Backend ---

bitbucket_check_cli() {
    command -v bkt &>/dev/null || die "bkt CLI is required for Bitbucket. Install: https://github.com/avivsinai/bitbucket-cli"
    bkt auth status &>/dev/null || die "bkt CLI is not authenticated. Run: bkt auth login https://bitbucket.org --kind cloud --web"
}

bitbucket_upstream_url() {
    local repo="$1" filepath="$2"
    echo "https://bitbucket.org/$repo/src/main/$filepath"
}

bitbucket_resolve_contributor() {
    # Bitbucket has no simple user API via bkt — always fall back
    return 1
}

bitbucket_create_issue() {
    local repo="$1" title="$2" body="$3"
    bkt issue create --title "$title" --body "$body" 2>&1
}

# --- Dispatcher Functions ---

source_check_cli() {
    case "$CONTRIBUTE_PLATFORM" in
        github) github_check_cli ;;
        gitlab) gitlab_check_cli ;;
        bitbucket) bitbucket_check_cli ;;
        *) die "Unknown platform: $CONTRIBUTE_PLATFORM" ;;
    esac
}

source_upstream_url() {
    local repo="$1" filepath="$2"
    case "$CONTRIBUTE_PLATFORM" in
        github) github_upstream_url "$repo" "$filepath" ;;
        gitlab) gitlab_upstream_url "$repo" "$filepath" ;;
        bitbucket) bitbucket_upstream_url "$repo" "$filepath" ;;
        *) die "Unknown platform: $CONTRIBUTE_PLATFORM" ;;
    esac
}

source_resolve_contributor() {
    case "$CONTRIBUTE_PLATFORM" in
        github) github_resolve_contributor ;;
        gitlab) gitlab_resolve_contributor ;;
        bitbucket) bitbucket_resolve_contributor ;;
        *) return 1 ;;
    esac
}

source_create_issue() {
    local repo="$1" title="$2" body="$3"
    case "$CONTRIBUTE_PLATFORM" in
        github) github_create_issue "$repo" "$title" "$body" ;;
        gitlab) gitlab_create_issue "$repo" "$title" "$body" ;;
        bitbucket) bitbucket_create_issue "$repo" "$title" "$body" ;;
        *) die "Unknown platform: $CONTRIBUTE_PLATFORM" ;;
    esac
}

# ============================================================
# CORE FUNCTIONS
# ============================================================

detect_contribute_mode() {
    local remote_url
    remote_url=$(git remote get-url origin 2>/dev/null || echo "")
    if [[ "$remote_url" == *"beyondeye/aitasks"* ]]; then
        echo "clone"
    else
        echo "downstream"
    fi
}

resolve_area_dirs() {
    local area_name="$1"
    local mode
    mode=$(detect_contribute_mode)

    for entry in "${AREAS[@]}"; do
        local name dirs
        name="${entry%%|*}"
        local rest="${entry#*|}"
        dirs="${rest%%|*}"

        if [[ "$name" == "$area_name" ]]; then
            if [[ "$name" == "website" && "$mode" == "downstream" ]]; then
                die "Area 'website' is only available in clone/fork mode"
            fi
            echo "$dirs"
            return 0
        fi
    done

    die "Unknown area: $area_name"
}

list_areas() {
    local mode
    mode=$(detect_contribute_mode)
    echo "MODE:$mode"

    for entry in "${AREAS[@]}"; do
        local name dirs desc
        name="${entry%%|*}"
        local rest="${entry#*|}"
        dirs="${rest%%|*}"
        desc="${rest#*|}"

        # Filter out website for downstream mode
        if [[ "$name" == "website" && "$mode" == "downstream" ]]; then
            continue
        fi

        echo "AREA|$name|$dirs|$desc"
    done
}

# Fetch upstream file content — uses AITASK_CONTRIBUTE_UPSTREAM_DIR for testing
fetch_upstream_file() {
    local filepath="$1"
    local repo="${ARG_REPO:-$DEFAULT_UPSTREAM_REPO}"

    if [[ -n "${AITASK_CONTRIBUTE_UPSTREAM_DIR:-}" ]]; then
        # Test mode: read from local upstream directory
        if [[ -f "$AITASK_CONTRIBUTE_UPSTREAM_DIR/$filepath" ]]; then
            cat "$AITASK_CONTRIBUTE_UPSTREAM_DIR/$filepath"
        fi
        return 0
    fi

    # Production mode: fetch via repo_fetch_file with platform-aware URL
    local url
    url=$(source_upstream_url "$repo" "$filepath")
    repo_fetch_file "$url" 2>/dev/null || true
}

list_changed_files() {
    local area_dirs="$1"
    local mode
    mode=$(detect_contribute_mode)

    IFS=',' read -ra dirs <<< "$area_dirs"

    if [[ "$mode" == "clone" ]]; then
        # Clone mode: use git diff against main
        git diff --name-only main -- "${dirs[@]}" 2>/dev/null || true
    else
        # Downstream mode: compare local files against upstream
        for dir in "${dirs[@]}"; do
            dir="${dir%/}"
            if [[ ! -d "$dir" ]]; then
                continue
            fi
            while IFS= read -r -d '' filepath; do
                local upstream_content
                upstream_content=$(fetch_upstream_file "$filepath")
                if [[ -z "$upstream_content" ]]; then
                    # File doesn't exist upstream — it's new
                    echo "$filepath"
                elif ! diff -q <(echo "$upstream_content") "$filepath" >/dev/null 2>&1; then
                    # File differs from upstream
                    echo "$filepath"
                fi
            done < <(find "$dir" -type f -print0 2>/dev/null | sort -z)
        done
    fi
}

generate_diff() {
    local files="$1"
    local mode
    mode=$(detect_contribute_mode)

    IFS=',' read -ra file_list <<< "$files"

    if [[ "$mode" == "clone" ]]; then
        git diff main -- "${file_list[@]}" 2>/dev/null || true
    else
        for filepath in "${file_list[@]}"; do
            filepath="$(echo "$filepath" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
            if [[ ! -f "$filepath" ]]; then
                warn "File not found: $filepath"
                continue
            fi
            local upstream_content
            upstream_content=$(fetch_upstream_file "$filepath")
            echo "diff --git a/$filepath b/$filepath"
            if [[ -z "$upstream_content" ]]; then
                # New file — show full content as addition
                echo "--- /dev/null"
                echo "+++ b/$filepath"
                local line_count
                line_count=$(wc -l < "$filepath" | tr -d ' ')
                echo "@@ -0,0 +1,$line_count @@"
                sed 's/^/+/' "$filepath"
            else
                diff -u <(echo "$upstream_content") "$filepath" 2>/dev/null | \
                    sed "1s|^--- .*|--- a/$filepath|" | \
                    sed "2s|^+++ .*|+++ b/$filepath|" || true
            fi
        done
    fi
}

resolve_contributor() {
    # Try platform-specific resolution first
    if source_resolve_contributor; then
        return 0
    fi

    # Fallback to git config (works for all platforms)
    local username user_email
    username=$(git config user.name 2>/dev/null || echo "unknown")
    user_email=$(git config user.email 2>/dev/null || echo "")
    echo "$username"
    echo "$user_email"
}

build_issue_body() {
    local title="$1"
    local motivation="$2"
    local scope="$3"
    local merge_approach="$4"
    local files="$5"
    local diff_output="$6"
    local contributor="$7"
    local contributor_email="$8"
    local preview_lines="${ARG_DIFF_PREVIEW_LINES:-$DEFAULT_DIFF_PREVIEW_LINES}"

    local version=""
    if [[ -f "$VERSION_FILE" ]]; then
        version=$(cat "$VERSION_FILE")
    fi

    # Header
    cat <<EOF
## Contribution: $title

### Scope
$scope

### Motivation
$motivation

### Proposed Merge Approach
${merge_approach:-Clean merge}

### Framework Version
${version:-unknown}

### Changed Files
EOF

    # File list as table
    echo ""
    echo "| File | Status |"
    echo "|------|--------|"
    IFS=',' read -ra file_list <<< "$files"
    for filepath in "${file_list[@]}"; do
        filepath="$(echo "$filepath" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        echo "| \`$filepath\` | Modified |"
    done
    echo ""

    # Code changes with per-file diff handling
    echo "### Code Changes"
    echo ""

    # Split diff by file using "diff --git" boundaries
    local current_file="" current_diff="" in_diff=false
    while IFS= read -r line; do
        if [[ "$line" == "diff --git "* ]]; then
            # Output previous file's diff if any
            if [[ -n "$current_file" && -n "$current_diff" ]]; then
                _output_file_diff "$current_file" "$current_diff" "$preview_lines"
            fi
            # Extract filename from "diff --git a/path b/path" or "diff --git c/path w/path"
            # The second path is the destination file
            current_file="${line##* }"
            # Strip any single-char prefix (a/, b/, c/, w/, etc.)
            current_file="${current_file#[a-z]/}"
            current_diff=""
            in_diff=true
        elif [[ "$line" == "--- "* && "$in_diff" == true ]]; then
            # Start of actual diff content (skip index line)
            current_diff="$line"
        elif [[ -n "$current_diff" && "$in_diff" == true ]]; then
            current_diff="$current_diff"$'\n'"$line"
        fi
    done <<< "$diff_output"

    # Output last file's diff
    if [[ -n "$current_file" && -n "$current_diff" ]]; then
        _output_file_diff "$current_file" "$current_diff" "$preview_lines"
    fi

    # Contributor metadata as HTML comment
    echo ""
    echo "<!-- aitask-contribute-metadata"
    echo "contributor: $contributor"
    echo "contributor_email: $contributor_email"
    echo "based_on_version: ${version:-unknown}"
    echo "-->"
}

_output_file_diff() {
    local file="$1"
    local diff_content="$2"
    local max_lines="$3"

    local line_count
    line_count=$(echo "$diff_content" | wc -l | tr -d ' ')

    if [[ "$line_count" -le "$max_lines" ]]; then
        # Small diff: show inline
        echo "#### \`$file\`"
        echo ""
        echo '```diff'
        echo "$diff_content"
        echo '```'
        echo ""
    else
        # Large diff: preview + full in HTML comment
        echo "#### \`$file\`"
        echo ""
        echo "*Preview — full diff available in raw view of this issue*"
        echo ""
        echo '```diff'
        echo "$diff_content" | head -n "$max_lines"
        echo '```'
        echo ""
        echo "<!-- full-diff:$file"
        echo '```diff'
        echo "$diff_content"
        echo '```'
        echo "-->"
        echo ""
    fi
}

create_issue() {
    local title="$1"
    local body="$2"
    local repo="${ARG_REPO:-$DEFAULT_UPSTREAM_REPO}"

    local result
    result=$(source_create_issue "$repo" "$title" "$body")
    echo "$result"
}

# ============================================================
# ARGUMENT PARSING
# ============================================================

show_help() {
    cat <<'HELP'
Usage: aitask_contribute.sh [OPTIONS]

Contribute local framework changes to the upstream aitasks repository
by generating structured diffs and creating GitHub/GitLab/Bitbucket issues.

Modes:
  --list-areas              List available contribution areas
  --list-changes --area X   List changed files in area X
  --dry-run                 Generate issue body without creating issue

Options:
  --area <name>             Contribution area (scripts, claude-skills, gemini, codex, opencode, website)
  --area-path <path>        Custom area path (alternative to --area)
  --files <f1,f2,...>       Specific files to include (comma-separated)
  --title <text>            Contribution title (required for issue creation)
  --motivation <text>       Motivation text
  --scope <type>            Scope: bug_fix|enhancement|new_feature|documentation|other
  --merge-approach <text>   Proposed merge approach
  --source <platform>       Target platform: github (default), gitlab, bitbucket
  --dry-run                 Output issue body to stdout, don't create issue
  --silent                  Output only the issue URL
  --repo <owner/repo>       Override upstream repo (default: beyondeye/aitasks)
  --diff-preview-lines <N>  Lines shown in rendered preview per file (default: 50)
  --help                    Show this help

Platform CLI requirements:
  github    gh CLI   (https://cli.github.com/)
  gitlab    glab CLI (https://gitlab.com/gitlab-org/cli)
  bitbucket bkt CLI  (https://github.com/avivsinai/bitbucket-cli)

Examples:
  # List areas
  aitask_contribute.sh --list-areas

  # List changed scripts
  aitask_contribute.sh --list-changes --area scripts

  # Dry run for specific files
  aitask_contribute.sh --dry-run --area scripts \
    --files ".aitask-scripts/aitask_ls.sh" \
    --title "Improve sorting" --motivation "Better UX" \
    --scope enhancement --merge-approach "clean merge"

  # Create issue on GitHub (default)
  aitask_contribute.sh --area scripts \
    --files ".aitask-scripts/aitask_ls.sh" \
    --title "Improve sorting" --motivation "Better UX" \
    --scope enhancement --merge-approach "clean merge"

  # Create issue on GitLab
  aitask_contribute.sh --source gitlab --repo group/project \
    --area scripts --files ".aitask-scripts/aitask_ls.sh" \
    --title "Improve sorting" --motivation "Better UX"
HELP
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --area) ARG_AREA="$2"; shift 2 ;;
            --area-path) ARG_AREA_PATH="$2"; shift 2 ;;
            --files) ARG_FILES="$2"; shift 2 ;;
            --title) ARG_TITLE="$2"; shift 2 ;;
            --motivation) ARG_MOTIVATION="$2"; shift 2 ;;
            --scope) ARG_SCOPE="$2"; shift 2 ;;
            --merge-approach) ARG_MERGE_APPROACH="$2"; shift 2 ;;
            --dry-run) ARG_DRY_RUN=true; shift ;;
            --silent) ARG_SILENT=true; shift ;;
            --source|-S) ARG_SOURCE="$2"; shift 2 ;;
            --repo) ARG_REPO="$2"; shift 2 ;;
            --diff-preview-lines) ARG_DIFF_PREVIEW_LINES="$2"; shift 2 ;;
            --list-areas) ARG_LIST_AREAS=true; shift ;;
            --list-changes) ARG_LIST_CHANGES=true; shift ;;
            --help|-h) ARG_HELP=true; shift ;;
            *) die "Unknown argument: $1" ;;
        esac
    done

    # Validate source platform if specified
    if [[ -n "$ARG_SOURCE" ]]; then
        case "$ARG_SOURCE" in
            github|gitlab|bitbucket) ;;
            *) die "Unknown source platform: $ARG_SOURCE (supported: github, gitlab, bitbucket)" ;;
        esac
    fi
}

# ============================================================
# MAIN
# ============================================================

main() {
    parse_args "$@"

    if [[ "$ARG_HELP" == true ]]; then
        show_help
        exit 0
    fi

    if [[ "$ARG_LIST_AREAS" == true ]]; then
        list_areas
        exit 0
    fi

    if [[ "$ARG_LIST_CHANGES" == true ]]; then
        if [[ -z "$ARG_AREA" && -z "$ARG_AREA_PATH" ]]; then
            die "--list-changes requires --area or --area-path"
        fi
        local area_dirs
        if [[ -n "$ARG_AREA_PATH" ]]; then
            area_dirs="$ARG_AREA_PATH"
        else
            area_dirs=$(resolve_area_dirs "$ARG_AREA")
        fi
        list_changed_files "$area_dirs"
        exit 0
    fi

    # Full contribution flow
    if [[ -z "$ARG_FILES" ]]; then
        die "--files is required for contribution"
    fi
    if [[ -z "$ARG_TITLE" ]]; then
        die "--title is required for contribution"
    fi

    # Resolve target platform
    if [[ -n "$ARG_SOURCE" ]]; then
        CONTRIBUTE_PLATFORM="$ARG_SOURCE"
    else
        CONTRIBUTE_PLATFORM="github"  # Default: upstream beyondeye/aitasks is on GitHub
    fi

    # Resolve contributor
    local contributor_info contributor contributor_email
    contributor_info=$(resolve_contributor)
    contributor=$(echo "$contributor_info" | head -1)
    contributor_email=$(echo "$contributor_info" | tail -1)

    # Generate diff
    local diff_output
    diff_output=$(generate_diff "$ARG_FILES")

    if [[ -z "$diff_output" ]]; then
        die "No differences found for specified files"
    fi

    # Build issue body
    local issue_body
    issue_body=$(build_issue_body \
        "$ARG_TITLE" \
        "${ARG_MOTIVATION:-No motivation provided}" \
        "$ARG_SCOPE" \
        "${ARG_MERGE_APPROACH:-Clean merge}" \
        "$ARG_FILES" \
        "$diff_output" \
        "$contributor" \
        "$contributor_email")

    if [[ "$ARG_DRY_RUN" == true ]]; then
        echo "$issue_body"
        exit 0
    fi

    # Check platform CLI before creating issue
    source_check_cli

    local issue_url
    issue_url=$(create_issue "[Contribution] $ARG_TITLE" "$issue_body")

    if [[ "$ARG_SILENT" == true ]]; then
        echo "$issue_url"
    else
        info "Issue created: $issue_url"
        info "Contributor: $contributor ($contributor_email)"
        info "When this issue is imported via /aitask-issue-import, your Co-authored-by attribution will be preserved."
    fi
}

main "$@"
