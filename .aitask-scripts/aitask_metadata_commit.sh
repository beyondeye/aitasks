#!/usr/bin/env bash
# aitask_metadata_commit.sh - Commit a shared aitasks/metadata file as its own
# owner (t1677).
#
# t1599_3 made `ait sync`'s pre-sync sweep refuse to commit any dirty file it
# cannot attribute to a task. Correct — but `aitasks/metadata/*` has no derivable
# task id, so nothing else committed those files at all, and an ownerless dirty
# file became a PERMANENT rebase deferral. This helper is the owner: an explicit,
# user-initiated config write commits itself, path-scoped, under a message that
# names the FILE rather than a task.
#
# Usage:
#   aitask_metadata_commit.sh [--allow-new] <path>...
#
# Paths are repo-relative and must live under aitasks/metadata/.
#
# EXPLICIT PATHS ONLY. There is deliberately no --sweep/--all mode: "commit
# everything dirty under aitasks/metadata/" would commit whatever a CONCURRENT
# session was mid-editing, publishing content this process never wrote — the
# raced-publication failure t1599_3 built a whole quarantine to prevent. Every
# caller names the paths it just wrote.
#
# Output (stdout is a data channel — one line per outcome):
#   COMMITTED:<n>:<subject>     n paths committed
#   NOCHANGE                    verified nothing to commit
#   SKIPPED:<path>              user-layer (gitignored) path, ignored
#   REFUSED:<reason>:<path>     out_of_scope | untracked | not_a_file
#   FAILED:<detail>             the commit itself failed
#
# Exit: 0 committed, 2 nothing to commit / refused, 1 commit failed.
#
# NEVER PUSHES. aidocs/framework/tui_conventions.md permits a commit on an
# explicit user-initiated save but not a push, and callers include Textual event
# handlers where a network round-trip would block the UI.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

METADATA_PREFIX="${TASK_DIR:-aitasks}/metadata/"

show_help() {
    cat <<'EOF'
Usage: aitask_metadata_commit.sh [--allow-new] <path>...

Commit one or more shared aitasks/metadata files path-scoped, under a message
naming the file rather than a task. Never pushes.

  --allow-new   Also accept a path that is not tracked yet. Pass it ONLY when
                this invocation actually created the file — derive it from an
                existence check taken before your own write, never hard-code it.

Exit: 0 committed, 2 nothing to commit / refused, 1 commit failed.
EOF
}

# _is_ignored <path> — 0 when git ignores the path (the per-user layer:
# *.local.json, userconfig.yaml, profiles/local/). Those are not an error for a
# caller that passes a whole layer pair; they are simply not ours to commit.
_is_ignored() {
    task_git check-ignore -q -- "$1" 2>/dev/null
}

# _is_tracked <path> — 0 when the path is known to the data branch. A DELETED
# tracked file still answers yes, which is what lets a deletion be committed.
_is_tracked() {
    task_git ls-files --error-unmatch -- "$1" >/dev/null 2>&1
}

main() {
    local allow_new=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --allow-new) allow_new=1; shift ;;
            --help | -h | help) show_help; return 0 ;;
            --*) die "Unknown option: $1 (try --help)" ;;
            *) break ;;
        esac
    done

    if [[ $# -eq 0 ]]; then
        show_help
        return 2
    fi

    local -a paths=() staged_by_us=()
    local p

    for p in "$@"; do
        # Scope check, fail-closed. An absolute path, a `..` escape, or anything
        # outside aitasks/metadata/ is refused rather than normalized: this
        # helper's whole contract is that it can only ever touch shared config.
        case "$p" in
            /*)          printf 'REFUSED:out_of_scope:%s\n' "$p"; return 2 ;;
            */../* | ../* | */..) printf 'REFUSED:out_of_scope:%s\n' "$p"; return 2 ;;
            "$METADATA_PREFIX"*) : ;;
            *)           printf 'REFUSED:out_of_scope:%s\n' "$p"; return 2 ;;
        esac

        if _is_ignored "$p"; then
            printf 'SKIPPED:%s\n' "$p"
            continue
        fi

        if _is_tracked "$p"; then
            paths+=("$p")
            continue
        fi

        # Untracked. task_git_commit_scoped STAGES what it is given, so accepting
        # one by default would silently add local content to the data branch —
        # beyond this helper's "tracked metadata" contract.
        if (( ! allow_new )); then
            printf 'REFUSED:untracked:%s\n' "$p"
            return 2
        fi
        if [[ ! -f "$p" ]]; then
            printf 'REFUSED:not_a_file:%s\n' "$p"
            return 2
        fi
        paths+=("$p")
    done

    if (( ${#paths[@]} == 0 )); then
        printf 'NOCHANGE\n'
        return 2
    fi

    local msg
    msg="$(ait_metadata_commit_message "${paths[@]}")"

    # Stage ONLY the untracked paths — a pathspec cannot name a file git does not
    # know about, so they have no alternative, while a tracked path needs no
    # staging at all because `commit -o` takes worktree content. Recording what we
    # staged is what lets the failure path unstage OUR entries and nobody else's;
    # the .aitask-data index is shared by every session on this machine.
    for p in "${paths[@]}"; do
        if ! _is_tracked "$p"; then
            if task_git add -- "$p" >/dev/null 2>&1; then
                staged_by_us+=("$p")
            fi
        fi
    done

    local rc=0
    task_git_commit_scoped --no-stage "$msg" "${paths[@]}" || rc=$?

    if [[ $rc -ne 0 ]]; then
        # A path left STAGED is worse than a dirty one: it is invisible to the
        # ownerless report and rides along in the next index-wide commit. Scope
        # the cleanup to entries this invocation created — every one was verified
        # untracked before staging, so the reset has no HEAD version to restore.
        if (( ${#staged_by_us[@]} )); then
            task_git reset -q -- "${staged_by_us[@]}" >/dev/null 2>&1 || true
        fi
    fi

    case "$rc" in
        0) printf 'COMMITTED:%d:%s\n' "${#paths[@]}" "$msg"; return 0 ;;
        2) printf 'NOCHANGE\n'; return 2 ;;
        *) printf 'FAILED:git commit failed for %s\n' "${paths[*]}"; return 1 ;;
    esac
}

main "$@"
