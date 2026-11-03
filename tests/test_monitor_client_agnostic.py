"""The `TmuxMonitor` producer is client-agnostic (t2034_2).

One producer must be able to serve many clients (monitor, minimonitors,
applink — the shared status server, t2037), so the four settings that used to
live inside it moved to — or were pinned as — the semantics below. One test
class per row:

- **Own pane** (`ExcludeIsClientSideTests`) — the producer excludes nothing and
  reads no `$TMUX_PANE`; the client view drops its own pane.
- **Multi-session** (`MultiSessionIsClientViewTests`) — the live producer scans
  every session; `M` flips the app's view flag only.
- **Parked** (`ParkedGlobalSetTests`, `SharedProducerParkedTests`) — which agents
  are parked is global; per-client capture pins decide what is still captured,
  and each client's view restores the placeholder for parked agents it does not
  pin. The two-client simulation runs B's REAL `_fast_preview_refresh`.
- **Compare mode** (`CompareModeIsSharedTests`) — one shared per-pane setting.
- **applink** (`ApplinkOwnPaneTests`) — with the server's own (unmarked) pane
  present in the producer cache, every cache-backed route still behaves as the
  cache miss it was while the producer excluded it.
- **Static pin** (`NoClientSettingsInProducerTests`, risk mitigation
  `pin_no_client_settings_in_producer`) — fake monitors in older tests still
  carry an inert `multi_session` attribute, so a production reader that was
  missed would pass under them and raise only live. This pins it in source.
"""
from __future__ import annotations

import ast
import asyncio
import contextlib
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "lib"))
sys.path.insert(0, str(SCRIPTS / "applink"))
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))   # tmux_server_model

# The suite may run inside a live agent pane: no ambient pane id may leak in.
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

import agent_marks  # noqa: E402
from monitor import monitor_core  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    CAPTURE_PIN_ALL, COMPARE_MODE_RAW, ClassifyResult, PaneCategory,
    PaneSnapshot, TmuxMonitor, TmuxPaneInfo, client_admits_pane,
    client_view_snapshots, parked_capture_skip,
)


def pane(session: str, window: str, pane_id: str, *,
         category: PaneCategory = PaneCategory.AGENT,
         frozen_record: str = "") -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index="1", window_name=window, pane_index="0", pane_id=pane_id,
        pane_pid=4242, current_command="node", width=80, height=24,
        category=category, session_name=session, frozen_record=frozen_record,
    )


def snap(p: TmuxPaneInfo, content: str = "live", **kw) -> PaneSnapshot:
    return PaneSnapshot(pane=p, content=content, timestamp=0.0,
                        idle_seconds=0.0, is_idle=False, **kw)


def list_panes_row(pane_id: str, window: str, pid: int) -> str:
    """One 11-field `list-panes` record (…<shadow>\t<history>\t<monitor_kind>)."""
    return "\t".join(["1", window, "0", pane_id, str(pid), "bash", "80", "24",
                      "", "0", ""])


class _MarkStore:
    """A throwaway marks store with one real project root (realpath'd)."""

    def __init__(self, case: unittest.TestCase) -> None:
        tmp = tempfile.TemporaryDirectory()
        case.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "repo"
        self.root.mkdir()
        self.store = Path(tmp.name) / "marks.json"

    def park(self, window: str) -> None:
        """Drive the real cycle to `parked` — never hand-write the record."""
        mf = agent_marks.load(self.store)
        agent_marks.cycle(mf, self.root, window)
        agent_marks.cycle(mf, self.root, window)
        agent_marks.dump(mf, self.store)

    def view(self) -> agent_marks.MarksView:
        view = agent_marks.MarksView(self.store)
        view.refresh()
        return view


# --- own pane ----------------------------------------------------------------


