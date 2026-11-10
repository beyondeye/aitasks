#!/usr/bin/env bash
# issue_backends.sh - Issue-tracker platform backends (GitHub, GitLab,
# Bitbucket) shared by the scripts that comment on or close a linked issue.
#
# Moved from aitask_issue_update.sh (t2261_1) so the release-time notifier can
# reuse the same backends instead of growing a parallel copy.
#
# Requires die() from lib/terminal_compat.sh (sourced via lib/task_utils.sh).
#
# Globals the dispatchers read (the sourcing script owns and sets them):
#   SOURCE            github | gitlab | bitbucket
#   GITLAB_REPO_SLUG  "group/project", for glab's -R flag (empty = current repo)
#
# Issue arguments: the source_* dispatchers take an *issue ref*, which is what
# the platform CLI receives — see source_issue_ref below. For GitHub that is the
# issue URL; for GitLab and Bitbucket it is the issue number.

[[ -n "${_AIT_ISSUE_BACKENDS_LOADED:-}" ]] && return 0
_AIT_ISSUE_BACKENDS_LOADED=1

# ============================================================
# PLATFORM BACKENDS
# To add a new platform (e.g., GitLab):
#   1. Implement all <platform>_* functions below
#   2. Add to --source validation in the caller's parse_args()
#   3. Add case to each source_* dispatcher function
# ============================================================

# --- GitHub Backend ---
# PLATFORM-EXTENSION-POINT: Add new platform backend functions here

github_check_cli() {
    command -v gh &>/dev/null || die "gh CLI is required for GitHub. Install: https://cli.github.com/"
    if ! gh auth status &>/dev/null; then
        die "gh CLI is not authenticated. Run: gh auth login"
    fi
}

# Extract issue number from full GitHub URL
# Input: "https://github.com/owner/repo/issues/123"
# Output: "123"
github_extract_issue_number() {
    local url="$1"
    echo "$url" | grep -oE '[0-9]+$'
}

# Get current issue state
# Input: issue ref (URL, or number for the current repository)
# Output: "OPEN" or "CLOSED"
github_get_issue_status() {
    local issue_ref="$1"
    gh issue view "$issue_ref" --json state -q '.state'
}

# Post a comment on an issue
# Input: issue ref, comment body
github_add_comment() {
    local issue_ref="$1"
    local body="$2"
    gh issue comment "$issue_ref" --body "$body"
}

# Close an issue with optional comment
# Input: issue ref, optional comment body
github_close_issue() {
    local issue_ref="$1"
    local comment="$2"
    if [[ -n "$comment" ]]; then
        gh issue close "$issue_ref" --comment "$comment"
    else
        gh issue close "$issue_ref"
    fi
}

