#!/usr/bin/env bash
# registry_lock.sh - the persistent-registry mutex, an ADAPTER over the shared
# stale_lock.sh core (t1507). Source this file from aitask scripts; do not
# execute directly.
#
# The project registry (~/.config/aitasks/projects.yaml) is mutated by a
# whole-file read-modify-write in aitask_projects.sh. Those mutations fire
# concurrently — `ait projects add` runs silently on every tmux session bootstrap
# (lib/tmux_bootstrap.sh), so a restart burst launches many writers at once.
# Without serialization the last writer clobbers the others with its stale
# snapshot, silently dropping project_group / last_opened fields (t1073). The
# same mutex also guards agent marks, shadow rejections, attach/artifact-manifest
# transactions (lib/attachment_lock.sh) and `ait gates sync-registry`.
#
# This file used to carry its OWN mkdir mutex, whose stale reclaim observed the
# holder pid and only THEN `mv`'d whatever was at the path — the observation and
# the destructive act were not serialized, so a contender could displace a
# freshly re-published live lock (two holders in the critical section). That is
# the exact race t1496 fixed for the gate/child locks by building
# lib/stale_lock.sh; t1507 converts this lib onto it, leaving ONE mutex protocol
# in the tree. All the protocol invariants (`.gc`-guarded single-winner reclaim,
# live PIDs never displaced, owner-token release, verified removals) now live
# there and are documented in that file — do not restate or fork them here.
#
# Provides:
#   registry_lock_acquire <lock_dir> [timeout_secs=10] [label]  -> 0 held / 1 busy
#   registry_lock_release <lock_dir>                            -> always 0
#   registry_lock_describe <lock_dir>                           -> recovery hint
#
# Lock paths are CALLER-CHOSEN and stay at fixed shared locations (the per-user
# config dir, the data worktree, /tmp). They are deliberately NOT routed through
# stale_lock's ait_lock_dir per-repo scoping: these ledgers are shared across
# repositories by design. Only the mutex protocol converges.
#
# Requires warn() from terminal_compat.sh — every caller sources it first.
#
# --- Deliberate boundary deltas (the adapter's whole surface) ---------------
#
#   1. TIMEOUT vs RETRY BUDGET. This API budgets SECONDS; stale_lock budgets
#      ATTEMPTS. The deadline loop below converts, re-arming from the REMAINING
#      time on each pass. Note the contract is coarser than it looks and is
#      preserved INCLUDING its coarseness: the deadline is quantized to whole
#      seconds by `date +%s`, so the guarantee is "never reports busy before the
#      integer clock reaches start_second + timeout" — NOT "waits at least
#      timeout seconds of real time". A call entered late in a second can
#      legitimately return almost immediately. Keeping `date +%s` is deliberate:
#      it is the existing behavior and it is portable.
#   2. RELEASE ALWAYS RETURNS 0. stale_lock_release returns 1 on a retained lock
#      or guard, but every caller is `set -euo pipefail` and calls this bare,
#      AFTER the protected mutation has already committed — propagating there
#      would abort the script mid-flow. Retention is surfaced as a warn instead.
#   4. MARKERLESS GUARD RECLAIM is opted in here, and that is a decision about
#      the LOCK DIR, not this adapter: none of this adapter's callers can reach
#      stale_lock_guarded_section, so no shipped version holds one of these
#      guards across an unbounded operation. `ait_lock_dir emails` is reached
#      both through here and through a direct stale_lock_acquire call in
#      aitask_create.sh, and the two MUST pass the same window — otherwise
#      whether a wedged guard self-heals would depend on which writer arrived
#      first. merge_lock.sh deliberately opts out.
#   3. TOKENLESS-AGE RECLAIM is newly reachable (stale_lock's 120s window). This
#      lib's own locks always carry a pid file, and publication happens under the
#      `.gc` guard, so a tokenless dir can only be a legacy/foreign lock — never
#      a holder mid-acquire. Strictly safer than the old code, which read a
#      tokenless dir as live and waited out the whole timeout.
#
# --- Recovery ---------------------------------------------------------------
#
# Since t1598 the `.gc` guard carries a holder record, so a process killed
# inside its few-file-op section leaves a guard naming a dead pid — and the next
# acquire frees it automatically. This adapter also passes a markerless-guard
# window (see delta 4), so a guard left by pre-t1598 code self-heals once it is
# older than that window.
#
# Two cases still need a human, and both are fail-safe rather than fail-open:
# a recycled holder pid reads as alive, and a genuinely hung holder is never
# displaced. For those, registry_lock_describe names the lock, the guard, and
# the holder pid when there is one; a caller whose failure is otherwise silent
# (`ait projects add` runs as `… >/dev/null 2>&1 || true` on every tmux
# bootstrap) should surface it.

