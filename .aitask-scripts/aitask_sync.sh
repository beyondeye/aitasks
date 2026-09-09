#!/usr/bin/env bash
# aitask_sync.sh - Bidirectional sync of task data with remote
#
# Supports both data-branch mode (.aitask-data worktree) and legacy mode
# (tasks on main branch). Auto-commits uncommitted task changes, fetches,
# rebases, and pushes.
#
# Usage:
#   ./.aitask-scripts/aitask_sync.sh            # Interactive mode (colored output)
#   ./.aitask-scripts/aitask_sync.sh --batch    # Structured output for scripting
#
# Batch output protocol (single line on stdout):
#   SYNCED                     Both push and pull completed
#   PUSHED                     Local changes pushed, nothing to pull
#   PULLED                     Remote changes pulled, nothing to push
#   NOTHING                    Already up-to-date
#   CONFLICT:<file1>,<file2>   Merge conflicts detected (rebase aborted)
#   AUTOMERGED                 Conflicts detected but all auto-resolved
#   NO_NETWORK                 Fetch/push timed out or failed
#   NO_REMOTE                  No remote configured
#   DEFERRED:<reason>[:<detail>]  Sync deliberately did less than a full cycle
#                              and this is NOT an error. Closed reason set:
#                              publication_blocked, protected_dirty,
#                              worktree_wedged. Split on the FIRST colon only;
#                              <detail> is free text and may contain colons.
#   ERROR:<message>            Unexpected error
#
# CONTINUATION LINES. A `DEFERRED:protected_dirty` status is followed by one
# line per protected file — the whole snapshot, so a consumer never has to
# re-derive locks or the dirty set for itself:
#
#   DEFERRED_FILE:<sub_reason>|<task>|<path>|<tree_state>|<holder>|<email>|
#                 <host>|<pid>|<pane>|<pane_state>|<action>
#
# path/action/email/host/pane are percent-encoded (%25 %7C %0A %0D); the rest
# are closed vocabularies validated by the parser. The status is still the FIRST
# line and only the first, so a consumer reading one line is unaffected.
# See lib/sync_action_runner.py (DeferredFile) for the authoritative field list;
# `show_help` carries the user-facing summary of the same thing.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/pid_anchor.sh
source "$SCRIPT_DIR/lib/pid_anchor.sh"        # lock_holder_liveness (the t1466 seam)
# shellcheck source=lib/stale_lock.sh
source "$SCRIPT_DIR/lib/stale_lock.sh"        # ait_lock_dir
# shellcheck source=lib/registry_lock.sh
source "$SCRIPT_DIR/lib/registry_lock.sh"     # registry_lock_acquire/release
# task_automerge.sh is THE conflict-resolution engine, shared with
# lib/task_utils.sh::_task_pull_rebase since t1727. It depends on _ait_data_git
# and _ait_detect_data_worktree from task_utils.sh (sourced above) and on
# resolve_python; both are already loaded by the time we get here.
# shellcheck source=lib/task_automerge.sh
source "$SCRIPT_DIR/lib/task_automerge.sh"

# --- Configuration ---
BATCH_MODE=false
NETWORK_TIMEOUT=10
# Opt-ins for the auto-commit sweep (t1599_3). All three default OFF: each one
# trades safety for availability, and that call is the operator's to make
# explicitly, never a silent consequence of an outage or a timer.
COMMIT_UNOWNED=false
ASSUME_UNLOCKED=false
RELEASE_QUARANTINE=false
# Commit-on-behalf (t1725_3). All three default OFF and are only ever set by an
# explicit operator action or by the syncer's per-file confirmation.
#   COMMIT_FOR_TASKS  ids whose OWN live session's edits may be committed
#   EXPECT_PATHS      the exact dirty set the caller showed the user
#   REQUIRE_WAITING   refuse unless the holder's pane is parked on a prompt
COMMIT_FOR_TASKS=()
EXPECT_PATHS=()
EXPECT_PATHS_SET=false
REQUIRE_WAITING=false

# --- Auto-merge support (best-effort) ---
# The engine lives in lib/task_automerge.sh and resolves its own python + driver
# lazily. Point its progress channel at iinfo_err so interactive `ait sync`
# keeps its per-file "Auto-merged: <f>" lines and `--batch` stays silent —
# unchanged from when those lines were emitted inline. Failures never come
# through here; they go to warn() and are never suppressed.
# shellcheck disable=SC2034  # consumed by lib/task_automerge.sh via indirect call
AIT_AUTOMERGE_PROGRESS_FN=iinfo_err

