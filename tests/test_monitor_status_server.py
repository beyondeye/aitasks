"""In-process tests for the monitor status server (t2037_1).

`StatusServer` on a scratch Unix socket, driven by real protocol clients. Most
tests use `FakeProducer` (the `TmuxMonitor` slice the server calls, with an
ordered call log). The two race tests — pins vs a partial refresh, and a
compare-mode change vs an in-flight tick — drive a REAL `TmuxMonitor` whose tmux
calls are stubbed (`_tmux_async`), because the bug they guard lives in the
producer's own state.

No tmux server is reached. `tests/test_monitor_status_server_live.py` covers the
process lifecycle against an isolated real tmux server.

Run:
  python3 tests/test_monitor_status_server.py
"""
from __future__ import annotations

import asyncio
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "lib"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from monitor import status_protocol as sp  # noqa: E402
from monitor import status_recording as sr  # noqa: E402
from monitor import status_server as ss  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    SESSION_CONFIG_KEYS, ClassifyResult, PaneCategory, PaneSnapshot, TmuxMonitor,
    TmuxPaneInfo,
)

VERSION = sr.framework_version()
SESSION = "s1"


def pane(pane_id: str, window: str = "agent-pick-1", *, session: str = SESSION,
         category: PaneCategory = PaneCategory.AGENT, shadow_target: str = "") -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index="1", window_name=window, pane_index="0", pane_id=pane_id,
        pane_pid=999991, current_command="node", width=80, height=24,
        category=category, session_name=session, shadow_target=shadow_target,
    )


def snap(p: TmuxPaneInfo, content: str = "live", **kw) -> PaneSnapshot:
    return PaneSnapshot(pane=p, content=content, timestamp=0.0, idle_seconds=1.0,
                        is_idle=False, **kw)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeProducer:
    """The `TmuxMonitor` slice `StatusServer` calls. `snaps` / `shadows` are what
    the next commit returns; `calls` logs the order of skip-set publishes and
    captures."""

    def __init__(self, root: Path):
        self.session = SESSION
        self.mapping = {SESSION: root}
        self.snaps: dict = {}
        self.shadows: dict = {}
        self.calls: list = []
        self.skip = frozenset()
        self.session_configs: list = []
        self.overrides: dict = {}
        self.exit_seen = False
        self.control_started = 0
        self.control_closed = 0
        self.started_sessions: list = []
        #: What the producer's TTL-cached session discovery would still return
        #: until `invalidate_sessions_cache` (None: no stale cache).
        self.stale_mapping = None
        self.contents: dict = {}
        self._gen = 0

    async def get_session_to_project_mapping_async(self):
        if self.stale_mapping is not None:
            return dict(self.stale_mapping)
        return dict(self.mapping)

    def invalidate_sessions_cache(self):
        self.stale_mapping = None

    def set_session_configs(self, configs):
        self.session_configs.append(configs)

    def set_parked_agents(self, pairs):
        self.skip = frozenset(pairs)
        self.calls.append(("skip", self.skip))

    async def capture_all_classified_async(self):
        self.calls.append("capture")
        self._gen += 1
        return self._gen, []

    def commit_snapshots(self, gen, classified):
        return dict(self.snaps)

    @property
    def capture_generation(self):
        return self._gen

    async def capture_pane_classified_async(self, pane_id, capture_lines=None):
        self.calls.append(("capture_one", pane_id))
        self._gen += 1
        s = self.snaps.get(pane_id)
        if s is None:
            return self._gen, None, None, None
        return self._gen, s.pane, s.content, ClassifyResult(compare_value=s.content)

    def commit_snapshot(self, gen, p, content, result):
        return self.snaps.get(p.pane_id)

    async def refresh_shadow_snapshot(self, followed):
        self.calls.append(("refresh_shadow", followed))
        return self.shadows.get(followed)

    async def capture_pane_content_async(self, pane_id, capture_lines=None, pane=None):
        if pane_id not in self.contents:
            return None
        return pane, self.contents[pane_id]

    def shadow_snapshots(self):
        return dict(self.shadows)

    def get_compare_mode(self, pane_id):
        return self.overrides.get(pane_id, "stripped")

    def is_compare_mode_overridden(self, pane_id):
        return pane_id in self.overrides

    def set_compare_mode(self, pane_id, mode):
        if mode is None:
            self.overrides.pop(pane_id, None)
        else:
            self.overrides[pane_id] = mode
        return self.get_compare_mode(pane_id)

    def cycle_compare_mode(self, pane_id):
        cur = self.overrides.get(pane_id)
        new = "raw" if cur is None else ("stripped" if cur == "raw" else None)
        return self.set_compare_mode(pane_id, new), new is None

    def get_last_change_wall(self, pane_id):
        return None

    def last_enumerated_sessions(self):
        return frozenset(self.mapping)

    def last_discovered_agents(self):
        return frozenset((s.pane.session_name, s.pane.window_name) for s in self.snaps.values())

    def last_discovered_panes(self):
        return {}

    def control_state(self):
        return SimpleNamespace(value="connected")

    def control_exit_seen(self):
        return self.exit_seen

    async def close_control_client(self):
        self.control_closed += 1
        self.exit_seen = False

    async def start_control_client(self):
        self.control_started += 1
        self.started_sessions.append(self.session)
        return True


