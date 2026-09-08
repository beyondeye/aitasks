#!/usr/bin/env bash
# github_release.sh - Resolve the latest GitHub release version with accurate
# error classification and a rate-limit-free git fallback.
# Source this file from aitask scripts; do not execute directly.
#
# Provides:
#   github_latest_release_version <repo>
#       REST API path. Prints the version (no leading 'v') on stdout (exit 0).
#       On failure prints a classification token to stderr and returns:
#         2  RATELIMIT  - API refused with a rate-limit error (403/429)
#         3  NOTFOUND   - 404 / no releases / unexpected empty result
#         4  NETWORK    - empty / unreachable response
#       Honors $GH_TOKEN / $GITHUB_TOKEN (Authorization: Bearer) when set,
#       which raises the unauthenticated 60/hour cap to 5000/hour.
#   github_latest_tag_version <repo>
#       Rate-limit-free fallback via `git ls-remote` (the git protocol is not
#       subject to the REST API quota). Prints the highest semver tag (no 'v')
#       on stdout, or nothing if no matching tag is found.
#   github_ratelimit_reset_minutes
#       Best-effort integer "minutes until the core quota resets", via the
#       exempt /rate_limit endpoint. Prints nothing if it cannot be determined.
#   github_resolve_latest_version <repo>
#       Combined: try the REST API; on RATELIMIT/NETWORK fall back to git tags.
#       Prints the version on stdout; on the fallback path, a short human note
#       to stderr. Returns the API failure code only if the fallback is empty.
#
# Environment:
#   AIT_GIT_LSREMOTE_TIMEOUT
#       Hard time bound, in whole seconds, for the `git ls-remote` fallback.
#       Defaults to 10 — the same bound the REST path carries as
#       `curl --max-time 10`. Any unset, empty, zero, negative or non-numeric
#       value normalizes back to that default (see _github_ls_remote_tags).
#
# Portability: ERE sed only (no GNU-only `\?` BRE quantifier), numeric `sort`
# (no GNU-only `sort -V`), and integer minute math instead of `date`
# formatting. See aidocs/framework/sed_macos_issues.md.

# Guard against double-sourcing (these are pure function definitions).
[[ -n "${_AIT_GITHUB_RELEASE_SH:-}" ]] && return 0
_AIT_GITHUB_RELEASE_SH=1

# Hard time bound (seconds) for the `git ls-remote` fallback. See
# _github_ls_remote_tags for why the fallback needs one and how the
# AIT_GIT_LSREMOTE_TIMEOUT override is normalized.
_AIT_GIT_LSREMOTE_TIMEOUT_DEFAULT=10

