"""In-process tests for `MonitorClient`, the subscription-backed TmuxMonitor (t2037_2).

No tmux server is reached. Two kinds of server stand in for the shared status
server:

- `ScriptedServer` — a real asyncio Unix server whose every line the test writes
  by hand (raw bytes for the malformed cases). It answers `hello` itself and, by
  default, answers liveness pings (`set_pins`); everything else lands in its
  inbox. Used for the protocol edges: stale and gapped deltas, resync failures,
  silence.
- the real `StatusServer` over the server tests' `FakeProducer` / `FakeMarks` /
  `FakeTaskCache`, reached through the module alias `fx` (only the alias is
  imported, so no foreign TestCase is collected). Used for integration: the real
  reply path, refresh, pins, compare mode, restart.

The local instance is `FakeLocal` (a recorder of the TmuxMonitor slice), or a real
`TmuxMonitor` with its control-client hooks stubbed out where the pane-cache seam
itself is under test — never a real control client.

Run:
  python3 tests/test_monitor_status_client.py
"""
from __future__ import annotations

import asyncio
import dataclasses
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
REPO_ROOT = TESTS.parent
SCRIPTS = REPO_ROOT / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "lib"))
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

import test_monitor_status_server as fx  # noqa: E402  (module alias only)
from monitor import monitor_core  # noqa: E402
from monitor import status_client as sc  # noqa: E402
from monitor import status_protocol as sp  # noqa: E402
from monitor import status_recording as sr  # noqa: E402
from monitor import status_server as ss  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    CAPTURE_PIN_ALL, PaneCategory, TmuxControlState, TmuxMonitor,
)

VERSION = fx.VERSION
SESSION = fx.SESSION
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "monitor_status" / "basic.jsonl"
wait_until = fx.wait_until


# ---------------------------------------------------------------------------
# Wire helpers
# ---------------------------------------------------------------------------

def rec(pane_id, window="agent-pick-1", content="live", *, category=PaneCategory.AGENT,
        shadow_target="", **kw) -> dict:
    snap = fx.snap(fx.pane(pane_id, window, category=category,
                           shadow_target=shadow_target), content)
    return sp.pane_record(snap, **kw)


def snapshot(gen, panes, *, id=None, shadows=None, **members) -> dict:
    msg = {
        "type": "snapshot", "ts": 1.0, "gen": gen, "panes": panes,
        "shadows": shadows or {}, "completed": [],
        "sessions": {SESSION: {"project_root": "/r", "project_name": "r"}},
        "parked": [], "discovery": sp.empty_discovery(), "control_state": "connected",
    }
    msg.update(members)
    if id is not None:
        msg["id"] = id
    return msg


def delta(gen, **members) -> dict:
    return {"type": "delta", "ts": 1.0 + gen, "gen": gen, **members}


def welcome() -> dict:
    return {"type": "welcome", "ts": 1.0, "proto": sp.PROTO, "version": VERSION,
            "server": {"impl": "scripted", "pid": 4242}}


def no_ts(snaps: dict) -> dict:
    return {k: dataclasses.replace(v, timestamp=0.0) for k, v in snaps.items()}


class ScriptedServer:
    """A Unix server driven line by line by the test (the newest connection)."""

    def __init__(self, path):
        self.path = str(path)
        self.inbox: asyncio.Queue = asyncio.Queue()
        self.hellos: list = []
        self.pings: list = []
        self.writers: list = []
        self.hello_reply: dict | None = None
        self.answer_hello = True
        self.answer_pings = True
        self.eofs = 0          # connections the CLIENT closed
        self.server = None

    async def start(self):
        self.server = await asyncio.start_unix_server(
            self._on_connect, path=self.path, limit=sp.MAX_CLIENT_LINE_BYTES)

    async def _on_connect(self, reader, writer):
        self.writers.append(writer)
        try:
            while True:
                line = await sp.read_line(reader)
                if line is None:
                    self.eofs += 1
                    return
                msg = sp.decode(line, direction=sp.CLIENT)
                if msg["type"] == "hello":
                    self.hellos.append(msg)
                    if self.answer_hello:
                        self.write(self.hello_reply or welcome(), writer)
                elif msg["type"] == "set_pins" and self.answer_pings and \
                        msg.get("pins") == self.ping_pins(msg):
                    self.pings.append(msg)
                    await self.inbox.put(msg)
                    self.write({"type": "result", "ts": 1.0, "request": "set_pins",
                                "id": msg["id"]}, writer)
                else:
                    await self.inbox.put(msg)
        except Exception:  # noqa: BLE001 - a dropped test connection
            return

    @staticmethod
    def ping_pins(msg):
        return msg.get("pins")

    def write(self, msg: dict, writer=None):
        (writer or self.writers[-1]).write(sp.encode(msg, direction=sp.SERVER))

    def write_raw(self, raw: bytes):
        self.writers[-1].write(raw)

    async def expect(self, kind: str, timeout: float = 2.0) -> dict:
        end = time.monotonic() + timeout
        while True:
            left = end - time.monotonic()
            if left <= 0:
                raise AssertionError(f"no {kind!r} request arrived")
            msg = await asyncio.wait_for(self.inbox.get(), left)
            if msg["type"] == kind:
                return msg

    def drain(self) -> list:
        out = []
        while not self.inbox.empty():
            out.append(self.inbox.get_nowait())
        return out

    def drop(self):
        for w in self.writers:
            w.close()

    async def close(self):
        self.drop()
        if self.server is not None:
            self.server.close()
            try:
                await asyncio.wait_for(self.server.wait_closed(), 2.0)
            except asyncio.TimeoutError:
                pass
        with __import__("contextlib").suppress(FileNotFoundError):
            os.unlink(self.path)


class FakeEnsure:
    """`ensure_server` stand-in: RUNNING at `sock` unless `results` says otherwise."""

    def __init__(self, sock):
        self.sock = str(sock)
        self.calls = 0
        self.results: list = []

    def __call__(self, **kw):
        self.calls += 1
        self.kw = kw
        if self.results:
            res = self.results.pop(0)
            if res is not None:
                return res
        return ss.EnsureResult("RUNNING", self.sock, 4242)


