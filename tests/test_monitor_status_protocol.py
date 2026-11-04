"""Codec tests for the monitor status protocol (t2034_3).

Covers ``.aitask-scripts/monitor/status_protocol.py``: per-type round trips,
record conversion, unknown members and types, the malformed-input rules, the
direction rules, determinism, the encoder → client-state stream (a seeded
random walk, with and without content selection), the generation rules, and a
pin of the spec's member tables (``aidocs/framework/monitor_status_protocol.md``)
against the codec's schema tables.
"""
from __future__ import annotations

import json
import random
import re
import sys
import time
import unittest
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / ".aitask-scripts", REPO_ROOT / ".aitask-scripts" / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from monitor import status_protocol as sp  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    PaneCategory,
    PaneSnapshot,
    TmuxMonitor,
    TmuxPaneInfo,
    _frozen_snapshot,
    _parked_snapshot,
)

SPEC = REPO_ROOT / "aidocs" / "framework" / "monitor_status_protocol.md"
TS = 1767225600.0


def make_pane(pane_id="%1", session="s1", window="agent-pick-1", *, category=PaneCategory.AGENT,
              shadow_target="", **kw) -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index=kw.pop("window_index", "1"), window_name=window,
        pane_index=kw.pop("pane_index", "0"), pane_id=pane_id,
        pane_pid=kw.pop("pane_pid", 4000 + int(pane_id[1:])),
        current_command=kw.pop("current_command", "claude"),
        width=kw.pop("width", 120), height=kw.pop("height", 40), category=category,
        session_name=session, shadow_target=shadow_target, **kw)


def make_record(pane_id="%1", *, content="hello\n", idle=0.0, **kw) -> dict:
    pane = make_pane(pane_id, **kw.pop("pane_kw", {}))
    snap = PaneSnapshot(pane=pane, content=content, timestamp=0.0, idle_seconds=idle,
                        is_idle=idle > 5, **kw)
    return sp.pane_record(snap, last_change=TS - idle)


def roundtrip(msg, direction):
    line = sp.encode(msg, direction=direction)
    out = sp.decode(line, direction=direction)
    return line, out


# ---------------------------------------------------------------------------
# Sample messages: one per type
# ---------------------------------------------------------------------------

def sample_messages() -> dict:
    rec = make_record("%1", awaiting_input=True, awaiting_input_kind="claude_plan_approval",
                      agent_key="claude", scoped=True)
    shadow = make_record("%9", pane_kw={"shadow_target": "%1"})
    discovery = sp.discovery_member(["s1"], [("s1", "agent-pick-1")],
                                    {("s1", "agent-pick-1"): [("%1", 4001, False), ("%9", 4009, False)]})
    sessions = sp.sessions_member({"s1": "/p/one"})
    return {
        "hello": (sp.CLIENT, {"type": "hello", "proto": 1, "version": "0.40.1",
                              "client": {"kind": "monitor", "pane": "%5", "pid": 77}}),
        "subscribe": (sp.CLIENT, {"type": "subscribe", "id": 1, "content": ["%3", "%1"],
                                  "include_shadows": False, "pins": [["s1", "w"]]}),
        "set_content": (sp.CLIENT, {"type": "set_content", "id": "a", "content": "none"}),
        "set_pins": (sp.CLIENT, {"type": "set_pins", "pins": "all"}),
        "refresh": (sp.CLIENT, {"type": "refresh", "id": 2, "panes": ["%1"], "shadows": ["%1"]}),
        "set_compare_mode": (sp.CLIENT, {"type": "set_compare_mode", "pane": "%1", "mode": None}),
        "cycle_compare_mode": (sp.CLIENT, {"type": "cycle_compare_mode", "id": 3, "pane": "%1"}),
        "capture": (sp.CLIENT, {"type": "capture", "pane": "%1", "lines": 50}),
        "welcome": (sp.SERVER, {"type": "welcome", "ts": TS, "proto": 1, "version": "0.40.1",
                                "server": {"impl": "python", "pid": 9},
                                "replay": {"recorded_version": "x", "source": "y"}}),
        "snapshot": (sp.SERVER, {"type": "snapshot", "ts": TS, "gen": 4, "id": 1,
                                 "panes": {"%1": rec}, "shadows": {"%1": shadow},
                                 "completed": ["%1"], "sessions": sessions,
                                 "parked": [["s1", "agent-pick-2"]], "discovery": discovery,
                                 "control_state": "connected"}),
        "delta": (sp.SERVER, {"type": "delta", "ts": TS + 3, "gen": 5,
                              "panes": {"%1": {"idle_seconds": 3.0}, "%2": make_record("%2")},
                              "removed": ["%4"], "shadows": {"%1": {"content": "x"}},
                              "shadows_removed": ["%7"], "completed": [], "sessions": sessions,
                              "parked": [], "discovery": discovery,
                              "control_state": "reconnecting"}),
        "result": (sp.SERVER, {"type": "result", "ts": TS, "id": 3, "request": "cycle_compare_mode",
                               "mode": "raw", "following_default": False}),
        "error": (sp.SERVER, {"type": "error", "ts": TS, "id": 1, "code": "version_mismatch",
                              "message": "wrong server", "request": "hello",
                              "server_proto": 1, "server_version": "0.39.0"}),
        "recording": (sp.RECORDING, {"type": "recording", "rev": 1, "proto": 1,
                                     "version": "synthetic", "source": "scenario:x",
                                     "created": TS, "note": "n"}),
    }


