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
#   aitask_metadata_commit.sh [--allow-new] [--expect <path>=<file>]... <path>...
#   aitask_metadata_commit.sh --preflight <path>...
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
#   REFUSED:<reason>:<path>     out_of_scope | untracked | not_a_file | changed
#   REFUSED:expect_incomplete   --expect given, but not for every committable path
#   FAILED:<detail>             the commit itself failed
#
# Exit: 0 committed, 2 nothing to commit / refused, 1 commit failed.
#
# --preflight (t1704): INSPECT the destination and write nothing. Added because
# the cross-repo config push (lib/cross_repo_settings.py::apply_push) writes
# ANOTHER repo's tracked config, and deciding what is safe there requires asking
# that repo about itself BEFORE the write. It resolves paths through the same
# scope / ignore / tracked ladder as the commit path, so there is one resolution
# rule rather than a parallel one reimplemented in Python.
#
#   MODE:branch|legacy
#   BRANCH:<name>|DETACHED
#   MIDOP:<state>               emitted ONLY when the data worktree is stuck
#   STATE:<path>:clean|dirty|untracked|ignored|absent
#
# Exit: 0 inspected, 2 scope refusal, 1 git could not be inspected (FAILED:).
#
# --expect <path>=<file> (t1704, repeatable): a compare-and-commit guard. Just
# before the commit, each named path is compared against the bytes the caller
# says it wrote; any mismatch (or a vanished path) answers REFUSED:changed:<path>
# having staged and committed NOTHING. It closes the window in which a
# concurrent writer'"'"'s bytes would otherwise be published under this helper'"'"'s own
# "ait: Update <file>" message — the framework attributing content it never
# wrote, which is exactly what t1599_3'"'"'s quarantine exists to prevent.
#
# FAIL-CLOSED: if --expect is passed at all, EVERY path that survives the
# scope/ignore/tracked filters must have an entry, else REFUSED:expect_incomplete.
# A partially-guarded commit is the shape that looks safe and is not. Omitting
# --expect entirely keeps the original behaviour, so the pre-existing callers
# (settings_app, aitask_board, chatlink/wizard) are untouched.
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
Usage: aitask_metadata_commit.sh [--allow-new] [--expect <path>=<file>]... <path>...
       aitask_metadata_commit.sh --preflight <path>...

Commit one or more shared aitasks/metadata files path-scoped, under a message
naming the file rather than a task. Never pushes.

  --allow-new   Also accept a path that is not tracked yet. Pass it ONLY when
                this invocation actually created the file — derive it from an
                existence check taken before your own write, never hard-code it.

  --expect <path>=<file>
                Compare-and-commit guard (repeatable). Commit only if <path>
                still holds exactly the bytes in <file>; otherwise answer
                REFUSED:changed:<path> and commit nothing. Fail-closed: once
                given, EVERY committable path needs an entry.

  --preflight   Inspect the destination and write nothing. Prints MODE:,
                BRANCH:, an optional MIDOP:, and one STATE:<path>:<state> per
                path. Cannot be combined with a commit.

Exit: 0 committed / inspected, 2 nothing to commit / refused, 1 failed.
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

# _scope_check <path> — the fail-closed scope ladder, shared by both modes so a
# preflight can never inspect a path the commit would refuse (or vice versa).
# Prints the refusal and returns 1; returns 0 when the path is in scope.
_scope_check() {
    case "$1" in
        /*)                   printf 'REFUSED:out_of_scope:%s\n' "$1"; return 1 ;;
        */../* | ../* | */..) printf 'REFUSED:out_of_scope:%s\n' "$1"; return 1 ;;
        "$METADATA_PREFIX"*)  return 0 ;;
        *)                    printf 'REFUSED:out_of_scope:%s\n' "$1"; return 1 ;;
    esac
}

# run_preflight <path>... — inspect and report; write nothing, refuse nothing
# except an out-of-scope path.
#
# Every git call here is read-only, so the whole mode runs with the wedged-
# worktree guard bypassed: reporting `MIDOP:merge` is the entire point, and
# assert_data_worktree_clean would instead DIE on the very state we were asked
# to describe. (check-ignore, which _is_ignored uses, is not on the readonly
# allowlist, so without this a mid-merge destination would kill the preflight.)
run_preflight() {
    local p
    for p in "$@"; do
        _scope_check "$p" || return 2
    done

    export AIT_GIT_SKIP_STATE_CHECK=1

    local mode branch
    mode="$(ait_data_mode)"
    printf 'MODE:%s\n' "$mode"

    # A failing rev-parse is "could not inspect", never "detached": an empty
    # answer must not be reported as a git state we did not observe.
    local br_rc=0
    branch="$(task_git rev-parse --abbrev-ref HEAD 2>/dev/null)" || br_rc=$?
    if [[ $br_rc -ne 0 ]]; then
        printf 'FAILED:cannot resolve HEAD of the task-data worktree\n'
        return 1
    fi
    if [[ -z "$branch" || "$branch" == "HEAD" ]]; then
        printf 'BRANCH:DETACHED\n'
    else
        printf 'BRANCH:%s\n' "$branch"
    fi

    local midop
    midop="$(ait_data_inprogress_state)"
    [[ -n "$midop" ]] && printf 'MIDOP:%s\n' "$midop"

    local st st_rc
    for p in "$@"; do
        if _is_ignored "$p"; then
            printf 'STATE:%s:ignored\n' "$p"
            continue
        fi
        if _is_tracked "$p"; then
            # Same "a failing status is unverified, never clean" rule
            # task_git_commit_scoped states — a dirty file reported as clean is
            # precisely the verdict that would let us overwrite someone's edit.
            st_rc=0
            st="$(task_git status --porcelain -- "$p" 2>/dev/null)" || st_rc=$?
            if [[ $st_rc -ne 0 ]]; then
                printf 'FAILED:cannot inspect status of %s\n' "$p"
                return 1
            fi
            if [[ -n "$st" ]]; then
                printf 'STATE:%s:dirty\n' "$p"
            else
                printf 'STATE:%s:clean\n' "$p"
            fi
            continue
        fi
        if [[ -e "$p" ]]; then
            printf 'STATE:%s:untracked\n' "$p"
        else
            printf 'STATE:%s:absent\n' "$p"
        fi
    done
    return 0
}

