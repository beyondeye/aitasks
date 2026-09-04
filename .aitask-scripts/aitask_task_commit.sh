#!/usr/bin/env bash
# aitask_task_commit.sh - Commit task / plan files path-scoped (t1702).
#
# The task/plan-file analogue of aitask_metadata_commit.sh. `ait board` wrote
# task and plan files and committed them with a pathspec-less `git commit`
# against the SHARED .aitask-data index, so whatever another session had staged
# rode along under the board's message — the same defect class t1599 closed for
# `ait sync`, aitask_pick_own.sh, aitask_create.sh and aitask_fold_mark.sh, and
# that t1677 refused to copy into Python.
#
# Usage:
#   aitask_task_commit.sh -m <message> <path>...
#
# Paths are repo-relative and must live under aitasks/ or aiplans/.
#
# EXPLICIT PATHS ONLY, and for the same reason as the metadata helper: "commit
# everything dirty under aitasks/" would publish whatever a CONCURRENT session
# was mid-editing. Every caller names the paths it just wrote — and it must name
# ALL of them, including files it edited as a side effect (a parent task's
# children_to_implement, a revived folded task), not only the ones it deleted:
# a write this commit drops is left ownerless, which is what `ait sync`'s
# pre-sync sweep quarantines permanently.
#
# STAGING IS PART OF THE CONTRACT, not an implementation detail. A scoped commit
# alone is only half the fix: `git rm` stages, and a staged entry sitting in the
# shared index is collectable by anyone's index-wide commit. Callers delete from
# the worktree and let this helper's `commit -o` record it.
#
# Differences from aitask_metadata_commit.sh, all deliberate:
#   * the message is CALLER-SUPPLIED (-m). Delete / rename / commit-dialog
#     messages differ, so there is nothing to derive the way
#     ait_metadata_commit_message() derives one from a filename.
#   * an untracked-but-existing path is accepted with NO --allow-new flag. A new
#     task file is a normal board commit (the board's own modified-file scan
#     collects `??` entries), so the gate would be always-passed dead weight;
#     the aitasks//aiplans/ scope check is what bounds this helper.
#
# Output (stdout is a data channel — one line per outcome):
#   COMMITTED:<n>:<subject>     n paths committed
#   NOCHANGE                    verified nothing to commit
#   SKIPPED:unknown:<path>      neither tracked nor on disk, ignored
#   REFUSED:out_of_scope:<path> outside aitasks/ or aiplans/, absolute, or ..
#   FAILED:<detail>             the commit itself failed
#
# Exit: 0 committed, 2 nothing to commit / refused, 1 commit failed.
#
# NEVER PUSHES. aidocs/framework/tui_conventions.md permits a commit on an
# explicit user-initiated gesture but not a push, and the callers are Textual
# event handlers where a network round-trip would block the UI.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

TASK_PREFIX="${TASK_DIR:-aitasks}/"
PLAN_PREFIX="${PLAN_DIR:-aiplans}/"

show_help() {
    cat <<'EOF'
Usage: aitask_task_commit.sh -m <message> <path>...

Commit one or more task / plan files path-scoped, under the given message.
Never pushes.

Paths must be repo-relative and under aitasks/ or aiplans/. A path that is
neither tracked nor present on disk is skipped (there is nothing to commit for
it, and naming it would abort the whole commit).

Exit: 0 committed, 2 nothing to commit / refused, 1 commit failed.
EOF
}

# _is_tracked <path> — 0 when the path is known to the data branch. A DELETED
# tracked file still answers yes, which is what lets a deletion be committed.
_is_tracked() {
    task_git ls-files --error-unmatch -- "$1" >/dev/null 2>&1
}

main() {
    local msg=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -m | --message)
                [[ $# -ge 2 ]] || die "-m requires a message"
                msg="$2"; shift 2 ;;
            --help | -h | help) show_help; return 0 ;;
            --) shift; break ;;
            --*) die "Unknown option: $1 (try --help)" ;;
            *) break ;;
        esac
    done

    if [[ -z "$msg" || $# -eq 0 ]]; then
        show_help
        return 2
    fi

    local -a paths=()
    local p

    # Path classification. The four cases below are measured, not assumed
    # (t1702 pre-phase probe against a scratch repo):
    #   tracked, deleted from the worktree → `commit -o` records the deletion
    #                                        with an EMPTY index. No staging.
    #   tracked, present                   → `commit -o` takes worktree content.
    #                                        No staging.
    #   untracked, present                 → `commit -o` fails, "pathspec did not
    #                                        match any file(s) known to git",
    #                                        UNTIL it is staged. Stage it.
    #   untracked, absent                   → same failure, and staging cannot fix
    #                                        it. One such path would abort the
    #                                        WHOLE commit, so drop it instead.
    # (And `commit -o` with an EMPTY pathspec is fatal — exit 128 — which is the
    # fail-loud counterpart to a bare `git commit` silently taking the index.)
    for p in "$@"; do
        # Scope check, fail-closed. An absolute path, a `..` escape, or anything
        # outside aitasks//aiplans/ is refused rather than normalized: this
        # helper's whole contract is that it can only ever touch task data.
        case "$p" in
            /*)                   printf 'REFUSED:out_of_scope:%s\n' "$p"; return 2 ;;
            */../* | ../* | */..) printf 'REFUSED:out_of_scope:%s\n' "$p"; return 2 ;;
            "$TASK_PREFIX"* | "$PLAN_PREFIX"*) : ;;
            *)                    printf 'REFUSED:out_of_scope:%s\n' "$p"; return 2 ;;
        esac

        if _is_tracked "$p" || [[ -f "$p" ]]; then
            paths+=("$p")
        else
            printf 'SKIPPED:unknown:%s\n' "$p"
        fi
    done

    if (( ${#paths[@]} == 0 )); then
        printf 'NOCHANGE\n'
        return 2
    fi

    # Staging, committing and the unstage-on-failure cleanup live once, in
    # lib/task_utils.sh (shared with aitask_metadata_commit.sh). The trap is
    # armed HERE rather than inside the library so it cannot clobber a caller's
    # own EXIT trap; it covers the exits the function itself cannot (a `die`
    # inside task_git, or a signal).
    #
    # EXIT alone is enough — no INT/TERM handler. Measured: bash runs an EXIT
    # trap on a fatal SIGTERM too, even at default disposition, so a killed run
    # still unwinds. Adding INT/TERM handlers here changed nothing observable,
    # so they are deliberately absent rather than shipped unfalsifiable.
    trap 'ait_unstage_staged_by_us' EXIT

    local rc=0
    ait_commit_paths_staging_untracked "$msg" "${paths[@]}" || rc=$?

    case "$rc" in
        0) printf 'COMMITTED:%d:%s\n' "${#paths[@]}" "$msg"; return 0 ;;
        2) printf 'NOCHANGE\n'; return 2 ;;
        *) printf 'FAILED:git commit failed for %s\n' "${paths[*]}"; return 1 ;;
    esac
}

main "$@"
