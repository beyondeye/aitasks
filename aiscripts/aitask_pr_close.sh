#!/usr/bin/env bash

# aitask_pr_close.sh - Close/decline GitHub/GitLab/Bitbucket PRs linked to AI tasks
# Posts implementation notes and commit references as PR comments
# Optionally closes/declines the PR
#
# Follows the same architecture as aitask_issue_update.sh but for pull requests.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

# Command options
SOURCE=""  # Auto-detected from PR URL or git remote if not set via --source
TASK_NUM=""
COMMITS_OVERRIDE=""
CLOSE_PR=false
NO_COMMENT=false
DRY_RUN=false
PR_URL_OVERRIDE=""
GITLAB_REPO_SLUG=""  # Extracted from GitLab URL for cross-repo -R flag

# --- Helper Functions ---

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

# Extract PR number from full GitHub URL
# Input: "https://github.com/owner/repo/pull/42"
# Output: "42"
github_extract_pr_number() {
    local url="$1"
    echo "$url" | grep -oE '[0-9]+$'
}

# Get current PR state
# Input: PR number
# Output: "OPEN", "CLOSED", or "MERGED"
github_get_pr_status() {
    local pr_num="$1"
    gh pr view "$pr_num" --json state -q '.state'
}

# Post a comment on a PR
# Input: PR number, comment body
github_add_comment() {
    local pr_num="$1"
    local body="$2"
    gh pr comment "$pr_num" --body "$body"
}

# Close a PR with optional comment
# Input: PR number, optional comment body
github_close_pr() {
    local pr_num="$1"
    local comment="$2"
    if [[ -n "$comment" ]]; then
        gh pr close "$pr_num" --comment "$comment"
    else
        gh pr close "$pr_num"
    fi
}

# --- GitLab Backend ---

gitlab_check_cli() {
    command -v glab &>/dev/null || die "glab CLI is required for GitLab. Install: https://gitlab.com/gitlab-org/cli"
    glab auth status &>/dev/null || die "glab CLI is not authenticated. Run: glab auth login"
}

# Extract MR number from full GitLab URL
# Input: "https://gitlab.com/group/project/-/merge_requests/42"
# Output: "42"
gitlab_extract_pr_number() {
    local url="$1"
    echo "$url" | grep -oE '[0-9]+$'
}

# Extract "group/project" from GitLab MR URL for -R flag
gitlab_extract_repo_from_url() {
    local url="$1"
    echo "$url" | sed 's|https://gitlab.com/||; s|/-/merge_requests/.*||'
}

# Get -R flag for glab mr commands (empty if no repo slug set)
glab_repo_flag() {
    if [[ -n "$GITLAB_REPO_SLUG" ]]; then
        echo "-R $GITLAB_REPO_SLUG"
    fi
}

# Get current MR state (normalized to OPEN/CLOSED/MERGED)
gitlab_get_pr_status() {
    local mr_num="$1"
    local state
    state=$(glab mr view "$mr_num" $(glab_repo_flag) -F json | jq -r '.state')
    case "$state" in
        opened) echo "OPEN" ;;
        closed) echo "CLOSED" ;;
        merged) echo "MERGED" ;;
        *) echo "$state" ;;
    esac
}

# Post a note on a merge request
gitlab_add_comment() {
    local mr_num="$1"
    local body="$2"
    glab mr note "$mr_num" $(glab_repo_flag) -m "$body"
}

# Close a MR with optional comment
# Note: glab mr close doesn't support --comment, so we post note first
gitlab_close_pr() {
    local mr_num="$1"
    local comment="$2"
    if [[ -n "$comment" ]]; then
        glab mr note "$mr_num" $(glab_repo_flag) -m "$comment"
    fi
    glab mr close "$mr_num" $(glab_repo_flag)
}

# --- Bitbucket Backend ---

bitbucket_check_cli() {
    command -v bkt &>/dev/null || die "bkt CLI is required for Bitbucket. Install: https://github.com/avivsinai/bitbucket-cli"
    bkt auth status &>/dev/null || die "bkt CLI is not authenticated. Run: bkt auth login https://bitbucket.org --kind cloud --web"
}

# Extract workspace/repo from Bitbucket PR URL
# Input: "https://bitbucket.org/workspace/repo/pull-requests/42"
# Sets: BKT_WORKSPACE, BKT_REPO
BKT_WORKSPACE=""
BKT_REPO=""
bitbucket_extract_repo_from_url() {
    local url="$1"
    # Pattern: https://bitbucket.org/<workspace>/<repo>/pull-requests/<num>
    BKT_WORKSPACE=$(echo "$url" | sed -E 's|https?://bitbucket\.org/([^/]+)/([^/]+)/.*|\1|')
    BKT_REPO=$(echo "$url" | sed -E 's|https?://bitbucket\.org/([^/]+)/([^/]+)/.*|\2|')
}