class RoundTripTests(unittest.TestCase):
    def test_samples_cover_every_message_type(self):
        self.assertEqual(set(sample_messages()), set(sp.MESSAGE_SCHEMAS))

    def test_every_type_round_trips_and_is_byte_stable(self):
        for name, (direction, msg) in sample_messages().items():
            with self.subTest(type=name):
                line, out = roundtrip(msg, direction)
                self.assertTrue(line.endswith(b"\n"))
                self.assertEqual(line.count(b"\n"), 1)
                self.assertEqual(out, sp.validate(msg, direction=direction))
                self.assertEqual(sp.encode(out, direction=direction), line)

    def test_results_per_request_round_trip(self):
        cases = {
            "set_pins": {},
            "refresh": {"gen": 7},
            "set_compare_mode": {"mode": "stripped", "following_default": True},
            "cycle_compare_mode": {"mode": "raw", "following_default": False},
            "capture": {"pane": "%2", "content": "a\x1b[0mb\n"},
        }
        self.assertEqual(set(cases), set(sp.RESULT_SCHEMAS))
        for request, extra in cases.items():
            with self.subTest(request=request):
                msg = {"type": "result", "ts": TS, "request": request, **extra}
                _line, out = roundtrip(msg, sp.SERVER)
                self.assertEqual(out, msg)

    def test_encoding_is_compact_sorted_and_escapes_control_chars(self):
        line = sp.encode({"type": "capture", "pane": "%1", "lines": 2}, direction=sp.CLIENT)
        self.assertEqual(line, b'{"lines":2,"pane":"%1","type":"capture"}\n')
        rec_line = sp.encode({"type": "result", "ts": TS, "request": "capture",
                              "pane": "%1", "content": "\x1b[1mx\ny"}, direction=sp.SERVER)
        self.assertNotIn(b"\x1b", rec_line)
        self.assertEqual(rec_line.count(b"\n"), 1)

    def test_selection_and_pins_normalize(self):
        out = sp.decode(json.dumps({"type": "subscribe", "content": ["%10", "%2", "%2"],
                                    "pins": [["b", "w"], ["a", "w"], ["a", "w"]]}),
                        direction=sp.CLIENT)
        self.assertEqual(out["content"], ["%2", "%10"])
        self.assertEqual(out["pins"], [["a", "w"], ["b", "w"]])


class RecordConversionTests(unittest.TestCase):
    def assertSnapshotsEqual(self, a: PaneSnapshot, b: PaneSnapshot):
        self.assertEqual(replace(a, timestamp=0.0), replace(b, timestamp=0.0))

    def test_every_field_round_trips(self):
        pane = make_pane("%3", "sess", "agent-qa-12_3", window_index="4", pane_index="2",
                         pane_pid=999, current_command="codex", width=211, height=63,
                         history_size=1234, frozen_record="", record_id="rec-1",
                         standin_ready="rec-1", pane_dead=True)
        snap = PaneSnapshot(pane=pane, content="\x1b[31mred\x1b[0m\n", timestamp=5.0,
                            idle_seconds=7.25, is_idle=True, awaiting_input=True,
                            awaiting_input_kind="codex_permission", agent_key="codex",
                            scoped=True)
        rec = sp.pane_record(snap, compare_mode="raw", compare_override=True,
                             last_change=TS - 7.25)
        _line, out = roundtrip({"type": "snapshot", "ts": TS, "gen": 1, "panes": {"%3": rec},
                                "shadows": {}, "completed": [], "sessions": {}, "parked": [],
                                "discovery": sp.empty_discovery(), "control_state": "x"},
                               sp.SERVER)
        back = sp.pane_snapshot(out["panes"]["%3"], timestamp=42.0)
        self.assertEqual(back.timestamp, 42.0)
        self.assertSnapshotsEqual(back, snap)
        self.assertEqual(out["panes"]["%3"]["compare_mode"], "raw")
        self.assertTrue(out["panes"]["%3"]["compare_override"])
        self.assertEqual(out["panes"]["%3"]["last_change"], round(TS - 7.25, 3))

    def test_history_size_none_and_placeholders(self):
        pane = make_pane("%4", history_size=None, frozen_record="rec-f")
        for snap in (_parked_snapshot(pane, 1.0), _frozen_snapshot(pane, 1.0)):
            with self.subTest(parked=snap.parked, frozen=snap.frozen):
                rec = sp.pane_record(snap)
                self.assertIsNone(rec["pane"]["history_size"])
                self.assertEqual(rec["content"], "")
                self.assertSnapshotsEqual(sp.pane_snapshot(rec), snap)

    def test_unselected_record_reads_as_empty_content(self):
        rec = sp.pane_record(PaneSnapshot(make_pane(), "secret", 0.0, 1.0, False),
                             include_content=False)
        self.assertNotIn("content", rec)
        self.assertEqual(sp.pane_snapshot(rec).content, "")

    def test_monitor_pane_record_reads_the_producer(self):
        monitor = TmuxMonitor(session="s1")
        snap = PaneSnapshot(make_pane("%1"), "c", 0.0, 10.0, True)
        plain = sp.monitor_pane_record(monitor, snap)
        self.assertEqual(plain["compare_mode"], sp.DEFAULT_COMPARE_MODE)
        self.assertFalse(plain["compare_override"])
        self.assertIsNone(plain["last_change"])
        monitor.set_compare_mode("%1", "raw")
        monitor._last_change_time["%1"] = time.monotonic() - 10.0
        rec = sp.monitor_pane_record(monitor, snap)
        self.assertEqual(rec["compare_mode"], "raw")
        self.assertTrue(rec["compare_override"])
        self.assertAlmostEqual(rec["last_change"], time.time() - 10.0, delta=1.0)