class FakeMarks:
    def __init__(self):
        self.parked: set = set()

    def refresh(self):
        return False

    def parked_windows(self):
        return set(self.parked)


class FakeTaskCache:
    """window name -> task id; ids in `done` resolve to a Done task."""

    def __init__(self):
        self.ids: dict = {}
        self.done: set = set()

    def update_session_mapping(self, mapping):
        pass

    def get_task_id_for_pane(self, p):
        return self.ids.get(p.window_name)

    def get_task_info(self, task_id, session_name=""):
        return SimpleNamespace(status="Done" if task_id in self.done else "Implementing",
                               task_file_abs=f"/x/aitasks/t{task_id}.md")


class Client:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer

    @classmethod
    async def open(cls, path) -> "Client":
        reader, writer = await asyncio.open_unix_connection(
            str(path), limit=sp.MAX_SERVER_LINE_BYTES)
        return cls(reader, writer)

    async def send(self, msg: dict) -> None:
        self.writer.write(sp.encode(msg, direction=sp.CLIENT))
        await self.writer.drain()

    async def recv(self, timeout: float = 3.0):
        line = await asyncio.wait_for(sp.read_line(self.reader), timeout)
        return None if line is None else sp.decode(line, direction=sp.SERVER)

    async def hello(self, *, version: str = VERSION, proto: int = sp.PROTO):
        await self.send({"type": "hello", "proto": proto, "version": version,
                         "client": {"kind": "test"}})
        return await self.recv()

    async def close(self):
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass


async def wait_until(predicate, timeout: float = 3.0, step: float = 0.01):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while not predicate():
        if loop.time() > end:
            raise AssertionError("condition not reached in time")
        await asyncio.sleep(step)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

class ServerCase(unittest.IsolatedAsyncioTestCase):
    """A started `StatusServer` over `FakeProducer` on a scratch socket.

    `interval_override` is huge, so ticks happen only on a stale subscribe and
    on `refresh` — the tests drive every generation explicitly."""

    grace = 60.0

    def make_monitor(self, root: Path):
        return FakeProducer(root)

    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.sock = self.root / "s.sock"
        self.fake = self.make_monitor(self.root)
        self.marks = FakeMarks()
        self.tasks = FakeTaskCache()
        self.server = ss.StatusServer(
            self.fake, socket_path=self.sock, version=VERSION, project_root=self.root,
            grace=self.grace, marks_view=self.marks, task_cache=self.tasks,
            watchdog_interval=0.02, interval_override=1000.0,
            start_control_client=False, hello_timeout=5.0,
        )
        await self.server.start()
        self.clients: list = []

    async def asyncTearDown(self):
        for c in self.clients:
            await c.close()
        await self.server.close()
        self._tmp.cleanup()

    async def client(self, *, hello: bool = True) -> Client:
        c = await Client.open(self.sock)
        self.clients.append(c)
        if hello:
            welcome = await c.hello()
            self.assertEqual(welcome["type"], "welcome")
        return c

    async def subscribed(self, **sub) -> tuple:
        c = await self.client()
        await c.send({"type": "subscribe", **sub})
        snapshot = await c.recv()
        self.assertEqual(snapshot["type"], "snapshot")
        state = sp.StreamState()
        state.apply(snapshot)
        return c, state, snapshot

    @property
    def realroot(self) -> str:
        return os.path.realpath(str(self.root))


# ---------------------------------------------------------------------------
# Handshake
# ---------------------------------------------------------------------------

