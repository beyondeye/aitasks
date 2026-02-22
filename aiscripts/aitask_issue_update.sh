#!/usr/bin/env bash

# aitask_issue_update.sh - Update GitHub/GitLab/Bitbucket issues linked to AI tasks
# Posts implementation notes and commit references as issue comments
# Optionally closes the issue

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

# Command options
SOURCE=""  # Auto-detected from issue URL or git remote if not set via --source
TASK_NUM=""
COMMITS_OVERRIDE=""
CLOSE_ISSUE=false
NO_COMMENT=false
DRY_RUN=false
ISSUE_URL_OVERRIDE=""

# --- Helper Functions ---

# ============================================================
# PLATFORM BACKENDS
# To add a new platform (e.g., GitLab):
#   1. Implement all <platform>_* functions below
#   2. Add to --source validation in parse_args()
#   3. Add case to each source_* dispatcher function
# ============================================================

# --- GitHub Backend ---
# PLATFORM-EXTENSION-POINT: Add new platform backend functions here

github_check_cli() {
    command -v gh &>/dev/null || die "gh CLI is required for GitHub. Install: https://cli.github.com/"
    gh auth status &>/dev/null || die "gh CLI is not authenticated. Run: gh auth login"
}

# Extract issue number from full GitHub URL
# Input: "https://github.com/owner/repo/issues/123"
# Output: "123"
github_extract_issue_number() {
    local url="$1"
    echo "$url" | grep -oE '[0-9]+$'
}

# Get current issue state
# Input: issue number
# Output: "OPEN" or "CLOSED"
github_get_issue_status() {
    local issue_num="$1"
    gh issue view "$issue_num" --json state -q '.state'
}

# Post a comment on an issue
# Input: issue number, comment body
github_add_comment() {
    local issue_num="$1"
    local body="$2"
    gh issue comment "$issue_num" --body "$body"
}

# Close an issue with optional comment
# Input: issue number, optional comment body
github_close_issue() {
    local issue_num="$1"
    local comment="$2"
    if [[ -n "$comment" ]]; then
        gh issue close "$issue_num" --comment "$comment"
    else
        gh issue close "$issue_num"
    fi
}

# --- GitLab Backend ---

gitlab_check_cli() {
    command -v glab &>/dev/null || die "glab CLI is required for GitLab. Install: https://gitlab.com/gitlab-org/cli"
    glab auth status &>/dev/null || die "glab CLI is not authenticated. Run: glab auth login"
}

# Extract issue number from full GitLab URL
# Input: "https://gitlab.com/group/project/-/issues/123"
# Output: "123"
gitlab_extract_issue_number() {
    local url="$1"
    echo "$url" | grep -oE '[0-9]+$'
}

# Get current issue state (normalized to OPEN/CLOSED)
gitlab_get_issue_status() {
    local issue_num="$1"
    local state
    state=$(glab issue view "$issue_num" -F json | jq -r '.state')
    case "$state" in
        opened) echo "OPEN" ;;
        closed) echo "CLOSED" ;;
        *) echo "$state" ;;
    esac
}

# Post a comment (note) on an issue
gitlab_add_comment() {
    local issue_num="$1"
    local body="$2"
    glab issue note "$issue_num" -m "$body"
}

# Close an issue with optional comment
# Note: glab issue close doesn't support --comment, so we post note first
gitlab_close_issue() {
    local issue_num="$1"
    local comment="$2"
    if [[ -n "$comment" ]]; then
        glab issue note "$issue_num" -m "$comment"
    fi
    glab issue close "$issue_num"
}

# --- Bitbucket Backend ---

bitbucket_check_cli() {
    command -v bkt &>/dev/null || die "bkt CLI is required for Bitbucket. Install: https://github.com/avivsinai/bitbucket-cli"
    bkt auth status &>/dev/null || die "bkt CLI is not authenticated. Run: bkt auth login https://bitbucket.org --kind cloud --web"
}

# Extract issue number from full Bitbucket URL
# Input: "https://bitbucket.org/workspace/repo/issues/123/optional-slug"
# Output: "123"
# Note: Bitbucket URLs can have a trailing slug after the number
bitbucket_extract_issue_number() {
    local url="$1"
    echo "$url" | grep -oE '/issues/[0-9]+' | grep -oE '[0-9]+'
}

