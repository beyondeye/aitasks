"""`kill_agent_pane_smart` retires the killed agent's bound helpers (t2088).

`kill-pane` / `kill-window` fire no `pane-died`, so `aitask_companion_cleanup.sh`
job 1 never runs when the monitor kills an agent directly. These tests drive
the REAL `kill_pane` / `kill_window` / `kill_agent_pane_smart` against an
in-memory server (`tests/lib/tmux_server_model.py`) that evaluates the guarded
`if-shell -F` dispatches, and pin:

* the pane branch kills the shadow and the pad bound to the killed agent, and
  leaves a pad bound to the surviving sibling and a frozen stand-in that
  retained a target;
* the window branch also kills a helper placed in ANOTHER window;
* both early fallbacks (cache miss, failed window listing) sweep too;
* a failed agent kill sweeps nothing;
* every helper kill is inside an `if-shell` branch, never a bare `kill-pane`.

The `drop_record` half lives in `tests/test_agent_freeze.py` (`DropVerbTests`),
next to the fixture that path already uses; the shared sweep itself and its
race tests in `tests/test_helper_panes.py`.

Run: python3 tests/test_kill_bound_helpers.py
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))

# Scrub the ambient tmux env so TmuxMonitor does not adopt this pane (t1240).
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from monitor.monitor_core import (  # noqa: E402
    FROZEN_OPTION,
    PaneCategory,
    SCRATCHPAD_TARGET_OPTION,
    SHADOW_TARGET_OPTION,
    TmuxMonitor,
    TmuxPaneInfo,
)
from tmux_server_model import TmuxServerModel  # noqa: E402

AGENT = "%1"


def _pane(pane_id, pid, window="7", **opts):
    return {"pane_id": pane_id, "pane_pid": str(pid), "window": window,
            "pane_dead": "0", **opts}


class KillAgentPaneSmartSweepTests(unittest.TestCase):

    def _run(self, panes, *, cached=True):
        model = TmuxServerModel(panes)
        mon = TmuxMonitor(session="demo", multi_session=False,
                          agent_prefixes=["agent-"], exclude_pane="")
        mon.tmux_run = model
        if cached:
            mon._pane_cache[AGENT] = TmuxPaneInfo(
                window_index="7", window_name="agent-pick-2088",
                pane_index="0", pane_id=AGENT, pane_pid=101,
                current_command="node", width=80, height=24,
                category=PaneCategory.AGENT, session_name="demo",
            )
        with patch("monitor.monitor_core._is_companion_process",
                   lambda pid: False):
            result = mon.kill_agent_pane_smart(AGENT)
        return model, result

    def _pane_branch_fixture(self):
        return {
            AGENT: _pane(AGENT, 101),
            "%2": _pane("%2", 202),                              # real sibling
            "%3": _pane("%3", 303, **{SHADOW_TARGET_OPTION: AGENT}),
            "%4": _pane("%4", 404, **{SCRATCHPAD_TARGET_OPTION: AGENT}),
            "%5": _pane("%5", 505, **{SCRATCHPAD_TARGET_OPTION: "%2"}),
            "%6": _pane("%6", 606, **{FROZEN_OPTION: "7f3a2c1d",
                                      SHADOW_TARGET_OPTION: AGENT}),
        }

    def test_pane_branch_kills_the_agent_s_helpers_only(self):
        model, (ok, killed_window) = self._run(self._pane_branch_fixture())
        self.assertTrue(ok)
        self.assertFalse(killed_window, "a real sibling keeps the window")
        self.assertEqual(sorted(model.panes), ["%2", "%5", "%6"],
                         "the sibling, its pad and the frozen stand-in stay")

    def test_negative_control_without_the_sweep_the_helpers_survive(self):
        """The fixture really exercises the sweep: stubbed out, nothing dies."""
        with patch.object(TmuxMonitor, "_kill_bound_helpers",
                          lambda self, pane_id: []):
            model, _ = self._run(self._pane_branch_fixture())
        self.assertIn("%3", model.panes)
        self.assertIn("%4", model.panes)

    def test_every_helper_kill_is_guarded(self):
        model, _ = self._run(self._pane_branch_fixture())
        guarded = [c for c in model.calls if c[0] == "if-shell"]
        self.assertEqual(len(guarded), 2)
        bare = [c for c in model.bare_kills() if c[-1] != AGENT]
        self.assertEqual(bare, [], "only the agent itself is killed bare")

    def test_window_branch_kills_a_helper_in_another_window(self):
        panes = {
            AGENT: _pane(AGENT, 101),
            "%3": _pane("%3", 303, window="9",
                        **{SHADOW_TARGET_OPTION: AGENT}),
            "%7": _pane("%7", 707, window="9"),
        }
        model, (ok, killed_window) = self._run(panes)
        self.assertTrue(ok)
        self.assertTrue(killed_window)
        self.assertEqual(sorted(model.panes), ["%7"])

    def test_cache_miss_fallback_also_sweeps(self):
        model, (ok, _) = self._run(self._pane_branch_fixture(), cached=False)
        self.assertTrue(ok)
        self.assertNotIn("%3", model.panes)
        self.assertNotIn("%4", model.panes)

    def test_failed_window_listing_fallback_also_sweeps(self):
        model = TmuxServerModel(self._pane_branch_fixture())
        real_list = model._list

        def list_fails_for_the_window(args):
            if "-a" not in args:
                return 1, ""
            return real_list(args)
        model._list = list_fails_for_the_window
        mon = TmuxMonitor(session="demo", multi_session=False,
                          agent_prefixes=["agent-"], exclude_pane="")
        mon.tmux_run = model
        mon._pane_cache[AGENT] = TmuxPaneInfo(
            window_index="7", window_name="agent-pick-2088", pane_index="0",
            pane_id=AGENT, pane_pid=101, current_command="node", width=80,
            height=24, category=PaneCategory.AGENT, session_name="demo",
        )
        ok, killed_window = mon.kill_agent_pane_smart(AGENT)
        self.assertTrue(ok)
        self.assertFalse(killed_window)
        self.assertNotIn("%3", model.panes)
        self.assertNotIn("%4", model.panes)

    def test_a_failed_agent_kill_sweeps_nothing(self):
        panes = self._pane_branch_fixture()
        model = TmuxServerModel(panes)
        model.kill_ok = False
        mon = TmuxMonitor(session="demo", multi_session=False,
                          agent_prefixes=["agent-"], exclude_pane="")
        mon.tmux_run = model
        ok, _ = mon.kill_agent_pane_smart(AGENT)
        self.assertFalse(ok)
        self.assertNotIn("if-shell", [c[0] for c in model.calls])
        self.assertEqual(
            [c for c in model.calls if c[0] == "list-panes" and "-a" in c], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