class HandshakeTests(ServerCase):

    async def test_welcome(self):
        c = await self.client(hello=False)
        welcome = await c.hello()
        self.assertEqual(welcome["type"], "welcome")
        self.assertEqual(welcome["server"]["impl"], "python")
        self.assertEqual(welcome["server"]["pid"], os.getpid())
        self.assertEqual(welcome["version"], VERSION)
        self.assertEqual(welcome["proto"], sp.PROTO)

    async def test_version_mismatch_closes(self):
        c = await self.client(hello=False)
        err = await c.hello(version=VERSION + "-other")
        self.assertEqual(err["code"], "version_mismatch")
        self.assertEqual(err["server_version"], VERSION)
        self.assertIsNone(await c.recv())

    async def test_proto_mismatch_closes(self):
        c = await self.client(hello=False)
        err = await c.hello(proto=sp.PROTO + 98)
        self.assertEqual(err["code"], "proto_mismatch")
        self.assertEqual(err["server_proto"], sp.PROTO)
        self.assertIsNone(await c.recv())

    async def test_request_before_hello_closes(self):
        c = await self.client(hello=False)
        await c.send({"type": "subscribe", "id": 7})
        err = await c.recv()
        self.assertEqual((err["code"], err.get("id")), ("bad_message", 7))
        self.assertIsNone(await c.recv())

    async def test_hello_timeout_closes(self):
        self.server.hello_timeout = 0.2
        c = await self.client(hello=False)
        err = await c.recv()
        self.assertEqual(err["code"], "bad_message")
        self.assertIsNone(await c.recv())

    async def test_unknown_type_keeps_connection(self):
        c = await self.client()
        c.writer.write(b'{"type":"frobnicate","id":"q"}\n')
        await c.writer.drain()
        err = await c.recv()
        self.assertEqual((err["code"], err.get("id")), ("unknown_type", "q"))
        await c.send({"type": "set_pins", "id": 1, "pins": []})
        self.assertEqual((await c.recv())["type"], "result")


# ---------------------------------------------------------------------------
# Generations and ordering
# ---------------------------------------------------------------------------

class OrderingTests(ServerCase):

    def setUp(self):
        self.p1, self.p2 = pane("%1", "agent-a"), pane("%2", "agent-b")

    async def test_contiguous_deltas_resync_and_result_order(self):
        self.fake.snaps = {"%1": snap(self.p1, "one"), "%2": snap(self.p2, "two")}
        a, sa, snap_a = await self.subscribed(id="a1")
        self.assertEqual((snap_a["gen"], snap_a.get("id")), (1, "a1"))
        b, sb, snap_b = await self.subscribed()
        self.assertEqual(snap_b["gen"], 1, "a fresh state is not re-ticked")

        self.fake.snaps["%1"] = snap(self.p1, "one-b")
        await a.send({"type": "refresh", "id": "r1"})
        delta = await a.recv()
        result = await a.recv()
        self.assertEqual((delta["type"], delta["gen"]), ("delta", 2))
        self.assertEqual((result["type"], result["request"], result["gen"], result["id"]),
                         ("result", "refresh", 2, "r1"),
                         "the refresh result follows the delta carrying its gen")
        sa.apply(delta)
        self.assertEqual(sa.records()["%1"]["content"], "one-b")
        db = await b.recv()
        self.assertEqual(db["gen"], 2)
        sb.apply(db)

        # Resync mid-stream: the reply snapshot's gen equals the last delta.
        self.fake.snaps["%2"] = snap(self.p2, "two-b")
        await a.send({"type": "refresh"})
        self.assertEqual((await b.recv())["gen"], 3)
        await b.send({"type": "subscribe", "id": "b2"})
        resync = await b.recv()
        self.assertEqual((resync["type"], resync["gen"], resync["id"]), ("snapshot", 3, "b2"))
        sb.apply(resync)
        await a.send({"type": "refresh"})
        nxt = await b.recv()
        self.assertEqual((nxt["type"], nxt["gen"]), ("delta", 4))
        self.assertIsNotNone(sb.apply(nxt))

    async def test_set_content_reply_and_filtered_deltas(self):
        self.fake.snaps = {"%1": snap(self.p1, "one"), "%2": snap(self.p2, "two")}
        a, sa, _ = await self.subscribed()
        await a.send({"type": "set_content", "id": 5, "content": ["%2"]})
        reply = await a.recv()
        self.assertEqual((reply["type"], reply["id"], reply["gen"]), ("snapshot", 5, 1))
        self.assertNotIn("content", reply["panes"]["%1"])
        self.assertEqual(reply["panes"]["%2"]["content"], "two")
        self.fake.snaps["%1"] = snap(self.p1, "one-changed")
        await a.send({"type": "refresh"})
        delta = await a.recv()
        self.assertEqual(delta["gen"], 2)
        self.assertNotIn("%1", delta.get("panes", {}),
                         "a content-only patch of an unselected pane is not sent")

    async def test_set_content_requires_subscribe(self):
        c = await self.client()
        await c.send({"type": "set_content", "content": "none"})
        self.assertEqual((await c.recv())["code"], "not_subscribed")

    async def test_failed_capture_is_removed_then_returns_full(self):
        self.fake.snaps = {"%1": snap(self.p1, "one"), "%2": snap(self.p2, "two")}
        a, sa, _ = await self.subscribed()
        del self.fake.snaps["%2"]
        await a.send({"type": "refresh"})
        delta = await a.recv()
        self.assertEqual(delta["removed"], ["%2"])
        sa.apply(delta)
        self.fake.snaps["%2"] = snap(self.p2, "two")
        await a.recv()  # the refresh result
        await a.send({"type": "refresh"})
        delta = await a.recv()
        self.assertIn("content", delta["panes"]["%2"], "a returning pane is a full record")
        sa.apply(delta)


