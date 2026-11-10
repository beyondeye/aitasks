#!/usr/bin/env bash

# aitask_issue_update.sh - Update GitHub/GitLab/Bitbucket issues linked to AI tasks
# Posts implementation notes and commit references as issue comments
# Optionally closes the issue

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/issue_backends.sh
source "$SCRIPT_DIR/lib/issue_backends.sh"
# shellcheck source=lib/release_issue_ledger.sh
source "$SCRIPT_DIR/lib/release_issue_ledger.sh"

# Command options
SOURCE=""  # Auto-detected from issue URL or git remote if not set via --source
TASK_NUM=""
COMMITS_OVERRIDE=""
CLOSE_ISSUE=false
NO_COMMENT=false
DRY_RUN=false
RECORD_ONLY=false    # --record-only: write the release-ledger entry, no platform call
ISSUE_URL_OVERRIDE=""
GITLAB_REPO_SLUG=""  # Extracted from GitLab URL for cross-repo -R flag
RESOLVED_ISSUE_URL=""  # Set by resolve_issue_target

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

# Steps 1-2: resolve the issue URL (override or task file), the source platform
# and the GitLab repo slug. Sets RESOLVED_ISSUE_URL, SOURCE, GITLAB_REPO_SLUG.
# Call it directly, never inside $( ): it prints info lines and may die.
resolve_issue_target() {
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

    # Extract repo slug for GitLab cross-repo support
    if [[ "$SOURCE" == "gitlab" ]]; then
        # shellcheck disable=SC2034  # read by glab_repo_flag (lib/issue_backends.sh)
        GITLAB_REPO_SLUG=$(gitlab_extract_repo_from_issue_url "$issue_url")
    fi

    RESOLVED_ISSUE_URL="$issue_url"
}

# --- Release ledger (t2261) ---
#
# After a successful update, the issue is recorded in the rolling ledger of
# "issues fixed since the last release" (lib/release_issue_ledger.sh), which
# the release step reads to announce the release that ships the fix.

# The ledger action for the flags of this run.
ledger_action() {
    if [[ "$CLOSE_ISSUE" == true && "$NO_COMMENT" == true ]]; then
        echo closed_silent
    elif [[ "$CLOSE_ISSUE" == true ]]; then
        echo closed
    else
        echo commented
    fi
}

# The exact command that records this run's entry without touching the issue.
# Every word is %q-quoted: the URL charset includes & ; ( ) ' $ ! * ? #.
record_only_command() {
    local -a argv=(./.aitask-scripts/aitask_issue_update.sh --record-only --source "$SOURCE")
    if [[ -n "$ISSUE_URL_OVERRIDE" ]]; then argv+=(--issue-url "$ISSUE_URL_OVERRIDE"); fi
    if [[ "$CLOSE_ISSUE" == true ]]; then argv+=(--close); fi
    if [[ "$NO_COMMENT" == true ]]; then argv+=(--no-comment); fi
    argv+=("$TASK_NUM")
    local out="" word
    for word in "${argv[@]}"; do
        out+="${out:+ }$(printf '%q' "$word")"
    done
    printf '%s\n' "$out"
}

# print_ledger_recovery_hint <reason-text> — stderr, through printf: warn() and
# info() use `echo -e`, which would mangle a %q-quoted URL.
print_ledger_recovery_hint() {
    local detail="$1" reason="${1%%:*}" path=""
    [[ "$detail" == *:* ]] && path="${detail#*:}"
    {
        if [[ "$RECORD_ONLY" == true ]]; then
            printf '%s\n' "Nothing was posted (--record-only); the release-ledger entry was not recorded ($detail)."
        else
            printf '%s\n' "The issue WAS updated — do not re-run this command; that would post the comment again."
            printf '%s\n' "Only its release-ledger entry was not recorded ($detail)."
        fi
        case "$reason" in
            invalid_task_id|invalid_url|invalid_platform|invalid_action|hash_collision)
                printf '%s\n' "This issue cannot be recorded in the release ledger, so no retry will succeed; its release notification will not be posted automatically."
                ;;
            malformed_record|uncommitted_record|uncommitted_change|persistence_unknown|commit_unverified|rollback_failed)
                printf '%s\n' "Inspect and resolve the record file first (commit, restore or remove it): ${path:-?}"
                printf '%s\n' "Then record the release-ledger entry with:"
                printf '  %s\n' "$(record_only_command)"
                ;;
            aborted)
                # A shared git helper died, and some of them silence their own
                # message. Report the one cause that can be read back.
                local wedge
                wedge="$(ait_data_inprogress_state)"
                if [[ -n "$wedge" ]]; then
                    printf '%s\n' "The task-data worktree is stuck mid-${wedge}; resolve that first (./ait git-health)."
                fi
                printf '%s\n' "Record the release-ledger entry with:"
                printf '  %s\n' "$(record_only_command)"
                ;;
            *)
                printf '%s\n' "Record the release-ledger entry with:"
                printf '  %s\n' "$(record_only_command)"
                ;;
        esac
    } >&2
}