# Get current issue state (normalized to OPEN/CLOSED)
# Bitbucket states: new, open → OPEN; resolved, on hold, invalid, duplicate, wontfix, closed → CLOSED
bitbucket_get_issue_status() {
    local issue_num="$1"
    local state
    state=$(bkt issue view "$issue_num" --json | jq -r '.state')
    case "$state" in
        new|open) echo "OPEN" ;;
        resolved|on\ hold|invalid|duplicate|wontfix|closed) echo "CLOSED" ;;
        *) echo "OPEN" ;;  # Default to OPEN for unknown states
    esac
}

# Post a comment on an issue
bitbucket_add_comment() {
    local issue_num="$1"
    local body="$2"
    bkt issue comment "$issue_num" -b "$body"
}

# Close an issue with optional comment
# Note: bkt issue close doesn't support --comment, so we post comment first
bitbucket_close_issue() {
    local issue_num="$1"
    local comment="$2"
    if [[ -n "$comment" ]]; then
        bkt issue comment "$issue_num" -b "$comment"
    fi
    bkt issue close "$issue_num"
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

source_extract_issue_number() {
    local url="$1"
    case "$SOURCE" in
        github) github_extract_issue_number "$url" ;;
        gitlab) gitlab_extract_issue_number "$url" ;;
        bitbucket) bitbucket_extract_issue_number "$url" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_get_issue_status() {
    local issue_num="$1"
    case "$SOURCE" in
        github) github_get_issue_status "$issue_num" ;;
        gitlab) gitlab_get_issue_status "$issue_num" ;;
        bitbucket) bitbucket_get_issue_status "$issue_num" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_add_comment() {
    local issue_num="$1"
    local body="$2"
    case "$SOURCE" in
        github) github_add_comment "$issue_num" "$body" ;;
        gitlab) gitlab_add_comment "$issue_num" "$body" ;;
        bitbucket) bitbucket_add_comment "$issue_num" "$body" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_close_issue() {
    local issue_num="$1"
    local comment="$2"
    case "$SOURCE" in
        github) github_close_issue "$issue_num" "$comment" ;;
        gitlab) gitlab_close_issue "$issue_num" "$comment" ;;
        bitbucket) bitbucket_close_issue "$issue_num" "$comment" ;;
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
    # Only source code commits include this parenthesized tag; administrative
    # commits (status changes, archival) use "t<N>" without parentheses.
    # The parentheses also act as delimiters, so "(t88)" won't match "(t88_1)".
    local search_pattern="(t${task_id})"

    git log --oneline --all --grep="$search_pattern" 2>/dev/null || true
}

# Build the comment body for posting to the issue
# Input: task_id, plan_file_path (may be empty), commits_text (may be empty)
# Output: formatted comment body
build_comment_body() {
    local task_id="$1"
    local plan_path="$2"
    local commits_text="$3"

    local body="## Resolved via aitask t${task_id}"
    body="${body}"$'\n'

    # Plan file reference (prominent, first after header)
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

    echo "$body"
}

# Main execution function
run_update() {
    # Step 1-2: Get issue URL (from override or task file)
    local issue_url
    if [[ -n "$ISSUE_URL_OVERRIDE" ]]; then
        issue_url="$ISSUE_URL_OVERRIDE"
        info "Issue URL (override): $issue_url"
    else
        local task_file
        task_file=$(resolve_task_file "$TASK_NUM")
        info "Task file: $task_file"

        issue_url=$(extract_issue_url "$task_file")
        if [[ -z "$issue_url" ]]; then
            die "Task t${TASK_NUM} has no 'issue' field in its frontmatter"
        fi
        info "Issue URL: $issue_url"
    fi

    # Auto-detect source platform from issue URL if not explicitly set
    if [[ -z "$SOURCE" ]]; then
        SOURCE=$(detect_platform_from_url "$issue_url")
        if [[ -z "$SOURCE" ]]; then
            SOURCE=$(detect_platform)
        fi
        if [[ -z "$SOURCE" ]]; then
            die "Could not auto-detect source platform. Use --source github|gitlab|bitbucket"
        fi
    fi

    source_check_cli

    # Step 3: Extract issue number from URL
    local issue_number
    issue_number=$(source_extract_issue_number "$issue_url")

    if [[ -z "$issue_number" ]]; then
        die "Could not extract issue number from URL: $issue_url"
    fi
    info "Issue number: #$issue_number"

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

    # Step 6: Build comment body (unless --no-comment)
    local comment_body=""
    if [[ "$NO_COMMENT" != true ]]; then
        comment_body=$(build_comment_body "$TASK_NUM" "$plan_file" "$commits_text")
    fi

    # Step 7: Dry run output
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
        if [[ "$CLOSE_ISSUE" == true ]]; then
            echo -e "${BLUE}Action: Close issue #$issue_number${NC}"
        else
            echo -e "${BLUE}Action: Post comment only (issue remains open)${NC}"
        fi
        return 0
    fi

    # Step 8: Execute
    if [[ "$CLOSE_ISSUE" == true ]]; then
        if [[ "$NO_COMMENT" == true ]]; then
            info "Closing issue #$issue_number without comment..."
            source_close_issue "$issue_number" ""
        else
            info "Closing issue #$issue_number with comment..."
            source_close_issue "$issue_number" "$comment_body"
        fi
        success "Issue #$issue_number closed."
    else
        if [[ "$NO_COMMENT" == true ]]; then
            die "Nothing to do: --no-comment without --close has no effect"
        fi
        info "Posting comment on issue #$issue_number..."
        source_add_comment "$issue_number" "$comment_body"
        success "Comment posted on issue #$issue_number."
    fi
}

