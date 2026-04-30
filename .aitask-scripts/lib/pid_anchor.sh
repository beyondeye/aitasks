#!/usr/bin/env bash
# Single source of truth for PID-anchor helpers used by lock/pick scripts.
# Idempotent: safe to source multiple times.
#
# Sourced by:
#   .aitask-scripts/aitask_lock.sh
#   .aitask-scripts/aitask_pick_own.sh
#   .aitask-scripts/aitask_backfill_pid_anchor.sh

[[ -n "${_AIT_PID_ANCHOR_LOADED:-}" ]] && return 0
_AIT_PID_ANCHOR_LOADED=1

# Linux: read /proc/<pid>/stat field 22 (jiffies since boot — invariant per
# process; survives PID recycling because new processes get fresh starttime).
# macOS: returns "-" — starttime check is skipped on Darwin.
get_pid_starttime() {
    local pid="${1:-}"
    [[ -z "$pid" || "$pid" == "-" ]] && { echo "-"; return; }
    [[ ! -r "/proc/$pid/stat" ]] && { echo "-"; return; }
    local raw
    raw=$(cat "/proc/$pid/stat" 2>/dev/null) || { echo "-"; return; }
    # comm field may contain spaces/parens — split after the LAST ')'
    local after_comm="${raw##*) }"
    local fields
    read -ra fields <<<"$after_comm"
    # Original field 22 is index 19 of the post-comm split:
    # state(1) ppid(2) pgrp(3) session(4) tty(5) tpgid(6) flags(7) minflt(8)
    # cminflt(9) majflt(10) cmajflt(11) utime(12) stime(13) cutime(14)
    # cstime(15) priority(16) nice(17) num_threads(18) itrealvalue(19)
    # starttime(20) -> 0-indexed = 19
    echo "${fields[19]:--}"
}

# Returns 0 if pid is running and (when starttime != "-") starttime matches.
# pid="-" or empty → not alive.
is_lock_holder_alive() {
    local pid="${1:-}" starttime="${2:--}"
    [[ -z "$pid" || "$pid" == "-" || "$pid" == "0" ]] && return 1
    kill -0 "$pid" 2>/dev/null || return 1
    if [[ -n "$starttime" && "$starttime" != "-" ]]; then
        local current
        current=$(get_pid_starttime "$pid")
        [[ "$current" == "$starttime" ]] || return 1
    fi
    return 0
}