class FakeLocal:
    """The `TmuxMonitor` slice the client delegates to, with a call log."""

    compare_mode_default = "stripped"
    session = SESSION

    def __init__(self):
        self.calls: list = []
        self.control_started = 0
        self.control_closed = 0
        self.skip = None
        self.block: asyncio.Event | None = None
        self.seeded = None
        self.teardown_gate: asyncio.Event | None = None
        self.closing = False
        self.snaps = {"%9": fx.snap(fx.pane("%9", "agent-local"), "local")}

    async def capture_all_async(self):
        self.calls.append("capture_all_async")
        return dict(self.snaps)

    async def capture_all_classified_async(self):
        self.calls.append("capture_all_classified_async")
        if self.block is not None:
            await self.block.wait()
        return 1, "classified"

    def commit_snapshots(self, gen, classified):
        return dict(self.snaps)

    async def capture_pane_classified_async(self, pane_id, capture_lines=None):
        self.calls.append(("capture_one", pane_id))
        s = self.snaps.get(pane_id)
        return 1, (s.pane if s else None), "content", None

    def commit_snapshot(self, gen, pane, content, result):
        return self.snaps.get(pane.pane_id)

    async def refresh_shadow_snapshot(self, pane_id):
        return None

    def get_shadow_snapshot(self, pane_id):
        return None

    def shadow_snapshots(self):
        return {}

    def get_pane(self, pane_id):
        s = self.snaps.get(pane_id)
        return s.pane if s else None

    def discover_panes(self):
        self.calls.append("discover_panes")
        return [s.pane for s in self.snaps.values()]

    def discover_panes_with_shadows_async(self):
        return "local-discovery"

    def get_session_to_project_mapping(self):
        return {"local": Path("/local")}

    async def get_session_to_project_mapping_async(self):
        return {"local": Path("/local")}

    def get_compare_mode(self, pane_id):
        return "stripped"

    def is_compare_mode_overridden(self, pane_id):
        return False

    def get_last_change_wall(self, pane_id):
        return None

    def cycle_compare_mode(self, pane_id):
        self.calls.append(("cycle", pane_id))
        return "raw", False

    def set_compare_mode(self, pane_id, mode):
        return mode or "stripped"

    def control_state(self):
        return TmuxControlState.CONNECTED

    def last_enumerated_sessions(self):
        return frozenset({"local"})

    def last_discovered_agents(self):
        return frozenset()

    def last_discovered_panes(self):
        return {}

    def set_parked_agents(self, pairs):
        self.skip = frozenset(pairs)

    async def start_control_client(self):
        self.control_started += 1
        return True

    async def close_control_client(self):
        self.closing = True
        if self.teardown_gate is not None:
            await self.teardown_gate.wait()
        self.control_closed += 1

    def send_keys(self, pane_id, keys, literal=False):
        self.calls.append(("send_keys", pane_id, keys))
        return True

    def seed_pane_cache(self, panes):
        self.seeded = dict(panes)