class UnknownAndOpenTests(unittest.TestCase):
    def test_unknown_members_dropped_at_every_level(self):
        rec = make_record("%1")
        rec["future"] = 1
        rec["pane"] = dict(rec["pane"], future_pane_field="x")
        msg = {"type": "snapshot", "ts": TS, "gen": 1, "panes": {"%1": rec}, "shadows": {},
               "completed": [], "sessions": {"s": {"project_root": "/r", "project_name": "r",
                                                   "extra": True}},
               "parked": [], "discovery": dict(sp.empty_discovery(), more=[1]),
               "control_state": "connected", "brand_new_top": {"a": 1}}
        out = sp.decode(json.dumps(msg), direction=sp.SERVER)
        self.assertNotIn("brand_new_top", out)
        self.assertNotIn("future", out["panes"]["%1"])
        self.assertNotIn("future_pane_field", out["panes"]["%1"]["pane"])
        self.assertNotIn("extra", out["sessions"]["s"])
        self.assertNotIn("more", out["discovery"])
        result = sp.decode(json.dumps({"type": "result", "ts": TS, "request": "refresh",
                                       "gen": 2, "later": 1}), direction=sp.SERVER)
        self.assertEqual(result, {"type": "result", "ts": TS, "request": "refresh", "gen": 2})
        hello = sp.decode(json.dumps({"type": "hello", "proto": 1, "version": "v",
                                      "client": {"kind": "k", "colour": "blue"}}),
                          direction=sp.CLIENT)
        self.assertEqual(hello["client"], {"kind": "k"})

    def test_result_for_unknown_request_keeps_common_members(self):
        out = sp.decode(json.dumps({"type": "result", "ts": TS, "request": "future_verb",
                                    "anything": [1]}), direction=sp.SERVER)
        self.assertEqual(out, {"type": "result", "ts": TS, "request": "future_verb"})

    def test_unknown_type_raises_unknown_message_type(self):
        for direction in (sp.CLIENT, sp.SERVER, sp.RECORDING):
            with self.subTest(direction=direction):
                with self.assertRaises(sp.UnknownMessageType) as cm:
                    sp.decode('{"type":"teleport"}', direction=direction)
                self.assertEqual(cm.exception.code, "unknown_type")
                self.assertEqual(cm.exception.type_name, "teleport")

    def test_open_strings_accept_new_values(self):
        rec = make_record("%1", awaiting_input=True, awaiting_input_kind="brand_new_kind")
        out = sp.decode(json.dumps({"type": "delta", "ts": TS, "gen": 1, "panes": {"%1": rec},
                                    "control_state": "brand_new_state"}), direction=sp.SERVER)
        self.assertEqual(out["panes"]["%1"]["awaiting_input_kind"], "brand_new_kind")
        self.assertEqual(out["control_state"], "brand_new_state")
        err = sp.decode(json.dumps({"type": "error", "ts": TS, "code": "future_code",
                                    "message": ""}), direction=sp.SERVER)
        self.assertEqual(err["code"], "future_code")