main() {
    local allow_new=0 preflight=0 have_expect=0
    local -a expect_specs=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --allow-new) allow_new=1; shift ;;
            --preflight) preflight=1; shift ;;
            --expect)
                [[ $# -ge 2 ]] || die "--expect requires <path>=<file>"
                # Split on the FIRST '=' — the path is the left side, so a path
                # containing '=' cannot be guarded. Metadata filenames do not
                # contain one, and the alternative (splitting on the last '=')
                # would break a TEMP FILE whose name contains one, which the
                # caller does not control.
                case "$2" in
                    *=*) : ;;
                    *) die "--expect argument must be <path>=<file>, got: $2" ;;
                esac
                expect_specs+=("$2")
                have_expect=1
                shift 2 ;;
            --help | -h | help) show_help; return 0 ;;
            --*) die "Unknown option: $1 (try --help)" ;;
            *) break ;;
        esac
    done

    if [[ $# -eq 0 ]]; then
        show_help
        return 2
    fi

    if (( preflight )); then
        # Mutually exclusive with a commit rather than silently ignoring the
        # flags: a caller that passed --expect meant to guard a write, and
        # answering it with an inspection would read as a successful commit.
        if (( allow_new || have_expect )); then
            die "--preflight cannot be combined with --allow-new or --expect"
        fi
        run_preflight "$@"
        return $?
    fi

    local -a paths=()
    local p

    for p in "$@"; do
        # Scope check, fail-closed. An absolute path, a `..` escape, or anything
        # outside aitasks/metadata/ is refused rather than normalized: this
        # helper's whole contract is that it can only ever touch shared config.
        _scope_check "$p" || return 2

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

    # --- Compare-and-commit guard (t1704) --------------------------------
    #
    # Placed HERE: after the committable set is known (so completeness can be
    # checked against it) and BEFORE the trap is armed and anything is staged,
    # so a REFUSED:changed exit trivially leaves the shared .aitask-data index
    # untouched — there is nothing yet to unwind.
    #
    # The residual window is helper-internal, between this cmp and git's own
    # read of the worktree, with no I/O in between. That is as narrow as
    # detect-and-refuse gets; real mutual exclusion needs every writer in the
    # destination repo to share a lock, which is a separate change.
    if (( have_expect )); then
        local spec ep ef seen
        # Fail-closed completeness FIRST. A partially-guarded commit looks safe
        # and is not: the unguarded path is exactly where a racer's bytes would
        # still be published.
        for p in "${paths[@]}"; do
            seen=0
            for spec in "${expect_specs[@]}"; do
                [[ "${spec%%=*}" == "$p" ]] && { seen=1; break; }
            done
            if (( ! seen )); then
                printf 'REFUSED:expect_incomplete\n'
                return 2
            fi
        done

        for spec in "${expect_specs[@]}"; do
            ep="${spec%%=*}"
            ef="${spec#*=}"
            # An expectation naming a path this invocation is not committing is
            # a programmer error in the same family as an incomplete set, and
            # must not pass silently as "all guards matched".
            seen=0
            for p in "${paths[@]}"; do
                [[ "$p" == "$ep" ]] && { seen=1; break; }
            done
            if (( ! seen )); then
                printf 'REFUSED:expect_incomplete\n'
                return 2
            fi
            # A vanished path is a change, not an absence: the caller wrote it
            # and something removed it.
            if [[ ! -f "$ep" ]]; then
                printf 'REFUSED:changed:%s\n' "$ep"
                return 2
            fi
            # cmp -s rather than a hash: no new library (so no test-scaffold
            # baseline entry — see shell_conventions.md), exact for binary
            # content, and aitask_note.sh already establishes it here.
            if ! cmp -s "$ef" "$ep"; then
                printf 'REFUSED:changed:%s\n' "$ep"
                return 2
            fi
        done
    fi

    local msg
    msg="$(ait_metadata_commit_message "${paths[@]}")"

    # Staging, committing and the unstage-on-failure cleanup live once, in
    # lib/task_utils.sh::ait_commit_paths_staging_untracked (t1702) — this script
    # and aitask_task_commit.sh both need them, and duplicating logic this subtle
    # is how one copy silently drifts. The trap is armed HERE rather than inside
    # the library so it cannot clobber a caller's own EXIT trap; it covers the
    # exits the function itself cannot (a `die` inside task_git, or a signal —
    # measured: bash runs an EXIT trap on a fatal SIGTERM too, so EXIT alone
    # covers a killed run and no INT/TERM handler is needed).
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
