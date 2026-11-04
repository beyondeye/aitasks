#!/usr/bin/env python3
"""sitrep_open.py - `ait sitrep open` (t2175_4): focus or launch the sitrep window.

The executable side of `monitor_core.spawn_sitrep`, kept in the monitor package
because it orchestrates the tmux launch stack (lib/ must not reach up into a TUI
package: tests/test_no_lib_to_tui_import.sh). The read-only verbs `root` and
`triage` stay in `lib/sitrep_cli.py`. Wire lines (also in `aitask_sitrep.sh`):

    SITREP_SPAWNED:<pane>|<session>:<window>   (+ SITREP_WARN:companion_not_spawned)
    SITREP_FOCUSED:<pane>
    SITREP_FOCUS_FAILED:<pane>                 exit 1 (it exists; switching failed)
    SITREP_REFUSED:<reason>                    exit 1

Needs tmux; the new window goes into the session holding $TMUX_PANE, or into
`--session <name>` when the caller names one (the monitor, minimonitor and TUI
switcher pass the SELECTED agent's / session's name, t2175_5). A named session
must exist on the server (exact match, `has-session -t =<name>`); otherwise
`SITREP_REFUSED:no_session`. A malformed name exits 2 before tmux is asked.
"""

from __future__ import annotations

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import monitor_core  # noqa: E402  (puts lib/ on sys.path)
from agent_launch_utils import pane_session  # noqa: E402
from tmux_exec import TmuxClient  # noqa: E402
from sitrep_cli import root_arg  # noqa: E402  (the one --root check)


def session_arg(value: str) -> str:
    """argparse ``type`` of ``--session``: a plain tmux session name.

    tmux itself never creates a name holding ``:`` or ``.`` (they are target
    separators), so either one, a control character, a leading ``-`` (an option
    to tmux) or an empty value can only be a malformed request: exit 2.
    """
    if (not value or value.startswith("-")
            or any(ch in value for ch in ":.")
            or any(ord(ch) < 0x20 or ord(ch) == 0x7f for ch in value)):
        raise argparse.ArgumentTypeError(f"invalid session name {value!r}")
    return value


class _Gateway:
    """The `monitor.tmux_run` duck type over the tmux gateway (`lib/tmux_exec`)."""

    def __init__(self):
        self._client = TmuxClient()

    def tmux_run(self, args, timeout: float = 5.0):
        return self._client.run(args, timeout=timeout)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ait sitrep open", allow_abbrev=False)
    ap.add_argument("--agent-string", default=None)
    ap.add_argument("--no-select", action="store_true")
    ap.add_argument("--root", default=".", type=root_arg)
    ap.add_argument("--session", default=None, type=session_arg)
    args = ap.parse_args(argv)
    pane = os.environ.get("TMUX_PANE", "")
    if not os.environ.get("TMUX") or (not pane and args.session is None):
        print("SITREP_REFUSED:not_in_tmux")
        print("Hint: run `ait sitrep` inside tmux, or `ait codeagent invoke "
              "sitrep` to start the agent in this terminal (no window, no "
              "duplicate guard).", file=sys.stderr)
        return 1
    gateway = _Gateway()
    if args.session is not None:
        rc, _ = gateway.tmux_run(["has-session", "-t", f"={args.session}"])
        session = args.session if rc == 0 else None
    else:
        session = pane_session(pane)
    if not session:
        print("SITREP_REFUSED:no_session")
        return 1
    res = monitor_core.spawn_sitrep(
        gateway, target_root=os.path.abspath(args.root), session=session,
        select_window=not args.no_select, agent_string=args.agent_string)
    if res.status == "spawned":
        print(f"SITREP_SPAWNED:{res.pane}|{res.window}")
        if res.detail:
            print(f"SITREP_WARN:{res.detail}")
        return 0
    if res.status == "focused":
        print(f"SITREP_FOCUSED:{res.pane}")
        return 0
    if res.status == "focus_failed":
        print(f"SITREP_FOCUS_FAILED:{res.pane}")
        return 1
    print(f"SITREP_REFUSED:{res.detail}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
