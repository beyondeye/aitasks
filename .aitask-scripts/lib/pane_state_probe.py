#!/usr/bin/env python3
"""pane_state_probe.py - is the agent in a tmux pane parked on a prompt? (t1725_4)

Answers ONE question for the sync sweep's deferral record and for its
``--require-waiting`` commit gate: at this instant, is the pane showing an
awaiting-input prompt?

    pane_state_probe.py <pane_id>

prints exactly one line on stdout and always exits 0:

    waiting_<kind>   a prompt from the monitor's registry is on screen; <kind>
                     is that pattern's name (``waiting_claude_askuserquestion``)
    active           the pane was read and no prompt is on screen
    (empty)          the state could not be established: a malformed id, no
                     server, a failed capture, or a failed framework import

The empty answer is the fail-closed one: ``aitask_sync.sh`` treats anything but
``waiting_*`` as "not waiting" and refuses to commit on the holder's behalf.
That makes a broken probe look exactly like a busy session to the sweep, so any
exception is ALSO written to stderr: visible when run by hand, discarded by the
sweep. The framework imports run at module top for the same reason. A broken
bootstrap then surfaces on every invocation, including ones that never get as
far as classifying. ``tests/test_pane_state_probe.py`` and
``tests/test_sync_holder_pane_live.sh`` (case P1) fail when it breaks.

Classification is the monitor's own, not a copy: the capture goes through the
tmux gateway (``TmuxClient``) and is classified by ``monitor_core._classify_one``
scoped to the pane's agent (``agent_keys.agent_key_from_pane``), which is the
call shape ``monitor_core._classify_batch`` uses. This probe therefore answers
what minimonitor shows, never looser. See
``aidocs/framework/monitor_idle_and_prompt_detection.md``.

"Idle" (running but quiet) is deliberately not attempted: it needs two samples
over time, and this is a single-shot probe.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Two-path bootstrap, the same shape as agent_freeze.py. Launched as a script,
# only lib/ is on sys.path, and the monitor package lives one level up: without
# the scripts root, `monitor.monitor_core` raises ModuleNotFoundError and every
# answer silently becomes "".
_LIB_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _LIB_DIR.parent
for _p in (str(_SCRIPTS_DIR), str(_LIB_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    # Package form for both monitor imports, so this module and monitor_core's
    # own relative import share one `monitor.prompt_patterns` module object.
    from monitor.monitor_core import (  # noqa: E402
        COMPARE_MODE_STRIPPED,
        PaneCategory,
        _classify_one,
    )
    from monitor.prompt_patterns import all_patterns  # noqa: E402
    from agent_keys import agent_key_from_pane  # noqa: E402
    from tmux_exec import TmuxClient  # noqa: E402
    _IMPORT_ERROR: Exception | None = None
except Exception as _exc:  # noqa: BLE001 - reported by main(), never raised here
    _IMPORT_ERROR = _exc

# A pane id is the ONE input shape accepted. A session/window target would need
# parsing, and a session name may legally contain any character. Both patterns
# are applied with fullmatch: `$` also matches just before a trailing newline,
# so `^…$` with match() would accept "%5\n".
_PANE_ID_RE = re.compile(r"%[0-9]+")
# The state grammar aitask_sync.sh writes and sync_action_runner parses. Its
# `_PANE_STATE_RE` also admits "", but "" is the absence of an answer, never an
# answer, so it is not admitted here. A registry pattern whose name falls outside
# `[a-z0-9_]+` therefore fails closed at the write site instead of making the
# parser drop the whole record.
_STATE_RE = re.compile(r"waiting_[a-z0-9_]+|active")
_TIMEOUT = 2.0
# `capture-pane -S -<n>` with no `-E` reads to the bottom of the visible pane, and
# every supported agent runs on the alternate screen, so this is the whole pane.
_CAPTURE_LINES = 200


def classify_text(text: str, current_command: str = "",
                  pane_pid: int | None = None, pane_id: str = "") -> str:
    """Classify captured pane text as ``waiting_<kind>``, ``active`` or ``""``."""
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR
    agent = agent_key_from_pane(current_command, pane_pid, pane_id)
    result = _classify_one(text, COMPARE_MODE_STRIPPED, all_patterns(),
                           PaneCategory.AGENT, agent)
    state = (f"waiting_{result.awaiting_input_kind}"
             if result.awaiting_input else "active")
    return state if _STATE_RE.fullmatch(state) else ""


def probe(pane_id: str, *, client=None) -> str:
    """Probe one pane by id (``%N``). ``""`` whenever the state is not established."""
    if not isinstance(pane_id, str) or not _PANE_ID_RE.fullmatch(pane_id):
        return ""
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR
    if client is None:
        client = TmuxClient()
    rc, out = client.run(
        ["display-message", "-p", "-t", pane_id,
         "#{pane_current_command}\t#{pane_pid}"],
        timeout=_TIMEOUT,
    )
    if rc != 0:
        return ""
    current_command, _, pid_text = out.rstrip("\n").partition("\t")
    pid_text = pid_text.strip()
    pane_pid = int(pid_text) if pid_text.isdigit() else None
    rc, text = client.run(
        ["capture-pane", "-p", "-e", "-t", pane_id, "-S", f"-{_CAPTURE_LINES}"],
        timeout=_TIMEOUT,
    )
    if rc != 0:
        return ""
    return classify_text(text, current_command, pane_pid, pane_id)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    state = ""
    try:
        if _IMPORT_ERROR is not None:
            raise _IMPORT_ERROR
        if len(args) == 1:
            state = probe(args[0])
        else:
            print("usage: pane_state_probe.py <pane_id>", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 - the contract is one line, exit 0
        print(f"pane_state_probe: {type(exc).__name__}: {exc}", file=sys.stderr)
        state = ""
    print(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
