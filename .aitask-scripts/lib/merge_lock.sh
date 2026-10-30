#!/usr/bin/env bash
# merge_lock.sh - the Step 9 MERGE mutex, an ADAPTER over the shared
# stale_lock.sh core (t1560_1). Source this file from aitask scripts; do not
# execute directly.
#
# Step 9's end-of-task merge runs in the SHARED repo root, not in the task's
# worktree, so every concurrently-merging task drives one HEAD, one index and
# one working tree. Nothing serialized it: two agents approving "Proceed with
# merge?" at the same time race on .git/index.lock, and a conflict-parked merge
# leaves the shared tree reserved by nobody - the second agent's merge commit
# then absorbs the first's partially-resolved conflict work.
#
# All the protocol invariants (`.gc`-guarded single-winner reclaim, live holders
# never displaced, owner-token release, verified removals) live in
# lib/stale_lock.sh and are documented there - do not restate or fork them here.
#
# Provides:
#   merge_lock_dir                                        -> resolved lock dir
#   merge_lock_acquire <task_id> <out_branch> <task_branch> [label]
#                                                         -> 0 held / 1 busy (ONE attempt)
#   merge_lock_poll_delay_ms <base_ms>                    -> sets _MERGE_LOCK_POLL_DELAY_MS
#   merge_lock_release <lock_dir>                         -> 0 released / 1 kept
#   merge_lock_read <lock_dir> <field>                    -> recorded value
#   merge_lock_authorize <lock_dir> <task_id>             -> 0 / prints reason
#   merge_lock_liveness <lock_dir>                        -> alive|dead|unknown
#
# --- Deliberate boundary deltas (the adapter's whole surface) ---------------
#
#   1. NO AUTO-RELEASE EXIT TRAP. registry_lock.sh installs
#      `trap "registry_lock_release '$dir'" EXIT` inside its acquire. This
#      adapter must NOT, and the difference is the whole feature: `begin`,
#      `finish` and `abort` are three SEPARATE short-lived processes, and the
#      reservation has to survive between them - across a human resolving a
#      conflict, across a multi-minute verification run. An inherited EXIT trap
#      would release the lock the instant `begin` returns, silently reducing
#      the mutex to a no-op that still passes every single-process test.
#      (Consequence: nothing auto-releases this lock. Every path that acquires
#      it must reach exactly one release, and the recovery ladder for a leaked
#      one is `aitask_merge_task.sh force-release`.)
#
#   2. HOLDER IDENTITY IS A SESSION ANCHOR, NOT $$. Because of delta 1, $$ is
#      dead the moment `begin` returns, and stale_lock's kill -0 reclaim would
#      hand the tree to the next contender while the first agent is still
#      resolving a conflict. STALE_LOCK_IDENTITY_PID is therefore set from
#      lib/pid_anchor.sh::get_session_anchor_pid - the same session identity
#      aitask_lock.sh anchors task locks to - and the _STALE_LOCK_LIVENESS_FN
#      seam replaces the core's pid probe with lock_holder_liveness over the
#      recorded triple.
#
#   3. "UNKNOWN" IS NEVER RECLAIMED. The core reclaims a tokenless lock on age
#      (_STALE_LOCK_WINDOW). Here, only a provably `dead` anchor is displaced:
#      `alive` AND `unknown` both mean "leave it alone". A merge reservation
#      whose owner cannot be proven dead is escalated to a human via
#      force-release, never auto-stolen - the same rule locks.md already
#      publishes for task locks.
#
#   4. A SECONDS BUDGET POLLED ON A LONG, JITTERED INTERVAL (t2167). The
#      reservation is held for MINUTES (merge, verification, sometimes a human
#      resolving a conflict), so registry_lock.sh's 50 ms cadence - right for
#      its millisecond critical sections - does not carry over: it made every
#      waiter take the .gc guard ~20 times a second for nothing. Here
#      merge_lock_acquire is ONE attempt (a short burst through the core: the
#      attempt plus up to two fast reclaim retries), and the waiting loop lives
#      in the caller (aitask_merge_task.sh begin), which polls every
#      _MERGE_LOCK_POLL_SECS +/-25% so concurrent waiters do not retry in
#      lockstep. The first attempt is immediate; each sleep is clamped to the
#      remaining budget, so the last attempt lands at the deadline and a wait
#      never overruns it by a whole interval. Scoped to this lock only: the
#      core and its other callers keep their short polls.
#
#   5. ONE GLOBAL LOCK PER REPO (`ait_lock_dir merge`), not one per branch. Two
#      tasks merging into DIFFERENT output branches still share one HEAD, one
#      index and one working tree, so a per-branch lock would not exclude them.
#
#   6. NO EXPENSIVE PROBE UNDER THE GUARD FOR A HOLDER NOT ALREADY JUDGED DEAD
#      (t2167, merged t2156). The core runs the liveness seam under the .gc
#      guard on every failed mkdir, and the holder probe (ps / the bsdinfo
#      probe) is slow. With N waiters doing that, the guard was almost never
#      free, and the HOLDER's own release - which needs the same guard, with a
#      bounded ~2 s wait - gave up and leaked a live reservation. Two layers:
#        a. Each attempt first probes the holder WITHOUT the guard. alive or
#           unknown -> busy, guard untouched. That verdict can only ever lead
#           to doing nothing, so forming it unguarded does not weaken
#           stale_lock.sh invariant 1.
#        b. The guarded seam re-probes only the holder INSTANCE (pid|owner)
#           that layer (a) judged dead in this same attempt; any other holder
#           - one published after the unguarded probe, or met on an internal
#           retry - is "leave it alone" for the price of two builtin reads.
#           Layer (a) alone is not enough: a waiter that saw the lock ABSENT
#           would otherwise probe a just-published live holder under the guard.
#      The destructive verdict is still formed and acted on in one guarded
#      section: a dead pre-verdict only PERMITS the guarded re-probe, it never
#      replaces it. A key collision costs one guarded probe, never a wrong
#      reclaim; a newly published holder that is in fact dead waits for the
#      next poll.
#
# Requires warn() from terminal_compat.sh - every caller sources it first.

