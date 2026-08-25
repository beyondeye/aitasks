#!/usr/bin/env bash
# stale_lock.sh - shared mkdir mutex with single-winner stale reclaim (t1496).
# Source this file from aitask scripts; do not execute directly.
#
# Used by aitask_gate.sh (per-task gate-ledger appends) and aitask_create.sh
# (per-parent child creation). Both previously carried a verbatim copy of a
# stat-then-mv stale reclaim that was NOT single-winner: a contender could act
# on a staleness verdict formed before another contender's reclaim+re-mkdir
# cycle, and move away the fresh live lock (two holders in the critical
# section — reproduced 3/25 rounds; see aiplans p1496).
#
# Invariants (do NOT relax — see the t1496 plan):
#   1. All lock-directory mutations — identity publication at acquire,
#      owner-checked release, reclaim observation+destruction — are serialized
#      by the `.gc` guard dir (<lock_dir>.gc, a mkdir mutex). Only the
#      protected application operation runs outside it. A staleness verdict is
#      therefore always acted on in the same guard section it was formed in.
#   2. `.gc` is never stolen from a LIVE holder, and never has two holders.
#      The claim is TWO steps and both are load-bearing: the single-winner
#      `mkdir "$gc"`, then a holder record (<gc>/h.<pid>.<nonce>) whose
#      read-back must find it ALONE. The read-back is what closes the window in
#      which the guard is observably empty — a creator paused there past the
#      markerless window has its guard reclaimed, and would otherwise publish
#      into the reclaimer's instance and hold alongside it. At most one
#      contender can ever see itself alone (see _stale_lock_gc_sole_record), so
#      a lost race costs an attempt, never correctness.
#
#      A guard whose record names a provably dead pid is reclaimed by an
#      instance-keyed disarm — so a staleness verdict can only ever destroy the
#      exact instance it was formed against, never a live replacement. Liveness
#      decides at ANY duration; age never enters the decision for a guard that
#      has a record. A guard with NO record (pre-t1598 code, or a foreign
#      holder) is reclaimed only where the caller passes a window
#      (stale_lock_acquire's 5th arg) AND only after that window — never by
#      default, and never for merge_lock, whose guarded section runs
#      `git reset --hard`. Any other guard content fails closed.
#   3. A live PID is never displaced; a dead PID may be reclaimed. Liveness is
#      `kill -0` with EPERM counted as alive. A lock dir with no readable
#      numeric pid file is legacy/foreign: reclaimed only when older than
#      _STALE_LOCK_WINDOW seconds, else waited on. PID reuse can leave an
#      orphaned lock (conservative; manual recovery via the error hint).
#   4. Release requires the unguessable owner token returned by acquire; the
#      lock is removed only on token match, so a process whose lock was
#      reclaimed never deletes the new owner's.
#   5. Lock paths are per-user, per-repository, and test-overridable — see
#      ait_lock_dir below.
#   6. Cleanup failures are propagated: removals are verified, and a retained
#      lock or guard is warned about and returned as failure, never reported
#      as success.
#
# Documented limitations:
#   - Rolling upgrade: an old-code process running while this lands uses the
#     old fixed /tmp path and is invisible to the new lock.
#   - Rolling upgrade, guard records (t1598): a process running pre-t1598 code
#     creates guards with NO holder record, and new code cannot tell one held by
#     a live old-code process from one leaked days ago — a recordless guard
#     carries exactly one bit, its mtime. This is why markerless reclaim is
#     opt-in per lock dir and off by default: it is enabled only where no
#     shipped version can hold that lock's guard across an unbounded operation.
#     In the dangerous direction the asymmetry holds — old code's bare
#     `rmdir "$gc"` fails ENOTEMPTY against a record, so it cannot destroy a new
#     holder's guard, and its `mkdir` fails, so it fails closed rather than
#     acquiring alongside us.
#   - PID reuse on a guard record: a recycled holder pid reads as alive, so that
#     guard is never reclaimed and the manual cure still applies. Fail-SAFE: it
#     can only prevent a reclaim, never authorize a wrong one.
#   - A guard whose holder is hung (not dead) is never reclaimed, by design —
#     the same rule invariant 3 applies to lock holders.
#   - The per-UID base means two DIFFERENT users sharing one checkout do not
#     serialize against each other by default (the old world-writable /tmp
#     lock did, unsafely). Point AITASKS_LOCK_DIR at an admin-created shared
#     base for that setup.
#   - Callers hold one lock at a time and acquire/release from the main script
#     process (the recorded holder pid is $$). Never invoke stale_lock_acquire
#     inside a command substitution: the returned STALE_LOCK_TOKEN would be
#     stranded in the subshell (redirect stderr to a file instead if you need
#     to capture the warnings).
#
# Requires warn() from terminal_compat.sh (both callers source it first).

