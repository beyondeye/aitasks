"""Action-contract tests for the prioritized-agent mark (t1326).

Bindings and glyphs passing is not enough: a wrong-root write or a dead
notification path would sail through a render-only suite while silently filing
one repo's agent under another repo's root. This module pins the seam itself —
the exact argv handed to the locked writer, and each of the four outcomes.

Both apps are covered. They have independent root-resolution and refresh paths,
so covering one does not cover the other.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

import agent_marks  # noqa: E402
from monitor.minimonitor_app import MiniMonitorApp  # noqa: E402
from monitor.monitor_app import MonitorApp  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    PaneCategory, PaneSnapshot, TmuxPaneInfo,
)

SESSION = "demo"
OTHER_SESSION = "other"

BOTH_APPS = (MiniMonitorApp, MonitorApp)


def pane(window, *, session=SESSION, pane_id="%1",
         category=PaneCategory.AGENT) -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index="1", window_name=window, pane_index="0", pane_id=pane_id,
        pane_pid=4242, current_command="node", width=80, height=24,
        category=category, session_name=session,
    )


def snapshot(window, **kw) -> PaneSnapshot:
    return PaneSnapshot(
        pane=pane(window, **kw), content="x", timestamp=0.0,
        idle_seconds=1.0, is_idle=False,
    )


class _FakeMonitor:
    """Publishes the discovery-derived liveness facts the purge reads.

    Deliberately independent of any snapshot set: the real monitor records these
    at DISCOVERY time, so a pane whose content capture failed is still present.
    """

    multi_session = True

    def __init__(self, mapping, *, sessions=None, agents=None):
        self._mapping = mapping
        self._sessions = frozenset(sessions or ())
        self._agents = frozenset(agents or ())

    def get_session_to_project_mapping(self): return self._mapping
    def last_enumerated_sessions(self): return self._sessions
    def last_discovered_agents(self): return self._agents


class _ActionFixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.store = self.tmp / "marks.json"
        self.here = self.tmp / "here"
        self.there = self.tmp / "there"
        self.here.mkdir()
        self.there.mkdir()

    def app(self, cls, *, focused="%1", snaps=None, mapping=None, reply=(0, ""),
            sessions=None, agents=None):
        app = cls.__new__(cls)
        app._project_root = self.here
        app._monitor = _FakeMonitor(
            mapping if mapping is not None
            else {SESSION: self.here, OTHER_SESSION: self.there},
            sessions=sessions, agents=agents,
        )
        app._snapshots = snaps if snaps is not None else {"%1": snapshot("agent-t1")}
        app._marks_view = agent_marks.MarksView(self.store)
        app._marks_purge_due_at = 0.0
        app._marks_purge_inflight = False
        app._set_session_root_map(app._monitor.get_session_to_project_mapping())
        app._refresh_marks()

        app.calls: list[list[str]] = []
        app.notes: list[tuple[str, str]] = []
        app.later: list = []
        app._get_focused_pane_id = lambda: focused
        app.notify = lambda msg, **kw: app.notes.append(
            (msg, kw.get("severity", "information"))
        )
        app.call_later = lambda fn, *a: app.later.append(fn)
        app._refresh_data = lambda: None

        async def fake_cmd(args):
            app.calls.append(list(args))
            return reply

        app._run_marks_cmd = fake_cmd
        return app

    @staticmethod
    def run_toggle(app):
        asyncio.run(app.action_toggle_mark())


class ArgvContractTests(_ActionFixture):
    """The rendered command shape is the contract — assert it token by token,
    never by substring, so a quoting or ordering change cannot slip through."""

    def test_exact_argv_for_the_focused_agent(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                app = self.app(cls, reply=(0, "MARKED:x|y"))
                self.run_toggle(app)
                self.assertEqual(len(app.calls), 1)
                self.assertEqual(
                    app.calls[0],
                    ["toggle", os.path.realpath(self.here), "agent-t1"],
                )

    def test_cross_session_card_resolves_its_OWN_root(self):
        """The bug this exists to catch: `_root_for_snap` would fall back to
        `self._project_root` and file the other repo's agent under this one."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                snaps = {"%9": snapshot("agent-far", session=OTHER_SESSION,
                                        pane_id="%9")}
                app = self.app(cls, focused="%9", snaps=snaps,
                               reply=(0, "MARKED:x|y"))
                self.run_toggle(app)
                self.assertEqual(
                    app.calls[0],
                    ["toggle", os.path.realpath(self.there), "agent-far"],
                )
                self.assertNotEqual(app.calls[0][1], os.path.realpath(self.here))

    def test_root_is_canonicalized(self):
        link = self.tmp / "link_to_here"
        try:
            link.symlink_to(self.here)
        except (OSError, NotImplementedError):  # pragma: no cover
            self.skipTest("symlinks unavailable")
        app = self.app(MiniMonitorApp, mapping={SESSION: link},
                       reply=(0, "MARKED:x|y"))
        self.run_toggle(app)
        self.assertEqual(app.calls[0][1], os.path.realpath(self.here))