# Extract PR number from full Bitbucket URL
# Input: "https://bitbucket.org/workspace/repo/pull-requests/42"
# Output: "42"
bitbucket_extract_pr_number() {
    local url="$1"
    echo "$url" | grep -oE '/pull-requests/[0-9]+' | grep -oE '[0-9]+'
}

# Get current PR state (normalized)
# Bitbucket states: OPEN, MERGED, DECLINED, SUPERSEDED
bitbucket_get_pr_status() {
    local pr_num="$1"
    local state
    # bkt pr view --json wraps data in .pull_request
    state=$(bkt pr view "$pr_num" --workspace "$BKT_WORKSPACE" --repo "$BKT_REPO" --json | jq -r '(.pull_request // .).state')
    case "$state" in
        OPEN) echo "OPEN" ;;
        MERGED) echo "MERGED" ;;
        DECLINED|SUPERSEDED) echo "CLOSED" ;;
        *) echo "OPEN" ;;
    esac
}

# Post a comment on a PR via API (bkt pr comment only supports Data Center)
bitbucket_add_comment() {
    local pr_num="$1"
    local body="$2"
    bkt api --method POST "/repositories/${BKT_WORKSPACE}/${BKT_REPO}/pullrequests/${pr_num}/comments" \
        --input "$(jq -nc --arg body "$body" '{"content":{"raw":$body}}')" >/dev/null
}

# Decline a PR with optional comment
# Uses API for comments (Cloud support), bkt pr decline for the decline action
bitbucket_close_pr() {
    local pr_num="$1"
    local comment="$2"
    if [[ -n "$comment" ]]; then
        bitbucket_add_comment "$pr_num" "$comment"
    fi
    bkt pr decline "$pr_num" --workspace "$BKT_WORKSPACE" --repo "$BKT_REPO"
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

source_extract_pr_number() {
    local url="$1"
    case "$SOURCE" in
        github) github_extract_pr_number "$url" ;;
        gitlab) gitlab_extract_pr_number "$url" ;;
        bitbucket) bitbucket_extract_pr_number "$url" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_get_pr_status() {
    local pr_num="$1"
    case "$SOURCE" in
        github) github_get_pr_status "$pr_num" ;;
        gitlab) gitlab_get_pr_status "$pr_num" ;;
        bitbucket) bitbucket_get_pr_status "$pr_num" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_add_comment() {
    local pr_num="$1"
    local body="$2"
    case "$SOURCE" in
        github) github_add_comment "$pr_num" "$body" ;;
        gitlab) gitlab_add_comment "$pr_num" "$body" ;;
        bitbucket) bitbucket_add_comment "$pr_num" "$body" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_close_pr() {
    local pr_num="$1"
    local comment="$2"
    case "$SOURCE" in
        github) github_close_pr "$pr_num" "$comment" ;;
        gitlab) gitlab_close_pr "$pr_num" "$comment" ;;
        bitbucket) bitbucket_close_pr "$pr_num" "$comment" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

# --- Core Logic ---

# Detect commits associated with a task from git history
# Input: task_id (e.g., "53_6" or "53")
# Output: commit list (one per line: "hash message")
detect_commits() {
    local task_id="$1"

    if [[ -n "$COMMITS_OVERRIDE" ]]; then
        # Handle comma-separated list of hashes
        if [[ "$COMMITS_OVERRIDE" == *","* ]]; then
            local IFS=','
            for hash in $COMMITS_OVERRIDE; do
                hash=$(echo "$hash" | xargs)
                git log --oneline -1 "$hash" 2>/dev/null || warn "Commit not found: $hash"
            done
        elif [[ "$COMMITS_OVERRIDE" == *".."* ]]; then
            # Handle range
            git log --oneline "$COMMITS_OVERRIDE" 2>/dev/null || warn "Invalid commit range: $COMMITS_OVERRIDE"
        else
            # Single commit
            git log --oneline -1 "$COMMITS_OVERRIDE" 2>/dev/null || warn "Commit not found: $COMMITS_OVERRIDE"
        fi
        return
    fi

    # Auto-detect: search git log for "(t<task_id>)" in commit messages
    local search_pattern="(t${task_id})"
    git log --oneline --all --grep="$search_pattern" 2>/dev/null || true
}