class ExcludeIsClientSideTests(unittest.TestCase):

    def test_the_producer_reads_no_tmux_pane(self):
        stdout = (list_panes_row("%5", "agent-mine", 1005) + "\n"
                  + list_panes_row("%6", "agent-other", 1006) + "\n")
        with patch.dict(os.environ, {"TMUX_PANE": "%5"}), \
                patch.object(monitor_core, "_is_companion_process",
                             return_value=False):
            mon = TmuxMonitor(session="demo", all_sessions=False)
            found, _shadows = mon._parse_list_panes(stdout, "demo")
        self.assertEqual([p.pane_id for p in found], ["%5", "%6"],
                         "the producer dropped $TMUX_PANE on a client's behalf")
        self.assertFalse(hasattr(mon, "exclude_pane"))

    def test_the_client_view_drops_its_own_pane(self):
        snaps = {"%5": snap(pane("demo", "agent-mine", "%5")),
                 "%6": snap(pane("demo", "agent-other", "%6"))}
        self.assertEqual(set(client_view_snapshots(snaps, own_pane="%5")),
                         {"%6"})
        # Control: no own pane -> nothing dropped.
        self.assertEqual(set(client_view_snapshots(snaps, own_pane=None)),
                         {"%5", "%6"})

    def test_freeze_all_still_skips_the_callers_own_pane(self):
        """`exclude_pane=""` used to fall back to `$TMUX_PANE`; the exclusion it
        gave freeze-all by accident is now explicit."""
        import agent_freeze

        recorded: dict = {}

        class _RecMon:
            def __init__(self, **kwargs):
                recorded.update(kwargs)

            def discover_panes(self):
                return [pane("demo", "agent-a", "%5"),
                        pane("demo", "agent-b", "%6")]

        with patch.object(agent_freeze, "TmuxMonitor", _RecMon):
            with patch.dict(os.environ, {"TMUX_PANE": "%5"}):
                caller_in_tmux = [p.pane_id for p in agent_freeze._agent_panes_for("demo")]
            no_tmux = [p.pane_id for p in agent_freeze._agent_panes_for("demo")]
        self.assertEqual(caller_in_tmux, ["%6"])
        self.assertEqual(no_tmux, ["%5", "%6"], "control: nothing to exclude")
        self.assertEqual(recorded, {"session": "demo", "all_sessions": False})


# --- multi-session -----------------------------------------------------------


class _NoViewMonitor:
    """A producer stand-in with NO `multi_session` attribute: touching it raises."""

    __slots__ = ("invalidated",)

    def __init__(self) -> None:
        self.invalidated = 0

    def invalidate_sessions_cache(self) -> None:
        self.invalidated += 1


class MultiSessionIsClientViewTests(unittest.IsolatedAsyncioTestCase):

    async def _listed_targets(self, mon: TmuxMonitor) -> list[str]:
        targets: list[str] = []

        async def fake_tmux(args, timeout=5.0):
            if args and args[0] == "list-panes":
                targets.append(args[args.index("-t") + 1])
            return 0, ""

        async def fake_sessions():
            return ["sA", "sB"]

        mon._tmux_async = fake_tmux
        mon._target_sessions_async = fake_sessions
        await mon.discover_panes_with_shadows_async()
        return targets

    async def test_the_live_producer_scans_every_session(self):
        targets = await self._listed_targets(TmuxMonitor(session="sA"))
        self.assertEqual(len(targets), 2)
        self.assertTrue(any("sA" in t for t in targets))
        self.assertTrue(any("sB" in t for t in targets))

    async def test_all_sessions_false_is_a_one_shot_scope(self):
        targets = await self._listed_targets(
            TmuxMonitor(session="sA", all_sessions=False))
        self.assertEqual(len(targets), 1)
        self.assertIn("sA", targets[0])

    def _toggle(self, cls):
        app = cls.__new__(cls)
        app._monitor = _NoViewMonitor()
        app._multi_session = True
        app.notify = lambda *a, **k: None
        app.call_later = lambda fn: None
        app._refresh_data = lambda: None
        app.action_toggle_multi_session()
        first = app._multi_session
        app.action_toggle_multi_session()
        return first, app._multi_session, app._monitor.invalidated

    def test_both_apps_flip_only_their_own_view_flag(self):
        from monitor.minimonitor_app import MiniMonitorApp
        from monitor.monitor_app import MonitorApp

        for cls in (MonitorApp, MiniMonitorApp):
            with self.subTest(app=cls.__name__):
                off, on, invalidated = self._toggle(cls)
                self.assertEqual((off, on), (False, True))
                self.assertEqual(invalidated, 0,
                                 "the toggle reached into the producer")

    def test_the_view_filter_keeps_only_the_home_session_when_off(self):
        snaps = {"%1": snap(pane("sA", "agent-a", "%1")),
                 "%2": snap(pane("sB", "agent-b", "%2")),
                 "%3": snap(pane("", "agent-legacy", "%3"))}
        off = client_view_snapshots(snaps, home_session="sA", multi_session=False)
        on = client_view_snapshots(snaps, home_session="sA", multi_session=True)
        self.assertEqual(set(off), {"%1", "%3"},
                         "an empty session name is a record of the home session")
        self.assertEqual(set(on), {"%1", "%2", "%3"})