# github_latest_release_version <repo>
github_latest_release_version() {
    local repo="$1"
    local url="https://api.github.com/repos/$repo/releases/latest"

    local -a auth=()
    local tok="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
    [[ -n "$tok" ]] && auth=(-H "Authorization: Bearer $tok")

    # Capture body + HTTP status in one call. `-w` appends the status on its own
    # trailing line; a failed connection still yields `\n000` (handled below).
    local resp http body version
    resp="$(curl -sS --max-time 10 "${auth[@]+"${auth[@]}"}" \
        -w $'\n%{http_code}' "$url" 2>/dev/null)" || true

    http="${resp##*$'\n'}"
    body="${resp%$'\n'*}"

    if [[ -z "$resp" || -z "$http" || "$http" == "000" ]]; then
        echo "NETWORK" >&2
        return 4
    fi

    version="$(printf '%s' "$body" | grep '"tag_name"' | head -1 \
        | sed -E 's/.*"tag_name": *"v?([^"]*)".*/\1/')"

    if [[ -n "$version" ]]; then
        printf '%s\n' "$version"
        return 0
    fi

    # No tag parsed — classify the error response.
    if { [[ "$http" == "403" || "$http" == "429" ]]; } \
        && printf '%s' "$body" | grep -qi 'rate limit'; then
        echo "RATELIMIT" >&2
        return 2
    fi

    # 404, a 403 without a rate-limit message, or any other unexpected shape.
    echo "NOTFOUND" >&2
    return 3
}

# github_ratelimit_reset_minutes
github_ratelimit_reset_minutes() {
    local reset now mins
    reset="$(curl -sS --max-time 5 "https://api.github.com/rate_limit" 2>/dev/null \
        | grep -A5 '"core"' | grep '"reset"' | head -1 \
        | sed -E 's/.*"reset": *([0-9]+).*/\1/')" || true
    [[ "$reset" =~ ^[0-9]+$ ]] || return 0
    now="$(date +%s)"
    mins=$(( (reset - now + 59) / 60 ))
    (( mins < 0 )) && mins=0
    printf '%s\n' "$mins"
}

# _github_kill_descendants <pid>
# Best-effort recursive walk, killing deepest first. Secondary mechanism only —
# see _github_kill_process_tree for why it cannot be the primary one.
_github_kill_descendants() {
    local pid="$1" child
    for child in $(pgrep -P "$pid" 2>/dev/null || true); do
        _github_kill_descendants "$child"
        kill "$child" 2>/dev/null || true
    done
}

# _github_kill_process_tree <pid>
# Kill <pid> and every descendant. Best-effort throughout: a pid that has
# already exited must never fail the caller. Killing only the direct child is
# not enough — `git ls-remote` runs the actual transfer in a `git-remote-https`
# grandchild, which outlives its parent and keeps the wedged socket open.
#
# The PROCESS GROUP is the primary mechanism, and it needs no external binary.
# An earlier version walked the tree with `pgrep -P` alone; on a system without
# `pgrep` (minimal containers ship no procps) that silently degrades to a
# depth-1 kill and leaves every descendant running — measured, and precisely the
# leak this helper exists to prevent.
_github_kill_process_tree() {
    local pid="$1"
    # The runner enables job control for the launch, so the job is its own
    # process-group leader and this single signal reaches the whole tree. If it
    # never got its own group, no group carries that id and the signal is simply
    # refused (ESRCH) — it can never reach this shell's own group, whose id is
    # this shell's pid, not the job's.
    kill -- "-$pid" 2>/dev/null || true
    # Fallback for a shell that could not give the job its own group.
    _github_kill_descendants "$pid"
    kill "$pid" 2>/dev/null || true
}

# _github_ls_remote_tags <url>
# Run `git ls-remote --tags --refs <url> 'v*'` under a hard time bound and print
# its raw output. Prints nothing when it times out; always returns 0.
#
# Deliberately NOT `timeout(1)`: macOS ships none, and the callers' test doubles
# stub `git` as a shell FUNCTION, which an exec'd `timeout` would bypass and turn
# into a live network call. So the bound is a background job plus a polling
# watchdog — the same shape as aitask_sync.sh:_git_with_timeout.
#
# Output goes to a temp file rather than a pipe: a surviving `git-remote-https`
# grandchild holding the write end of a pipe keeps the reader blocked for the
# full hang (measured in t1223_2). A file has no such reader.
_github_ls_remote_tags() {
    local url="$1"
    local timeout_s tmp pid deadline timed_out=0

    # The knob is externally set, so normalize it before it reaches arithmetic or
    # git. Unguarded, `abc` aborts the function under `set -u` ("unbound
    # variable") and takes the caller's command substitution with it, while ""
    # / 0 / a negative make the deadline expire instantly — silently disabling
    # the fallback for good. `10#` is required: `(( 08 > 0 ))` is an
    # invalid-octal error. if/else rather than `[[ … ]] && (( … ))`, because a
    # false `&&` list is a non-zero statement and trips `set -e`.
    timeout_s="${AIT_GIT_LSREMOTE_TIMEOUT:-$_AIT_GIT_LSREMOTE_TIMEOUT_DEFAULT}"
    if [[ "$timeout_s" =~ ^[0-9]+$ ]] && (( 10#$timeout_s > 0 )); then
        timeout_s=$(( 10#$timeout_s ))
    else
        timeout_s="$_AIT_GIT_LSREMOTE_TIMEOUT_DEFAULT"
    fi

    tmp="$(mktemp "${TMPDIR:-/tmp}/ait_lsremote.XXXXXX" 2>/dev/null)" || return 0

    # GIT_HTTP_LOW_SPEED_* asks git to give up on its own first, which tears the
    # transport helper down cleanly; the watchdog below is the hard backstop for
    # the phases that timer does not cover (DNS, TCP connect).
    #
    # Job control is enabled for the launch ONLY: it is what puts the background
    # job in a process group of its own, which is how the whole descendant tree
    # can later be killed with one signal and no external binary. Restored
    # immediately, and only when this shell did not already have it.
    local had_monitor=0
    case "$-" in *m*) had_monitor=1 ;; esac
    set -m
    GIT_TERMINAL_PROMPT=0 \
    GIT_HTTP_LOW_SPEED_LIMIT=1 \
    GIT_HTTP_LOW_SPEED_TIME="$timeout_s" \
    git ls-remote --tags --refs "$url" 'v*' >"$tmp" 2>/dev/null &
    pid=$!
    [[ "$had_monitor" -eq 1 ]] || set +m

    # $SECONDS keeps the bound honest whichever sleep granularity the platform
    # accepts (BSD and GNU sleep both take fractions; a stricter one would not).
    deadline=$(( SECONDS + timeout_s ))
    while kill -0 "$pid" 2>/dev/null && (( SECONDS < deadline )); do
        sleep 0.2 2>/dev/null || sleep 1
    done
    if kill -0 "$pid" 2>/dev/null; then
        timed_out=1
        _github_kill_process_tree "$pid"
    fi
    wait "$pid" 2>/dev/null || true

    if [[ "$timed_out" -eq 0 ]]; then
        cat "$tmp" 2>/dev/null || true
    fi
    rm -f "$tmp"
    return 0
}

# github_latest_tag_version <repo>
github_latest_tag_version() {
    local repo="$1"
    # `|| true`: under `pipefail` a grep that matches nothing makes the whole
    # pipeline exit 1 — routine now that a timeout yields no input at all — and
    # callers capture this in an unguarded `$( )` under `set -e`
    # (aitask_upgrade.sh:67, github_resolve_latest_version below). "No version
    # found" must be an empty string with status 0, not a silent script death.
    _github_ls_remote_tags "https://github.com/$repo" \
        | sed -E 's#.*refs/tags/v?##' \
        | grep -E '^[0-9]+(\.[0-9]+)*$' \
        | sort -t. -k1,1n -k2,2n -k3,3n \
        | tail -1 || true
}

# github_resolve_latest_version <repo>
github_resolve_latest_version() {
    local repo="$1"
    local version rc=0
    version="$(github_latest_release_version "$repo" 2>/dev/null)" || rc=$?

    if [[ $rc -eq 0 && -n "$version" ]]; then
        printf '%s\n' "$version"
        return 0
    fi

    # Rate-limited or network failure → try the quota-free git fallback.
    if [[ $rc -eq 2 || $rc -eq 4 ]]; then
        version="$(github_latest_tag_version "$repo")"
        if [[ -n "$version" ]]; then
            echo "resolved via git tags (REST API unavailable)" >&2
            printf '%s\n' "$version"
            return 0
        fi
    fi

    return "$rc"
}
