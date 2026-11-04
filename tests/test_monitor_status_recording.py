"""Recording, replay and recorder tests for the monitor status protocol (t2034_3).

Covers ``.aitask-scripts/monitor/status_recording.py`` and the committed
synthetic fixture ``tests/fixtures/monitor_status/basic.jsonl``:

- the fixture checks, covers the scenario it claims, regenerates
  byte-identically, and contains nothing any prompt pattern matches (the
  ``fixture_prompt_self_scan`` mitigation, with a captured dialog as the
  negative control);
- the replayer's handshake, selection, requests, mid-playback resync /
  set_content ordering (gated pacer), and the oversized-line framing rule;
- the recorder: round trip against the replayer, its full-content contract and
  its completion guard;
- pacing and the CLI.
"""
from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / ".aitask-scripts", REPO_ROOT / ".aitask-scripts" / "lib",
           REPO_ROOT / "tests", REPO_ROOT / "tests" / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import monitor_status_scenarios as scenarios  # noqa: E402
import review_loop_fixtures as captured  # noqa: E402
from agent_keys import AGENT_KEYS  # noqa: E402
from monitor import status_protocol as sp  # noqa: E402
from monitor import status_recording as sr  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    COMPARE_MODE_STRIPPED,
    PaneCategory,
    classify_content,
)
from monitor.prompt_patterns import all_patterns  # noqa: E402

FIXTURE = scenarios.BASIC_FIXTURE
CLI = REPO_ROOT / ".aitask-scripts" / "monitor" / "status_recording.py"
STEP = 5.0  # generous per-message timeout for socket reads


def states_of(recording: sr.Recording):
    """Every reconstructed state of a recording, after each applied message."""
    state = sp.StreamState(require_content=True)
    out = []
    for msg in recording.messages[1:]:
        state.apply(msg)
        out.append((msg, state.frame()))
    return out


# ---------------------------------------------------------------------------
# The committed fixture
# ---------------------------------------------------------------------------

