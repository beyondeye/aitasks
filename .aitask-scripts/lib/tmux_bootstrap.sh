#!/usr/bin/env bash
# tmux_bootstrap.sh - Spawn a project's tmux session detached.
#
# Shared between `aitask_ide.sh` (sourced) and `tui_switcher.py`
# (subprocess via the standalone CLI form below). Single source of
# truth for: how a session is named, which window is seeded first,
# which env vars are written, and whether the syncer auto-starts.
#
# Sourced form (from aitask_ide.sh):
#     source "$SCRIPT_DIR/lib/tmux_bootstrap.sh"
#     # then call any of the public helpers below.
#
# Standalone form (from tui_switcher.py via `bash <path> <root>`):
#     bash .aitask-scripts/lib/tmux_bootstrap.sh /path/to/project
#         Idempotent — no-op if the target session already exists.

# Guard against double-sourcing.
if [[ -n "${_AIT_TMUX_BOOTSTRAP_LOADED:-}" ]]; then
    # shellcheck disable=SC2317  # `return` is reachable when sourced.
    return 0 2>/dev/null || true
fi
_AIT_TMUX_BOOTSTRAP_LOADED=1

# Resolve our own SCRIPT_DIR so the standalone form can find sibling
# scripts (terminal_compat.sh, aitask_projects.sh). When sourced, the
# caller's SCRIPT_DIR already points at .aitask-scripts/; we recompute
# our own anchor here to stay robust to either case.
_TMUX_BOOTSTRAP_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_TMUX_BOOTSTRAP_SCRIPTS_DIR="$(cd "$_TMUX_BOOTSTRAP_LIB_DIR/.." && pwd)"

# Gateway for all tmux invocations (socket flag + exact-match targeting),
# shared with the Python TmuxClient. Pulls in terminal_compat.sh (die/warn/info)
# transitively; both are guarded against double-sourcing.
# shellcheck source=tmux_exec.sh disable=SC1091
source "$_TMUX_BOOTSTRAP_LIB_DIR/tmux_exec.sh"

# --- Public helpers (callable after sourcing) ---------------------------

