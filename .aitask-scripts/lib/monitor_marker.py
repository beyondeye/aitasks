#!/usr/bin/env python3
"""The `@aitask_monitor_kind` pane marker and its liveness rule (t1451).

A running `ait monitor` / `ait minimonitor` stamps its own tmux pane with this
user option so the single-instance guards can recognise it. The guards used to
match `#{pane_current_command}` against `minimonitor` / `monitor_app`, but a
live monitor pane reports `python`, so neither guard could ever fire — dead code
pretending to be a guard.

**This module is the ONE implementation of the liveness rule.** It is called
from Python (`agent_launch_utils.maybe_spawn_minimonitor`) and, via the CLI
entry point below, from shell (`aitask_minimonitor.sh`). A shell rewrite of the
rule diverges silently in at least two ways, which is why there is not one:

* `${marker##*:}` reads `garbage:123` as a dead numeric pid, so the shell would
  clear a marker this module calls unverifiable and blocks on;
* `kill -0` reports *failure* for a live process owned by another user, where
  `os.kill(pid, 0)`'s `PermissionError` means the process exists.

Deliberately **stdlib-only** — no `tmux_exec`, no yaml — so the shell guard can
exec it as a script without paying for `agent_launch_utils`' import graph.
The *writers* (`mark_monitor_pane` / `unmark_monitor_pane`) live in
`agent_launch_utils.py`, which owns the tmux gateway client.
"""

from __future__ import annotations

import os
import re
import sys

MONITOR_KIND_OPTION = "@aitask_monitor_kind"

# The only kinds a writer may stamp. A value naming anything else is not ours
# to interpret — see `monitor_marker_state`.
MONITOR_KINDS = ("minimonitor", "monitor")

_MARKER_RE = re.compile(r"^(minimonitor|monitor):([0-9]+)$")

# Classification results.
STATE_ABSENT = "absent"
STATE_PRESENT = "present"
STATE_STALE = "stale"

# Verdict codes for the CLI. Chosen ABOVE the range a failing interpreter can
# produce: an uncaught exception exits 1, a missing file or usage error exits 2,
# a non-executable / not-found exec exits 126/127, a signal exits 128+n. If a
# verdict shared any of those, an interpreter failure would be indistinguishable
# from a decision — and mapping it to "stale" would make the shell guard CLEAR A
# LIVE MARKER on a crash.
EXIT_PRESENT = 0
EXIT_STALE = 10
EXIT_ABSENT = 11

_STATE_EXIT = {
    STATE_PRESENT: EXIT_PRESENT,
    STATE_STALE: EXIT_STALE,
    STATE_ABSENT: EXIT_ABSENT,
}


def parse_monitor_marker(value: str) -> tuple[str, int] | None:
    """``<kind>:<pid>`` with a KNOWN kind -> ``(kind, pid)``; anything else -> None."""
    match = _MARKER_RE.match(value or "")
    if match is None:
        return None
    return match.group(1), int(match.group(2))


def _process_exists(pid: int) -> bool:
    """Is there a process with this pid?

    ``PermissionError`` means it exists but belongs to another user — that is
    still "exists". Only ``ProcessLookupError`` is proof of absence.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        # Anything else is an unverifiable read; do not call it absence.
        return True
    return True


def monitor_marker_state(value: str) -> str:
    """Classify a `@aitask_monitor_kind` value.

    ============================================  ============
    Condition                                     Result
    ============================================  ============
    ``""``                                        ``"absent"``
    parseable, process exists                     ``"present"``
    parseable, process gone                       ``"stale"``
    non-empty but NOT parseable                   ``"present"``
    ============================================  ============

    **Unverifiable is not absence** — the same principle as the staleness fix
    this task ships alongside. "Not parseable" covers an unknown kind
    (``garbage:123``), a missing pid (``minimonitor``), a non-numeric pid, and
    extra fields (``minimonitor:1:2``). Every one of those classifies as
    ``present`` and must never be cleared: clearing a marker we do not
    understand would silently delete another tool's state.

    Only ``"stale"`` licenses a caller to clear the option. Pid reuse is
    possible in principle; its consequence is a guard that declines to launch a
    second monitor, which is the safe direction.
    """
    if not value:
        return STATE_ABSENT
    parsed = parse_monitor_marker(value)
    if parsed is None:
        return STATE_PRESENT  # cannot verify -> assume a monitor is there
    _kind, pid = parsed
    return STATE_PRESENT if _process_exists(pid) else STATE_STALE


def monitor_marker_alive(value: str) -> bool:
    """The guards' predicate: does this value mean a monitor is running here?"""
    return monitor_marker_state(value) == STATE_PRESENT


def main(argv: list[str]) -> int:
    """CLI: ``monitor_marker.py state <value>`` -> exit code, nothing printed.

    Exit status IS the verdict, so no caller can mistake detection output for a
    decision. Every failure path returns :data:`EXIT_PRESENT`: an unclassified
    marker is "present", and the contract must not rest on the caller's mapping
    alone.

    No ``argparse``: the value is read as a bare positional, so a marker
    beginning with ``-`` is classified rather than parsed as an option (an
    argparse usage error would exit 2 — a *verdict-shaped* status — and would
    also mean parsing untrusted pane state).
    """
    try:
        if len(argv) != 3 or argv[1] != "state":
            return EXIT_PRESENT  # usage error -> unverifiable -> block
        return _STATE_EXIT[monitor_marker_state(argv[2])]
    except Exception:
        return EXIT_PRESENT  # internal failure -> unverifiable -> block


if __name__ == "__main__":
    sys.exit(main(sys.argv))