class RefreshStoresTheProjectedSetTests(unittest.IsolatedAsyncioTestCase):
    """Both apps' bulk refresh stores the client view, not the producer's dict."""

    async def _refreshed(self, cls, *, multi: bool):
        marks = _MarkStore(self)
        own = pane("demo", "agent-own", "%9")
        home = pane("demo", "agent-home", "%1")
        other = pane("other", "agent-far", "%2")
        produced = {p.pane_id: snap(p) for p in (own, home, other)}

        class _Mon:
            capture_generation = 1

            def set_parked_agents(self, pairs):
                pass

            async def capture_all_classified_async(self):
                return 1, []

            async def capture_all_async(self):
                return dict(produced)

            def commit_snapshots(self, gen, classified):
                return dict(produced)

            async def get_session_to_project_mapping_async(self):
                return {"demo": marks.root}

            def get_session_to_project_mapping(self):
                return {"demo": marks.root}

            def control_state(self):
                return None

            def get_shadow_snapshots(self):
                return {}

        app = cls.__new__(cls)
        app._monitor = _Mon()
        app._session = "demo"
        app._project_root = marks.root
        app._own_pane_id = "%9"
        app._multi_session = multi
        app._marks_view = marks.view()
        app._marks_purge_due_at = float("inf")
        app._marks_purge_inflight = False
        app._maintenance_inflight = False
        app._refresh_inflight = False
        app._session_root_map = {}
        app._hide_inactive = False
        app._snapshots = {}
        app._task_cache = SimpleNamespace(
            update_session_mapping=lambda m: None,
            get_task_id_for_pane=lambda p: None,
            get_task_info=lambda t, s=None: None)
        app._gate_cache = SimpleNamespace(clear=lambda: None)
        app._completed_pane_ids = frozenset()
        app._own_window_name = "agent-own"
        app._own_identity_confirmed = False
        app._focused_pane_id = None
        app._active_zone = None
        app._parked_pane_ids = frozenset()
        app._compute_completed_panes = lambda: frozenset()

        async def own_info():
            return True

        app._update_own_window_info = own_info
        # Everything after the snapshot write is DOM work this test does not
        # exercise; it raises on the stub and is suppressed.
        with contextlib.suppress(Exception):
            await app._refresh_data()
        return set(app._snapshots)

    async def test_both_apps(self):
        from monitor.minimonitor_app import MiniMonitorApp
        from monitor.monitor_app import MonitorApp

        for cls in (MonitorApp, MiniMonitorApp):
            with self.subTest(app=cls.__name__):
                self.assertEqual(await self._refreshed(cls, multi=True),
                                 {"%1", "%2"})
                self.assertEqual(await self._refreshed(cls, multi=False),
                                 {"%1"})


# --- parked: global set + per-client capture pins ----------------------------


class ParkedGlobalSetTests(unittest.TestCase):

    def test_parked_session_windows(self):
        marks = _MarkStore(self)
        marks.park("agent-x")
        parked = marks.view().parked_windows()
        link = marks.root.parent / "link"
        link.symlink_to(marks.root)
        got = agent_marks.parked_session_windows(
            parked, {"s1": marks.root, "s2": marks.root, "s3": link,
                     "s4": marks.root.parent})
        self.assertEqual(got, {("s1", "agent-x"), ("s2", "agent-x"),
                               ("s3", "agent-x")})
        self.assertEqual(agent_marks.parked_session_windows(set(), {"s1": marks.root}),
                         frozenset())

    def test_parked_capture_skip(self):
        g = frozenset({("s", "a"), ("s", "b"), ("s", "c")})
        self.assertEqual(parked_capture_skip(g, []), g)
        self.assertEqual(parked_capture_skip(g, [frozenset()]), g)
        self.assertEqual(parked_capture_skip(g, [{("s", "a")}]),
                         {("s", "b"), ("s", "c")})
        self.assertEqual(parked_capture_skip(g, [{("s", "a")}, {("s", "b")}]),
                         {("s", "c")})
        self.assertEqual(parked_capture_skip(g, [{("s", "a")}, CAPTURE_PIN_ALL]),
                         frozenset())
        self.assertEqual(parked_capture_skip(g, [{("s", "zz")}]), g,
                         "a pin on a non-parked pair is inert")

    def _apps(self, *, confirmed: bool):
        from monitor.minimonitor_app import MiniMonitorApp
        from monitor.monitor_app import MonitorApp

        marks = _MarkStore(self)
        marks.park("agent-followed")
        marks.park("agent-elsewhere")
        apps = []
        for cls in (MonitorApp, MiniMonitorApp):
            app = cls.__new__(cls)
            app._session = "demo"
            app._marks_view = marks.view()
            app._set_session_root_map({"demo": marks.root})
            app._own_window_name = "agent-followed"
            app._own_identity_confirmed = confirmed
            apps.append(app)
        return apps

    def test_every_client_derives_the_same_global_set(self):
        mon_app, mini_app = self._apps(confirmed=True)
        both = {("demo", "agent-followed"), ("demo", "agent-elsewhere")}
        self.assertEqual(mon_app._global_parked_pairs(), both)
        self.assertEqual(mini_app._global_parked_pairs(), both)
        # The published SKIP sets differ only by the minimonitor's followed pair.
        self.assertEqual(mon_app._parked_agent_pairs(), both)
        self.assertEqual(mini_app._parked_agent_pairs(),
                         {("demo", "agent-elsewhere")})

    def test_an_unconfirmed_minimonitor_pins_everything(self):
        _mon_app, mini_app = self._apps(confirmed=False)
        self.assertIs(mini_app._capture_pins(), CAPTURE_PIN_ALL)
        self.assertEqual(mini_app._parked_agent_pairs(), frozenset())


