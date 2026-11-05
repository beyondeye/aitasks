"""`TmuxMonitor` producer seams for the shared status server (t2037_1).

The status server owns ONE producer for every aitasks session on a tmux server,
so the producer grows three additive seams:

- per-session ``tmux.monitor`` config (``set_session_configs``), read by
  ``classify_pane`` / the idle verdict / ``_capture_args`` / ``get_compare_mode``;
- ``%exit`` visibility (``TmuxControlClient.saw_exit`` → backend
  ``exit_seen`` → ``TmuxMonitor.control_exit_seen``);
- the public ``shadow_snapshots()`` accessor.

``NoConfigCharacterization`` is the risk-mitigation pre-phase
``pin_producer_defaults``: written and run green BEFORE the seams existed, and
kept unedited after. It pins today's no-config outputs as LITERALS — never
computed from the instance attributes the seams fall back to, which would make
the pin agree with any fallback, right or wrong. Every in-process client
(monitor, minimonitor, applink) publishes no session config, so these outputs
are exactly what they see.

Run:
  python3 tests/test_monitor_producer_seams.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "lib"))

# The suite may run inside a live agent pane: no ambient pane id may leak in.
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from monitor.monitor_core import (  # noqa: E402
    ClassifyResult, PaneCategory, PaneSnapshot, TmuxMonitor, TmuxPaneInfo,
)


def pane(pane_id: str, *, session: str = "s1", window: str = "agent-pick-1",
         category: PaneCategory = PaneCategory.AGENT,
         shadow_target: str = "") -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index="1", window_name=window, pane_index="0", pane_id=pane_id,
        pane_pid=4242, current_command="node", width=80, height=24,
        category=category, session_name=session, shadow_target=shadow_target,
    )


def idle_verdict(monitor: TmuxMonitor, p: TmuxPaneInfo, age: float) -> bool:
    """`is_idle` for a pane whose content last changed `age` seconds ago."""
    result = ClassifyResult(compare_value="same")
    now = time.monotonic()
    monitor._last_content[p.pane_id] = "same"
    monitor._last_change_time[p.pane_id] = now - age
    return monitor._apply_bookkeeping(p, "same", result, now).is_idle


class NoConfigCharacterization(unittest.TestCase):
    """[pin_producer_defaults] Today's outputs with no session config published.

    Two monitors: the constructor defaults, and one built with non-default
    values (``compare_mode_default="raw"``, ``idle_threshold=2.0``,
    ``capture_lines=77``) so a fallback that read the wrong source would show.
    """

    def setUp(self):
        self.default = TmuxMonitor(session="s1")
        self.custom = TmuxMonitor(session="s1", compare_mode_default="raw",
                                  idle_threshold=2.0, capture_lines=77)

    # -- classify_pane ------------------------------------------------------

    def test_classify_pane(self):
        for monitor in (self.default, self.custom):
            self.assertEqual(monitor.classify_pane("agent-pick-1"), PaneCategory.AGENT)
            self.assertEqual(monitor.classify_pane("board"), PaneCategory.TUI)
            self.assertEqual(monitor.classify_pane("brainstorm-42"), PaneCategory.TUI)
            self.assertEqual(monitor.classify_pane("zsh"), PaneCategory.OTHER)
            self.assertEqual(monitor.classify_pane("work-x"), PaneCategory.OTHER)

    # -- idle verdict -------------------------------------------------------

    def test_idle_verdict_default_threshold(self):
        agent = pane("%1")
        self.assertFalse(idle_verdict(self.default, agent, 4.5))
        self.assertTrue(idle_verdict(self.default, agent, 5.5))

    def test_idle_verdict_custom_threshold(self):
        agent = pane("%1")
        self.assertFalse(idle_verdict(self.custom, agent, 1.5))
        self.assertTrue(idle_verdict(self.custom, agent, 2.5))

    def test_idle_verdict_non_agent_is_never_idle(self):
        other = pane("%2", window="zsh", category=PaneCategory.OTHER)
        for monitor in (self.default, self.custom):
            self.assertFalse(idle_verdict(monitor, other, 100.0))

    def test_idle_verdict_empty_session(self):
        agent = pane("%3", session="")
        self.assertFalse(idle_verdict(self.custom, agent, 1.5))
        self.assertTrue(idle_verdict(self.custom, agent, 2.5))

    # -- capture args -------------------------------------------------------

    def test_capture_args(self):
        self.assertEqual(self.default._capture_args("%1"),
                         ["capture-pane", "-p", "-e", "-t", "%1", "-S", "-200"])
        self.assertEqual(self.custom._capture_args("%1"),
                         ["capture-pane", "-p", "-e", "-t", "%1", "-S", "-77"])
        self.assertEqual(self.default._capture_args("%1", 50),
                         ["capture-pane", "-p", "-e", "-t", "%1", "-S", "-50"])
        self.assertEqual(self.custom._capture_args("%1", 50),
                         ["capture-pane", "-p", "-e", "-t", "%1", "-S", "-50"])

    # -- compare mode -------------------------------------------------------

    def test_compare_mode_cached_agent_pane(self):
        for monitor, expected in ((self.default, "stripped"), (self.custom, "raw")):
            monitor._pane_cache["%1"] = pane("%1")
            self.assertEqual(monitor.get_compare_mode("%1"), expected)

    def test_compare_mode_shadow_pane(self):
        # Shadow panes are never in `_pane_cache` (cache-boundary invariant).
        for monitor, expected in ((self.default, "stripped"), (self.custom, "raw")):
            self.assertEqual(monitor.get_compare_mode("%9"), expected)

    def test_compare_mode_empty_session_pane(self):
        for monitor, expected in ((self.default, "stripped"), (self.custom, "raw")):
            monitor._pane_cache["%4"] = pane("%4", session="")
            self.assertEqual(monitor.get_compare_mode("%4"), expected)

    def test_compare_mode_undiscovered_pane(self):
        for monitor, expected in ((self.default, "stripped"), (self.custom, "raw")):
            self.assertEqual(monitor.get_compare_mode("%777"), expected)

    def test_compare_mode_override(self):
        self.default._pane_cache["%5"] = pane("%5")
        self.assertEqual(self.default.set_compare_mode("%5", "raw"), "raw")
        self.assertEqual(self.default.get_compare_mode("%5"), "raw")
        self.assertTrue(self.default.is_compare_mode_overridden("%5"))
        self.assertEqual(self.custom.set_compare_mode("%5", "stripped"), "stripped")
        self.assertEqual(self.custom.get_compare_mode("%5"), "stripped")
        self.assertEqual(self.custom.set_compare_mode("%5", None), "raw")
        self.assertFalse(self.custom.is_compare_mode_overridden("%5"))


class PerSessionConfigTests(unittest.TestCase):
    """Published per-session config reaches every seam; other sessions keep
    the instance values."""

    def setUp(self):
        self.mon = TmuxMonitor(session="sa")
        self.mon.set_session_configs({
            "sa": {"idle_threshold": 1.0, "agent_prefixes": ["agent-", "work-"],
                   "capture_lines": 33, "compare_mode_default": "raw",
                   "tui_names": {"mytui"}},
        })

    def test_idle_threshold_per_session(self):
        a, b = pane("%1", session="sa"), pane("%2", session="sb")
        self.assertTrue(idle_verdict(self.mon, a, 1.5))
        self.assertFalse(idle_verdict(self.mon, b, 1.5))

    def test_agent_prefixes_and_tui_names_per_session(self):
        self.assertEqual(self.mon.classify_pane("work-x", "sa"), PaneCategory.AGENT)
        self.assertEqual(self.mon.classify_pane("work-x", "sb"), PaneCategory.OTHER)
        self.assertEqual(self.mon.classify_pane("work-x"), PaneCategory.OTHER)
        self.assertEqual(self.mon.classify_pane("mytui", "sa"), PaneCategory.TUI)
        self.assertEqual(self.mon.classify_pane("board", "sa"), PaneCategory.OTHER,
                         "a session's tui_names replace the instance set")

    def test_capture_lines_per_session(self):
        self.assertEqual(self.mon._capture_args("%1", session_name="sa")[-1], "-33")
        self.assertEqual(self.mon._capture_args("%1", session_name="sb")[-1], "-200")
        self.assertEqual(self.mon._capture_args("%1", 9, session_name="sa")[-1], "-9")

    def test_capture_routes_pass_the_pane_session(self):
        seen = []

        async def tmux(args, timeout=5.0):
            seen.append(args[-1])
            return 0, "x"
        self.mon._tmux_async = tmux
        shadow = pane("%12", session="sa", shadow_target="%1")
        asyncio.run(self.mon.capture_pane_content_async("%12", pane=shadow))
        self.mon._pane_cache["%3"] = pane("%3", session="sb")
        asyncio.run(self.mon.capture_pane_content_async("%3"))
        self.assertEqual(seen, ["-33", "-200"])

    def test_compare_default_follows_the_pane_session_shadows_included(self):
        lines = [
            "\t".join(["1", "agent-a", "0", "%1", "999991", "node", "80", "24",
                       "", "10", "", "", "", "", "0", ""]),
            "\t".join(["1", "agent-a", "1", "%12", "999992", "node", "80", "24",
                       "%1", "10", "", "", "", "", "0", ""]),
        ]
        panes, shadows = self.mon._parse_list_panes("\n".join(lines) + "\n", "sa")
        self.assertEqual([p.pane_id for p in shadows], ["%12"])
        self.assertNotIn("%12", self.mon._pane_cache)
        self.assertEqual(self.mon.get_compare_mode("%1"), "raw")
        self.assertEqual(self.mon.get_compare_mode("%12"), "raw")
        self.mon._parse_list_panes(lines[0].replace("%1", "%5") + "\n", "sb")
        self.assertEqual(self.mon.get_compare_mode("%5"), "stripped")

    def test_pane_sessions_reaped_with_discovery(self):
        self.mon._pane_sessions.update({"%1": "sa", "%2": "sa"})
        self.mon._clean_stale({"%1"})
        self.assertEqual(self.mon._pane_sessions, {"%1": "sa"})

    def test_publish_rebinds(self):
        held = self.mon._session_configs
        self.mon.set_session_configs({})
        self.assertIn("sa", held, "set_session_configs mutated the previous map")


class ExitAndAccessorTests(unittest.TestCase):

    def test_control_client_sets_saw_exit_on_exit_line(self):
        from monitor.monitor_core import TmuxControlClient

        async def run():
            client = TmuxControlClient(session="x", socket_args=[])
            reader = asyncio.StreamReader()
            reader.feed_data(b"%begin 1 1 0\n%end 1 1 0\n%exit server exited\n")
            reader.feed_eof()
            client._proc = type("P", (), {"stdout": reader})()
            client._alive = True
            await client._reader_loop()
            return client
        client = asyncio.run(run())
        self.assertTrue(client.saw_exit)
        self.assertFalse(client.is_alive)

    def test_control_client_without_exit_line(self):
        from monitor.monitor_core import TmuxControlClient

        async def run():
            client = TmuxControlClient(session="x", socket_args=[])
            reader = asyncio.StreamReader()
            reader.feed_data(b"%sessions-changed\n")
            reader.feed_eof()
            client._proc = type("P", (), {"stdout": reader})()
            await client._reader_loop()
            return client
        self.assertFalse(asyncio.run(run()).saw_exit)

    def test_control_exit_seen_without_backend(self):
        self.assertFalse(TmuxMonitor(session="s1").control_exit_seen())

    def test_backend_exit_seen_reads_the_current_client(self):
        from monitor.monitor_core import TmuxControlBackend
        backend = TmuxControlBackend(session="x", socket_args=[])
        self.assertFalse(backend.exit_seen)
        backend._client = type("C", (), {"saw_exit": True, "is_alive": False})()
        self.assertTrue(backend.exit_seen)
        mon = TmuxMonitor(session="s1")
        mon._backend = backend
        self.assertTrue(mon.control_exit_seen())

    def test_shadow_snapshots_returns_a_copy(self):
        mon = TmuxMonitor(session="s1")
        s = PaneSnapshot(pane=pane("%12", shadow_target="%1"), content="x",
                         timestamp=0.0, idle_seconds=0.0, is_idle=False)
        mon._shadow_snapshots = {"%1": s}
        copy = mon.shadow_snapshots()
        copy.clear()
        self.assertEqual(mon.shadow_snapshots(), {"%1": s})

    def test_is_task_completed_is_shared(self):
        from monitor import monitor_core, monitor_shared
        self.assertIs(monitor_shared.is_task_completed, monitor_core.is_task_completed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