class MalformedTests(unittest.TestCase):
    def _assert_rejected(self, line, direction=sp.CLIENT, code="bad_message"):
        with self.assertRaises(sp.ProtocolError) as cm:
            sp.decode(line, direction=direction)
        self.assertEqual(cm.exception.code, code, str(cm.exception))
        return cm.exception

    def test_rejection_table(self):
        rec_bad_key = make_record("%2")
        shadow_bad_key = make_record("%9", pane_kw={"shadow_target": "%3"})
        snap = {"type": "snapshot", "ts": TS, "gen": 1, "panes": {}, "shadows": {},
                "completed": [], "sessions": {}, "parked": [],
                "discovery": sp.empty_discovery(), "control_state": "c"}
        cases = [
            ("not json", "{", sp.CLIENT),
            ("not an object", "[1, 2]", sp.CLIENT),
            ("json scalar", "3", sp.CLIENT),
            ("empty line", "", sp.CLIENT),
            ("blank line", "  \n", sp.CLIENT),
            ("invalid utf-8", b'{"type":"capture","pane":"%1","lines":1,"x":"\xff"}\n', sp.CLIENT),
            ("missing type", '{"pane":"%1"}', sp.CLIENT),
            ("type not a string", '{"type":3}', sp.CLIENT),
            ("missing required member", '{"type":"hello","proto":1,"client":{"kind":"k"}}', sp.CLIENT),
            ("missing nested required", '{"type":"hello","proto":1,"version":"v","client":{}}', sp.CLIENT),
            ("bool is not an int", '{"type":"hello","proto":true,"version":"v","client":{"kind":"k"}}', sp.CLIENT),
            ("float is not an int", '{"type":"hello","proto":1.0,"version":"v","client":{"kind":"k"}}', sp.CLIENT),
            ("exponent is not an int", '{"type":"capture","pane":"%1","lines":1e2}', sp.CLIENT),
            ("string is not a bool", '{"type":"subscribe","include_shadows":"yes"}', sp.CLIENT),
            ("negative int", json.dumps(dict(snap, gen=-1)), sp.SERVER),
            ("int over 2^53", json.dumps(dict(snap, gen=2 ** 53)), sp.SERVER),
            ("lines below range", '{"type":"capture","pane":"%1","lines":0}', sp.CLIENT),
            ("lines above range", '{"type":"capture","pane":"%1","lines":10001}', sp.CLIENT),
            ("negative seconds", json.dumps(dict(snap, ts=-1)), sp.SERVER),
            ("bad pane id", '{"type":"capture","pane":"3","lines":1}', sp.CLIENT),
            ("bad pane id letters", '{"type":"capture","pane":"%x","lines":1}', sp.CLIENT),
            ("pane id with trailing newline", '{"type":"capture","pane":"%1\\n","lines":1}', sp.CLIENT),
            ("pane id with leading newline", '{"type":"capture","pane":"\\n%1","lines":1}', sp.CLIENT),
            ("pane id with non-ASCII digit", '{"type":"capture","pane":"%\\u0661","lines":1}', sp.CLIENT),
            ("selection id with trailing newline", '{"type":"set_content","content":["%1\\n"]}', sp.CLIENT),
            ("shadow_target with trailing newline", json.dumps(dict(snap, shadows={"%1": dict(
                make_record("%9", pane_kw={"shadow_target": "%1"}),
                pane=dict(make_record("%9", pane_kw={"shadow_target": "%1"})["pane"],
                          shadow_target="%1\n"))})), sp.SERVER),
            ("map key with trailing newline", json.dumps(dict(snap, panes={"%1\n": make_record("%1")})), sp.SERVER),
            ("bad pane id in selection", '{"type":"set_content","content":["%1","x"]}', sp.CLIENT),
            ("bad selection string", '{"type":"set_content","content":"some"}', sp.CLIENT),
            ("bad pins string", '{"type":"set_pins","pins":"everything"}', sp.CLIENT),
            ("pin not a pair", '{"type":"set_pins","pins":[["s"]]}', sp.CLIENT),
            ("bad compare mode", '{"type":"set_compare_mode","pane":"%1","mode":"fuzzy"}', sp.CLIENT),
            ("bad category", json.dumps(dict(snap, panes={"%1": dict(
                make_record("%1"), pane=dict(make_record("%1")["pane"], category="robot"))})), sp.SERVER),
            ("NaN", '{"type":"capture","pane":"%1","lines":NaN}', sp.CLIENT),
            ("Infinity", json.dumps(dict(snap)).replace(f'"ts": {TS}', '"ts": Infinity'), sp.SERVER),
            ("overflowing number", '{"type":"capture","pane":"%1","lines":1e999}', sp.CLIENT),
            ("duplicate top-level key", '{"type":"capture","pane":"%1","pane":"%2","lines":1}', sp.CLIENT),
            ("duplicate nested key", '{"type":"hello","proto":1,"version":"v","client":{"kind":"a","kind":"b"}}', sp.CLIENT),
            ("oversize list", json.dumps({"type": "refresh", "panes": ["%1"] * (sp.MAX_ITEMS + 1)}), sp.CLIENT),
            ("oversize id", json.dumps({"type": "refresh", "id": "x" * (sp.MAX_ID_CHARS + 1)}), sp.CLIENT),
            ("pane key mismatch", json.dumps(dict(snap, panes={"%1": rec_bad_key})), sp.SERVER),
            ("shadow key mismatch", json.dumps(dict(snap, shadows={"%1": shadow_bad_key})), sp.SERVER),
            ("patch pane key mismatch", json.dumps({"type": "delta", "ts": TS, "gen": 1,
                                                    "panes": {"%1": {"pane": rec_bad_key["pane"]}}}), sp.SERVER),
            ("deep nesting", "[" * 200000 + "]" * 200000, sp.SERVER),
        ]
        for desc, line, direction in cases:
            with self.subTest(case=desc):
                self._assert_rejected(line, direction)

    def test_too_long_is_a_framing_error(self):
        line = json.dumps({"type": "refresh", "pad": "x" * sp.MAX_CLIENT_LINE_BYTES})
        exc = self._assert_rejected(line, sp.CLIENT, code="too_long")
        self.assertIsInstance(exc, sp.FramingError)
        # The same line is fine server→client (64 MiB limit).
        sp.decode(json.dumps({"type": "result", "ts": TS, "request": "x",
                              "pad": "x" * sp.MAX_CLIENT_LINE_BYTES}), direction=sp.SERVER)

    def test_exactly_at_the_limit_is_accepted(self):
        head = '{"type":"refresh","pad":"'
        tail = '"}'
        line = head + "x" * (sp.MAX_CLIENT_LINE_BYTES - len(head) - len(tail)) + tail
        self.assertEqual(len(line.encode()), sp.MAX_CLIENT_LINE_BYTES)
        self.assertEqual(sp.decode(line + "\n", direction=sp.CLIENT), {"type": "refresh"})
        with self.assertRaises(sp.FramingError):
            sp.decode(line[:-2] + 'x"}', direction=sp.CLIENT)

    def test_encode_validates_and_rejects(self):
        with self.assertRaises(sp.ProtocolError):
            sp.encode({"type": "capture", "pane": "%1", "lines": 0}, direction=sp.CLIENT)
        pins = [[f"session-{i}-" + "x" * 100, "w"] for i in range(1000)]
        with self.assertRaises(sp.FramingError):
            sp.encode({"type": "set_pins", "pins": pins}, direction=sp.CLIENT)
        with self.assertRaises(sp.UnknownMessageType):
            sp.encode({"type": "teleport"}, direction=sp.CLIENT)