class SharedProducerParkedTests(unittest.IsolatedAsyncioTestCase):
    """One producer, two clients. A follows parked agent X (pins it); B pins
    nothing. A's pin makes the producer capture X live; B must keep seeing it
    parked — on the bulk view AND on B's own fast-preview route."""

    X = ("demo", "agent-x")

    def _producer(self, panes):
        mon = TmuxMonitor(session="demo", all_sessions=False)
        self.captures = 0

        async def fake_discover(enum_sink=None):
            if enum_sink is not None:
                enum_sink.append(frozenset({"demo"}))
            return list(panes), []

        async def fake_capture(pane_id, capture_lines=None, pane=None):
            self.captures += 1
            target = pane or mon._pane_cache.get(pane_id)
            return (target, f"{pane_id} output v{self.captures}")

        async def run_offloaded(fn):
            return fn()

        for p in panes:
            mon._pane_cache[p.pane_id] = p
        mon.discover_panes_with_shadows_async = fake_discover
        mon.capture_pane_content_async = fake_capture
        mon._run_offloaded = run_offloaded
        return mon

    async def _bulk(self, mon, global_parked, pins_a, pins_b):
        mon.set_parked_agents(parked_capture_skip(global_parked, [pins_a, pins_b]))
        gen, classified = await mon.capture_all_classified_async()
        return mon.commit_snapshots(gen, classified)

    async def test_bulk_views_diverge_by_pin(self):
        x = pane("demo", "agent-x", "%2")
        live = pane("demo", "agent-live", "%1")
        mon = self._producer([live, x])
        g = frozenset({self.X})
        snaps = await self._bulk(mon, g, {self.X}, frozenset())

        self.assertFalse(snaps["%2"].parked, "A's pin must let X be captured")
        a = client_view_snapshots(snaps, parked_pairs=g, pins={self.X})
        b = client_view_snapshots(snaps, parked_pairs=g, pins=frozenset())
        self.assertFalse(a["%2"].parked)
        self.assertIn("output", a["%2"].content)
        self.assertTrue(b["%2"].parked, "A's pin leaked live data into B's row")
        self.assertEqual(b["%2"].content, "")
        self.assertFalse(b["%1"].parked, "an unparked agent is untouched")

    async def test_frozen_stays_frozen_in_both_views(self):
        x = pane("demo", "agent-x", "%2", frozen_record="rec-1")
        mon = self._producer([x])
        g = frozenset({self.X})
        snaps = await self._bulk(mon, g, {self.X}, frozenset())
        for pins in ({self.X}, frozenset()):
            with self.subTest(pins=pins):
                v = client_view_snapshots(snaps, parked_pairs=g, pins=pins)
                self.assertTrue(v["%2"].frozen)
                self.assertFalse(v["%2"].parked, "frozen takes precedence")

    def _client_b(self, mon, marks, *, focus: str, pins=None, multi=True):
        from monitor.monitor_app import MonitorApp

        app = MonitorApp.__new__(MonitorApp)
        app._monitor = mon
        app._session = "demo"
        app._own_pane_id = "%9"
        app._multi_session = multi
        app._marks_view = marks.view()
        app._set_session_root_map({"demo": marks.root})
        app._focused_pane_id = focus
        app._update_content_preview = lambda: None
        if pins is not None:
            app._capture_pins = lambda: pins
        return app

    async def test_b_fast_preview_keeps_the_placeholder(self):
        marks = _MarkStore(self)
        marks.park("agent-x")
        x = pane("demo", "agent-x", "%2")
        mon = self._producer([x])
        g = frozenset({self.X})
        snaps = await self._bulk(mon, g, {self.X}, frozenset())

        b = self._client_b(mon, marks, focus="%2")
        self.assertEqual(b._global_parked_pairs(), g)
        b._snapshots = b._project_snapshots(snaps)
        self.assertTrue(b._snapshots["%2"].parked, "initial view")
        before = mon._last_content.get("%2")

        await b._fast_preview_refresh()

        self.assertEqual(self.captures, 2, "the producer captured X live (A's pin)")
        self.assertTrue(b._snapshots["%2"].parked,
                        "B's fast preview overwrote its parked placeholder")
        self.assertEqual(b._snapshots["%2"].content, "")
        self.assertNotEqual(mon._last_content.get("%2"), before,
                            "the producer's idle bookkeeping must still advance")

        # Control: when B itself pins X, the same route stores the live result.
        b_pins = self._client_b(mon, marks, focus="%2", pins={self.X})
        b_pins._snapshots = {}
        await b_pins._fast_preview_refresh()
        self.assertFalse(b_pins._snapshots["%2"].parked)
        self.assertIn("output", b_pins._snapshots["%2"].content)

    async def test_b_fast_preview_stores_nothing_it_does_not_admit(self):
        marks = _MarkStore(self)
        own = pane("demo", "agent-own", "%9")
        far = pane("other", "agent-far", "%3")
        mon = self._producer([own, far])
        for focus, multi in (("%9", True), ("%3", False)):
            with self.subTest(focus=focus):
                b = self._client_b(mon, marks, focus=focus, multi=multi)
                b._snapshots = {}
                await b._fast_preview_refresh()
                self.assertEqual(b._snapshots, {})