# ---------------------------------------------------------------------------
# Pins and the skip set
# ---------------------------------------------------------------------------

class SkipSetTests(ServerCase):

    def last_skip_before_last_capture(self):
        last_capture = max(i for i, c in enumerate(self.fake.calls) if c == "capture")
        skips = [c for c in self.fake.calls[:last_capture] if isinstance(c, tuple) and c[0] == "skip"]
        self.assertTrue(skips, "no skip set was published before the capture")
        return skips[-1][1]

    async def test_skip_set_is_global_minus_union_of_pins(self):
        self.marks.parked = {(self.realroot, "agent-p7"), (self.realroot, "agent-p8")}
        a, _, _ = await self.subscribed(pins=[[SESSION, "agent-p7"]])
        self.assertEqual(self.last_skip_before_last_capture(),
                         {(SESSION, "agent-p8")})

        b, _, _ = await self.subscribed(pins=[[SESSION, "agent-p8"]])
        self.assertEqual(self.fake.skip, frozenset(), "both parked agents are pinned")

        await b.send({"type": "set_pins", "id": 2, "pins": "all"})
        self.assertEqual((await b.recv())["request"], "set_pins")
        await a.send({"type": "refresh"})
        self.assertEqual((await a.recv())["type"], "delta")
        self.assertEqual((await a.recv())["request"], "refresh")
        self.assertEqual(self.last_skip_before_last_capture(), frozenset())

        await b.close()
        self.clients.remove(b)
        await wait_until(lambda: self.fake.skip == {(SESSION, "agent-p8")})

        await a.send({"type": "set_pins", "pins": []})
        self.assertEqual((await a.recv())["request"], "set_pins")
        self.assertEqual(self.fake.skip, {(SESSION, "agent-p7"), (SESSION, "agent-p8")})

    async def test_pins_before_subscribe_do_not_count(self):
        self.marks.parked = {(self.realroot, "agent-p7")}
        c = await self.client()
        await c.send({"type": "set_pins", "pins": "all"})
        await c.recv()
        a, _, _ = await self.subscribed()
        self.assertEqual(self.last_skip_before_last_capture(), {(SESSION, "agent-p7")})


# ---------------------------------------------------------------------------
# completed, compare mode, capture, refresh interval
# ---------------------------------------------------------------------------

class MembersTests(ServerCase):

    async def test_completed_excludes_parked_and_globally_parked(self):
        p1, p2, p3, p4 = (pane("%1", "agent-pick-11"), pane("%2", "agent-pick-12"),
                          pane("%3", "agent-pick-13"), pane("%4", "agent-pick-14"))
        self.tasks.ids = {"agent-pick-11": "11", "agent-pick-12": "12",
                          "agent-pick-13": "13", "agent-pick-14": "14"}
        self.tasks.done = {"11", "12", "13"}
        self.marks.parked = {(self.realroot, "agent-pick-12"), (self.realroot, "agent-pick-13")}
        self.fake.snaps = {
            "%1": snap(p1),
            "%2": snap(p2),                          # pinned live by someone, globally parked
            "%3": snap(p3, "", parked=True),         # parked placeholder
            "%4": snap(p4),                          # not done
        }
        _, state, snapshot = await self.subscribed(pins=[[SESSION, "agent-pick-12"]])
        self.assertEqual(snapshot["completed"], ["%1"])
        self.assertEqual(sorted(map(tuple, snapshot["parked"])),
                         [(SESSION, "agent-pick-12"), (SESSION, "agent-pick-13")])

    async def test_compare_mode_is_shared(self):
        self.fake.snaps = {"%1": snap(pane("%1"))}
        a, _, _ = await self.subscribed()
        b, sb, _ = await self.subscribed()
        await a.send({"type": "set_compare_mode", "id": 1, "pane": "%1", "mode": "raw"})
        res = await a.recv()
        self.assertEqual((res["mode"], res["following_default"]), ("raw", False))
        await a.send({"type": "refresh"})
        delta = await b.recv()
        self.assertEqual(delta["panes"]["%1"]["compare_mode"], "raw")
        self.assertTrue(delta["panes"]["%1"]["compare_override"])
        await a.recv(); await a.recv()  # a's delta and refresh result
        await a.send({"type": "cycle_compare_mode", "pane": "%1"})
        res = await a.recv()
        self.assertEqual((res["request"], res["mode"]), ("cycle_compare_mode", "stripped"))
        await a.send({"type": "set_compare_mode", "pane": "%9", "mode": None})
        self.assertEqual((await a.recv())["code"], "not_found")

    async def test_capture_tail_and_not_found(self):
        self.fake.snaps = {"%1": snap(pane("%1"))}
        self.fake.contents = {"%1": "l1\nl2\nl3\n"}
        a, _, _ = await self.subscribed()
        await a.send({"type": "capture", "id": "c", "pane": "%1", "lines": 2})
        res = await a.recv()
        self.assertEqual((res["pane"], res["content"], res["id"]), ("%1", "l2\nl3\n", "c"))
        await a.send({"type": "capture", "pane": "%55", "lines": 2})
        self.assertEqual((await a.recv())["code"], "not_found")

    async def test_capture_of_a_shadow_pane(self):
        self.fake.snaps = {"%1": snap(pane("%1"))}
        self.fake.shadows = {"%1": snap(pane("%12", "agent-pick-1", shadow_target="%1"), "sh")}
        self.fake.contents = {"%12": "shadow text\n"}
        a, _, snapshot = await self.subscribed()
        self.assertIn("%1", snapshot["shadows"])
        await a.send({"type": "capture", "pane": "%12", "lines": 5})
        self.assertEqual((await a.recv())["content"], "shadow text\n")

    async def test_only_monitor_keys_reach_the_producer(self):
        cfg = self.root / "aitasks" / "metadata"
        cfg.mkdir(parents=True)
        (cfg / "project_config.yaml").write_text(
            "tmux:\n  monitor:\n    refresh_seconds: 2\n    idle_threshold_seconds: 9\n")
        await self.subscribed()
        published = self.fake.session_configs[-1][SESSION]
        self.assertLessEqual(set(published), set(SESSION_CONFIG_KEYS))
        self.assertEqual(published["idle_threshold"], 9.0)
        self.assertNotIn("refresh_seconds", published)


class IntervalTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.cache = ss.ProjectConfigCache()

    def tearDown(self):
        self._tmp.cleanup()

    def project(self, name: str, refresh=None, *, file: bool = True) -> Path:
        root = self.base / name
        meta = root / "aitasks" / "metadata"
        meta.mkdir(parents=True)
        if file:
            body = "tmux:\n  monitor:\n"
            body += f"    refresh_seconds: {refresh}\n" if refresh is not None else "    capture_lines: 100\n"
            (meta / "project_config.yaml").write_text(body)
        return root

    def interval(self, *roots) -> float:
        return ss.tick_interval([self.cache.get(r) for r in roots])

    def test_minimum_over_projects(self):
        self.assertEqual(self.interval(self.project("a", 7), self.project("b", 2)), 2.0)

    def test_default_is_resolved_per_project_before_the_minimum(self):
        self.assertEqual(self.interval(self.project("a", 7), self.project("b")), 3.0)
        self.assertEqual(self.interval(self.project("c", 7), self.project("d", file=False)), 3.0)

    def test_clamp(self):
        self.assertEqual(self.interval(self.project("a", 0.2)), 1.0)
        self.assertEqual(self.interval(self.project("b", 500)), 60.0)

    def test_invalid_values_resolve_to_the_default(self):
        for i, bad in enumerate(['"fast"', "true", "0", "-1", ".nan"]):
            with self.subTest(value=bad):
                self.assertEqual(self.interval(self.project(f"x{i}", 7),
                                               self.project(f"y{i}", bad)), 3.0)

    def test_nothing_mapped(self):
        self.assertEqual(ss.tick_interval([]), 3.0)

    def test_an_oversized_integer_clamps_instead_of_overflowing(self):
        self.assertEqual(ss.refresh_seconds_of({"monitor": {"refresh_seconds": 10 ** 400}}), 60.0)
        root = self.project("huge", "1" + "0" * 400)
        self.assertEqual(self.interval(root), 60.0)
        self.assertEqual(self.interval(root, self.project("small", 2)), 2.0)

    def test_cache_rereads_on_change(self):
        root = self.project("a", 7)
        self.assertEqual(self.cache.get(root).refresh_seconds, 7.0)
        (root / "aitasks" / "metadata" / "project_config.yaml").write_text(
            "tmux:\n  monitor:\n    refresh_seconds: 4.5\n")
        self.assertEqual(self.cache.get(root).refresh_seconds, 4.5)


