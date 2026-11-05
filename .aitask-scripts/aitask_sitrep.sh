#!/usr/bin/env bash
# aitask_sitrep.sh - `ait sitrep`: open the repository's sitrep agent window, and
# the read-only facts its skill reads (t2175_4).
#
# Usage:
#   ait sitrep [open] [--agent-string <a>] [--no-select] [--root <path>]
#                     [--session <name>]
#   ait sitrep root [--root <path>]
#   ait sitrep triage <id> [--root <path>]
#   ait sitrep triage --open [--root <path>]
#   ait sitrep case <verb> ...      (the review-case corpus; t2175_6)
#
# open (the default verb) focuses the repository's sitrep agent, or launches it
# in its OWN tmux window `agent-sitrep` (`-<n>` when the session already holds
# that name) with a minimonitor companion. One sitrep per repository: the agent
# pane is stamped `@aitask_sitrep_root=<canonical root>`, and a live lookup under
# a per-server lock refuses rather than spawn a second one. Needs tmux; the new
# window goes into the session holding $TMUX_PANE, or into `--session <name>`
# (which must exist; the TUIs pass the selected agent's session).
#   SITREP_SPAWNED:<pane>|<session>:<window>   (+ SITREP_WARN:companion_not_spawned)
#   SITREP_FOCUSED:<pane>
#   SITREP_FOCUS_FAILED:<pane>                 exit 1 (it exists; switching to it
#                                              failed; --no-select never switches)
#   SITREP_REFUSED:<reason>                    exit 1
#     reasons: not_in_tmux, no_session (also an unknown --session), root:<why>,
#     lock_busy, lookup_failed, no_command, window_list_failed, launch:<why>,
#     stamp:<exited|removed|stuck>
#
# root prints the canonical project root (a linked or removed `aiwork/` worktree
# maps to the main worktree), then whether the cwd is it:
#   ROOT:<path>  then  CWD_OK | CWD_MISMATCH:<cwd>    (ROOT_FAILED:<why>, exit 1)
#
# triage <id> reports the mechanical facts of triaging one harvested wrap-up
# item (PASSAGE/BANNER/KEY/CAPTURE, TASK/PLAN/COMMIT, TRAIL_WATCHED /
# TRAIL_UNWATCHED, DERIVED, last TRIAGE:c<N>|<state>|<rev>); `triage --open`
# prints that block for every open triage item, then one
# BATCH_TRAIL_UNWATCHED:<handle>|c<a>,c<b> line per handle no watch carries
# (NO_TRIAGE when none is open), so one watch covers every pending wrap-up
# naming the trail. The full line contract is in lib/sitrep_cli.py. NOT_FOUND /
# NOT_TRIAGE exit 2; an unreadable store exits 4.
#
# case <verb> ... is `aitask_sitrep_harvest.sh case`: the harvest's review cases
# (uncertain output kept verbatim with its diagnostics) -- list, show, read,
# review, replay [--apply], export, check-fixture. Its contract is in
# lib/sitrep_corpus.py.
#
# Exit codes: 0 ok, 1 refused, 2 usage (incl. a `..` path; nothing read),
# 4 store unusable.
#
# Callers: users (`ait sitrep`), the sitrep skill (`root`, `triage`, `case`; hence the
# code-agent allow-list entries, aidocs/framework/aitasks_extension_points.md),
# and t2175_5's TUI keys (`S` in monitor / minimonitor / TUI switcher), which
# run `open --root <r> --session <s>`. All tmux goes through the gateways
# (lib/tmux_exec.py). See aidocs/framework/sitrep.md.
#
# `open` runs monitor/sitrep_open.py (it drives the tmux launch stack, which
# lib/ must not import); `root` and `triage` run lib/sitrep_cli.py (stdlib).
#
# `task_utils.sh` is NOT sourced (it claims the EXIT trap at source time; the
# same reason as aitask_sitrep_todo.sh).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"

CORE="$SCRIPT_DIR/lib/sitrep_cli.py"
OPEN="$SCRIPT_DIR/monitor/sitrep_open.py"

usage() {
    echo "Usage: ait sitrep [open] [--agent-string <a>] [--no-select] [--root <path>] [--session <name>]" >&2
    echo "       ait sitrep root [--root <path>]" >&2
    echo "       ait sitrep triage <id>|--open [--root <path>]" >&2
    echo "       ait sitrep case list|show|read|review|replay|export|check-fixture ..." >&2
    exit 2
}

verb="open"
case "${1:-}" in
    open|root|triage) verb="$1"; shift ;;
    case) shift; exec "$SCRIPT_DIR/aitask_sitrep_harvest.sh" case "$@" ;;
    -h|--help) usage ;;
    ""|--*) ;;
    *) printf 'Error: unknown verb %s\n' "$1" >&2; usage ;;
esac

# `--root` is checked by the Python parsers (`sitrep_cli.root_arg`), the one
# place that sees every spelling they accept: an empty value or a `..` segment
# exits 2 before anything reads the path.

PY="$(require_ait_python)"
if [[ "$verb" == "open" ]]; then
    exec "$PY" "$OPEN" "$@"
fi
exec "$PY" "$CORE" "$verb" "$@"