[[ -n "${_AIT_MERGE_LOCK_LOADED:-}" ]] && return 0
_AIT_MERGE_LOCK_LOADED=1

_AIT_MERGE_LOCK_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/stale_lock.sh
source "$_AIT_MERGE_LOCK_SELF/stale_lock.sh"
# shellcheck source=lib/pid_anchor.sh
source "$_AIT_MERGE_LOCK_SELF/pid_anchor.sh"

# Waiter cadence (delta 4): base seconds between attempts, jittered +/-25%.
_MERGE_LOCK_POLL_SECS=30
# One attempt = this many core iterations, _MERGE_LOCK_ATTEMPT_SLEEP apart when
# the guard is busy (a reclaim retries at once): the attempt + up to 2 reclaims.
_MERGE_LOCK_ATTEMPT_RETRIES=3
_MERGE_LOCK_ATTEMPT_SLEEP=0.05

# Fields the publish fn records, in one place so the writer and every reader
# agree. `state` is deliberately NOT here: it is written after acquire and is
# purely advisory - no decision reads it.
_MERGE_LOCK_FIELDS="anchor_token anchor_kind task_id output_branch task_branch acquired_at"

# Set by merge_lock_acquire, consumed by the publish fn (which stale_lock calls
# with only <lock_dir>, under the guard).
_merge_lock_task_id=""
_merge_lock_output_branch=""
_merge_lock_task_branch=""
_merge_lock_anchor_pid=""
_merge_lock_anchor_token=""
_merge_lock_anchor_kind=""
# The holder instance this attempt's UNGUARDED probe judged dead (delta 6b);
# empty = none, so the guarded seam probes nothing.
_merge_lock_dead_key=""

# merge_lock_dir — the one global merge lock for this repo (delta 5).
merge_lock_dir() {
    ait_lock_dir merge
}

# merge_lock_read <lock_dir> <field> — echo a recorded field, empty if absent.
merge_lock_read() {
    local v
    v="$(cat "$1/$2" 2>/dev/null || true)"
    printf '%s' "$v"
}

# merge_lock_liveness <lock_dir> — the holder verdict over the RECORDED triple.
# Echoes alive|dead|unknown. A lock with no recorded anchor is `unknown`, never
# `dead`: an incomplete acquisition must not look reclaimable (delta 3).
merge_lock_liveness() {
    local d="$1" pid token kind
    pid="$(merge_lock_read "$d" pid)"
    token="$(merge_lock_read "$d" anchor_token)"
    kind="$(merge_lock_read "$d" anchor_kind)"
    [[ -n "$pid" ]]   || { printf 'unknown'; return 0; }
    [[ -n "$token" ]] || token="-"
    [[ -n "$kind" ]]  || kind="proc"
    lock_holder_liveness "$pid" "$token" "$kind"
}