class CorrelationAndBoundsTests(unittest.TestCase):
    def test_errors_carry_the_readable_id_and_type(self):
        with self.assertRaises(sp.ProtocolError) as cm:
            sp.decode('{"type":"capture","id":"pending","pane":"%1","lines":0}',
                      direction=sp.CLIENT)
        self.assertEqual((cm.exception.request_id, cm.exception.request_type),
                         ("pending", "capture"))
        with self.assertRaises(sp.UnknownMessageType) as cm:
            sp.decode('{"type":"teleport","id":4}', direction=sp.CLIENT)
        self.assertEqual((cm.exception.request_id, cm.exception.request_type), (4, "teleport"))
        for bad_id in ("true", "-1", '"' + "x" * 200 + '"', "1.5"):
            with self.subTest(id=bad_id):
                with self.assertRaises(sp.ProtocolError) as cm:
                    sp.decode('{"type":"capture","id":%s,"pane":"%%1","lines":0}' % bad_id,
                              direction=sp.CLIENT)
                self.assertIsNone(cm.exception.request_id)
        with self.assertRaises(sp.UnknownMessageType) as cm:
            sp.decode(json.dumps({"type": "t" * 65}), direction=sp.CLIENT)
        self.assertIsNone(cm.exception.request_type)
        self.assertLess(len(str(cm.exception)), 200)

    def test_huge_numbers_are_protocol_errors(self):
        digits = "9" * 400
        lines = [
            '{"type":"delta","gen":2,"ts":%s}' % digits,
            '{"type":"delta","gen":%s,"ts":1}' % digits,
            '{"type":"delta","gen":2,"ts":-%s}' % digits,
            '{"type":"delta","gen":2,"ts":1e400}',
        ]
        for line in lines:
            with self.subTest(line=line[:40]):
                with self.assertRaises(sp.ProtocolError):
                    sp.decode(line, direction=sp.SERVER)

    def test_validate_leaks_no_other_exception(self):
        rng = random.Random(11)
        base = sample_messages()
        for _ in range(300):
            name = rng.choice(sorted(base))
            direction, msg = base[name]
            msg = dict(msg)
            key = rng.choice(sorted(msg))
            msg[key] = rng.choice([10 ** 400, -(10 ** 400), float("inf"), [], {}, "", None,
                                   True, "x" * 70000, [[["deep"]]], {"%1": 10 ** 400}])
            try:
                sp.validate(msg, direction=direction)
            except sp.ProtocolError:
                pass


class DirectionTests(unittest.TestCase):
    def test_client_cannot_send_server_types(self):
        _d, snap = sample_messages()["snapshot"]
        with self.assertRaises(sp.ProtocolError) as cm:
            sp.decode(json.dumps(snap), direction=sp.CLIENT)
        self.assertNotIsInstance(cm.exception, sp.UnknownMessageType)

    def test_server_cannot_send_client_types(self):
        with self.assertRaises(sp.ProtocolError):
            sp.decode('{"type":"capture","pane":"%1","lines":1}', direction=sp.SERVER)

    def test_recording_header_only_in_files(self):
        _d, header = sample_messages()["recording"]
        sp.decode(json.dumps(header), direction=sp.RECORDING)
        for direction in (sp.CLIENT, sp.SERVER):
            with self.subTest(direction=direction):
                with self.assertRaises(sp.ProtocolError) as cm:
                    sp.decode(json.dumps(header), direction=direction)
                self.assertNotIsInstance(cm.exception, sp.UnknownMessageType)

    def test_recording_direction_has_no_requests_or_replies(self):
        for name in ("result", "error"):
            _d, msg = sample_messages()[name]
            with self.subTest(type=name):
                with self.assertRaises(sp.ProtocolError):
                    sp.decode(json.dumps(msg), direction=sp.RECORDING)


class SurrogateTests(unittest.TestCase):
    def test_lone_surrogates_become_replacement_characters(self):
        msg = {"type": "result", "ts": TS, "request": "capture", "pane": "%1",
               "content": "a\ud800b"}
        line = sp.encode(msg, direction=sp.SERVER)
        line.decode("utf-8")  # valid UTF-8
        self.assertEqual(sp.decode(line, direction=sp.SERVER)["content"], "a�b")


# ---------------------------------------------------------------------------
# Stream: encoder → client state
# ---------------------------------------------------------------------------

def strip_unselected(frame: sp.StreamFrame, content) -> sp.StreamFrame:
    def proj(entries):
        out = {}
        for key, rec in entries.items():
            out[key] = rec if sp._selected(key, content) else {
                k: v for k, v in rec.items() if k != "content"}
        return out
    return replace(frame, panes=proj(frame.panes), shadows=proj(frame.shadows))


def normalized(frame: sp.StreamFrame) -> sp.StreamFrame:
    return sp.frame_from_members(sp._frame_members(frame))