[[ -n "${_AIT_STALE_LOCK_LOADED:-}" ]] && return 0
_AIT_STALE_LOCK_LOADED=1

# Repo identity for the default lock base: this lib's own repo root, never the
# ambient cwd — fixtures that copy .aitask-scripts/ into a temp repo get an
# isolated namespace for free.
_AIT_STALE_LOCK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"

# Legacy/foreign locks (no pid file) older than this are reclaimable.
_STALE_LOCK_WINDOW="${_STALE_LOCK_WINDOW:-120}"

# A guard with NO holder record — one left by a process killed in the two-syscall
# window between `mkdir "$gc"` and the record write, or one created by pre-t1598
# code — is reclaimable only when older than this AND only where the caller opts
# in by passing it (see stale_lock_acquire's 5th argument). A guard that HAS a
# record is decided by liveness, never by age, at any duration.
#
# Deliberately not exported, same as _STALE_LOCK_WINDOW: a child bash re-defaults
# it, and policy must not be inherited by a process that did not ask for it.
_STALE_LOCK_GC_WINDOW_DEFAULT="${_STALE_LOCK_GC_WINDOW_DEFAULT:-600}"

# Basename prefix of the guard's holder-record directory: <gc>/h.<pid>.<nonce>.
_STALE_LOCK_GC_MARK_PREFIX="h."

# --- Opt-in seams (all default-off; unset => this file behaves exactly as it
# --- did before they existed, so no existing caller changes behaviour) ------
#
#   STALE_LOCK_IDENTITY_PID   Value written into <lock_dir>/pid at publish time
#                             INSTEAD of $$, and compared on read-back. Both
#                             sites, always: overriding only the write makes the
#                             read-back compare the override against $$, fail,
#                             and take the partial-publish unwind path - i.e.
#                             every acquire would fail closed. The owner token
#                             keeps its own $$ prefix (it is per-process
#                             uniqueness, not identity). For a holder whose
#                             reservation must outlive the acquiring process,
#                             set this to a durable session anchor.
#   _STALE_LOCK_LIVENESS_FN   Called as `<fn> <lock_dir>` at the TOP of
#                             _stale_lock_reclaim_under_gc, under the guard.
#                             SOLE authority on the holder verdict: exit 0 =
#                             do not displace, 1 = reclaim. Bypasses both the
#                             kill -0 branch and the tokenless-age branch,
#                             because a durable anchor is not this process tree.
#   STALE_LOCK_PUBLISH_FN     Called as `<fn> <lock_dir>` INSIDE the .gc guard,
#                             after pid/owner are written and read-back-verified
#                             and before the guard is dropped. Nonzero is a
#                             publish failure and takes the existing
#                             unwind-and-fail-closed path. This seam exists
#                             because the guard is released inside
#                             stale_lock_acquire before it returns, so a caller
#                             cannot make its own identity files atomic with the
#                             acquisition from the outside.
#
# None of these relax the invariants above: identity is still published under
# the guard and verified on read-back, a verdict is still formed and acted on in
# one guarded section, and a publish failure still fails closed.

# ait_lock_dir <name> — echo the resolved lock dir path for <name>.
# $AITASKS_LOCK_DIR (the documented test/deployment seam) wins; otherwise a
# per-user, per-repo base under $TMPDIR. Returns 1 (with a warn) when the
# default base path exists but is not a directory owned by the current uid —
# never chmods or trusts a foreign path (the base name is predictable, and a
# foreign owner could delete live locks regardless of sticky bits).
ait_lock_dir() {
    local name="$1" base
    if [[ -n "${AITASKS_LOCK_DIR:-}" ]]; then
        base="$AITASKS_LOCK_DIR"
        if [[ ! -d "$base" ]]; then
            mkdir -p "$base" 2>/dev/null || { warn "stale_lock: cannot create AITASKS_LOCK_DIR '$base'"; return 1; }
        fi
    else
        local cks
        cks="$(printf '%s' "$_AIT_STALE_LOCK_ROOT" | cksum | awk '{print $1}')"
        base="${TMPDIR:-/tmp}/aitask-locks-$(id -u)-${cks}"
        # Atomic owner-only creation: a plain mkdir honors the caller's umask,
        # and a permissive umask would expose a world-writable window.
        if ! (umask 077; mkdir "$base" 2>/dev/null); then
            if [[ -L "$base" ]]; then
                warn "stale_lock: lock base '$base' is a symlink — refusing"
                return 1
            fi
            if [[ ! -d "$base" ]]; then
                warn "stale_lock: lock base '$base' exists and is not a directory — refusing"
                return 1
            fi
            local owner_uid
            owner_uid="$(stat -c %u "$base" 2>/dev/null || stat -f %u "$base" 2>/dev/null)"
            if [[ "$owner_uid" != "$(id -u)" ]]; then
                warn "stale_lock: lock base '$base' is owned by uid ${owner_uid:-?} — refusing"
                return 1
            fi
            chmod 700 "$base" 2>/dev/null || true
        fi
    fi
    printf '%s/%s\n' "$base" "$name"
}

