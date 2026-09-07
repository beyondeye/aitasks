#!/usr/bin/env bash
# agent_sessions.sh - Shell-side constants and helpers for the framework
# session store (t1705_2).
#
# The store itself lives in `lib/agent_sessions.py`, written only through
# `aitask_agent_sessions.sh`. This file carries what SHELL callers need: the
# pane-option spellings, the capture-directory resolver, and the one sanctioned
# way to stamp the pane->record join.
#
# The Python spellings of these option names live in
# `monitor/monitor_core.py` beside SHADOW_TARGET_OPTION (added by t1705_4).
# `tests/test_agent_sessions_stamp.sh` pins the two copies together — when
# t1705_4 lands, re-point that parity check at monitor_core.
#
# Source it:
#     source "$SCRIPT_DIR/lib/agent_sessions.sh"

# Guard against double-sourcing.
if [[ -n "${_AIT_AGENT_SESSIONS_LOADED:-}" ]]; then
    # shellcheck disable=SC2317  # `return` is reachable when sourced.
    return 0 2>/dev/null || true
fi
_AIT_AGENT_SESSIONS_LOADED=1

_AGENT_SESSIONS_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tmux_exec.sh disable=SC1091
source "$_AGENT_SESSIONS_LIB_DIR/tmux_exec.sh"

# --- pane options (tmux user options, pane-scoped) --------------------------
#
# Pane user options SURVIVE `respawn-pane` — they are pane-scoped, not
# process-scoped. That is why @aitask_record stays valid across a freeze/restore
# on the same pane, and why @aitask_standin_ready must be explicitly unset
# before every respawn rather than assumed cleared.

# The pane-visible join to a store record. Set by the CALLER after a successful
# `upsert` (see ait_stamp_record); cleared implicitly by pane death, and by
# `drop`.
AIT_RECORD_OPTION="@aitask_record"

# Marks a pane as a frozen stand-in. THE authoritative classifier for the
# monitors — set by the freeze engine immediately before `respawn-pane`.
# shellcheck disable=SC2034  # Read by callers after sourcing this lib.
AIT_FROZEN_OPTION="@aitask_frozen"

# Positive proof the stand-in viewer is actually up. Stamped by the viewer
# itself after mount (only an app stamps its own pane — the mark_monitor_pane
# rule); cleared by the freeze engine and restore coordinator before every
# respawn. It is the only signal that separates "stamped, viewer running" from
# "stamped, agent still running".
# shellcheck disable=SC2034  # Read by callers after sourcing this lib.
AIT_STANDIN_READY_OPTION="@aitask_standin_ready"

# The codeagent session id, recorded by the SessionStart hook on $TMUX_PANE.
# shellcheck disable=SC2034  # Read by callers after sourcing this lib.
AIT_AGENT_SESSION_OPTION="@aitask_agent_session"

# --- capture directory ------------------------------------------------------

# ait_frozen_dir [record_id]
# Echo the frozen-capture root, or one record's directory beneath it. Mirrors
# `agent_sessions.frozen_root()` / `capture_dir()`.
ait_frozen_dir() {
    local root="${AITASKS_FROZEN_DIR:-$HOME/.config/aitasks/frozen}"
    local record_id="${1:-}"
    if [[ -n "$record_id" ]]; then
        printf '%s/%s' "$root" "$record_id"
    else
        printf '%s' "$root"
    fi
}

# --- the pane -> record join ------------------------------------------------

# ait_stamp_record <pane> <record_id>
#
# Stamp the pane->record join. THE store never touches tmux (t1705_2 A8):
# `lib/agent_sessions.py` imports no tmux, and `tests/test_no_raw_tmux.sh`
# permits raw `tmux` only from the two gateways. So establishing the join is
# the CALLER's obligation, and this is the one sanctioned way to discharge it:
#
#   * the SessionStart hook (t1705_3) stamps on the normal path;
#   * the freeze engine (t1705_4) stamps on its fallback path.
#
# CALL IT ONLY AFTER `aitask_agent_sessions.sh` PRINTED `UPSERTED:<id>|…`.
# A stamp without a stored record is a dangling join; a stored record without a
# stamp breaks the identity handoff every later restart/restore path depends on
# — the next upsert from that pane arrives with no `--id`, and after a tmux
# restart (fresh pane ids) there is nothing left to match on, so the freeze
# engine's fallback creates a SECOND record for an agent already recorded.
#
# Returns 2 on a non-canonical id without emitting any tmux call: the id reaches
# a pane option that later feeds `capture_dir()` and the stand-in command
# string, so it is validated here too (t1705_2 A9).
ait_stamp_record() {
    local pane="${1:-}" record_id="${2:-}"
    if [[ -z "$pane" ]]; then
        echo "ait_stamp_record: missing pane" >&2
        return 2
    fi
    if [[ ! "$record_id" =~ ^[0-9a-f]{8}$ ]]; then
        echo "ait_stamp_record: record id must be 8 lowercase hex: '$record_id'" >&2
        return 2
    fi
    ait_tmux set-option -p -t "$pane" "$AIT_RECORD_OPTION" "$record_id"
}
