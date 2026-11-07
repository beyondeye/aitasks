"""`ait monitor` and `ait minimonitor` read through `MonitorClient` (t2037_3).

The apps wrap their own `TmuxMonitor` in a `MonitorClient`
(`monitor_shared.build_monitor_client`). Under a shared status server the
interval tick only READS the subscription, while a user action asks the server
to scan. The scan wait is never on the App message pump (it runs in the
`scan-refresh` worker), and each scan round publishes THIS tick's skip set and
pins, flushes the pins and only then requests the scan.

Every server here is a real `StatusServer` over a fake producer, or the scripted
socket from `test_monitor_status_client`. No test reaches a tmux server:
`ensure` is injected, and the module runs with `AITASKS_MONITOR_SERVER=0` as a
safety net, so any construction this file does not control stays in-process.

Positive controls (run by hand; each must FAIL its test):

| mutation | must fail |
|---|---|
| the interval timer wired back to `self._refresh_data` (default `scan=True`) | `test_the_interval_issues_no_full_server_scans` (`AppTimerTests`): the producer's scan count grows with the ticks |
| `_request_server_scan` moved ABOVE the identity / publish block in `minimonitor_app._refresh_data` | `test_a_followed_window_that_is_parked_is_scanned_live`: `agent-b` is in the requested scan's skip set and `%2` comes back as a parked placeholder |
| `_publish_parked_agents` without its `set_capture_pins` call | `test_publish_hands_both_the_skip_set_and_the_pins_down` |
| `_cycle_compare_mode_async` notifying the sync prediction | `test_d_notifies_the_servers_answer_not_the_prediction` |

Run: python3 tests/test_monitor_apps_subscribe.py
or:  bash tests/run_all_python_tests.sh
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
if str(REPO_ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tests"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

import agent_marks  # noqa: E402
import test_monitor_status_client as cx  # noqa: E402  (module alias only)
import test_monitor_status_server as fx  # noqa: E402  (module alias only)
import monitor.minimonitor_app as mm  # noqa: E402
import monitor.monitor_app as ma  # noqa: E402
from monitor import monitor_shared as ms  # noqa: E402
from monitor import status_server as ss  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    CAPTURE_PIN_ALL, PaneCategory, PaneSnapshot, TmuxMonitor, TmuxPaneInfo,
    parked_capture_skip,
)
from monitor.status_client import ClientMode, MonitorClient, RequestFailed  # noqa: E402

SESSION = fx.SESSION
VERSION = fx.VERSION

_ENV_PATCH = mock.patch.dict(os.environ, {"AITASKS_MONITOR_SERVER": "0"})


def setUpModule() -> None:   # noqa: N802 - unittest's hook name
    _ENV_PATCH.start()


def tearDownModule() -> None:   # noqa: N802
    _ENV_PATCH.stop()


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

def pane(pane_id: str, window: str, index: str) -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index=index, window_name=window, pane_index="0", pane_id=pane_id,
        pane_pid=999991, current_command="node", width=80, height=24,
        category=PaneCategory.AGENT, session_name=SESSION,
    )


class QuietLocal(cx.FakeLocal):
    """The client's local instance: the gateway answers without any tmux."""

    async def tmux_run_async(self, args, timeout=5.0):
        self.calls.append(("tmux_run_async", tuple(args)))
        return 1, ""

    def tmux_run(self, args, timeout=5.0):
        return 1, ""

    async def discover_window_panes_async(self, window_id):
        return False, []


class SkipHonouringProducer(fx.FakeProducer):
    """A producer that honours the skip set as the real one does: a skipped
    agent commits as the parked placeholder, never with its live content."""

    def commit_snapshots(self, gen, classified):
        out = {}
        for pid, snap in self.snaps.items():
            key = (snap.pane.session_name, snap.pane.window_name)
            if key in self.skip:
                out[pid] = PaneSnapshot(pane=snap.pane, content="", timestamp=0.0,
                                        idle_seconds=0.0, is_idle=False, parked=True)
            else:
                out[pid] = snap
        return out