# stale_lock_describe <lock_dir> — echo a human recovery hint for an exhausted
# acquire: the resolved dir, the recorded holder pid when readable, and the
# guard dir when one exists. Appended by callers after their pinned die text.
stale_lock_describe() {
    local lock_dir="$1" pid hint
    pid="$(cat "$lock_dir/pid" 2>/dev/null || true)"
    if [[ -n "$pid" ]]; then
        hint=" (held by pid $pid at $lock_dir — remove that directory if that process is gone"
    else
        hint=" (lock at $lock_dir — remove it if its holder is gone"
    fi
    if [[ -e "${lock_dir}.gc" ]]; then
        local gc_pid
        gc_pid="$(_stale_lock_gc_holder "${lock_dir}.gc" 2>/dev/null || true)"
        if [[ -n "$gc_pid" ]]; then
            hint+="; stale-reclaim guard ${lock_dir}.gc held by pid $gc_pid"
            hint+=" — it self-heals once that process is gone"
        else
            # The cure is still rmdir-only (rmdir cannot destroy a lock's
            # contents, which is why it is prescribed) but it is now TWO
            # arguments: a guard carrying a holder record is not empty, so a
            # bare `rmdir <dir>.gc` returns ENOTEMPTY.
            hint+="; stale-reclaim guard ${lock_dir}.gc present with no holder"
            hint+=" record — remove with: rmdir '${lock_dir}.gc'/h.* '${lock_dir}.gc'"
        fi
    fi
    printf '%s)' "$hint"
}

# _stale_lock_rm_verified <dir> — rm -rf and verify the path is gone. A failed
# removal is a retained dir: warn and return 1, never claim the state changed.
# ONLY for the lock dir, and only while holding the guard: the guard is what
# makes the absence check race-free (no one can re-mkdir the lock while .gc is
# held). Never use this on the guard itself — see _stale_lock_gc_release.
_stale_lock_rm_verified() {
    local d="$1"
    rm -rf "$d" 2>/dev/null || true
    if [[ -e "$d" ]]; then
        warn "stale_lock: could not remove '$d' — retained"
        return 1
    fi
    return 0
}

# --- Guard holder records (t1598) -------------------------------------------
#
# The guard keeps its exact previous lifecycle: one atomic `mkdir` to claim,
# `rmdir` to free, ABSENT when free. The only addition is that whoever wins the
# mkdir immediately publishes an identity record DIRECTORY inside it:
#
#     <lock_dir>.gc/h.<pid>.<nonce>/
#
# The record is IDENTITY, not ownership — the `mkdir "$gc"` is still what grants
# the guard. That distinction is what keeps the design from recursing: making
# the record itself the claim just moves the same contention one level down.
#
# Why the destructive steps are safe. Only two primitives are ever used to
# destroy something, and each is authoritative on its own exit status:
#
#   rmdir <gc>/h.<pid>.<nonce>   names an INSTANCE. A verdict formed against one
#                                instance can never be applied to a later one,
#                                because nonces are never reused.
#   rmdir <gc>                   requires EMPTINESS. A live instance is
#                                non-empty within two syscalls of creation, so a
#                                stale actor cannot remove a fresh guard.
#
# `mv` was considered and rejected: rename resolves by PATH, so a contender that
# judged instance I1 stale and then stalled would happily rename away instance
# I2 — a live, legitimately-held guard — after someone else reclaimed and
# republished in between.