# --- Help ---
show_help() {
    cat <<'EOF'
Usage: aitask_sync.sh [options]

Sync task data with remote: auto-commit local changes, fetch, rebase,
and push. Works in both data-branch mode (.aitask-data worktree) and
legacy mode (tasks on main branch).

Options:
  --batch               Structured output for scripting (no colors, no prompts)
  --commit-unowned      Auto-commit files with no derivable task owner
  --assume-unlocked     Sweep even when the lock branch cannot be read
  --release-quarantine  Publish withheld commits (see below)
  --commit-for-task <id>[,<id>...]
                        Commit the dirty files of a task whose OWN live session
                        holds it. Only ever your own verified session (same host
                        AND same userconfig email as the lock); any other holder,
                        including one whose identity cannot be verified, is
                        refused. See "Committing on a live session's behalf".
  --expect-path <path>  Repeatable. The exact dirty paths you were shown; if the
                        group differs at commit time the group is skipped. Give
                        one --expect-path per file, percent-encoded -- NOT a
                        comma-separated list, since a comma is a legal character
                        in a path.
  --require-waiting     With --commit-for-task, refuse unless the holding
                        session is parked on a prompt. Fails CLOSED: if the pane
                        cannot be probed the group is skipped.
  --help, -h            Show this help

Interactive mode:
  Shows colored progress messages. On merge conflicts, opens $EDITOR
  (default: nano) for each conflicted file, then continues the rebase.

Batch output protocol (single line on stdout):
  SYNCED                     Both push and pull completed
  PUSHED                     Local changes pushed, nothing to pull
  PULLED                     Remote changes pulled, nothing to push
  NOTHING                    Already up-to-date
  CONFLICT:<file1>,<file2>   Merge conflicts (rebase aborted in batch)
  AUTOMERGED                 Conflicts detected but all auto-resolved
  NO_NETWORK                 Fetch/push timed out or failed
  NO_REMOTE                  No remote configured
  DEFERRED:<reason>[:<detail>]  Deliberately did less than a full cycle; not an
                             error. Reasons: publication_blocked,
                             protected_dirty, worktree_wedged.
  ERROR:<message>            Unexpected error

  A protected_dirty deferral is followed by one continuation line per file:

  DEFERRED_FILE:<sub_reason>|<task>|<path>|<tree_state>|<holder>|<email>|<host>|
                <pid>|<pane>|<pane_state>|<action>

  <holder> is self|other|remote|unverified|none and <tree_state> is
  tracked|untracked|unknown. Textual fields are percent-encoded (%25 %7C %0A
  %0D). The status line is still the first line, so a reader that takes only
  that one is unaffected. The same detail is also printed on stderr in prose.

Committing on a live session'"'"'s behalf:
  The sweep never commits a file whose task is held by another live session --
  that is the correct outcome, and it stays. But when the holder is YOUR OWN
  session, parked on a question you have walked away from, the deferral names it
  and offers the way out:

      ./ait sync --commit-for-task <id>

  This commits that task'"'"'s dirty files exactly as they stand right now. The
  sweep cannot tell a session that is waiting from one that is mid-edit and
  momentarily quiet, so the flag is deliberately never automatic and prints a
  warning when it fires. It bypasses no other guard: the state re-check and the
  publication quarantine both still apply.

Auto-commit policy:
  The pre-sync sweep groups dirty task/plan files by their OWNING task and
  commits each group path-scoped, so a commit never carries another task's
  file. It skips (and reports on stderr) anything it cannot vouch for: a file
  whose task is locked by a live -- or unverifiable -- session, a file with no
  derivable owner, an ambiguous cross-task rename, and everything at all when
  the lock branch is unreadable. Skipped files stay dirty, which is safe.

  --commit-unowned      Also commit files with no derivable task id (e.g.
                        aitasks/metadata/*), under a message that names no task.
  --assume-unlocked     Treat an UNREADABLE lock branch as "nothing is locked".
                        Availability over safety -- an outage can coincide with
                        a live editor, so this is deliberately never automatic.
  --release-quarantine  Publish commits withheld because a file was rewritten
                        while they were being made. Nothing else releases them:
                        age never does, because an expiry would publish exactly
                        the raced content the hold exists to withhold.
EOF
}

# --- Argument parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --batch)  BATCH_MODE=true; shift ;;
        --commit-unowned)     COMMIT_UNOWNED=true; shift ;;
        --assume-unlocked)    ASSUME_UNLOCKED=true; shift ;;
        --release-quarantine) RELEASE_QUARANTINE=true; shift ;;
        --commit-for-task)
            [[ $# -ge 2 ]] || die "--commit-for-task needs an id (or comma-separated ids)"
            IFS=',' read -r -a _cft <<< "$2"
            COMMIT_FOR_TASKS+=("${_cft[@]}")
            shift 2 ;;
        # REPEATABLE, one path per argument — never a CSV. A comma is a legal
        # character in a git path and _pct_encode deliberately leaves it alone,
        # so joining a list on commas would split a legal path and fail every
        # scope check that follows.
        --expect-path)
            [[ $# -ge 2 ]] || die "--expect-path needs a percent-encoded path"
            # Stored ENCODED and decoded at use time: this loop runs before the
            # function definitions below, so _pct_decode does not exist yet.
            EXPECT_PATHS+=("$2")
            EXPECT_PATHS_SET=true
            shift 2 ;;
        --require-waiting) REQUIRE_WAITING=true; shift ;;
        --help|-h) show_help; exit 0 ;;
        *) die "Unknown option: $1. Use --help for usage." ;;
    esac
done

# --- Portable timeout wrapper ---
# Uses coreutils timeout if available, falls back to background process watchdog.
# Returns 124 on timeout (same as coreutils timeout).
# Note: Cannot use `timeout task_git` because task_git is a shell function.
# Instead, we build the raw git command args respecting the data worktree.
_git_with_timeout() {
    _ait_detect_data_worktree
    local git_args=()
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git_args=(-C "$_AIT_DATA_WORKTREE")
    fi
    git_args+=("$@")

    if command -v timeout &>/dev/null; then
        timeout "$NETWORK_TIMEOUT" git "${git_args[@]}"
    else
        # macOS fallback: background process with watchdog
        git "${git_args[@]}" &
        local pid=$!
        local i=0
        while kill -0 "$pid" 2>/dev/null && [[ $i -lt $NETWORK_TIMEOUT ]]; do
            sleep 1
            i=$((i + 1))
        done
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
            return 124
        fi
        wait "$pid"
    fi
}

# --- Output helpers ---
batch_out() {
    if [[ "$BATCH_MODE" == true ]]; then
        echo "$1"
    fi
}

# A CONTINUATION line: extra structured detail written AFTER a status line that
# batch_out already emitted. Deliberately NOT batch_out, for two reasons:
#
#   1. tests/test_sync_action_runner.py's _emitted_tokens scan reads every
#      `batch_out "<literal>"` in this file as a declared STATUS token. A detail
#      line routed through batch_out would be scanned as one and fail the
#      closed-vocabulary contract.
#   2. parse_sync_output takes the status from the FIRST non-empty line only, so
#      a detail line must never be able to occupy that position.
#
# Emitted only from _emit_protected_deferral, never merely because records
# exist — several existing tests assert `not_contains "DEFERRED"` over the whole
# stdout of runs that HAVE protected records and correctly do not defer.
batch_detail() {
    if [[ "$BATCH_MODE" == true ]]; then
        echo "$1"
    fi
}

# Only show interactive messages in non-batch mode
iinfo() {
    if [[ "$BATCH_MODE" == false ]]; then
        info "$1"
    fi
}

# Interactive info routed to STDERR. For use inside functions whose STDOUT is a
# data channel — a progress line written there is parsed by the caller as a
# conflicted filename and the interactive loop then opens $EDITOR on it. This is
# what AIT_AUTOMERGE_PROGRESS_FN points at, so lib/task_automerge.sh's per-file
# notices keep landing on stderr and stay silent in --batch.
iinfo_err() {
    if [[ "$BATCH_MODE" == false ]]; then
        info "$1" >&2
    fi
}

iwarn() {
    if [[ "$BATCH_MODE" == false ]]; then
        warn "$1"
    fi
}

isuccess() {
    if [[ "$BATCH_MODE" == false ]]; then
        success "$1"
    fi
}

# --- Check for remote ---
check_remote() {
    if ! task_git remote get-url origin &>/dev/null; then
        batch_out "NO_REMOTE"
        if [[ "$BATCH_MODE" == false ]]; then
            warn "No remote configured"
        fi
        exit 0
    fi
}

# --- Auto-commit uncommitted task/plan changes (t1599_3) ---
#
# This sweep is INTENTIONAL — its job is to leave the worktree clean so the later
# `pull --rebase` can run — so path-scoping alone is not the fix. It used to
# `add aitasks/ aiplans/` and then commit the WHOLE index, so any file another
# session was mid-edit on was swept into a commit whose message named a
# different task (18 of 66 sync auto-commits on the live data branch carried
# more than two task/plan files).
#
# It now groups the dirty set by OWNING task, commits each group path-scoped
# under a message naming its real task, and refuses to commit anything it cannot
# vouch for. Everything below is arranged so this function NEVER aborts and
# always returns 0: under `set -euo pipefail` a stray non-zero would exit the
# script with no stdout, and every consumer reads empty stdout as
# `ERROR: empty output from sync script` (the syncer escalates that into an
# offer to spawn a code agent).

# Outcome sets. These are two ORTHOGONAL non-success outcomes and must not share
# a flag — see the guards in main():
#   PROT_*               files we could not commit are still dirty. Blocks the
#                        REBASE — see _rebase_blocked for exactly when.
#   PUBLICATION_BLOCKED  we made a commit whose content we cannot vouch for.
#                        Blocks the PUSH, regardless of remote_ahead — the race
#                        advances refs/heads/aitask-locks, never aitask-data, so
#                        remote_ahead == 0 is its NORMAL shape and a
#                        rebase-gated guard would detect it and push anyway.
#
# The protection record is PER FILE, not per skip event (t1725_3). It used to be
# a flat list of reason strings, which is why the deferral could only ever say
# "N file(s) held by other sessions": the path, the owner, the holder and the
# remedy were all computed and then thrown away at the wire. Every consumer
# (syncer, board) now gets the whole snapshot — see _emit_protected_deferral.
#
# ELEVEN PARALLEL ARRAYS, APPENDED IN LOCKSTEP. Only _protect() may append, and
# it appends to all of them in one place; a per-call-site append would let them
# drift in length, and a short read under `set -u` aborts the script with empty
# stdout — the exact failure tests/test_sync_protect_paths.sh characterizes.
PROT_REASON=()      # closed set: the _protect "<reason>" literals
PROT_TASK=()        # owning task id, or "" for a path-less protection
PROT_PATH=()        # repo-relative path, or "" for a path-less protection
PROT_STATE=()       # tracked | untracked | unknown
PROT_HOLDER=()      # self | other | remote | unverified | none
PROT_EMAIL=()       # lock's locked_by, when known
PROT_HOST=()        # lock's hostname, when known
PROT_PID=()         # lock's pid, when known
PROT_PANE=()        # always "" here; t1725_4 fills it
PROT_PANE_STATE=()  # always "" here; t1725_4 fills it
PROT_ACTION=()      # the prescriptive line: what would clear this file
PUBLICATION_BLOCKED=()
declare -A PATH_STATE=()
SKIP_REPORT=()
QUARANTINE_HELD=()

_note_skip() { SKIP_REPORT+=("$1"); }

# --- test-only seams -------------------------------------------------------
#
# Two boundaries in this file are only reachable by winning a race against
# another process, so they cannot be driven by an ordinary fixture. A git
# `pre-commit` hook is NOT usable for the second one: under `commit --only` git
# runs prepare_index() and writes the tree BEFORE prepare_to_commit() invokes
# the hook, so a hook that rewrites the file cannot change the committed bytes —
# the recorded hash would still match and the publication guard would never
# fire, giving a test that passes while proving nothing.
#
# The seams are inert in production by construction: an env var alone can never
# enable them, only an env var TOGETHER with a marker file in the lock base.
# NEVER create that file in a real lock base. Same gate shape as
# aitask_merge_task.sh:40-45.
#
#   pre_commit_phase   after the dirty scan + first lock enumeration, BEFORE the
#                      5a.2 CAS re-enumeration      (proves the CAS fires)
#   pre_group_commit   after the 5a.3 state re-check, IMMEDIATELY before the
#                      commit                       (proves the publication guard)
#   pre_push           immediately before the FIRST push, so a hook can advance
#                      the remote in the window between main's rebase gate and
#                      the push       (proves do_push re-gates on fresh inputs)
_sync_test_seams_enabled() {
    local base
    base="$(dirname "$(ait_lock_dir data_index)")" || return 1
    [[ -f "$base/.ait_sync_test_seams" ]]
}
_sync_test_seam() {
    local point="$1" var="AIT_SYNC_SEAM_${1}"
    [[ -n "${!var:-}" ]] || return 0
    _sync_test_seams_enabled || return 0
    warn "aitask_sync: TEST SEAM ACTIVE - running ${point} hook"
    eval "${!var}" || true
    return 0
}

# _protect <reason> <task> <path> <tree_state> <human line>
#
# <task> and <path> are "" for a path-less protection (scan_failed,
# lock_contended), whose <tree_state> is `unknown`. Per-task protections call
# this ONCE PER PATH of that task, so the record set is per file.
#
# The holder columns are resolved here rather than by the caller: every caller
# that knows a task id also wants the same classification, and duplicating it
# per call site is how the "held by other sessions" text got out of step with
# what the lock actually said.
_protect() {
    local reason="$1" task="$2" path="$3" state="$4" line="$5"
    local holder="none" email="" host="" pid=""
    if [[ -n "$task" && "$task" != "__unowned__" ]]; then
        holder="$(_holder_class "$task")"
        email="${LOCK_EMAIL[$task]:-}"
        host="${LOCK_HOST[$task]:-}"
        pid="${LOCK_PID[$task]:-}"
    fi
    PROT_REASON+=("$reason")
    PROT_TASK+=("$task")
    PROT_PATH+=("$path")
    PROT_STATE+=("$state")
    PROT_HOLDER+=("$holder")
    PROT_EMAIL+=("$email")
    PROT_HOST+=("$host")
    PROT_PID+=("$pid")
    PROT_PANE+=("")
    PROT_PANE_STATE+=("")
    PROT_ACTION+=("$line")
    _note_skip "$line"
}

# Resolve the git-dir that owns the data worktree, falling back to this repo's
# in legacy mode. Used for state that must NOT live under aitasks/ — putting it
# there would make it the very ownerless-dirty-file problem this sweep skips.
_sync_gitdir() {
    local gd
    gd="$(_ait_data_gitdir)"
    if [[ -z "$gd" ]]; then
        gd="$(git rev-parse --git-dir 2>/dev/null)" || gd=".git"
    fi
    printf '%s' "${gd:-.git}"
}

_quarantine_path() { printf '%s/ait-sync-quarantine' "$(_sync_gitdir)"; }

# A git path may contain ANY byte except NUL — including `|` and a newline, both
# of which are legal and both of which would corrupt the `|`-delimited,
# line-based quarantine record below (a mangled path is then checked against the
# wrong file, which can release a hold that should stand). Percent-encode the
# three characters that carry meaning in that record; everything else is passed
# through, so the common case stays readable in the file.
#
# CR is encoded for the SAME reason as LF, not as an afterthought: the
# DEFERRED_FILE: records these fields travel in are consumed by Python, and a
# raw CR would be read as a line boundary there (and would make the stderr
# report and this persisted record unreadable besides). The parser splits on LF
# alone precisely so this codec does not have to chase every character
# `str.splitlines()` recognises — see lib/sync_action_runner.py.
#
# Decode order matters: `%25` LAST, so a path that literally contained "%7C"
# (encoded "%257C") does not decode twice.
_pct_encode() {
    local sVar="$1" out="" c i
    for ((i = 0; i < ${#sVar}; i++)); do
        c="${sVar:i:1}"
        case "$c" in
            '%')   out+='%25' ;;
            '|')   out+='%7C' ;;
            $'\n') out+='%0A' ;;
            $'\r') out+='%0D' ;;
            *)     out+="$c" ;;
        esac
    done
    printf '%s' "$out"
}
_pct_decode() {
    local sVar="$1"
    sVar="${sVar//%0A/$'\n'}"
    sVar="${sVar//%0D/$'\r'}"
    sVar="${sVar//%7C/|}"
    sVar="${sVar//%25/%}"
    printf '%s' "$sVar"
}

# Name the git-dir sentinel when the data worktree is wedged, else return 1.
# task_git add/reset/commit are on neither allowlist, so assert_data_worktree_clean
# would die() — exit 1 with no batch_out — in the middle of this function.
_worktree_wedged() {
    local gd st
    gd="$(_sync_gitdir)"
    for st in rebase-merge rebase-apply MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD BISECT_LOG; do
        if [[ -e "$gd/$st" ]]; then printf '%s' "$st"; return 0; fi
    done
    return 1
}

# Path -> owning task id, or exit 1 when the path has no derivable owner.
# This is the INVERSE of resolve_task_file()/resolve_plan_file() in task_utils.sh
# (id -> path); no shared helper exists for this direction and no sibling needs
# one, so it lives here.
_owner_of_path() {
    local p="$1" d
    case "$p" in
        aitasks/*) d="${p#aitasks/}" ;;
        aiplans/*) d="${p#aiplans/}" ;;
        *) return 1 ;;
    esac
    d="${d#archived/}"
    # Child: t<P>/t<P>_<C>_*.md — the two parent numbers must agree, otherwise
    # the path is malformed and guessing an owner for it is exactly the
    # mis-attribution this task exists to stop.
    if [[ "$d" =~ ^[tp]([0-9]+)/[tp]([0-9]+)_([0-9]+)_[^/]*\.md$ ]]; then
        [[ "${BASH_REMATCH[1]}" == "${BASH_REMATCH[2]}" ]] || return 1
        printf '%s_%s' "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}"
        return 0
    fi
    if [[ "$d" =~ ^[tp]([0-9]+)_[^/]*\.md$ ]]; then
        printf '%s' "${BASH_REMATCH[1]}"
        return 0
    fi
    return 1
}

# Two-valued path state: `present:<blob>` or `absent`. Returns 1 when the path
# exists but cannot be hashed — that is an ERROR, never evidence of absence.
#
# EXISTENCE decides the state. `git hash-object` on a missing path exits 128
# with empty stdout, so keying the state on its failure would collapse "deleted"
# and "unreadable" into one value. The eligible set deliberately contains absent
# paths: a deletion, and the source half of an archive move.
_path_state() {
    local p="$1" full="$1" h
    [[ "$_AIT_DATA_WORKTREE" != "." ]] && full="$_AIT_DATA_WORKTREE/$p"
    if [[ ! -e "$full" ]]; then
        printf 'absent'
        return 0
    fi
    # _ait_data_git, not task_git: hash-object is on neither the read-only nor
    # the recovery allowlist, so task_git would die() on a wedged worktree.
    h="$(_ait_data_git hash-object -- "$p" 2>/dev/null)" || return 1
    [[ -n "$h" ]] || return 1
    printf 'present:%s' "$h"
}

# --- Lock snapshot ---------------------------------------------------------
declare -A LOCK_HOST=() LOCK_PID=() LOCK_START=() LOCK_KIND=() LOCK_EMAIL=()
LOCKS_STATUS=""

# Populate the snapshot from ONE `aitask_lock.sh --list --batch` call (one
# ls-remote + one fetch, regardless of how many locks exist).
_lock_snapshot() {
    LOCK_HOST=(); LOCK_PID=(); LOCK_START=(); LOCK_KIND=(); LOCK_EMAIL=()
    LOCKS_STATUS=""
    local out rc=0 line rest lid lemail lhost lpid lstart lkind
    out="$("$SCRIPT_DIR/aitask_lock.sh" --list --batch 2>/dev/null)" || rc=$?
    if [[ $rc -ne 0 ]]; then
        LOCKS_STATUS="LOCKS_UNAVAILABLE"
        return 0
    fi
    while IFS= read -r line; do
        case "$line" in
            LOCKS_OK|LOCKS_UNINITIALIZED|LOCKS_UNAVAILABLE) LOCKS_STATUS="$line" ;;
            LOCK:*)
                rest="${line#LOCK:}"
                IFS='|' read -r lid lemail lhost lpid lstart lkind <<< "$rest"
                [[ -n "$lid" ]] || continue
                LOCK_HOST["$lid"]="$lhost"
                LOCK_PID["$lid"]="$lpid"
                LOCK_START["$lid"]="$lstart"
                LOCK_KIND["$lid"]="$lkind"
                # Kept, not discarded: _holder_class compares it against
                # get_user_email to decide `self` vs `other` (t1725_3).
                LOCK_EMAIL["$lid"]="$lemail"
                ;;
        esac
    done <<< "$out"
    # A snapshot with no verdict line is not a snapshot. Fail safe.
    [[ -n "$LOCKS_STATUS" ]] || LOCKS_STATUS="LOCKS_UNAVAILABLE"
}

# free | alive | dead | unknown — the routing verdict for ONE task.
# `dead` is the only verdict that permits committing another session's file.
# True when <tid> was named by --commit-for-task.
_commit_for_task_listed() {
    local tid="$1" c
    for c in ${COMMIT_FOR_TASKS+"${COMMIT_FOR_TASKS[@]}"}; do
        [[ "$c" == "$tid" ]] && return 0
    done
    return 1
}

_holder_verdict() {
    local tid="$1" h cur
    [[ "$ASSUME_UNLOCKED" == true ]] && { printf 'free'; return 0; }

    # --commit-for-task: commit a task's dirty files even though its own session
    # is live. Evaluated HERE rather than at the call sites so it applies at
    # BOTH lock snapshots — the pre-scan one and the 5a.2 CAS re-enumeration.
    # That is what makes a lock changing hands mid-run fall out for free: the
    # two verdicts then disagree and the existing CAS drops the group as
    # lock_acquired_during_scan.
    #
    # `self` ONLY. Every other class is refused, `unverified` included: an
    # unverifiable identity is not this user's, and treating it as one would
    # commit a stranger's uncommitted work. The override bypasses neither the
    # 5a.3 state re-check nor the 5a.4 publication guard.
    if _commit_for_task_listed "$tid"; then
        local cls
        cls="$(_holder_class "$tid")"
        if [[ "$cls" == "self" ]]; then
            printf 'free'
            return 0
        fi
        warn "--commit-for-task t${tid} refused: the lock is ${cls} (${LOCK_EMAIL[$tid]:-no email} on ${LOCK_HOST[$tid]:-unknown host}), not your own verified session"
    fi

    h="${LOCK_HOST[$tid]:-}"
    [[ -z "$h" ]] && { printf 'free'; return 0; }

    cur="$(hostname 2>/dev/null || echo unknown)"
    # Cross-host guard, replicating aitask_lock.sh's: lock_holder_liveness takes
    # only (pid, starttime, kind) and has NO host awareness, so handed a foreign
    # machine's PID it probes the LOCAL process table and fabricates a verdict.
    # A coincidentally-absent local PID would read `dead` and we would commit a
    # file another machine's live session owns. "unknown" is not comparable
    # either — two machines both reporting it would compare equal.
    if [[ "$h" == "unknown" || "$h" != "$cur" ]]; then
        printf 'unknown'
        return 0
    fi
    # Prints alive|dead|unknown on STDOUT and always exits 0. is_lock_holder_alive
    # collapses dead and unknown into one false, so it is unusable here.
    lock_holder_liveness "${LOCK_PID[$tid]:--}" "${LOCK_START[$tid]:--}" "${LOCK_KIND[$tid]:-proc}"
}

# self | other | remote | unverified | none — WHO holds this task's lock,
# relative to the person running this sync (t1725_3).
#
# This exists because "held by other sessions" was wrong in the case that
# actually happens: on 2026-09-07 all 13 locks on the branch belonged to the
# same user, 12 of them on this host, and the blocking one was that user's own
# pane parked on a prompt. Telling them a stranger held it sent them looking in
# the wrong place for a whole session.
#
# `self` is deliberately the HARDEST verdict to reach: every identity must be
# present AND verified. An absent local email must never compare equal to an
# absent lock email — that would classify every anonymous lock as the user's own
# and make it eligible for --commit-for-task, which commits another session's
# uncommitted work. Anything missing or malformed is `unverified`, never `self`.
_AIT_SELF_EMAIL_CACHED=""
_AIT_SELF_EMAIL_DONE=false
_self_email() {
    if [[ "$_AIT_SELF_EMAIL_DONE" != true ]]; then
        _AIT_SELF_EMAIL_CACHED="$(get_user_email 2>/dev/null || true)"
        _AIT_SELF_EMAIL_DONE=true
    fi
    printf '%s' "$_AIT_SELF_EMAIL_CACHED"
}

_holder_class() {
    local tid="$1" lhost lemail me cur
    lhost="${LOCK_HOST[$tid]:-}"
    [[ -z "$lhost" ]] && { printf 'none'; return 0; }

    lemail="${LOCK_EMAIL[$tid]:-}"
    cur="$(hostname 2>/dev/null || true)"

    # A host we cannot name, on either side, is not a host we can compare.
    if [[ "$lhost" == "unknown" || -z "$cur" || "$cur" == "unknown" ]]; then
        printf 'unverified'
        return 0
    fi
    # A different machine: liveness is not decidable from here at all.
    if [[ "$lhost" != "$cur" ]]; then
        printf 'remote'
        return 0
    fi
    # Same verified host. Now the identity has to be real on BOTH sides.
    me="$(_self_email)"
    if [[ -z "$lemail" || -z "$me" ]]; then
        printf 'unverified'
        return 0
    fi
    if [[ "$lemail" == "$me" ]]; then
        printf 'self'
    else
        printf 'other'
    fi
}

# The prescriptive line for a lock-held file, per holder class. This is the text
# that reaches the user, so it names the concrete next action rather than the
# internal reason. "held by other sessions" appears nowhere.
_holder_action() {
    local tid="$1" path="$2" class="$3"
    local host="${LOCK_HOST[$tid]:-?}" pid="${LOCK_PID[$tid]:-?}" email="${LOCK_EMAIL[$tid]:-}"
    case "$class" in
        self)
            printf 't%s: %s — held by YOUR OWN live session on this host (pid %s) — finish or answer that session; or commit on its behalf: ./ait sync --commit-for-task %s' \
                "$tid" "$path" "$pid" "$tid" ;;
        other)
            printf 't%s: %s — held by %s'"'"'s live session on %s (pid %s) — left for that session' \
                "$tid" "$path" "$email" "$host" "$pid" ;;
        remote)
            printf 't%s: %s — held on %s (liveness cannot be verified from here) — left for that host' \
                "$tid" "$path" "$host" ;;
        *)
            printf 't%s: %s — held by a session whose identity could not be verified (lock email / local userconfig email missing) — left as is' \
                "$tid" "$path" ;;
    esac
}

# True when the snapshot is trustworthy enough to conclude anything about a task.
# This answers ONE question and says nothing about any particular task; whether a
# given task is held is answered by LOCK_HOST. There is deliberately no global
# "nothing is locked" test — using one as a per-task precondition would let an
# unrelated live lock on tY gate a decision about tX.
_locks_readable() {
    [[ "$LOCKS_STATUS" == "LOCKS_OK" || "$LOCKS_STATUS" == "LOCKS_UNINITIALIZED" ]]
}

# --- Quarantine (durable, cross-invocation) --------------------------------
#
# PUBLICATION_BLOCKED is script-scope state; the raced commit is not. Without
# persistence the hold would last exactly one run: the next sync finds the path
# still dirty and still locked, calls it protected_dirty, sees remote_ahead == 0
# and pushes the commit this run withheld.
#
# Keyed by (path, blob), never by commit SHA: a later `pull --rebase` rewrites
# the SHA and would silently invalidate a SHA-keyed entry.
# Line format: <path>|<blob>|<task_id>|<first_seen_epoch>
_quarantine_load_and_prune() {
    local qf line p p_enc blob tid seen head_blob rc verdict age warn_age
    qf="$(_quarantine_path)"
    QUARANTINE_HELD=()
    [[ -s "$qf" ]] || return 0

    warn_age="${AIT_SYNC_QUARANTINE_WARN_AGE:-86400}"

    while IFS='|' read -r p_enc blob tid seen; do
        [[ -n "$p_enc" && -n "$blob" ]] || continue
        p="$(_pct_decode "$p_enc")"

        # Clause 1 — superseded: a later commit landed on top, so publishing now
        # publishes history rather than a tip. Independent of any lock.
        rc=0
        head_blob="$(task_git rev-parse --verify --quiet "HEAD:$p" 2>/dev/null)" || rc=$?
        if [[ $rc -ne 0 || "$head_blob" != "$blob" ]]; then
            iinfo_err "quarantine released (superseded): $p"
            continue
        fi

        # Clause 2 — ownership released AND state verified. All three, never any.
        # A CLEAN worktree is NOT settlement on its own: `commit -o` committed
        # the worktree bytes, so the path is clean BY CONSTRUCTION right after
        # the race, and a cleanliness-only clause would release immediately.
        if _locks_readable; then
            verdict="$(_holder_verdict "$tid")"
            if [[ "$verdict" == "free" || "$verdict" == "dead" ]] \
               && [[ -z "$(task_git status --porcelain -- "$p" 2>/dev/null)" ]]; then
                iinfo_err "quarantine released (owner gone, state settled): $p"
                continue
            fi
        fi

        QUARANTINE_HELD+=("${p_enc}|${blob}|${tid}|${seen}")
        PUBLICATION_BLOCKED+=("$p")

        # Age NEVER releases. An automatic expiry would fire in exactly the
        # states clause 2 refuses to release on — a live holder, an `unknown`
        # cross-host holder, an unreadable lock branch — so a session that
        # legitimately runs longer than the window would have its raced content
        # published merely because time passed. That is the cross-session
        # swallow this task exists to prevent, re-entering through the escape
        # hatch. Past the window the report ESCALATES; only the operator
        # releases, which makes the safety-vs-availability call explicit.
        age=$(( $(date +%s) - ${seen:-0} ))
        if (( ${seen:-0} > 0 && age > warn_age )); then
            _note_skip "QUARANTINE HELD ${age}s (>${warn_age}s): $p (t${tid}, holder: ${LOCK_HOST[$tid]:-none}) — sync is publishing NOTHING until this clears. Release deliberately with: ./ait sync --release-quarantine"
        else
            _note_skip "quarantine held: $p (t${tid}) — withheld from the remote until t${tid}'s session commits or ends"
        fi
    done < "$qf"
    return 0
}

_quarantine_persist() {
    local qf tmp
    qf="$(_quarantine_path)"
    if (( ${#QUARANTINE_HELD[@]} == 0 )); then
        rm -f "$qf" 2>/dev/null || true
        return 0
    fi
    tmp="${qf}.tmp.$$"
    printf '%s\n' "${QUARANTINE_HELD[@]}" > "$tmp" 2>/dev/null || return 0
    mv -f "$tmp" "$qf" 2>/dev/null || rm -f "$tmp" 2>/dev/null || true
    return 0
}

# --- The sweep -------------------------------------------------------------
auto_commit() {
    local rc=0 dirtyf
    dirtyf="$(mktemp)" || { _protect "scan_failed" "" "" "unknown" "could not allocate a scratch file — nothing swept"; return 0; }
    # -uall is MANDATORY, not cosmetic: git's default collapses an untracked
    # directory to the directory itself, so a new child task shows as
    # `?? aitasks/t99/`. That has no derivable owner and would be skipped as
    # ownerless, silently never committing a new child task.
    #
    # To a FILE, not a variable: bash discards NUL bytes in command
    # substitution, so `$(git status -z)` loses every separator it exists for.
    #
    # The dirty scan runs BEFORE the lock enumeration on purpose: a lock
    # acquired while we were scanning is then visible to us. The reverse order
    # is silently unsafe.
    task_git status --porcelain -z -uall -- aitasks/ aiplans/ > "$dirtyf" 2>/dev/null || rc=$?
    if [[ $rc -ne 0 ]]; then
        rm -f "$dirtyf"
        _protect "scan_failed" "" "" "unknown" "could not read the worktree status — nothing swept"
        return 0
    fi

    local qf; qf="$(_quarantine_path)"
    # Fast path: nothing dirty and nothing quarantined is today's no-op, with no
    # added network cost on the overwhelmingly common clean sync.
    if [[ ! -s "$dirtyf" && ! -s "$qf" ]]; then
        rm -f "$dirtyf"
        return 0
    fi

    if [[ "$RELEASE_QUARANTINE" == true ]]; then
        rm -f "$qf" 2>/dev/null || true
        iwarn "Quarantine released by operator request (--release-quarantine)."
    fi

    # Serialize the whole classify -> commit phase. `.aitask-data` is ONE
    # worktree with ONE index shared by every session on this machine, and
    # task_git does no locking at all. Fail CLOSED: never sweep unlocked.
    local lock_dir
    lock_dir="$(ait_lock_dir data_index)"
    if ! registry_lock_acquire "$lock_dir" 15 "sync auto-commit"; then
        _protect "lock_contended" "" "" "unknown" "another sync holds the data-index lock — nothing swept"
        # No commit was made, so nothing is withheld from the remote; but a
        # quarantine from an EARLIER run must still hold. Evaluate it read-only.
        _lock_snapshot
        _quarantine_load_and_prune
        rm -f "$dirtyf"
        return 0
    fi

    _lock_snapshot
    _quarantine_load_and_prune

    if [[ -s "$dirtyf" ]]; then
        _sweep_dirty "$dirtyf"
    fi

    _quarantine_persist
    registry_lock_release "$lock_dir"
    rm -f "$dirtyf"
    return 0
}

# Group the dirty set by owning task and commit each group path-scoped.
# Reads the NUL-delimited porcelain from a FILE: bash discards NUL bytes in
# command substitution, so `$(git status -z)` silently loses every separator.
# Porcelain XY -> the tree state the rebase gate reasons about. `??` is the only
# untracked shape; everything else git reports is a tracked path. The
# distinction is load-bearing: `git rebase` refuses on unstaged TRACKED changes
# but ignores an untracked path entirely unless an incoming commit creates it.
_xy_state() {
    [[ "${1:-}" == "??" ]] && { printf 'untracked'; return 0; }
    printf 'tracked'
}

# _protect_task_paths <reason> <tid> <template>
#
# A per-TASK protection expanded into one record PER PATH of that task, so the
# deferral can name files rather than reporting a count of skip events. Reads
# _sweep_dirty's ent_* arrays through bash's dynamic scope — it is only ever
# called from there, and its own frame is what keeps them alive.
#
# <template> is either the literal `@holder_action` (build the line with
# _holder_action, which picks the wording from the holder class) or free text
# containing %PATH%.
#
# A task with no surviving entries still records ONE path-less row: a protection
# that produced no record at all would be a file the user is never told about.
_protect_task_paths() {
    local reason="$1" tid="$2" template="$3"
    local gi hit=0 line class
    class="$(_holder_class "$tid")"
    for ((gi = 0; gi < ${#ent_path[@]}; gi++)); do
        [[ "${ent_owner[$gi]}" == "$tid" ]] || continue
        hit=1
        if [[ "$template" == "@holder_action" ]]; then
            line="$(_holder_action "$tid" "${ent_path[$gi]}" "$class")"
        else
            line="${template//%PATH%/${ent_path[$gi]}}"
        fi
        _protect "$reason" "$tid" "${ent_path[$gi]}" "${ent_state[$gi]}" "$line"
    done
    if (( hit == 0 )); then
        if [[ "$template" == "@holder_action" ]]; then
            line="$(_holder_action "$tid" "(no files resolved)" "$class")"
        else
            line="${template//%PATH%/(no files resolved)}"
        fi
        _protect "$reason" "$tid" "" "unknown" "$line"
    fi
}

_sweep_dirty() {
    local tmpf="$1"
    local -a fields=()
    local f
    while IFS= read -r -d '' f; do fields+=("$f"); done < "$tmpf"

    # Parallel indexed arrays, NOT a delimiter-joined string. A git path may
    # contain a newline, so joining on one would split a single file into two
    # bogus paths — which then miss in PATH_STATE and, under `set -u`, abort the
    # whole script with EMPTY stdout: the exact `ERROR: empty output` failure
    # this sweep exists to avoid. Bash strings cannot hold NUL, so there is no
    # safe delimiter; carrying the paths as array elements avoids needing one.
    local -a ent_path=() ent_owner=() ent_state=()
    local -A owner_seen=()
    PATH_STATE=()               # path   -> present:<blob> | absent (script scope:
                                # _commit_group reads it; no namerefs in this tree)
    local i=0 n=${#fields[@]}

    while (( i < n )); do
        local entry="${fields[$i]}" xy path orig="" owner owner2 st
        i=$((i + 1))
        [[ -z "$entry" ]] && continue
        xy="${entry:0:2}"
        path="${entry:3}"
        # An `R`/`C` entry names TWO paths: with -z the NEXT field is the
        # source, i.e. <new> then <orig> — the reverse of the arrow display.
        # (Verified. Note git only emits R when BOTH halves are staged; an
        # unstaged worktree move arrives as separate ` D <orig>` + `?? <new>`
        # entries, which group correctly on their own.)
        if [[ "$xy" == R* || "$xy" == C* ]]; then
            orig="${fields[$i]:-}"
            i=$((i + 1))
        fi
        [[ -z "$path" ]] && continue

        if ! owner="$(_owner_of_path "$path")"; then
            if [[ "$COMMIT_UNOWNED" == true ]]; then
                owner="__unowned__"
            else
                # Never sweep an ownerless path into a residual commit — that is
                # what left aitasks/metadata/stats_config.json with three of its
                # four commits attributed to unrelated tasks. The report must be
                # PRESCRIPTIVE: an ownerless dirty file is a standing state.
                #
                # Since t1677 the config-editing surfaces (settings TUI, board
                # column CRUD, chatlink wizard, `ait setup`) commit their own
                # writes, so most metadata files DO have an owner now — what
                # reaches here is a hand edit, a deliberately human-reviewed file
                # like gates.yaml, or a commit that failed. The remedy names the
                # same helper those writers use, so the advice and the behaviour
                # cannot drift.
                _protect "ownerless" "" "$path" "$(_xy_state "$xy")" "ownerless, NOT auto-committed: $path — no session is going to commit this file for you. Clear it with: ./.aitask-scripts/aitask_metadata_commit.sh '$path'   (or, for a path outside aitasks/metadata/, ./ait git add '$path' && ./ait git commit -m '$(ait_metadata_commit_message "$path")')   (or re-run with --commit-unowned)"
                continue
            fi
        fi

        # An entry that legitimately names two paths gets no guessed owner.
        if [[ -n "$orig" ]]; then
            if ! owner2="$(_owner_of_path "$orig")" || [[ "$owner2" != "$owner" ]]; then
                _protect "ambiguous_rename" "$owner" "$path" "$(_xy_state "$xy")" "ambiguous cross-task rename, skipped: '$path' <- '$orig'"
                continue
            fi
        fi

        # Resolve BOTH halves before adding EITHER: a failure on the source
        # side must not leave a half-added rename in the group.
        local st_orig=""
        if ! st="$(_path_state "$path")"; then
            _protect "unverifiable" "$owner" "$path" "$(_xy_state "$xy")" "could not hash (skipped): $path"
            continue
        fi
        if [[ -n "$orig" ]] && ! st_orig="$(_path_state "$orig")"; then
            _protect "unverifiable" "$owner" "$orig" "$(_xy_state "$xy")" "could not hash (skipped): $orig"
            continue
        fi
        PATH_STATE["$path"]="$st"
        ent_path+=("$path"); ent_owner+=("$owner"); ent_state+=("$(_xy_state "$xy")")
        owner_seen["$owner"]=1
        if [[ -n "$orig" ]]; then
            PATH_STATE["$orig"]="$st_orig"
            # The source half of a rename is by construction TRACKED: git only
            # emits R when both halves are staged.
            ent_path+=("$orig"); ent_owner+=("$owner"); ent_state+=("tracked")
        fi
    done

    (( ${#owner_seen[@]} )) || return 0

    # An unreadable lock branch is NOT evidence of no locks; an outage can
    # easily coincide with a live editor. The operator makes the
    # availability-over-safety call explicitly, never a network failure.
    if ! _locks_readable && [[ "$ASSUME_UNLOCKED" != true ]]; then
        local tid
        for tid in "${!owner_seen[@]}"; do
            _protect_task_paths "locks_unavailable" "$tid" "t${tid}: %PATH% — lock branch unreadable, so no holder could be checked; left dirty (re-run with --assume-unlocked to override)"
        done
        return 0
    fi

    # Per-task routing. `dead` is the recovery case and the ONLY verdict that
    # permits committing; `alive` and `unknown` both skip. Fail safe.
    local -A eligible=() pre_verdict=()
    local tid verdict
    for tid in "${!owner_seen[@]}"; do
        if [[ "$tid" == "__unowned__" ]]; then
            eligible["$tid"]=1
            pre_verdict["$tid"]="free"
            continue
        fi
        verdict="$(_holder_verdict "$tid")"
        pre_verdict["$tid"]="$verdict"
        case "$verdict" in
            free|dead) eligible["$tid"]=1 ;;
            alive)   _protect_task_paths "live_lock" "$tid" "@holder_action" ;;
            *)       _protect_task_paths "unknown_liveness" "$tid" "t${tid}: %PATH% — the holder could not be verified as gone (${LOCK_HOST[$tid]:-?}); treated as live and left dirty" ;;
        esac
    done
    (( ${#eligible[@]} )) || return 0

    _sync_test_seam pre_commit_phase

    # Step 5a.2 — compare-and-swap the snapshot immediately before committing.
    # A session can acquire a lock and start editing AFTER our enumeration and
    # BEFORE this group's commit; the claim path takes hundreds of milliseconds
    # between its lock push and its own commit, so the window is real.
    _lock_snapshot
    for tid in "${!eligible[@]}"; do
        [[ "$tid" == "__unowned__" ]] && continue
        verdict="$(_holder_verdict "$tid")"
        if [[ "$verdict" != "${pre_verdict[$tid]}" ]]; then
            _protect_task_paths "lock_acquired_during_scan" "$tid" "t${tid}: %PATH% — was locked while we were scanning, so the group was dropped; re-run once that session settles"
            unset "eligible[$tid]"
        fi
    done

    local msg
    for tid in "${!eligible[@]}"; do
        local -a paths=()
        local gi
        for ((gi = 0; gi < ${#ent_path[@]}; gi++)); do
            [[ "${ent_owner[$gi]}" == "$tid" ]] && paths+=("${ent_path[$gi]}")
        done
        (( ${#paths[@]} )) || continue

        if [[ "$tid" == "__unowned__" ]]; then
            # A message that stays true regardless of who appended — the same
            # rule aitask_pick_own.sh applies to the shared contributor list.
            msg="ait: Auto-commit unowned task data before sync"
        else
            msg="ait: Auto-commit t${tid} task data before sync"
        fi
        _commit_group "$tid" "$msg" "${paths[@]}"
    done
    return 0
}

# Commit ONE owner's paths. <state_ref> is the name of the path_state map.
# The tree state recorded for <path> during the scan. _commit_group runs inside
# _sweep_dirty's frame, so ent_* are visible here through bash's dynamic scope.
# `unknown` is the fail-safe answer: a path we cannot classify must block the
# rebase rather than be assumed harmless.
_group_state() {
    local want="$1" gi
    for ((gi = 0; gi < ${#ent_path[@]}; gi++)); do
        [[ "${ent_path[$gi]}" == "$want" ]] && { printf '%s' "${ent_state[$gi]}"; return 0; }
    done
    printf 'unknown'
}

# A group-wide protection expanded to one record per path of the group. Same
# shape as _protect_task_paths, but driven by _commit_group's own `paths` array
# (the group is already resolved by the time it runs).
_protect_group_paths() {
    local reason="$1" tid="$2" template="$3" gp
    for gp in "${paths[@]}"; do
        _protect "$reason" "$tid" "$gp" "$(_group_state "$gp")" "${template//%PATH%/$gp}"
    done
}

_commit_group() {
    local tid="$1" msg="$2"; shift 2
    local -a paths=("$@")
    local p now cur rc

    # Hazard B — never touch an index entry another session staged. `add` would
    # replace it and `reset` would remove it, destroying in-flight work while
    # trying not to swallow it. Defer the whole group instead.
    local staged
    staged="$(task_git diff --cached --name-only -- "${paths[@]}" 2>/dev/null)" || staged=""
    if [[ -n "$staged" ]]; then
        local sp
        for sp in "${paths[@]}"; do
            _protect "staged_elsewhere" "$tid" "$sp" "$(_group_state "$sp")" \
                "t${tid}: $sp — another session has staged $(echo "$staged" | tr '\n' ' ')so the whole group was deferred; let that session finish"
        done
        return 0
    fi

    # Step 5a.3 — re-derive the STATE (not just a hash) immediately before the
    # commit and require it to be unchanged. Both transition directions matter:
    # absent->present is a deleted file another session recreated, which a
    # hash-only check cannot see at all.
    for p in "${paths[@]}"; do
        if ! now="$(_path_state "$p")"; then
            _protect_group_paths "unverifiable" "$tid" "t${tid}: %PATH% — could not re-hash '$p' just before the commit, so the group was skipped"
            return 0
        fi
        # `:-` guard: a miss must degrade to "skip this group", never abort the
        # script under `set -u` with no stdout.
        if [[ "$now" != "${PATH_STATE[$p]:-}" ]]; then
            _protect_group_paths "content_changed" "$tid" "t${tid}: %PATH% — '$p' changed after classification, so the group was skipped; re-run once that session settles"
            return 0
        fi
    done

    # --- commit-on-behalf guards ------------------------------------------
    #
    # These apply only to a group that reached here through --commit-for-task,
    # i.e. one whose owning session is LIVE. Everything a UI showed the user is
    # a snapshot; these re-validate it at the moment of effect.
    #
    # PLACEMENT IS LOAD-BEARING: after the 5a.3 re-check (so they judge settled
    # state) but BEFORE the staging loop below. Both of them abandon the group
    # with `return 0`, and a path this run had already staged would stay in the
    # shared index -- where it blocks the rebase exactly like an unstaged one,
    # which is why the commit-failed path further down has to unstage. Running
    # before anything is staged means there is nothing to unwind.
    if _commit_for_task_listed "$tid"; then
        # --expect-path: the caller states the exact dirty set it showed. If the
        # group has grown or shrunk since, the confirmation the user gave was
        # for a different set of files, so it does not carry.
        if [[ "$EXPECT_PATHS_SET" == true ]]; then
            local -A want=() have=()
            local w pw delta=""
            for w in ${EXPECT_PATHS+"${EXPECT_PATHS[@]}"}; do
                pw="$(_pct_decode "$w")"; want["$pw"]=1
            done
            for p in "${paths[@]}"; do have["$p"]=1; done
            for p in "${paths[@]}"; do
                [[ -n "${want[$p]:-}" ]] || delta+=" +$p"
            done
            for w in "${!want[@]}"; do
                [[ -n "${have[$w]:-}" ]] || delta+=" -$w"
            done
            if [[ -n "$delta" ]]; then
                _protect_group_paths "commit_scope_changed" "$tid" \
                    "t${tid}: %PATH% — the dirty set changed after it was confirmed (${delta# }); nothing was committed. Re-check and confirm again."
                return 0
            fi
        fi

        # --require-waiting: only commit on behalf of a session that is parked
        # on a prompt, re-probed HERE rather than trusted from the snapshot the
        # UI rendered. FAILS CLOSED when the probe is unavailable — which it is
        # until t1725_4 lands the helpers, so today this flag always refuses.
        # That is the intended direction: never commit another session's work on
        # the strength of a check that did not run.
        if [[ "$REQUIRE_WAITING" == true ]]; then
            local pane_state="unresolvable"
            if declare -F ait_tmux_pane_for_pid >/dev/null \
               && [[ -f "$SCRIPT_DIR/lib/pane_state_probe.py" ]]; then
                local hpane
                hpane="$(ait_tmux_pane_for_pid "${LOCK_PID[$tid]:-}" 2>/dev/null || true)"
                if [[ -n "$hpane" ]]; then
                    local py
                    py="$(resolve_python 2>/dev/null || true)"
                    if [[ -n "$py" ]]; then
                        pane_state="$("$py" "$SCRIPT_DIR/lib/pane_state_probe.py" "$hpane" 2>/dev/null || echo unresolvable)"
                    fi
                fi
            fi
            if [[ "$pane_state" != waiting_* ]]; then
                _protect_group_paths "holder_not_waiting" "$tid" \
                    "t${tid}: %PATH% — t${tid}'s session is not parked on a prompt (observed: ${pane_state}), so its files were left alone. Answer that session, or re-run without --require-waiting to override deliberately."
                return 0
            fi
        fi
    fi

    # Stage ONLY untracked paths, and remember exactly which — a pathspec cannot
    # name a file git does not know about, but a tracked path needs no staging
    # because `commit -o` takes worktree content. Recording what we staged is
    # what lets the failure path unstage our entries and nobody else's.
    local -a staged_by_us=()
    for p in "${paths[@]}"; do
        if ! task_git ls-files --error-unmatch -- "$p" >/dev/null 2>&1; then
            [[ "${PATH_STATE[$p]:-}" == absent ]] && continue
            if task_git add -- "$p" >/dev/null 2>&1; then
                staged_by_us+=("$p")
            fi
        fi
    done

    _sync_test_seam pre_group_commit

    rc=0
    task_git_commit_scoped --no-stage "$msg" "${paths[@]}" || rc=$?
    if [[ $rc -eq 1 ]]; then
        # A path left staged blocks the rebase exactly like an unstaged one, so
        # the cleanup is required — but it is scoped to entries THIS run created,
        # which is what keeps it from unstaging another session's work.
        if (( ${#staged_by_us[@]} )); then
            task_git reset -q -- "${staged_by_us[@]}" >/dev/null 2>&1 || true
        fi
        _protect_group_paths "commit_failed" "$tid" "t${tid}: %PATH% — the commit failed, so the file was left dirty"
        return 0
    fi
    [[ $rc -eq 2 ]] && return 0   # verified nothing to commit

    # Progress parity with the pre-t1599_3 "Auto-committing N files..." line,
    # now per group so the user can see WHICH task each commit belongs to.
    # iinfo is a no-op in batch mode, where stdout is the data channel.
    if [[ "$tid" == "__unowned__" ]]; then
        iinfo "Auto-committed ${#paths[@]} unowned task/plan file(s)"
    else
        iinfo "Auto-committed ${#paths[@]} file(s) for t${tid}"
    fi

    # Say plainly what was just done on someone's behalf. The sweep cannot see
    # whether that session was mid-edit but momentarily quiet, so the content is
    # whatever it happened to be at this instant — and the person who asked for
    # it is the only one who can judge that. warn() so it survives --batch,
    # where stdout is the data channel.
    if _commit_for_task_listed "$tid"; then
        warn "t${tid}'s session is live — its uncommitted edits were committed as they stand now (${#paths[@]} file(s))"
    fi

    # Step 5a.4 — guard publication, PER STATE. A `present` path must resolve in
    # HEAD to the blob we classified; an `absent` one must NOT resolve at all
    # (that absence is what records a deletion or a rename's source side).
    for p in "${paths[@]}"; do
        rc=0
        cur="$(task_git rev-parse --verify --quiet "HEAD:$p" 2>/dev/null)" || rc=$?
        if [[ "${PATH_STATE[$p]:-}" == absent ]]; then
            (( rc != 0 )) && continue
            _quarantine_add "$p" "$cur" "$tid"
        else
            local want="${PATH_STATE[$p]:-}"; want="${want#present:}"
            [[ $rc -eq 0 && "$cur" == "$want" ]] && continue
            _quarantine_add "$p" "${cur:-$want}" "$tid"
        fi
    done
    return 0
}

# Record a commit whose content we cannot vouch for. It is NOT un-made:
# reversing it would mean `reset --soft/--mixed HEAD^`, which moves HEAD and
# leaves the content in the SHARED index — Hazard B, against a path another
# session is actively writing.
_quarantine_add() {
    local p="$1" blob="$2" tid="$3"
    QUARANTINE_HELD+=("$(_pct_encode "$p")|${blob}|${tid}|$(date +%s)")
    PUBLICATION_BLOCKED+=("$p")
    _note_skip "PUBLICATION WITHHELD: $p was rewritten while t${tid}'s commit was being made. The commit is local-only and will NOT be pushed until t${tid}'s session commits its own version or ends."
}

# Everything skipped, with its reason. STDERR in BOTH modes: in batch mode
# stdout is the data channel and parse_sync_output() reads the FIRST non-empty
# line, so a report line there would be consumed as the status.
# --- The rebase gate ------------------------------------------------------
#
# Which incoming paths a pull would check out. Populated once per fetch.
declare -A INCOMING=()

# 0 = INCOMING is authoritative; 1 = unknown (caller must fail closed).
#
# NUL-DELIMITED, VIA A FILE. `$(task_git diff --name-only …)` is wrong twice
# over, and both ways fail OPEN — the membership test misses and the gate lets a
# rebase overwrite the very file it is protecting:
#
#   * a path containing a newline is split into two names that match nothing;
#   * git C-QUOTES paths with unusual bytes by default, so `"a\nb.md"` never
#     compares equal to the raw porcelain path the sweep recorded;
#   * and `$( )` discards NUL outright, which is why the dirty scan in
#     auto_commit already writes to a file for exactly this reason.
#
# NO TRAP IS NEEDED, AND THAT IS A PROPERTY TO PRESERVE. Between mktemp and
# `rm -f` there is no exit point: `diff` is on the read-only allowlist so
# task_git cannot die() here, `|| rc=$?` absorbs the status under `set -e`, and
# the read loop cannot exit. This script has no trap at all and its deferral,
# conflict and network paths all exit from nested functions, so a temp file
# allocated at call-site scope would leak on every one of them. Anything added
# inside this window must keep it exit-free.
_load_incoming() {
    INCOMING=()
    local incf p rc=0
    incf="$(mktemp)" || return 1
    task_git diff --name-only -z "HEAD..@{u}" > "$incf" 2>/dev/null || rc=$?
    if [[ $rc -eq 0 ]]; then
        while IFS= read -r -d '' p; do INCOMING["$p"]=1; done < "$incf"
    fi
    rm -f "$incf"
    return $rc
}

# _rebase_blocked <local_ahead> <remote_ahead> — 0 = blocked, 1 = not blocked.
#
# The old rule was "any protected file AND remote_ahead > 0". That deferred two
# cases that nothing actually blocks, which is what made a parked pane able to
# stall a whole branch (t1725, finding 4). The rule is now five-way:
#
#   1. remote_ahead == 0  -> NOT blocked, unconditionally. There is no rebase to
#      block; do_push needs no clean tree, so eligible commits still publish.
#      This clause is what keeps the deliberate asymmetry (t1599_3) intact.
#   2. tree_state=unknown -> blocked. We could not classify the file, and an
#      unclassified file is not an absent one.
#   3. tracked AND local_ahead > 0 -> blocked. Replaying local commits needs a
#      clean tree; `git pull --rebase` refuses with unstaged tracked changes.
#   4. path is INCOMING -> blocked, tracked or untracked alike. The checkout
#      would overwrite the file we are protecting.
#   5. otherwise -> NOT blocked. With local_ahead == 0 main fast-forwards
#      (a fast-forward never conflicts); with local_ahead > 0 only untracked,
#      non-incoming files remain, which a rebase ignores.
_rebase_blocked() {
    local local_ahead="$1" remote_ahead="$2" i

    [[ "$remote_ahead" -gt 0 ]] || return 1

    for ((i = 0; i < ${#PROT_REASON[@]}; i++)); do
        [[ "${PROT_STATE[$i]}" == "unknown" ]] && return 0
        if [[ "${PROT_STATE[$i]}" == "tracked" && "$local_ahead" -gt 0 ]]; then
            return 0
        fi
        local pth="${PROT_PATH[$i]}"
        if [[ -n "$pth" && -n "${INCOMING[$pth]:-}" ]]; then
            return 0
        fi
    done
    return 1
}

# The ONE emitter for a protected_dirty deferral: the status line plus one
# DEFERRED_FILE: continuation per record. Both call sites (main and do_push) go
# through here so the two can never drift, and so records are emitted only
# alongside a status line that declares them.
#
# The first line keeps its `DEFERRED:protected_dirty:` prefix and the closed
# three-reason set, so parse_sync_output and the token-contract scan are
# unaffected. Its detail text now carries per-sub-reason counts instead of the
# wrong "held by other sessions" (all 13 locks in the incident that motivated
# this belonged to the user running the sync).
_emit_protected_deferral() {
    local n=${#PROT_REASON[@]} i counts="" r
    local -A tally=()
    for ((i = 0; i < n; i++)); do
        tally["${PROT_REASON[$i]}"]=$(( ${tally["${PROT_REASON[$i]}"]:-0} + 1 ))
    done
    for r in $(printf '%s\n' "${!tally[@]}" | sort); do
        counts+=" ${r}=${tally[$r]}"
    done
    batch_out "DEFERRED:protected_dirty:${n} file(s) block the rebase:${counts}"

    for ((i = 0; i < n; i++)); do
        # Every textual field is percent-encoded: a git path may contain `|` and
        # a newline, `hostname` and `locked_by` are user-controlled, and a tmux
        # session name (t1725_4's pane target) may contain both. The closed and
        # numeric fields travel bare and are validated by the parser.
        batch_detail "DEFERRED_FILE:${PROT_REASON[$i]}|${PROT_TASK[$i]}|$(_pct_encode "${PROT_PATH[$i]}")|${PROT_STATE[$i]}|${PROT_HOLDER[$i]}|$(_pct_encode "${PROT_EMAIL[$i]}")|$(_pct_encode "${PROT_HOST[$i]}")|${PROT_PID[$i]}|$(_pct_encode "${PROT_PANE[$i]}")|${PROT_PANE_STATE[$i]}|$(_pct_encode "${PROT_ACTION[$i]}")"
    done
    # Neutral wording: this emitter serves both main() and do_push()'"'"'s retry, and
    # each adds its own context line after it.
    iwarn "Sync deferred: ${n} protected file(s) block the rebase."
}

report_skipped() {
    (( ${#SKIP_REPORT[@]} )) || return 0
    local l
    {
        echo "sync: not everything was auto-committed —"
        for l in "${SKIP_REPORT[@]}"; do echo "  - $l"; done
    } >&2
    return 0
}

# --- Fetch with timeout ---
do_fetch() {
    iinfo "Fetching from remote..."
    local fetch_exit=0
    _git_with_timeout fetch origin 2>/dev/null || fetch_exit=$?

    if [[ $fetch_exit -eq 124 ]]; then
        batch_out "NO_NETWORK"
        if [[ "$BATCH_MODE" == false ]]; then
            warn "Network timeout during fetch"
        fi
        exit 0
    elif [[ $fetch_exit -ne 0 ]]; then
        batch_out "NO_NETWORK"
        if [[ "$BATCH_MODE" == false ]]; then
            warn "Fetch failed (no network?)"
        fi
        exit 0
    fi
}

# --- Count commits ahead/behind ---
count_local_ahead() {
    task_git rev-list --count "@{u}..HEAD" 2>/dev/null || echo "0"
}

count_remote_ahead() {
    task_git rev-list --count "HEAD..@{u}" 2>/dev/null || echo "0"
}

# --- Pull with rebase ---
# Returns: 0 = normal pull, 1 = failure, 2 = automerged
_PULL_AUTOMERGED=false
do_pull_rebase() {
    local remote_count="$1"
    iinfo "Pulling $remote_count new commits (rebase)..."

    local pull_exit=0
    task_git pull --rebase --quiet &>/dev/null || pull_exit=$?

    if [[ $pull_exit -ne 0 ]]; then
        # Check if it's a conflict
        local conflicted
        conflicted=$(task_git diff --name-only --diff-filter=U 2>/dev/null || true)

        if [[ -n "$conflicted" ]]; then
            # The whole resolve-and-advance cycle — including the multi-commit
            # replay — lives in lib/task_automerge.sh, shared with
            # task_utils.sh::_task_pull_rebase (t1727).
            #
            # ABSORBING CAPTURE, never a bare call: this script runs
            # `set -euo pipefail`, so `ait_automerge_rebase_loop; rc=$?` would
            # exit the shell on the loop's own documented rc 1 (unresolved) and
            # rc 2 (advance failed) — bypassing the CONFLICT: token and the
            # interactive fallback exactly when they are needed. `local` on its
            # own line so the declaration's status never masks the call's.
            local remaining=""
            local loop_rc=0
            ait_automerge_rebase_loop || loop_rc=$?

            case $loop_rc in
                0)
                    _PULL_AUTOMERGED=true
                    isuccess "All conflicts auto-merged successfully"
                    return 0 ;;
                2)
                    # Advance failed for a non-conflict reason.
                    task_git rebase --abort 2>/dev/null || true
                    batch_out "ERROR:rebase_continue_failed"
                    return 1 ;;
            esac
            remaining="$AIT_AUTOMERGE_REMAINING"

            # Some files unresolved (or auto-merge unavailable)
            if [[ "$BATCH_MODE" == true ]]; then
                task_git rebase --abort 2>/dev/null || true
                local conflict_list
                conflict_list=$(echo "$remaining" | tr '\n' ',' | sed 's/,$//')
                batch_out "CONFLICT:${conflict_list}"
                exit 0
            else
                # Interactive conflict resolution with remaining files only
                warn "Remaining conflicts in:"
                echo "$remaining" | while IFS= read -r f; do echo "  - $f"; done

                local editor="${EDITOR:-nano}"
                echo ""
                info "Opening each conflicted file in $editor for resolution..."

                # `<<<`, NOT `echo | while`: a pipeline runs the loop in a
                # SUBSHELL, so `all_resolved=false` never reached the check
                # below, and a die() in the body killed only the subshell —
                # silently ending the loop after the FIRST file.
                local all_resolved=true
                while IFS= read -r f; do
                    [[ -z "$f" ]] && continue
                    echo ""
                    info "Editing: $f"
                    if $editor "$(ait_automerge_conflict_path "$f")"; then
                        # Staging a resolved conflict is exactly what this loop
                        # exists to do, and it owns the rebase it is resolving —
                        # so scope the documented bypass to this one call, as
                        # the auto-merge site above does. Without it
                        # assert_data_worktree_clean die()s mid-loop.
                        #
                        # Keep the call inside `$( )`: the loop now runs in the
                        # CURRENT shell under `set -euo pipefail`, so a die()
                        # reached through task_git must stay confined to the
                        # substitution and surface as a non-zero rc.
                        local add_err add_rc=0
                        add_err="$(AIT_GIT_SKIP_STATE_CHECK=1 task_git add "$f" 2>&1)" || add_rc=$?
                        if [[ $add_rc -ne 0 ]]; then
                            # A file we could not stage is NOT resolved:
                            # `rebase --continue` would fail later with the
                            # diagnostic already thrown away by `2>/dev/null`.
                            # warn() -> stderr, never info()/iinfo().
                            warn "could not stage $f (git add rc=$add_rc): ${add_err:-<no output>}"
                            all_resolved=false
                        fi
                    else
                        warn "Editor exited with error for $f"
                        all_resolved=false
                    fi
                done <<< "$remaining"

                if [[ "$all_resolved" == true ]]; then
                    if ! ait_automerge_advance; then
                        warn "Rebase continue failed. Aborting rebase."
                        task_git rebase --abort 2>/dev/null || true
                        return 1
                    fi
                else
                    warn "Not all conflicts resolved. Aborting rebase."
                    task_git rebase --abort 2>/dev/null || true
                    return 1
                fi
            fi
        else
            # Not a conflict — some other pull/rebase error
            task_git rebase --abort 2>/dev/null || true
            batch_out "ERROR:pull_rebase_failed"
            if [[ "$BATCH_MODE" == false ]]; then
                warn "Pull --rebase failed (non-conflict error)"
            fi
            return 1
        fi
    fi
    return 0
}

# --- Push with retry ---
do_push() {
    local local_count="$1"
    iinfo "Pushing $local_count commits to remote..."

    _sync_test_seam pre_push

    local push_exit=0
    _git_with_timeout push origin 2>/dev/null || push_exit=$?

    if [[ $push_exit -eq 124 ]]; then
        batch_out "NO_NETWORK"
        if [[ "$BATCH_MODE" == false ]]; then
            warn "Network timeout during push"
        fi
        exit 0
    elif [[ $push_exit -ne 0 ]]; then
        # `remote_ahead` was sampled ONCE, from the step-5 fetch, so on a branch
        # several sessions push to in parallel the remote can advance afterwards
        # and a run that correctly saw remote_ahead == 0 still lands here.
        #
        # Defensive: main() exits before do_push when a publication quarantine
        # is held, but the guard's correctness must not depend on one call
        # site's ordering — a future reorder must not be able to publish a
        # commit we deliberately withheld.
        if (( ${#PUBLICATION_BLOCKED[@]} )); then
            batch_out "DEFERRED:publication_blocked:${#PUBLICATION_BLOCKED[@]} path(s) withheld"
            iwarn "Push withheld: ${#PUBLICATION_BLOCKED[@]} path(s) under publication quarantine."
            return 2
        fi

        # Retry once (remote may have advanced during our rebase).
        #
        # The gate is re-evaluated HERE, on inputs sampled AFTER this fetch, not
        # before it. main's gate ran against the step-5 fetch; the rejection
        # proves the remote moved since, and a commit that arrived in between can
        # create exactly the protected untracked path main's gate waved through.
        iinfo "Push rejected, retrying after fetch+rebase..."

        # A FAILED retry fetch must not be swallowed. `|| true` left @{u} stale,
        # after which the recomputation below can read remote_ahead == 0, decide
        # "not blocked", and act on a world it never saw — surfacing later as a
        # generic push/rebase error instead of the true outcome. Same contract as
        # do_fetch: report the network, stop the run.
        local refetch_exit=0
        _git_with_timeout fetch origin 2>/dev/null || refetch_exit=$?
        if [[ $refetch_exit -ne 0 ]]; then
            batch_out "NO_NETWORK"
            if [[ "$BATCH_MODE" == false ]]; then
                warn "Push rejected and the follow-up fetch failed (rc=$refetch_exit)"
            fi
            exit 0
        fi

        local retry_local retry_remote
        retry_local=$(count_local_ahead)
        retry_remote=$(count_remote_ahead)
        if ! _load_incoming; then
            local _ri
            for ((_ri = 0; _ri < ${#PROT_STATE[@]}; _ri++)); do PROT_STATE[_ri]="unknown"; done
        fi

        # With protected files that genuinely block, the rebase below is actively
        # wrong: `pull --rebase` refuses (rc 128), the old `|| true` SWALLOWED
        # that, the still-un-rebased push was rejected again, and the run reported
        # ERROR:push_failed — blaming the push for a failure the protected files
        # caused, and bypassing the protection entirely.
        if (( ${#PROT_REASON[@]} )) && _rebase_blocked "$retry_local" "$retry_remote"; then
            _emit_protected_deferral
            iwarn "Push deferred: protected files block the rebase this push needs."
            return 2
        fi

        # Through do_pull_rebase, never a bare `pull --rebase`: on conflict that
        # one left `rebase-merge` behind for the next ./ait git write to trip
        # over (t1725_1). do_pull_rebase aborts, and reports CONFLICT: / ERROR:
        # itself.
        if ! do_pull_rebase "$retry_remote"; then
            batch_out "ERROR:push_rebase_failed"
            if [[ "$BATCH_MODE" == false ]]; then
                warn "Push rejected and the follow-up rebase failed"
            fi
            return 1
        fi
        local retry_exit=0
        _git_with_timeout push origin 2>/dev/null || retry_exit=$?

        if [[ $retry_exit -ne 0 ]]; then
            batch_out "ERROR:push_failed"
            if [[ "$BATCH_MODE" == false ]]; then
                warn "Push failed after retry"
            fi
            return 1
        fi
    fi
    return 0
}

# --- Main ---
main() {
    # Step 1: Detect mode
    _ait_detect_data_worktree

    # Step 1b: Refuse early on a wedged data worktree.
    #
    # This MUST come before check_remote: that helper runs
    # `task_git remote get-url origin &>/dev/null`, and `remote` is on neither
    # the read-only nor the recovery allowlist, so assert_data_worktree_clean
    # die()s — with the message swallowed by `&>/dev/null`. The script would
    # exit 1 with empty stdout and empty stderr, which every consumer classifies
    # as `ERROR: empty output from sync script`.
    local wedged
    if wedged="$(_worktree_wedged)"; then
        _note_skip "data worktree is stuck mid-${wedged} — nothing swept; resolve the rebase/merge first"
        report_skipped
        batch_out "DEFERRED:worktree_wedged:${wedged}"
        iwarn "Data worktree is stuck mid-${wedged}. Resolve it, then re-run sync."
        exit 0
    fi

    # Step 2: Check for remote
    check_remote

    # Step 3: Auto-commit uncommitted changes (per owning task; see auto_commit)
    auto_commit

    # Step 4: Count local-ahead commits
    local local_ahead
    local_ahead=$(count_local_ahead)

    # Step 5: Fetch with timeout
    do_fetch

    # Step 6: Count remote-ahead commits
    local remote_ahead
    remote_ahead=$(count_remote_ahead)

    report_skipped

    # Which incoming paths a pull would check out. Computed once, after the
    # fetch, and consumed by _rebase_blocked. An UNKNOWN incoming set is not an
    # empty one: fail closed by marking every record unclassifiable, so the gate
    # blocks rather than waving a possible overwrite through.
    if ! _load_incoming; then
        local _pi
        for ((_pi = 0; _pi < ${#PROT_STATE[@]}; _pi++)); do PROT_STATE[_pi]="unknown"; done
    fi

    # Two early exits, in this order. They are ORTHOGONAL outcomes:
    #
    #   1. publication_blocked — we hold a commit whose content we cannot vouch
    #      for. Blocks the PUSH, and must NOT be gated on remote_ahead: the race
    #      advances refs/heads/aitask-locks, never aitask-data, so
    #      remote_ahead == 0 is its normal shape and a rebase-gated guard would
    #      detect the mismatch and then push it anyway.
    #   2. protected_dirty — files we could not commit are still dirty. Whether
    #      that blocks the REBASE is decided by _rebase_blocked's five-way rule
    #      (tree state x local_ahead x remote_ahead x incoming), NOT by the mere
    #      existence of a protected file. The old "any protected file and the
    #      remote is ahead" test deferred two cases nothing actually blocks: an
    #      untracked file no incoming commit touches, and a behind-only branch
    #      that can simply fast-forward.
    if (( ${#PUBLICATION_BLOCKED[@]} )); then
        batch_out "DEFERRED:publication_blocked:${#PUBLICATION_BLOCKED[@]} path(s) withheld"
        iwarn "Sync deferred: ${#PUBLICATION_BLOCKED[@]} path(s) under publication quarantine — nothing pushed."
        exit 0
    fi
    if (( ${#PROT_REASON[@]} )) && _rebase_blocked "$local_ahead" "$remote_ahead"; then
        _emit_protected_deferral
        iwarn "The fetch still ran, so the branch is up to date on disk."
        exit 0
    fi

    # Step 7: Converge with the remote when it has commits.
    #
    # Two ways to converge, and the choice is not a preference. With no local
    # commits a FAST-FORWARD is the right move and the only one available while
    # protected files are dirty: it never conflicts, and git refuses it outright
    # if it would overwrite a dirty file — a case _rebase_blocked already
    # excluded above. This mirrors task_data_converge's ff-only rule (t1658_1)
    # and is what lets a behind-only branch converge instead of deferring
    # forever behind someone else's parked session (t1696).
    local did_pull=false
    if [[ "$remote_ahead" -gt 0 ]]; then
        if [[ "$local_ahead" -eq 0 ]] && (( ${#PROT_REASON[@]} )); then
            if task_git merge --ff-only --quiet "@{u}" 2>/dev/null; then
                did_pull=true
            elif do_pull_rebase "$remote_ahead"; then
                did_pull=true
            else
                exit 1
            fi
        elif do_pull_rebase "$remote_ahead"; then
            did_pull=true
        else
            # Pull failed (non-batch conflict resolution or error)
            exit 1
        fi
    fi

    # Step 8: Push if local has commits (recount after possible rebase)
    local did_push=false
    local_ahead=$(count_local_ahead)
    if [[ "$local_ahead" -gt 0 ]]; then
        local push_rc=0
        do_push "$local_ahead" || push_rc=$?
        case $push_rc in
            0) did_push=true ;;
            2) exit 0 ;;   # deferred, not failed — do_push already emitted its token
            *) exit 1 ;;
        esac
    fi

    # Step 9: Output result
    if [[ "$_PULL_AUTOMERGED" == true ]]; then
        batch_out "AUTOMERGED"
        isuccess "Sync complete: conflicts auto-merged"
    elif [[ "$did_push" == true && "$did_pull" == true ]]; then
        batch_out "SYNCED"
        isuccess "Sync complete: pushed and pulled changes"
    elif [[ "$did_push" == true ]]; then
        batch_out "PUSHED"
        isuccess "Sync complete: pushed $local_ahead commits"
    elif [[ "$did_pull" == true ]]; then
        batch_out "PULLED"
        isuccess "Sync complete: pulled $remote_ahead commits"
    else
        batch_out "NOTHING"
        isuccess "Already up to date"
    fi
}

main