class RandomWalk:
    """Seeded random frames: panes and shadows come and go, members, content
    and every top-level member change."""

    POOL = [f"%{n}" for n in range(1, 13)]

    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.panes: dict = {}
        self.shadows: dict = {}
        self.tick = 0

    def _new_record(self, pane_id, *, shadow_of=None):
        r = self.rng
        session = r.choice(["s1", "s2", "s3"])
        pane_kw = {"history_size": r.choice([None, r.randint(0, 900)]),
                   "width": r.randint(40, 250)}
        if shadow_of:
            pane_kw["shadow_target"] = shadow_of
        pane = make_pane(pane_id, session, f"agent-pick-{pane_id[1:]}",
                         category=r.choice(list(PaneCategory)), **pane_kw)
        snap = PaneSnapshot(pane=pane, content=f"start {pane_id}\x1b[0m\n", timestamp=0.0,
                            idle_seconds=float(r.randint(0, 40)), is_idle=r.random() < 0.5,
                            awaiting_input=r.random() < 0.3,
                            awaiting_input_kind=r.choice(["", "claude_plan_approval", "x_new"]),
                            agent_key=r.choice(["", "claude", "codex"]), scoped=r.random() < 0.5,
                            parked=r.random() < 0.1)
        return sp.pane_record(snap, compare_mode=r.choice(["stripped", "raw"]),
                              compare_override=r.random() < 0.2,
                              last_change=r.choice([None, TS + r.randint(0, 999)]))

    def _mutate(self, rec):
        r = self.rng
        rec = dict(rec)
        choice = r.randint(0, 5)
        if choice == 0:
            rec["content"] = rec.get("content", "") + f"line {self.tick}\n"
        elif choice == 1:
            rec["idle_seconds"] = rec["idle_seconds"] + 3.0
            rec["is_idle"] = rec["idle_seconds"] > 5
        elif choice == 2:
            rec["awaiting_input"] = not rec["awaiting_input"]
        elif choice == 3:
            rec["pane"] = dict(rec["pane"], width=r.randint(40, 250),
                               history_size=r.choice([None, r.randint(0, 900)]))
        elif choice == 4:
            rec["compare_mode"] = r.choice(["stripped", "raw"])
            rec["last_change"] = TS + self.tick
        return rec

    def step(self) -> tuple[float, sp.StreamFrame]:
        r = self.rng
        self.tick += 1
        for pane_id in self.POOL:
            roll = r.random()
            if pane_id not in self.panes and roll < 0.15:
                self.panes[pane_id] = self._new_record(pane_id)
            elif pane_id in self.panes and roll < 0.08:
                del self.panes[pane_id]
                self.shadows.pop(pane_id, None)
            elif pane_id in self.panes and roll < 0.6:
                self.panes[pane_id] = self._mutate(self.panes[pane_id])
        for followed in list(self.panes):
            roll = r.random()
            if followed not in self.shadows and roll < 0.1:
                self.shadows[followed] = self._new_record(
                    f"%{100 + int(followed[1:])}", shadow_of=followed)
            elif followed in self.shadows and roll < 0.1:
                del self.shadows[followed]
            elif followed in self.shadows and roll < 0.5:
                self.shadows[followed] = self._mutate(self.shadows[followed])
        ids = sorted(self.panes)
        frame = sp.StreamFrame(
            panes=dict(self.panes),
            shadows=dict(self.shadows),
            completed=frozenset(i for i in ids if r.random() < 0.2),
            sessions=sp.sessions_member({s: f"/p/{s}" for s in ("s1", "s2", "s3")
                                         if r.random() < 0.8}),
            parked=frozenset({("s1", f"agent-pick-{n}") for n in range(r.randint(0, 3))}),
            discovery=sp.discovery_member(
                [s for s in ("s1", "s2") if r.random() < 0.9],
                [(self.panes[i]["pane"]["session_name"], self.panes[i]["pane"]["window_name"])
                 for i in ids],
                {(self.panes[i]["pane"]["session_name"], self.panes[i]["pane"]["window_name"]):
                     [(i, 4000, r.random() < 0.05)] for i in ids}),
            control_state=r.choice(["connected"] * 8 + ["reconnecting", "fallback"]),
        )
        return TS + 3.0 * self.tick, frame


def wire(msg) -> dict:
    return sp.decode(sp.encode(msg, direction=sp.SERVER), direction=sp.SERVER)