# _stale_lock_gc_holder <gc_dir> — classify the guard's contents.
# Echoes the holder pid and returns 0 for exactly one WELL-FORMED record.
# Returns 1 for a genuinely empty guard (the only markerless state that may
# reach an age branch), and 2 for every malformed or foreign state.
#
# Malformed is FAIL-CLOSED BY RULE, not by luck. Measured: a dangling symlink
# named h.<pid>.<nonce> is invisible to `[[ -e ]]`, so a naive glob reads the
# guard as empty and takes the age path — stopped only by rmdir's incidental
# ENOTEMPTY. Safety must not rest on that, so entries are enumerated with
# `-e || -L` and a record must be a real directory.
_stale_lock_gc_holder() {
    local gc="$1" entry base found="" extra=0 pid
    for entry in "$gc"/* "$gc"/.[!.]*; do
        [[ -e "$entry" || -L "$entry" ]] || continue
        base="${entry##*/}"
        case "$base" in
            "$_STALE_LOCK_GC_MARK_PREFIX"*) ;;
            *) extra=1; continue ;;          # foreign content: never age-reclaim
        esac
        [[ -d "$entry" && ! -L "$entry" ]] || { extra=1; continue; }
        pid="${base#"$_STALE_LOCK_GC_MARK_PREFIX"}"
        pid="${pid%%.*}"
        [[ "$pid" =~ ^[0-9]+$ ]] || { extra=1; continue; }
        if [[ -n "$found" ]]; then extra=1; continue; fi
        found="$pid"
    done
    if [[ "$extra" -ne 0 ]]; then return 2; fi
    if [[ -z "$found" ]]; then return 1; fi
    printf '%s\n' "$found"
    return 0
}

# _stale_lock_gc_sole_record <gc_dir> <mark> — read-back: is <mark> the ONLY
# entry in the guard? Returns 0 iff it is.
#
# THIS IS WHAT MAKES THE CLAIM SINGLE-WINNER, and it is not optional. `mkdir
# "$gc"` alone is not enough, because the guard is observably EMPTY between that
# call and the record write: a process paused there (SIGSTOP, a suspended VM, a
# pathologically loaded box) past the markerless window has its guard reclaimed,
# and when it resumes its `mkdir "$gc/$mark"` lands inside the RECLAIMER's
# instance — leaving two processes each believing they hold the mutex.
# Reproduced before this check existed.
#
# Why the read-back closes it, rather than merely narrowing it. Each contender
# creates its record before reading, so `mkdir < read` for both. If A's read saw
# only its own record then B's mkdir came after A's read; if B's read saw only
# its own then A's mkdir came after B's read. Together those give
# A.mkdir > B.read > B.mkdir > A.read > A.mkdir — a contradiction. At most one
# contender can ever see itself alone, whatever the interleaving.
#
# The loser removes only its own record, so a lost race costs an attempt, never
# correctness. A third party observing the brief two-record state classifies it
# as unrecognized and fails closed — availability, not corruption.
_stale_lock_gc_sole_record() {
    local gc="$1" mark="$2" entry base
    for entry in "$gc"/* "$gc"/.[!.]*; do
        [[ -e "$entry" || -L "$entry" ]] || continue
        base="${entry##*/}"
        [[ "$base" == "$mark" ]] || return 1
    done
    [[ -d "$gc/$mark" ]]
}

# _stale_lock_gc_probe <gc_dir> <markerless_window> — reclaim decision.
# Returns 0 iff the guard slot CHANGED (caller should retry mkdir at once).
# A live holder is never displaced, at any duration — which is what makes a long
# legitimate guarded section (aitask_merge_task.sh runs `git reset --hard` under
# one) safe without reference to any window.
_stale_lock_gc_probe() {
    local gc="$1" window="${2:-}" holder rc=0 gc_mtime gc_age
    holder="$(_stale_lock_gc_holder "$gc")" || rc=$?
    case "$rc" in
        0)
            if _stale_lock_pid_alive "$holder"; then
                return 1                     # LIVE holder: never displaced
            fi
            # Instance-keyed disarm: this names the exact record we judged, so a
            # verdict that went stale while we were descheduled can only ever
            # fail with ENOENT — it can never reach a replacement instance.
            rmdir "$gc/$_STALE_LOCK_GC_MARK_PREFIX$holder".* 2>/dev/null || return 1
            rmdir "$gc" 2>/dev/null || return 1
            warn "stale_lock: guard '$gc' freed — holder pid $holder is gone"
            return 0
            ;;
        2)
            warn "stale_lock: guard '$gc' holds an unrecognized record — leaving it alone"
            return 1
            ;;
    esac
    # Genuinely empty: pre-t1598 code, a foreign holder, or our own two-syscall
    # publish window. Off unless this caller opted in.
    [[ -n "$window" && "$window" != "0" ]] || return 1
    if ! gc_mtime="$(stat -c %Y "$gc" 2>/dev/null || stat -f %m "$gc" 2>/dev/null)"; then
        return 0                             # vanished between checks: retry now
    fi
    gc_age=$(( $(date +%s) - gc_mtime ))
    [[ "$gc_age" -gt "$window" ]] || return 1
    rmdir "$gc" 2>/dev/null || return 1      # emptiness is the race protection
    warn "stale_lock: guard '$gc' freed — no holder record after ${gc_age}s"
    return 0
}

