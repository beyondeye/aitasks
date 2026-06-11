#!/usr/bin/env bash
# Tmux isolation helper for tmux-destructive tests.
#
# Tests that source this helper create and tear down their own tmux server
# (via TMUX_TMPDIR=$(mktemp -d) + tmux kill-server). Historically that
# isolation has leaked — `kill-server` cleanup, pane-id collisions, or
# control-client paths have cascaded into the surrounding user's tmux
# server, killing every pane inside it (long-running TUIs, shells, editors).
#
# This file used to expose `require_no_tmux`, which simply ABORTED (exit 2)
# whenever the user had any tmux session alive on the default socket or the
# test was launched from inside tmux. That made the 8 tmux tests unrunnable on
# any developer machine running tmux (the common case), so the full suite could
# never go green locally without first detaching/killing tmux.
#
# `require_isolated_tmux` replaces that refusal with a stronger, positive
# guarantee: instead of aborting, it makes the user's default-socket server
# *unreachable* for the whole test process. With that in place the test can run
# safely alongside a live user session — and even a stray tmux call that forgets
# its own per-fixture override can no longer touch the user's server.
#
# Usage:
#   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   . "$SCRIPT_DIR/lib/tmux_isolation.sh"
#   require_isolated_tmux

if [[ -z "${_AIT_TMUX_ISOLATION_LOADED:-}" ]]; then
    _AIT_TMUX_ISOLATION_LOADED=1

    require_isolated_tmux() {
        # 1. Detach from any tmux server inherited from the surrounding
        #    terminal: a stray `tmux` call can no longer reach the user's
        #    server via $TMUX. Sourced, so this persists for the whole test
        #    process (the per-fixture `unset TMUX` in callers is now redundant
        #    but harmless).
        unset TMUX

        # 2. Redirect tmux's *default* socket directory away from the user's
        #    (/tmp/tmux-$UID) to a private, per-user location. Per-case
        #    `export TMUX_TMPDIR=...` in the tests still overrides this; this is
        #    the safety net so that any tmux call WITHOUT its own override still
        #    lands in an isolated dir and can never address the user's server.
        #
        #    A fixed per-user path (mode 0700) is reused across runs, so it
        #    needs no per-run cleanup and cannot accumulate temp dirs. Nothing
        #    should ever spawn a server here (every real test sets its own
        #    fixture TMUX_TMPDIR), so it stays empty in normal operation; if a
        #    stray call ever did, that server would be isolated and harmless.
        if [[ -z "${_AIT_ISOLATED_TMUX_TMPDIR:-}" ]]; then
            _AIT_ISOLATED_TMUX_TMPDIR="${TMPDIR:-/tmp}/ait_isolated_tmux_$(id -u)"
            mkdir -p "$_AIT_ISOLATED_TMUX_TMPDIR" 2>/dev/null || true
            chmod 700 "$_AIT_ISOLATED_TMUX_TMPDIR" 2>/dev/null || true
            export _AIT_ISOLATED_TMUX_TMPDIR
        fi
        export TMUX_TMPDIR="$_AIT_ISOLATED_TMUX_TMPDIR"

        # 3. Pin the gateway socket knob to the no-flag escape hatch (t953):
        #    unset AITASKS_TMUX_SOCKET now means the dedicated `-L ait`
        #    socket, so gateway-routed app code under test would otherwise
        #    target a different server than the raw (no `-L`) fixture spawns
        #    in the tests. Set-but-empty => no socket flag for BOTH, so they
        #    agree on the default socket inside the isolated TMUX_TMPDIR.
        #    This also shields the suite from a custom AITASKS_TMUX_SOCKET
        #    value inherited from the developer's shell.
        export AITASKS_TMUX_SOCKET=""
    }
fi
