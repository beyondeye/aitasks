#!/usr/bin/env bash
# aitask_task_worktree.sh - Record-aware resolution and teardown of a TASK worktree.
#
# Scope: task worktrees only - the `aitask/<task_name>` branch and whatever
# worktree currently holds it. NOT the `.aitask-data` worktree (see `ait git` /
# `ait git-health`) and NOT agentcrew worktrees (see aitask_crew_cleanup.sh).
#
# This is the single canonical classifier for "where does this task's worktree
# actually live". Step 7's deferred fork, the Re-entry Routing reuse check and
# the Task Abort / Step 9 teardown all read it, so a worktree that was moved out
# of aiwork/<task_name> can never be found by one and missed by another (t1548).
#
# Safety contract:
#   * NEVER runs `git worktree prune`. Prune is repo-global: it would discard
#     administrative metadata for unrelated stale worktrees that crash recovery
#     or another task depends on. Worse, pruning a *matching* stale record is
#     what lets the subsequent `git branch -d` succeed, stranding the user's
#     manually-moved directory with no branch pointing at its work.
#   * NEVER uses `git branch -D`. An abort must not silently destroy commits.
#   * NEVER follows a `gitdir:` pointer stored inside a directory it is about to
#     delete. Administrative metadata is resolved from git's own registry only.
#   * Refuses (rather than guesses) whenever git itself is refusing.
#
# Usage:
#   aitask_task_worktree.sh resolve <task_name>
#   aitask_task_worktree.sh remove  <task_name> [--force] [--strict]
#
# resolve - prints exactly one line, state first and path last:
#   NONE
#   USABLE <path>    record matches, path is a directory
#   STALE  <path>    record matches but is prunable / its path is not a directory
#   LOCKED <path>    record carries a `locked` line
#   MAIN   <path>    the matching record IS the main worktree root
#   UNSAFE <pct-encoded-path>   path contains TAB / newline / CR
#
# remove - tears down, re-verifies, then prints three lines:
#   WORKTREE_NONE | WORKTREE_REMOVED <path> | WORKTREE_KEPT <reason> <path>
#   BRANCH_NONE   | BRANCH_DELETED <branch> | BRANCH_KEPT <reason> <branch>
#   CLEAN | PRESERVED | RESIDUE
#
#   worktree reasons: stale_record locked main_worktree dirty unsafe_path unknown
#   branch   reasons: checked_out skipped unmerged_into:<ref> unknown
#
#   --force   pass --force to `git worktree remove` (abort semantics: discard).
#             Omit it for Step 9, where uncommitted work must still block removal.
#   --strict  only CLEAN exits 0; PRESERVED and RESIDUE exit 1. Step 9 uses this
#             so a surviving branch blocks archival instead of being a line of
#             stdout the caller is merely asked to read.
#
# Exit codes:
#   0  resolve: any state.  remove: CLEAN, or PRESERVED without --strict.
#   1  remove: RESIDUE, or PRESERVED with --strict.
#   2  usage error.
#   3  environment error (not a git repository, bare repository, git failed).
#
# On exit 2 and 3 stdout is EMPTY and the diagnostic goes to stderr: a producer
# failure is its own state, never reported as NONE or CLEAN. Callers MUST keep
# the exit status - `read -r state path <<<"$(...)"` succeeds with an empty
# state on a failed run, so an empty parse is indistinguishable from a result
# unless the status is checked. Tests pin the empty-stdout property.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=.aitask-scripts/lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

envdie() { echo "aitask_task_worktree: $1" >&2; exit 3; }
usage() {
    cat <<'EOF' >&2
Usage:
  aitask_task_worktree.sh resolve <task_name>
  aitask_task_worktree.sh remove  <task_name> [--force] [--strict]
EOF
    exit 2
}

# --- Argument parsing -------------------------------------------------------

[[ $# -ge 2 ]] || usage
CMD="$1"; shift
TASK_NAME="$1"; shift
[[ -n "$TASK_NAME" ]] || usage

FORCE=false
STRICT=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)  FORCE=true;  shift ;;
        --strict) STRICT=true; shift ;;
        *) echo "aitask_task_worktree: unknown option '$1'" >&2; usage ;;
    esac
