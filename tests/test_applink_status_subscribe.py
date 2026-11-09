"""applink reads pane status from the shared monitor status server (t2037_4).

The real `AppLinkServer` transport (`_handle`, `_ensure_pusher`, the client
lifecycle, pins, deferred replies), the real `FrameRouter` and the real
`PushScheduler`, against either:

- the real `StatusServer` over the server tests' `FakeProducer` (module alias
  `fx`) — the reply path, partial refreshes, the skip set, compare mode; or
- the client tests' `ScriptedServer` (alias `cx`) — a reply the test holds back.

No tmux server is reached: the server's per-client local `TmuxMonitor` is built
by `_local_factory` (an `AppLocal` recorder), the base monitor is one too, and
`ensure` is injected. The producer's interval is huge, so it scans only when a
subscribe or a `refresh` asks it to, and a full scan is the `"capture"` entry in
`FakeProducer.calls`, a partial one `("capture_one", pane)`.

Positive controls, run by hand (each makes the named test fail):

| change in the code under test | failing test |
|---|---|
| `_build_client` without `client.start_detached()` | test_one_phone_leaving_mid_startup_never_strands_the_other (mode stays `connecting`) |
| `_refresh_targets` restricted to focused + forced panes | test_a_read_only_fast_cadence_gets_fresh_content_before_any_background_scan (stale content) |
| due-ness from `st.last_send_t` instead of `st.last_refresh_t` | same test, the unchanged-output leg (one refresh per pass) |
| `request_refresh` before `_publish_pins` / `flush_pins` | test_a_streamed_parked_pane_is_pinned_before_its_refresh |
| `_publish_pins` only from the push pass (drop the `_handle` calls) | test_pins_follow_pause_resume_empty_roster_and_removal_without_any_push_pass |
| restart gate through `capture_pane` instead of `status_snapshot` | test_restart_gate_reads_the_servers_idle_clock |
| router `cycle_compare_mode` always sync (no DeferredReply) | test_compare_mode_answer_is_the_servers_and_never_holds_the_read_loop |
| parked guard as `force.discard` only (no baseline reset / resync mark) | test_live_parked_live_with_unchanged_content_resyncs_with_a_keyframe (`[1]`), test_live_parked_live_with_changed_content_resyncs_with_a_keyframe (`[1, 2]`) |
| `_spawn_deferred` without its admission check | test_a_burst_against_a_silent_server_stays_bounded (50 tasks in flight) |

Run:
  python3 tests/test_applink_status_subscribe.py
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent / ".aitask-scripts"
APPLINK = SCRIPTS / "applink"
for _p in (str(APPLINK), str(SCRIPTS), str(SCRIPTS / "lib"), str(TESTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    import msgpack  # noqa: F401
    import yaml  # noqa: F401
except ImportError as exc:  # pragma: no cover - environment without the applink deps
    raise unittest.SkipTest(f"applink deps missing: {exc}")

import test_monitor_status_client as cx  # noqa: E402  (module alias only)
import test_monitor_status_server as fx  # noqa: E402  (module alias only)
import content as C  # noqa: E402
import paths  # noqa: E402
import profiles as P  # noqa: E402
import router as RT  # noqa: E402
import server as SV  # noqa: E402
import sessions as S  # noqa: E402
from monitor import status_client as sc  # noqa: E402
from monitor import status_protocol as sp  # noqa: E402
from monitor import status_server as ss  # noqa: E402
from monitor.monitor_core import _parked_snapshot  # noqa: E402

SESSION = fx.SESSION
wait_until = fx.wait_until
T0 = 1000.0


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class AppLocal(cx.FakeLocal):
    """The local `TmuxMonitor` slice applink reaches, with a call log."""

    def __init__(self):
        super().__init__()
        self.snaps = {}

    async def capture_cursor_async(self, pane_id):
        self.calls.append(("cursor", pane_id))
        return (0, 0, True, 0)

    def capture_pane(self, pane_id, capture_lines=None):
        self.calls.append(("capture_pane", pane_id))
        return self.snaps.get(pane_id)

    async def capture_pane_content_async(self, pane_id, capture_lines=None):
        self.calls.append(("capture_content", pane_id))
        return None

    def get_pane_option_sync(self, pane_id, option):
        return True, ""

    def switch_to_pane(self, pane_id, prefer_companion=False):
        self.calls.append(("switch", pane_id))
        return True

    def captures(self) -> list:
        return [c for c in self.calls if c in ("capture_all_async", "capture_all_classified_async")
                or (isinstance(c, tuple) and c[0] in ("capture_one", "capture_pane"))]


class ParkingProducer(fx.FakeProducer):
    """`FakeProducer` that honours the skip set the way `TmuxMonitor` does: a
    skipped agent's snapshot is the empty parked placeholder."""

    def _view(self, snaps):
        out = {}
        for pid, s in snaps.items():
            pair = (s.pane.session_name, s.pane.window_name)
            out[pid] = _parked_snapshot(s.pane, 0.0) if pair in self.skip else s
        return out

    def commit_snapshots(self, gen, classified):
        return self._view(self.snaps)

    def commit_snapshot(self, gen, p, content, result):
        return self._view({p.pane_id: self.snaps[p.pane_id]}).get(p.pane_id) \
            if p.pane_id in self.snaps else None