# --- compare mode: one shared per-pane setting --------------------------------


class CompareModeIsSharedTests(unittest.TestCase):

    def test_an_override_is_what_every_reader_sees(self):
        mon = TmuxMonitor(session="demo", all_sessions=False)
        mon.set_compare_mode("%2", COMPARE_MODE_RAW)
        # Two clients reading the same producer: there is no per-client value.
        self.assertEqual(mon.get_compare_mode("%2"), COMPARE_MODE_RAW)
        self.assertTrue(mon.is_compare_mode_overridden("%2"))

    def test_a_clients_view_never_reaps_an_override(self):
        """Reaped by the producer's discovery only — not because one client's
        single-session view hides the pane."""
        mon = TmuxMonitor(session="sA", all_sessions=False)
        home, far = pane("sA", "agent-a", "%1"), pane("sB", "agent-b", "%2")
        mon.set_compare_mode("%2", COMPARE_MODE_RAW)
        gen = mon._next_generation()
        snaps = mon.commit_snapshots(gen, [
            (home, "a", ClassifyResult(compare_value="a")),
            (far, "b", ClassifyResult(compare_value="b")),
        ])
        view = client_view_snapshots(snaps, home_session="sA", multi_session=False)
        self.assertNotIn("%2", view)
        self.assertTrue(mon.is_compare_mode_overridden("%2"))
        # Positive control: once discovery loses the pane, it IS reaped.
        gen = mon._next_generation()
        mon.commit_snapshots(gen, [(home, "a", ClassifyResult(compare_value="a"))])
        self.assertFalse(mon.is_compare_mode_overridden("%2"))

    def test_the_applink_verb_and_the_app_action_share_one_dict(self):
        import profiles as P
        import sessions as S
        from router import ConnState, FrameRouter

        mon = TmuxMonitor(session="demo", all_sessions=False)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        st = S.SessionTable(Path(tmp.name), persist=False)
        router = FrameRouter(st, P.ProfileGate.load(
            REPO_ROOT / "aitasks" / "metadata" / "applink_profiles"), mon)
        bearer = st.issue_bearer("monitor_control").bearer
        router.handle({"v": 1, "id": "m", "kind": "req",
                       "verb": "cycle_compare_mode",
                       "payload": {"pane_id": "%2"}, "auth": bearer}, ConnState())
        self.assertEqual(mon.get_compare_mode("%2"), COMPARE_MODE_RAW,
                         "the remote override is the desktop's override")


