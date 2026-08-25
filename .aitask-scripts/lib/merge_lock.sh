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
#   merge_lock_acquire <task_id> <out_branch> <task_branch> [wait_secs] [label]
#                                                         -> 0 held / 1 busy
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
#   4. SECONDS, NOT ATTEMPTS. Like registry_lock.sh this API budgets SECONDS
#      and converts to the core's attempt budget, with the same quantization
#      caveat. The conversion is COPIED rather than called: registry_lock's
#      acquire carries delta 1's EXIT trap, so it cannot be reused here.
#
#   5. ONE GLOBAL LOCK PER REPO (`ait_lock_dir merge`), not one per branch. Two
#      tasks merging into DIFFERENT output branches still share one HEAD, one
#      index and one working tree, so a per-branch lock would not exclude them.
#
# Requires warn() from terminal_compat.sh - every caller sources it first.

[[ -n "${_AIT_MERGE_LOCK_LOADED:-}" ]] && return 0
_AIT_MERGE_LOCK_LOADED=1

_AIT_MERGE_LOCK_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/stale_lock.sh
source "$_AIT_MERGE_LOCK_SELF/stale_lock.sh"
# shellcheck source=lib/pid_anchor.sh
source "$_AIT_MERGE_LOCK_SELF/pid_anchor.sh"

# One value pair, defined together because they are one value: the poll interval
# and its reciprocal. Changing either alone silently rescales every wait budget.
_MERGE_LOCK_SLEEP=0.05
_MERGE_LOCK_ATTEMPTS_PER_SEC=20

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

# _merge_lock_liveness_seam <lock_dir> — the _STALE_LOCK_LIVENESS_FN seam.
# Exit 0 = do not displace, 1 = reclaim. Only a provably dead anchor is
# reclaimed; `alive` and `unknown` are both "leave it alone" (delta 3).
_merge_lock_liveness_seam() {
    [[ "$(merge_lock_liveness "$1")" == "dead" ]] && return 1
    return 0
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

# merge_lock_acquire <task_id> <output_branch> <task_branch> [wait_secs] [label]
# 0 = held (STALE_LOCK_TOKEN is NOT the release capability across processes —
# see merge_lock_authorize), 1 = a holder kept it past the deadline.
#
# The caller MUST have resolved a session anchor first: a reservation whose
# owner cannot later be proven is exactly the hole force-release exists to
# clean up. Callers refuse with NO_SESSION_ANCHOR before reaching here.
merge_lock_acquire() {
    local task_id="$1" out_branch="$2" task_branch="$3"
    local wait_secs="${4:-0}" label="${5:-merge lock}"
    local dir deadline now remaining retries

    dir="$(merge_lock_dir)" || return 1

    _merge_lock_task_id="$task_id"
    _merge_lock_output_branch="$out_branch"
    _merge_lock_task_branch="$task_branch"
    _merge_lock_anchor_pid="$(get_session_anchor_pid)"
    _merge_lock_anchor_token="$(get_pid_starttime "$_merge_lock_anchor_pid")"
    _merge_lock_anchor_kind="$(get_pid_starttime_kind "$_merge_lock_anchor_pid")"

    # shellcheck disable=SC2034  # all three are read by lib/stale_lock.sh
    STALE_LOCK_IDENTITY_PID="$_merge_lock_anchor_pid"
    # shellcheck disable=SC2034
    _STALE_LOCK_LIVENESS_FN=_merge_lock_liveness_seam
    # shellcheck disable=SC2034
    STALE_LOCK_PUBLISH_FN=_merge_lock_publish

    deadline=$(( $(date +%s) + wait_secs ))
    while :; do
        now=$(date +%s)
        remaining=$(( deadline - now ))
        [[ "$remaining" -lt 0 ]] && remaining=0
        retries=$(( remaining * _MERGE_LOCK_ATTEMPTS_PER_SEC ))
        [[ "$retries" -lt 3 ]] && retries=3      # attempt + up to two reclaims

        # NO markerless-guard window, deliberately (t1598): aitask_merge_task.sh
        # runs `git merge --abort` and `git reset --hard` under this lock's guard
        # via stale_lock_guarded_section, so no age window can dominate a
        # legitimate hold. A merge guard leaked by pre-record code stays a
        # force-release / manual matter. Anyone adding a long guarded section to
        # another lock dir must contradict this comment first.
        if stale_lock_acquire "$dir" "$retries" "$_MERGE_LOCK_SLEEP" "$label"; then
            return 0
        fi
        [[ "$(date +%s)" -ge "$deadline" ]] && return 1
    done
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