# Build the comment body for posting to the PR
# Input: task_id, plan_file_path (may be empty), commits_text (may be empty), contributor (may be empty)
# Output: formatted comment body
build_comment_body() {
    local task_id="$1"
    local plan_path="$2"
    local commits_text="$3"
    local contributor="$4"

    local body="## Resolved via aitask t${task_id}"
    body="${body}"$'\n'
    body="${body}"$'\n'"This pull request was reviewed through the aitask workflow. While the PR was not merged directly, the ideas and approach were incorporated into the implementation."$'\n'

    # Plan file reference
    if [[ -n "$plan_path" && -f "$plan_path" ]]; then
        body="${body}"$'\n'"**Full implementation details:** \`${plan_path}\`"$'\n'

        # Final Implementation Notes
        local notes
        notes=$(extract_final_implementation_notes "$plan_path")

        if [[ -n "$notes" ]]; then
            body="${body}"$'\n'"### Implementation Notes"$'\n'
            body="${body}"$'\n'"${notes}"$'\n'
        fi
    fi

    # Associated commits
    if [[ -n "$commits_text" ]]; then
        body="${body}"$'\n'"### Associated Commits"$'\n'
        body="${body}"$'\n'"\`\`\`"
        body="${body}"$'\n'"${commits_text}"
        body="${body}"$'\n'"\`\`\`"$'\n'
    fi

    # Contributor attribution
    if [[ -n "$contributor" ]]; then
        body="${body}"$'\n'"Thank you for your contribution, @${contributor}!"$'\n'
    fi

    echo "$body"
}

# Main execution function
run_close() {
    # Step 1: Get PR URL (from override or task file)
    local pr_url
    if [[ -n "$PR_URL_OVERRIDE" ]]; then
        pr_url="$PR_URL_OVERRIDE"
        info "PR URL (override): $pr_url"
    else
        local task_file
        task_file=$(resolve_task_file "$TASK_NUM")
        info "Task file: $task_file"

        pr_url=$(extract_pr_url "$task_file")
        if [[ -z "$pr_url" ]]; then
            die "Task t${TASK_NUM} has no 'pull_request' field in its frontmatter"
        fi
        info "PR URL: $pr_url"
    fi

    # Step 2: Auto-detect source platform from PR URL if not explicitly set
    if [[ -z "$SOURCE" ]]; then
        SOURCE=$(detect_platform_from_url "$pr_url")
        if [[ -z "$SOURCE" ]]; then
            SOURCE=$(detect_platform)
        fi
        if [[ -z "$SOURCE" ]]; then
            die "Could not auto-detect source platform. Use --source github|gitlab|bitbucket"
        fi
    fi

    # Extract repo slug for GitLab cross-repo support
    if [[ "$SOURCE" == "gitlab" ]]; then
        GITLAB_REPO_SLUG=$(gitlab_extract_repo_from_url "$pr_url")
    fi

    # Extract workspace/repo for Bitbucket API calls
    if [[ "$SOURCE" == "bitbucket" ]]; then
        bitbucket_extract_repo_from_url "$pr_url"
    fi

    source_check_cli

    # Step 3: Extract PR number from URL
    local pr_number
    pr_number=$(source_extract_pr_number "$pr_url")

    if [[ -z "$pr_number" ]]; then
        die "Could not extract PR number from URL: $pr_url"
    fi
    info "PR number: #$pr_number"

    # Step 4: Resolve plan file (optional)
    local plan_file
    plan_file=$(resolve_plan_file "$TASK_NUM")

    if [[ -n "$plan_file" ]]; then
        info "Plan file: $plan_file"
    else
        warn "No plan file found for task t${TASK_NUM}"
    fi

    # Step 5: Detect commits
    local commits_text
    commits_text=$(detect_commits "$TASK_NUM")

    if [[ -n "$commits_text" ]]; then
        local commit_count
        commit_count=$(echo "$commits_text" | wc -l)
        info "Found $commit_count associated commit(s)"
    else
        warn "No associated commits found"
    fi

    # Step 6: Get contributor (for comment attribution)
    local contributor=""
    if [[ -z "$PR_URL_OVERRIDE" ]]; then
        local task_file
        task_file=$(resolve_task_file "$TASK_NUM")
        contributor=$(extract_contributor "$task_file")
    fi

    # Step 7: Build comment body (unless --no-comment)
    local comment_body=""
    if [[ "$NO_COMMENT" != true ]]; then
        comment_body=$(build_comment_body "$TASK_NUM" "$plan_file" "$commits_text" "$contributor")
    fi

    # Step 8: Dry run output
    if [[ "$DRY_RUN" == true ]]; then
        echo ""
        echo -e "${YELLOW}=== DRY RUN ===${NC}"
        echo ""
        if [[ -n "$comment_body" ]]; then
            echo -e "${BLUE}Comment to post:${NC}"
            echo "---"
            echo "$comment_body"
            echo "---"
        fi
        if [[ "$CLOSE_PR" == true ]]; then
            echo -e "${BLUE}Action: Close/decline PR #$pr_number${NC}"
        else
            echo -e "${BLUE}Action: Post comment only (PR remains open)${NC}"
        fi
        return 0
    fi

    # Step 9: Execute
    if [[ "$CLOSE_PR" == true ]]; then
        if [[ "$NO_COMMENT" == true ]]; then
            info "Closing/declining PR #$pr_number without comment..."
            source_close_pr "$pr_number" ""
        else
            info "Closing/declining PR #$pr_number with comment..."
            source_close_pr "$pr_number" "$comment_body"
        fi
        success "PR #$pr_number closed/declined."
    else
        if [[ "$NO_COMMENT" == true ]]; then
            die "Nothing to do: --no-comment without --close has no effect"
        fi
        info "Posting comment on PR #$pr_number..."
        source_add_comment "$pr_number" "$comment_body"
        success "Comment posted on PR #$pr_number."
    fi
}