class ServerCase(cx.ClientCase):
    """A real `StatusServer` over a fake producer, and a store-backed marks view
    shared by the app and the server (both see the same parked set)."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.root = Path(os.path.realpath(self.root))
        self.store = self.root / "marks.json"
        self._marks_env = mock.patch.dict(
            os.environ, {agent_marks.MARKS_ENV: str(self.store)})
        self._marks_env.start()
        self.addCleanup(self._marks_env.stop)

    async def server(self, producer=None, snaps=None):
        fake = producer or fx.FakeProducer(self.root)
        fake.mapping = {SESSION: self.root}
        fake.snaps = dict(snaps or {})
        server = ss.StatusServer(
            fake, socket_path=self.sock, version=VERSION, project_root=self.root,
            grace=60.0, marks_view=agent_marks.MarksView(self.store),
            task_cache=fx.FakeTaskCache(), watchdog_interval=0.02,
            interval_override=1000.0, start_control_client=False, hello_timeout=5.0,
        )
        await server.start()
        self._servers = getattr(self, "_servers", []) + [server]
        return server, fake

    def park(self, window: str) -> None:
        mf = agent_marks.load(self.store)
        agent_marks.cycle(mf, self.root, window)   # prioritized
        agent_marks.cycle(mf, self.root, window)   # parked
        agent_marks.dump(mf, self.store)

    def server_client(self, local=None, **kw) -> MonitorClient:
        kw.setdefault("ensure", self.ensure)
        kw.setdefault("enabled", True)
        kw.setdefault("request_timeout", 5.0)
        kw.setdefault("connect_deadline", 2.0)
        kw.setdefault("backoff", (30.0,))
        kw.setdefault("ping_after", 30.0)
        kw.setdefault("kind", "test")
        c = MonitorClient(local or QuietLocal(), version=VERSION, **kw)
        self._clients = getattr(self, "_clients", []) + [c]
        return c

    def mini(self, **kw) -> mm.MiniMonitorApp:
        kw.setdefault("refresh_seconds", 999)
        return mm.MiniMonitorApp(session=SESSION, project_root=self.root, **kw)

    def full(self, **kw) -> ma.MonitorApp:
        kw.setdefault("refresh_seconds", 999)
        return ma.MonitorApp(session=SESSION, project_root=self.root, **kw)

    @staticmethod
    async def drain(app, pilot) -> None:
        """Wait for the scan worker and any refresh to finish — a worker still
        in flight at `run_test` exit fails the enclosing test."""
        for _ in range(500):
            if not app._scan_inflight and not app._refresh_inflight:
                break
            await pilot.pause(0.01)
        await pilot.pause()

    @staticmethod
    def skips_before_last_capture(fake) -> list:
        calls = fake.calls
        idx = len(calls) - 1 - calls[::-1].index("capture")
        return [c[1] for c in calls[:idx] if isinstance(c, tuple) and c[0] == "skip"]


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class WiringTests(unittest.IsolatedAsyncioTestCase):
    """Both apps build their `TmuxMonitor` as before and wrap it."""

    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    async def asyncTearDown(self):
        self._tmp.cleanup()

    async def _start(self, app_cls, **kw):
        built: dict = {}
        real_build = ms.build_monitor_client

        def build(local, **bkw):
            built.update(bkw, local=local)
            return real_build(local, **bkw)

        app = app_cls(session=SESSION, project_root=self.root, refresh_seconds=999, **kw)
        mod = ma if app_cls is ma.MonitorApp else mm
        ensure = mock.Mock(side_effect=AssertionError("ensure must not run"))
        async with app.run_test(size=(80, 24)) as pilot:
            with mock.patch.object(mod, "build_monitor_client", build), \
                    mock.patch.object(mod, "TmuxMonitor",
                                      lambda **tkw: QuietLocal()), \
                    mock.patch("monitor.status_server.ensure_server", ensure):
                app._start_monitoring()
            app._refresh_timer.stop()
            client = app._monitor
            await client.start()
            await pilot.pause()
            app._monitor = None
            await client.close()
        return built, client, ensure

    async def test_the_monitor_wraps_its_tmux_monitor(self):
        app_kw = {}
        built, client, ensure = await self._start(ma.MonitorApp, **app_kw)
        self.assertIsInstance(client, MonitorClient)
        self.assertEqual(built["kind"], "monitor")
        self.assertEqual(built["session"], SESSION)
        self.assertEqual(built["project_root"], self.root)
        self.assertEqual(built["pins"], frozenset(), "a monitor pins nothing")
        self.assertIsNone(built["enabled"], "no override: follow the env switch")
        self.assertIsInstance(built["local"], QuietLocal)
        # The env switch (module setUp) keeps it in-process: ensure never ran.
        self.assertIs(client.mode, ClientMode.FALLBACK)
        ensure.assert_not_called()

    async def test_the_minimonitor_wraps_and_pins_everything_until_confirmed(self):
        built, client, ensure = await self._start(mm.MiniMonitorApp)
        self.assertEqual(built["kind"], "minimonitor")
        self.assertIs(built["pins"], CAPTURE_PIN_ALL,
                      "an unconfirmed identity must pin everything (fail-safe)")
        self.assertIs(client.mode, ClientMode.FALLBACK)

    async def test_monitor_server_false_never_touches_the_server(self):
        with mock.patch.dict(os.environ, {"AITASKS_MONITOR_SERVER": "1"}):
            built, client, ensure = await self._start(ma.MonitorApp, monitor_server=False)
        self.assertIs(built["enabled"], False)
        self.assertIs(client.mode, ClientMode.FALLBACK)
        ensure.assert_not_called()


class MainOverrideTests(unittest.TestCase):
    """An explicit `--interval` / `--lines` keeps that instance in-process."""

    def _main(self, mod, app_name, argv) -> dict:
        captured: dict = {}

        class _App:
            def __init__(self, **kw):
                captured.update(kw)

            def run(self):
                pass

        with mock.patch.object(mod, app_name, _App), \
                mock.patch.object(sys, "argv", ["x", *argv]), \
                mock.patch.object(mod, "_detect_tmux_session", lambda: SESSION):
            mod.main()
        return captured

    def test_monitor_flags(self):
        self.assertIsNone(self._main(ma, "MonitorApp", [])["monitor_server"])
        self.assertIs(self._main(ma, "MonitorApp", ["--lines", "50"])["monitor_server"], False)
        self.assertIs(self._main(ma, "MonitorApp", ["--interval", "1"])["monitor_server"], False)

    def test_minimonitor_flags(self):
        self.assertIsNone(self._main(mm, "MiniMonitorApp", [])["monitor_server"])
        self.assertIs(self._main(mm, "MiniMonitorApp", ["-i", "2"])["monitor_server"], False)


# ---------------------------------------------------------------------------
# One refresh path, both modes
# ---------------------------------------------------------------------------

class BothModesTests(ServerCase):
    """The same producer snapshots reach `app._snapshots` alike whether they
    come from the subscription or from the in-process fallback."""

    SNAPS = {
        "%1": fx.snap(pane("%1", "agent-pick-1", "1"), "one"),
        "%2": fx.snap(pane("%2", "agent-pick-2", "2"), "two"),
    }

    async def _view(self, app, client):
        async with app.run_test(size=(100, 30)) as pilot:
            app._monitor = client
            await client.start()
            await app._refresh_data(scan=False)
            await self.drain(app, pilot)
            view = {pid: (s.pane.category, s.pane.window_name, s.content)
                    for pid, s in app._snapshots.items()}
            app._monitor = None
        return view

    async def _both(self, app_factory):
        await self.server(snaps=self.SNAPS)
        server_view = await self._view(app_factory(), self.server_client())
        local = QuietLocal()
        local.snaps = dict(self.SNAPS)
        fallback_view = await self._view(app_factory(),
                                         self.server_client(local, enabled=False))
        self.assertEqual(set(server_view), {"%1", "%2"})
        self.assertEqual(server_view, fallback_view)

    async def test_monitor(self):
        await self._both(self.full)

    async def test_minimonitor(self):
        await self._both(self.mini)


# ---------------------------------------------------------------------------
# Scan policy
# ---------------------------------------------------------------------------

class ScanPolicyTests(ServerCase):

    async def _mini_on_server(self, pilot_body, *, snaps=None):
        _, fake = await self.server(snaps=snaps or {
            "%1": fx.snap(pane("%1", "agent-pick-1", "1"), "one")})
        client = self.server_client()
        app = self.mini()
        async with app.run_test(size=(80, 24)) as pilot:
            app._monitor = client
            await client.start()
            self.assertIs(client.mode, ClientMode.SERVER)
            try:
                await pilot_body(app, pilot, client, fake)
            finally:
                await self.drain(app, pilot)
                app._monitor = None

    def _record(self, client, log, *, hold=None):
        """Wrap the client's scan-path methods to log their order."""
        flush, refresh = client.flush_pins, client.request_refresh

        async def rec_flush():
            log.append("flush_pins")
            await flush()

        async def rec_refresh(*a, **k):
            log.append("request_refresh")
            if hold is not None:
                await hold.wait()
            return await refresh(*a, **k)

        client.flush_pins = rec_flush
        client.request_refresh = rec_refresh

    async def test_a_user_refresh_returns_at_once_and_scans_in_order(self):
        async def body(app, pilot, client, fake):
            log: list = []
            self._record(client, log)
            pub = app._publish_parked_agents

            def rec_publish():
                log.append("publish")
                pub()

            app._publish_parked_agents = rec_publish
            hold = asyncio.Event()
            refresh = client.request_refresh

            async def held(*a, **k):
                await hold.wait()
                return await refresh(*a, **k)

            client.request_refresh = held
            try:
                await app._refresh_data()           # the call_later route
                self.assertTrue(app._scan_inflight, "no scan worker was started")
                self.assertFalse(app._refresh_inflight)
            finally:
                hold.set()                          # never strand the worker
            await self.drain(app, pilot)
            self.assertEqual(log, ["publish", "flush_pins", "request_refresh"])
            self.assertEqual(fake.calls.count("capture") >= 1, True)

        await self._mini_on_server(body)

    async def test_reads_never_request_a_scan(self):
        async def body(app, pilot, client, fake):
            log: list = []
            self._record(client, log)
            await app._refresh_data(scan=False)
            await app._tick_refresh()
            self.assertEqual(log, [])
            self.assertFalse(app._scan_inflight)

        await self._mini_on_server(body)

    async def test_three_quick_refreshes_coalesce_into_two_rounds(self):
        async def body(app, pilot, client, fake):
            log: list = []
            hold = asyncio.Event()
            self._record(client, log, hold=hold)
            try:
                for _ in range(3):
                    await app._refresh_data()
                    await pilot.pause()
            finally:
                hold.set()                          # never strand the worker
            await self.drain(app, pilot)
            self.assertEqual(log.count("request_refresh"), 2,
                             "one round, plus one for the calls made meanwhile")

        await self._mini_on_server(body)

    async def test_a_turned_away_round_is_re_dispatched_once(self):
        async def body(app, pilot, client, fake):
            log: list = []
            self._record(client, log)
            app._refresh_inflight = True        # a timer tick is mid-flight
            await app._refresh_data()
            await self.drain_worker_only(app, pilot)
            self.assertEqual(log, [], "the turned-away round must not scan")
            self.assertTrue(app._scan_rerun)
            # The tick's `finally` re-dispatches it exactly once.
            app._refresh_inflight = False
            app._maybe_rerun_refresh()
            await self.drain(app, pilot)
            self.assertEqual(log.count("request_refresh"), 1)
            self.assertFalse(app._scan_rerun)

        await self._mini_on_server(body)

    @staticmethod
    async def drain_worker_only(app, pilot):
        for _ in range(500):
            if not app._scan_inflight:
                break
            await pilot.pause(0.01)

    async def test_a_replaced_monitor_stops_the_round(self):
        async def body(app, pilot, client, fake):
            log: list = []
            flush = client.flush_pins
            gate = asyncio.Event()

            async def held_flush():
                await gate.wait()
                await flush()

            client.flush_pins = held_flush
            refresh = client.request_refresh

            async def rec_refresh(*a, **k):
                log.append("request_refresh")
                return await refresh(*a, **k)

            client.request_refresh = rec_refresh
            try:
                await app._refresh_data()
                await pilot.pause()
                app._monitor = SimpleNamespace()     # teardown replaced the client
            finally:
                gate.set()                           # never strand the worker
            await self.drain(app, pilot)
            self.assertEqual(log, [], "the old client was asked to scan")

        await self._mini_on_server(body)

    async def test_fallback_and_fakes_refresh_inline(self):
        local = QuietLocal()
        client = self.server_client(local, enabled=False)
        app = self.mini()
        async with app.run_test(size=(80, 24)) as pilot:
            app._monitor = client
            await client.start()
            await app._refresh_data()
            self.assertFalse(app._scan_inflight, "fallback must not start a worker")
            self.assertIn("capture_all_async", local.calls)
            app._monitor = SimpleNamespace(capture_all_async=None)
            self.assertFalse(app._wants_offpump_scan())
            app._monitor = None


