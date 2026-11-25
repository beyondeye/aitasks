#!/usr/bin/env python3
"""The frozen-agent sitrep badge in `ait monitor` / `ait minimonitor` (t2337).

* the shared formatter is total over `frozen_sitrep.STATES`, and its width
  helper (the one width calculation) matches what it renders;
* a frozen row shows the badge only for a verdict bound to ITS frozen
  instance -- a reused record id on a new stand-in shows none;
* the badge shows IN PLACE OF the word `frozen` (t2354), and the row keeps its
  `F` prefix -- with a badge shown, the only frozen marker left;
* the minimonitor's name budget pays only the badge's width over the word's;
* the badge pass is ONE coalesced background worker: the refresh only kicks
  it, never awaits it, so a held badge read never delays a refresh (both
  TUIs, real `_refresh_data` under `App.run_test`);
* a failing pass leaves no badge.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from rich.cells import cell_len  # noqa: E402
from rich.text import Text  # noqa: E402

import agent_marks  # noqa: E402
import frozen_sitrep  # noqa: E402
from monitor.minimonitor_app import MiniMonitorApp  # noqa: E402
from monitor.monitor_app import MonitorApp  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    PaneCategory, PaneSnapshot, TmuxControlState, TmuxPaneInfo,
)
from monitor.monitor_shared import (  # noqa: E402
    FROZEN_SITREP_BADGES, format_frozen_prefix, format_frozen_sitrep_badge,
    format_frozen_state, frozen_state_width,
)

SESSION = "demo"
RID = "0123abcd"


def frozen_pane(window: str = "agent-pick-7", *, pane_id: str = "%3",
                pid: int = 100) -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index="1", window_name=window, pane_index="0", pane_id=pane_id,
        pane_pid=pid, current_command="bash", width=80, height=24,
        category=PaneCategory.AGENT, session_name=SESSION, frozen_record=RID,
    )


def frozen_snap(**kw) -> PaneSnapshot:
    return PaneSnapshot(pane=frozen_pane(**kw), content="", timestamp=0.0,
                        idle_seconds=0.0, is_idle=False, frozen=True,
                        frozen_record_id=RID)


def verdict(state: str, pane_id: str = "%3", pid: int = 100):
    return frozen_sitrep.FrozenSitrepState(state, instance=(RID, pane_id, pid))


class FormatterTests(unittest.TestCase):

    def test_the_table_is_total_over_the_states(self):
        self.assertEqual(set(frozen_sitrep.STATES), set(FROZEN_SITREP_BADGES))

    def test_the_width_matches_the_render(self):
        for state in (None, *frozen_sitrep.STATES):
            with self.subTest(state):
                plain = Text.from_markup(format_frozen_state(state)).plain
                self.assertEqual(cell_len(plain), frozen_state_width(state))
                self.assertFalse(plain.startswith(" "), repr(plain))
                self.assertTrue(plain.isascii())
                if state is None:
                    continue
                # The docked card's suffix: the same badge, one leading space.
                docked = Text.from_markup(format_frozen_sitrep_badge(state)).plain
                self.assertEqual(docked, " " + plain)
                self.assertEqual(cell_len(docked), 1 + frozen_state_width(state))

    def test_a_badge_replaces_the_frozen_word(self):
        for state in frozen_sitrep.STATES:
            with self.subTest(state):
                plain = Text.from_markup(format_frozen_state(state)).plain
                self.assertEqual(plain, "".join(
                    text for text, _style in FROZEN_SITREP_BADGES[state]))
                self.assertNotIn("frozen", plain)

    def test_drop_ok_only_for_safe_states(self):
        for state in frozen_sitrep.STATES:
            plain = Text.from_markup(format_frozen_sitrep_badge(state)).plain
            self.assertEqual("drop ok" in plain,
                             state in frozen_sitrep.SAFE_STATES, state)

    def test_none_renders_the_word(self):
        self.assertEqual("", format_frozen_sitrep_badge(None))
        self.assertEqual("frozen",
                         Text.from_markup(format_frozen_state(None)).plain)
        self.assertEqual(6, frozen_state_width(None))

    def test_an_unknown_key_raises(self):
        for fn in (format_frozen_sitrep_badge, format_frozen_state,
                   frozen_state_width):
            with self.subTest(fn.__name__), self.assertRaises(KeyError):
                fn("droppable")


class _FakeTaskCache:
    def get_task_id_for_pane(self, pane): return None
    def get_task_info(self, task_id, session=None): return None
    def update_session_mapping(self, mapping): pass


class _RowMonitor:
    multi_session = False

    def __init__(self, root): self._mapping = {SESSION: root}
    def get_session_to_project_mapping(self): return self._mapping
    def get_compare_mode(self, pane_id): return "stripped"
    def is_compare_mode_overridden(self, pane_id): return False
    def get_shadow_snapshot(self, pane_id): return None


class RowTests(unittest.TestCase):
    """Rows through the real card builders of an unmounted app."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def app(self, cls):
        app = cls.__new__(cls)
        app._monitor = _RowMonitor(self.root)
        app._completed_pane_ids = frozenset()
        app._task_cache = _FakeTaskCache()
        app._project_root = self.root
        app._has_fresh_concerns = lambda pane_id: False
        app._marks_view = agent_marks.MarksView(self.root / "marks.json")
        app._marks_purge_due_at = 0.0
        app._marks_purge_inflight = False
        app._set_session_root_map(app._monitor.get_session_to_project_mapping())
        app._refresh_marks()
        return app

    @staticmethod
    def row(app, snap) -> str:
        builder = (app._agent_card_text if isinstance(app, MiniMonitorApp)
                   else app._format_agent_card_text)
        return Text.from_markup(builder(snap)).plain

    def assert_badged_line(self, app, line: str, badge: str) -> None:
        """A badged row: the badge in place of `frozen`, and the `F` prefix
        still at the mark position -- the row's only frozen marker now."""
        self.assertTrue(line.endswith("  " + badge), line)
        self.assertNotIn("frozen", line)
        prefix = Text.from_markup(
            format_frozen_prefix(agent_marks.KIND_NONE)).plain + " "
        # Minimonitor rows start at the mark; `ait monitor` indents one space.
        lead = "" if isinstance(app, MiniMonitorApp) else " "
        self.assertTrue(line.startswith(lead + prefix), (prefix, line))

    def test_a_bound_verdict_renders_in_both_tuis(self):
        for cls in (MonitorApp, MiniMonitorApp):
            with self.subTest(cls.__name__):
                app = self.app(cls)
                app._frozen_sitrep_results = {
                    RID: verdict(frozen_sitrep.TRIAGE_OPEN)}
                line = self.row(app, frozen_snap()).split("\n")[0]
                self.assert_badged_line(app, line, "drop ok, triage")

    def test_no_result_renders_no_badge(self):
        for cls in (MonitorApp, MiniMonitorApp):
            with self.subTest(cls.__name__):
                app = self.app(cls)
                app._frozen_sitrep_results = {}
                plain = self.row(app, frozen_snap())
                self.assertIn("frozen", plain)
                self.assertNotIn("drop ok", plain)

    def test_a_bound_unknown_renders_sitrep_question_mark(self):
        for cls in (MonitorApp, MiniMonitorApp):
            with self.subTest(cls.__name__):
                app = self.app(cls)
                app._frozen_sitrep_results = {RID: verdict(frozen_sitrep.UNKNOWN)}
                plain = self.row(app, frozen_snap())
                self.assert_badged_line(app, plain.split("\n")[0], "sitrep ?")
                self.assertNotIn("drop ok", plain)

    def test_a_reused_record_id_on_a_new_standin_renders_no_badge(self):
        """Re-freeze keeps the record id; the old verdict must not show."""
        for cls in (MonitorApp, MiniMonitorApp):
            with self.subTest(cls.__name__):
                app = self.app(cls)
                app._frozen_sitrep_results = {RID: verdict(frozen_sitrep.NOTHING,
                                                           pid=100)}
                self.assertNotIn("drop ok", self.row(app, frozen_snap(pid=200)))
                self.assertNotIn("drop ok",
                                 self.row(app, frozen_snap(pane_id="%9", pid=100)))
                # Control: the matching instance renders it.
                self.assertIn("drop ok", self.row(app, frozen_snap(pid=100)))

    def test_the_minimonitor_name_budget_pays_for_the_badge(self):
        from monitor import minimonitor_app as mm
        app = self.app(MiniMonitorApp)
        long_name = "agent-" + "z" * 60
        app._frozen_sitrep_results = {}
        bare = self.row(app, frozen_snap(window=long_name))
        app._frozen_sitrep_results = {RID: verdict(frozen_sitrep.TRIAGED)}
        badged = self.row(app, frozen_snap(window=long_name))
        name_bare = bare.split("  ")[0].split(" ")[-1]
        name_badged = badged.split("  ")[0].split(" ")[-1]
        self.assertEqual(cell_len(name_bare) - cell_len(name_badged),
                         frozen_state_width(frozen_sitrep.TRIAGED)
                         - frozen_state_width(None))
        self.assertLessEqual(cell_len(badged.split("\n")[0]),
                             mm._row_budget(app._target_width))


