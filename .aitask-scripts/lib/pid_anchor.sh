#!/usr/bin/env bash
# Single source of truth for PID-anchor helpers used by lock/pick scripts.
# Idempotent: safe to source multiple times.
#
# A task lock records a PID so a later re-pick can tell "the previous agent
# crashed" from "the previous agent is still working". Two things make that
# work, and both live here:
#
#   * the WRITER side (get_session_anchor_pid) must name a process whose
#     lifetime tracks the AGENT SESSION;
#   * the READER side (lock_holder_liveness) must distinguish three states —
#     alive, dead, and "cannot tell" — never collapsing the third into either
#     of the first two.
#
# Sourced by:
#   .aitask-scripts/aitask_lock.sh
#   .aitask-scripts/aitask_pick_own.sh
#   .aitask-scripts/aitask_backfill_pid_anchor.sh

[[ -n "${_AIT_PID_ANCHOR_LOADED:-}" ]] && return 0
_AIT_PID_ANCHOR_LOADED=1

_PID_ANCHOR_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Sentinel written into a lock's `pid:` when no session-tracking process can be
# named. It is deliberately NOT a PID: "unknown" is its own state, distinct
# from a dead PID, and lock_holder_liveness reports it as such. (`0` — written
# by aitask_backfill_pid_anchor.sh into pre-anchor locks — means the same
# thing and is accepted as an equivalent unknown marker.)
AIT_PID_ANCHOR_UNKNOWN="-"

# --- Identity token ("starttime") -------------------------------------------
#
# A bare PID is not an identity: PIDs are recycled. The token pins WHICH
# process a PID referred to when the lock was written. Two sources, in
# decreasing strength — see get_pid_starttime_kind() for why the strength is
# recorded alongside the value rather than assumed by the reader.

# Linux: /proc/<pid>/stat field 22 (jiffies since boot — invariant per process).
# Resolution is ~10 ms, so it excludes PID recycling for practical purposes.
_pid_starttime_proc() {
    local pid="$1" raw after_comm
    [[ -r "/proc/$pid/stat" ]] || return 1
    raw=$(cat "/proc/$pid/stat" 2>/dev/null) || return 1
    # comm field may contain spaces/parens — split after the LAST ')'
    after_comm="${raw##*) }"
    local fields
    read -ra fields <<<"$after_comm"
    # Original field 22 is index 19 of the post-comm split:
    # state(1) ppid(2) pgrp(3) session(4) tty(5) tpgid(6) flags(7) minflt(8)
    # cminflt(9) majflt(10) cmajflt(11) utime(12) stime(13) cutime(14)
    # cstime(15) priority(16) nice(17) num_threads(18) itrealvalue(19)
    # starttime(20) -> 0-indexed = 19
    [[ -n "${fields[19]:-}" ]] || return 1
    printf '%s\n' "${fields[19]}"
}

# BSD / macOS (anywhere without /proc): the process start time from `ps`,
# whitespace-collapsed into one opaque word (e.g. Mon_Aug_10_09:19:16_2026).
# LC_ALL=C pins the month names so the token is comparable across reads.
#
# WEAK BY CONSTRUCTION: `lstart` has one-SECOND resolution, so a PID recycled
# within the same second can carry an equal token. That is why a match on this
# token can never license an `alive` verdict (see lock_holder_liveness).
_pid_starttime_ps() {
    local pid="$1" raw
    raw=$(LC_ALL=C ps -p "$pid" -o lstart= 2>/dev/null) || return 1
    raw="$(printf '%s' "$raw" | tr -s '[:space:]' '_')"
    raw="${raw#_}"; raw="${raw%_}"
    [[ -n "$raw" ]] || return 1
    printf '%s\n' "$raw"
}

# Echo the identity token for <pid>, or "-" when none can be obtained.
get_pid_starttime() {
    local pid="${1:-}"
    [[ -z "$pid" || "$pid" == "-" ]] && { echo "-"; return; }
    _pid_starttime_proc "$pid" && return 0
    _pid_starttime_ps "$pid" && return 0
    echo "-"
}

# Echo which source produced (or would produce) the token: proc | ps | none.
#
# The writer stores this in the lock beside the token, and the reader trusts
# the stored value rather than re-deriving it from its own platform. Two
# reasons: it is provenance for the value stored next to it, and it makes the
# weak-token branch plantable — hence testable on Linux — instead of only
# reachable on a platform this project cannot run its test suite on.
get_pid_starttime_kind() {
    local pid="${1:-}"
    [[ -z "$pid" || "$pid" == "-" ]] && { echo "none"; return; }
    _pid_starttime_proc "$pid" >/dev/null 2>&1 && { echo "proc"; return; }
    _pid_starttime_ps "$pid" >/dev/null 2>&1 && { echo "ps"; return; }
    echo "none"
}

# --- Existence -------------------------------------------------------------