[[ -n "${_AIT_REGISTRY_LOCK_LOADED:-}" ]] && return 0
_AIT_REGISTRY_LOCK_LOADED=1

_AIT_REGISTRY_LOCK_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/stale_lock.sh
source "$_AIT_REGISTRY_LOCK_SELF/stale_lock.sh"

# One value pair, defined together because they are one value: the poll interval
# and its reciprocal. They are what converts this API's seconds into the core's
# attempt budget — changing either alone silently rescales every timeout.
_REGISTRY_LOCK_SLEEP=0.05
_REGISTRY_LOCK_ATTEMPTS_PER_SEC=20

# One active lock per process. Set on acquire, cleared on release.
_registry_lock_dir=""
_registry_lock_token=""

# registry_lock_acquire <lock_dir> [timeout_secs] [label]
# Returns 0 with the lock held, or 1 if a live holder kept it past the deadline.
# Emits nothing on the busy path: aitask_shadow_rejected.sh and
# aitask_agent_marks.sh both pin an exact `LOCK_BUSY` on 2>&1-captured output.
registry_lock_acquire() {
    local dir="$1"
    local timeout="${2:-10}"
    local label="${3:-lock $1}"
    local deadline remaining retries
    deadline=$(( $(date +%s) + timeout ))

    while :; do
        remaining=$(( deadline - $(date +%s) ))
        if (( remaining < 0 )); then
            remaining=0
        fi
        retries=$(( remaining * _REGISTRY_LOCK_ATTEMPTS_PER_SEC ))
        # Floor of 3: a reclaim consumes an attempt without acquiring, so a zero
        # or sub-second timeout must still get the follow-up mkdir that the old
        # `continue`-after-steal loop gave it — and since t1598 there can be TWO
        # such reclaims before the acquiring mkdir (the guard, then the lock dir).
        if (( retries < 3 )); then
            retries=3
        fi
        # This adapter MAY opt in to markerless guard reclaim: none of its
        # callers can reach stale_lock_guarded_section, so no shipped version
        # holds one of its guards across an unbounded operation. See delta 4.
        if stale_lock_acquire "$dir" "$retries" "$_REGISTRY_LOCK_SLEEP" "$label" \
                "${_REGISTRY_LOCK_GC_WINDOW:-$_STALE_LOCK_GC_WINDOW_DEFAULT}"; then
            _registry_lock_dir="$dir"
            _registry_lock_token="$STALE_LOCK_TOKEN"
            # shellcheck disable=SC2064  # expand $dir now, on purpose
            trap "registry_lock_release '$dir'" EXIT
            return 0
        fi
        # Re-arm until the deadline actually passes. stale_lock's budget is a
        # retry count and a burst of dead-holder reclaims spends it WITHOUT
        # sleeping, so returning on the first exhaustion would report busy early
        # — the one thing this API's timeout promises not to do.
        if (( $(date +%s) >= deadline )); then
            return 1   # live holder, timed out → FAIL SAFELY (never write unlocked)
        fi
    done
}

# registry_lock_release <lock_dir>
# Removes the lock dir ONLY if this process still owns it (token match).
# Always returns 0 — see delta 2 in the header.
registry_lock_release() {
    local dir="$1"
    [[ -n "$_registry_lock_dir" && "$dir" == "$_registry_lock_dir" ]] || return 0
    stale_lock_release "$dir" "$_registry_lock_token" \
        || warn "registry_lock: '$dir' not fully released"
    _registry_lock_dir=""
    _registry_lock_token=""
    trap - EXIT
    return 0
}

# registry_lock_describe <lock_dir> — human recovery hint for an exhausted
# acquire: the resolved dir, the recorded holder pid, and the `.gc` guard when
# one is present. Callers append it to their own busy message.
registry_lock_describe() {
    stale_lock_describe "$1"
}