# ---------------------------------------------------------------------------
# The real interval wiring issues no full server scans
# ---------------------------------------------------------------------------

class AppTimerTests(ServerCase):
    """Mount each app through its REAL `_start_monitoring` and let its real
    `set_interval` tick. The server's own tick is set to 1000 s, so every full
    scan the producer logs is one an app asked for. Monitor and minimonitor run
    one after the other against the same server (Textual drives one app per
    `run_test`)."""

    async def _ticks(self, app, fake, mod, *, user_action) -> tuple[int, int]:
        ticks = 0

        def build(local, **bkw):
            bkw["enabled"] = True
            return MonitorClient(QuietLocal(), ensure=self.ensure, version=VERSION,
                                 request_timeout=5.0, connect_deadline=2.0,
                                 backoff=(30.0,), ping_after=30.0,
                                 **{k: v for k, v in bkw.items() if k != "log"})

        async with app.run_test(size=(100, 30)) as pilot:
            real_tick = app._tick_refresh

            async def counted():
                nonlocal ticks
                ticks += 1
                await real_tick()

            app._tick_refresh = counted
            with mock.patch.object(mod, "build_monitor_client", build), \
                    mock.patch.object(mod, "TmuxMonitor", lambda **kw: QuietLocal()):
                app._start_monitoring()
            client = app._monitor
            await client.start()
            self.assertIs(client.mode, ClientMode.SERVER)
            for _ in range(100):                    # first refresh + subscribe settle
                if ticks >= 1 and not app._refresh_inflight:
                    break
                await pilot.pause(0.02)
            baseline = fake.calls.count("capture")
            seen = ticks
            for _ in range(200):
                if ticks - seen >= 5:
                    break
                await pilot.pause(0.02)
            self.assertGreaterEqual(ticks - seen, 5, "the interval never ticked")
            await self.drain(app, pilot)
            idle_scans = fake.calls.count("capture") - baseline
            user_action(app)
            await pilot.pause()
            await self.drain(app, pilot)
            action_scans = fake.calls.count("capture") - baseline - idle_scans
            app._refresh_timer.stop()
            app._monitor = None
            await client.close()
        return idle_scans, action_scans

    async def test_the_interval_issues_no_full_server_scans(self):
        _, fake = await self.server(snaps={
            "%1": fx.snap(pane("%1", "agent-pick-1", "1"), "one")})
        for app, mod, action in (
            (self.full(refresh_seconds=0.05), ma, lambda a: a.action_refresh()),
            (self.mini(refresh_seconds=0.05), mm,
             lambda a: a.call_later(a._refresh_data)),
        ):
            idle, user = await self._ticks(app, fake, mod, user_action=action)
            self.assertEqual(idle, 0, f"{mod.__name__}: the interval requested "
                                      f"{idle} full server scan(s)")
            self.assertEqual(user, 1, f"{mod.__name__}: a user action must cost "
                                      f"exactly one scan, got {user}")