# --- applink: the server's own (unmarked) pane ---------------------------------


class _CacheMonitor:
    """A producer whose cache DOES hold the own pane (exclusion removed)."""

    def __init__(self, panes) -> None:
        self.cache = {p.pane_id: p for p in panes}
        self.calls: list[tuple] = []

    def discover_panes(self):
        return list(self.cache.values())

    def get_pane(self, pane_id):
        return self.cache.get(pane_id)

    def get_pane_option_sync(self, pane_id, option, timeout=2.0):
        return True, ""

    def switch_to_pane(self, pane_id, prefer_companion=False):
        self.calls.append(("focus", pane_id))
        return pane_id in self.cache

    def capture_pane(self, pane_id):
        p = self.cache.get(pane_id)
        if p is None:
            return None
        return SimpleNamespace(pane=p, is_idle=True, idle_seconds=99.0)

    def kill_agent_pane_smart(self, pane_id, cache_miss=False):
        self.calls.append(("kill_cache_miss" if cache_miss else "kill_smart",
                           pane_id))
        return True, not cache_miss

    def send_keys(self, pane_id, keys, literal=False):
        self.calls.append(("send_keys", pane_id))
        return True


class ApplinkOwnPaneTests(unittest.TestCase):
    OWN, OTHER = "%9", "%1"

    def setUp(self):
        import profiles as P
        import sessions as S
        from router import FrameRouter

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.st = S.SessionTable(Path(tmp.name), persist=False)
        self.gate = P.ProfileGate.load(
            REPO_ROOT / "aitasks" / "metadata" / "applink_profiles")
        self.FrameRouter = FrameRouter

    def _router(self, own_pane):
        mon = _CacheMonitor([pane("demo", "applink", self.OWN,
                                  category=PaneCategory.OTHER),
                             pane("demo", "agent-a", self.OTHER)])
        return self.FrameRouter(self.st, self.gate, mon, own_pane=own_pane), mon

    def _req(self, router, conn, verb, payload, profile="full"):
        bearer = self.st.issue_bearer(profile).bearer
        return router.handle({"v": 1, "id": "m", "kind": "req", "verb": verb,
                              "payload": payload, "auth": bearer}, conn)

    def _subscribed(self, own_pane, panes):
        from router import ConnState

        router, _mon = self._router(own_pane)
        conn = ConnState()
        self._req(router, conn, "subscribe", {"panes": panes})
        return set(conn.subscription.panes), router, conn

    def test_subscribe_roster_and_explicit(self):
        for panes in ([], [self.OWN, self.OTHER]):
            with self.subTest(panes=panes):
                got, *_ = self._subscribed(self.OWN, panes)
                self.assertEqual(got, {self.OTHER})
                control, *_ = self._subscribed(None, panes)
                self.assertEqual(control, {self.OWN, self.OTHER})

    def test_history_for_the_own_pane_is_rejected(self):
        _got, router, conn = self._subscribed(self.OWN, [self.OWN, self.OTHER])
        r = self._req(router, conn, "history",
                      {"pane_id": self.OWN, "before_line": 0, "count": 10})
        self.assertEqual(r["kind"], "err")
        ok = self._req(router, conn, "history",
                       {"pane_id": self.OTHER, "before_line": 0, "count": 10})
        self.assertEqual(ok["kind"], "res", "control: a subscribed pane is accepted")

    def _verbs(self, own_pane):
        from router import ConnState

        router, mon = self._router(own_pane)
        focus = self._req(router, ConnState(), "focus", {"pane_id": self.OWN})
        restart = self._req(router, ConnState(), "restart_task",
                            {"pane_id": self.OWN})
        self._req(router, ConnState(), "kill_pane",
                  {"pane_id": self.OWN, "confirmed": True})
        keys = self._req(router, ConnState(), "send_keys",
                         {"pane_id": self.OWN, "keys": "x"})
        return focus, restart, keys, mon.calls

    def test_cache_backed_verbs_treat_the_own_pane_as_a_cache_miss(self):
        focus, restart, keys, calls = self._verbs(self.OWN)
        self.assertIs(focus["payload"]["ok"], False)
        self.assertEqual(restart["payload"]["detail"]["reason"], "not_found")
        self.assertIn(("kill_cache_miss", self.OWN), calls)
        self.assertNotIn(("kill_smart", self.OWN), calls)
        self.assertNotIn(("focus", self.OWN), calls)
        self.assertIs(keys["payload"]["ok"], True, "send_keys never read the cache")
        self.assertIn(("send_keys", self.OWN), calls)

    def test_control_without_an_own_pane_admits_it_everywhere(self):
        focus, restart, keys, calls = self._verbs(None)
        self.assertIs(focus["payload"]["ok"], True)
        # Past the cache gate: the pane is found and idle, and only then fails
        # on the stub's missing task id — not `not_found`.
        self.assertEqual(restart["payload"]["detail"]["reason"], "no_task")
        self.assertIn(("kill_smart", self.OWN), calls)
        self.assertIs(keys["payload"]["ok"], True)