class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recording = sr.read_recording(FIXTURE)
        cls.states = states_of(cls.recording)

    def test_check_passes(self):
        summary = sr.check_recording(FIXTURE)
        self.assertEqual((summary["gen_first"], summary["gen_last"], summary["deltas"]),
                         (1, 6, 5))
        self.assertEqual(summary["version"], "synthetic")

    def test_order(self):
        types = [self.recording.header["type"]] + [m["type"] for m in self.recording.messages]
        self.assertEqual(types, ["recording", "welcome", "snapshot"] + ["delta"] * 5)
        gens = [m["gen"] for m in self.recording.messages[1:]]
        self.assertEqual(gens, list(range(1, 7)))

    def test_golden_regeneration_is_byte_identical(self):
        self.assertEqual(scenarios.render_basic(), FIXTURE.read_bytes(),
                         "regenerate with: python3 tests/lib/monitor_status_scenarios.py --write")

    def test_coverage(self):
        seen = {k: set() for k in ("sessions", "kinds", "categories", "control")}
        flags = dict.fromkeys(("idle", "active", "parked", "frozen", "shadow", "completed",
                               "unscoped_awaiting", "removed", "appeared", "compare_raw",
                               "awaiting_cleared"), False)
        awaiting_before: dict = {}
        prev_ids: set = set()
        for index, (msg, frame) in enumerate(self.states):
            seen["sessions"].update(frame.sessions)
            seen["control"].add(frame.control_state)
            flags["shadow"] |= bool(frame.shadows)
            flags["completed"] |= bool(frame.completed)
            flags["removed"] |= bool(msg.get("removed"))
            ids = set(frame.panes)
            if index:
                flags["appeared"] |= bool(ids - prev_ids)
            prev_ids = ids
            for pane_id, rec in frame.panes.items():
                seen["categories"].add(rec["pane"]["category"])
                is_agent = rec["pane"]["category"] == "agent"
                flags["parked"] |= rec["parked"]
                flags["frozen"] |= rec["frozen"]
                flags["compare_raw"] |= rec["compare_mode"] == "raw" and rec["compare_override"]
                live = is_agent and not rec["parked"] and not rec["frozen"]
                flags["idle"] |= live and rec["is_idle"] and not rec["awaiting_input"]
                flags["active"] |= live and rec["idle_seconds"] == 0.0
                if rec["awaiting_input"]:
                    seen["kinds"].add(rec["awaiting_input_kind"])
                    flags["unscoped_awaiting"] |= not rec["scoped"] and rec["agent_key"] == ""
                elif awaiting_before.get(pane_id):
                    flags["awaiting_cleared"] = True
                awaiting_before[pane_id] = rec["awaiting_input"]
        self.assertGreaterEqual(len(seen["sessions"]), 2)
        self.assertGreaterEqual(len(seen["kinds"]), 3)
        self.assertEqual(seen["categories"], {"agent", "tui", "other"})
        self.assertIn("reconnecting", seen["control"])
        for name, value in flags.items():
            self.assertTrue(value, f"fixture does not cover: {name}")
        self.assertTrue(self.states[-1][1].parked, "global parked set present")

    def test_check_rejects_a_contentless_full_record(self):
        lines = FIXTURE.read_bytes().splitlines(keepends=True)
        snap = json.loads(lines[2])
        del snap["panes"]["%1"]["content"]
        lines[2] = json.dumps(snap, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.jsonl"
            bad.write_bytes(b"".join(lines))
            with self.assertRaises(sr.RecordingError):
                sr.check_recording(bad)


class RecordingVersionGateTests(unittest.TestCase):
    def mutated(self, header=None, welcome=None) -> bytes:
        lines = FIXTURE.read_bytes().splitlines(keepends=True)
        for index, changes in ((0, header), (1, welcome)):
            if changes:
                obj = dict(json.loads(lines[index]), **changes)
                lines[index] = json.dumps(obj, sort_keys=True,
                                          separators=(",", ":")).encode() + b"\n"
        return b"".join(lines)

    def test_unsupported_or_inconsistent_versions_are_refused(self):
        cases = {
            "rev 99": self.mutated(header={"rev": 99}),
            "header proto 99": self.mutated(header={"proto": 99}),
            "welcome proto 99": self.mutated(welcome={"proto": 99}),
            "both proto 99": self.mutated(header={"proto": 99}, welcome={"proto": 99}),
            "version mismatch": self.mutated(welcome={"version": "0.1.0"}),
        }
        with tempfile.TemporaryDirectory() as tmp:
            for name, data in cases.items():
                with self.subTest(case=name):
                    with self.assertRaises(sr.RecordingError):
                        sr.parse_recording(data)
                    path = Path(tmp) / "bad.jsonl"
                    path.write_bytes(data)
                    with self.assertRaises(sr.RecordingError):
                        sr.check_recording(path)

    def test_a_supplied_recording_object_is_gated_too(self):
        rec = sr.read_recording(FIXTURE)
        rec.header = dict(rec.header, proto=99)
        with self.assertRaises(sr.RecordingError):
            sr.check_recording(rec)

    def test_any_recorded_framework_version_is_accepted(self):
        data = self.mutated(header={"version": "0.1.0"}, welcome={"version": "0.1.0"})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "old.jsonl"
            path.write_bytes(data)
            self.assertEqual(sr.check_recording(path)["version"], "0.1.0")


class FixturePromptSelfScanTests(unittest.TestCase):
    """Post-phase mitigation ``fixture_prompt_self_scan``: nothing in the
    committed fixture may look like a dialog to any prompt pattern."""

    @staticmethod
    def detected(text: str) -> str:
        patterns = all_patterns()
        for agent in ("",) + tuple(AGENT_KEYS):
            result = classify_content(text, COMPARE_MODE_STRIPPED, patterns,
                                      PaneCategory.AGENT, agent)
            if result.awaiting_input:
                return f"{result.awaiting_input_kind} (agent={agent!r})"
        return ""

    def test_negative_control_a_captured_dialog_is_detected(self):
        self.assertTrue(self.detected(captured.CODEX_PERMISSION_RAW))

    def test_no_fixture_content_or_line_matches_any_pattern(self):
        recording = sr.read_recording(FIXTURE)
        texts = []
        for _msg, frame in states_of(recording):
            for entries in (frame.panes, frame.shadows):
                for key, rec in entries.items():
                    texts.append((f"content of {key}", rec.get("content", "")))
        for number, raw in enumerate(FIXTURE.read_bytes().splitlines(), start=1):
            texts.append((f"raw line {number}", raw.decode("utf-8")))
        self.assertGreater(len(texts), 50)
        for where, text in texts:
            with self.subTest(where=where):
                self.assertEqual(self.detected(text), "", where)


# ---------------------------------------------------------------------------
# Socket helpers
# ---------------------------------------------------------------------------

class Client:
    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer

    @classmethod
    async def connect(cls, path):
        reader, writer = await asyncio.open_unix_connection(
            str(path), limit=sp.MAX_SERVER_LINE_BYTES)
        return cls(reader, writer)

    async def send(self, msg):
        self.writer.write(sp.encode(msg, direction=sp.CLIENT))
        await self.writer.drain()

    async def send_raw(self, data: bytes):
        self.writer.write(data)
        await self.writer.drain()

    async def recv(self, timeout=STEP):
        line = await asyncio.wait_for(sp.read_line(self.reader), timeout)
        return None if line is None else sp.decode(line, direction=sp.SERVER)

    async def recv_raw(self, timeout=STEP):
        return await asyncio.wait_for(sp.read_line(self.reader), timeout)

    async def hello(self, version="9.9.9"):
        await self.send({"type": "hello", "proto": sp.PROTO, "version": version,
                         "client": {"kind": "test"}})
        return await self.recv()

    async def closed(self) -> bool:
        """True when the peer closed the connection: EOF, or the reset or broken
        pipe a write after the close surfaces as."""
        try:
            return await self.recv() is None
        except (ConnectionError, OSError):
            return True

    async def nothing_within(self, seconds=0.2):
        try:
            line = await asyncio.wait_for(sp.read_line(self.reader), seconds)
        except asyncio.TimeoutError:
            return True
        raise AssertionError(f"unexpected message: {line!r}")

    async def close(self):
        self.writer.close()
        with contextlib.suppress(Exception):
            await self.writer.wait_closed()


class Gate:
    """A pacer that holds playback until the test releases deltas."""

    def __init__(self):
        self.sem = asyncio.Semaphore(0)

    async def __call__(self, _index, _delay):
        await self.sem.acquire()

    def release(self, n=1):
        for _ in range(n):
            self.sem.release()


class SocketTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # /tmp keeps the socket path well within the AF_UNIX length limit.
        self.tmp = tempfile.mkdtemp(dir="/tmp", prefix="ait-msr-")
        self.sock = os.path.join(self.tmp, "s.sock")
        self.recording = sr.read_recording(FIXTURE)
        self.servers = []
        self.clients = []

    async def asyncTearDown(self):
        for client in self.clients:
            await client.close()
        for server in self.servers:
            await server.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    async def replay(self, **kw):
        server = sr.ReplayServer(self.recording, self.sock, **{"speed": 0, **kw})
        await server.start()
        self.servers.append(server)
        return server

    async def client(self):
        client = await Client.connect(self.sock)
        self.clients.append(client)
        return client


# ---------------------------------------------------------------------------
# Replayer
# ---------------------------------------------------------------------------

class ReplayerTests(SocketTestCase):
    async def test_handshake_echoes_version_and_marks_replay(self):
        await self.replay()
        welcome = await (await self.client()).hello("1.2.3")
        self.assertEqual(welcome["type"], "welcome")
        self.assertEqual(welcome["version"], "1.2.3")
        self.assertEqual(welcome["server"]["impl"], "replay")
        self.assertEqual(welcome["replay"], {"recorded_version": "synthetic",
                                             "source": "scenario:basic"})

    async def test_subscribe_streams_the_recording_verbatim(self):
        await self.replay()
        c = await self.client()
        await c.hello()
        await c.send({"type": "subscribe"})
        got = [await c.recv_raw() for _ in range(6)]
        self.assertEqual(got, self.recording.lines[1:])
        await c.nothing_within()

    async def _stream(self, subscribe):
        c = await self.client()
        await c.hello()
        await c.send(subscribe)
        return c, [await c.recv() for _ in range(6)]

    async def test_content_none_keeps_every_status_member(self):
        await self.replay()
        _c, msgs = await self._stream({"type": "subscribe", "content": "none"})
        for got, want in zip(msgs, self.recording.messages[1:]):
            self.assertEqual(got["gen"], want["gen"])
            self.assertEqual(got, sp.filter_message(want, content="none"))
            for rec in list(got.get("panes", {}).values()) + list(got.get("shadows", {}).values()):
                self.assertNotIn("content", rec)
        snap = msgs[0]
        self.assertEqual(set(snap["panes"]), set(self.recording.snapshot["panes"]))
        for key, rec in snap["panes"].items():
            full = dict(self.recording.snapshot["panes"][key])
            full.pop("content")
            self.assertEqual(rec, full)

    async def test_selected_pane_only(self):
        await self.replay()
        _c, msgs = await self._stream({"type": "subscribe", "content": ["%1"]})
        for msg in msgs:
            for group in ("panes", "shadows"):
                for key, rec in msg.get(group, {}).items():
                    if key != "%1":
                        self.assertNotIn("content", rec, f"{group}[{key}] gen {msg['gen']}")
        self.assertIn("content", msgs[0]["panes"]["%1"])
        self.assertTrue(all("content" in m["panes"]["%1"] for m in msgs[1:]))
        self.assertIn("content", msgs[1]["shadows"]["%1"])  # shadow follows %1

    async def test_requests(self):
        await self.replay()
        c = await self.client()
        await c.hello()
        await c.send({"type": "subscribe"})
        for _ in range(6):
            await c.recv()
        final = sr.check_recording(FIXTURE)["gen_last"]

        await c.send({"type": "set_content", "id": "x", "content": ["%3"]})
        snap = await c.recv()
        self.assertEqual((snap["type"], snap["id"], snap["gen"]), ("snapshot", "x", final))
        self.assertIn("content", snap["panes"]["%3"])
        self.assertNotIn("content", snap["panes"]["%1"])

        last_state = states_of(self.recording)[-1][1]
        await c.send({"type": "capture", "id": 4, "pane": "%1", "lines": 1})
        result = await c.recv()
        self.assertEqual((result["type"], result["id"], result["pane"]), ("result", 4, "%1"))
        self.assertEqual(result["content"],
                         last_state.panes["%1"]["content"].split("\n")[-2] + "\n")

        await c.send({"type": "capture", "id": 5, "pane": "%77", "lines": 3})
        err = await c.recv()
        self.assertEqual((err["type"], err["code"], err["id"]), ("error", "not_found", 5))

        await c.send({"type": "refresh", "id": 6})
        refresh = await c.recv()
        self.assertEqual((refresh["request"], refresh["gen"], refresh["id"]), ("refresh", final, 6))
        await c.send({"type": "set_pins", "pins": "all"})
        self.assertEqual((await c.recv())["request"], "set_pins")
        await c.send({"type": "cycle_compare_mode", "id": 9, "pane": "%1"})
        err = await c.recv()
        self.assertEqual((err["code"], err["id"], err["request"]),
                         ("unavailable", 9, "cycle_compare_mode"))

    async def test_capture_resolves_a_shadow_by_its_own_pane_id(self):
        await self.replay()
        c = await self.client()
        await c.hello()
        await c.send({"type": "subscribe"})
        for _ in range(6):
            await c.recv()
        shadow = states_of(self.recording)[-1][1].shadows["%1"]
        self.assertEqual(shadow["pane"]["pane_id"], "%12")
        await c.send({"type": "capture", "id": "s", "pane": "%12", "lines": 1})
        result = await c.recv()
        self.assertEqual((result["type"], result["id"], result["pane"]), ("result", "s", "%12"))
        self.assertEqual(result["content"], shadow["content"].split("\n")[-2] + "\n")
        await c.send({"type": "capture", "id": "p", "pane": "%1", "lines": 1})
        self.assertEqual((await c.recv())["pane"], "%1")  # the key still means the pane

    async def test_long_unknown_types_are_answered_and_the_connection_kept(self):
        await self.replay()
        c = await self.client()
        await c.hello()
        for length in (64, 65, 10000):
            with self.subTest(length=length):
                name = "t" * length
                await c.send_raw(json.dumps({"type": name, "id": length}).encode() + b"\n")
                err = await c.recv()
                self.assertEqual((err["type"], err["code"], err["id"]),
                                 ("error", "unknown_type", length))
                self.assertLessEqual(len(err["message"]), sp.MAX_TEXT_CHARS)
                if length <= 64:
                    self.assertEqual(err["request"], name)
                else:
                    self.assertNotIn("request", err)
        await c.send({"type": "refresh", "id": "still-here"})
        self.assertEqual((await c.recv())["id"], "still-here")

    async def test_errors_carry_the_readable_request_id(self):
        await self.replay()
        c = await self.client()
        await c.hello()
        await c.send_raw(
            sp.encode({"type": "refresh", "id": "other"}, direction=sp.CLIENT)
            + b'{"type":"capture","id":"pending","pane":"%1","lines":0}\n'
            + b'{"type":"teleport","id":17}\n'
            + b'{"type":"capture","id":true,"pane":"%1","lines":0}\n'
            + b'{"type":"capture","id":"x' + b"x" * 200 + b'","pane":"%1","lines":1}\n')
        replies = [await c.recv() for _ in range(5)]
        self.assertEqual((replies[0]["type"], replies[0]["id"]), ("result", "other"))
        self.assertEqual((replies[1]["code"], replies[1]["id"], replies[1]["request"]),
                         ("bad_message", "pending", "capture"))
        self.assertEqual((replies[2]["code"], replies[2]["id"]), ("unknown_type", 17))
        self.assertEqual(replies[3]["code"], "bad_message")
        self.assertNotIn("id", replies[3])  # an invalid id is never echoed
        self.assertEqual(replies[4]["code"], "bad_message")
        self.assertNotIn("id", replies[4])  # neither is an oversize one

    async def test_proto_mismatch_closes(self):
        await self.replay()
        c = await self.client()
        await c.send({"type": "hello", "proto": sp.PROTO + 1, "version": "v",
                      "client": {"kind": "t"}})
        err = await c.recv()
        self.assertEqual((err["code"], err["server_proto"]), ("proto_mismatch", sp.PROTO))
        self.assertIsNone(await c.recv())

    async def test_request_before_hello_closes(self):
        await self.replay()
        c = await self.client()
        await c.send({"type": "subscribe"})
        self.assertEqual((await c.recv())["type"], "error")
        self.assertIsNone(await c.recv())

    async def test_malformed_and_unknown_keep_the_connection(self):
        await self.replay()
        c = await self.client()
        await c.hello()
        await c.send_raw(b'{"type":"capture","pane":"%1","lines":0}\n')
        self.assertEqual((await c.recv())["code"], "bad_message")
        await c.send_raw(b"not json\n")
        self.assertEqual((await c.recv())["code"], "bad_message")
        await c.send_raw(b'{"type":"teleport"}\n')
        self.assertEqual((await c.recv())["code"], "unknown_type")
        await c.send({"type": "refresh", "id": 1})
        self.assertEqual((await c.recv())["type"], "result")


class ReplayLifecycleTests(SocketTestCase):
    async def test_shutdown_leaves_no_reader_tasks_behind(self):
        for _round in range(3):
            server = await self.replay()
            c = await self.client()
            await c.hello()
            await asyncio.sleep(0.05)  # the connection is now idle in its reader
            await server.close()
            self.servers.remove(server)
            await c.close()
            self.clients.remove(c)
            await asyncio.sleep(0)
            leftovers = [t for t in asyncio.all_tasks()
                         if t.get_name().startswith("replay-") and not t.done()]
            self.assertEqual(leftovers, [])

    async def test_bad_speeds_are_refused_at_start_up(self):
        for speed in (-1, float("nan"), float("inf"), "2", True):
            with self.subTest(speed=speed):
                with self.assertRaises(ValueError):
                    sr.ReplayServer(self.recording, self.sock, speed=speed)
        self.assertFalse(os.path.exists(self.sock))
        sr.ReplayServer(self.recording, self.sock, speed=0)  # unpaced stays valid

    def test_cli_refuses_bad_speeds(self):
        for speed in ("-1", "nan", "inf", "fast"):
            with self.subTest(speed=speed):
                proc = subprocess.run(
                    [sys.executable, str(CLI), "replay", str(FIXTURE), "--socket",
                     os.path.join(self.tmp, "never.sock"), "--speed", speed],
                    capture_output=True, text=True, timeout=60)
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertFalse(os.path.exists(os.path.join(self.tmp, "never.sock")))


class ReplayValidationTests(SocketTestCase):
    def gap_recording_bytes(self) -> bytes:
        lines = FIXTURE.read_bytes().splitlines(keepends=True)
        delta = json.loads(lines[3])
        delta["gen"] = 4  # jumps from gen 1 to gen 4
        lines[3] = json.dumps(delta, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        return b"".join(lines)

    async def test_an_invalid_recording_is_refused_before_serving(self):
        data = self.gap_recording_bytes()
        path = Path(self.tmp) / "gap.jsonl"
        path.write_bytes(data)
        parsed = sr.parse_recording(data)  # the shapes and order are fine…
        for source in (str(path), parsed):
            with self.subTest(source=type(source).__name__):
                with self.assertRaises(sr.RecordingError):
                    sr.ReplayServer(source, self.sock)  # …the stream is not
        self.assertFalse(os.path.exists(self.sock))

    async def test_a_playback_failure_is_surfaced_and_closes(self):
        server = await self.replay()
        # Corrupt the stream AFTER validation, as a defect would.
        # messages = [welcome, snapshot, first delta, …]: break the first delta.
        server.recording.messages[2] = dict(server.recording.messages[2], gen=9)
        c = await self.client()
        await c.hello()
        await c.send({"type": "subscribe", "content": "none"})
        self.assertEqual((await c.recv())["type"], "snapshot")
        err = await c.recv()
        self.assertEqual((err["type"], err["code"]), ("error", "internal"))
        self.assertTrue(await c.closed())


class MidPlaybackTests(SocketTestCase):
    """Playback held at an exact position by a gated pacer (``speed=0`` alone
    would finish playback before the interaction under test)."""

    async def test_repeated_subscribe_resyncs_without_rewinding(self):
        gate = Gate()
        await self.replay(pacer=gate)
        c = await self.client()
        await c.hello()
        await c.send({"type": "subscribe"})
        state = sp.StreamState()
        state.apply(await c.recv())
        gate.release(2)
        for want_gen in (2, 3):
            delta = await c.recv()
            self.assertEqual(delta["gen"], want_gen)
            state.apply(delta)
        await c.nothing_within()

        await c.send({"type": "subscribe", "id": 7})
        resync = await c.recv()
        self.assertEqual((resync["type"], resync["id"], resync["gen"]), ("snapshot", 7, 3))
        self.assertEqual(sp.frame_from_members(resync), state.frame())
        recorded_initial = self.recording.snapshot
        self.assertGreater(resync["gen"], recorded_initial["gen"])
        self.assertNotEqual(resync["panes"], recorded_initial["panes"])

        fresh = sp.StreamState()
        fresh.apply(resync)
        gate.release(1)
        nxt = await c.recv()
        self.assertEqual(nxt, self.recording.deltas[2])
        self.assertIsNotNone(fresh.apply(nxt))
        gate.release(10)
        rest = [await c.recv() for _ in range(2)]
        self.assertEqual([m["gen"] for m in rest], [5, 6])
        for msg in rest:
            fresh.apply(msg)
        await c.send({"type": "refresh", "id": "end"})
        tail = await c.recv()
        self.assertEqual((tail["type"], tail["id"]), ("result", "end"))  # no second playback
        await c.nothing_within()
        self.assertEqual(fresh.frame(), states_of(self.recording)[-1][1])

    async def test_set_content_mid_playback(self):
        gate = Gate()
        await self.replay(pacer=gate)
        c = await self.client()
        await c.hello()
        await c.send({"type": "subscribe", "content": ["%2"]})
        snap = await c.recv()
        self.assertNotIn("content", snap["panes"]["%1"])
        gate.release(2)
        for _ in range(2):
            delta = await c.recv()
            self.assertNotIn("content", delta["panes"]["%1"])
        await c.send({"type": "set_content", "id": "c", "content": ["%1"]})
        reply = await c.recv()
        self.assertEqual((reply["type"], reply["id"], reply["gen"]), ("snapshot", "c", 3))
        full_at_3 = states_of(self.recording)[2][1]
        self.assertEqual(reply["panes"]["%1"]["content"], full_at_3.panes["%1"]["content"])
        self.assertNotIn("content", reply["panes"]["%2"])
        gate.release(10)
        later = [await c.recv() for _ in range(3)]
        self.assertEqual([m["gen"] for m in later], [4, 5, 6])
        for msg in later:
            self.assertIn("content", msg["panes"]["%1"])
            for group in ("panes", "shadows"):
                for key, rec in msg.get(group, {}).items():
                    if key != "%1":
                        self.assertNotIn("content", rec)

    async def test_reply_is_ordered_between_deltas(self):
        gate = Gate()
        await self.replay(pacer=gate)
        c = await self.client()
        await c.hello()
        await c.send({"type": "subscribe"})
        await c.recv()
        gate.release(1)
        self.assertEqual((await c.recv())["gen"], 2)
        await c.send({"type": "refresh", "id": "r"})
        result = await c.recv()
        self.assertEqual((result["type"], result["id"], result["gen"]), ("result", "r", 2))
        gate.release(10)
        self.assertEqual([(await c.recv())["gen"] for _ in range(4)], [3, 4, 5, 6])


class FramingTests(SocketTestCase):
    OVER = sp.MAX_CLIENT_LINE_BYTES + 1

    @staticmethod
    def padded(size: int) -> bytes:
        head, tail = b'{"type":"refresh","id":"big","pad":"', b'"}'
        return head + b"x" * (size - len(head) - len(tail)) + tail

    async def _expect_too_long_then_eof(self, c):
        err = await c.recv()
        self.assertEqual((err["type"], err["code"]), ("error", "too_long"))
        self.assertTrue(await c.closed(), "the connection must close; nothing else answered")

    async def test_oversized_in_one_write(self):
        await self.replay()
        c = await self.client()
        await c.hello()
        valid = sp.encode({"type": "refresh", "id": "after"}, direction=sp.CLIENT)
        await c.send_raw(self.padded(self.OVER) + b"\n" + valid)
        await self._expect_too_long_then_eof(c)

    async def test_oversized_in_fragments(self):
        await self.replay()
        c = await self.client()
        await c.hello()
        line = self.padded(self.OVER)
        await c.send_raw(line[:40000])
        await asyncio.sleep(0.05)
        valid = sp.encode({"type": "refresh", "id": "after"}, direction=sp.CLIENT)
        await c.send_raw(line[40000:] + b"\n" + valid)
        await self._expect_too_long_then_eof(c)

    async def test_oversized_without_newline_is_refused_before_it_ends(self):
        await self.replay()
        c = await self.client()
        await c.hello()
        await c.send_raw(b'{"type":"refresh","pad":"' + b"x" * self.OVER)
        err = await c.recv()  # answered without waiting for the newline
        self.assertEqual(err["code"], "too_long")
        with contextlib.suppress(ConnectionError):
            await c.send_raw(b'","id":"tail"}\n'
                             + sp.encode({"type": "refresh", "id": "after"}, direction=sp.CLIENT))
        self.assertTrue(await c.closed(), "the tail and the later request must never be answered")

    async def test_unterminated_tail_at_eof_is_never_parsed(self):
        await self.replay()
        c = await self.client()
        await c.hello()
        await c.send_raw(sp.encode({"type": "refresh", "id": 1}, direction=sp.CLIENT)[:-1])
        c.writer.write_eof()
        self.assertIsNone(await c.recv())

    async def test_exactly_at_the_limit_is_accepted(self):
        await self.replay()
        c = await self.client()
        await c.hello()
        await c.send_raw(self.padded(sp.MAX_CLIENT_LINE_BYTES) + b"\n")
        result = await c.recv()
        self.assertEqual((result["type"], result["id"]), ("result", "big"))


class ReadLineTests(unittest.IsolatedAsyncioTestCase):
    async def _reader(self, limit=16):
        return asyncio.StreamReader(limit=limit)

    async def test_at_the_limit(self):
        r = await self._reader()
        r.feed_data(b"x" * 16 + b"\n")
        self.assertEqual(await sp.read_line(r), b"x" * 16 + b"\n")

    async def test_over_the_limit(self):
        r = await self._reader()
        r.feed_data(b"x" * 17 + b"\nnext\n")
        with self.assertRaises(sp.FramingError):
            await sp.read_line(r)

    async def test_fragmented_over_the_limit(self):
        r = await self._reader()
        r.feed_data(b"x" * 10)
        task = asyncio.ensure_future(sp.read_line(r))
        await asyncio.sleep(0)
        r.feed_data(b"x" * 10 + b"\n")
        with self.assertRaises(sp.FramingError):
            await task

    async def test_unterminated_tail_and_empty_eof(self):
        r = await self._reader()
        r.feed_data(b"abc")
        r.feed_eof()
        self.assertIsNone(await sp.read_line(r))
        empty = await self._reader()
        empty.feed_eof()
        self.assertIsNone(await sp.read_line(empty))


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------

class StubServer:
    """A scripted status server: answers the handshake, then sends what the
    test tells it to."""

    def __init__(self, path):
        self.path = path
        self.received = []
        self.welcomed = asyncio.Event()
        self.release_snapshot = asyncio.Event()
        self.snapshot = None
        self.deltas = []
        self.raw_after = []
        self.welcome_proto = sp.PROTO
        self.welcome_version = sr.framework_version()
        self.close_after_welcome = False
        self.hold_after_snapshot = True
        self._server = None

    async def start(self):
        self._server = await asyncio.start_unix_server(self._handle, path=self.path)

    async def _handle(self, reader, writer):
        try:
            for _ in range(2):
                line = await sp.read_line(reader)
                self.received.append(sp.decode(line, direction=sp.CLIENT))
            writer.write(sp.encode({"type": "welcome", "ts": 1.0,
                                    "proto": self.welcome_proto,
                                    "version": self.welcome_version,
                                    "server": {"impl": "stub"}}, direction=sp.SERVER))
            await writer.drain()
            self.welcomed.set()
            if self.close_after_welcome:
                return
            await self.release_snapshot.wait()
            writer.write(sp.encode(self.snapshot, direction=sp.SERVER))
            for delta in self.deltas:
                writer.write(sp.encode(delta, direction=sp.SERVER))
            for raw in self.raw_after:
                writer.write(raw)
            await writer.drain()
            if self.hold_after_snapshot:
                await asyncio.Event().wait()
        finally:
            writer.close()

    async def close(self):
        if self._server is not None:
            self._server.close()
            self._server = None
        with contextlib.suppress(FileNotFoundError):
            os.unlink(self.path)


class RecorderTests(SocketTestCase):
    def out_files(self):
        out = Path(self.tmp) / "rec.jsonl"
        return out, out.with_name(out.name + ".partial")

    async def stub(self, *, snapshot=None, deltas=(), **kw):
        stub = StubServer(self.sock)
        stub.snapshot = snapshot or self.recording.snapshot
        stub.deltas = list(deltas)
        for key, value in kw.items():
            setattr(stub, key, value)
        await stub.start()
        self.servers.append(stub)
        return stub

    async def test_round_trip_against_the_replayer(self):
        await self.replay(exit_at_end=True)
        out, partial = self.out_files()
        result = await sr.record_connect(self.sock, out)
        self.assertTrue(result.published, result.reason)
        self.assertEqual(result.deltas, 5)
        self.assertFalse(partial.exists())
        recorded = sr.read_recording(out)
        self.assertEqual(recorded.lines[1:], self.recording.lines[1:])
        self.assertEqual(recorded.header["version"], sr.framework_version())
        self.assertTrue(recorded.header["source"].startswith("connect:"))
        sr.check_recording(out)

    async def test_max_deltas(self):
        await self.replay()
        out, _partial = self.out_files()
        result = await sr.record_connect(self.sock, out, max_deltas=2)
        self.assertTrue(result.published)
        self.assertEqual(len(sr.read_recording(out).deltas), 2)

    def test_no_content_option_anywhere(self):
        self.assertNotIn("content", inspect.signature(sr.record_connect).parameters)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(open(os.devnull, "w")):
            sr.build_parser().parse_args(["record", "--connect", "s", "--out", "o",
                                          "--content", "all"])

    async def test_recorder_subscribes_for_full_content(self):
        stub = await self.stub()
        stub.release_snapshot.set()
        out, _partial = self.out_files()
        result = await sr.record_connect(self.sock, out, max_deltas=0)
        self.assertTrue(result.published, result.reason)
        hello, subscribe = stub.received
        self.assertEqual(hello["type"], "hello")
        self.assertEqual(subscribe, {"type": "subscribe", "content": "all",
                                     "include_shadows": True})
        sr.check_recording(out)

    async def test_contentless_snapshot_publishes_nothing(self):
        bare = sp.filter_message(self.recording.snapshot, content="none")
        stub = await self.stub(snapshot=bare)
        stub.release_snapshot.set()
        out, partial = self.out_files()
        result = await sr.record_connect(self.sock, out, duration=STEP)
        self.assertFalse(result.published)
        self.assertIn("no usable recording captured", result.reason)
        self.assertFalse(out.exists())
        self.assertFalse(partial.exists())

    async def test_stops_before_the_snapshot_publish_nothing(self):
        out, partial = self.out_files()
        # (a) duration elapses while the snapshot is held
        await self.stub()
        result = await sr.record_connect(self.sock, out, duration=0.3)
        self.assertFalse(result.published)
        self.assertIn("no usable recording captured", result.reason)
        self.assertIn("before the snapshot", result.reason)
        self.assertFalse(out.exists() or partial.exists())
        await self.servers.pop().close()

        # (b) cancellation while the snapshot is held: still propagates
        stub = await self.stub()
        task = asyncio.ensure_future(sr.record_connect(self.sock, out))
        await asyncio.wait_for(stub.welcomed.wait(), STEP)
        await asyncio.sleep(0.1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertFalse(out.exists() or partial.exists())
        await self.servers.pop().close()

        # (c) the server closes after the welcome
        await self.stub(close_after_welcome=True)
        result = await sr.record_connect(self.sock, out, duration=STEP)
        self.assertFalse(result.published)
        self.assertIn("before the snapshot", result.reason)
        self.assertFalse(out.exists() or partial.exists())

    async def test_stops_after_the_snapshot_publish(self):
        out, partial = self.out_files()
        for stop in ("duration", "max_deltas", "cancel"):
            with self.subTest(stop=stop):
                stub = await self.stub(deltas=self.recording.deltas[:2])
                stub.release_snapshot.set()
                if stop == "duration":
                    result = await sr.record_connect(self.sock, out, duration=0.3)
                    self.assertTrue(result.published, result.reason)
                elif stop == "max_deltas":
                    result = await sr.record_connect(self.sock, out, max_deltas=0)
                    self.assertTrue(result.published, result.reason)
                    self.assertEqual(len(sr.read_recording(out).deltas), 0)
                else:
                    task = asyncio.ensure_future(sr.record_connect(self.sock, out))
                    await asyncio.wait_for(stub.welcomed.wait(), STEP)
                    await asyncio.sleep(0.2)
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                self.assertTrue(out.exists())
                self.assertFalse(partial.exists())
                sr.check_recording(out)
                out.unlink()
                await self.servers.pop().close()

    async def test_handshake_gates_publish_nothing(self):
        out, partial = self.out_files()
        for name, attrs in {
            "proto": {"welcome_proto": 99},
            "version": {"welcome_version": "0.0.1-other"},
        }.items():
            with self.subTest(gate=name):
                stub = await self.stub(**attrs)
                stub.release_snapshot.set()
                result = await sr.record_connect(self.sock, out, max_deltas=0)
                self.assertFalse(result.published)
                self.assertIn(f"{name} mismatch", result.reason)
                self.assertFalse(out.exists() or partial.exists())
                await self.servers.pop().close()

    async def test_malformed_input_after_the_snapshot_publishes_nothing(self):
        out, partial = self.out_files()
        huge_ts = (b'{"gen":2,"ts":' + b"9" * 400 + b',"type":"delta"}\n')
        cases = {
            "overflowing number": huge_ts,
            "not json": b"{oops\n",
            "gap": sp.encode({"type": "delta", "ts": 9.0, "gen": 9}, direction=sp.SERVER),
        }
        for name, raw in cases.items():
            with self.subTest(case=name):
                stub = await self.stub(deltas=self.recording.deltas[:1])
                stub.raw_after = [raw]
                stub.release_snapshot.set()
                result = await sr.record_connect(self.sock, out, duration=STEP)
                self.assertFalse(result.published, result.reason)
                self.assertIn("no usable recording captured", result.reason)
                self.assertFalse(out.exists() or partial.exists())
                await self.servers.pop().close()

    async def test_an_unexpected_error_after_the_snapshot_publishes_nothing(self):
        out, partial = self.out_files()
        stub = await self.stub(deltas=self.recording.deltas[:2])
        stub.release_snapshot.set()
        real_apply = sp.StreamState.apply

        def flaky_apply(state, msg):
            if msg["type"] == "delta" and msg["gen"] == 3:
                raise RuntimeError("simulated defect")
            return real_apply(state, msg)

        sp.StreamState.apply = flaky_apply
        try:
            result = await sr.record_connect(self.sock, out, duration=STEP)
        finally:
            sp.StreamState.apply = real_apply
        self.assertFalse(result.published)
        self.assertIn("internal error", result.reason)
        self.assertFalse(out.exists() or partial.exists())

    def test_cli_record_exits_nonzero_when_nothing_published(self):
        out = Path(self.tmp) / "never.jsonl"
        proc = subprocess.run(
            [sys.executable, str(CLI), "record", "--connect",
             os.path.join(self.tmp, "absent.sock"), "--out", str(out), "--duration", "1"],
            capture_output=True, text=True, timeout=60)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("no usable recording captured", proc.stderr)
        self.assertFalse(out.exists())


# ---------------------------------------------------------------------------
# Pacing and CLI
# ---------------------------------------------------------------------------

class PacingTests(unittest.TestCase):
    def test_replay_delays(self):
        rec = sr.read_recording(FIXTURE)
        self.assertEqual(sr.replay_delays(rec, 1.0), [3.0] * 5)
        self.assertEqual(sr.replay_delays(rec, 2.0), [1.5] * 5)
        self.assertEqual(sr.replay_delays(rec, 0), [0.0] * 5)
        for bad in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                sr.replay_delays(rec, bad)

    def test_backwards_ts_never_waits_negative(self):
        rec = sr.read_recording(FIXTURE)
        rec.messages[3] = dict(rec.messages[3], ts=rec.snapshot["ts"] - 100)
        self.assertEqual(sr.replay_delays(rec, 1.0)[1], 0.0)


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *args], capture_output=True,
                              text=True, timeout=60)

    def test_check_the_fixture(self):
        proc = self.run_cli("check", str(FIXTURE))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["deltas"], 5)

    def test_check_a_corrupted_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            lines = FIXTURE.read_bytes().splitlines(keepends=True)
            for name, data in {
                "dropped_delta": b"".join(lines[:4] + lines[5:]),
                "truncated": b"".join(lines)[:-40],
                "garbage_line": b"".join(lines[:3] + [b"{oops\n"] + lines[3:]),
            }.items():
                with self.subTest(case=name):
                    path = Path(tmp) / f"{name}.jsonl"
                    path.write_bytes(data)
                    proc = self.run_cli("check", str(path))
                    self.assertEqual(proc.returncode, 1)
                    self.assertIn("INVALID", proc.stderr)


if __name__ == "__main__":
    unittest.main()
