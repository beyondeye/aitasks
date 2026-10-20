"""minimonitor `_find_sibling_pane_id` never hands `tab` / `enter` to a helper (t1388).

`tab` focuses, and `enter` types into, the pane `_find_sibling_pane_id`
returns. It resolves in two rungs:

1. the followed-pane snapshot (`_find_own_window_snapshot`);
2. when no snapshot resolves, a raw `list-panes` of the own window.

Rung 2 used to take the first pane that was not the minimonitor itself, so a
shadow — or now a scratchpad — sharing the window could receive the Enter
keystroke. It now classifies the window with `monitor_core.classify_window_panes`,
the one helper rule, which also carries the frozen-first precedence: a frozen
stand-in carrying a retained helper marker is still the agent.

Covered here:

* rung 2 driven directly (rung 1 forced to ``None``) through a format-driven
  tmux stub, so the rows always follow the format production requests;
* frozen precedence at rung 2;
* discovery → rung 1 end to end, because discovery keeps a frozen stand-in that
  carries a retained scratchpad target, and rung 1 must resolve to it;
* negative controls proving each fixture discriminates.

Run: python3 tests/test_minimonitor_sibling_fallback.py
"""

from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

# Nothing here may touch the pane the suite runs in (t1240).
os.environ.pop("TMUX", None)

import monitor.minimonitor_app as mm  # noqa: E402
from monitor.monitor_core import PaneSnapshot, TmuxMonitor  # noqa: E402

MM_PANE = "%10"        # this minimonitor
HELPER = "%11"         # a shadow / scratchpad / second minimonitor / stand-in
AGENT = "%12"          # the followed agent
WINDOW = "@3"
FROZEN = "7f3a2c1d"
#: A LIVE companion marker: `monitor_marker_alive` checks the recorded pid with
#: `os.kill(pid, 0)`, and this process is certainly alive.
LIVE_MARKER = f"minimonitor:{os.getpid()}"


def _pane(pane_id: str, pid: int, **opts: str) -> dict[str, str]:
    """One pane of the model. Keys are the `#{...}` names without the braces."""
    return {"pane_id": pane_id, "pane_pid": str(pid), "pane_dead": "0",
            "window_index": "1", "window_name": "agent-pick-42",
            "pane_index": pane_id.lstrip("%"), "pane_current_command": "node",
            "pane_width": "80", "pane_height": "24", "history_size": "0",
            **opts}


class _FormatDrivenMonitor:
    """`tmux_run` answering `list-panes -F <fmt>` from a pane model.

    Each requested `#{spec}` is rendered from the model (missing → ""), so the
    rows follow whatever format production asks for — a fixture that hard-coded
    a tab count would silently drift out of step with it.
    """

    def __init__(self, panes: list[dict[str, str]]):
        self.panes = panes
        self.calls: list[list[str]] = []

    def tmux_run(self, args, timeout=None):
        self.calls.append(list(args))
        if args[0] != "list-panes":
            return 1, ""
        fmt = args[args.index("-F") + 1]
        rows = ["\t".join(p.get(spec.strip("#{}"), "") for spec in fmt.split("\t"))
                for p in self.panes]
        return 0, "\n".join(rows) + "\n"


def _app(monitor, snapshots=None) -> "mm.MiniMonitorApp":
    app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
    app._monitor = monitor
    app._own_window_id = WINDOW
    app._own_window_index = "1"
    app._session = "demo"
    app._snapshots = snapshots if snapshots is not None else {}
    app.notes = []
    app.notify = lambda msg, **kw: app.notes.append(msg)
    return app


def _no_cmdline_companions():
    """Fake pids must not reach the real /proc cmdline rung."""
    return patch("monitor.monitor_core._is_companion_process", lambda pid: False)


def _rung2(panes, *, blank_frozen: bool = False):
    """Drive rung 2 directly: rung 1 forced to `None`."""
    if blank_frozen:
        panes = [{**p, "@aitask_frozen": ""} for p in panes]
    app = _app(_FormatDrivenMonitor(panes))
    app._find_own_window_snapshot = lambda: None
    with patch.dict(os.environ, {"TMUX_PANE": MM_PANE}), _no_cmdline_companions():
        return app._find_sibling_pane_id(), app


def _pre_fix_rung2(panes) -> str | None:
    """The unfiltered rule t1388 removed: the first pane that is not me."""
    others = [p["pane_id"] for p in panes if p["pane_id"] != MM_PANE]
    return others[0] if others else None


def _window(helper_opts: dict[str, str]) -> list[dict[str, str]]:
    """`[minimonitor, <helper>, agent]` — the helper is listed BEFORE the agent."""
    return [
        _pane(MM_PANE, 100, **{"@aitask_monitor_kind": LIVE_MARKER}),
        _pane(HELPER, 101, **helper_opts),
        _pane(AGENT, 102),
    ]


SHADOW = {"@aitask_shadow_target": AGENT}
SCRATCHPAD = {"@aitask_scratchpad_target": AGENT}
SECOND_MINIMONITOR = {"@aitask_monitor_kind": LIVE_MARKER}