# Does <pid> exist?  0 = exists, 1 = CONFIRMED absent, 2 = cannot inspect.
#
# No single probe is authoritative:
#   * /proc and ps answer without needing signal permission, but both go blind
#     under a hidepid=2 / hidepid=invisible procfs mount, where another user's
#     LIVE process is simply not listed;
#   * `kill -0`'s exit status collapses EPERM into ESRCH — `kill -0 1` and
#     `kill -0 4000000` both return 1 — but its errno MESSAGE separates them,
#     and EPERM ("Operation not permitted") is itself positive proof that the
#     process exists.
#
# So a negative from /proc/ps is never believed on its own. Absence is
# reported only on an explicit "No such process"; anything unrecognised is
# "cannot inspect", never "absent". Getting this wrong in the other direction
# is what makes a live holder look crashed (t1465).
_pid_exists() {
    local pid="${1:-}" err
    [[ "$pid" =~ ^[0-9]+$ ]] || return 2
    [[ -e "/proc/$pid" ]] && return 0
    ps -p "$pid" -o pid= >/dev/null 2>&1 && return 0
    err="$(LC_ALL=C kill -0 "$pid" 2>&1)" && return 0   # signalable => exists
    case "$err" in
        *"No such process"*) return 1 ;;                # ESRCH => absent
        *"not permitted"*)   return 0 ;;                # EPERM => exists
    esac
    return 2                                            # undecidable
}

# --- Liveness verdict ------------------------------------------------------

# Echo exactly one of: alive | dead | unknown.
#   $1 = recorded pid, $2 = recorded identity token, $3 = token kind (proc|ps)
#
# `alive` means "this PID is PROVABLY the process the lock recorded" — it
# requires existence AND a matching STRONG token. `dead` requires positive
# evidence: a confirmed-absent PID, or a token that proves a different process
# now holds the number. Everything else is `unknown`: no usable anchor
# ("-", "0", non-numeric); a process we cannot inspect; a process with no
# recorded token (a bare PID cannot be told apart from a recycled one); and a
# process whose token matches but was only second-granular (kind `ps`), which
# cannot exclude same-second recycling.
#
# Reporting any `unknown` as a crash is what made RECLAIM_CRASH meaningless
# (t1465). Reporting one as alive would mislead the acquire-path liveness gate
# that consumes this verdict (t1466).
#
# $3 defaults to `proc` for backward compatibility: every anchored lock written
# before the kind field existed came from the /proc path.
lock_holder_liveness() {
    local pid="${1:-}" starttime="${2:--}" kind="${3:-proc}" current rc=0
    if ! [[ "$pid" =~ ^[0-9]+$ ]] || (( pid <= 0 )); then
        echo unknown; return 0            # "-", "0", empty, non-numeric
    fi
    _pid_exists "$pid" || rc=$?
    case $rc in
        1) echo dead;    return 0 ;;   # confirmed absent
        2) echo unknown; return 0 ;;   # cannot inspect
    esac
    # Exists. Identity is required before calling it the same process.
    [[ -n "$starttime" && "$starttime" != "-" ]] || { echo unknown; return 0; }
    # Re-derive the token from the SAME source the lock recorded. Using the
    # generic get_pid_starttime here would compare a /proc token against a
    # recorded `ps` one on any host that has both, and every weak-token lock
    # would read as `dead` — a false crash, the exact defect being fixed.
    case "$kind" in
        proc) current=$(_pid_starttime_proc "$pid" 2>/dev/null) || current="-" ;;
        ps)   current=$(_pid_starttime_ps "$pid" 2>/dev/null)   || current="-" ;;
        *)    current="-" ;;   # unrecognised kind => cannot compare
    esac
    [[ "$current" == "-" || -z "$current" ]] && { echo unknown; return 0; }
    [[ "$current" == "$starttime" ]] || { echo dead; return 0; }
    [[ "$kind" == "proc" ]] || { echo unknown; return 0; }   # weak token
    echo alive
}

# Boolean convenience wrapper over lock_holder_liveness: true only for a
# provable `alive`. Both `dead` and `unknown` are false here, so callers that
# need to tell those apart must use lock_holder_liveness directly.
is_lock_holder_alive() {
    [[ "$(lock_holder_liveness "${1:-}" "${2:--}" "${3:-proc}")" == "alive" ]]
}

# --- Self-identity (is that anchor MY session?) -----------------------------

# Internal: this session's own anchor triple, resolved once and cached.
#
# Memoized because the default rung shells out to tmux, and the value is
# invariant for the life of a (short-lived) claim script. Cached even when the
# anchor is UNKNOWN — "no session process could be named" is just as stable an
# answer as a PID, and re-asking a wedged tmux server on every call is exactly
# the cost this cache exists to avoid.
_AIT_SELF_ANCHOR_CACHED=""
_AIT_SELF_ANCHOR_PID=""
_AIT_SELF_ANCHOR_TOKEN=""
_AIT_SELF_ANCHOR_KIND=""
_ait_current_anchor() {
    if [[ -z "$_AIT_SELF_ANCHOR_CACHED" ]]; then
        _AIT_SELF_ANCHOR_PID="$(get_session_anchor_pid)"
        _AIT_SELF_ANCHOR_TOKEN="$(get_pid_starttime "$_AIT_SELF_ANCHOR_PID")"
        _AIT_SELF_ANCHOR_KIND="$(get_pid_starttime_kind "$_AIT_SELF_ANCHOR_PID")"
        _AIT_SELF_ANCHOR_CACHED=1
    fi
}