# --- Argument Parsing ---

show_help() {
    cat << 'EOF'
Usage: aitask_issue_update.sh [OPTIONS] TASK_NUM

Update a GitHub/GitLab/Bitbucket issue linked to an AI task with implementation notes and commits.

Required:
  TASK_NUM                Task number (e.g., 53 or 53_6 for child task)

Options:
  --source, -S PLATFORM   Source platform: github, gitlab, bitbucket (auto-detected from issue URL)
  --issue-url URL          Provide issue URL directly (skip task file lookup)
                           Useful when the task file has been deleted (e.g., folded tasks)
  --commits RANGE          Override auto-detected commits
                           Formats: "abc123,def456" or "abc123..def456" or "abc123"
  --close                  Close the issue after posting the comment
  --comment-only           Only post the comment, don't close (default)
  --no-comment             Close without posting a comment (requires --close)
  --dry-run                Show what would be done without doing it
  --help, -h               Show help

The script reads the task's 'issue' metadata field to find the issue URL.
The source platform is auto-detected from the issue URL (github.com → GitHub,
gitlab.com → GitLab, bitbucket.org → Bitbucket). Use --source to override auto-detection.
Commits are auto-detected from git history by searching for the task ID in commit
messages. Use --commits to override the auto-detection.

The comment includes:
  - Header with task reference
  - Link to the archived plan file (full implementation details)
  - "Final Implementation Notes" from the plan file
  - List of associated commits

Examples:
  # Post implementation notes as a comment
  ./aitask_issue_update.sh 83

  # Close the issue with implementation notes
  ./aitask_issue_update.sh --close 53_1

  # Override commit detection
  ./aitask_issue_update.sh --commits "abc123,def456" 83

  # Dry run to preview the comment
  ./aitask_issue_update.sh --dry-run 53_6

  # Close without a comment
  ./aitask_issue_update.sh --close --no-comment 83

  # Close a folded task's issue using the primary task for context
  ./aitask_issue_update.sh --issue-url "https://github.com/owner/repo/issues/42" --close 106
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --source|-S) SOURCE="$2"; shift 2 ;;
            --commits) COMMITS_OVERRIDE="$2"; shift 2 ;;
            --issue-url) ISSUE_URL_OVERRIDE="$2"; shift 2 ;;
            --close) CLOSE_ISSUE=true; shift ;;
            --comment-only) shift ;;  # Default behavior
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

    # Validate source platform (empty means auto-detect later in run_update)
    if [[ -n "$SOURCE" ]]; then
        case "$SOURCE" in
            github) ;;
            gitlab) ;;
            bitbucket) ;;
            *) die "Unknown source platform: $SOURCE (supported: github, gitlab, bitbucket)" ;;
        esac
    fi

    # Validate --no-comment requires --close
    if [[ "$NO_COMMENT" == true && "$CLOSE_ISSUE" != true ]]; then
        die "--no-comment requires --close (nothing to do otherwise)"
    fi
}

# --- Main ---

main() {
    parse_args "$@"
    run_update
}

main "$@"