# List every comment body on an issue (all pages), for a marker search.
# Input: the issue URL, https://<host>/<owner>/<repo>/issues/<n>
# Output: the bodies on stdout, rc 0. ANY failure — a URL that does not parse,
# a failed or partial API call — is non-zero, which means UNKNOWN, never "no
# comments": a caller must not read a failed listing as "the marker is absent".
github_list_comment_bodies() {
    local url="$1" host owner repo num
    local -a host_args=()
    [[ "$url" =~ ^https?://([^/]+)/([^/]+)/([^/]+)/issues/([0123456789]+)/?$ ]] || return 2
    host="${BASH_REMATCH[1]}"
    owner="${BASH_REMATCH[2]}"
    repo="${BASH_REMATCH[3]}"
    num="${BASH_REMATCH[4]}"
    if [[ "$host" != "github.com" ]]; then host_args=(--hostname "$host"); fi
    gh api --paginate "${host_args[@]}" "repos/$owner/$repo/issues/$num/comments" --jq '.[].body'
}

# --- GitLab Backend ---

gitlab_check_cli() {
    command -v glab &>/dev/null || die "glab CLI is required for GitLab. Install: https://gitlab.com/gitlab-org/cli"
    if ! glab auth status &>/dev/null; then
        die "glab CLI is not authenticated. Run: glab auth login"
    fi
}

# Extract issue number from full GitLab URL
# Input: "https://gitlab.com/group/project/-/issues/123"
# Output: "123"
gitlab_extract_issue_number() {
    local url="$1"
    echo "$url" | grep -oE '[0-9]+$'
}

# Extract "group/project" from GitLab issue URL for -R flag
gitlab_extract_repo_from_issue_url() {
    local url="$1"
    echo "$url" | sed 's|https://gitlab.com/||; s|/-/issues/.*||'
}

# Get -R flag for glab issue commands (empty if no repo slug set)
glab_repo_flag() {
    if [[ -n "$GITLAB_REPO_SLUG" ]]; then
        echo "-R $GITLAB_REPO_SLUG"
    fi
}

# The unquoted $(glab_repo_flag) below is deliberate: the flag is the two words
# `-R <slug>`, or nothing at all, and must split into exactly that.

# Get current issue state (normalized to OPEN/CLOSED)
gitlab_get_issue_status() {
    local issue_num="$1"
    local state
    # shellcheck disable=SC2046  # intended split of "-R <slug>" (see above)
    state=$(glab issue view "$issue_num" $(glab_repo_flag) -F json | jq -r '.state')
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
    # shellcheck disable=SC2046  # intended split of "-R <slug>" (see above)
    glab issue note "$issue_num" $(glab_repo_flag) -m "$body"
}

# Close an issue with optional comment
# Note: glab issue close doesn't support --comment, so we post note first
gitlab_close_issue() {
    local issue_num="$1"
    local comment="$2"
    if [[ -n "$comment" ]]; then
        # shellcheck disable=SC2046  # intended split of "-R <slug>" (see above)
        glab issue note "$issue_num" $(glab_repo_flag) -m "$comment"
    fi
    # shellcheck disable=SC2046  # intended split of "-R <slug>" (see above)
    glab issue close "$issue_num" $(glab_repo_flag)
}

# List every note body on an issue (all pages), for a marker search.
# Input: the issue URL, https://<host>/<group>[/<subgroup>...]/<project>/-/issues/<iid>
# Output: the bodies on stdout, rc 0; any failure is non-zero = UNKNOWN (see
# github_list_comment_bodies). `glab api --paginate` prints one JSON array per
# page, so the bodies are taken with jq over the whole stream.
gitlab_list_comment_bodies() {
    local url="$1" host slug iid enc out
    local -a host_args=()
    [[ "$url" =~ ^https?://([^/]+)/(.+)/-/issues/([0123456789]+)/?$ ]] || return 2
    host="${BASH_REMATCH[1]}"
    slug="${BASH_REMATCH[2]}"
    iid="${BASH_REMATCH[3]}"
    [[ "$slug" =~ ^[ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._/-]+$ ]] || return 2
    enc="${slug//\//%2F}"
    if [[ "$host" != "gitlab.com" ]]; then host_args=(--hostname "$host"); fi
    command -v jq >/dev/null 2>&1 || return 1
    out="$(glab api "${host_args[@]}" --paginate "projects/$enc/issues/$iid/notes?per_page=100")" || return 1
    printf '%s' "$out" | jq -r '.[].body'
}

# --- Bitbucket Backend ---
# Retirement owned by t2251 (the Bitbucket Cloud issue API was removed on
# 2026-08-20). Kept verbatim here until that task removes it.

bitbucket_check_cli() {
    command -v bkt &>/dev/null || die "bkt CLI is required for Bitbucket. Install: https://github.com/avivsinai/bitbucket-cli"
    if ! bkt auth status &>/dev/null; then
        die "bkt CLI is not authenticated. Run: bkt auth login https://bitbucket.org --kind cloud --web"
    fi
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

# source_issue_ref <issue_url> — the issue argument the platform CLI receives.
#
# GitHub: the issue URL itself. `gh issue view|comment|close` accept
# `{<number> | <url>}`, and only the URL names the repository: a bare number
# targets the CURRENT repository, which is the wrong issue for an `issue:` URL
# in another repository or on GitHub Enterprise. A value that is not a URL
# (a bare number) passes through as the extracted number, as before.
#
# GitLab / Bitbucket: the issue number. GitLab names the repository through
# GITLAB_REPO_SLUG (-R), so its argv is unchanged.
source_issue_ref() {
    local url="$1"
    case "$SOURCE" in
        github)
            case "$url" in
                http://*|https://*) printf '%s\n' "$url" ;;
                *) github_extract_issue_number "$url" ;;
            esac
            ;;
        gitlab|bitbucket) source_extract_issue_number "$url" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_get_issue_status() {
    local issue_ref="$1"
    case "$SOURCE" in
        github) github_get_issue_status "$issue_ref" ;;
        gitlab) gitlab_get_issue_status "$issue_ref" ;;
        bitbucket) bitbucket_get_issue_status "$issue_ref" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

source_add_comment() {
    local issue_ref="$1"
    local body="$2"
    case "$SOURCE" in
        github) github_add_comment "$issue_ref" "$body" ;;
        gitlab) gitlab_add_comment "$issue_ref" "$body" ;;
        bitbucket) bitbucket_add_comment "$issue_ref" "$body" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}

# source_list_comment_bodies <issue_url> — tri-state comment listing (see
# github_list_comment_bodies). GitHub and GitLab only: anything else is
# non-zero (unknown), never an empty listing.
source_list_comment_bodies() {
    local url="$1"
    case "$SOURCE" in
        github) github_list_comment_bodies "$url" ;;
        gitlab) gitlab_list_comment_bodies "$url" ;;
        *) return 1 ;;
    esac
}

source_close_issue() {
    local issue_ref="$1"
    local comment="$2"
    case "$SOURCE" in
        github) github_close_issue "$issue_ref" "$comment" ;;
        gitlab) gitlab_close_issue "$issue_ref" "$comment" ;;
        bitbucket) bitbucket_close_issue "$issue_ref" "$comment" ;;
        *) die "Unknown source: $SOURCE" ;;
    esac
}