class EncoderStateTests(unittest.TestCase):
    def test_random_walk_reconstructs_every_frame(self):
        walk = RandomWalk(seed=20341103)
        encoder = sp.StreamEncoder()
        full = sp.StreamState(require_content=True)
        selection = ["%1", "%3", "%7"]
        selected = sp.StreamState()
        no_shadows = sp.StreamState()
        full.apply(wire(encoder.snapshot(ts=TS)))
        selected.apply(wire(encoder.snapshot(ts=TS, content=selection)))
        no_shadows.apply(wire(encoder.snapshot(ts=TS, content="none", include_shadows=False)))
        saw = {"removed": 0, "shadows_removed": 0, "patch": 0, "full_in_delta": 0}
        for step in range(300):
            ts, frame = walk.step()
            delta = encoder.update(frame, ts=ts)
            self.assertEqual(delta["gen"], step + 1)
            saw["removed"] += bool(delta.get("removed"))
            saw["shadows_removed"] += bool(delta.get("shadows_removed"))
            for rec in delta.get("panes", {}).values():
                saw["full_in_delta" if "pane" in rec and len(rec) >= 13 else "patch"] += 1
            expected = normalized(frame)

            self.assertIsNotNone(full.apply(wire(delta)))
            self.assertEqual(full.frame(), expected, f"step {step}")

            if step == 150:
                # set_content mid-stream: a fresh snapshot under the new
                # selection brings the newly selected panes' CURRENT content.
                selection = ["%2", "%5", "%11"]
                selected.apply(wire(encoder.snapshot(ts=ts, content=selection)))
            else:
                selected.apply(wire(sp.filter_message(delta, content=selection)))
            want = strip_unselected(expected, selection)
            self.assertEqual(selected.frame(), want, f"step {step}")
            self.assertEqual(set(selected.frame().panes), set(expected.panes))

            no_shadows.apply(wire(sp.filter_message(delta, content="none",
                                                    include_shadows=False)))
            want_none = replace(strip_unselected(expected, "none"), shadows={})
            self.assertEqual(no_shadows.frame(), want_none, f"step {step}")
        for what, count in saw.items():
            self.assertGreater(count, 0, f"the walk never exercised {what}")

    def test_status_members_never_depend_on_selection(self):
        walk = RandomWalk(seed=7)
        encoder = sp.StreamEncoder()
        for _ in range(20):
            ts, frame = walk.step()
            delta = encoder.update(frame, ts=ts)
            projected = sp.filter_message(delta, content="none")
            for key, rec in delta.get("panes", {}).items():
                status = {k: v for k, v in rec.items() if k != "content"}
                if status:
                    self.assertEqual(projected["panes"][key], status)
                else:
                    self.assertNotIn(key, projected.get("panes", {}))
            for name in sp.TOP_LEVEL_MEMBERS + ("removed", "shadows_removed", "gen", "ts"):
                self.assertEqual(projected.get(name), delta.get(name))

    def test_filter_never_drops_a_delta(self):
        encoder = sp.StreamEncoder()
        encoder.update(sp.StreamFrame(panes={"%1": make_record("%1")}), ts=TS)
        delta = encoder.update(sp.StreamFrame(panes={"%1": make_record("%1", content="new")}),
                               ts=TS + 3)
        self.assertEqual(set(delta["panes"]["%1"]), {"content"})
        projected = sp.filter_message(delta, content="none")
        self.assertEqual(projected, {"type": "delta", "gen": 2, "ts": TS + 3})

    def test_determinism(self):
        def stream(seed):
            walk, encoder, out = RandomWalk(seed), sp.StreamEncoder(), []
            for _ in range(40):
                ts, frame = walk.step()
                out.append(sp.encode(encoder.update(frame, ts=ts), direction=sp.SERVER))
            out.append(sp.encode(encoder.snapshot(), direction=sp.SERVER))
            return b"".join(out)
        self.assertEqual(stream(3), stream(3))
        self.assertNotEqual(stream(3), stream(4))

    def test_encoder_refuses_a_vanishing_member(self):
        encoder = sp.StreamEncoder()
        encoder.update(sp.StreamFrame(panes={"%1": make_record("%1")}), ts=TS)
        bare = {k: v for k, v in make_record("%1").items() if k != "content"}
        with self.assertRaises(ValueError):
            encoder.update(sp.StreamFrame(panes={"%1": bare}), ts=TS + 3)

    def test_unchanged_frame_is_an_empty_heartbeat_delta(self):
        encoder = sp.StreamEncoder()
        frame = sp.StreamFrame(panes={"%1": make_record("%1")}, control_state="connected")
        encoder.update(frame, ts=TS)
        self.assertEqual(encoder.update(frame, ts=TS + 3), {"type": "delta", "gen": 2, "ts": TS + 3})


class GenerationRuleTests(unittest.TestCase):
    def setUp(self):
        self.encoder = sp.StreamEncoder()
        self.frame1 = sp.StreamFrame(panes={"%1": make_record("%1")}, control_state="connected")
        self.d1 = wire(self.encoder.update(self.frame1, ts=TS))
        self.frame2 = sp.StreamFrame(panes={"%1": make_record("%1", idle=3.0),
                                            "%2": make_record("%2")}, control_state="connected")
        self.d2 = wire(self.encoder.update(self.frame2, ts=TS + 3))
        self.snap0 = wire(sp.snapshot_message(sp.StreamFrame(), gen=0, ts=TS - 3))

    def test_delta_before_snapshot_raises(self):
        with self.assertRaises(sp.StreamError):
            sp.StreamState().apply(self.d1)

    def test_stale_delta_is_dropped(self):
        state = sp.StreamState()
        state.apply(self.snap0)
        state.apply(self.d1)
        state.apply(self.d2)
        before = state.frame()
        self.assertIsNone(state.apply(self.d1))
        self.assertIsNone(state.apply(self.d2))
        self.assertEqual(state.frame(), before)
        self.assertEqual(state.gen, 2)

    def test_gap_raises_stream_gap(self):
        state = sp.StreamState()
        state.apply(self.snap0)
        with self.assertRaises(sp.StreamGap):
            state.apply(self.d2)
        self.assertEqual(state.gen, 0)

    def test_patch_for_an_unknown_id_raises_and_leaves_state(self):
        state = sp.StreamState()
        state.apply(self.snap0)
        bad = {"type": "delta", "ts": TS, "gen": 1, "panes": {"%1": {"idle_seconds": 1.0}},
               "control_state": "changed"}
        with self.assertRaises(sp.StreamError):
            state.apply(wire(bad))
        self.assertEqual(state.gen, 0)
        self.assertEqual(state.control_state, "stopped")

    def test_empty_delta_is_applied(self):
        state = sp.StreamState()
        state.apply(self.snap0)
        applied = state.apply(wire({"type": "delta", "ts": TS, "gen": 1}))
        self.assertEqual((applied.kind, applied.gen, applied.changed), ("delta", 1, frozenset()))
        self.assertEqual(state.gen, 1)

    def test_snapshot_replaces_wholesale_and_patch_replaces_members(self):
        state = sp.StreamState()
        state.apply(wire(self.encoder.snapshot()))
        self.assertEqual(state.frame(), normalized(self.frame2))
        applied = state.apply(wire({"type": "delta", "ts": TS + 6, "gen": 3,
                                    "panes": {"%1": {"pane": dict(make_record("%1")["pane"],
                                                                  width=99)}},
                                    "removed": ["%2"]}))
        self.assertEqual(applied.changed, {"%1"})
        self.assertEqual(applied.removed, {"%2"})
        self.assertEqual(state.records()["%1"]["pane"]["width"], 99)
        self.assertEqual(state.records()["%1"]["idle_seconds"], 3.0)
        resync = wire(sp.snapshot_message(self.frame1, gen=10, ts=TS + 30))
        state.apply(resync)
        self.assertEqual((state.gen, set(state.records())), (10, {"%1"}))

    def test_require_content_rejects_contentless_full_records(self):
        state = sp.StreamState(require_content=True)
        snap = wire(sp.snapshot_message(self.frame1, gen=1, ts=TS, content="none"))
        with self.assertRaises(sp.StreamError):
            state.apply(snap)

    def test_read_surface(self):
        state = sp.StreamState()
        with self.assertRaises(sp.StreamError):
            state.snapshots()
        frame = sp.StreamFrame(
            panes={"%1": make_record("%1")},
            shadows={"%1": make_record("%9", pane_kw={"shadow_target": "%1"})},
            completed=frozenset({"%1"}), sessions=sp.sessions_member({"s1": "/p/s1"}),
            parked=frozenset({("s1", "w")}),
            discovery=sp.discovery_member(["s1"], [("s1", "w")], {("s1", "w"): [("%1", 1, False)]}),
            control_state="connected")
        state.apply(wire(sp.snapshot_message(frame, gen=1, ts=TS)))
        snaps = state.snapshots(now=9.0)
        self.assertEqual(snaps["%1"].timestamp, 9.0)
        self.assertEqual(state.shadow_snapshots()["%1"].pane.pane_id, "%9")
        self.assertEqual(state.completed, {"%1"})
        self.assertEqual(state.parked, {("s1", "w")})
        self.assertEqual(state.session_roots(), {"s1": "/p/s1"})
        self.assertEqual(state.discovery["enumerated"], ["s1"])
        self.assertEqual(state.control_state, "connected")


