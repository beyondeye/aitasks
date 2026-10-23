#!/usr/bin/env bash
# git_utils.sh - Shared git helpers for aitask scripts.
# Source this file from aitask scripts; do not execute directly.

# --- Guard against double-sourcing ---
[[ -n "${_AIT_GIT_UTILS_LOADED:-}" ]] && return 0
_AIT_GIT_UTILS_LOADED=1

# Resolve the repository's primary branch name dynamically, against the current
# working directory (callers cd to the repo root). Resolution order:
#   1. origin/HEAD symbolic-ref (authoritative remote default — main/master/...),
#      read as the full ref and trusted only under refs/remotes/origin/
#   2. local main -> master probe
#   3. "main" fallback
# Keeps "main" as the logical default so main-default repos are unchanged, while
# master-default repos (where origin/main does not exist) resolve correctly.
#
# MAINTAINER GUARD: this is the bash twin of
# .aitask-scripts/lib/desync_state.py:detect_primary_branch — keep the two
# resolution orders in sync. (t1031)
detect_primary_branch() {
    local head
    # Full ref, never --short: --short abbreviates by ambiguity, so a local
    # branch named "origin/main" turns its answer into "remotes/origin/main". (t2123)
    head="$(git symbolic-ref --quiet refs/remotes/origin/HEAD 2>/dev/null || true)"
    case "$head" in
        refs/remotes/origin/?*)
            printf '%s\n' "${head#refs/remotes/origin/}"
            return 0
            ;;
    esac

    local candidate
    for candidate in main master; do
        if git rev-parse --verify --quiet "$candidate" >/dev/null 2>&1; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done

    printf 'main\n'
}