class _Host:
    """Just the mixin's worker surface, for the coalescing unit tests."""

    from monitor.monitor_shared import AgentMarksMixin as _M
    _kick_frozen_sitrep = _M._kick_frozen_sitrep
    _frozen_sitrep_pass = _M._frozen_sitrep_pass
    _frozen_sitrep_state = _M._frozen_sitrep_state

    def __init__(self, tracker) -> None:
        self._snapshots = {"%3": frozen_snap()}
        self._frozen_sitrep_results = {}
        self._frozen_sitrep_tracker = tracker
        self._frozen_sitrep_inflight = False
        self._frozen_sitrep_pending = None
        self.dispatched = []
        self.coros = []

    def _dispatch_frozen_sitrep(self, ids):
        self.dispatched.append(ids)
        self.coros.append(self._frozen_sitrep_pass(ids))


class _Tracker:
    def __init__(self, result=None, exc=None):
        self.calls = []
        self.result, self.exc = result, exc

    def states(self, ids):
        self.calls.append(ids)
        if self.exc:
            raise self.exc
        return {rid: self.result for rid in ids}


class CoalescingTests(unittest.TestCase):

    def test_a_kick_while_in_flight_only_queues_the_newest_ids(self):
        host = _Host(_Tracker(verdict(frozen_sitrep.NOTHING)))
        host._kick_frozen_sitrep()
        host._kick_frozen_sitrep()
        host._kick_frozen_sitrep()
        self.assertEqual([(RID,)], host.dispatched)
        self.assertEqual((RID,), host._frozen_sitrep_pending)

        async def drive():
            await host.coros.pop(0)
            self.assertEqual(2, len(host.dispatched), "one queued pass runs")
            await host.coros.pop(0)
        asyncio.run(drive())
        self.assertFalse(host._frozen_sitrep_inflight)
        self.assertIsNone(host._frozen_sitrep_pending)
        self.assertEqual(frozen_sitrep.NOTHING, host._frozen_sitrep_state(frozen_snap()))

    def test_a_failing_pass_leaves_no_badge(self):
        host = _Host(_Tracker(exc=RuntimeError("boom")))
        host._frozen_sitrep_results = {RID: verdict(frozen_sitrep.NOTHING)}
        host._kick_frozen_sitrep()
        asyncio.run(host.coros.pop(0))
        self.assertEqual({}, host._frozen_sitrep_results)
        self.assertIsNone(host._frozen_sitrep_state(frozen_snap()))
        self.assertFalse(host._frozen_sitrep_inflight)

    def test_results_are_restricted_to_the_asked_ids(self):
        host = _Host(_Tracker(verdict(frozen_sitrep.NOTHING)))
        host._snapshots = {}
        host._frozen_sitrep_results = {RID: verdict(frozen_sitrep.NOTHING)}
        host._kick_frozen_sitrep()
        self.assertEqual([], host.dispatched)
        self.assertEqual({}, host._frozen_sitrep_results)