# ---------------------------------------------------------------------------
# Publish before scan (the followed identity moves to a parked window)
# ---------------------------------------------------------------------------

class PublishBeforeScanTests(ServerCase):

    async def _run(self, *, confirm_on_scan: bool):
        a = pane("%1", "agent-a", "1")
        b = pane("%2", "agent-b", "2")
        self.park("agent-b")
        producer = SkipHonouringProducer(self.root)
        _, fake = await self.server(producer, snaps={
            "%1": fx.snap(a, "a-live"), "%2": fx.snap(b, "b-old")})
        client = self.server_client(pins=CAPTURE_PIN_ALL)
        app = self.mini()
        identity = {"name": "agent-a", "index": "1", "ok": True}

        async def own_info():
            if not identity["ok"]:
                return False
            app._own_window_name = identity["name"]
            app._own_window_index = identity["index"]
            return True

        result: dict = {}
        async with app.run_test(size=(80, 24)) as pilot:
            app._monitor = client
            app._update_own_window_info = own_info
            await client.start()
            await app._refresh_data(scan=False)        # tick 1: following agent-a
            await self.drain(app, pilot)
            # Between ticks: the followed window is now the PARKED agent-b.
            identity.update(name="agent-b", index="2", ok=confirm_on_scan)
            fake.snaps["%2"] = fx.snap(b, "b-fresh")
            fake.calls.clear()
            await app._refresh_data()                  # a user action
            await self.drain(app, pilot)
            result["skip"] = self.skips_before_last_capture(fake)[-1]
            result["snap"] = app._snapshots.get("%2")
            result["own"] = app._find_own_agent_snapshot()
            app._monitor = None
        return result

    async def test_a_followed_window_that_is_parked_is_scanned_live(self):
        r = await self._run(confirm_on_scan=True)
        self.assertNotIn((SESSION, "agent-b"), r["skip"],
                         "the requested scan ran under the previous tick's pin")
        self.assertIsNotNone(r["snap"])
        self.assertFalse(r["snap"].parked, "the followed agent came back parked")
        self.assertEqual(r["snap"].content, "b-fresh")
        self.assertIs(r["own"], r["snap"])

    async def test_an_unconfirmed_identity_scans_under_pin_all(self):
        r = await self._run(confirm_on_scan=False)
        self.assertEqual(r["skip"], frozenset(),
                         "an unconfirmed identity must publish CAPTURE_PIN_ALL")


