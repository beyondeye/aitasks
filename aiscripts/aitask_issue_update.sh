#!/bin/bash

# aitask_issue_update.sh - Update GitHub issues linked to AI tasks
# Posts implementation notes and commit references as issue comments
# Optionally closes the issue

set -e

TASK_DIR="aitasks"
ARCHIVED_DIR="aitasks/archived"
PLAN_DIR="aiplans"
ARCHIVED_PLAN_DIR="aiplans/archived"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Command options
SOURCE="github"
TASK_NUM=""
COMMITS_OVERRIDE=""
CLOSE_ISSUE=false
NO_COMMENT=false
DRY_RUN=false

# --- Helper Functions ---

die() {
    echo -e "${RED}Error: $1${NC}" >&2
    exit 1
}

info() {
    echo -e "${BLUE}$1${NC}"
}

success() {
    echo -e "${GREEN}$1${NC}"
}

warn() {
    echo -e "${YELLOW}Warning: $1${NC}" >&2
}

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

# --- Dispatcher Functions ---
# PLATFORM-EXTENSION-POINT: Add new platform cases to each dispatcher

source_check_cli() {
    case "$SOURCE" in
        github) github_check_cli ;;
        # gitlab) gitlab_check_cli ;;  # PLATFORM-EXTENSION-POINT
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_extract_issue_number() {
    local url="$1"
    case "$SOURCE" in
        github) github_extract_issue_number "$url" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_get_issue_status() {
    local issue_num="$1"
    case "$SOURCE" in
        github) github_get_issue_status "$issue_num" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_add_comment() {
    local issue_num="$1"
    local body="$2"
    case "$SOURCE" in
        github) github_add_comment "$issue_num" "$body" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_close_issue() {
    local issue_num="$1"
    local comment="$2"
    case "$SOURCE" in
        github) github_close_issue "$issue_num" "$comment" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

# --- Task and Plan Resolution ---

# Resolve task number to file path, checking both active and archived directories
# Input: task_id (e.g., "53" or "53_6")
# Output: file path
resolve_task_file() {
    local task_id="$1"
    local files=""

    if [[ "$task_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local parent_num="${BASH_REMATCH[1]}"
        local child_num="${BASH_REMATCH[2]}"

        # Check active directory first
        files=$(ls "$TASK_DIR"/t${parent_num}/t${parent_num}_${child_num}_*.md 2>/dev/null || true)

        # Check archived directory
        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_DIR"/t${parent_num}/t${parent_num}_${child_num}_*.md 2>/dev/null || true)
        fi

        if [[ -z "$files" ]]; then
            die "No task file found for t${parent_num}_${child_num} (checked active and archived)"
        fi
    else
        # Parent task
        files=$(ls "$TASK_DIR"/t${task_id}_*.md 2>/dev/null || true)

        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_DIR"/t${task_id}_*.md 2>/dev/null || true)
        fi

        if [[ -z "$files" ]]; then
            die "No task file found for task number $task_id (checked active and archived)"
        fi
    fi

    local count
    count=$(echo "$files" | wc -l)

    if [[ "$count" -gt 1 ]]; then
        die "Multiple task files found for task $task_id"
    fi

    echo "$files"
}

# Resolve plan file from task number, checking both active and archived
# Plan naming convention:
#   Parent task t53_name.md -> plan p53_name.md
#   Child task t53/t53_1_name.md -> plan p53/p53_1_name.md
# Input: task_id (e.g., "53" or "53_6")
# Output: file path or empty string if not found
resolve_plan_file() {
    local task_id="$1"
    local files=""

    if [[ "$task_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local parent_num="${BASH_REMATCH[1]}"
        local child_num="${BASH_REMATCH[2]}"

        # Check active plan directory
        files=$(ls "$PLAN_DIR"/p${parent_num}/p${parent_num}_${child_num}_*.md 2>/dev/null || true)

        # Check archived plan directory
        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_PLAN_DIR"/p${parent_num}/p${parent_num}_${child_num}_*.md 2>/dev/null || true)
        fi
    else
        # Parent plan
        files=$(ls "$PLAN_DIR"/p${task_id}_*.md 2>/dev/null || true)

        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_PLAN_DIR"/p${task_id}_*.md 2>/dev/null || true)
        fi
    fi

    if [[ -z "$files" ]]; then
        echo ""
        return
    fi

    local count
    count=$(echo "$files" | wc -l)
    if [[ "$count" -gt 1 ]]; then
        echo "$files" | head -1
    else
        echo "$files"
    fi
}

# Extract the issue URL from a task file's YAML frontmatter
# Input: task file path
# Output: issue URL or empty string
extract_issue_url() {
    local file_path="$1"
    local in_yaml=false

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then
                break
            else
                in_yaml=true
                continue
            fi
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^issue:[[:space:]]*(.*) ]]; then
            local url="${BASH_REMATCH[1]}"
            url=$(echo "$url" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$url"
            return
        fi
    done < "$file_path"

    echo ""
}

# Extract "Final Implementation Notes" section from a plan file
# Input: plan file path
# Output: the section content
extract_final_implementation_notes() {
    local plan_path="$1"
    local in_section=false
    local content=""

    while IFS= read -r line; do
        if [[ "$line" =~ ^##[[:space:]]+Final[[:space:]]+Implementation[[:space:]]+Notes ]]; then
            in_section=true
            continue
        fi

        if [[ "$in_section" == true ]]; then
            # Stop at next level-2 heading
            if [[ "$line" =~ ^##[[:space:]] ]]; then
                break
            fi
            if [[ -n "$content" ]]; then
                content="${content}"$'\n'"${line}"
            else
                content="$line"
            fi
        fi
    done < "$plan_path"

    # Trim leading/trailing blank lines
    echo "$content" | sed '/./,$!d' | sed -e :a -e '/^[[:space:]]*$/{ $d; N; ba; }'
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
    source_check_cli

    # Step 1: Resolve task file
    local task_file
    task_file=$(resolve_task_file "$TASK_NUM")
    info "Task file: $task_file"

    # Step 2: Extract issue URL from task metadata
    local issue_url
    issue_url=$(extract_issue_url "$task_file")

    if [[ -z "$issue_url" ]]; then
        die "Task t${TASK_NUM} has no 'issue' field in its frontmatter"
    fi
    info "Issue URL: $issue_url"

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

Update a GitHub issue linked to an AI task with implementation notes and commits.

Required:
  TASK_NUM                Task number (e.g., 53 or 53_6 for child task)

Options:
  --source, -S PLATFORM   Source platform: github (default)
  --commits RANGE          Override auto-detected commits
                           Formats: "abc123,def456" or "abc123..def456" or "abc123"
  --close                  Close the issue after posting the comment
  --comment-only           Only post the comment, don't close (default)
  --no-comment             Close without posting a comment (requires --close)
  --dry-run                Show what would be done without doing it
  --help, -h               Show help

The script reads the task's 'issue' metadata field to find the GitHub issue URL.
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
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --source|-S) SOURCE="$2"; shift 2 ;;
            --commits) COMMITS_OVERRIDE="$2"; shift 2 ;;
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
    [[ -z "$TASK_NUM" ]] && die "Task number is required. Use --help for usage."

    # Validate source platform
    case "$SOURCE" in
        github) ;;
        # gitlab) ;;  # PLATFORM-EXTENSION-POINT
        *) die "Unknown source platform: $SOURCE (supported: github)" ;;
    esac

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