# --- the refresh never waits on a badge read (both TUIs, mounted) -------------

class _BlockingTracker:
    """`states` blocks on a threading.Event, as a slow store read would."""

    def __init__(self, result) -> None:
        self.gate = threading.Event()
        self.entered = threading.Event()
        self.calls = 0
        self.result = result

    def states(self, ids):
        self.calls += 1
        self.entered.set()
        self.gate.wait(timeout=30)
        return {rid: self.result for rid in ids}


class _TickMonitor:
    """The tick surface both apps' `_refresh_data` reach, with ONE frozen pane."""

    multi_session = False
    capture_generation = 1

    def __init__(self, root: Path, snap: PaneSnapshot) -> None:
        self.root = root
        self.snap = snap

    # discovery / capture
    async def capture_all_classified_async(self):
        return 1, []

    def commit_snapshots(self, gen, classified):
        return {self.snap.pane.pane_id: self.snap}

    async def capture_all_async(self):
        return {self.snap.pane.pane_id: self.snap}

    # session mapping
    async def get_session_to_project_mapping_async(self):
        return {SESSION: self.root}

    def get_session_to_project_mapping(self):
        return {SESSION: self.root}

    def set_parked_agents(self, pairs): pass
    def control_state(self): return TmuxControlState.CONNECTED
    def get_shadow_snapshots(self): return {}
    def get_shadow_snapshot(self, pane_id): return None
    def get_compare_mode(self, pane_id): return "stripped"
    def is_compare_mode_overridden(self, pane_id): return False
    async def tmux_run_async(self, args, timeout=5.0): return (1, "")
    async def discover_window_panes_async(self, window_id): return (False, [])
    def last_discovered_agents(self): return frozenset()