# _tmux_bootstrap_resolve_session <project_root>
#
# Echoes the tmux session name for <project_root>: reads
# `tmux.default_session` from its project_config.yaml; falls back to
# the literal "aitasks" (mirrors aitask_ide.sh::resolve_session).
_tmux_bootstrap_resolve_session() {
    local root="$1"
    local cfg="$root/aitasks/metadata/project_config.yaml"
    if [[ -f "$cfg" ]]; then
        local name
        name=$(awk '
            /^tmux:/ { intmux=1; next }
            intmux && /^  default_session:/ {
                sub(/^  default_session:[ \t]*/, "")
                gsub(/"/, "")
                gsub(/'"'"'/, "")
                sub(/[[:space:]]+$/, "")
                print
                exit
            }
            /^[^ #]/ && !/^tmux:/ { intmux=0 }
        ' "$cfg")
        if [[ -n "$name" ]]; then
            echo "$name"
            return
        fi
    fi
    echo "aitasks"
}

# _tmux_bootstrap_read_syncer_autostart <project_root>
#
# Echoes "1" if tmux.syncer.autostart is true in <project_root>'s
# project_config.yaml; "0" otherwise (mirrors
# aitask_ide.sh::read_syncer_autostart).
_tmux_bootstrap_read_syncer_autostart() {
    local root="$1"
    local cfg="$root/aitasks/metadata/project_config.yaml"
    [[ -f "$cfg" ]] || { echo "0"; return; }
    local out
    out=$(awk '
        /^tmux:/ { intmux=1; next }
        intmux && /^  syncer:/ { insyncer=1; next }
        insyncer && /^    autostart:/ {
            sub(/^    autostart:[ \t]*/, "")
            gsub(/"/, "")
            gsub(/'"'"'/, "")
            sub(/[[:space:]]+$/, "")
            if ($0 == "true") { print "1"; exit }
            print "0"; exit
        }
        /^[^ #]/ && !/^tmux:/ { intmux=0; insyncer=0 }
        intmux && /^  [^ ]/ && !/^  syncer:/ { insyncer=0 }
    ' "$cfg" 2>/dev/null)
    [[ -z "$out" ]] && out="0"
    echo "$out"
}

# _tmux_bootstrap_set_project_registry <project_root> <session>
#
# Registers <project_root> under the per-session tmux global env var
# AITASKS_PROJECT_<session> AND appends it to the per-user persistent
# index via `aitask_projects.sh add`. Both writes are best-effort.
_tmux_bootstrap_set_project_registry() {
    local root="$1"
    local session="$2"
    ait_tmux set-environment -g "AITASKS_PROJECT_${session}" "$root" 2>/dev/null || true
    "$_TMUX_BOOTSTRAP_SCRIPTS_DIR/aitask_projects.sh" add "$root" >/dev/null 2>&1 || true
}

# _tmux_bootstrap_ensure_syncer_window <project_root> <session>
#
# If the project's syncer autostart flag is on AND the session does
# not already have a `syncer` window, creates one (with cwd anchored
# at <project_root> so `ait syncer` resolves correctly).
_tmux_bootstrap_ensure_syncer_window() {
    local root="$1"
    local session="$2"
    local autostart
    autostart=$(_tmux_bootstrap_read_syncer_autostart "$root")
    [[ "$autostart" == "1" ]] || return 0
    local session_t
    session_t="$(ait_tmux_session_target "$session")"
    if ! ait_tmux list-windows -t "$session_t" -F '#{window_name}' 2>/dev/null | grep -qx 'syncer'; then
        ait_tmux new-window -t "${session_t}:" -c "$root" -n syncer 'ait syncer' 2>/dev/null || true
    fi
}

# spawn_session_detached <project_root>
#
# Idempotently spawns a detached tmux session for <project_root> with
# the project's configured session name and a seeded `monitor` window.
# If the session already exists, only the per-session env / persistent
# registry / syncer-window steps run (the existing session is left
# untouched). Safe to call from inside another tmux session.
spawn_session_detached() {
    local root="$1"
    if [[ -z "$root" ]]; then
        echo "spawn_session_detached: missing <project_root>" >&2
        return 2
    fi
    if [[ ! -d "$root" ]]; then
        echo "spawn_session_detached: not a directory: $root" >&2
        return 2
    fi
    if [[ ! -f "$root/aitasks/metadata/project_config.yaml" ]]; then
        # Structured sentinel consumed by tui_switcher._ensure_session_live
        # (race-condition path: entry was OK at switcher mount but went
        # STALE before bootstrap). Followed by the human-readable detail
        # so casual CLI users still see what went wrong.
        echo "BOOTSTRAP_FAILED:stale_path" >&2
        echo "spawn_session_detached: not an aitasks project: $root" >&2
        return 42
    fi

    local session session_t
    session=$(_tmux_bootstrap_resolve_session "$root")
    session_t="$(ait_tmux_session_target "$session")"

    command -v tmux >/dev/null || {
        echo "spawn_session_detached: tmux is not installed" >&2
        return 3
    }

    if ! ait_tmux has-session -t "$session_t" 2>/dev/null; then
        # First session => this call creates the tmux SERVER. Spawn it inside a
        # persistent systemd-user service (session.slice) so a compositor /
        # app.slice teardown no longer kills the server (t943). Socket
        # unchanged; only the new server's cgroup placement differs. The helper
        # degrades gracefully (setsid → plain tmux) where systemd --user is
        # unavailable, preserving today's behavior.
        # new-session -s takes a literal session name; do not prefix '='.
        ait_tmux_new_session_persistent "$session" "$root" monitor 'ait monitor' \
            || {
                echo "spawn_session_detached: tmux new-session failed for '$session'" >&2
                return 4
            }
    fi

    _tmux_bootstrap_set_project_registry "$root" "$session"
    _tmux_bootstrap_ensure_syncer_window "$root" "$session"
}

# --- Standalone CLI dispatch -------------------------------------------

# When invoked as `bash tmux_bootstrap.sh <project_root>`, dispatch
# to spawn_session_detached. Distinguish "sourced vs. executed" via
# BASH_SOURCE[0] == $0.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    set -euo pipefail
    if [[ $# -lt 1 ]]; then
        echo "Usage: tmux_bootstrap.sh <project_root>" >&2
        exit 2
    fi
    # Source error helpers only when standalone (saves a round-trip
    # when sourced by aitask_ide.sh, which already loads them).
    # shellcheck source=terminal_compat.sh disable=SC1091
    source "$_TMUX_BOOTSTRAP_LIB_DIR/terminal_compat.sh"
    spawn_session_detached "$1"
fi