# Is the recorded anchor <pid> <token> <kind> THIS session's own anchor?
#   0 = provably this session, 1 = anything else (different session, or
#   not provable).
#
# All three fields must match. The PID alone is not enough — a recycled PID
# carries the same number with a different token, and calling that "self" would
# hand the lock straight back to the caller it is meant to exclude. The kind
# must match too: comparing a `ps` token against a `proc` one is comparing two
# incomparable encodings of the same instant, and a false "self" here disables
# the acquire gate entirely.
#
# An unresolvable own anchor ("-", "none") can never claim identity: a session
# that cannot name its own process has no basis to assert that someone else's
# recorded process is it. That asymmetry is deliberate — it fails toward the
# gate, not around it.
#
# Consumed by aitask_lock.sh's acquire gate (a same-email refresh by the SAME
# session must stay silent — Step 7's ownership guard, an in-pane re-pick and
# an in-flight resume all take that path) and by aitask_pick_own.sh's
# post-claim reclaim-signal choice.
lock_anchor_is_self() {
    local pid="${1:-}" token="${2:--}" kind="${3:-proc}"
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    _ait_current_anchor
    [[ "$_AIT_SELF_ANCHOR_PID" =~ ^[0-9]+$ ]] || return 1
    [[ "$pid"   == "$_AIT_SELF_ANCHOR_PID"   ]] || return 1
    [[ "$token" == "$_AIT_SELF_ANCHOR_TOKEN" ]] || return 1
    [[ "$kind"  == "$_AIT_SELF_ANCHOR_KIND"  ]] || return 1
    return 0
}

# --- Anchor resolution (writer side) ---------------------------------------

# Internal: the tmux pane process this claim is running under, via the gateway.
# tmux_exec.sh is sourced LAZILY and only if present, mirroring the pattern
# terminal_compat.sh uses for ait_tmux_new_session_persistent — this file is
# copied standalone into test fixtures, and a missing gateway must degrade to
# "unknown" rather than break sourcing.
_anchor_tmux_pane_pid() {
    if ! declare -F ait_tmux_self_pane_pid >/dev/null 2>&1; then
        [[ -r "$_PID_ANCHOR_LIB_DIR/tmux_exec.sh" ]] || return 1
        # shellcheck source=tmux_exec.sh disable=SC1091
        source "$_PID_ANCHOR_LIB_DIR/tmux_exec.sh" || return 1
        declare -F ait_tmux_self_pane_pid >/dev/null 2>&1 || return 1
    fi
    ait_tmux_self_pane_pid
}

# Echo the PID a task lock should anchor to — a process whose lifetime tracks
# the agent session — or AIT_PID_ANCHOR_UNKNOWN when none can be named.
#
# Resolution ladder, first hit wins:
#
#   1. $AIT_AGENT_PID — explicit override for launchers that start an agent
#      outside tmux, and for tests. It must be a positive integer naming a
#      process that exists right now; anything else is ignored with a warning
#      rather than trusted, because at claim time the agent is by definition
#      alive and a stale value would re-create the very defect below.
#   2. The tmux PANE process (lib/tmux_exec.sh::ait_tmux_self_pane_pid). The
#      framework launches every agent as its pane's own process, so this is the
#      agent CLI itself and it dies exactly when the agent/pane dies.
#   3. UNKNOWN. There is deliberately NO further fallback: writing some other,
#      short-lived PID is what this function exists to stop.
#
# History: this used to be `echo "$PPID"`, described as "the agent's
# bash/claude process". On the path that matters — aitask_pick_own.sh invokes
# aitask_lock.sh inside a command substitution — $PPID was the claim script
# itself, which exits seconds later. Every same-host re-pick therefore reported
# a crash, and a genuine crash became indistinguishable from normal operation
# (t1465).
get_session_anchor_pid() {
    local pid
    if [[ -n "${AIT_AGENT_PID:-}" ]]; then
        if [[ "$AIT_AGENT_PID" =~ ^[0-9]+$ ]] && (( AIT_AGENT_PID > 1 )) \
           && _pid_exists "$AIT_AGENT_PID"; then
            printf '%s\n' "$AIT_AGENT_PID"
            return 0
        fi
        printf 'warning: AIT_AGENT_PID=%s does not name a live process — ignoring it as the lock anchor\n' \
            "$AIT_AGENT_PID" >&2
    fi
    if pid=$(_anchor_tmux_pane_pid); then
        printf '%s\n' "$pid"
        return 0
    fi
    printf '%s\n' "$AIT_PID_ANCHOR_UNKNOWN"
}