_ENV = mock.patch.dict(os.environ, {"AITASKS_MONITOR_SERVER": "0"})


class RefreshNeverWaitsTests(unittest.TestCase):

    def setUp(self) -> None:
        _ENV.start()
        self.addCleanup(_ENV.stop)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _scenario(self, app) -> None:
        async def scenario():
            tracker = _BlockingTracker(verdict(frozen_sitrep.NOTHING))
            async with app.run_test(size=(100, 30)):
                app._monitor = _TickMonitor(self.root, frozen_snap())
                app._frozen_sitrep_tracker = tracker
                dispatched = []
                real_dispatch = app._dispatch_frozen_sitrep

                def spy(ids):
                    dispatched.append(ids)
                    real_dispatch(ids)
                app._dispatch_frozen_sitrep = spy
                try:
                    await asyncio.wait_for(app._refresh_data(), timeout=10)
                    await asyncio.to_thread(tracker.entered.wait, 10)
                    self.assertTrue(tracker.entered.is_set(), "no pass started")
                    # The pass is held open; a second refresh still completes.
                    await asyncio.wait_for(app._refresh_data(), timeout=10)
                    self.assertEqual(1, len(dispatched), "no second pass while one runs")
                    self.assertEqual((RID,), app._frozen_sitrep_pending)
                    self.assertIsNone(app._frozen_sitrep_state(frozen_snap()),
                                      "no badge before a validated verdict")
                finally:
                    tracker.gate.set()
                # The held pass ends, the queued one runs once, and the next
                # ordinary refresh renders the published verdict.
                for _ in range(200):
                    if not app._frozen_sitrep_inflight and len(dispatched) == 2:
                        break
                    await asyncio.sleep(0.02)
                self.assertEqual(2, len(dispatched))
                self.assertFalse(app._frozen_sitrep_inflight)
                self.assertEqual(frozen_sitrep.NOTHING,
                                 app._frozen_sitrep_state(frozen_snap()))
        asyncio.run(scenario())

    def test_the_full_monitor_refresh_never_waits(self):
        self._scenario(MonitorApp(session=SESSION, project_root=self.root))

    def test_the_minimonitor_refresh_never_waits(self):
        self._scenario(MiniMonitorApp(session=SESSION, project_root=self.root,
                                      refresh_seconds=999))


if __name__ == "__main__":
    unittest.main(verbosity=2)
