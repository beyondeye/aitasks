#!/usr/bin/env bash
# cross_repo_reexec.sh - Cross-repo --project re-exec for read-side helpers.
#
# Shared dispatch for `aitask_query_files.sh`, `aitask_ls.sh`, and
# `aitask_find_by_file.sh` (t832_1). Each helper sources this lib and
# calls `cross_repo_reexec_or_continue <basename> "$@"` near the top.
#
# Contract:
#   - If `--project <name>` appears in argv, resolve <name> via
#     aitask_project_resolve.sh, then `exec` the sibling project's
#     same-named helper inside the sibling root with `--project <name>`
#     stripped. The function does not return in that case.
#   - Otherwise, set CROSS_REPO_FORWARDED_ARGV to the original argv
#     (still stripped of any --project pair, which there isn't) and
#     return so the caller proceeds locally.
#
# Source this file from helpers; do not execute directly.

[[ -n "${_AIT_CROSS_REPO_REEXEC_LOADED:-}" ]] && return 0
_AIT_CROSS_REPO_REEXEC_LOADED=1

_CROSS_REPO_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_CROSS_REPO_SCRIPTS_DIR="$(cd "$_CROSS_REPO_LIB_DIR/.." && pwd)"
# shellcheck source=terminal_compat.sh
source "$_CROSS_REPO_LIB_DIR/terminal_compat.sh"

# Re-exec into a sibling project's same-named helper if `--project <name>`
# appears in argv. On success the call to `exec` does not return; on
# missing `--project` the function sets CROSS_REPO_FORWARDED_ARGV to the
# unchanged argv and returns 0.
#
# Args:
#   $1   = helper basename (e.g. "aitask_query_files.sh")
#   $2+  = the caller's "$@"
cross_repo_reexec_or_continue() {
    local helper="$1"; shift

    local project_name=""
    local forwarded=()
    local _argv=("$@")
    local _i=0
    while [[ $_i -lt ${#_argv[@]} ]]; do
        case "${_argv[$_i]}" in
            --project)
                project_name="${_argv[$_i+1]:-}"
                [[ -n "$project_name" ]] || die "--project requires a value"
                _i=$((_i + 2))
                ;;
            *)
                forwarded+=("${_argv[$_i]}")
                _i=$((_i + 1))
                ;;
        esac
    done

    # CROSS_REPO_FORWARDED_ARGV is consumed by callers (e.g. via `set --`)
    # — shellcheck cannot see the cross-script use.
    # shellcheck disable=SC2034
    CROSS_REPO_FORWARDED_ARGV=("${forwarded[@]}")

    [[ -n "$project_name" ]] || return 0

    local resolved
    resolved=$("$_CROSS_REPO_SCRIPTS_DIR/aitask_project_resolve.sh" "$project_name")
    case "$resolved" in
        RESOLVED:*)
            local root="${resolved#RESOLVED:}"
            local target_script="$root/.aitask-scripts/$helper"
            [[ -x "$target_script" ]] || die "Resolved $project_name → $root, but $target_script is missing or not executable"
            cd "$root" || die "Failed to cd into $root"
            exec "$target_script" "${forwarded[@]}"
            ;;
        STALE:*)
            die "Project '$project_name' is registered but its path is stale: ${resolved#STALE:}. Run \`cd /path/to/$project_name && ait projects add\` to refresh."
            ;;
        NOT_FOUND:*)
            die "Project '$project_name' is not registered. Run \`cd /path/to/$project_name && ait projects add\`."
            ;;
        *)
            die "Resolver returned unexpected output: $resolved"
            ;;
    esac
}