done
case "$CMD" in
    resolve|remove) ;;
    *) echo "aitask_task_worktree: unknown subcommand '$CMD'" >&2; usage ;;
esac
if [[ "$CMD" == "resolve" ]] && { $FORCE || $STRICT; }; then
    echo "aitask_task_worktree: --force / --strict are only valid for 'remove'" >&2
    usage
fi

BRANCH="aitask/$TASK_NAME"
BRANCH_REF="refs/heads/$BRANCH"

# --- Environment ------------------------------------------------------------

git rev-parse --git-dir >/dev/null 2>&1 \
    || envdie "not inside a git repository - refusing to touch anything"
[[ "$(git rev-parse --is-bare-repository 2>/dev/null)" == "false" ]] \
    || envdie "bare repository - task worktrees are not supported here"

GIT_COMMON_DIR="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" \
    || envdie "could not resolve --git-common-dir"
MAIN_ROOT="$(dirname "$GIT_COMMON_DIR")"

# --- Helpers ----------------------------------------------------------------

# Percent-encode a byte string so a control-character path can be printed on one
# line without corrupting the caller's parse. Byte-wise (LC_ALL=C) on purpose.
pct_encode() (
    LC_ALL=C
    local s="$1" out="" i c
    for (( i = 0; i < ${#s}; i++ )); do
        c="${s:i:1}"
        case "$c" in
            [A-Za-z0-9._/~:@+-]) out+="$c" ;;
            *) out+="$(printf '%%%02X' "'$c")" ;;
        esac
    done
    printf '%s' "$out"
)

has_control_char() {
    case "$1" in
        *"$(printf '\t')"*|*"$(printf '\r')"*) return 0 ;;
    esac
    [[ "$1" == *$'\n'* ]] && return 0
    return 1
}

# Write `git worktree list` output to $1 in the safest transport available.
#
# NUL-delimited (--porcelain -z) is the correct parse: on a path containing a
# newline the line-based record splits, and a line parser captures the *prefix* -
# which, if it exists as a directory, is unrelated data this script would then
# try to delete. A temp file is the only transport that preserves NULs: bash
# strips them from command substitution, and process substitution would hide
# git's exit status so a failed listing would read as "no worktrees".
#
# Sets WT_LIST_ZERO=true when the -z form was used.
WT_LIST_ZERO=false
write_worktree_listing() {
    local dest="$1"
    if git worktree list --porcelain -z > "$dest" 2>/dev/null; then
        WT_LIST_ZERO=true
        return 0
    fi
    warn "git worktree list --porcelain -z unavailable (git < 2.36) - falling back to the line parser; records with unparseable lines are refused rather than resolved"
    git worktree list --porcelain > "$dest" \
        || envdie "git worktree list failed - refusing to touch anything"
    WT_LIST_ZERO=false
}