def quiet_tmux_monitor() -> TmuxMonitor:
    """A real TmuxMonitor whose control-client hooks never reach tmux."""
    m = TmuxMonitor(session=SESSION)

    async def _start():
        return False

    async def _close():
        return None

    m.start_control_client = _start
    m.close_control_client = _close
    return m


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class ClientCase(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.sock = self.root / "s.sock"
        self.ensure = FakeEnsure(self.sock)
        self.modes: list = []

    async def asyncTearDown(self):
        for c in getattr(self, "_clients", []):
            await c.close()
        for s in getattr(self, "_servers", []):
            if isinstance(s, ScriptedServer):
                await s.close()
            else:
                await s.close()
        self._tmp.cleanup()

    def client(self, local=..., **kw) -> sc.MonitorClient:
        """`local` omitted → a FakeLocal; an explicit None is passed through
        (replay runs with no local instance)."""
        kw.setdefault("ensure", self.ensure)
        kw.setdefault("enabled", True)
        kw.setdefault("request_timeout", 2.0)
        kw.setdefault("connect_deadline", 1.0)
        kw.setdefault("backoff", (30.0,))
        kw.setdefault("ping_after", 30.0)
        c = sc.MonitorClient(FakeLocal() if local is ... else local, kind="test",
                             version=VERSION, own_pane="%99", **kw)
        c.add_mode_listener(self.modes.append)
        self._clients = getattr(self, "_clients", []) + [c]
        return c

    async def scripted(self) -> ScriptedServer:
        srv = ScriptedServer(self.sock)
        await srv.start()
        self._servers = getattr(self, "_servers", []) + [srv]
        return srv

    async def real_server(self, snaps=None, shadows=None):
        fake = fx.FakeProducer(self.root)
        fake.snaps = dict(snaps or {})
        fake.shadows = dict(shadows or {})
        marks = fx.FakeMarks()
        server = ss.StatusServer(
            fake, socket_path=self.sock, version=VERSION, project_root=self.root,
            grace=60.0, marks_view=marks, task_cache=fx.FakeTaskCache(),
            watchdog_interval=0.02, interval_override=1000.0,
            start_control_client=False, hello_timeout=5.0,
        )
        await server.start()
        self._servers = getattr(self, "_servers", []) + [server]
        return server, fake, marks

    async def started_scripted(self, client, srv, panes=None, **members) -> dict:
        """Start `client` against `srv` and answer its subscribe; returns it."""
        task = asyncio.create_task(client.start())
        sub = await srv.expect("subscribe")
        srv.write(snapshot(1, panes if panes is not None else {"%1": rec("%1")},
                           id=sub["id"], **members))
        await asyncio.wait_for(task, 3.0)
        self.assertIs(client.mode, sc.ClientMode.SERVER)
        return sub


# ---------------------------------------------------------------------------
# Subscription, snapshot, deltas
# ---------------------------------------------------------------------------

class SubscriptionTests(ClientCase):

    async def test_subscribe_and_snapshot_reads(self):
        srv = await self.scripted()
        local = FakeLocal()
        c = self.client(local, pins={(SESSION, "agent-pick-1")}, content="all")
        discovery = sp.discovery_member(
            {SESSION}, {(SESSION, "agent-pick-1")},
            {(SESSION, "agent-pick-1"): [("%1", 11, False), ("%5", 15, False)]})
        sub = await self.started_scripted(
            c, srv,
            panes={"%1": rec("%1", content="one", compare_mode="raw",
                             compare_override=True, last_change=123.0),
                   "%2": rec("%2", "board", category=PaneCategory.TUI)},
            shadows={"%1": rec("%5", "agent-pick-1", "shadow", shadow_target="%1",
                               compare_mode="raw")},
            discovery=discovery, control_state="reconnecting")

        self.assertEqual(srv.hellos[0]["client"], {"kind": "test", "pane": "%99",
                                                   "pid": os.getpid()})
        self.assertEqual(sub["content"], "all")
        self.assertTrue(sub["include_shadows"])
        self.assertEqual(sub["pins"], [[SESSION, "agent-pick-1"]])

        snaps = await c.capture_all_async()
        self.assertEqual(set(snaps), {"%1", "%2"})
        self.assertEqual(snaps["%1"].content, "one")
        self.assertEqual(c.get_shadow_snapshot("%1").pane.pane_id, "%5")
        self.assertIsNone(c.get_pane("%5"), "get_pane never serves a shadow")
        self.assertEqual(c.get_pane("%2").window_name, "board")
        self.assertEqual({p.pane_id for p in c.discover_panes()}, {"%1", "%2"})
        self.assertEqual(c.get_session_to_project_mapping(), {SESSION: Path("/r")})
        self.assertEqual(await c.get_session_to_project_mapping_async(),
                         {SESSION: Path("/r")})
        self.assertEqual(c.get_compare_mode("%1"), "raw")
        self.assertTrue(c.is_compare_mode_overridden("%1"))
        self.assertEqual(c.get_last_change_wall("%1"), 123.0)
        self.assertEqual(c.get_compare_mode("%5"), "raw", "a shadow's own record")
        self.assertEqual(c.get_compare_mode("%404"), "stripped")
        self.assertIs(c.control_state(), TmuxControlState.RECONNECTING)
        self.assertEqual(c.last_enumerated_sessions(), frozenset({SESSION}))
        self.assertEqual(c.last_discovered_agents(), frozenset({(SESSION, "agent-pick-1")}))
        self.assertEqual(c.last_discovered_panes(),
                         {(SESSION, "agent-pick-1"): [("%1", 11, False), ("%5", 15, False)]})
        self.assertEqual(c.server_info["impl"], "scripted")
        self.assertNotIn("capture_all_async", local.calls)
        self.assertEqual(local.control_started, 0, "no local control client in server mode")

    async def test_record_lookups_build_one_index_per_generation(self):
        srv = await self.scripted()
        c = self.client()
        panes = {f"%{n}": rec(f"%{n}", f"agent-pick-{n}") for n in range(1, 12)}
        await self.started_scripted(c, srv, panes=panes)
        with mock.patch.object(c._state, "records", wraps=c._state.records) as recs:
            for pid in panes:
                c.get_compare_mode(pid)
                c.is_compare_mode_overridden(pid)
                c.get_last_change_wall(pid)
            self.assertEqual(recs.call_count, 1, "one map copy for 33 lookups")
            applied = []
            c.add_update_listener(applied.append)
            srv.write(delta(2, panes={"%1": {"compare_mode": "raw",
                                             "compare_override": True}}))
            await wait_until(lambda: applied)
            self.assertEqual(c.get_compare_mode("%1"), "raw", "a new generation re-indexes")
            self.assertEqual(recs.call_count, 2)

    async def test_unknown_control_state_passes_through(self):
        srv = await self.scripted()
        c = self.client()
        await self.started_scripted(c, srv, control_state="paused")
        self.assertEqual(c.control_state(), "paused")

    async def test_delta_applies_and_notifies(self):
        srv = await self.scripted()
        c = self.client()
        applied = []
        c.add_update_listener(applied.append)
        await self.started_scripted(c, srv, panes={"%1": rec("%1"), "%2": rec("%2")})
        srv.write(delta(2, panes={"%1": {"content": "new"}, "%3": rec("%3")},
                        removed=["%2"], completed=["%1"]))
        await wait_until(lambda: applied)
        snaps = await c.capture_all_async()
        self.assertEqual(set(snaps), {"%1", "%3"})
        self.assertEqual(snaps["%1"].content, "new")
        self.assertEqual(applied[0].changed, frozenset({"%1", "%3"}))
        self.assertEqual(applied[0].removed, frozenset({"%2"}))

    async def test_stale_delta_is_dropped(self):
        srv = await self.scripted()
        c = self.client()
        applied = []
        c.add_update_listener(applied.append)
        task = asyncio.create_task(c.start())
        sub = await srv.expect("subscribe")
        srv.write(snapshot(5, {"%1": rec("%1", content="five")}, id=sub["id"]))
        await task
        before = c.capture_generation
        srv.write(delta(5, panes={"%1": {"content": "stale-5"}}))
        srv.write(delta(3, panes={"%1": {"content": "stale-3"}}))
        srv.write(delta(6))   # marker: processed after the two stale ones
        await wait_until(lambda: applied)
        self.assertEqual([a.gen for a in applied], [6])
        self.assertEqual(c.capture_generation, before + 1)
        self.assertEqual((await c.capture_all_async())["%1"].content, "five")


# ---------------------------------------------------------------------------
# Request / reply completion and resync
# ---------------------------------------------------------------------------

class RequestReplyTests(ClientCase):

    async def test_subscribe_and_set_content_complete_through_real_replies(self):
        await self.real_server({"%1": fx.snap(fx.pane("%1"), "one"),
                                "%2": fx.snap(fx.pane("%2", "agent-pick-2"), "two")})
        c = self.client(request_timeout=1.0)
        t0 = time.monotonic()
        await c.start()
        self.assertIs(c.mode, sc.ClientMode.SERVER)
        self.assertLess(time.monotonic() - t0, 0.9, "subscribe resolved by its snapshot")
        t0 = time.monotonic()
        self.assertTrue(await c.set_content(["%1"]))
        self.assertLess(time.monotonic() - t0, 0.9, "set_content resolved by its snapshot")
        snaps = await c.capture_all_async()
        self.assertEqual(snaps["%1"].content, "one")
        self.assertEqual(snaps["%2"].content, "", "unselected after the reply applied")

    async def test_snapshot_with_another_id_does_not_complete(self):
        srv = await self.scripted()
        c = self.client(request_timeout=0.3)
        t0 = time.monotonic()
        task = asyncio.create_task(c.start())
        sub = await srv.expect("subscribe")
        srv.write(snapshot(1, {"%1": rec("%1")}, id=sub["id"] + 100))
        await asyncio.wait_for(task, 3.0)
        self.assertGreaterEqual(time.monotonic() - t0, 0.3)
        self.assertIs(c.mode, sc.ClientMode.FALLBACK)
        self.assertIn("subscribe timed out", c.last_error)

    async def test_error_reply_to_subscribe_falls_back(self):
        srv = await self.scripted()
        c = self.client()
        task = asyncio.create_task(c.start())
        sub = await srv.expect("subscribe")
        srv.write({"type": "error", "ts": 1.0, "code": "internal", "message": "boom",
                   "id": sub["id"]})
        await asyncio.wait_for(task, 3.0)
        self.assertIs(c.mode, sc.ClientMode.FALLBACK)

    async def test_gap_resyncs_without_blocking_the_reader(self):
        srv = await self.scripted()
        c = self.client()
        await self.started_scripted(c, srv)
        srv.write(delta(3))                   # gap after gen 1
        resub = await srv.expect("subscribe")
        srv.write(delta(4, panes={"%1": {"content": "dropped"}}))
        srv.write(snapshot(5, {"%1": rec("%1", content="five")}, id=resub["id"]))
        srv.write(delta(6, panes={"%1": {"content": "six"}}))
        await wait_until(lambda: c._state is not None and c._state.gen == 6)
        self.assertEqual((await c.capture_all_async())["%1"].content, "six")
        await asyncio.sleep(0.05)
        self.assertEqual([m for m in srv.drain() if m["type"] == "subscribe"], [],
                         "exactly one resubscribe")
        self.assertIs(c.mode, sc.ClientMode.SERVER)

    async def test_resync_answered_by_error_fails_the_connection(self):
        srv = await self.scripted()
        c = self.client(resync_timeout=2.0)
        applied = []
        c.add_update_listener(applied.append)
        await self.started_scripted(c, srv)
        srv.write(delta(3))
        resub = await srv.expect("subscribe")
        srv.write({"type": "error", "ts": 1.0, "code": "internal",
                   "message": "reply could not be encoded", "id": resub["id"]})
        srv.write(delta(4, panes={"%1": {"content": "after-error"}}))
        t0 = time.monotonic()
        await wait_until(lambda: c.mode is sc.ClientMode.FALLBACK, timeout=1.5)
        self.assertLess(time.monotonic() - t0, 1.5, "well inside resync_timeout")
        self.assertIn("resync failed: internal", c.last_error)
        self.assertEqual(applied, [], "nothing applied after the gap")

    async def test_resync_without_reply_times_out_while_traffic_continues(self):
        srv = await self.scripted()
        c = self.client(resync_timeout=0.3, ping_after=0.05, ping_timeout=1.0)
        await self.started_scripted(c, srv)
        srv.write(delta(3))
        await srv.expect("subscribe")         # never answered
        t0 = time.monotonic()
        gen = 4
        while c.mode is sc.ClientMode.SERVER and time.monotonic() - t0 < 2.0:
            with __import__("contextlib").suppress(Exception):
                srv.write(delta(gen))
            gen += 1
            await asyncio.sleep(0.03)
        self.assertIs(c.mode, sc.ClientMode.FALLBACK)
        self.assertGreaterEqual(time.monotonic() - t0, 0.25)
        self.assertIn("resync timed out", c.last_error)

    async def test_set_content_error_fails_the_connection(self):
        srv = await self.scripted()
        c = self.client()
        await self.started_scripted(c, srv)
        task = asyncio.create_task(c.set_content(["%1"]))
        req = await srv.expect("set_content")
        srv.write({"type": "error", "ts": 1.0, "code": "internal", "message": "x",
                   "id": req["id"]})
        self.assertFalse(await asyncio.wait_for(task, 3.0))
        self.assertIs(c.mode, sc.ClientMode.FALLBACK)


# ---------------------------------------------------------------------------
# Fallback, reconnect, liveness
# ---------------------------------------------------------------------------

class FallbackTests(ClientCase):

    async def test_malformed_line_falls_back_then_reconnects(self):
        srv = await self.scripted()
        local = FakeLocal()
        c = self.client(local, backoff=(0.0, 0.05))
        await self.started_scripted(c, srv)
        srv.write_raw(b"{not json\n")
        await wait_until(lambda: c.mode is sc.ClientMode.FALLBACK)
        self.assertIn("protocol violation", c.last_error)
        await wait_until(lambda: local.control_started == 1)
        snaps = await c.capture_all_async()
        self.assertEqual(set(snaps), {"%9"})
        self.assertIn("capture_all_async", local.calls)
        # The reconnect loop reaches the server again.
        sub = await srv.expect("subscribe")
        srv.write(snapshot(1, {"%1": rec("%1", content="back")}, id=sub["id"]))
        await wait_until(lambda: c.mode is sc.ClientMode.SERVER)
        self.assertGreaterEqual(local.control_closed, 1, "local control closed again")
        self.assertEqual((await c.capture_all_async())["%1"].content, "back")
        self.assertGreaterEqual(self.ensure.calls, 2)

    async def test_server_restart_reconnects(self):
        server_a, _, _ = await self.real_server({"%1": fx.snap(fx.pane("%1"), "a")})
        c = self.client(backoff=(0.0, 0.05))
        await c.start()
        self.assertEqual(set(await c.capture_all_async()), {"%1"})
        await server_a.close()
        await wait_until(lambda: c.mode is sc.ClientMode.FALLBACK)
        await self.real_server({"%7": fx.snap(fx.pane("%7", "agent-pick-7"), "b")})
        await wait_until(lambda: c.mode is sc.ClientMode.SERVER, timeout=5.0)
        self.assertEqual(set(await c.capture_all_async()), {"%7"})

    async def test_unreachable_falls_back(self):
        self.ensure.results = [ss.EnsureResult("UNAVAILABLE", reason="no_tmux_server")]
        local = FakeLocal()
        c = self.client(local)
        await c.start()
        self.assertIs(c.mode, sc.ClientMode.FALLBACK)
        self.assertIn("no_tmux_server", c.last_error)
        self.assertEqual(set(await c.capture_all_async()), {"%9"})
        self.assertEqual(c.get_pane("%9").window_name, "agent-local")
        self.assertEqual(c.get_session_to_project_mapping(), {"local": Path("/local")})
        self.assertEqual(c.discover_panes()[0].pane_id, "%9")
        c.set_parked_agents({(SESSION, "agent-x")})
        self.assertEqual(local.skip, {(SESSION, "agent-x")})
        self.assertEqual(c.cycle_compare_mode("%9"), ("raw", False))
        await wait_until(lambda: local.control_started == 1)

    async def test_version_mismatch_falls_back(self):
        srv = await self.scripted()
        srv.hello_reply = {"type": "error", "ts": 1.0, "code": "version_mismatch",
                           "message": "other", "server_version": "9.9"}
        c = self.client()
        await c.start()
        self.assertIs(c.mode, sc.ClientMode.FALLBACK)
        self.assertIn("version_mismatch", c.last_error)

    async def test_disabled_never_calls_ensure(self):
        c = self.client(enabled=False)
        await c.start()
        self.assertIs(c.mode, sc.ClientMode.FALLBACK)
        self.assertEqual(self.ensure.calls, 0)
        with mock.patch.dict(os.environ, {sc.ENV_SWITCH: "0"}):
            c2 = sc.MonitorClient(FakeLocal(), kind="test", version=VERSION,
                                  ensure=self.ensure)
        self._clients.append(c2)
        await c2.start()
        self.assertIs(c2.mode, sc.ClientMode.FALLBACK)
        self.assertEqual(self.ensure.calls, 0)

    async def test_hung_server_is_detected_by_the_ping(self):
        srv = await self.scripted()
        srv.answer_pings = False
        c = self.client(ping_after=0.05, ping_timeout=0.1)
        await self.started_scripted(c, srv)
        ping = await srv.expect("set_pins")
        self.assertEqual(ping["pins"], [])
        await wait_until(lambda: c.mode is sc.ClientMode.FALLBACK)
        self.assertIn("ping timed out", c.last_error)


# ---------------------------------------------------------------------------
# Generation token, fast preview, pins, compare mode, content
# ---------------------------------------------------------------------------

class CaptureTests(ClientCase):

    async def test_overlapping_captures_supersede(self):
        srv = await self.scripted()
        c = self.client()
        await self.started_scripted(c, srv)
        t1, p1 = await c.capture_all_classified_async()
        t2, p2 = await c.capture_all_classified_async()
        self.assertIsNone(c.commit_snapshots(t1, p1))
        self.assertEqual(set(c.commit_snapshots(t2, p2)), {"%1"})

    async def test_capture_straddling_a_mode_switch_commits_nothing(self):
        srv = await self.scripted()
        local = FakeLocal()
        local.block = asyncio.Event()
        self.ensure.results = [ss.EnsureResult("UNAVAILABLE", reason="start_timeout")]
        c = self.client(local, backoff=(0.1,))
        await c.start()
        self.assertIs(c.mode, sc.ClientMode.FALLBACK)
        task = asyncio.create_task(c.capture_all_classified_async())
        sub = await srv.expect("subscribe", timeout=3.0)
        srv.write(snapshot(1, {"%1": rec("%1")}, id=sub["id"]))
        await asyncio.sleep(0.1)
        self.assertIs(c.mode, sc.ClientMode.FALLBACK,
                      "the switch waits for the in-flight local capture to drain")
        local.block.set()
        token, payload = await task
        await wait_until(lambda: c.mode is sc.ClientMode.SERVER)
        self.assertIsNone(c.commit_snapshots(token, payload))

    async def test_fast_preview_and_shadow_refresh(self):
        _, fake, _ = await self.real_server(
            {"%1": fx.snap(fx.pane("%1"), "one")},
            {"%1": fx.snap(fx.pane("%5", shadow_target="%1"), "shadow")})
        c = self.client()
        await c.start()
        fake.snaps["%1"] = fx.snap(fx.pane("%1"), "fresh")
        gen, pane, content, result = await c.capture_pane_classified_async("%1")
        self.assertEqual(pane.pane_id, "%1")
        self.assertEqual(c.commit_snapshot(gen, pane, content, result).content, "fresh")
        self.assertIn(("capture_one", "%1"), fake.calls)
        shadow = await c.refresh_shadow_snapshot("%1")
        self.assertEqual(shadow.pane.pane_id, "%5")
        self.assertIn(("refresh_shadow", "%1"), fake.calls)
        self.assertIsInstance(await c.request_refresh(), int)

    async def test_fast_preview_survives_a_dropped_connection(self):
        srv = await self.scripted()
        c = self.client()
        await self.started_scripted(c, srv)
        task = asyncio.create_task(c.capture_pane_classified_async("%1"))
        await srv.expect("refresh")
        srv.drop()
        gen, pane, content, result = await asyncio.wait_for(task, 3.0)
        self.assertIsNone(pane)

    async def test_pins_reach_the_server_once_and_on_resubscribe(self):
        srv = await self.scripted()
        c = self.client(backoff=(0.0,))
        await self.started_scripted(c, srv)
        c.set_capture_pins({(SESSION, "w")})
        self.assertEqual((await srv.expect("set_pins"))["pins"], [[SESSION, "w"]])
        c.set_capture_pins({(SESSION, "w")})
        await asyncio.sleep(0.1)
        self.assertEqual([m for m in srv.drain() if m["type"] == "set_pins"], [])
        c.set_capture_pins(CAPTURE_PIN_ALL)
        self.assertEqual((await srv.expect("set_pins"))["pins"], "all")
        srv.drop()
        sub = await srv.expect("subscribe", timeout=3.0)
        self.assertEqual(sub["pins"], "all")

    async def test_pins_drive_the_real_servers_skip_set(self):
        _, fake, marks = await self.real_server({"%1": fx.snap(fx.pane("%1"), "one")})
        marks.parked = {(os.path.realpath(str(self.root)), "agent-p7")}
        c = self.client(pins={(SESSION, "agent-p7")})
        await c.start()
        self.assertEqual(fake.skip, frozenset())
        c.set_capture_pins(frozenset())
        await wait_until(lambda: fake.skip == {(SESSION, "agent-p7")})

    async def test_flush_pins_holds_the_next_request_until_set_pins_is_answered(self):
        """`flush_pins` orders a scan request after the pins it must run under
        (t2037_3): `set_capture_pins` only spawns its send, so without the
        flush a `refresh` could reach the server first."""
        srv = await self.scripted()
        srv.answer_pings = False             # hold every set_pins result back
        c = self.client()
        await self.started_scripted(c, srv)
        c.set_capture_pins({(SESSION, "agent-b")})

        async def flush_then_refresh():
            await c.flush_pins()
            return await c.request_refresh()

        task = asyncio.create_task(flush_then_refresh())
        held = await srv.expect("set_pins")
        await asyncio.sleep(0.2)
        self.assertEqual([m["type"] for m in srv.drain()], [],
                         "a request went out before set_pins was answered")
        srv.write({"type": "result", "ts": 1.0, "request": "set_pins", "id": held["id"]})
        ref = await srv.expect("refresh")
        srv.write(delta(2))
        srv.write({"type": "result", "ts": 1.0, "request": "refresh", "id": ref["id"],
                   "gen": 2})
        self.assertEqual(await asyncio.wait_for(task, 3.0), 2)

    async def test_flush_pins_is_bounded_and_never_raises(self):
        srv = await self.scripted()
        srv.answer_pings = False
        c = self.client(request_timeout=0.3)
        await self.started_scripted(c, srv)
        await c.flush_pins()                 # nothing pending: immediate no-op
        c.set_capture_pins(CAPTURE_PIN_ALL)
        await srv.expect("set_pins")
        start = time.monotonic()
        await asyncio.wait_for(c.flush_pins(), 3.0)
        self.assertLess(time.monotonic() - start, 1.5)

    async def test_flushed_pins_govern_the_requested_scans_skip_set(self):
        """Effect on the real server: the skip set published right before the
        requested scan's capture is computed from the flushed pins."""
        _, fake, marks = await self.real_server({"%1": fx.snap(fx.pane("%1"), "one")})
        root = os.path.realpath(str(self.root))
        marks.parked = {(root, "agent-a"), (root, "agent-b")}
        c = self.client(pins={(SESSION, "agent-a")})
        await c.start()
        fake.calls.clear()
        c.set_capture_pins({(SESSION, "agent-b")})
        await c.flush_pins()
        await c.request_refresh()
        capture_at = len(fake.calls) - 1 - fake.calls[::-1].index("capture")
        skips = [e for e in fake.calls[:capture_at] if isinstance(e, tuple)
                 and e[0] == "skip"]
        self.assertTrue(skips, fake.calls)
        self.assertEqual(skips[-1][1], {(SESSION, "agent-a")},
                         "the requested scan did not run under the flushed pins")

    async def test_compare_mode(self):
        _, fake, _ = await self.real_server({"%1": fx.snap(fx.pane("%1"), "one")})
        c = self.client()
        await c.start()
        self.assertEqual(await c.cycle_compare_mode_async("%1"), ("raw", False))
        await c.request_refresh()
        self.assertEqual(c.get_compare_mode("%1"), "raw")
        self.assertEqual(c.cycle_compare_mode("%1"), ("stripped", False), "prediction")
        await wait_until(lambda: fake.overrides.get("%1") == "stripped")
        await c.request_refresh()
        self.assertEqual(c.get_compare_mode("%1"), "stripped")
        self.assertTrue(c.is_compare_mode_overridden("%1"))
        self.assertEqual(await c.set_compare_mode_async("%1", None), ("stripped", True))

    async def test_capture_reads_the_wire(self):
        _, fake, _ = await self.real_server({"%1": fx.snap(fx.pane("%1"), "one")})
        fake.contents["%1"] = "a\nb\nc"
        c = self.client()
        await c.start()
        self.assertEqual(await c.capture("%1", 2), "b\nc")
        self.assertIsNone(await c.capture("%404", 2))


# ---------------------------------------------------------------------------
# The gateway's pane cache
# ---------------------------------------------------------------------------

class PaneCacheTests(ClientCase):

    async def test_seeded_from_the_subscription(self):
        srv = await self.scripted()
        local = quiet_tmux_monitor()
        c = self.client(local)
        await self.started_scripted(
            c, srv, panes={"%1": rec("%1"), "%2": rec("%2", "board", category=PaneCategory.TUI)},
            shadows={"%1": rec("%5", shadow_target="%1")})
        self.assertEqual(local.get_pane("%1").window_name, "agent-pick-1")
        self.assertIsNone(local.get_pane("%5"), "shadows never enter the cache")
        srv.write(delta(2, removed=["%2"]))
        await wait_until(lambda: local.get_pane("%2") is None)

    async def test_released_on_fallback_before_any_discovery(self):
        srv = await self.scripted()
        local = quiet_tmux_monitor()
        c = self.client(local)
        await self.started_scripted(
            c, srv, panes={"%1": rec("%1"), "%2": rec("%2", "board", category=PaneCategory.TUI)})
        self.assertEqual(local.get_running_tuis(), {"board"})
        srv.drop()
        await wait_until(lambda: c.mode is sc.ClientMode.FALLBACK)
        self.assertIsNone(local.get_pane("%1"))
        self.assertEqual(local.get_running_tuis(), set())

    def test_clean_stale_does_not_reap_a_seed(self):
        """Negative control: why the client must release the seed itself."""
        local = TmuxMonitor(session=SESSION)
        local.seed_pane_cache({"%1": fx.pane("%1")})
        local._clean_stale(set())
        self.assertIsNotNone(local.get_pane("%1"))

    async def test_close_releases_the_seed(self):
        srv = await self.scripted()
        local = quiet_tmux_monitor()
        c = self.client(local)
        await self.started_scripted(c, srv)
        self.assertIsNotNone(local.get_pane("%1"))
        await c.close()
        self.assertIsNone(local.get_pane("%1"))


# ---------------------------------------------------------------------------
# Delegation and replay
# ---------------------------------------------------------------------------

class DelegationTests(ClientCase):

    async def test_server_mode_delegates_only_the_gateway(self):
        srv = await self.scripted()
        local = FakeLocal()
        c = self.client(local)
        await self.started_scripted(c, srv)
        self.assertTrue(c.send_keys("%1", "x"))
        self.assertIn(("send_keys", "%1", "x"), local.calls)
        with self.assertRaises(AttributeError):
            c.discover_panes_with_shadows_async
        self.assertIsNone(getattr(c, "nonexistent", None))
        self.assertEqual(c.session, SESSION, "config attributes are gateway")

    async def test_fallback_delegates_everything(self):
        self.ensure.results = [ss.EnsureResult("UNAVAILABLE", reason="x")]
        c = self.client()
        await c.start()
        self.assertEqual(c.discover_panes_with_shadows_async(), "local-discovery")


class ReplayTests(ClientCase):

    @staticmethod
    def final_state() -> sp.StreamState:
        recording = sr.read_recording(FIXTURE)
        state = sp.StreamState()
        state.apply(recording.snapshot)
        for d in recording.deltas:
            state.apply(d)
        return state

    def replay_client(self, **kw):
        return self.client(None, replay=FIXTURE, replay_speed=0, **kw)

    async def test_replays_the_fixture(self):
        expected = self.final_state()
        c = self.replay_client()
        await c.start()
        self.assertIsNone(c._local, "replay runs with no local monitor")
        self.assertIs(c.mode, sc.ClientMode.REPLAY)
        self.assertEqual(c.server_info["impl"], "replay")
        await wait_until(lambda: c._state is not None and c._state.gen == expected.gen)
        self.assertEqual(no_ts(await c.capture_all_async()), no_ts(expected.snapshots()))
        self.assertEqual(self.ensure.calls, 0)
        with self.assertRaises(sc.ReplayReadOnly):
            c.send_keys("%1", "x")
        self.assertIsNone(getattr(c, "send_keys", None))
        with self.assertRaises(sc.ReplayReadOnly):
            await c.cycle_compare_mode_async("%2")
        self.assertEqual(c.cycle_compare_mode("%2"),
                         (c.get_compare_mode("%2"), not c.is_compare_mode_overridden("%2")))
        tmp = c._replay_dir
        self.assertTrue(os.path.isdir(tmp))
        await c.close()
        self.assertFalse(os.path.exists(tmp))

    async def test_content_selection_in_replay(self):
        expected = self.final_state()
        c = self.replay_client(content="none")
        await c.start()
        await wait_until(lambda: c._state is not None and c._state.gen == expected.gen)
        snaps = await c.capture_all_async()
        self.assertTrue(all(s.content == "" for s in snaps.values()))
        self.assertTrue(await c.set_content(["%1"]))
        snaps = await c.capture_all_async()
        self.assertEqual(snaps["%1"].content, expected.records()["%1"]["content"])
        self.assertTrue(all(s.content == "" for k, s in snaps.items() if k != "%1"))


class FakeBackend:
    """`TmuxControlBackend` stand-in: `start()` blocks its worker thread until
    released, like the real one's up-to-14 s start; `stop()` is counted."""

    instances: list = []

    def __init__(self, session=None):
        self.release = threading.Event()
        self.stops = 0
        self.is_alive = False
        FakeBackend.instances.append(self)

    def start(self):
        self.release.wait(10)
        self.is_alive = True
        return True

    def stop(self):
        self.stops += 1
        self.is_alive = False


class ControlStartTests(ClientCase):
    """The REAL `TmuxMonitor.start_control_client` coroutine, over a backend whose
    start blocks in its worker thread. Cancelling that coroutine would abandon
    its stale-generation `backend.stop()` and leave the backend running."""

    def setUp(self):
        FakeBackend.instances = []
        patcher = mock.patch.object(monitor_core, "TmuxControlBackend", FakeBackend)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def started_in_fallback(self, **kw):
        local = TmuxMonitor(session=SESSION)
        self.ensure.results = [ss.EnsureResult("UNAVAILABLE", reason="start_timeout")]
        c = self.client(local, **kw)
        await c.start()
        self.assertIs(c.mode, sc.ClientMode.FALLBACK)
        await wait_until(lambda: FakeBackend.instances)
        return c, local, FakeBackend.instances[0]

    async def test_reconnect_during_start_retires_the_backend(self):
        srv = await self.scripted()
        c, local, backend = await self.started_in_fallback(backoff=(0.1,))
        sub = await srv.expect("subscribe", timeout=3.0)
        srv.write(snapshot(1, {"%1": rec("%1")}, id=sub["id"]))
        await wait_until(lambda: c.mode is sc.ClientMode.SERVER)
        backend.release.set()          # the worker thread's start completes now
        await wait_until(lambda: backend.stops == 1, timeout=5.0)
        self.assertIsNone(local._backend, "no live backend left installed")

    async def test_close_during_start_retires_the_backend(self):
        c, local, backend = await self.started_in_fallback()
        threading.Timer(0.2, backend.release.set).start()
        await c.close()
        self.assertEqual(backend.stops, 1, "close() waited for the start to retire it")
        self.assertIsNone(local._backend)


class DiscoveryOverlapTests(ClientCase):
    """A REAL local discovery (`_parse_list_panes` writes the pane cache) still
    running when the server comes back. Invariant: a subscribed mode never
    coexists with an in-flight local capture, so the gateway's cache is never
    stale while the client serves from the subscription."""

    async def local_with_paused_capture(self, pause: str):
        """`pause="list"` stops before discovery writes the cache; `"classify"`
        stops after it wrote the stale entry, in the offloaded classification."""
        local = quiet_tmux_monitor()
        gate = asyncio.Event()
        stub = fx.StubTmux({"%1": ("agent-stale", "1")}, {"%1": "x"})

        async def tmux(args, timeout=5.0):
            if pause == "list" and args and args[0] == "list-panes":
                await gate.wait()
            return await stub(args, timeout)

        async def offloaded(fn):
            if pause == "classify":
                await gate.wait()
            return fn()

        async def sessions():
            return [SESSION]

        async def mapping():
            return {SESSION: self.root}

        local._tmux_async = tmux
        local._run_offloaded = offloaded
        local._target_sessions_async = sessions
        local.get_session_to_project_mapping_async = mapping
        return local, gate

    async def overlap(self, pause: str, **kw):
        srv = await self.scripted()
        local, gate = await self.local_with_paused_capture(pause)
        self.ensure.results = [ss.EnsureResult("UNAVAILABLE", reason="start_timeout")]
        c = self.client(local, backoff=(0.1,), **kw)
        await c.start()
        task = asyncio.create_task(c.capture_all_async())
        sub = await srv.expect("subscribe", timeout=3.0)
        srv.write(snapshot(1, {"%1": rec("%1", "agent-pick-101")}, id=sub["id"]))
        return srv, c, local, gate, task

    def assert_consistent(self, c, local):
        """What the client serves and what the gateway's cache-backed actions
        see agree — whichever of the two currently owns the cache."""
        self.assertEqual(c.get_pane("%1").window_name, local.get_pane("%1").window_name)

    async def test_switch_waits_for_a_paused_discovery(self):
        _, c, local, gate, task = await self.overlap("list")
        await asyncio.sleep(0.1)
        self.assertIs(c.mode, sc.ClientMode.FALLBACK)
        gate.set()
        await task
        await wait_until(lambda: c.mode is sc.ClientMode.SERVER)
        self.assertEqual(local.get_pane("%1").window_name, "agent-pick-101")
        self.assert_consistent(c, local)

    async def test_cache_stays_consistent_while_a_classification_is_suspended(self):
        _, c, local, gate, task = await self.overlap("classify")
        await wait_until(lambda: local.get_pane("%1") is not None)
        for _ in range(5):              # the stale write landed; the op is suspended
            await asyncio.sleep(0.03)
            self.assertIs(c.mode, sc.ClientMode.FALLBACK)
            self.assert_consistent(c, local)
        gate.set()
        await task
        await wait_until(lambda: c.mode is sc.ClientMode.SERVER)
        self.assertEqual(local.get_pane("%1").window_name, "agent-pick-101")
        self.assert_consistent(c, local)

    async def test_drain_timeout_abandons_the_attach_then_retries(self):
        srv, c, local, gate, task = await self.overlap("classify", local_drain_timeout=0.1)
        await wait_until(lambda: "did not drain" in c.last_error)
        self.assertIs(c.mode, sc.ClientMode.FALLBACK, "never SERVER beside a live local op")
        self.assert_consistent(c, local)
        gate.set()
        await task
        sub = await srv.expect("subscribe", timeout=3.0)   # the reconnect loop retries
        srv.write(snapshot(1, {"%1": rec("%1", "agent-pick-101")}, id=sub["id"]))
        await wait_until(lambda: c.mode is sc.ClientMode.SERVER)
        self.assertEqual(local.get_pane("%1").window_name, "agent-pick-101")

    async def test_reconnect_lost_during_the_drain_keeps_the_fallback_cache(self):
        srv, c, local, gate, task = await self.overlap("classify")
        await wait_until(lambda: c._switch_pending)
        cached = local.get_pane("%1")
        self.assertIsNotNone(cached, "the fallback discovery wrote its result")
        srv.drop()                      # the reconnecting server goes away mid-drain
        await wait_until(lambda: c._link is None)   # the loss was handled
        self.assertIs(c.mode, sc.ClientMode.FALLBACK)
        self.assertIs(local.get_pane("%1"), cached,
                      "a cache the subscription never owned is not released")
        gate.set()
        await task
        self.assertIsNotNone(local.get_pane("%1"))

    async def test_new_local_captures_are_refused_while_the_switch_is_pending(self):
        srv = await self.scripted()
        local = FakeLocal()
        local.block = asyncio.Event()
        self.ensure.results = [ss.EnsureResult("UNAVAILABLE", reason="start_timeout")]
        c = self.client(local, backoff=(0.1,))
        await c.start()
        blocked = asyncio.create_task(c.capture_all_classified_async())
        sub = await srv.expect("subscribe", timeout=3.0)
        srv.write(snapshot(1, {"%1": rec("%1")}, id=sub["id"]))
        await wait_until(lambda: c._switch_pending)
        before = list(local.calls)
        self.assertIsNone(await c.capture_all_async())
        token, payload = await c.capture_all_classified_async()
        self.assertIsNone(c.commit_snapshots(token, payload))
        self.assertEqual(local.calls, before, "the local producer was not touched")
        local.block.set()
        await blocked
        await wait_until(lambda: c.mode is sc.ClientMode.SERVER)


class TeardownLossTests(ClientCase):

    async def test_server_lost_during_local_teardown_keeps_retrying(self):
        srv = await self.scripted()
        local = FakeLocal()
        local.teardown_gate = asyncio.Event()
        self.addCleanup(local.teardown_gate.set)
        self.ensure.results = [ss.EnsureResult("UNAVAILABLE", reason="start_timeout")]
        c = self.client(local, backoff=(0.1,))
        await c.start()
        await wait_until(lambda: local.control_started == 1)
        sub = await srv.expect("subscribe", timeout=3.0)
        srv.write(snapshot(1, {"%1": rec("%1")}, id=sub["id"]))
        await wait_until(lambda: local.closing)          # teardown is paused
        srv.drop()
        await wait_until(lambda: c.mode is sc.ClientMode.FALLBACK)
        local.teardown_gate.set()
        sub = await srv.expect("subscribe", timeout=3.0)   # a retry path is alive
        srv.write(snapshot(1, {"%1": rec("%1", content="again")}, id=sub["id"]))
        await wait_until(lambda: c.mode is sc.ClientMode.SERVER)
        self.assertEqual((await c.capture_all_async())["%1"].content, "again")


class ResyncRaceTests(ClientCase):

    async def test_gap_right_behind_the_reply_snapshot_resyncs_again(self):
        srv = await self.scripted()
        c = self.client(resync_timeout=1.0)
        await self.started_scripted(c, srv)
        srv.write(delta(3))
        first = await srv.expect("subscribe")
        srv.write(snapshot(5, {"%1": rec("%1")}, id=first["id"]))
        srv.write(delta(7))             # a new gap, already buffered
        second = await srv.expect("subscribe")
        srv.write(snapshot(9, {"%1": rec("%1", content="nine")}, id=second["id"]))
        srv.write(delta(10, panes={"%1": {"content": "ten"}}))
        await wait_until(lambda: c._state is not None and c._state.gen == 10)
        self.assertIs(c.mode, sc.ClientMode.SERVER)
        self.assertFalse(c._resyncing)


class BlockedSendTests(ClientCase):
    """One deadline covers the whole request, the send's `drain()` included."""

    @staticmethod
    def block_writes(c):
        async def never():
            await asyncio.Event().wait()
        c._link.writer.drain = never

    async def test_blocked_ping_send_fails_the_connection(self):
        srv = await self.scripted()
        c = self.client(ping_after=0.05, ping_timeout=0.2)
        await self.started_scripted(c, srv)
        self.block_writes(c)
        await wait_until(lambda: c.mode is sc.ClientMode.FALLBACK, timeout=2.0)
        self.assertIn("ping timed out", c.last_error)

    async def test_blocked_resync_send_fails_the_connection(self):
        srv = await self.scripted()
        c = self.client(resync_timeout=0.2)
        await self.started_scripted(c, srv)
        self.block_writes(c)
        srv.write(delta(3))
        await wait_until(lambda: c.mode is sc.ClientMode.FALLBACK, timeout=2.0)
        self.assertIn("resync timed out", c.last_error)


class HandshakeCleanupTests(ClientCase):
    """The handshake socket is closed by the client itself. The test keeps a
    reference to every link, so a socket the client merely dropped is NOT
    closed for it by `StreamWriter.__del__` and the check stays meaningful."""

    def setUp(self):
        self.links: list = []
        links = self.links

        class RecordingLink(sc._Link):
            def __init__(self, reader, writer):
                super().__init__(reader, writer)
                links.append(self)

        patcher = mock.patch.object(sc, "_Link", RecordingLink)
        patcher.start()
        self.addCleanup(patcher.stop)

    def assert_all_closed(self):
        self.assertTrue(self.links, "a connection was opened")
        self.assertTrue(all(link.writer.is_closing() for link in self.links),
                        "every handshake socket was closed by the client")

    async def test_close_during_an_unanswered_hello_closes_the_socket(self):
        srv = await self.scripted()
        srv.answer_hello = False
        c = self.client(request_timeout=30.0)
        start = asyncio.create_task(c.start())
        await wait_until(lambda: srv.hellos)
        await asyncio.wait_for(c.close(), 3.0)
        self.assertTrue(await asyncio.wait_for(start, 3.0))
        self.assert_all_closed()
        await wait_until(lambda: srv.eofs == 1)
        self.assertEqual(c._connecting, set())

    async def test_cancelled_start_closes_the_socket(self):
        srv = await self.scripted()
        srv.answer_hello = False
        c = self.client(request_timeout=30.0)
        start = asyncio.create_task(c.start())
        await wait_until(lambda: srv.hellos)
        start.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await start
        self.assert_all_closed()
        await wait_until(lambda: srv.eofs == 1)
        self.assertEqual(c._connecting, set())


class CloseTests(ClientCase):

    async def test_close_is_idempotent_and_fails_pending(self):
        srv = await self.scripted()
        c = self.client()
        await self.started_scripted(c, srv)
        task = asyncio.create_task(c.request_refresh())
        await srv.expect("refresh")
        await c.close()
        self.assertIsNone(await asyncio.wait_for(task, 2.0))
        await c.close()
        self.assertIsNone(c._link)
        self.assertEqual(c._bg, set())


if __name__ == "__main__":
    unittest.main(verbosity=2)