class FakeWS:
    """A websocket for `_handle`: frames the test pushes, sends it records."""

    remote_address = ("10.0.0.5", 4321)

    def __init__(self):
        self.inbox: asyncio.Queue = asyncio.Queue()
        self.sent: list = []
        self.closed = False
        self.sent_after_close = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = await self.inbox.get()
        if item is None:
            raise StopAsyncIteration
        return item

    async def send(self, data):
        if self.closed:
            self.sent_after_close += 1
            raise ConnectionError("closed")
        self.sent.append(data)

    async def close(self):
        if not self.closed:
            self.closed = True
            self.inbox.put_nowait(None)

    def push(self, frame: dict):
        self.inbox.put_nowait(json.dumps(frame))

    def texts(self) -> list:
        return [json.loads(d) for d in self.sent if isinstance(d, str)]

    def reply(self, msg_id):
        for f in self.texts():
            if f.get("id") == msg_id and f.get("kind") in ("res", "err"):
                return f
        return None

    def statuses(self, pane_id) -> list:
        return [f["payload"] for f in self.texts()
                if f.get("verb") == "pane_status" and f["payload"]["pane_id"] == pane_id]

    def content_frames(self, pane_id) -> list:
        out = []
        for d in self.sent:
            if isinstance(d, (bytes, bytearray)) and d[0] in (
                    C.FRAME_KEYFRAME, C.FRAME_DELTA, C.FRAME_APPEND):
                body = msgpack.unpackb(d[1:], raw=False, strict_map_key=False)
                if body[0] == pane_id:
                    out.append(bytes(d))
        return out


class FakeTasks:
    """The TaskInfoCache slice the router's restart gate reads."""

    def get_task_id_for_pane(self, pane):
        return "42"

    def invalidate(self, task_id, session_name=""):
        pass

    def get_task_info(self, task_id, session_name=""):
        return SimpleNamespace(title="t", status="Implementing")


def req(msg_id, verb, payload, bearer):
    return {"v": 1, "id": msg_id, "kind": "req", "verb": verb,
            "payload": payload, "auth": bearer}


def unavailable(**kw):
    return ss.EnsureResult("UNAVAILABLE", "no_tmux_server", None)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