# record_release_ledger <issue_url> — record the entry; print exactly one
# RELEASE_LEDGER* line. Returns 0 (recorded / duplicate / skipped) or 3.
record_release_ledger() {
    local issue_url="$1" out_file rc=0 line=""
    case "$SOURCE" in
        github|gitlab) ;;
        *)
            # Bitbucket's issue API is gone (t2251 retires that backend).
            echo "RELEASE_LEDGER:skipped:unsupported_platform"
            return 0
            ;;
    esac
    if ! out_file="$(mktemp "${TMPDIR:-/tmp}/aitask_issue_ledger.XXXXXX" 2>/dev/null)"; then
        line="RELEASE_LEDGER_FAILED:tmp_unavailable"
    else
        # Not $( ): ril_record takes the ledger lock, and its body is a subshell
        # that prints its one result line (or nothing, if a shared helper died).
        ril_record "$TASK_NUM" "$issue_url" "$SOURCE" "$(ledger_action)" > "$out_file" || rc=$?
        line="$(grep -m1 '^RELEASE_LEDGER' "$out_file" 2>/dev/null)" || line=""
        rm -f "$out_file"
        if [[ "$rc" == 0 && "$line" == RELEASE_LEDGER:* ]]; then
            printf '%s\n' "$line"
            return 0
        fi
        [[ "$line" == RELEASE_LEDGER_FAILED:* ]] || line="RELEASE_LEDGER_FAILED:aborted"
    fi
    printf '%s\n' "$line"
    print_ledger_recovery_hint "${line#RELEASE_LEDGER_FAILED:}"
    return 3
}

# --record-only: the recovery for exit 3. Records the entry from the same
# flags, with no CLI check and no platform call.
run_record_only() {
    resolve_issue_target
    info "Record-only: no platform call is made"
    record_release_ledger "$RESOLVED_ISSUE_URL" || exit $?
}

# Main execution function
run_update() {
    # Steps 1-2: issue URL, source platform, GitLab slug
    resolve_issue_target
    local issue_url="$RESOLVED_ISSUE_URL"

    source_check_cli

    # Step 3: Extract issue number from URL
    local issue_number
    issue_number=$(source_extract_issue_number "$issue_url")

    if [[ -z "$issue_number" ]]; then
        die "Could not extract issue number from URL: $issue_url"
    fi
    info "Issue number: #$issue_number"

    # The argument the backend CLI receives (the URL for GitHub, so an issue in
    # another repository is not resolved against the current one). Messages keep
    # using the number.
    local issue_ref
    issue_ref=$(source_issue_ref "$issue_url")

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
            source_close_issue "$issue_ref" ""
        else
            info "Closing issue #$issue_number with comment..."
            source_close_issue "$issue_ref" "$comment_body"
        fi
        success "Issue #$issue_number closed."
    else
        if [[ "$NO_COMMENT" == true ]]; then
            die "Nothing to do: --no-comment without --close has no effect"
        fi
        info "Posting comment on issue #$issue_number..."
        source_add_comment "$issue_ref" "$comment_body"
        success "Comment posted on issue #$issue_number."
    fi

    # Step 9: record it in the release ledger. Only reached after the platform
    # call succeeded: a failed call exits under `set -e` first, which is why
    # main() never calls run_update inside a conditional.
    record_release_ledger "$issue_url" || exit $?
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
  --record-only            Only record the release-ledger entry, from the same
                           flags: no CLI check, no platform call. The recovery
                           for exit status 3. Cannot be combined with --dry-run.
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

  # Record the release-ledger entry after an exit-3 run (posts nothing)
  ./aitask_issue_update.sh --record-only --source github --close 53_1

Release ledger:
  After the comment is posted and/or the issue is closed, the issue is recorded
  in the release ledger (aitasks/metadata/release_issues/pending/, one file per
  issue, committed with the task data). The release step reads it to announce
  the release that ships the fix. GitHub and GitLab issues are recorded;
  --dry-run records nothing. The last stdout line reports the outcome:
    RELEASE_LEDGER:recorded:<path>       committed by this run
    RELEASE_LEDGER:duplicate:<path>      already recorded for this task + issue
    RELEASE_LEDGER:skipped:unsupported_platform
    RELEASE_LEDGER_FAILED:<reason>       see exit status 3

Exit status:
  0  Done (any RELEASE_LEDGER: line above).
  1  Failed before or during the platform call; nothing was recorded.
  3  The issue WAS updated, but its release-ledger entry was not recorded
     (RELEASE_LEDGER_FAILED:<reason>). Do not re-run the command, which would
     post the comment again: run the --record-only command printed on stderr.
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
            --record-only) RECORD_ONLY=true; shift ;;
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

    if [[ "$RECORD_ONLY" == true && "$DRY_RUN" == true ]]; then
        die "--record-only cannot be combined with --dry-run"
    fi
}

# --- Main ---

main() {
    parse_args "$@"
    # Never `run_update || …`: a conditional context disables errexit inside it,
    # and errexit is what stops a failed platform call before the ledger hook.
    if [[ "$RECORD_ONLY" == true ]]; then
        run_record_only
    else
        run_update
    fi
}

main "$@"
