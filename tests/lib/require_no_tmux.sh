#!/usr/bin/env bash
# Pre-flight guard for tmux-destructive tests.
#
# Tests that source this helper create and tear down their own tmux server
# (via TMUX_TMPDIR=$(mktemp -d) + tmux kill-server). Historically that
# isolation has leaked — `kill-server` cleanup, pane-id collisions, or
# control-client paths have cascaded into the surrounding user's tmux
# server, killing every pane inside it (long-running TUIs, shells, editors).
#
# `require_no_tmux` aborts with a clear, actionable message when:
#   1. The test is being run from inside a tmux pane ($TMUX is set), OR
#   2. Any user tmux server is reachable on the default socket
#      (`tmux list-sessions` returns 0).
#
# Usage:
#   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   . "$SCRIPT_DIR/lib/require_no_tmux.sh"
#   require_no_tmux

if [[ -z "${_AIT_REQUIRE_NO_TMUX_LOADED:-}" ]]; then
    _AIT_REQUIRE_NO_TMUX_LOADED=1

    require_no_tmux() {
        local script_name
        script_name="$(basename "${0:-this test}")"

        if [[ -n "${TMUX:-}" ]]; then
            cat >&2 <<EOF
ERROR: ${script_name} cannot run from inside a tmux session.

This test creates and tears down its own tmux server. Past failures have
cascaded into the surrounding user server, killing every pane inside it
(long-running TUIs, shells, editors) — possible data loss.

Open a fresh terminal that is NOT inside tmux, then re-run:
    bash tests/${script_name}
EOF
            exit 2
        fi

        if command -v tmux >/dev/null 2>&1 && tmux list-sessions >/dev/null 2>&1; then
            local sessions
            sessions="$(tmux list-sessions -F '#{session_name}' 2>/dev/null | paste -sd, -)"
            cat >&2 <<EOF
ERROR: ${script_name} refuses to run while other tmux sessions are alive.

Detected sessions on the default socket: ${sessions}

This test isolates its own tmux server, but historical leaks have killed
the user's main server (and every pane inside it). Aborting to protect any
in-progress work.

Save state in your existing sessions, detach, then:
    tmux kill-server
And re-run from a fresh terminal that is NOT inside tmux.
EOF
            exit 2
        fi
    }
fi