class GuardTests(_ActionFixture):
    def test_no_focused_card_is_a_silent_no_op(self):
        """Silent, not a warning: with a modal up this fires on every `space`,
        and a toast behind the dialog would be noise."""
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                app = self.app(cls, focused=None)
                self.run_toggle(app)
                self.assertEqual(app.calls, [])
                self.assertEqual(app.notes, [])

    def test_focused_pane_absent_from_snapshots_is_a_no_op(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                app = self.app(cls, focused="%missing")
                self.run_toggle(app)
                self.assertEqual(app.calls, [])

    def test_unresolvable_session_warns_and_never_invokes_the_writer(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                app = self.app(cls, mapping={})
                self.run_toggle(app)
                self.assertEqual(app.calls, [], "must not write under a guessed root")
                self.assertEqual(len(app.notes), 1)
                self.assertEqual(app.notes[0][1], "warning")
                self.assertIn("resolve", app.notes[0][0].lower())


class OutcomeTests(_ActionFixture):
    def test_marked_notifies_and_schedules_a_repaint(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                app = self.app(cls, reply=(0, "MARKED:/r|agent-t1"))
                self.run_toggle(app)
                self.assertEqual(app.notes[0][1], "information")
                self.assertIn("agent-t1", app.notes[0][0])
                self.assertEqual(len(app.later), 1, "must schedule a repaint")

    def test_unmarked_notifies_and_schedules_a_repaint(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                app = self.app(cls, reply=(0, "UNMARKED:/r|agent-t1"))
                self.run_toggle(app)
                self.assertIn("Unmarked", app.notes[0][0])
                self.assertEqual(len(app.later), 1)

    def test_lock_busy_warns_and_changes_nothing(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                app = self.app(cls, reply=(3, "LOCK_BUSY"))
                self.run_toggle(app)
                self.assertEqual(app.notes[0][1], "warning")
                self.assertIn("busy", app.notes[0][0].lower())
                self.assertEqual(app.later, [], "must not repaint on a failed write")

    def test_error_reports_and_changes_nothing(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                app = self.app(cls, reply=(4, "ERROR:store is corrupt"))
                self.run_toggle(app)
                self.assertEqual(app.notes[0][1], "error")
                self.assertEqual(app.later, [])

    def test_unexpected_output_is_treated_as_a_failure(self):
        for cls in BOTH_APPS:
            with self.subTest(app=cls.__name__):
                app = self.app(cls, reply=(0, "surprise"))
                self.run_toggle(app)
                self.assertEqual(app.notes[0][1], "error")
                self.assertEqual(app.later, [])


class ObservationTests(_ActionFixture):
    """`_collect_marks_observation` is what makes the purge fail-closed.

    Its inputs come from DISCOVERY, never from the committed snapshots —
    `commit_snapshots` drops panes whose content capture failed, so a snapshot
    -derived agent set would read a transient capture failure as a departed
    agent and delete a live mark.
    """

    def test_enumerated_session_with_no_agents_is_sweepable_and_empty(self):
        """The case that must purge promptly: session up, every agent gone."""
        app = self.app(MiniMonitorApp, sessions={SESSION}, agents=())
        observed, sweepable, complete = app._collect_marks_observation()
        self.assertEqual(sweepable, {os.path.realpath(self.here)})
        self.assertEqual(observed, {os.path.realpath(self.here): set()})
        self.assertTrue(complete)

    def test_discovered_agents_are_recorded_per_root(self):
        app = self.app(
            MiniMonitorApp,
            sessions={SESSION, OTHER_SESSION},
            agents={(SESSION, "agent-a"), (SESSION, "agent-b"),
                    (OTHER_SESSION, "agent-c")},
        )
        observed, sweepable, complete = app._collect_marks_observation()
        self.assertEqual(
            observed[os.path.realpath(self.here)], {"agent-a", "agent-b"}
        )
        self.assertEqual(observed[os.path.realpath(self.there)], {"agent-c"})
        self.assertEqual(len(sweepable), 2)
        self.assertTrue(complete)

    def test_agent_whose_capture_failed_is_still_observed(self):
        """THE regression this rework exists for.

        `agent-flaky` produced no snapshot this tick because its content capture
        failed, but discovery still listed it. It must appear in `observed`, or
        its sibling would keep the root sweepable while it looked departed — and
        its live mark would be deleted.
        """
        app = self.app(
            MiniMonitorApp,
            sessions={SESSION},
            agents={(SESSION, "agent-ok"), (SESSION, "agent-flaky")},
            snaps={"%1": snapshot("agent-ok")},   # only one snapshot committed
        )
        observed, sweepable, _ = app._collect_marks_observation()
        self.assertEqual(
            observed[os.path.realpath(self.here)], {"agent-ok", "agent-flaky"},
            "an agent whose capture failed must not look departed",
        )
        self.assertEqual(sweepable, {os.path.realpath(self.here)})

    def test_unenumerated_session_is_not_sweepable(self):
        app = self.app(MiniMonitorApp, sessions=set(), agents=())
        observed, sweepable, complete = app._collect_marks_observation()
        self.assertEqual((observed, sweepable), ({}, set()))
        self.assertTrue(complete)

    def test_unattributable_agent_marks_the_tick_incomplete(self):
        app = self.app(
            MiniMonitorApp,
            sessions={SESSION},
            agents={(SESSION, "agent-a"), ("unmapped", "agent-lost")},
        )
        _, _, complete = app._collect_marks_observation()
        self.assertFalse(
            complete, "an unattributable agent must suppress the sweep"
        )

    def test_unattributable_SESSION_does_not_suppress_the_sweep(self):
        """An enumerated session with no project mapping carries no marks, so it
        is simply not sweepable — not a visibility gap."""
        app = self.app(
            MiniMonitorApp,
            sessions={SESSION, "unmapped"},
            agents={(SESSION, "agent-a")},
        )
        _, sweepable, complete = app._collect_marks_observation()
        self.assertTrue(complete)
        self.assertEqual(sweepable, {os.path.realpath(self.here)})

    def test_monitor_without_discovery_facts_fails_closed(self):
        """A monitor that cannot report discovery facts gives no basis for
        concluding anything departed."""
        app = self.app(MiniMonitorApp)
        app._monitor = type("Bare", (), {
            "get_session_to_project_mapping": lambda s: {}
        })()
        observed, sweepable, complete = app._collect_marks_observation()
        self.assertEqual((observed, sweepable), ({}, set()))
        self.assertFalse(complete)

    def test_observation_file_round_trips_through_the_reader(self):
        app = self.app(
            MiniMonitorApp, sessions={SESSION}, agents={(SESSION, "agent-a")}
        )
        observed, sweepable, complete = app._collect_marks_observation()
        path = app._write_observation_file(observed, sweepable, complete)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        r_observed, r_roots, r_complete = agent_marks._read_observed(path)
        self.assertEqual(r_observed, {k: v for k, v in observed.items() if v})
        self.assertEqual(r_roots, sweepable)
        self.assertEqual(r_complete, complete)


class PurgeSchedulingTests(_ActionFixture):
    def test_first_tick_purges_then_backs_off(self):
        app = self.app(MiniMonitorApp)
        asyncio.run(app._maybe_purge_marks())
        self.assertEqual(len(app.calls), 1)
        self.assertEqual(app.calls[0][0], "purge")
        self.assertIn("--observed", app.calls[0])
        # Second immediate tick must be skipped by the due-time.
        asyncio.run(app._maybe_purge_marks())
        self.assertEqual(len(app.calls), 1)

    def test_inflight_run_is_never_stacked(self):
        app = self.app(MiniMonitorApp)
        app._marks_purge_inflight = True
        asyncio.run(app._maybe_purge_marks())
        self.assertEqual(app.calls, [])

    def test_inflight_flag_is_cleared_even_when_the_writer_raises(self):
        """A crashed or hung wrapper must not wedge the scheduler forever."""
        app = self.app(MiniMonitorApp)

        async def boom(args):
            raise RuntimeError("wrapper died")

        app._run_marks_cmd = boom
        asyncio.run(app._maybe_purge_marks())
        self.assertFalse(app._marks_purge_inflight)
        self.assertGreater(app._marks_purge_due_at, 0.0)

    def test_observation_temp_file_is_removed(self):
        app = self.app(MiniMonitorApp)
        seen: list[str] = []

        async def capture(args):
            seen.append(args[args.index("--observed") + 1])
            return (0, "PURGED:0")

        app._run_marks_cmd = capture
        asyncio.run(app._maybe_purge_marks())
        self.assertEqual(len(seen), 1)
        self.assertFalse(os.path.exists(seen[0]), "temp observation file leaked")


if __name__ == "__main__":
    unittest.main(verbosity=1)