# Classify the record bound to $BRANCH_REF. Sets REC_STATE and REC_PATH.
#
# REC_STATE: NONE | USABLE | STALE | LOCKED | MAIN | UNSAFE
REC_STATE=""
REC_PATH=""
classify_record() {
    local listing field
    listing="$(mktemp "${TMPDIR:-/tmp}/aitask_task_worktree.XXXXXX")" \
        || envdie "could not create a temporary file"
    write_worktree_listing "$listing"

    # Attributes are evaluated at the RECORD boundary, not at the `branch` field:
    # git emits `locked` and `prunable` AFTER `branch`, so deciding on sight of
    # the branch would miss both - and missing `locked` would send a deliberately
    # locked worktree into the forced removal path.
    local cur_path="" cur_locked=false cur_prunable=false cur_hit=false
    local hit_path="" hit_locked=false hit_prunable=false found=false
    local unparseable=false

    _flush_record() {
        if $cur_hit && ! $found; then
            hit_path="$cur_path"; hit_locked=$cur_locked
            hit_prunable=$cur_prunable; found=true
        fi
        cur_path=""; cur_locked=false; cur_prunable=false; cur_hit=false
    }

    if $WT_LIST_ZERO; then
        while IFS= read -r -d '' field; do
            case "$field" in
                "")                   _flush_record ;;
                worktree\ *)          cur_path="${field#worktree }" ;;
                locked|locked\ *)     cur_locked=true ;;
                prunable|prunable\ *) cur_prunable=true ;;
                "$BRANCH_REF_FIELD")  cur_hit=true ;;
            esac
        done < "$listing"
    else
        # Fallback for git < 2.36 (no `-z`). Fail closed on any line that is not a
        # known key: on a newline-containing path the continuation line lands here
        # and the record must not be trusted.
        while IFS= read -r field; do
            case "$field" in
                "")                   _flush_record ;;
                worktree\ *)          cur_path="${field#worktree }" ;;
                HEAD\ *|detached|bare) ;;
                locked|locked\ *)     cur_locked=true ;;
                prunable|prunable\ *) cur_prunable=true ;;
                branch\ *)
                    [[ "$field" == "$BRANCH_REF_FIELD" ]] && cur_hit=true
                    ;;
                *) unparseable=true ;;
            esac
        done < "$listing"
    fi
    _flush_record
    unset -f _flush_record
    rm -f "$listing"

    if ! $found; then
        if $unparseable; then
            # An unknown line means a record we cannot trust; if it belongs to our
            # branch we would otherwise resolve a prefix path. Fail closed.
            REC_STATE="UNSAFE"; REC_PATH=""
            return 0
        fi
        REC_STATE="NONE"; REC_PATH=""
        return 0
    fi

    REC_PATH="$hit_path"
    if has_control_char "$hit_path"; then REC_STATE="UNSAFE"; return 0; fi
    if [[ "$hit_path" == "$MAIN_ROOT" ]];  then REC_STATE="MAIN";   return 0; fi
    if $hit_locked;                        then REC_STATE="LOCKED"; return 0; fi
    if $hit_prunable || [[ ! -d "$hit_path" ]]; then REC_STATE="STALE"; return 0; fi
    REC_STATE="USABLE"
}
BRANCH_REF_FIELD="branch $BRANCH_REF"

branch_exists() { git show-ref --verify --quiet "$BRANCH_REF"; }

