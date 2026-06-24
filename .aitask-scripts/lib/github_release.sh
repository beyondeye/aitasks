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
# Portability: ERE sed only (no GNU-only `\?` BRE quantifier), numeric `sort`
# (no GNU-only `sort -V`), and integer minute math instead of `date`
# formatting. See aidocs/framework/sed_macos_issues.md.

# Guard against double-sourcing (these are pure function definitions).
[[ -n "${_AIT_GITHUB_RELEASE_SH:-}" ]] && return 0
_AIT_GITHUB_RELEASE_SH=1

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

# github_latest_tag_version <repo>
github_latest_tag_version() {
    local repo="$1"
    git ls-remote --tags --refs "https://github.com/$repo" 'v*' 2>/dev/null \
        | sed -E 's#.*refs/tags/v?##' \
        | grep -E '^[0-9]+(\.[0-9]+)*$' \
        | sort -t. -k1,1n -k2,2n -k3,3n \
        | tail -1
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