# ---------------------------------------------------------------------------
# Pins and compare mode
# ---------------------------------------------------------------------------

class _RecordingMonitor:
    def __init__(self):
        self.skips: list = []
        self.pins: list = []

    def set_parked_agents(self, pairs):
        self.skips.append(frozenset(pairs))

    def set_capture_pins(self, pins):
        self.pins.append(pins)


class PinsTests(unittest.TestCase):

    def test_publish_hands_both_the_skip_set_and_the_pins_down(self):
        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        app._monitor = _RecordingMonitor()
        app._session = SESSION
        app._session_root_map = {}
        app._marks_view = SimpleNamespace(parked_windows=lambda: set())
        app._own_identity_confirmed = False
        app._own_window_name = "agent-x"
        app._publish_parked_agents()
        self.assertTrue(app._monitor.pins, "set_capture_pins was never called — "
                        "a shared server would never see this client's pins")
        self.assertIs(app._monitor.pins[-1], CAPTURE_PIN_ALL)
        app._own_identity_confirmed = True
        app._publish_parked_agents()
        self.assertEqual(app._monitor.pins[-1], frozenset({(SESSION, "agent-x")}))
        self.assertEqual(len(app._monitor.skips), 2)

    def test_the_monitor_pins_nothing(self):
        app = ma.MonitorApp.__new__(ma.MonitorApp)
        app._monitor = _RecordingMonitor()
        app._session_root_map = {}
        app._marks_view = SimpleNamespace(parked_windows=lambda: set())
        app._publish_parked_agents()
        self.assertEqual(app._monitor.pins, [frozenset()])