# Administrative directory for a REGISTERED worktree, resolved from git's own
# registry. Never reads the target directory's own `.git` file: an unregistered
# or tampered one can name <repo_root>/.git, and following it would delete the
# user's repository.
admin_dir_for() {
    local target_gitfile="$1/.git" d
    for d in "$GIT_COMMON_DIR"/worktrees/*/; do
        [[ -f "${d}gitdir" ]] || continue
        if [[ "$(cat "${d}gitdir")" == "$target_gitfile" ]]; then
            local resolved="${d%/}"
            # Containment guard: must be a direct child of <common>/worktrees.
            [[ "$(dirname "$resolved")" == "$GIT_COMMON_DIR/worktrees" ]] || return 1
            printf '%s' "$resolved"
            return 0
        fi
    done
    return 1
}

# --- resolve ----------------------------------------------------------------

cmd_resolve() {
    classify_record
    case "$REC_STATE" in
        NONE)   printf 'NONE\n' ;;
        UNSAFE) printf 'UNSAFE %s\n' "$(pct_encode "$REC_PATH")" ;;
        *)      printf '%s %s\n' "$REC_STATE" "$REC_PATH" ;;
    esac
}

# --- remove -----------------------------------------------------------------

cmd_remove() {
    # Once the target directory is unlinked this process's cwd may no longer
    # exist and every later git call fails. Stand in the main worktree root.
    cd "$MAIN_ROOT" || envdie "could not enter the main worktree root '$MAIN_ROOT'"

    classify_record

    local wt_line="" br_line="" verdict="CLEAN"
    local skip_branch=false

    case "$REC_STATE" in
        STALE|LOCKED|MAIN|UNSAFE)
            # Refusals. Touch nothing, and do NOT attempt the branch delete: for
            # STALE it is the surviving record that makes `git branch -d` refuse,
            # so not pruning keeps the user's work reachable by construction.
            local reason display
            case "$REC_STATE" in
                STALE)  reason="stale_record";  display="$REC_PATH" ;;
                LOCKED) reason="locked";        display="$REC_PATH" ;;
                MAIN)   reason="main_worktree"; display="$REC_PATH" ;;
                UNSAFE) reason="unsafe_path";   display="$(pct_encode "$REC_PATH")" ;;
            esac
            wt_line="WORKTREE_KEPT $reason $display"
            skip_branch=true
            verdict="RESIDUE"
            ;;
        USABLE|NONE)
            local -a candidates=()
            [[ "$REC_STATE" == "USABLE" ]] && candidates+=("$REC_PATH")
            local conventional="$MAIN_ROOT/aiwork/$TASK_NAME"
            if [[ -d "$conventional" && "$conventional" != "${candidates[0]:-}" ]]; then
                candidates+=("$conventional")
            fi

            if [[ ${#candidates[@]} -eq 0 ]]; then
                wt_line="WORKTREE_NONE"
            else
                local removed_path="" kept_path="" kept_reason=""
                local target rc
                for target in "${candidates[@]}"; do
                    rc=0
                    if $FORCE; then
                        git worktree remove "$target" --force >/dev/null 2>&1 || rc=$?
                    else
                        git worktree remove "$target" >/dev/null 2>&1 || rc=$?
                    fi
                    if [[ $rc -eq 0 && ! -e "$target" ]]; then
                        [[ -n "$removed_path" ]] || removed_path="$target"
                        continue
                    fi
                    # `git worktree remove` declined. Without --force that is the
                    # documented dirty-tree refusal and we honour it.
                    if ! $FORCE && [[ -d "$target" ]]; then
                        kept_path="$target"; kept_reason="dirty"
                        continue
                    fi
                    # Forced fallback. Only for a path that is not the main root
                    # and is control-character free.
                    if [[ -z "$target" || "$target" == "$MAIN_ROOT" ]] || has_control_char "$target"; then
                        kept_path="$target"; kept_reason="unknown"
                        continue
                    fi
                    if [[ "$target" == "$REC_PATH" ]]; then
                        # Registered: clean the directory, then its admin entry as
                        # named by git's registry (never by the target's own file).
                        local admin=""
                        admin="$(admin_dir_for "$target" || true)"
                        rm -rf "$target"
                        [[ -n "$admin" ]] && rm -rf "$admin"
                    elif [[ "$target" == "$conventional" ]]; then
                        # Unregistered leftover: remove that directory and nothing
                        # else. No metadata handling, no pointer following.
                        rm -rf "$target"
                    else
                        kept_path="$target"; kept_reason="unknown"
                        continue
                    fi
                    if [[ -e "$target" ]]; then
                        kept_path="$target"; kept_reason="unknown"
                    else
                        [[ -n "$removed_path" ]] || removed_path="$target"
                    fi
                done

                if [[ -n "$kept_path" ]]; then
                    wt_line="WORKTREE_KEPT $kept_reason $kept_path"
                    skip_branch=true
                    verdict="RESIDUE"
                elif [[ -n "$removed_path" ]]; then
                    wt_line="WORKTREE_REMOVED $removed_path"
                else
                    wt_line="WORKTREE_NONE"
                fi
            fi
            ;;
    esac

    # --- branch ---
    if ! branch_exists; then
        br_line="BRANCH_NONE"
    elif $skip_branch; then
        br_line="BRANCH_KEPT skipped $BRANCH"
        verdict="RESIDUE"
    else
        if git branch -d "$BRANCH" >/dev/null 2>&1; then
            br_line="BRANCH_DELETED $BRANCH"
        else
            classify_record
            local reason
            if [[ "$REC_STATE" != "NONE" ]]; then
                reason="checked_out"
            else
                local head_ref anc_rc=0
                head_ref="$(git symbolic-ref --short -q HEAD || echo HEAD)"
                git merge-base --is-ancestor "$BRANCH_REF" HEAD >/dev/null 2>&1 || anc_rc=$?
                if [[ $anc_rc -eq 1 ]]; then
                    reason="unmerged_into:$head_ref"
                else
                    reason="unknown"
                fi
            fi
            br_line="BRANCH_KEPT $reason $BRANCH"
            if [[ "$reason" == unmerged_into:* && "$verdict" == "CLEAN" ]]; then
                verdict="PRESERVED"
            else
                verdict="RESIDUE"
            fi
        fi
    fi

    printf '%s\n%s\n%s\n' "$wt_line" "$br_line" "$verdict"

    case "$verdict" in
        CLEAN)     return 0 ;;
        PRESERVED) $STRICT && return 1; return 0 ;;
        *)         return 1 ;;
    esac
}

case "$CMD" in
    resolve) cmd_resolve ;;
    remove)  cmd_remove ;;
esac