class SchedulingTests(ServerCase):
    """Review findings: full-scan cadence, resync selection order, retry pacing."""

    def fast_ticks(self, interval: float) -> None:
        self.server._interval_override = interval
        self.server.interval = interval

    def captures(self) -> int:
        return sum(1 for c in self.fake.calls if c == "capture")

    async def drain(self, client: Client, seconds: float) -> list:
        msgs = []
        loop = asyncio.get_running_loop()
        end = loop.time() + seconds
        while loop.time() < end:
            try:
                msgs.append(await client.recv(timeout=max(0.01, end - loop.time())))
            except asyncio.TimeoutError:
                break
        return msgs

    async def test_partial_refreshes_do_not_postpone_full_scans(self):
        self.fake.snaps = {"%1": snap(pane("%1"))}
        self.fast_ticks(0.1)
        a, _, _ = await self.subscribed()
        before = self.captures()
        for _ in range(12):
            await a.send({"type": "refresh", "panes": ["%1"]})
            await asyncio.sleep(0.04)
        await self.drain(a, 0.05)
        self.assertGreaterEqual(self.captures() - before, 3,
                                "sustained partial refreshes starved full discovery")

    async def test_resync_tick_delta_uses_the_old_selection(self):
        self.fake.snaps = {"%1": snap(pane("%1"))}
        shadow_pane = pane("%12", shadow_target="%1")
        self.fake.shadows = {"%1": snap(shadow_pane, "sh-1")}
        b, state, first = await self.subscribed(include_shadows=False)
        self.assertEqual(first["shadows"], {})
        self.fake.shadows = {"%1": snap(shadow_pane, "sh-2")}
        self.server._last_full_tick = self.server._clock() - 10_000   # force a stale resync
        await b.send({"type": "subscribe", "id": "re", "include_shadows": True})
        delta = await b.recv()
        reply = await b.recv()
        self.assertEqual(delta["type"], "delta")
        self.assertNotIn("shadows", delta,
                         "the prerequisite tick's delta used the NEW selection")
        state.apply(delta)
        self.assertEqual((reply["type"], reply["id"]), ("snapshot", "re"))
        self.assertEqual(reply["shadows"]["%1"]["content"], "sh-2")
        state.apply(reply)

    async def test_failed_ticks_are_paced_and_the_loop_stays_responsive(self):
        attempts = []

        async def broken():
            attempts.append(self.server._clock())
            # Yield once, so an unpaced retry loop shows up as a burst of
            # counted attempts rather than starving the test itself.
            await asyncio.sleep(0)
            raise RuntimeError("bad config")
        self.fake.get_session_to_project_mapping_async = broken
        self.fast_ticks(0.05)
        a, _, snapshot = await self.subscribed()
        self.assertEqual(snapshot["gen"], 0, "a failed tick pretended a generation")
        loop = asyncio.get_running_loop()
        started = loop.time()
        await asyncio.sleep(0.5)
        elapsed = loop.time() - started
        self.assertLessEqual(len(attempts), elapsed / 0.05 + 3,
                             f"{len(attempts)} attempts in {elapsed:.2f}s: retries are not paced")
        self.assertGreaterEqual(len(attempts), 3, "a failed tick is never retried")
        t0 = loop.time()
        await a.send({"type": "set_pins", "pins": []})
        self.assertEqual((await a.recv(timeout=1.0))["request"], "set_pins")
        self.assertLess(loop.time() - t0, 0.5, "the loop is starved by retries")
        self.assertEqual(self.server._encoder.gen, 0)


# ---------------------------------------------------------------------------
# Lifecycle: idle, %exit, socket replaced, slow client
# ---------------------------------------------------------------------------

class LifecycleTests(ServerCase):
    grace = 0.3

    async def test_idle_exit_with_no_subscriber(self):
        reason = await asyncio.wait_for(self.server.serve_until_exit(), 5)
        self.assertEqual(reason, "idle")
        self.assertFalse(self.sock.exists())
        self.assertNotIn("capture", self.fake.calls, "ticks run only with subscribers")

    async def test_idle_grace_restarts_when_the_last_subscriber_leaves(self):
        a, _, _ = await self.subscribed()
        await asyncio.sleep(0.5)
        self.assertIsNone(self.server.exit_reason, "a subscriber holds the server")
        await a.close()
        self.clients.remove(a)
        reason = await asyncio.wait_for(self.server.serve_until_exit(), 5)
        self.assertEqual(reason, "idle")

    async def test_exit_seen_with_tmux_gone_exits(self):
        self.server.grace = 60
        self.server._probe_tmux = lambda: None
        self.fake.exit_seen = True
        reason = await asyncio.wait_for(self.server.serve_until_exit(), 5)
        self.assertEqual(reason, "exit_seen")

    async def test_exit_seen_from_a_session_detach_restarts_the_control_client(self):
        self.server.grace = 60
        self.server._probe_tmux = lambda: "/tmp/tmux-x/default"
        self.server._expected_tmux_socket = "/tmp/tmux-x/default"
        self.fake.exit_seen = True
        await wait_until(lambda: self.fake.control_started >= 1)
        self.assertGreaterEqual(self.fake.control_closed, 1)
        self.assertIsNone(self.server.exit_reason)
        c = await self.client()   # still serving
        await c.send({"type": "set_pins", "pins": []})
        self.assertEqual((await c.recv())["type"], "result")

    async def test_restart_after_exit_skips_the_session_that_went_away(self):
        # The last tick's mapping still lists the destroyed session; the
        # restart must pick from the live sessions instead (t2245).
        self.server.grace = 60
        self.server._probe_tmux = lambda: "/tmp/tmux-x/default"
        self.server._expected_tmux_socket = "/tmp/tmux-x/default"
        self.server._mapping = {SESSION: self.root, "s2": self.root}
        self.fake.stale_mapping = {SESSION: self.root, "s2": self.root}
        self.fake.mapping = {"s2": self.root}
        self.fake.exit_seen = True
        await wait_until(lambda: self.fake.control_started >= 1)
        self.assertEqual(self.fake.started_sessions, ["s2"])

    async def test_socket_replaced_exits_and_leaves_the_stranger(self):
        self.server.grace = 60
        os.unlink(self.sock)
        stranger = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        stranger.bind(str(self.sock))
        try:
            ino = os.lstat(self.sock).st_ino
            reason = await asyncio.wait_for(self.server.serve_until_exit(), 5)
            self.assertEqual(reason, "socket_replaced")
            self.assertEqual(os.lstat(self.sock).st_ino, ino, "the stranger's socket was removed")
        finally:
            stranger.close()

    async def test_slow_subscriber_is_dropped_alone(self):
        self.server.grace = 60
        self.server.outbound_limit = 3
        self.server.writer_close_timeout = 0.1
        self.fake.snaps = {"%1": snap(pane("%1"))}
        slow, _, _ = await self.subscribed()
        (conn,) = list(self.server._connections)

        async def never():
            await asyncio.Event().wait()
        conn.writer.drain = never
        fast, sf, _ = await self.subscribed()
        for i in range(8):
            self.fake.snaps["%1"] = snap(pane("%1"), f"v{i}")
            await self.server.run_tick()
            delta = await fast.recv()
            self.assertIsNotNone(sf.apply(delta))
        await wait_until(lambda: conn not in self.server._connections)
        self.assertEqual(len(self.server._connections), 1)