class AppLinkCase(cx.ClientCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.locals: list = []
        self.handles: list = []
        self.gate = P.ProfileGate.load(paths.profiles_dir())

    async def asyncTearDown(self):
        for ws, task in self.handles:
            await ws.close()
            with __import__("contextlib").suppress(Exception):
                await asyncio.wait_for(task, 5.0)
        srv = getattr(self, "srv", None)
        if srv is not None and srv._client is not None:
            await srv._client.close()
        await super().asyncTearDown()

    def make_server(self, *, enabled=True, ensure=..., tasks=None) -> SV.AppLinkServer:
        srv = SV.AppLinkServer.__new__(SV.AppLinkServer)
        srv._conns, srv._live, srv._pushers, srv._conns_by_ip = set(), {}, {}, {}
        srv._audit = logging.getLogger("applink.audit.test")
        srv._on_change = None
        srv._sessions = S.SessionTable(self.root / "sessions", persist=False)
        srv.tunnel = None
        srv._own_pane = None
        srv._task_cache = tasks
        srv._history_capture_lines = 2000
        srv._monitor = AppLocal()
        srv._router = RT.FrameRouter(srv._sessions, self.gate, srv._monitor,
                                     audit=srv._audit, task_resolver=tasks)
        srv._use_status_server = enabled
        srv._client = None
        srv._client_ensure = self.ensure if ensure is ... else ensure
        srv._client_config = {}
        srv._project_root = self.root
        srv._deferred = {}
        srv._status_log = None

        def local():
            lo = AppLocal()
            self.locals.append(lo)
            return lo
        srv._local_factory = local
        self.srv = srv
        return srv

    def bearer(self, profile="monitor_control") -> str:
        return self.srv._sessions.issue_bearer(profile).bearer

    def connect(self) -> FakeWS:
        ws = FakeWS()
        task = asyncio.create_task(self.srv._handle(ws))
        self.handles.append((ws, task))
        return ws

    async def disconnect(self, ws):
        await ws.close()
        for w, task in self.handles:
            if w is ws:
                await asyncio.wait_for(task, 5.0)

    async def three_panes(self, producer=fx.FakeProducer, **snaps):
        fake = producer(self.root)
        fake.snaps = {
            "%1": fx.snap(fx.pane("%1", "agent-a"), "content-a"),
            "%2": fx.snap(fx.pane("%2", "agent-b"), "content-b"),
            "%3": fx.snap(fx.pane("%3", "agent-c"), "content-c"),
        }
        fake.snaps.update(snaps)
        marks = fx.FakeMarks()
        server = ss.StatusServer(
            fake, socket_path=self.sock, version=fx.VERSION, project_root=self.root,
            grace=60.0, marks_view=marks, task_cache=fx.FakeTaskCache(),
            watchdog_interval=0.02, interval_override=1000.0,
            start_control_client=False, hello_timeout=5.0,
        )
        await server.start()
        self._servers = getattr(self, "_servers", []) + [server]
        return server, fake, marks

    async def scheduler(self, payload, *, profile="monitor_control", clock=None,
                        publish=True):
        """A subscribed connection and its (unstarted) push scheduler on the
        shared client, so the test drives `_run_once` with its own clock."""
        srv = self.srv
        client = srv._acquire_status_monitor()
        await client.start()
        conn = RT.ConnState()
        reply = srv._router.handle(req("s", "subscribe", payload, self.bearer(profile)), conn)
        self.assertEqual(reply["kind"], "res", reply)
        ws = FakeWS()
        now = clock or {"t": T0}
        sched = SV.PushScheduler(
            conn, ws, client, clock=lambda: now["t"], audit=srv._audit,
            publish_pins=srv._publish_pins if publish else None)
        srv._pushers[conn] = sched
        return client, conn, ws, sched, now

    def realroot(self) -> str:
        return os.path.realpath(str(self.root))


def captures_one(fake) -> list:
    return [c[1] for c in fake.calls if isinstance(c, tuple) and c[0] == "capture_one"]


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

class LifecycleTests(AppLinkCase):

    async def test_one_client_per_streaming_period(self):
        await self.three_panes()
        srv = self.make_server()
        bearer = self.bearer()
        self.assertIsNone(srv._client)

        a = self.connect()
        a.push(req("a1", "subscribe", {"panes": ["%1"]}, bearer))
        await wait_until(lambda: srv._client is not None)
        client = srv._client
        self.assertIsInstance(client, sc.MonitorClient)
        self.assertEqual(client._kind, "applink")
        self.assertFalse(client._include_shadows)
        self.assertIs(srv._router._monitor, client)
        self.assertIs(client._local, self.locals[0])
        self.assertIsNot(client._local, srv._monitor, "a fresh local, not the base one")

        b = self.connect()
        b.push(req("b1", "subscribe", {"panes": ["%2"]}, bearer))
        await wait_until(lambda: len(srv._pushers) == 2)
        self.assertIs(srv._client, client, "the second phone shares the client")

        await self.disconnect(a)
        self.assertIs(srv._client, client, "one phone left, one still streams")
        await self.disconnect(b)
        self.assertIsNone(srv._client)
        self.assertTrue(client._closed)
        self.assertIs(srv._router._monitor, srv._monitor)

        c = self.connect()
        c.push(req("c1", "subscribe", {"panes": ["%1"]}, bearer))
        await wait_until(lambda: srv._client is not None)
        self.assertIsNot(srv._client, client)
        self.assertIs(srv._client._local, self.locals[1])

    async def test_disabled_keeps_the_in_process_monitor(self):
        srv = self.make_server(enabled=False)
        bearer = self.bearer()
        a = self.connect()
        a.push(req("a1", "subscribe", {"panes": ["%1"]}, bearer))
        await wait_until(lambda: srv._pushers)
        self.assertIsNone(srv._client)
        self.assertIs(next(iter(srv._pushers.values()))._monitor, srv._monitor)
        self.assertEqual(self.locals, [])
        self.assertEqual(self.ensure.calls, 0)

    async def test_one_phone_leaving_mid_startup_never_strands_the_other(self):
        """Phone A's push loop is cancelled while the shared client is still
        starting; phone B must end up on a subscribed client."""
        await self.three_panes()
        held = cx.HeldEnsure(self.ensure)
        srv = self.make_server(ensure=held)
        bearer = self.bearer()
        a = self.connect()
        a.push(req("a1", "subscribe", {"panes": ["%1"]}, bearer))
        await asyncio.to_thread(held.entered.wait, 3.0)
        b = self.connect()
        b.push(req("b1", "subscribe", {"panes": ["%1"]}, bearer))
        await wait_until(lambda: len(srv._pushers) == 2)
        client = srv._client
        await self.disconnect(a)
        self.assertIs(srv._client, client)
        held.release.set()
        await wait_until(lambda: client.mode is sc.ClientMode.SERVER)
        await wait_until(lambda: b.statuses("%1"))
        self.assertEqual(client._local.captures(), [], "status came from the subscription")
        await self.disconnect(b)
        self.assertIsNone(srv._client)
        self.assertTrue(client._closed)

    async def test_one_phone_leaving_mid_startup_still_reaches_fallback(self):
        held = cx.HeldEnsure(unavailable)
        srv = self.make_server(ensure=held)
        bearer = self.bearer()
        a = self.connect()
        a.push(req("a1", "subscribe", {"panes": ["%1"]}, bearer))
        await asyncio.to_thread(held.entered.wait, 3.0)
        b = self.connect()
        b.push(req("b1", "subscribe", {"panes": ["%1"]}, bearer))
        await wait_until(lambda: len(srv._pushers) == 2)
        client = srv._client
        await self.disconnect(a)
        held.release.set()
        await wait_until(lambda: client.mode is sc.ClientMode.FALLBACK)
        self.assertIsNotNone(client._reconnect_task)
        self.assertFalse(client._reconnect_task.done())


# ---------------------------------------------------------------------------
# The push loop on the shared client
# ---------------------------------------------------------------------------

class PushTests(AppLinkCase):

    async def test_status_comes_from_the_subscription(self):
        _, fake, _ = await self.three_panes()
        self.make_server()
        client, conn, ws, sched, now = await self.scheduler(
            {"panes": ["%1", "%2"], "cadence_idle_ms": 60000})
        await sched._run_once()                      # the forced subscribe pass
        base_full = fake.calls.count("capture")
        base_one = len(captures_one(fake))
        status = ws.statuses("%1")[-1]
        self.assertEqual(status["window_name"], "agent-a")
        self.assertEqual(status["idle_seconds"], 1.0)
        for i in range(5):
            now["t"] = T0 + 1 + i
            await sched._run_once()
        self.assertEqual(fake.calls.count("capture"), base_full, "no full scan per pass")
        self.assertEqual(len(captures_one(fake)), base_one, "no refresh per pass")
        self.assertEqual(client._local.captures(), [], "the local instance never scans")

    async def test_a_read_only_fast_cadence_gets_fresh_content_before_any_background_scan(self):
        _, fake, _ = await self.three_panes()
        srv = self.make_server()
        client, conn, ws, sched, now = await self.scheduler(
            {"panes": ["%1", "%2"], "content_panes": ["%1"], "cadence_idle_ms": 500},
            profile="read_only")
        focus = srv._router.handle(req("f", "focus", {"pane_id": "%1"},
                                       conn.session.bearer), conn)
        self.assertEqual(focus["payload"]["code"], RT.ERR_PERMISSION_DENIED)

        fake.calls.clear()
        await sched._run_once()                      # t=0: the forced subscribe pass
        self.assertEqual(captures_one(fake), ["%1"])
        base_full = fake.calls.count("capture")

        now["t"] = T0 + 0.25                         # not due
        await sched._run_once()
        self.assertEqual(captures_one(fake), ["%1"])

        fake.snaps["%1"] = fx.snap(fx.pane("%1", "agent-a"), "fresh-output-xyz")
        now["t"] = T0 + 0.5                          # due: one partial capture of A
        await sched._run_once()
        self.assertEqual(captures_one(fake), ["%1", "%1"])
        self.assertTrue(any(b"fresh-output-xyz" in f for f in ws.content_frames("%1")),
                        "the phone did not get A's new content")
        self.assertEqual(fake.calls.count("capture"), base_full,
                         "the fresh content must not wait for a background scan")
        self.assertNotIn("%2", captures_one(fake), "a status-only pane was captured")
        self.assertNotIn("%3", captures_one(fake), "an unrelated pane was captured")

        for t in (0.625, 0.75, 0.875):               # unchanged output, not due again
            now["t"] = T0 + t
            await sched._run_once()
        self.assertEqual(captures_one(fake), ["%1", "%1"], "one refresh per pass")
        now["t"] = T0 + 1.0                          # one per cadence
        await sched._run_once()
        self.assertEqual(captures_one(fake), ["%1", "%1", "%1"])
        # Nothing was sent at 1.0 (unchanged output), so a send-driven clock
        # would call A due again on every pass from here; the attempt clock
        # waits a full cadence.
        for t in (1.125, 1.25, 1.375):
            now["t"] = T0 + t
            await sched._run_once()
        self.assertEqual(captures_one(fake), ["%1", "%1", "%1"],
                         "unchanged output re-requested on every pass")

    async def test_a_focused_pane_refreshes_at_the_focused_cadence(self):
        _, fake, _ = await self.three_panes()
        srv = self.make_server()
        client, conn, ws, sched, now = await self.scheduler(
            {"panes": ["%1", "%2"], "cadence_idle_ms": 60000})
        srv._router.handle(req("f", "focus", {"pane_id": "%1"}, conn.session.bearer), conn)
        fake.calls.clear()
        await sched._run_once()                      # forced: both panes
        self.assertEqual(sorted(captures_one(fake)), ["%1", "%2"])
        now["t"] = T0 + 0.25
        await sched._run_once()
        self.assertEqual(len(captures_one(fake)), 2)
        now["t"] = T0 + 0.375                        # the 300 ms focused cadence
        await sched._run_once()
        self.assertEqual(captures_one(fake)[2:], ["%1"])

    async def test_due_panes_share_one_request_after_the_pins(self):
        await self.three_panes()
        self.make_server()
        client, conn, ws, sched, now = await self.scheduler(
            {"panes": ["%1", "%2"], "cadence_idle_ms": 500})
        order: list = []
        for name in ("set_capture_pins", "flush_pins", "request_refresh",
                     "capture_all_async"):
            orig = getattr(client, name)

            def spy(*a, _orig=orig, _name=name, **kw):
                order.append((_name, kw.get("panes")))
                return _orig(*a, **kw)
            setattr(client, name, spy)
        await sched._run_once()
        names = [n for n, _ in order]
        self.assertEqual(names, ["set_capture_pins", "flush_pins", "request_refresh",
                                 "capture_all_async"])
        refreshes = [p for n, p in order if n == "request_refresh"]
        self.assertEqual(refreshes, [["%1", "%2"]], "one batched request")

    async def test_forced_panes_refresh_once_and_a_gone_pane_never(self):
        _, fake, _ = await self.three_panes()
        self.make_server()
        client, conn, ws, sched, now = await self.scheduler(
            {"panes": ["%1", "%7"], "cadence_idle_ms": 60000})
        fake.calls.clear()
        await sched._run_once()
        self.assertEqual(captures_one(fake), ["%1"], "%7 is not in the subscription view")
        now["t"] = T0 + 1
        await sched._run_once()
        self.assertEqual(captures_one(fake), ["%1"])
        conn.subscription.request_keyframe("%1")
        now["t"] = T0 + 2
        await sched._run_once()
        self.assertEqual(captures_one(fake), ["%1", "%1"])

    async def test_fallback_scans_in_process_with_no_requests(self):
        self.make_server(ensure=unavailable)
        client, conn, ws, sched, now = await self.scheduler({"panes": ["%9"]})
        self.assertIs(client.mode, sc.ClientMode.FALLBACK)
        client._local.snaps = {"%9": fx.snap(fx.pane("%9", "agent-local"), "local")}
        await sched._run_once()
        self.assertIn("capture_all_async", client._local.calls)
        self.assertTrue(ws.statuses("%9"))


# ---------------------------------------------------------------------------
# Pins and the parked view
# ---------------------------------------------------------------------------

class PinsTests(AppLinkCase):

    def applink_pins(self, server):
        pins = [c.pins for c in server._connections if c.pins_active]
        self.assertEqual(len(pins), 1, pins)
        return pins[0]

    async def test_a_streamed_parked_pane_is_pinned_before_its_refresh(self):
        _, fake, marks = await self.three_panes(ParkingProducer)
        marks.parked = {(self.realroot(), "agent-a"), (self.realroot(), "agent-b")}
        self.make_server()
        client, conn, ws, sched, now = await self.scheduler(
            {"panes": ["%1", "%2"], "content_panes": ["%1"], "cadence_idle_ms": 60000})
        fake.calls.clear()
        await sched._run_once()
        at = fake.calls.index(("capture_one", "%1"))
        skips = [c[1] for c in fake.calls[:at] if isinstance(c, tuple) and c[0] == "skip"]
        self.assertTrue(skips, fake.calls)
        self.assertNotIn((SESSION, "agent-a"), skips[-1], "the refresh ran under old pins")
        self.assertIn((SESSION, "agent-b"), skips[-1], "a status-only pane was pinned")
        self.assertTrue(any(b"content-a" in f for f in ws.content_frames("%1")))
        self.assertEqual(ws.content_frames("%2"), [], "a parked status-only pane streamed")
        status_b = ws.statuses("%2")[-1]
        self.assertFalse(status_b["is_idle"])
        self.assertEqual(status_b["idle_seconds"], 0.0)

    async def test_a_parked_agent_pinned_only_by_another_client_stays_parked_here(self):
        server, fake, marks = await self.three_panes(
            ParkingProducer,
            **{"%3": dataclasses.replace(fx.snap(fx.pane("%3", "agent-c"), "content-c"),
                                         idle_seconds=7.0, is_idle=True)})
        marks.parked = {(self.realroot(), "agent-c")}
        other = await fx.Client.open(self.sock)
        self.addAsyncCleanup(other.close)
        await other.hello()
        await other.send({"type": "subscribe", "pins": [[SESSION, "agent-c"]]})
        self.assertEqual((await other.recv())["type"], "snapshot")
        self.make_server()
        client, conn, ws, sched, now = await self.scheduler(
            {"panes": ["%3"], "content_panes": [], "cadence_idle_ms": 60000})
        await client.request_refresh()               # %3 is live in the stream
        self.assertFalse(client.status_snapshot("%3").parked)
        await sched._run_once()
        status = ws.statuses("%3")[-1]
        self.assertFalse(status["is_idle"], "another subscriber's pin leaked live data")
        self.assertEqual(status["idle_seconds"], 0.0)

    async def test_a_parked_placeholder_never_becomes_a_content_frame(self):
        _, fake, marks = await self.three_panes(ParkingProducer)
        marks.parked = {(self.realroot(), "agent-a")}
        self.make_server()
        client, conn, ws, sched, now = await self.scheduler(
            {"panes": ["%1"], "cadence_idle_ms": 500}, publish=False)
        await sched._run_once()                      # unpinned: the placeholder
        self.assertTrue(ws.statuses("%1"))
        self.assertEqual(ws.content_frames("%1"), [])
        self.assertNotIn("%1", conn.subscription.force)
        client.set_capture_pins({(SESSION, "agent-a")})
        now["t"] = T0 + 0.5
        await sched._run_once()
        frames = ws.content_frames("%1")
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0][0], C.FRAME_KEYFRAME, "the first live frame is a keyframe")
        self.assertIn(b"content-a", frames[0])

    async def _live_parked_live(self, *, change: bool) -> list:
        """Stream %1 live, request a recovery keyframe, let the refresh meet a
        parked placeholder (pins dropped), then go live again. Returns the frame
        types sent for %1."""
        # Several rows, of which a change touches ONE: a one-row pane would go
        # out as a keyframe anyway (the delta cost rule), hiding a lost resync.
        rows = "".join(f"row {i}\n" for i in range(8))
        _, fake, marks = await self.three_panes(
            ParkingProducer, **{"%1": fx.snap(fx.pane("%1", "agent-a"), rows)})
        marks.parked = {(self.realroot(), "agent-a")}
        self.make_server()
        client, conn, ws, sched, now = await self.scheduler(
            {"panes": ["%1"], "cadence_idle_ms": 500}, publish=False)
        pinned = {(SESSION, "agent-a")}
        client.set_capture_pins(pinned)
        await client.flush_pins()
        await sched._run_once()                      # live keyframe (the baseline)
        self.assertEqual([f[0] for f in ws.content_frames("%1")], [C.FRAME_KEYFRAME])

        conn.subscription.request_keyframe("%1")     # a recovery request ...
        client.set_capture_pins(frozenset())         # ... that meets a placeholder
        await client.flush_pins()
        now["t"] = T0 + 0.5
        await sched._run_once()
        self.assertTrue(client.status_snapshot("%1").parked)
        self.assertEqual(len(ws.content_frames("%1")), 1, "a placeholder was streamed")

        if change:
            fake.snaps["%1"] = fx.snap(fx.pane("%1", "agent-a"),
                                       rows.replace("row 7", "row 7 moved on"))
        client.set_capture_pins(pinned)
        await client.flush_pins()
        now["t"] = T0 + 1.0                          # due: refreshed live again
        await sched._run_once()
        self.assertFalse(client.status_snapshot("%1").parked)
        return [f[0] for f in ws.content_frames("%1")]

    async def test_live_parked_live_with_unchanged_content_resyncs_with_a_keyframe(self):
        """Positive control (recorded): the guard without the resync mark (only
        `force.discard`) sends nothing here — the hash is unchanged."""
        self.assertEqual(await self._live_parked_live(change=False),
                         [C.FRAME_KEYFRAME, C.FRAME_KEYFRAME])

    async def test_live_parked_live_with_changed_content_resyncs_with_a_keyframe(self):
        """Positive control (recorded): the guard without the resync mark sends
        a delta (types [1, 2]) against a baseline the phone may not hold."""
        self.assertEqual(await self._live_parked_live(change=True),
                         [C.FRAME_KEYFRAME, C.FRAME_KEYFRAME])

    async def test_pins_follow_pause_resume_empty_roster_and_removal_without_any_push_pass(self):
        server, fake, marks = await self.three_panes()
        marks.parked = {(self.realroot(), "agent-a"), (self.realroot(), "agent-b")}
        srv = self.make_server()
        bearer = self.bearer()
        wa, wb = (SESSION, "agent-a"), (SESSION, "agent-b")
        with mock.patch.object(SV.PushScheduler, "start", lambda self: None):
            a = self.connect()
            a.push(req("a1", "subscribe", {"panes": ["%1"]}, bearer))
            b = self.connect()
            b.push(req("b1", "subscribe", {"panes": ["%2"]}, bearer))
            await wait_until(lambda: len(srv._pushers) == 2)
            client = srv._client
            await client.start()
            srv._publish_pins()                      # setup: the client now serves
            await wait_until(lambda: self.applink_pins(server) == {wa, wb})

            a.push(req("a2", "pause", {}, bearer))
            await wait_until(lambda: self.applink_pins(server) == {wb})
            a.push(req("a3", "resume", {}, bearer))
            await wait_until(lambda: self.applink_pins(server) == {wa, wb})
            b.push(req("b2", "subscribe", {"panes": ["%bogus"]}, bearer))
            await wait_until(lambda: self.applink_pins(server) == {wa})
            b.push(req("b3", "pause", {}, bearer))
            await self.disconnect(a)
            await wait_until(lambda: self.applink_pins(server) == frozenset())
            await self.disconnect(b)
            self.assertIsNone(srv._client)
            self.assertTrue(client._closed)