# _merge_lock_instance_key <lock_dir> — set _MERGE_LOCK_KEY to "<pid>|<owner>",
# the identity of one holder INSTANCE (the owner token is never reused). Builtin
# reads only, no fork: this also runs under the guard (delta 6b). A missing
# file reads as empty.
_MERGE_LOCK_KEY=""
_merge_lock_instance_key() {
    local p="" o=""
    { IFS= read -r p < "$1/pid"; } 2>/dev/null || true
    { IFS= read -r o < "$1/owner"; } 2>/dev/null || true
    _MERGE_LOCK_KEY="$p|$o"
}

# _merge_lock_liveness_seam <lock_dir> — the _STALE_LOCK_LIVENESS_FN seam, run
# UNDER the guard. Exit 0 = do not displace, 1 = reclaim. Only a provably dead
# anchor is reclaimed; `alive` and `unknown` are both "leave it alone" (delta 3).
# Only the instance this attempt's unguarded probe already judged dead is
# probed again here; every other holder is left alone unprobed (delta 6b).
_merge_lock_liveness_seam() {
    _merge_lock_instance_key "$1"
    [[ -n "$_merge_lock_dead_key" && "$_MERGE_LOCK_KEY" == "$_merge_lock_dead_key" ]] || return 0
    [[ "$(merge_lock_liveness "$1")" == "dead" ]] && return 1
    return 0
}

# merge_lock_poll_delay_ms <base_ms> — set _MERGE_LOCK_POLL_DELAY_MS to a delay
# drawn uniformly from [0.75*base, 1.25*base] (delta 4). A global rather than an
# echo, so the caller needs no `$(...)` subshell to read it.
_MERGE_LOCK_POLL_DELAY_MS=0
merge_lock_poll_delay_ms() {
    local base="$1"
    _MERGE_LOCK_POLL_DELAY_MS=$(( base - base / 4 + ( (RANDOM << 15 | RANDOM) % (base / 2 + 1) ) ))
}

# _merge_lock_publish <lock_dir> — the STALE_LOCK_PUBLISH_FN seam. Runs INSIDE
# the .gc guard, so everything a later process needs to reason about this holder
# lands atomically with the acquisition. Every field is verified on read-back;
# a partial write is a publish failure and the core unwinds it, fail closed.
_merge_lock_publish() {
    local d="$1" f v
    for f in $_MERGE_LOCK_FIELDS; do
        case "$f" in
            anchor_token)   v="$_merge_lock_anchor_token" ;;
            anchor_kind)    v="$_merge_lock_anchor_kind" ;;
            task_id)        v="$_merge_lock_task_id" ;;
            output_branch)  v="$_merge_lock_output_branch" ;;
            task_branch)    v="$_merge_lock_task_branch" ;;
            acquired_at)    v="$(date -u +%Y-%m-%dT%H:%M:%SZ)" ;;
            *)              v="" ;;
        esac
        printf '%s\n' "$v" > "$d/$f" 2>/dev/null || return 1
        [[ "$(cat "$d/$f" 2>/dev/null)" == "$v" ]] || return 1
    done
    return 0
}