class CompareModeTests(ServerCase):

    async def _press_d(self, app, client, pilot, before_press=None) -> list:
        notes: list = []
        app.notify = lambda msg, **kw: notes.append((msg, kw.get("severity")))
        app._monitor = client
        await client.start()
        await app._refresh_data(scan=False)
        app._focused_pane_id = "%1"
        if isinstance(app, ma.MonitorApp):
            app._get_focused_pane_id = lambda: "%1"
        if before_press is not None:
            before_press()
        app.action_cycle_compare_mode()
        for _ in range(300):
            if notes and not app._scan_inflight and not app._refresh_inflight:
                break
            await pilot.pause(0.01)
        await self.drain(app, pilot)
        app._monitor = None
        return notes

    async def _d_answer(self, app):
        _, fake = await self.server(snaps={
            "%1": fx.snap(pane("%1", "agent-pick-1", "1"), "one")})
        client = self.server_client()

        def server_side_override():
            # The server gains an override AFTER the client's last record
            # (another client's `d`): the record still says "default", so the
            # sync prediction is "raw", while the server cycles raw -> "stripped".
            fake.overrides["%1"] = "raw"
            self.assertFalse(client.is_compare_mode_overridden("%1"))

        async with app.run_test(size=(100, 30)) as pilot:
            notes = await self._press_d(app, client, pilot, server_side_override)
        self.assertTrue(notes, "no notification")
        msg, severity = notes[0]
        self.assertIn("stripped", msg, notes)
        self.assertNotIn("raw", msg, "the prediction was notified")
        self.assertIsNone(severity)

    async def test_d_notifies_the_servers_answer_not_the_prediction(self):
        await self._d_answer(self.mini())

    async def test_d_in_the_monitor_notifies_the_servers_answer(self):
        await self._d_answer(self.full())

    async def test_a_failed_request_warns(self):
        await self.server(snaps={"%1": fx.snap(pane("%1", "agent-pick-1", "1"), "one")})
        client = self.server_client()

        async def fail(pane_id):
            raise RequestFailed("internal", "boom")

        client.cycle_compare_mode_async = fail
        app = self.mini()
        async with app.run_test(size=(80, 24)) as pilot:
            notes = await self._press_d(app, client, pilot)
        self.assertTrue(any("request failed" in m and s == "warning" for m, s in notes),
                        notes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
