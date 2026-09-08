#!/usr/bin/env bash
# aitask_frozen.sh - Freeze / restore / reconcile entry point for frozen code
# agents (t1705_4, restore added by t1705_5).
#
# A thin shell face over the two frozen-agent engines. It exists so they can be
# reached from places that can only run a command string:
#
#   * a TUI keybinding (t1705_7 wires the minimonitor / monitor keys);
#   * `tmux run-shell -b "<repo>/.aitask-scripts/aitask_frozen.sh reconcile"`,
#     which is how a coordinator that must OUTLIVE the pane it respawns gets
#     started — a detached tmux server job, not a child of the dying pane.
#
# Verbs:
#   freeze <pane_id>          freeze one agent pane into a stand-in viewer
#   freeze --all              freeze every agent-facing pane on every session
#   restore <id> [--repick]   relaunch one frozen agent in its stand-in's pane
#   restore --all [--repick]  relaunch every frozen agent, sequentially
#   reconcile                 settle every non-`live` record from observable facts
#
# TUIs MUST invoke `restore` through `run-shell -b`, never inline: the
# coordinator respawns the very pane a TUI keybinding would be running in, so a
# child of that pane would be killed mid-transaction — leaving a `restoring`
# record for reconcile to clean up and, to the user, a dead pane. `run-shell -b`
# is a detached tmux server job and outlives the respawn (measured, t1705_1).
#
# Two engines, dispatched HERE rather than inside one module: `restore` execs
# `lib/agent_restore.py`, everything else execs `lib/agent_freeze.py`. That keeps
# each module's `main()` owning exactly its own verbs, and — the load-bearing
# half — avoids `agent_freeze` importing `agent_restore`. Reconcile is the repair
# side: it must settle an abandoned restore with NO coordinator present, so it
# cannot depend on the coordinator module.
#
# NOT SKILL-INVOKED. Callers are TUIs, sibling scripts and tmux jobs — never a
# SKILL.md — so per `aidocs/framework/aitasks_extension_points.md` this script
# needs no code-agent allow-list entries. It also has NO `ait` dispatcher case
# yet: `ait frozenagent` (the viewer) arrives with t1705_6, and whether a
# user-facing `ait frozen` verb is worth having is decided in t1705_9/10.
#
# It issues no raw `tmux` of its own — every tmux call is inside the Python
# module, which routes through the `lib/tmux_exec.py` gateway — so
# `tests/test_no_raw_tmux.sh` needs no allowlist entry for it.
#
# Exit codes:
#   0  every result succeeded (an empty batch counts as success)
#   1  at least one pane failed; its `FREEZE_FAILED:<stage>|…` line says which
#   2  usage error
#
# Wire lines are printed verbatim on stdout, one per pane / per record, so a
# caller can parse them without re-deriving anything.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"

FREEZE_PY="$SCRIPT_DIR/lib/agent_freeze.py"
RESTORE_PY="$SCRIPT_DIR/lib/agent_restore.py"

usage() {
    cat >&2 <<'EOF'
Usage: aitask_frozen.sh freeze <pane_id>
       aitask_frozen.sh freeze --all
       aitask_frozen.sh restore <id> [--repick]
       aitask_frozen.sh restore --all [--repick]
       aitask_frozen.sh reconcile
EOF
    exit 2
}

[ $# -ge 1 ] || usage

ENGINE="$FREEZE_PY"

case "$1" in
    freeze)
        [ $# -eq 2 ] || usage
        ;;
    restore)
        # `restore <id>` / `restore --all`, each optionally with `--repick`.
        # Arity is validated in the module (it owns the flag vocabulary); this
        # only rejects the no-argument form so `usage` stays the shell's answer.
        [ $# -ge 2 ] || usage
        ENGINE="$RESTORE_PY"
        ;;
    reconcile)
        [ $# -eq 1 ] || usage
        ;;
    -h|--help)
        usage
        ;;
    *)
        echo "ERROR:unknown verb: $1" >&2
        usage
        ;;
esac

# `exec` on purpose: the Python module's exit status IS this script's contract,
# and for the `run-shell -b` coordinator case there is no reason to keep a shell
# alive around it.
exec "$(require_ait_python)" "$ENGINE" "$@"
