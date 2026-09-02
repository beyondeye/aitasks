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
#                              (Per-file skip reasons such as an unreadable lock
#                              branch are reported on stderr and roll up into
#                              protected_dirty here.)
#   ERROR:<message>            Unexpected error

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

# --- Configuration ---
BATCH_MODE=false
NETWORK_TIMEOUT=10
# Opt-ins for the auto-commit sweep (t1599_3). All three default OFF: each one
# trades safety for availability, and that call is the operator's to make
# explicitly, never a silent consequence of an outage or a timer.
COMMIT_UNOWNED=false
ASSUME_UNLOCKED=false
RELEASE_QUARANTINE=false

# --- Auto-merge support (best-effort) ---
# resolve_python may return empty in fully-stripped environments; try_auto_merge
# already guards on $_MERGE_PYTHON being non-empty before invoking it.
_MERGE_PYTHON="$(resolve_python)"
_MERGE_SCRIPT="$SCRIPT_DIR/board/aitask_merge.py"

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
                             protected_dirty, worktree_wedged. Per-file skip
                             reasons go to stderr, not here.
  ERROR:<message>            Unexpected error

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

# Only show interactive messages in non-batch mode
iinfo() {
    if [[ "$BATCH_MODE" == false ]]; then
        info "$1"
    fi
}

# Interactive info routed to STDERR. For use inside functions whose STDOUT is a
# data channel — `try_auto_merge` returns the unresolved-file list on stdout, so
# a progress line written there is parsed by the caller as a conflicted
# filename and the interactive loop then opens $EDITOR on it.
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
#   PROTECTED_DIRTY      files we could not commit are still dirty. Blocks the
#                        REBASE, and only matters when remote_ahead > 0.
#   PUBLICATION_BLOCKED  we made a commit whose content we cannot vouch for.
#                        Blocks the PUSH, regardless of remote_ahead — the race
#                        advances refs/heads/aitask-locks, never aitask-data, so
#                        remote_ahead == 0 is its NORMAL shape and a
#                        rebase-gated guard would detect it and push anyway.
PROTECTED_DIRTY=()
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