# _stale_lock_gc_take <gc_dir> [<markerless_window>] — claim the guard.
# 0 = held (record name in _STALE_LOCK_GC_MARK), 1 = busy, 2 = the slot changed
# so the caller should retry immediately without sleeping.
_stale_lock_gc_take() {
    local gc="$1" window="${2:-}" mark
    _STALE_LOCK_GC_MARK=""
    if mkdir "$gc" 2>/dev/null; then
        # Built INLINE, never via `$(...)`: a command substitution runs in a
        # subshell, so `BASHPID` there is that transient subshell's pid — dead
        # the instant it returns. Every guard record would then name a dead
        # process and be reclaimable on sight. Same hazard the header documents
        # for STALE_LOCK_TOKEN, and the reason the owner token below is built
        # inline too. No `date` fork either: this runs on every acquire
        # iteration.
        mark="$_STALE_LOCK_GC_MARK_PREFIX${BASHPID:-$$}.${RANDOM}${RANDOM}"
        if mkdir "$gc/$mark" 2>/dev/null && _stale_lock_gc_sole_record "$gc" "$mark"; then
            _STALE_LOCK_GC_MARK="$mark"
            return 0
        fi
        # Either the record could not be written, or the read-back found company
        # — see _stale_lock_gc_sole_record. Unwind our own record (instance-keyed,
        # so it can never touch anyone else's) and fail closed. The trailing
        # `rmdir` succeeds only if the guard is now empty, i.e. only if nobody
        # else is in it: emptiness is what makes it safe to remove.
        warn "stale_lock: could not record the guard holder in '$gc'"
        rmdir "$gc/$mark" 2>/dev/null || true
        rmdir "$gc" 2>/dev/null || true
        return 1
    fi
    if _stale_lock_gc_probe "$gc" "$window"; then return 2; fi
    return 1
}

# _stale_lock_gc_release <gc_dir> [<mark>] — drop the guard we hold.
#   0 = released   1 = RETAINED (removal failed; we STILL hold it)
#   2 = LOST       (our record is gone: we hold NOTHING, mutate NOTHING)
#
# `rmdir`'s own exit status stays authoritative, for the reason it always was —
# the guard is the one dir another contender may legitimately recreate the
# instant it is free, so "rm then check absence" would misread that replacement
# as our guard being retained — PLUS a stronger one now: a successful
# `rmdir "$gc"` can only have removed an EMPTY `$gc`, and after our own record
# removal the only empty `$gc` at that path is ours (a replacement instance is
# non-empty within two syscalls, and is too fresh for any markerless window).
#
# rc 2 is unreachable without manual `rm -rf`, since a live pid is never judged
# dead — it is a self-check, not a mechanism.
_stale_lock_gc_release() {
    local gc="$1" mark="${2:-}"
    if [[ -n "$mark" ]]; then
        if ! rmdir "$gc/$mark" 2>/dev/null; then
            if [[ -e "$gc/$mark" ]]; then
                warn "stale_lock: guard record '$gc/$mark' could not be dropped"
                return 1
            fi
            warn "stale_lock: guard claim '$gc/$mark' vanished — not touching the guard"
            return 2
        fi
    fi
    if rmdir "$gc" 2>/dev/null; then
        return 0
    fi
    # Genuinely retained. Re-publish so the guard stays identified: without this
    # it would be an empty guard held by a live process, i.e. reclaimable by the
    # markerless window while we still believe we hold it.
    [[ -z "$mark" ]] || mkdir "$gc/$mark" 2>/dev/null || true
    return 1
}

# _stale_lock_run_publish_fn <lock_dir> — dispatch the STALE_LOCK_PUBLISH_FN
# seam. No seam configured is success (the default path publishes pid+owner and
# nothing else). Runs under the guard; a nonzero return is a publish failure.
_stale_lock_run_publish_fn() {
    [[ -n "${STALE_LOCK_PUBLISH_FN:-}" ]] || return 0
    "$STALE_LOCK_PUBLISH_FN" "$1"
}

# _stale_lock_pid_alive <pid> — 0 iff the process exists. EPERM ("we may not
# signal it") counts as alive: fail-safe, never displace what might be running.
_stale_lock_pid_alive() {
    local pid="$1" err rc=0
    err="$(LC_ALL=C kill -0 "$pid" 2>&1)" || rc=$?
    if [[ $rc -eq 0 ]]; then
        return 0
    fi
    [[ "$err" == *"not permitted"* ]]
}