class ApplinkOwnPaneKillSweepTests(unittest.TestCase):
    """`kill_pane` on the own pane, through the REAL router and producer.

    The cache-miss route this pane used to take is a plain pane kill FOLLOWED
    BY the bound-helper sweep (t2088). The own-pane branch must keep both: no
    window collapse, and a shadow bound to the pane in another window dies too.
    """

    OWN = "%1"

    def _kill(self, own_pane):
        import profiles as P
        import sessions as S
        from monitor_marker import MONITOR_KIND_OPTION
        from router import ConnState, FrameRouter
        from tmux_server_model import TmuxServerModel

        def p(pane_id, pid, window, **opts):
            return {"pane_id": pane_id, "pane_pid": str(pid), "window": window,
                    "pane_dead": "0", **opts}

        model = TmuxServerModel({
            self.OWN: p(self.OWN, 101, "7"),
            # A companion in the same window: dies only on a window collapse.
            "%4": p("%4", 404, "7", **{MONITOR_KIND_OPTION: "minimonitor"}),
            # A shadow bound to the own pane, in ANOTHER window: only the
            # helper sweep can reach it.
            "%3": p("%3", 303, "9",
                    **{monitor_core.SHADOW_TARGET_OPTION: self.OWN}),
            "%7": p("%7", 707, "9"),
        })
        mon = TmuxMonitor(session="demo", all_sessions=False,
                          agent_prefixes=["agent-"])
        mon.tmux_run = model
        # Present in the producer cache — the exclusion is gone (t2034_2).
        mon._pane_cache[self.OWN] = pane("demo", "agent-own", self.OWN)
        mon._pane_cache[self.OWN].window_index = "7"
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        st = S.SessionTable(Path(tmp.name), persist=False)
        router = FrameRouter(st, P.ProfileGate.load(
            REPO_ROOT / "aitasks" / "metadata" / "applink_profiles"), mon,
            own_pane=own_pane)
        with patch.object(monitor_core, "_is_companion_process",
                          return_value=False):
            r = router.handle({
                "v": 1, "id": "k", "kind": "req", "verb": "kill_pane",
                "payload": {"pane_id": self.OWN, "confirmed": True},
                "auth": st.issue_bearer("full").bearer}, ConnState())
        return r["payload"], set(model.panes)

    def test_own_pane_kill_is_plain_and_still_sweeps_helpers(self):
        payload, left = self._kill(self.OWN)
        self.assertIs(payload["ok"], True)
        self.assertIs(payload["killed_window"], False)
        self.assertNotIn(self.OWN, left)
        self.assertNotIn("%3", left, "the bound shadow survived the kill")
        self.assertIn("%4", left, "the window collapsed — the smart path ran")

    def test_control_the_smart_path_collapses_the_window(self):
        """Without an own pane the same fixture takes the smart path: the
        companion dies with the window, so the assertion above discriminates."""
        payload, left = self._kill(None)
        self.assertIs(payload["killed_window"], True)
        self.assertNotIn("%4", left)
        self.assertNotIn("%3", left)