_protect() {   # <reason> <human line>
    PROTECTED_DIRTY+=("$1")
    _note_skip "$2"
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
            *)     out+="$c" ;;
        esac
    done
    printf '%s' "$out"
}
_pct_decode() {
    local sVar="$1"
    sVar="${sVar//%0A/$'\n'}"
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
declare -A LOCK_HOST=() LOCK_PID=() LOCK_START=() LOCK_KIND=()
LOCKS_STATUS=""

# Populate the snapshot from ONE `aitask_lock.sh --list --batch` call (one
# ls-remote + one fetch, regardless of how many locks exist).
_lock_snapshot() {
    LOCK_HOST=(); LOCK_PID=(); LOCK_START=(); LOCK_KIND=()
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
                : "$lemail"
                ;;
        esac
    done <<< "$out"
    # A snapshot with no verdict line is not a snapshot. Fail safe.
    [[ -n "$LOCKS_STATUS" ]] || LOCKS_STATUS="LOCKS_UNAVAILABLE"
}

# free | alive | dead | unknown — the routing verdict for ONE task.
# `dead` is the only verdict that permits committing another session's file.
_holder_verdict() {
    local tid="$1" h cur
    [[ "$ASSUME_UNLOCKED" == true ]] && { printf 'free'; return 0; }
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
    dirtyf="$(mktemp)" || { _protect "scan_failed" "could not allocate a scratch file — nothing swept"; return 0; }
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
        _protect "scan_failed" "could not read the worktree status — nothing swept"
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
        _protect "lock_contended" "another sync holds the data-index lock — nothing swept"
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
    local -a ent_path=() ent_owner=()
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
                # PRESCRIPTIVE: nothing else will ever commit these files, so an
                # ownerless dirty file is a standing state a human must clear.
                _protect "ownerless" "ownerless, NOT auto-committed: $path — nothing else commits this file. Clear it with: ./ait git add '$path' && ./ait git commit -m 'ait: Update ${path##*/}'   (or re-run with --commit-unowned)"
                continue
            fi
        fi

        # An entry that legitimately names two paths gets no guessed owner.
        if [[ -n "$orig" ]]; then
            if ! owner2="$(_owner_of_path "$orig")" || [[ "$owner2" != "$owner" ]]; then
                _protect "ambiguous_rename" "ambiguous cross-task rename, skipped: '$path' <- '$orig'"
                continue
            fi
        fi

        # Resolve BOTH halves before adding EITHER: a failure on the source
        # side must not leave a half-added rename in the group.
        local st_orig=""
        if ! st="$(_path_state "$path")"; then
            _protect "unverifiable" "could not hash (skipped): $path"
            continue
        fi
        if [[ -n "$orig" ]] && ! st_orig="$(_path_state "$orig")"; then
            _protect "unverifiable" "could not hash (skipped): $orig"
            continue
        fi
        PATH_STATE["$path"]="$st"
        ent_path+=("$path"); ent_owner+=("$owner"); owner_seen["$owner"]=1
        if [[ -n "$orig" ]]; then
            PATH_STATE["$orig"]="$st_orig"
            ent_path+=("$orig"); ent_owner+=("$owner")
        fi
    done

    (( ${#owner_seen[@]} )) || return 0

    # An unreadable lock branch is NOT evidence of no locks; an outage can
    # easily coincide with a live editor. The operator makes the
    # availability-over-safety call explicitly, never a network failure.
    if ! _locks_readable && [[ "$ASSUME_UNLOCKED" != true ]]; then
        local tid
        for tid in "${!owner_seen[@]}"; do
            _protect "locks_unavailable" "lock branch unreadable — skipped t${tid}'s files (re-run with --assume-unlocked to override)"
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
            alive)   _protect "live_lock" "t${tid} is locked by a LIVE session on ${LOCK_HOST[$tid]:-?} — its files left dirty for that session to commit" ;;
            *)       _protect "unknown_liveness" "t${tid}'s holder could not be verified as gone (${LOCK_HOST[$tid]:-?}) — treated as live, files left dirty" ;;
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
            _protect "lock_acquired_during_scan" "t${tid} was locked while we were scanning — skipped"
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
        _protect "staged_elsewhere" "t${tid}: another session has staged $(echo "$staged" | tr '\n' ' ')— group deferred"
        return 0
    fi

    # Step 5a.3 — re-derive the STATE (not just a hash) immediately before the
    # commit and require it to be unchanged. Both transition directions matter:
    # absent->present is a deleted file another session recreated, which a
    # hash-only check cannot see at all.
    for p in "${paths[@]}"; do
        if ! now="$(_path_state "$p")"; then
            _protect "unverifiable" "t${tid}: could not re-hash $p — group skipped"
            return 0
        fi
        # `:-` guard: a miss must degrade to "skip this group", never abort the
        # script under `set -u` with no stdout.
        if [[ "$now" != "${PATH_STATE[$p]:-}" ]]; then
            _protect "content_changed" "t${tid}: $p changed after classification — group skipped"
            return 0
        fi
    done

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
        _protect "commit_failed" "t${tid}: commit failed — files left dirty"
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

# --- Auto-merge conflicted task/plan files ---
# try_auto_merge <conflicted_files_newline_separated>
# Attempts auto-merge for each task/plan file using Python merge script.
# Outputs remaining unresolved files (newline-separated) to stdout.
# Returns 0 if ALL resolved, 1 if any remain unresolved.
try_auto_merge() {
    local conflicted="$1"
    local unresolved=""
    local resolved_count=0

    if [[ -z "$_MERGE_PYTHON" ]] || [[ ! -f "$_MERGE_SCRIPT" ]]; then
        echo "$conflicted"
        return 1
    fi

    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        case "$f" in
            aitasks/*.md|aiplans/*.md)
                local file_path merge_exit=0
                file_path="$(_resolve_conflict_path "$f")"
                # Supply the MERGE BASE from git's conflicted index (stage 1 =
                # base, 2 = ours, 3 = theirs). The diff3 marker base is not an
                # option: `merge.conflictStyle` is configured nowhere, so git
                # emits 2-way markers and the parser has no ancestor to read.
                # `$f` (repo-relative), never `$file_path` — a `:1:` pathspec is
                # resolved against the repo, not the filesystem.
                # `show` is on assert_data_worktree_clean's read-only allowlist,
                # so this works while the rebase is wedged. An add/add conflict
                # has no stage 1; the extraction fails, no flag is passed, and
                # base-aware fields fail closed to PARTIAL.
                local base_tmp base_args=()
                base_tmp="$(mktemp)"
                if task_git show ":1:$f" > "$base_tmp" 2>/dev/null; then
                    base_args=(--base-file "$base_tmp")
                else
                    rm -f "$base_tmp"
                    base_tmp=""
                fi
                # STDOUT of this function IS the unresolved-file list its caller
                # parses, so the driver's own stdout ("RESOLVED" / "PARTIAL:...")
                # must not leak into it — it was being reported as a conflicted
                # filename (`CONFLICT:RESOLVED`). Only the exit status matters.
                PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$SCRIPT_DIR/board" "$_MERGE_PYTHON" "$_MERGE_SCRIPT" "$file_path" --batch --rebase ${base_args[@]+"${base_args[@]}"} >/dev/null 2>&1 || merge_exit=$?
                if [[ -n "$base_tmp" ]]; then rm -f "$base_tmp"; fi
                if [[ $merge_exit -eq 0 ]]; then
                    # The state-check guard rejects mutating verbs while the data
                    # worktree is mid-rebase — but staging a resolved conflict is
                    # exactly what this code path exists to do, and it owns that
                    # rebase. Scope the documented bypass to this one call.
                    local add_err add_rc=0
                    add_err="$(AIT_GIT_SKIP_STATE_CHECK=1 task_git add "$f" 2>&1)" || add_rc=$?
                    if [[ $add_rc -eq 0 ]]; then
                        resolved_count=$((resolved_count + 1))
                        iinfo_err "Auto-merged: $f"
                    else
                        # A file we could not stage is an UNRESOLVED merge, not a
                        # resolved one: `rebase --continue` would fail later with
                        # the diagnostic already discarded. warn() -> stderr,
                        # never info()/iinfo(), which write to the data channel.
                        warn "auto-merge could not stage $f (git add rc=$add_rc): ${add_err:-<no output>}"
                        unresolved="${unresolved}${unresolved:+$'\n'}$f"
                    fi
                else
                    unresolved="${unresolved}${unresolved:+$'\n'}$f"
                fi
                ;;
            *)
                unresolved="${unresolved}${unresolved:+$'\n'}$f"
                ;;
        esac
    done <<< "$conflicted"

    if [[ -z "$unresolved" ]]; then
        iinfo_err "Auto-merged $resolved_count file(s)"
        return 0
    else
        [[ $resolved_count -gt 0 ]] && iinfo_err "Auto-merged $resolved_count file(s), remaining conflicts need manual resolution"
        echo "$unresolved"
        return 1
    fi
}

# --- Rebase advancement helper ---
# Try rebase --continue, fall back to --skip for empty patches (when
# auto-merge result matches the current HEAD exactly, git sees "nothing to commit").
_rebase_advance() {
    if GIT_EDITOR=true task_git rebase --continue &>/dev/null; then
        return 0
    fi
    # If no unresolved files remain, this is an empty patch — skip it
    local unresolved
    unresolved=$(task_git diff --name-only --diff-filter=U 2>/dev/null || true)
    if [[ -z "$unresolved" ]] && task_git rebase --skip &>/dev/null; then
        return 0
    fi
    return 1
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
            # Try auto-merge first
            local remaining=""
            local merge_rc=1
            remaining=$(try_auto_merge "$conflicted") && merge_rc=0 || merge_rc=$?

            if [[ $merge_rc -eq 0 ]]; then
                # All conflicts auto-resolved — advance rebase (may loop for multi-commit)
                local continue_ok=true
                while true; do
                    if _rebase_advance; then
                        break  # rebase complete
                    fi
                    # Check for new conflicts from next commit
                    local new_conflicted
                    new_conflicted=$(task_git diff --name-only --diff-filter=U 2>/dev/null || true)
                    if [[ -n "$new_conflicted" ]]; then
                        local new_remaining=""
                        local new_merge_rc=1
                        new_remaining=$(try_auto_merge "$new_conflicted") && new_merge_rc=0 || new_merge_rc=$?
                        if [[ $new_merge_rc -ne 0 ]]; then
                            # Can't auto-merge this round
                            if [[ "$BATCH_MODE" == true ]]; then
                                task_git rebase --abort 2>/dev/null || true
                                local conflict_list
                                conflict_list=$(echo "$new_remaining" | tr '\n' ',' | sed 's/,$//')
                                batch_out "CONFLICT:${conflict_list}"
                                exit 0
                            else
                                warn "Auto-merged earlier commits, but new conflicts in:"
                                echo "$new_remaining" | while IFS= read -r f; do echo "  - $f"; done
                                remaining="$new_remaining"
                                continue_ok=false
                                break
                            fi
                        fi
                        # new conflicts also auto-merged, loop to advance rebase
                    else
                        # rebase advance failed for non-conflict reason
                        task_git rebase --abort 2>/dev/null || true
                        batch_out "ERROR:rebase_continue_failed"
                        return 1
                    fi
                done

                if [[ "$continue_ok" == true ]]; then
                    _PULL_AUTOMERGED=true
                    isuccess "All conflicts auto-merged successfully"
                    return 0
                fi
                # If continue_ok=false, fall through to interactive handling with $remaining
            fi

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
                    if $editor "$(_resolve_conflict_path "$f")"; then
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
                    if ! _rebase_advance; then
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

# Resolve the file path for editing during conflict resolution
_resolve_conflict_path() {
    local file="$1"
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        echo "$_AIT_DATA_WORKTREE/$file"
    else
        echo "$file"
    fi
}

# --- Push with retry ---
do_push() {
    local local_count="$1"
    iinfo "Pushing $local_count commits to remote..."

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

        # With protected files present the retry below is actively wrong:
        # `pull --rebase` refuses (rc 128), the old `|| true` SWALLOWED that,
        # the still-un-rebased push was rejected again, and the run reported
        # ERROR:push_failed — blaming the push for a failure the protected files
        # caused, and bypassing the protection entirely.
        if (( ${#PROTECTED_DIRTY[@]} )); then
            batch_out "DEFERRED:protected_dirty:${#PROTECTED_DIRTY[@]} file(s) held by other sessions"
            iwarn "Push deferred: protected files block the rebase this push needs."
            return 2
        fi

        # Retry once (remote may have advanced during our rebase)
        iinfo "Push rejected, retrying after fetch+rebase..."
        _git_with_timeout fetch origin 2>/dev/null || true
        # Route on the rebase's exit status instead of blind-retrying a push
        # that cannot succeed: swallowing it is what turns a diagnosable cause
        # into a bare ERROR:push_failed.
        local rebase_exit=0
        task_git pull --rebase --quiet 2>/dev/null || rebase_exit=$?
        if [[ $rebase_exit -ne 0 ]]; then
            batch_out "ERROR:push_rebase_failed"
            if [[ "$BATCH_MODE" == false ]]; then
                warn "Push rejected and the follow-up rebase failed (rc=$rebase_exit)"
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

    # Two early exits, in this order. They are ORTHOGONAL outcomes:
    #
    #   1. publication_blocked — we hold a commit whose content we cannot vouch
    #      for. Blocks the PUSH, and must NOT be gated on remote_ahead: the race
    #      advances refs/heads/aitask-locks, never aitask-data, so
    #      remote_ahead == 0 is its normal shape and a rebase-gated guard would
    #      detect the mismatch and then push it anyway.
    #   2. protected_dirty — files we could not commit are still dirty, which
    #      blocks the REBASE. `git pull --rebase` refuses with unstaged changes
    #      (rc 128), so with the remote ahead this run would die at
    #      ERROR:pull_rebase_failed. With remote_ahead == 0 it is NOT a
    #      deferral: do_push needs no clean tree, so eligible commits publish.
    if (( ${#PUBLICATION_BLOCKED[@]} )); then
        batch_out "DEFERRED:publication_blocked:${#PUBLICATION_BLOCKED[@]} path(s) withheld"
        iwarn "Sync deferred: ${#PUBLICATION_BLOCKED[@]} path(s) under publication quarantine — nothing pushed."
        exit 0
    fi
    if (( ${#PROTECTED_DIRTY[@]} )) && [[ "$remote_ahead" -gt 0 ]]; then
        batch_out "DEFERRED:protected_dirty:${#PROTECTED_DIRTY[@]} file(s) held by other sessions"
        iwarn "Sync deferred: ${#PROTECTED_DIRTY[@]} protected file(s) block the rebase; the fetch still ran."
        exit 0
    fi

    # Step 7: Pull rebase if remote has commits
    local did_pull=false
    if [[ "$remote_ahead" -gt 0 ]]; then
        if do_pull_rebase "$remote_ahead"; then
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