# _stale_lock_reclaim_under_gc <lock_dir> <label> — caller HOLDS the guard.
# Fresh observation + destruction in one guarded section. Returns 0 iff the
# lock-dir state changed (caller should retry mkdir immediately).
_stale_lock_reclaim_under_gc() {
    local lock_dir="$1" label="$2"
    [[ -d "$lock_dir" ]] || return 0            # vanished -> retry mkdir now
    # Seam: a caller whose holder identity is a durable session anchor (not a
    # pid in this process tree) owns the verdict entirely - neither kill -0 nor
    # the tokenless-age window can reason about it.
    if [[ -n "${_STALE_LOCK_LIVENESS_FN:-}" ]]; then
        if "$_STALE_LOCK_LIVENESS_FN" "$lock_dir"; then
            return 1                            # alive or undecidable: never displaced
        fi
        warn "Reclaiming $label from dead holder"
        if _stale_lock_rm_verified "$lock_dir"; then return 0; else return 1; fi
    fi
    local holder
    holder="$(cat "$lock_dir/pid" 2>/dev/null || true)"
    if [[ "$holder" =~ ^[0-9]+$ ]]; then
        if _stale_lock_pid_alive "$holder"; then
            return 1                            # LIVE holder: never displaced
        fi
        warn "Reclaiming $label from dead holder pid $holder"
        if _stale_lock_rm_verified "$lock_dir"; then return 0; else return 1; fi
    fi
    # No/malformed pid: legacy or foreign lock. Age-based, t1188 semantics on
    # a failed stat (dir vanished between -d and stat -> state changed).
    local lock_mtime lock_age
    if ! lock_mtime="$(stat -c %Y "$lock_dir" 2>/dev/null || stat -f %m "$lock_dir" 2>/dev/null)"; then
        return 0
    fi
    lock_age=$(( $(date +%s) - lock_mtime ))
    if [[ "$lock_age" -le "$_STALE_LOCK_WINDOW" ]]; then
        return 1                                # fresh: holder mid-acquire, wait
    fi
    warn "Removing stale $label (age: ${lock_age}s)"
    if _stale_lock_rm_verified "$lock_dir"; then return 0; else return 1; fi
}

# stale_lock_acquire <lock_dir> <retries> <sleep_s> <label> [<gc_window>]
# <gc_window> (t1598, optional) opts this lock dir in to reclaiming a guard that
# carries NO holder record, once it is older than <gc_window> seconds. Unset or
# 0 = never, which is the default and what `stale_lock_release` /
# `stale_lock_guarded_section` always use. A guard that HAS a record is decided
# by liveness at any duration, everywhere, and needs no opt-in.
#
# ONE LOCK DIR, ONE WINDOW: the value is a property of the lock dir, not of the
# call site. `ait_lock_dir emails` is reached both through registry_lock.sh and
# through a direct call here, and if the two disagreed then whether a wedged
# guard self-heals would depend on which writer arrived first.
# On success returns 0 with the lock held and STALE_LOCK_TOKEN set (pass it to
# stale_lock_release). On exhaustion or publish failure returns 1 with nothing
# held. Errexit-safe: every routine-nonzero internal runs in a condition
# context — both callers are `set -e` scripts.
# shellcheck disable=SC2034  # consumed by sourcing callers, not in this file
STALE_LOCK_TOKEN=""
stale_lock_acquire() {
    local lock_dir="$1" retries="$2" sleep_s="$3" label="$4" gc_window="${5:-}"
    local gc="${lock_dir}.gc" retry=0 reclaimed token ident_pid gc_take_rc gc_mark
    ident_pid="${STALE_LOCK_IDENTITY_PID:-$$}"
    STALE_LOCK_TOKEN=""
    while :; do
        reclaimed=1
        gc_take_rc=0
        _stale_lock_gc_take "$gc" "$gc_window" || gc_take_rc=$?
        if [[ "$gc_take_rc" -eq 2 ]]; then
            # The guard slot changed (a leaked guard was reclaimed). Retry the
            # mkdir at once — same fast-retry shape a lock reclaim gets.
            reclaimed=0
        elif [[ "$gc_take_rc" -eq 0 ]]; then
            gc_mark="$_STALE_LOCK_GC_MARK"
            if mkdir "$lock_dir" 2>/dev/null; then
                # -- publish identity under the guard, verified --
                # The token keeps its own $$ prefix: it is per-process
                # uniqueness, not the holder identity ident_pid records.
                token="$$-${RANDOM}-${RANDOM}-$(date +%s)"
                if printf '%s\n' "$ident_pid" > "$lock_dir/pid" 2>/dev/null &&
                   printf '%s\n' "$token" > "$lock_dir/owner" 2>/dev/null &&
                   [[ "$(cat "$lock_dir/pid" 2>/dev/null)" == "$ident_pid" ]] &&
                   [[ "$(cat "$lock_dir/owner" 2>/dev/null)" == "$token" ]] &&
                   _stale_lock_run_publish_fn "$lock_dir"; then
                    gc_take_rc=0
                    _stale_lock_gc_release "$gc" "$gc_mark" || gc_take_rc=$?
                    if [[ "$gc_take_rc" -eq 0 ]]; then
                        # shellcheck disable=SC2034  # consumed by sourcing callers
                        STALE_LOCK_TOKEN="$token"
                        return 0
                    fi
                    if [[ "$gc_take_rc" -eq 2 ]]; then
                        # Our guard was reclaimed while we published. The lock is
                        # published and carries a LIVE identity, so no reclaimer
                        # may displace it (invariant 3) — and unwinding it here
                        # would mutate the lock dir outside a guard we do not
                        # hold, which invariant 1 forbids. Hand back the lock.
                        # shellcheck disable=SC2034  # consumed by sourcing callers
                        STALE_LOCK_TOKEN="$token"
                        return 0
                    fi
                    # Genuinely retained guard (rmdir failed, so we STILL hold
                    # it): unwind the lock under that held guard — returning
                    # success would hand back a lock whose release needs a guard
                    # nobody can take.
                    _stale_lock_rm_verified "$lock_dir" || warn "stale_lock: lock '$lock_dir' also retained"
                    warn "stale_lock: guard '$gc' retained — acquire failed closed"
                    return 1
                fi
                # Partial publish (I/O failure): unwind, fail closed. Drop the
                # guard only once the partial lock is verified absent — a
                # guardless tokenless dir would be age-reclaimable while the
                # failure is investigated.
                warn "stale_lock: could not publish identity into '$lock_dir'"
                if _stale_lock_rm_verified "$lock_dir"; then
                    _stale_lock_gc_release "$gc" "$gc_mark" || warn "stale_lock: guard '$gc' retained"
                else
                    warn "stale_lock: partial lock retained — keeping guard '$gc' (fail closed)"
                fi
                return 1
            fi
            if _stale_lock_reclaim_under_gc "$lock_dir" "$label"; then reclaimed=0; fi
            _stale_lock_gc_release "$gc" "$gc_mark" || reclaimed=1  # retained/lost: no fast retry
        fi
        # Every failed attempt counts, reclaim included — a stream of stale
        # replacements cannot loop past the budget.
        retry=$((retry + 1))
        if [[ "$retry" -ge "$retries" ]]; then
            return 1
        fi
        if [[ "$reclaimed" -ne 0 ]]; then
            sleep "$sleep_s"
        fi
    done
}