# ---------------------------------------------------------------------------
# Spec pin (post-phase mitigation spec_codec_constants_pin)
# ---------------------------------------------------------------------------

_MARKER = re.compile(r"^<!-- schema:(message|object|result|list) ([\w.-]+) -->$")
_MEMBER = re.compile(r"^`([^`]+)`$")


def parse_spec(text: str) -> dict:
    """``{kind: {name: parsed}}`` from the spec's ``schema:`` markers. A table
    parses to ``{member: required}``, a list to its backticked items."""
    out: dict = {"message": {}, "object": {}, "result": {}, "list": {}}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = _MARKER.match(lines[i].strip())
        i += 1
        if not m:
            continue
        kind, name = m.groups()
        if name in out[kind]:
            raise AssertionError(f"duplicate schema marker {kind} {name}")
        if kind == "list":
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                item = _MEMBER.match(lines[i][2:].strip())
                if item is None:
                    raise AssertionError(f"list {name}: not a backticked item: {lines[i]!r}")
                items.append(item.group(1))
                i += 1
            out[kind][name] = items
            continue
        members: dict = {}
        if i < len(lines) and lines[i].startswith("|"):
            header = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            req_col = header.index("Required")
            i += 2  # header + separator
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                member = _MEMBER.match(cells[0])
                if member is None:
                    raise AssertionError(f"{kind} {name}: bad member cell {cells[0]!r}")
                if cells[req_col] not in ("yes", "no"):
                    raise AssertionError(f"{kind} {name}: Required must be yes/no")
                members[member.group(1)] = cells[req_col] == "yes"
                i += 1
        out[kind][name] = members
    return out


class SpecPinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = parse_spec(SPEC.read_text(encoding="utf-8"))

    def test_every_message_table_matches_the_codec(self):
        self.assertEqual(set(self.spec["message"]), set(sp.MESSAGE_SCHEMAS))
        for name in sp.MESSAGE_SCHEMAS:
            with self.subTest(message=name):
                self.assertEqual(self.spec["message"][name], sp.message_members(name))

    def test_every_object_table_matches_the_codec(self):
        self.assertEqual(set(self.spec["object"]), set(sp.OBJECT_SCHEMAS))
        for name in sp.OBJECT_SCHEMAS:
            with self.subTest(object=name):
                self.assertEqual(self.spec["object"][name], sp.object_members(name))

    def test_every_result_table_matches_the_codec(self):
        self.assertEqual(set(self.spec["result"]), set(sp.RESULT_SCHEMAS))
        for name in sp.RESULT_SCHEMAS:
            with self.subTest(result=name):
                self.assertEqual(self.spec["result"][name], sp.result_members(name))

    def test_lists_match_the_codec(self):
        expected = {
            "error-codes": list(sp.ERROR_CODES),
            "category": list(sp.CATEGORY_VALUES),
            "compare_mode": list(sp.COMPARE_MODE_VALUES),
            "types-client": list(sp.CLIENT_TYPES),
            "types-server": list(sp.SERVER_TYPES),
            "types-recording": list(sp.RECORDING_TYPES),
        }
        self.assertEqual(self.spec["list"], expected)

    def test_the_parser_sees_a_drifted_table(self):
        # Negative control: the pin is only worth something if a one-row drift
        # in the document is visible to it.
        text = SPEC.read_text(encoding="utf-8").replace(
            "| `lines` | integer | yes |", "| `lines` | integer | no |", 1)
        drifted = parse_spec(text)
        self.assertNotEqual(drifted["message"]["capture"], sp.message_members("capture"))
        removed = SPEC.read_text(encoding="utf-8").replace("- `too_long`\n", "", 1)
        self.assertNotEqual(parse_spec(removed)["list"]["error-codes"], list(sp.ERROR_CODES))


if __name__ == "__main__":
    unittest.main()
