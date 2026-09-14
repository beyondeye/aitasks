#!/usr/bin/env bash
# tmux_bootstrap.sh - Spawn a project's tmux session detached.
#
# Shared between `aitask_ide.sh` (sourced), `tui_switcher.py` and
# `agent_restore.py` (both via the standalone CLI form below). Single source of
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
#
# Create-only form (from agent_restore.py, restoring a frozen agent whose
# project has no tmux session — t1784):
#     bash .aitask-scripts/lib/tmux_bootstrap.sh --create-only /path/to/project
#         Create the session or change nothing; see spawn_session_detached.

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
# Prints the tmux session name for <project_root>: `tmux.default_session`
# from its project_config.yaml, or the literal "aitasks" (mirrors
# aitask_ide.sh::resolve_session) when the key is absent or blank.
#
# Twin of agent_launch_utils.py::_read_default_session / _yaml_line_scalar;
# tests/test_tmux_default_session_resolvers.py pins the two against each other
# and against yaml.safe_load. The shared rule: the key counts only as a direct
# child of a column-0 `tmux:` block (the block's first indented content line
# fixes the child indent); a quoted value is the text between its quotes,
# verbatim; a plain value is cut at an inline comment (`#` at the start or
# after whitespace) and trimmed; YAML-1.1 nulls (~ null Null NULL), empty and
# whitespace-only values mean "not configured".
#
# `tr '\r' '\n'` gives awk the universal newlines Python's open() applies, so
# a CRLF blank line (a lone "\r" record) cannot end the block and a CR-only
# file is not read as one record. awk reads to end of input rather than
# `exit`ing on the match: an early exit leaves `tr` writing into a closed pipe
# (SIGPIPE, exit 141), which aborts a direct call under set -e + pipefail.
# Today's callers run this inside $(…), where errexit is not inherited, so
# they would survive it — reading to EOF removes the hazard instead of relying
# on that. Output uses printf, never echo — bash's echo swallows an
# option-like name such as `-n`.
_tmux_bootstrap_resolve_session() {
    local root="$1"
    local cfg="$root/aitasks/metadata/project_config.yaml"
    if [[ -f "$cfg" ]]; then
        local name
        name=$(tr '\r' '\n' < "$cfg" | awk -v SQ="'" '
            done { next }
            /^[ \t]*$/ { next }
            /^tmux:/ { intmux=1; ci=0; next }
            /^[^ \t#]/ { intmux=0; next }
            intmux && /^ +[^ #]/ {
                match($0, /^ +/); ind = RLENGTH
                if (ci == 0) ci = ind
                if (ind != ci) next
                v = substr($0, ind + 1)
                if (substr(v, 1, 16) != "default_session:") next
                v = substr(v, 17)
                sub(/^[ \t]+/, "", v)
                q = substr(v, 1, 1)
                if (q == "\"" || q == SQ) {
                    v = substr(v, 2); i = index(v, q)
                    if (i > 0) v = substr(v, 1, i - 1)
                } else {
                    sub(/^#.*/, "", v); sub(/[ \t]#.*/, "", v)
                    sub(/[[:space:]]+$/, "", v)
                    if (v == "~" || v == "null" || v == "Null" || v == "NULL") v = ""
                }
                print v; done = 1
            }
        ')
        if [[ -n "${name//[[:space:]]/}" ]]; then
            printf '%s\n' "$name"
            return 0
        fi
    fi
    printf '%s\n' aitasks
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

# _tmux_bootstrap_report_exists <session>
#
# The --create-only refusal: a structured sentinel first (parsed by
# agent_restore._bootstrap_project_session), then the human-readable detail —
# the same two-line shape as the BOOTSTRAP_FAILED:stale_path refusal.
_tmux_bootstrap_report_exists() {
    echo "BOOTSTRAP_FAILED:session_exists:$1" >&2
    echo "spawn_session_detached: session '$1' already exists; --create-only leaves it untouched" >&2
}

# spawn_session_detached <project_root> [--create-only]
#
# Idempotently spawns a detached tmux session for <project_root> with
# the project's configured session name and a seeded `monitor` window.
# If the session already exists, only the per-session env / persistent
# registry / syncer-window steps run (the existing session is left
# untouched). Safe to call from inside another tmux session.
#
# --create-only: CREATE the session or change NOTHING (t1784). The default
# mode is "ensure", which is right for `ait ide` — a user running it in a
# project means "this session is mine" — but wrong for a caller that must not
# claim a session it does not own: the registry and syncer steps would re-point
# a same-named session belonging to another project at <project_root>, and
# `discover_aitasks_sessions()` falls back to that registry entry. With the flag:
#   - an existing session of that name is left completely untouched (no env,
#     no registry, no syncer window) and reported on stderr as
#     BOOTSTRAP_FAILED:session_exists:<name>, exit 43;
#   - so is one created concurrently between the check and `new-session`: the
#     duplicate `new-session` fails and the name now exists — same report;
#   - only after THIS call created the session do the registry and syncer steps
#     run, and stdout then carries BOOTSTRAP_CREATED:<name> — the one answer a
#     caller may treat as ownership.
#
# Exit codes: 2 usage / not a directory, 3 tmux missing, 4 new-session failed,
# 42 not an aitasks project (BOOTSTRAP_FAILED:stale_path), 43 the session
# already exists (--create-only only).
spawn_session_detached() {
    local root="$1"
    local mode="${2:-}"
    if [[ -n "$mode" && "$mode" != "--create-only" ]]; then
        echo "spawn_session_detached: unknown option: $mode" >&2
        return 2
    fi
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
        # Legacy-session detection (t953): a same-name session may still live
        # on the user's default server from before the dedicated-socket move
        # (tmux cannot move sessions between servers). Warn-only here — this
        # path is non-interactive (tui_switcher bootstrap); `ait ide` runs its
        # own interactive offer before reaching this helper. Skipped when the
        # gateway already targets the default server.
        local sock_name
        sock_name="$(ait_tmux_socket_name)"
        if [[ -n "$sock_name" && "$sock_name" != "default" ]] \
            && ait_tmux_legacy has-session -t "$session_t" 2>/dev/null; then
            echo "WARNING: session '$session' also exists on the legacy default tmux server;" >&2
            echo "         run 'AITASKS_TMUX_SOCKET=default ait ide' to reach it." >&2
        fi
        # First session => this call creates the tmux SERVER. Spawn it inside a
        # persistent systemd-user service (session.slice) so a compositor /
        # app.slice teardown no longer kills the server (t943). The socket flag
        # comes from the gateway (dedicated `-L ait` by default, t953); the
        # helper also fixes the new server's cgroup placement. It degrades
        # gracefully (setsid → plain tmux) where systemd --user is unavailable.
        # new-session -s takes a literal session name; do not prefix '='.
        ait_tmux_new_session_persistent "$session" "$root" monitor 'ait monitor' \
            || {
                # --create-only: a name that exists NOW was created concurrently
                # by someone else. It is not ours — report it and touch nothing.
                if [[ "$mode" == "--create-only" ]] \
                    && ait_tmux has-session -t "$session_t" 2>/dev/null; then
                    _tmux_bootstrap_report_exists "$session"
                    return 43
                fi
                echo "spawn_session_detached: tmux new-session failed for '$session'" >&2
                return 4
            }
    elif [[ "$mode" == "--create-only" ]]; then
        # An existing session, and the caller asked to create or change nothing:
        # return BEFORE the registry / syncer steps, which would re-point it.
        _tmux_bootstrap_report_exists "$session"
        return 43
    fi

    _tmux_bootstrap_set_project_registry "$root" "$session"
    _tmux_bootstrap_ensure_syncer_window "$root" "$session"
    if [[ "$mode" == "--create-only" ]]; then
        echo "BOOTSTRAP_CREATED:$session"
    fi
    return 0
}

# --- Standalone CLI dispatch -------------------------------------------

# When invoked as `bash tmux_bootstrap.sh <project_root>`, dispatch
# to spawn_session_detached. Distinguish "sourced vs. executed" via
# BASH_SOURCE[0] == $0.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    set -euo pipefail
    _tmux_bootstrap_mode=""
    if [[ "${1:-}" == "--create-only" ]]; then
        _tmux_bootstrap_mode="--create-only"
        shift
    fi
    if [[ $# -lt 1 ]]; then
        echo "Usage: tmux_bootstrap.sh [--create-only] <project_root>" >&2
        exit 2
    fi
    # Source error helpers only when standalone (saves a round-trip
    # when sourced by aitask_ide.sh, which already loads them).
    # shellcheck source=terminal_compat.sh disable=SC1091
    source "$_TMUX_BOOTSTRAP_LIB_DIR/terminal_compat.sh"
    spawn_session_detached "$1" ${_tmux_bootstrap_mode:+"$_tmux_bootstrap_mode"}
fi