# --- Guarded section (for destructive recovery paths) -----------------------
#
# stale_lock_guarded_section <lock_dir> <fn> [<max_tries>]
#
# Runs `<fn> <lock_dir>` while holding the .gc guard, so a whole
# inspect -> repair -> destroy sequence is serialized against acquire, reclaim
# and release. This upholds invariant 1 for callers that must act on a staleness
# verdict with more than a file operation: without it, a contender can reclaim
# and republish between the verdict and the destruction, and the destruction
# then removes a FRESH, live reservation.
#
# Returns <fn>'s status; 1 if the guard could not be taken, and 1 (with a warn)
# if the guard could not be released afterwards.
#
# SIGNALS. This is the only trap-installing function in this file, and it is a
# shared-library export, so it SAVES and RESTORES the caller's INT/TERM/HUP
# handlers rather than clearing them - `trap -` would silently strip a cleanup
# path the caller installed. On a catchable signal it releases the guard,
# restores the caller's handlers and RE-RAISES: a guarded section must not
# swallow a signal the caller was prepared to handle. Releasing on a signal is
# safe for a destroy-last <fn>, because the lock dir is still present with its
# original holder, so the pre-section state is restored.
#
# A <fn> whose final step destroys the lock dir must wrap that step in
# stale_lock_guard_critical: being interrupted between "lock dir removed" and
# "guard released" is the one ordering that strands a guard over no lock.
#
# An UNCATCHABLE kill still leaks the guard - that is invariant 2, deliberately.
# The published recovery applies unchanged: stale_lock_describe names the guard
# path, and the cure is `rmdir <lock_dir>.gc` (never rm -rf).
_STALE_LOCK_GUARD_ACTIVE=""
_STALE_LOCK_GUARD_MARK=""
_STALE_LOCK_GUARD_SAVED_TRAPS=""

# _stale_lock_restore_traps <saved> — reinstall exactly what the caller had.
# An empty <saved> means the caller had no handler, so ours must simply go.
_stale_lock_restore_traps() {
    trap - INT TERM HUP
    [[ -z "$1" ]] || eval "$1"
}