# ---------------------------------------------------------------------------
# Router: the restart gate and the deferred compare answer
# ---------------------------------------------------------------------------

class RouterTests(AppLinkCase):

    async def test_restart_gate_reads_the_servers_idle_clock(self):
        idle = dataclasses.replace(fx.snap(fx.pane("%1", "agent-a"), "x"),
                                   idle_seconds=42.0, is_idle=True)
        await self.three_panes(**{"%1": idle})
        srv = self.make_server(tasks=FakeTasks())
        client = srv._acquire_status_monitor()
        await client.start()
        conn = RT.ConnState()
        bearer = self.bearer("full")
        r = srv._router.handle(req("r1", "restart_task", {"pane_id": "%1"}, bearer), conn)
        self.assertEqual(r["kind"], "res", r)
        self.assertTrue(r["payload"]["confirm_required"])
        self.assertEqual(r["payload"]["idle_seconds"], 42.0)
        r = srv._router.handle(req("r2", "restart_task", {"pane_id": "%2"}, bearer), conn)
        self.assertEqual(r["payload"]["detail"]["reason"], "not_idle")
        self.assertNotIn(("capture_pane", "%1"), client._local.calls)

    async def test_restart_gate_in_fallback_is_the_local_capture(self):
        srv = self.make_server(ensure=unavailable, tasks=FakeTasks())
        client = srv._acquire_status_monitor()
        await client.start()
        client._local.snaps = {"%9": dataclasses.replace(
            fx.snap(fx.pane("%9", "agent-z"), "x"), is_idle=True)}
        r = srv._router.handle(req("r1", "restart_task", {"pane_id": "%9"},
                                   self.bearer("full")), RT.ConnState())
        self.assertTrue(r["payload"]["confirm_required"], r)
        self.assertIn(("capture_pane", "%9"), client._local.calls)

    async def test_compare_mode_answer_is_the_servers_and_never_holds_the_read_loop(self):
        srv_s = await self.scripted()
        self.make_server()
        bearer = self.bearer()
        ws = self.connect()
        ws.push(req("s1", "subscribe", {"panes": ["%1"], "cadence_idle_ms": 60000}, bearer))
        sub = await srv_s.expect("subscribe")
        srv_s.write(cx.snapshot(1, {"%1": cx.rec("%1")}, id=sub["id"]))
        ref = await srv_s.expect("refresh")          # the forced subscribe pass
        srv_s.write(cx.delta(2))
        srv_s.write({"type": "result", "ts": 1.0, "request": "refresh",
                     "id": ref["id"], "gen": 2})

        ws.push(req("c1", "cycle_compare_mode", {"pane_id": "%1"}, bearer))
        held = await srv_s.expect("cycle_compare_mode")
        ws.push(req("k1", "send_keys", {"pane_id": "%1", "keys": "x"}, bearer))
        await wait_until(lambda: ws.reply("k1") is not None)
        self.assertIsNone(ws.reply("c1"), "the compare answer was not deferred")
        srv_s.write({"type": "result", "ts": 1.0, "request": "cycle_compare_mode",
                     "id": held["id"], "mode": "stripped", "following_default": False})
        await wait_until(lambda: ws.reply("c1") is not None)
        res = ws.reply("c1")
        self.assertEqual(res["kind"], "res")
        self.assertEqual(res["payload"], {"mode": "stripped", "following_default": False},
                         "the server's answer, not the prediction (raw)")

        ws.push(req("c2", "cycle_compare_mode", {"pane_id": "%1"}, bearer))
        held = await srv_s.expect("cycle_compare_mode")
        srv_s.write({"type": "error", "ts": 1.0, "id": held["id"], "code": "bad_pane",
                     "message": "no such pane", "request": "cycle_compare_mode"})
        await wait_until(lambda: ws.reply("c2") is not None)
        err = ws.reply("c2")
        self.assertEqual(err["kind"], "err")
        self.assertEqual(err["payload"]["code"], RT.ERR_INTERNAL)
        self.assertEqual(err["payload"]["detail"]["reason"], "RequestFailed")

        ws.push(req("c3", "cycle_compare_mode", {"pane_id": "%1"}, bearer))
        await srv_s.expect("cycle_compare_mode")
        await wait_until(lambda: self.srv._deferred and any(self.srv._deferred.values()))
        tasks = [t for ts in self.srv._deferred.values() for t in ts]
        await self.disconnect(ws)
        for t in tasks:
            self.assertTrue(t.done())
        await asyncio.sleep(0.1)
        self.assertIsNone(ws.reply("c3"))
        self.assertEqual(ws.sent_after_close, 0)

    async def test_a_burst_against_a_silent_server_stays_bounded(self):
        """Positive control (recorded): without the admission check every one of
        the burst's requests becomes a task and a pending status-server request."""
        srv_s = await self.scripted()
        self.make_server()
        bearer = self.bearer()
        ws = self.connect()
        ws.push(req("s1", "subscribe", {"panes": ["%1"], "cadence_idle_ms": 60000}, bearer))
        sub = await srv_s.expect("subscribe")
        srv_s.write(cx.snapshot(1, {"%1": cx.rec("%1")}, id=sub["id"]))
        ref = await srv_s.expect("refresh")
        srv_s.write(cx.delta(2))
        srv_s.write({"type": "result", "ts": 1.0, "request": "refresh",
                     "id": ref["id"], "gen": 2})
        client = self.srv._client
        await wait_until(lambda: not client._link.pending)

        burst = 50
        for i in range(burst):                       # the server answers none of them
            ws.push(req(f"c{i}", "cycle_compare_mode", {"pane_id": "%1"}, bearer))
        ws.push(req("k1", "send_keys", {"pane_id": "%1", "keys": "x"}, bearer))
        await wait_until(lambda: ws.reply("k1") is not None)
        self.assertEqual(ws.reply("k1")["payload"], {"ok": True}, "ordinary input stalled")
        limit = SV.MAX_DEFERRED_PER_CONN
        in_flight = [t for ts in self.srv._deferred.values() for t in ts if not t.done()]
        self.assertEqual(len(in_flight), limit)
        await wait_until(lambda: len(client._link.pending) == limit)
        await asyncio.sleep(0.1)
        self.assertEqual(len(client._link.pending), limit, "pending requests grew")
        refused = [ws.reply(f"c{i}") for i in range(limit, burst)]
        self.assertTrue(all(r is not None and r["kind"] == "err" for r in refused))
        self.assertEqual({r["payload"]["detail"]["reason"] for r in refused},
                         {"too_many_pending"})

        held = [m for m in srv_s.drain() if m["type"] == "cycle_compare_mode"]
        self.assertEqual(len(held), limit)
        for m in held:
            srv_s.write({"type": "result", "ts": 1.0, "request": "cycle_compare_mode",
                         "id": m["id"], "mode": "raw", "following_default": False})
        await wait_until(lambda: all(ws.reply(f"c{i}") is not None for i in range(limit)))
        self.assertTrue(all(ws.reply(f"c{i}")["kind"] == "res" for i in range(limit)))
        await wait_until(lambda: not any(self.srv._deferred.get(c) for c in self.srv._deferred))
        ws.push(req("again", "cycle_compare_mode", {"pane_id": "%1"}, bearer))
        m = await srv_s.expect("cycle_compare_mode")
        srv_s.write({"type": "result", "ts": 1.0, "request": "cycle_compare_mode",
                     "id": m["id"], "mode": "stripped", "following_default": False})
        await wait_until(lambda: ws.reply("again") is not None)
        self.assertEqual(ws.reply("again")["kind"], "res", "admission did not recover")

    async def test_the_in_process_monitor_keeps_the_sync_answer(self):
        srv = self.make_server(enabled=False)
        r = srv._router.handle(req("c1", "cycle_compare_mode", {"pane_id": "%1"},
                                   self.bearer()), RT.ConnState())
        self.assertEqual(r["kind"], "res")
        self.assertEqual(r["payload"], {"mode": "raw", "following_default": False})


if __name__ == "__main__":
    unittest.main(verbosity=2)
