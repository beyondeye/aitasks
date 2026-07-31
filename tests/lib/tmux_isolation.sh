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
# This file therefore holds TWO deliberately different policies, and the
# difference is the point:
#
#   require_isolated_tmux   — isolate, NEVER refuse. The default for tests whose
#                             every tmux call is gateway- or fixture-routed.
#   require_clean_ait_server — refuse (exit 2) when it is unsafe. For the small
#                             set of tests that run framework code which reaches
#                             tmux OUTSIDE the gateway, where isolation alone is
#                             not a sufficient guarantee.
#
# Usage:
#   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   . "$SCRIPT_DIR/lib/tmux_isolation.sh"
#   require_clean_ait_server     # only for the "refuse" class; MUST come first
#   require_isolated_tmux

if [[ -z "${_AIT_TMUX_ISOLATION_LOADED:-}" ]]; then
    _AIT_TMUX_ISOLATION_LOADED=1

    require_isolated_tmux() {
        # 1. Detach from any tmux server inherited from the surrounding
        #    terminal: a stray `tmux` call can no longer reach the user's
        #    server via $TMUX. Sourced, so this persists for the whole test
        #    process (the per-fixture `unset TMUX` in callers is now redundant
        #    but harmless).
        #
        #    Also drop $TMUX_PANE: it names the *outer* session's current pane
        #    (e.g. "%2"). Mock-based tests fabricate synthetic pane ids (%1, %2,
        #    …) and construct app objects that auto-exclude their own pane via
        #    os.environ["TMUX_PANE"] (see TmuxMonitor.__init__). If the inherited
        #    value collides with a synthetic id, that pane is silently excluded
        #    from discovery — a pane-id collision leak this helper exists to
        #    prevent. Unsetting it keeps synthetic-pane tests hermetic.
        unset TMUX
        unset TMUX_PANE

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

    # Pre-flight REFUSAL guard for the narrow class of live tests that execute
    # framework code reaching tmux **outside** the gateway — where
    # `require_isolated_tmux` is not a sufficient guarantee.
    #
    # The motivating case is the shadow cleanup hook: `attach_shadow_cleanup_hook`
    # arms a persistent `remain-on-exit` + `pane-died` hook that later runs
    # `aitask_companion_cleanup.sh`, and that script issues raw `tmux` with no
    # socket flag BY DESIGN (it relies on `$TMUX` from the firing server's job
    # environment). `AITASKS_TMUX_SOCKET` therefore cannot sandbox it, so a test
    # that really fires such a hook wants a positively empty playing field, not
    # only a redirected one.
    #
    # Policy (mirrors the pick-time preflight in
    # `aidocs/framework/tui_conventions.md`, "Tmux-stress tasks"):
    #   1. Launched from inside tmux ($TMUX set)   -> refuse, exit 2.
    #   2. The dedicated `-L ait` server is alive  -> refuse, exit 2, listing its
    #      panes. Any pane there is framework work (agents, shadows, TUIs) that
    #      the caller told us not to gamble with. Deliberately NOT classified
    #      per-pane: the agent/TUI-name lists are canonical Python data
    #      (`monitor_core.DEFAULT_AGENT_PREFIXES` / `DEFAULT_TUI_NAMES`) and
    #      re-deriving them in bash would be a duplicate that silently drifts.
    #      Refusing on any pane is the fail-closed reading and needs no list.
    #   3. Any other reachable server (the user's personal default socket) ->
    #      WARN and continue. Refusing there is the over-strictness t936 removed,
    #      and these tests never address that socket.
    #   4. AIT_LIVE_TMUX_TEST_FORCE=1 overrides 1 and 2 (dedicated CI box).
    #
    # ORDERING IS LOAD-BEARING: call this BEFORE `require_isolated_tmux`. That
    # function unsets $TMUX and repoints $TMUX_TMPDIR, after which this guard
    # could neither see rule 1 nor resolve `-L ait` to the user's real socket
    # (/tmp/tmux-<uid>/ait) — it would probe the empty isolated dir and pass
    # vacuously.
    require_clean_ait_server() {
        local script_name
        script_name="$(basename "${0:-this test}")"

        if [[ -n "${AIT_LIVE_TMUX_TEST_FORCE:-}" ]]; then
            echo "WARNING: AIT_LIVE_TMUX_TEST_FORCE is set — skipping the clean-server pre-flight." >&2
            return 0
        fi

        if [[ -n "${TMUX:-}" ]]; then
            cat >&2 <<EOF
ERROR: ${script_name} cannot run from inside a tmux session.

This test arms real \`pane-died\` cleanup hooks. \`aitask_companion_cleanup.sh\`
runs raw \`tmux\` with no socket flag by design, so no environment override can
sandbox it once it fires.

Open a fresh terminal that is NOT inside tmux, then re-run:
    bash tests/${script_name}

To override (dedicated CI box only):
    AIT_LIVE_TMUX_TEST_FORCE=1 bash tests/${script_name}
EOF
            exit 2
        fi

        command -v tmux >/dev/null 2>&1 || return 0

        local ait_panes
        ait_panes="$(tmux -L ait list-panes -a \
            -F '  #{pane_id} #{window_name} #{pane_current_command} [#{@aitask_shadow_target}]' \
            2>/dev/null || true)"
        if [[ -n "$ait_panes" ]]; then
            cat >&2 <<EOF
ERROR: ${script_name} refuses to run while the dedicated \`-L ait\` tmux server
is alive.

Panes currently on that server:
${ait_panes}

That server carries this framework's coding agents, shadows and TUIs. This test
arms real \`pane-died\` cleanup hooks, and \`aitask_companion_cleanup.sh\` reaches
tmux with raw, un-flagged calls — so the safe pre-condition is an empty field,
not a redirected one.

Save your work, then from a terminal that is NOT inside tmux:
    tmux -L ait kill-server
    bash tests/${script_name}

To override (dedicated CI box only):
    AIT_LIVE_TMUX_TEST_FORCE=1 bash tests/${script_name}
EOF
            exit 2
        fi

        local other
        other="$(tmux list-sessions -F '#{session_name}' 2>/dev/null | paste -sd, - || true)"
        if [[ -n "$other" ]]; then
            echo "NOTE: personal tmux sessions are alive on the default socket (${other})." >&2
            echo "      They are not touched — this test runs on its own throwaway server." >&2
        fi
        return 0
    }
fi