class ApplinkPusherOwnPaneTests(unittest.IsolatedAsyncioTestCase):
    OWN, OTHER = "%9", "%1"

    def _sched(self, own_pane):
        import content as C
        from pusher import PushScheduler

        own = pane("demo", "applink", self.OWN, category=PaneCategory.OTHER)
        other = pane("demo", "agent-a", self.OTHER)
        snaps = {self.OWN: snap(own), self.OTHER: snap(other)}
        self.pushed: list[str] = []
        self.history_captures: list[str] = []

        class _Mon:
            async def capture_all_async(self):
                return dict(snaps)

            def get_pane(self, pane_id):
                s = snaps.get(pane_id)
                return s.pane if s is not None else None

            async def capture_pane_content_async(inner, pane_id, capture_lines=None):
                self.history_captures.append(pane_id)
                return None

        # A subscription built BEFORE the router's filter could apply.
        sub = C.Subscription()
        sub.apply_subscribe({"panes": [self.OWN, self.OTHER]})
        conn = SimpleNamespace(subscription=sub, paused=False)
        ws = SimpleNamespace(transport=None, send=None)
        sched = PushScheduler(conn, ws, _Mon(), own_pane=own_pane)

        async def record_push(sub_, pane_id, snap_, now):
            self.pushed.append(pane_id)

        sched._push_pane = record_push
        return sched, sub

    async def test_live_push_and_history_drain_skip_the_own_pane(self):
        sched, sub = self._sched(self.OWN)
        await sched._run_once()
        self.assertEqual(self.pushed, [self.OTHER])
        sub.request_history(self.OWN, 0, 10)
        sub.request_history(self.OTHER, 0, 10)
        await sched._drain_history(sub)
        self.assertEqual(self.history_captures, [self.OTHER])

    async def test_control_without_an_own_pane(self):
        sched, sub = self._sched(None)
        await sched._run_once()
        self.assertEqual(sorted(self.pushed), [self.OTHER, self.OWN])
        sub.request_history(self.OWN, 0, 10)
        await sched._drain_history(sub)
        self.assertEqual(self.history_captures, [self.OWN])


# --- static pin (post-phase risk mitigation) ---------------------------------


class NoClientSettingsInProducerTests(unittest.TestCase):
    APPS = (SCRIPTS / "monitor" / "monitor_app.py",
            SCRIPTS / "monitor" / "minimonitor_app.py")

    def test_the_producer_holds_no_client_setting(self):
        mon = TmuxMonitor(session="demo")
        self.assertFalse(hasattr(mon, "multi_session"))
        self.assertFalse(hasattr(mon, "exclude_pane"))
        src = (SCRIPTS / "monitor" / "monitor_core.py").read_text()
        self.assertIsNone(re.search(r"environ[^\n]*TMUX_PANE", src),
                          "monitor_core reads $TMUX_PANE again")

    def test_no_client_reads_a_view_setting_through_the_producer(self):
        files = list(self.APPS) + sorted((SCRIPTS / "applink").glob("*.py"))
        pat = re.compile(r"_monitor\.(multi_session|exclude_pane)\b")
        hits = [f"{f.name}:{n}" for f in files
                for n, line in enumerate(f.read_text().splitlines(), 1)
                if pat.search(line)]
        self.assertEqual(hits, [])

    def test_every_snapshot_write_goes_through_the_projection(self):
        """`self._snapshots = …` / `self._snapshots[k] = …` only from
        `_project_snapshots` (or a subscript of a name bound from it)."""
        for path in self.APPS:
            tree = ast.parse(path.read_text())
            projected_names: set[str] = set()
            for node in ast.walk(tree):
                if (isinstance(node, ast.Assign) and len(node.targets) == 1
                        and isinstance(node.targets[0], ast.Name)
                        and _is_projection_call(node.value)):
                    projected_names.add(node.targets[0].id)
            writes = []
            for node in ast.walk(tree):
                targets = []
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                    targets = [node.target]
                for t in targets:
                    if _is_snapshots_target(t):
                        writes.append((node.lineno, node.value))
            with self.subTest(app=path.name):
                self.assertTrue(writes, "no snapshot write found — pin is vacuous")
                for lineno, value in writes:
                    if _is_empty_dict_init(value):
                        continue  # the `__init__` reset to {}
                    ok = _is_projection_call(value) or (
                        isinstance(value, ast.Subscript)
                        and isinstance(value.value, ast.Name)
                        and value.value.id in projected_names)
                    self.assertTrue(ok, f"{path.name}:{lineno} writes "
                                        "self._snapshots bypassing the view")


def _is_projection_call(node) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_project_snapshots")


def _is_snapshots_target(t) -> bool:
    if isinstance(t, ast.Subscript):
        t = t.value
    return (isinstance(t, ast.Attribute) and t.attr == "_snapshots"
            and isinstance(t.value, ast.Name) and t.value.id == "self")


def _is_empty_dict_init(value) -> bool:
    return isinstance(value, ast.Dict) and not value.keys


if __name__ == "__main__":
    unittest.main()