# merge_lock_acquire <task_id> <output_branch> <task_branch> [label]
# ONE attempt (delta 4): 0 = held (STALE_LOCK_TOKEN is NOT the release
# capability across processes — see merge_lock_authorize), 1 = busy. Waiting
# and polling are the caller's job.
#
# The caller MUST have resolved a session anchor first: a reservation whose
# owner cannot later be proven is exactly the hole force-release exists to
# clean up. Callers refuse with NO_SESSION_ANCHOR before reaching here.
merge_lock_acquire() {
    local task_id="$1" out_branch="$2" task_branch="$3" label="${4:-merge lock}"
    local dir before live

    dir="$(merge_lock_dir)" || return 1

    _merge_lock_task_id="$task_id"
    _merge_lock_output_branch="$out_branch"
    _merge_lock_task_branch="$task_branch"
    _merge_lock_anchor_pid="$(get_session_anchor_pid)"
    read -r _merge_lock_anchor_kind _merge_lock_anchor_token \
        <<<"$(get_pid_identity "$_merge_lock_anchor_pid")"

    # shellcheck disable=SC2034  # all three are read by lib/stale_lock.sh
    STALE_LOCK_IDENTITY_PID="$_merge_lock_anchor_pid"
    # shellcheck disable=SC2034
    _STALE_LOCK_LIVENESS_FN=_merge_lock_liveness_seam
    # shellcheck disable=SC2034
    STALE_LOCK_PUBLISH_FN=_merge_lock_publish

    # Delta 6a: judge the holder WITHOUT the guard. Only an absent lock, or a
    # holder instance that stayed the same across a `dead` probe, goes on to
    # the guarded core - and only that instance may be re-probed there (6b).
    _merge_lock_dead_key=""
    if [[ -d "$dir" ]]; then
        _merge_lock_instance_key "$dir"; before="$_MERGE_LOCK_KEY"
        live="$(merge_lock_liveness "$dir")"
        _merge_lock_instance_key "$dir"
        if [[ -d "$dir" ]]; then
            # Replaced mid-probe: the verdict describes nobody. Busy until the
            # next poll rather than spend the guard on it.
            [[ "$_MERGE_LOCK_KEY" == "$before" ]] || return 1
            [[ "$live" == "dead" ]] || return 1
            _merge_lock_dead_key="$before"
        fi
        # Vanished during the probe: free now, attempt with no dead key.
    fi

    # NO markerless-guard window, deliberately (t1598): aitask_merge_task.sh
    # runs `git merge --abort` and `git reset --hard` under this lock's guard
    # via stale_lock_guarded_section, so no age window can dominate a
    # legitimate hold. A merge guard leaked by pre-record code stays a
    # force-release / manual matter. Anyone adding a long guarded section to
    # another lock dir must contradict this comment first.
    stale_lock_acquire "$dir" "$_MERGE_LOCK_ATTEMPT_RETRIES" "$_MERGE_LOCK_ATTEMPT_SLEEP" "$label"
}

# merge_lock_authorize <lock_dir> <task_id> — the cross-process release
# capability. STALE_LOCK_TOKEN is an in-process value and `begin`/`finish`/
# `abort` are separate processes, so the durable capability is the identity
# triple the publish fn wrote under the guard.
#
# Echoes a verdict and returns non-zero when refused:
#   NOT_HOLDER:<holder_task>              task ids differ
#   NOT_OWNER_SESSION:<holder_task>:<pid> this session cannot prove it is the holder
#   HOLDER_INCOMPLETE                     no task_id recorded (never matchable)
#
# A task-id match is NEVER sufficient alone: two unidentifiable sessions on one
# task id would both pass, and the second would free the first's live
# reservation. lock_anchor_is_self is a literal pid+token+kind comparison, not a
# liveness verdict, so a genuine holder proves identity even where liveness can
# only ever say `unknown`.
merge_lock_authorize() {
    local d="$1" want="$2" holder pid token kind
    holder="$(merge_lock_read "$d" task_id)"
    if [[ -z "$holder" ]]; then
        printf 'HOLDER_INCOMPLETE'
        return 1
    fi
    if [[ "$holder" != "$want" ]]; then
        printf 'NOT_HOLDER:%s' "$holder"
        return 1
    fi
    pid="$(merge_lock_read "$d" pid)"
    token="$(merge_lock_read "$d" anchor_token)"
    kind="$(merge_lock_read "$d" anchor_kind)"
    [[ -n "$token" ]] || token="-"
    [[ -n "$kind" ]]  || kind="proc"
    if ! lock_anchor_is_self "$pid" "$token" "$kind"; then
        printf 'NOT_OWNER_SESSION:%s:%s' "$holder" "${pid:--}"
        return 1
    fi
    return 0
}

# merge_lock_release <lock_dir> — release using the owner token READ FROM DISK
# (not remembered): stale_lock_release re-reads and re-compares it under the
# .gc guard, so a lock reclaimed between our read and the release is a safe
# no-op rather than us deleting a new owner's lock.
# 0 = nothing of ours left behind, 1 = genuinely retained.
merge_lock_release() {
    local d="$1" token
    [[ -e "$d" ]] || return 0
    token="$(merge_lock_read "$d" owner)"
    stale_lock_release "$d" "$token"
}
