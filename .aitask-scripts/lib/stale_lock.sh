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
#   2. `.gc` is fail-closed and never automatically stolen. A leaked guard
#      (process killed inside its few-file-op section) wedges that one lock
#      until removed by hand; the caller's exhaustion error names it via
#      stale_lock_describe. No age/PID heuristics on the guard.
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
        hint+="; stale-reclaim guard ${lock_dir}.gc present — remove it too if no reclaim is running"
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

# _stale_lock_gc_release <gc_dir> — drop the guard we hold. A bare rmdir whose
# OWN exit status is authoritative: the guard is the one dir another contender
# may legitimately recreate the instant it is free, so "rm then check absence"
# would misread that replacement as our guard being retained (and the acquire
# path would then unwind a perfectly valid lock, mutating it outside any held
# guard). rmdir succeeding means WE removed OUR guard, full stop; guard dirs
# are always empty (nothing ever writes into them), so a failure is a genuine
# retention — and means we STILL hold the guard.
_stale_lock_gc_release() {
    rmdir "$1" 2>/dev/null
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

# stale_lock_acquire <lock_dir> <retries> <sleep_s> <label>
# On success returns 0 with the lock held and STALE_LOCK_TOKEN set (pass it to
# stale_lock_release). On exhaustion or publish failure returns 1 with nothing
# held. Errexit-safe: every routine-nonzero internal runs in a condition
# context — both callers are `set -e` scripts.
# shellcheck disable=SC2034  # consumed by sourcing callers, not in this file
STALE_LOCK_TOKEN=""
stale_lock_acquire() {
    local lock_dir="$1" retries="$2" sleep_s="$3" label="$4"
    local gc="${lock_dir}.gc" retry=0 reclaimed token
    STALE_LOCK_TOKEN=""
    while :; do
        reclaimed=1
        if mkdir "$gc" 2>/dev/null; then
            if mkdir "$lock_dir" 2>/dev/null; then
                # -- publish identity under the guard, verified --
                token="$$-${RANDOM}-${RANDOM}-$(date +%s)"
                if printf '%s\n' "$$" > "$lock_dir/pid" 2>/dev/null &&
                   printf '%s\n' "$token" > "$lock_dir/owner" 2>/dev/null &&
                   [[ "$(cat "$lock_dir/pid" 2>/dev/null)" == "$$" ]] &&
                   [[ "$(cat "$lock_dir/owner" 2>/dev/null)" == "$token" ]]; then
                    if _stale_lock_gc_release "$gc"; then
                        # shellcheck disable=SC2034  # consumed by sourcing callers
                        STALE_LOCK_TOKEN="$token"
                        return 0
                    fi
                    # Genuinely retained guard (rmdir failed, so we STILL hold
                    # it): unwind the lock under that held guard — returning
                    # success would hand back an unreleasable lock (release
                    # needs the guard, and the guard is never auto-broken).
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
                    _stale_lock_gc_release "$gc" || warn "stale_lock: guard '$gc' retained"
                else
                    warn "stale_lock: partial lock retained — keeping guard '$gc' (fail closed)"
                fi
                return 1
            fi
            if _stale_lock_reclaim_under_gc "$lock_dir" "$label"; then reclaimed=0; fi
            _stale_lock_gc_release "$gc" || reclaimed=1    # retained guard: no fast retry
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
    while ! mkdir "$gc" 2>/dev/null; do
        tries=$((tries + 1))
        if [[ "$tries" -ge 40 ]]; then
            warn "stale_lock: guard '$gc' busy — lock '$lock_dir' NOT released"
            return 1
        fi
        sleep 0.05
    done
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
    if ! _stale_lock_gc_release "$gc"; then     # retained guard also wedges the key
        warn "stale_lock: guard '$gc' retained"
        rc=1
    fi
    return "$rc"
}