# ---------------------------------------------------------------------------
# Recorder against the server
# ---------------------------------------------------------------------------

class RecordTests(ServerCase):

    async def test_record_connect_then_check(self):
        p1 = pane("%1")
        self.fake.snaps = {"%1": snap(p1, "a")}
        out = self.root / "rec.jsonl"
        recording = asyncio.create_task(sr.record_connect(self.sock, out, max_deltas=3))
        await wait_until(lambda: self.server._subscriber_count() == 1)
        driver = await self.client()
        for i in range(3):
            self.fake.snaps = {"%1": snap(p1, f"a{i}")}
            if i == 1:
                self.fake.snaps["%2"] = snap(pane("%2", "agent-b"), "b")
            await driver.send({"type": "refresh"})
            await driver.recv()
        result = await asyncio.wait_for(recording, 5)
        self.assertTrue(result.published, result.reason)
        summary = sr.check_recording(out)
        self.assertEqual(summary["deltas"], 3)


# ---------------------------------------------------------------------------
# Races against a REAL TmuxMonitor (tmux stubbed)
# ---------------------------------------------------------------------------

def list_panes_line(pane_id: str, window: str, win_idx: str) -> str:
    # The 16-field `_LIST_PANES_FORMAT` record; pid 999991 is no companion.
    return "\t".join([win_idx, window, "0", pane_id, "999991", "node", "80", "24",
                      "", "10", "", "", "", "", "0", ""])


class StubTmux:
    def __init__(self, windows: dict, contents: dict):
        self.windows = windows          # pane id -> (window, index)
        self.contents = contents        # pane id -> capture text
        self.captured: list = []

    async def __call__(self, args, timeout=5.0):
        if args and args[0] == "list-panes":
            lines = [list_panes_line(pid, w, i) for pid, (w, i) in self.windows.items()]
            return 0, "\n".join(lines) + "\n"
        if args and args[0] == "capture-pane":
            pane_id = args[args.index("-t") + 1]
            self.captured.append(pane_id)
            if pane_id not in self.contents:
                return 1, ""
            return 0, self.contents[pane_id]
        return 1, ""


class RealProducerCase(ServerCase):

    def make_monitor(self, root: Path):
        mon = TmuxMonitor(session=SESSION)
        self.stub = StubTmux({}, {})
        mon._tmux_async = self.stub

        async def sessions():
            return [SESSION]

        async def mapping():
            return {SESSION: root}

        mon._target_sessions_async = sessions
        mon.get_session_to_project_mapping_async = mapping
        return mon


