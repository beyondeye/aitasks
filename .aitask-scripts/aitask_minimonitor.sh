#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/tmux_exec.sh
source "$SCRIPT_DIR/lib/tmux_exec.sh"

PYTHON="$(require_ait_python)"

# Read-only review-loop event log (t1606). Dispatched HERE, before everything
# below it, and that placement is load-bearing rather than tidiness: reading a
# log needs neither Textual nor tmux, and the single-instance guard further down
# would answer "A monitor is already running. Exiting." (exit 0, no output) for
# anyone asking why their loop disarmed from the very window that hosts the
# minimonitor — i.e. it would fail in exactly the case it exists to serve.
if [[ "${1:-}" == "--loop-log" ]]; then
    shift
    exec "$PYTHON" "$SCRIPT_DIR/monitor/review_loop_log.py" "$@"
fi

# Catch the "venv exists but lacks deps" case (framework upgraded but setup not re-run).
missing=()
"$PYTHON" -c "import textual" 2>/dev/null || missing+=(textual)
"$PYTHON" -c "import yaml"    2>/dev/null || missing+=(pyyaml)
if [[ ${#missing[@]} -gt 0 ]]; then
    die "Missing Python packages: ${missing[*]}. Run 'ait setup' to install all dependencies."
fi

# Check tmux is available
if ! command -v tmux &>/dev/null; then
    echo "Error: tmux is not installed. The mini monitor TUI requires tmux." >&2
    exit 1
fi

# Check terminal capabilities (warn on incapable terminals)
ait_warn_if_incapable_terminal

# Single-instance guard: skip if another minimonitor/monitor runs in the same
# window. Matches the @aitask_monitor_kind pane marker each app stamps on itself
# at mount — the old test was `pane_current_command` against `minimonitor` /
# `monitor_app`, but a live monitor pane reports `python`, so it could never
# fire (t1451). Only a booted app ever writes the marker, so THIS pane cannot be
# carrying one yet and no self-exclusion is needed.
#
# Liveness is decided by lib/monitor_marker.py, NOT reimplemented here: a shell
# rewrite of the rule diverges silently (`${marker##*:}` reads `garbage:123` as
# a dead pid; `kill -0` reports failure for another user's live process where
# os.kill counts it alive). MARKER_TOOL is assigned unconditionally on purpose —
# a `${MARKER_TOOL:-…}` override would be a test-only backdoor that also lets a
# caller point this at an arbitrary script we then execute. Tests inject faults
# through $AIT_PYTHON, the documented interpreter override.
#
# BLOCKING IS THE DEFAULT ARM. Only the two verified verdicts — 11 absent, 10
# stale — let the loop continue. Every other status (a crashed interpreter => 1,
# a missing file / usage error => 2, 126/127, a signal) means the marker was
# never classified, and an unclassified marker is "present".
#
# "THIS WINDOW" MEANS $TMUX_PANE's WINDOW. An untargeted `list-panes` does not
# list the window this pane is in: tmux resolves it to the session's CURRENT
# window (measured on tmux 3.8, t2039). A companion split into a background
# window — `ait ide`'s recreated viewers, a `-d` launch, a cross-session spawn —
# therefore read the active `monitor` window's live marker and exited at once.
# A pane target lists that pane's window. Without $TMUX_PANE there is no own
# window to name, so the read stays untargeted: the pre-t2039 behaviour, which
# keeps the blocking default rather than skipping the guard. A $TMUX_PANE from a
# foreign server can name another pane on the gateway's server; that collision
# predates this target and is not widened by it.
MARKER_TOOL="$SCRIPT_DIR/lib/monitor_marker.py"
GUARD_TARGET=()
[[ -n "${TMUX_PANE:-}" ]] && GUARD_TARGET=(-t "$TMUX_PANE")
if [[ -n "${TMUX:-}" ]]; then
    while IFS='|' read -r pane_id marker; do
        [[ -z "$marker" ]] && continue
        marker_rc=0
        "$PYTHON" "$MARKER_TOOL" state "$marker" || marker_rc=$?
        case "$marker_rc" in
            11) continue ;;                       # verified absent
            10) # verified stale — the marking process is gone; self-heal
                ait_tmux set-option -pu -t "$pane_id" \
                    @aitask_monitor_kind 2>/dev/null || true
                continue ;;
            0)  echo "A monitor is already running in this window. Exiting." ;;
            *)  # NOT a verdict: the check itself failed. Say so distinctly — a
                # silent block is indistinguishable from a real monitor.
                echo "Could not classify the monitor marker on $pane_id" \
                     "(check exited $marker_rc) — assuming a monitor is" \
                     "running. Exiting." >&2 ;;
        esac
        # Outside the case, so a future arm must `continue` explicitly to avoid
        # exiting: no new non-blocking path can be created by omission.
        exit 0
    done < <(ait_tmux list-panes ${GUARD_TARGET[@]+"${GUARD_TARGET[@]}"} \
        -F "#{pane_id}|#{@aitask_monitor_kind}" 2>/dev/null || true)
fi

exec "$PYTHON" "$SCRIPT_DIR/monitor/minimonitor_app.py" "$@"