class Rung2HelperFilterTests(unittest.TestCase):
    """AC: rung 2 skips bound helpers and companions (t1388)."""

    def test_shadow_is_skipped(self):
        found, _app_ = _rung2(_window(SHADOW))
        self.assertEqual(found, AGENT)

    def test_scratchpad_is_skipped(self):
        found, _app_ = _rung2(_window(SCRATCHPAD))
        self.assertEqual(found, AGENT)

    def test_second_minimonitor_is_skipped(self):
        """Decision (t1388): companions ARE filtered at rung 2."""
        found, _app_ = _rung2(_window(SECOND_MINIMONITOR))
        self.assertEqual(found, AGENT)

    def test_negative_control_the_pre_fix_rule_picks_the_helper(self):
        """Each fixture discriminates: the old rule returns the helper, not the agent."""
        for opts in (SHADOW, SCRATCHPAD, SECOND_MINIMONITOR):
            with self.subTest(helper=opts):
                self.assertEqual(_pre_fix_rung2(_window(opts)), HELPER)

    def test_requests_the_shared_classifier_format(self):
        _found, app = _rung2(_window(SCRATCHPAD))
        (call,) = app._monitor.calls
        self.assertEqual(call[:3], ["list-panes", "-t", WINDOW])
        self.assertEqual(call[call.index("-F") + 1],
                         mm.FROZEN_AWARE_PANE_FORMAT)

    def test_agent_as_the_last_record_with_empty_trailing_fields(self):
        """The record most easily lost to a whole-buffer `strip()`."""
        found, _app_ = _rung2(_window(SHADOW))
        stdout = _FormatDrivenMonitor(_window(SHADOW)).tmux_run(
            ["list-panes", "-F", mm.FROZEN_AWARE_PANE_FORMAT])[1]
        self.assertTrue(stdout.endswith("\t\n"),
                        "precondition: the agent's last field must be empty")
        self.assertEqual(found, AGENT)

    def test_helpers_only_returns_none_and_says_so(self):
        panes = [_pane(MM_PANE, 100, **{"@aitask_monitor_kind": LIVE_MARKER}),
                 _pane(HELPER, 101, **SCRATCHPAD)]
        found, app = _rung2(panes)
        self.assertIsNone(found)
        self.assertEqual(app.notes, ["No agent pane in this window"])


class Rung2FrozenPrecedenceTests(unittest.TestCase):
    """A frozen stand-in with a retained helper marker is the agent, at rung 2."""

    FROZEN_COMPANION_MARKED = {"@aitask_frozen": FROZEN,
                               "@aitask_monitor_kind": LIVE_MARKER}
    FROZEN_SCRATCH = {"@aitask_frozen": FROZEN,
                      "@aitask_scratchpad_target": AGENT}

    def test_frozen_standin_is_selected_over_the_later_agent(self):
        for opts in (self.FROZEN_COMPANION_MARKED, self.FROZEN_SCRATCH):
            with self.subTest(standin=opts):
                found, _app_ = _rung2(_window(opts))
                self.assertEqual(found, HELPER,
                                 "the frozen stand-in is the first non-helper")

    def test_negative_control_a_frozen_blind_filter_skips_the_standin(self):
        """With the frozen field blanked the same rows ARE helpers — the fixture discriminates."""
        for opts in (self.FROZEN_COMPANION_MARKED, self.FROZEN_SCRATCH):
            with self.subTest(standin=opts):
                found, _app_ = _rung2(_window(opts), blank_frozen=True)
                self.assertEqual(found, AGENT)


def _discovery_row(p: dict[str, str]) -> str:
    return "\t".join(p.get(spec.strip("#{}"), "")
                     for spec in TmuxMonitor._LIST_PANES_FORMAT.split("\t"))


def _snapshots_from_discovery(panes) -> dict:
    """Real discovery → `_snapshots`, in discovery order (what rung 1 reads)."""
    mon = TmuxMonitor(session="demo", multi_session=False,
                      agent_prefixes=["agent-"], exclude_pane=MM_PANE)
    stdout = "\n".join(_discovery_row(p) for p in panes) + "\n"
    with _no_cmdline_companions():
        found, _shadows = mon._parse_list_panes(stdout, "demo")
    now = time.monotonic()
    return {p.pane_id: PaneSnapshot(pane=p, content="", timestamp=now,
                                    idle_seconds=0.0, is_idle=False)
            for p in found}


def _rung1_end_to_end(panes) -> str | None:
    """Discovery → snapshots → the REAL `_find_sibling_pane_id` (rung 1 live).

    The monitor stub answers nothing, so a result can only come from rung 1.
    """
    app = _app(_FormatDrivenMonitor([]), _snapshots_from_discovery(panes))
    with patch.dict(os.environ, {"TMUX_PANE": MM_PANE}), _no_cmdline_companions():
        return app._find_sibling_pane_id()


class DiscoveryToRung1Tests(unittest.TestCase):
    """The frozen + scratchpad pane survives discovery, so rung 1 resolves to it."""

    def test_frozen_standin_with_a_scratchpad_target_is_followed(self):
        found = _rung1_end_to_end(_window({"@aitask_frozen": FROZEN,
                                           "@aitask_scratchpad_target": AGENT}))
        self.assertEqual(found, HELPER,
                         "discovery must keep the stand-in, so rung 1 follows it "
                         "rather than the later agent")

    def test_an_ordinary_scratchpad_is_still_excluded(self):
        self.assertEqual(_rung1_end_to_end(_window(SCRATCHPAD)), AGENT)

    def test_negative_control_without_the_stamp_the_later_agent_wins(self):
        found = _rung1_end_to_end(_window({"@aitask_frozen": "",
                                           "@aitask_scratchpad_target": AGENT}))
        self.assertEqual(found, AGENT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