_stale_lock_guard_on_signal() {
    local sig="$1"
    if [[ -n "$_STALE_LOCK_GUARD_ACTIVE" ]]; then
        _stale_lock_gc_release "$_STALE_LOCK_GUARD_ACTIVE" "$_STALE_LOCK_GUARD_MARK" ||
            warn "stale_lock: guard '$_STALE_LOCK_GUARD_ACTIVE' retained after $sig"
        _STALE_LOCK_GUARD_ACTIVE=""
        _STALE_LOCK_GUARD_MARK=""
    fi
    warn "stale_lock: INTERRUPTED:guard_released ($sig)"
    _stale_lock_restore_traps "$_STALE_LOCK_GUARD_SAVED_TRAPS"
    kill -s "$sig" $$           # re-raise into the caller's own handler
}

# stale_lock_guard_critical <cmd> [args...] — run <cmd> with INT/TERM/HUP
# MASKED, then restore this section's handler. For the few file ops that must
# not be interrupted partway (typically the lock-dir removal itself).
stale_lock_guard_critical() {
    local rc=0
    trap '' INT TERM HUP
    "$@" || rc=$?
    trap '_stale_lock_guard_on_signal INT'  INT
    trap '_stale_lock_guard_on_signal TERM' TERM
    trap '_stale_lock_guard_on_signal HUP'  HUP
    return "$rc"
}

stale_lock_guarded_section() {
    local lock_dir="$1" fn="$2" max_tries="${3:-40}"
    local gc="${lock_dir}.gc" tries=0 rc=0
    _STALE_LOCK_GUARD_SAVED_TRAPS="$(trap -p INT TERM HUP)"
    # Bounded guard wait, same shape as stale_lock_release: an ordinary
    # contender holds the guard for microseconds; only a leaked guard exhausts.
    # No markerless window here (and none in stale_lock_release): those paths
    # get dead-record reclaim only, so force-release stays the human ladder it
    # was designed to be.
    while ! _stale_lock_gc_take "$gc"; do
        tries=$((tries + 1))
        if [[ "$tries" -ge "$max_tries" ]]; then
            warn "stale_lock: guard '$gc' busy — guarded section not entered"
            _stale_lock_restore_traps "$_STALE_LOCK_GUARD_SAVED_TRAPS"
            return 1
        fi
        sleep 0.05
    done
    _STALE_LOCK_GUARD_ACTIVE="$gc"
    _STALE_LOCK_GUARD_MARK="$_STALE_LOCK_GC_MARK"
    trap '_stale_lock_guard_on_signal INT'  INT
    trap '_stale_lock_guard_on_signal TERM' TERM
    trap '_stale_lock_guard_on_signal HUP'  HUP

    "$fn" "$lock_dir" || rc=$?

    if [[ -n "$_STALE_LOCK_GUARD_ACTIVE" ]]; then
        if ! _stale_lock_gc_release "$gc" "$_STALE_LOCK_GUARD_MARK"; then
            warn "stale_lock: guard '$gc' retained"
            rc=1
        fi
        _STALE_LOCK_GUARD_MARK=""
        _STALE_LOCK_GUARD_ACTIVE=""
    fi
    _stale_lock_restore_traps "$_STALE_LOCK_GUARD_SAVED_TRAPS"
    return "$rc"
}

# stale_lock_release <lock_dir> <token>
# Returns 0 when nothing of ours is left behind (removed, already gone, or
# provably not ours); 1 when our lock or the guard is genuinely retained.
stale_lock_release() {
    local lock_dir="$1" token="$2"
    local gc="${lock_dir}.gc" tries=0 rc=0
    [[ -e "$lock_dir" ]] || return 0            # already gone: nothing retained
    # Bounded guard wait: an ordinary contender holds the guard only for
    # microseconds per iteration, so a try-once here would make routine
    # contention abandon our own lock. Only a leaked guard exhausts this.
    local rel_mark
    while ! _stale_lock_gc_take "$gc"; do
        tries=$((tries + 1))
        if [[ "$tries" -ge 40 ]]; then
            warn "stale_lock: guard '$gc' busy — lock '$lock_dir' NOT released"
            return 1
        fi
        sleep 0.05
    done
    rel_mark="$_STALE_LOCK_GC_MARK"
    local on_disk
    on_disk="$(cat "$lock_dir/owner" 2>/dev/null || true)"
    if [[ -n "$token" && "$on_disk" == "$token" ]]; then
        if ! _stale_lock_rm_verified "$lock_dir"; then
            rc=1                                # still-held lock: report, never mask
        fi
    else
        # Our lock was reclaimed and re-published by a new owner (or the token
        # is empty): never delete what is not provably ours. Correct no-op.
        warn "stale_lock: not owner of '$lock_dir' — leaving intact"
    fi
    if ! _stale_lock_gc_release "$gc" "$rel_mark"; then  # retained guard wedges the key
        warn "stale_lock: guard '$gc' retained"
        rc=1
    fi
    return "$rc"
}