class PinsThenPartialRefreshTests(RealProducerCase):

    async def test_set_pins_takes_effect_on_the_next_partial_refresh(self):
        self.stub.windows = {"%7": ("agent-p7", "1")}
        self.stub.contents = {"%7": "live seven\n"}
        self.marks.parked = {(self.realroot, "agent-p7")}
        a, state, snapshot = await self.subscribed()
        self.assertTrue(snapshot["panes"]["%7"]["parked"], "parked placeholder first")
        self.assertNotIn("%7", self.stub.captured)

        await a.send({"type": "set_pins", "pins": [[SESSION, "agent-p7"]]})
        await a.recv()
        await a.send({"type": "refresh", "panes": ["%7"]})
        delta = await a.recv()
        state.apply(delta)
        rec = state.records()["%7"]
        self.assertFalse(rec["parked"], "the pin was ignored by the single-pane capture")
        self.assertEqual(rec["content"], "live seven\n")
        await a.recv()  # refresh result

        await a.send({"type": "set_pins", "pins": []})
        await a.recv()
        await a.send({"type": "refresh", "panes": ["%7"]})
        delta = await a.recv()
        state.apply(delta)
        self.assertTrue(state.records()["%7"]["parked"], "the removed pin still applied")

    async def test_set_pins_republishes_before_any_capture(self):
        """The `set_pins` guard alone: the producer's skip set changes with the
        `result`, before any capture route could republish it."""
        mon = self.server.monitor
        self.stub.windows = {"%7": ("agent-p7", "1")}
        self.stub.contents = {"%7": "live seven\n"}
        self.marks.parked = {(self.realroot, "agent-p7")}
        a, _, _ = await self.subscribed()
        self.assertEqual(mon._parked_agents, {(SESSION, "agent-p7")})
        await a.send({"type": "set_pins", "pins": [[SESSION, "agent-p7"]]})
        await a.recv()
        self.assertEqual(mon._parked_agents, frozenset())

    async def test_partial_refresh_republishes_a_marks_change(self):
        """The partial-refresh guard alone: the agent is unparked in the marks
        store after the last tick, with no `set_pins` in between."""
        self.stub.windows = {"%7": ("agent-p7", "1")}
        self.stub.contents = {"%7": "live seven\n"}
        self.marks.parked = {(self.realroot, "agent-p7")}
        a, state, snapshot = await self.subscribed()
        self.assertTrue(snapshot["panes"]["%7"]["parked"])
        self.marks.parked = set()
        await a.send({"type": "refresh", "panes": ["%7"]})
        delta = await a.recv()
        state.apply(delta)
        self.assertFalse(state.records()["%7"]["parked"],
                         "the partial refresh captured under a stale skip set")


class CompareModeRaceTests(RealProducerCase):
    """A compare-mode change sent while a tick is blocked inside its offloaded
    classify. Serialized, the old tick's commit lands first and the setter then
    drops the baseline; unserialized (control), the old tick writes a
    stripped-form baseline AFTER the setter."""

    CONTENT = "\x1b[31mhello\x1b[0m\n"

    def install_barrier(self):
        self.block = False
        self.entered = asyncio.Event()
        self.gate = asyncio.Event()
        mon = self.server.monitor

        async def offload(fn):
            if self.block:
                self.entered.set()
                await self.gate.wait()
            return fn()
        mon._run_offloaded = offload

    async def start_blocked_tick(self, a: Client):
        self.block = True
        await a.send({"type": "refresh", "id": "tick"})
        await asyncio.wait_for(self.entered.wait(), 3)

    async def test_serialized_mode_change_leaves_no_stale_baseline(self):
        mon = self.server.monitor
        self.stub.windows = {"%1": ("agent-a", "1")}
        self.stub.contents = {"%1": self.CONTENT}
        self.install_barrier()
        a, state, _ = await self.subscribed()
        await self.start_blocked_tick(a)
        await a.send({"type": "set_compare_mode", "id": "mode", "pane": "%1", "mode": "raw"})
        await asyncio.sleep(0.05)
        self.block = False
        self.gate.set()
        order = [await a.recv() for _ in range(3)]
        kinds = [(m["type"], m.get("id")) for m in order]
        self.assertLess(kinds.index(("delta", None)), kinds.index(("result", "mode")),
                        f"the mode result overtook the in-flight tick: {kinds}")
        self.assertNotIn("%1", mon._last_content,                                 # (b)
                         "a stale baseline was written after the setter dropped it")
        await a.send({"type": "refresh"})
        await a.recv(); await a.recv()
        self.assertEqual(mon._last_content["%1"], self.CONTENT)                    # (c)
        changed_at = mon._last_change_time["%1"]
        await a.send({"type": "refresh"})
        await a.recv(); await a.recv()
        self.assertEqual(mon._last_change_time["%1"], changed_at,                  # (d)
                         "an unchanged capture reset the idle clock")

    async def test_control_unserialized_setter_leaves_a_stale_baseline(self):
        mon = self.server.monitor
        self.stub.windows = {"%1": ("agent-a", "1")}
        self.stub.contents = {"%1": self.CONTENT}
        self.install_barrier()
        a, _, _ = await self.subscribed()
        await self.start_blocked_tick(a)
        mon.set_compare_mode("%1", "raw")      # bypasses the producer lock
        self.block = False
        self.gate.set()
        await a.recv(); await a.recv()
        self.assertIn("%1", mon._last_content,
                      "the race did not manifest, so the serialized test proves nothing")
        self.assertEqual(mon._last_content["%1"], "hello\n", "a stripped-form baseline")


if __name__ == "__main__":
    unittest.main(verbosity=2)