# --- Argument Parsing ---

show_help() {
    cat << 'EOF'
Usage: aitask_pr_close.sh [OPTIONS] TASK_NUM

Close/decline a GitHub/GitLab/Bitbucket pull request linked to an AI task
with implementation notes and commits.

Required:
  TASK_NUM                Task number (e.g., 53 or 53_6 for child task)

Options:
  --source, -S PLATFORM   Source platform: github, gitlab, bitbucket (auto-detected from PR URL)
  --pr-url URL            Provide PR URL directly (skip task file lookup)
                          Useful when the task file has been deleted (e.g., folded tasks)
  --commits RANGE         Override auto-detected commits
                          Formats: "abc123,def456" or "abc123..def456" or "abc123"
  --close                 Close/decline the PR after posting the comment
  --no-comment            Close/decline without posting a comment (requires --close)
  --dry-run               Show what would be done without doing it
  --help, -h              Show help

The script reads the task's 'pull_request' metadata field to find the PR URL.
The source platform is auto-detected from the PR URL (github.com → GitHub,
gitlab.com → GitLab, bitbucket.org → Bitbucket). Use --source to override.
Commits are auto-detected from git history by searching for the task ID in
commit messages. Use --commits to override.

The comment includes:
  - Header with task reference
  - Note about the PR being reviewed through the aitask workflow
  - Link to the archived plan file (full implementation details)
  - "Final Implementation Notes" from the plan file
  - List of associated commits
  - Contributor attribution (if contributor metadata is set)

Examples:
  # Post implementation notes as a comment
  ./aitask_pr_close.sh 83

  # Close/decline the PR with implementation notes
  ./aitask_pr_close.sh --close 53_1

  # Override commit detection
  ./aitask_pr_close.sh --commits "abc123,def456" 83

  # Dry run to preview the comment
  ./aitask_pr_close.sh --dry-run 53_6

  # Close/decline without a comment
  ./aitask_pr_close.sh --close --no-comment 83

  # Close a folded task's PR using the primary task for context
  ./aitask_pr_close.sh --pr-url "https://github.com/owner/repo/pull/42" --close 106
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --source|-S) SOURCE="$2"; shift 2 ;;
            --commits) COMMITS_OVERRIDE="$2"; shift 2 ;;
            --pr-url) PR_URL_OVERRIDE="$2"; shift 2 ;;
            --close) CLOSE_PR=true; shift ;;
            --no-comment) NO_COMMENT=true; shift ;;
            --dry-run) DRY_RUN=true; shift ;;
            --help|-h) show_help; exit 0 ;;
            -*)
                die "Unknown option: $1. Use --help for usage."
                ;;
            *)
                # Positional argument - task number
                if [[ "$1" =~ ^t?[0-9]+(_[0-9]+)?$ ]]; then
                    TASK_NUM="${1#t}"  # Remove leading 't' if present
                    shift
                else
                    die "Invalid task number: $1 (use format: 53, 53_6, or t53_6)"
                fi
                ;;
        esac
    done

    # Validate required argument
    if [[ -z "$TASK_NUM" ]]; then
        die "Task number is required. Use --help for usage."
    fi

    # Validate source platform (empty means auto-detect later in run_close)
    if [[ -n "$SOURCE" ]]; then
        case "$SOURCE" in
            github) ;;
            gitlab) ;;
            bitbucket) ;;
            *) die "Unknown source platform: $SOURCE (supported: github, gitlab, bitbucket)" ;;
        esac
    fi

    # Validate --no-comment requires --close
    if [[ "$NO_COMMENT" == true && "$CLOSE_PR" != true ]]; then
        die "--no-comment requires --close (nothing to do otherwise)"
    fi
}

# --- Main ---

main() {
    parse_args "$@"
    run_close
}

main "$@"
