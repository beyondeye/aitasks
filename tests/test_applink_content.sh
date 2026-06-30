#!/usr/bin/env bash
# test_applink_content.sh — unit tests for the applink data-plane content
# encoding (t822_8): the SGR -> styled-span parser, the keyframe/cursor/dim
# MessagePack frame encoders, and the pure Subscription state. No sockets, no
# tmux. Run: bash tests/test_applink_content.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

# msgpack backs the frame encoders; skip on a fresh clone that has not run setup.
if ! "$PYTHON" -c "import msgpack" 2>/dev/null; then
    echo "SKIP: msgpack not installed (run 'ait setup' first)"
    exit 0
fi

"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))

import msgpack
import content as C

PASS = 0
def check(label, cond):
    global PASS
    assert cond, f"FAIL: {label}"
    PASS += 1
    print(f"ok - {label}")


# --- char width ------------------------------------------------------------
check("ascii width 1", C.char_width("a") == 1)
check("wide CJK width 2", C.char_width("世") == 2)
check("fullwidth digit width 2", C.char_width("１") == 2)
check("combining mark width 0", C.char_width("́") == 0)
check("zero-width joiner width 0", C.char_width("‍") == 0)

# --- SGR parser: plain text ------------------------------------------------
spans, urls = C.parse_sgr_line("hello")
check("plain -> single span", len(spans) == 1)
check("plain span text", spans[0][0] == "hello")
check("plain span default fg/bg null", spans[0][1] is None and spans[0][2] is None)
check("plain span attrs 0", spans[0][3] == 0)
check("plain span width = len", spans[0][4] == 5)
check("plain no url", urls == [""])

# --- SGR parser: colours + attrs + escape stripping ------------------------
spans, _ = C.parse_sgr_line("\x1b[1;4;31mRED\x1b[0m plain")
check("bold+underline+fg split into styled span", spans[0][0] == "RED")
check("fg 31 -> palette 1", spans[0][1] == 1)
check("bold bit set", spans[0][3] & C.ATTR_BOLD)
check("underline bit set", spans[0][3] & C.ATTR_UNDERLINE)
check("style change splits span", spans[1][0] == " plain" and spans[1][3] == 0)
check("NO ESC survives into any span text", all("\x1b" not in s[0] for s in spans))

spans, _ = C.parse_sgr_line("\x1b[48;5;236mBG")
check("256-colour bg -> palette index", spans[0][2] == 236)

spans, _ = C.parse_sgr_line("\x1b[38;2;10;20;30mTC")
check("truecolor fg packed negative",
      spans[0][1] == -(((0xFF) << 24) | (10 << 16) | (20 << 8) | 30))

spans, _ = C.parse_sgr_line("\x1b[7mrev\x1b[27mnorm")
check("reverse bit set then cleared",
      (spans[0][3] & C.ATTR_REVERSE) and not (spans[1][3] & C.ATTR_REVERSE))

# bright colours map to palette 8-15
spans, _ = C.parse_sgr_line("\x1b[91mbright")
check("bright fg (91) -> palette 9", spans[0][1] == 9)

# --- SGR parser: OSC8 hyperlinks (BEL and ESC\ terminators) ----------------
spans, urls = C.parse_sgr_line("\x1b]8;;https://x\x1b\\link\x1b]8;;\x1b\\ after")
check("osc8 span sets hyperlink bit", spans[0][3] & C.ATTR_HYPERLINK)
check("osc8 url captured", urls[0] == "https://x")
check("osc8 close resets url", urls[1] == "" and not (spans[1][3] & C.ATTR_HYPERLINK))

spans, urls = C.parse_sgr_line("\x1b]8;;https://bel\atext\x1b]8;;\a")
check("osc8 with BEL terminator", urls[0] == "https://bel" and spans[0][0] == "text")

# --- snapshot_to_rows + frame-global osc8 sidecar --------------------------
rows, osc8 = C.snapshot_to_rows("a\n\x1b]8;;u\x1b\\b\x1b]8;;\x1b\\\n")
check("rows from 0 (top of viewport)", rows[0][0] == 0 and rows[1][0] == 1)
check("trailing newline does not add an empty row", len(rows) == 2)
check("osc8 sidecar keyed by frame-global span offset", osc8 == {1: "u"})

# --- frame encoders --------------------------------------------------------
kf = C.encode_keyframe("%1", 7, 80, 24, [3, 4, True, 0],
                       [[0, [["hi", None, None, 0, 2]]]], None)
check("keyframe type tag 0x01", kf[0] == C.FRAME_KEYFRAME)
dec = msgpack.unpackb(kf[1:], raw=False)
check("keyframe fields round-trip",
      dec[:5] == ["%1", 7, 80, 24, [3, 4, True, 0]])
check("keyframe rows round-trip", dec[5] == [[0, [["hi", None, None, 0, 2]]]])
check("keyframe omits osc8 when empty", len(dec) == 6)

kf2 = C.encode_keyframe("%1", 8, 80, 24, [0, 0, False, 0],
                        [[0, [["x", None, None, C.ATTR_HYPERLINK, 1]]]], {0: "u"})
# osc8 sidecar keys are int span-offsets (content_transport.md) -> the decoder
# must allow int map keys (strict_map_key=False); mobile configures the same.
dec2 = msgpack.unpackb(kf2[1:], raw=False, strict_map_key=False)
check("keyframe includes osc8 when present", len(dec2) == 7 and dec2[6] == {0: "u"})

cur = C.encode_cursor("%1", 9, [1, 2, True, 0])
check("cursor type tag 0x04", cur[0] == C.FRAME_CURSOR)
check("cursor fields round-trip", msgpack.unpackb(cur[1:], raw=False) == ["%1", 9, [1, 2, True, 0]])

dim = C.encode_dim("%1", 100, 30)
check("dim type tag 0x05", dim[0] == C.FRAME_DIM)
check("dim fields round-trip (palette_hash default 0)",
      msgpack.unpackb(dim[1:], raw=False) == ["%1", 100, 30, 0])

# --- t822_9 delta engine: parse_snapshot / build_osc8 / row_signature ------
parsed = C.parse_snapshot("a\n\x1b]8;;u\x1b\\b\x1b]8;;\x1b\\\n")
check("parse_snapshot yields (row_id, spans, urls)",
      [p[0] for p in parsed] == [0, 1] and parsed[0][1][0][0] == "a")
check("parse_snapshot retains per-span urls", parsed[1][2] == ["u"])
check("snapshot_to_rows unchanged after refactor",
      C.snapshot_to_rows("a\n\x1b]8;;u\x1b\\b\x1b]8;;\x1b\\\n") ==
      ([[0, [["a", None, None, 0, 1]]],
        [1, [["b", None, None, C.ATTR_HYPERLINK, 1]]]], {1: "u"}))

# --- t1054 viewport trim: live frames carry only the visible viewport ------
# Capture = 3 scrollback rows above the 3-row viewport. parse_snapshot with a
# viewport_height keeps only the trailing `height` rows, renumbered from 0 so
# row_id 0 == top of the VISIBLE viewport (content_transport.md §Row schema).
vp = C.parse_snapshot("s0\ns1\ns2\nv0\nv1\nv2\n", 3)
check("viewport trim keeps exactly `height` rows", len(vp) == 3)
check("viewport rows renumbered 0..height-1", [p[0] for p in vp] == [0, 1, 2])
check("row_id 0 == first VISIBLE row, not oldest scrollback",
      [p[1][0][0] for p in vp] == ["v0", "v1", "v2"])
# Defensive: height >= captured row count -> all rows, numbered from 0.
vp_all = C.parse_snapshot("only\n", 24)
check("viewport_height > captured rows -> all rows from 0",
      [p[0] for p in vp_all] == [0] and vp_all[0][1][0][0] == "only")
# Degenerate zero-height pane -> no rows (NOT the whole capture via lines[-0:]).
check("viewport_height 0 -> no rows", C.parse_snapshot("a\nb\n", 0) == [])
# No viewport_height (default) -> full parse, unchanged (snapshot_to_rows path).
check("parse_snapshot without height is unchanged (full parse)",
      [p[0] for p in C.parse_snapshot("s0\ns1\nv0\nv1\n")] == [0, 1, 2, 3])

# build_osc8 over a row SUBSET -> offsets relative to the subset, not the grid.
psub = C.parse_snapshot("plain\n\x1b]8;;z\x1b\\link\x1b]8;;\x1b\\\n")
check("build_osc8 over subset -> subset-relative offset", C.build_osc8([psub[1]]) == {0: "z"})
check("build_osc8 over full -> global offset", C.build_osc8(psub) == {1: "z"})

# row_signature: equal for identical spans, differs on any field change.
check("row_signature stable for equal spans",
      C.row_signature([["x", 1, None, 0, 1]]) == C.row_signature([["x", 1, None, 0, 1]]))
check("row_signature differs on field change",
      C.row_signature([["x", 1, None, 0, 1]]) != C.row_signature([["x", 2, None, 0, 1]]))

# deltify: change 1 row of 3 -> 1 changed row, nothing removed.
base = C.parse_snapshot("l0\nl1\nl2\n")
prev = {rid: C.row_signature(spans) for rid, spans, _u in base}
changed, removed, new_sigs, subset = C.deltify(prev, C.parse_snapshot("l0\nXX\nl2\n"))
check("deltify -> exactly one changed row", len(changed) == 1 and changed[0][0] == 1)
check("deltify changed row carries new content", changed[0][1][0][0] == "XX")
check("deltify nothing removed when count stable", removed == [])
check("deltify new_sigs covers all current rows", set(new_sigs) == {0, 1, 2})
check("deltify changed_subset matches changed rows", [s[0] for s in subset] == [1])

# deltify: unchanged snapshot -> empty changed + removed.
c2, r2, _n2, _s2 = C.deltify(prev, C.parse_snapshot("l0\nl1\nl2\n"))
check("deltify unchanged -> empty changed and removed", c2 == [] and r2 == [])

# deltify: a dropped trailing line -> its row_id in `removed`.
c3, r3, _n3, _s3 = C.deltify(prev, C.parse_snapshot("l0\nl1\n"))
check("deltify dropped row -> removed (cleared by caller)", r3 == [2] and c3 == [])

# deltify: None baseline is a programming error (caller routes via the keyframe path).
try:
    C.deltify(None, base)
    check("deltify(None) raises", False)
except AssertionError:
    check("deltify(None) raises AssertionError", True)

# --- encode_delta (0x02) ---------------------------------------------------
d = C.encode_delta("%1", 5, 4, [1, 2, True, 0], [[1, [["XX", None, None, 0, 2]]]], None)
check("delta type tag 0x02", d[0] == C.FRAME_DELTA)
ddec = msgpack.unpackb(d[1:], raw=False)
check("delta fields round-trip [pane,fid,prev,cursor,rows]",
      ddec == ["%1", 5, 4, [1, 2, True, 0], [[1, [["XX", None, None, 0, 2]]]]])
check("delta omits osc8 when empty", len(ddec) == 5)
d2 = C.encode_delta("%1", 6, 5, [0, 0, False, 0],
                    [[1, [["L", None, None, C.ATTR_HYPERLINK, 1]]]], {0: "z"})
d2dec = msgpack.unpackb(d2[1:], raw=False, strict_map_key=False)
check("delta includes osc8 when present", len(d2dec) == 6 and d2dec[5] == {0: "z"})

# --- t822_10 append fast path: encode_append + detect_append ---------------
ap = C.encode_append("%1", 11, [[2, [["new", None, None, 0, 3]]]])
check("append type tag 0x03", ap[0] == C.FRAME_APPEND)
apdec = msgpack.unpackb(ap[1:], raw=False)
check("append fields round-trip [pane,fid,rows]",
      apdec == ["%1", 11, [[2, [["new", None, None, 0, 3]]]]])
check("append has no cursor/prev/osc8 (exactly 3 elements)", len(apdec) == 3)

def _sigs(text):
    return {rid: C.row_signature(spans) for rid, spans, _u in C.parse_snapshot(text)}

# clean scroll-by-1: new == prev shifted up by 1, one brand-new bottom row.
check("detect_append scroll-by-1 -> 1",
      C.detect_append(_sigs("a\nb\nc\n"), _sigs("b\nc\nd\n")) == 1)
# clean scroll-by-2.
check("detect_append scroll-by-2 -> 2",
      C.detect_append(_sigs("a\nb\nc\nd\n"), _sigs("c\nd\ne\nf\n")) == 2)
# repeated lines: smallest matching k is still convergence-safe.
check("detect_append repeated-line scroll -> 1",
      C.detect_append(_sigs("a\na\na\n"), _sigs("a\na\nb\n")) == 1)
# mid-screen edit (only row 1 changed) -> not a shift.
check("detect_append mid-screen edit -> None",
      C.detect_append(_sigs("a\nb\nc\n"), _sigs("a\nX\nc\n")) is None)
# full replacement (no shared row) -> None.
check("detect_append full replacement -> None",
      C.detect_append(_sigs("a\nb\n"), _sigs("c\nd\n")) is None)
# differing row counts -> None.
check("detect_append differing row counts -> None",
      C.detect_append(_sigs("a\nb\nc\n"), _sigs("b\nc\n")) is None)
# None baseline -> None (caller routes the first frame via the keyframe path).
check("detect_append None baseline -> None", C.detect_append(None, _sigs("a\nb\n")) is None)

# --- Subscription ----------------------------------------------------------
sub = C.Subscription()
accepted = sub.apply_subscribe({
    "panes": ["%1", "%2"], "cadence_idle_ms": 50, "cadence_focused_ms": 10,
    "keyframe_interval_ms": 100,
})
check("apply_subscribe returns accepted panes", accepted == {"%1", "%2"})
check("idle cadence clamped up to floor", sub.cadence_idle_ms == C.FLOOR_IDLE_MS)
check("focused cadence clamped up to floor", sub.cadence_focused_ms == C.FLOOR_FOCUSED_MS)
check("keyframe interval clamped up to floor", sub.keyframe_interval_ms == C.MIN_KEYFRAME_INTERVAL_MS)
check("subscribe seeds force set", sub.force == {"%1", "%2"})

# --- t1007: cadence + pane-count hardening ---------------------------------
# keyframe interval is also UPPER-bounded (an unbounded value defeats periodic resync)
subk = C.Subscription()
subk.apply_subscribe({"panes": ["%1"], "keyframe_interval_ms": 10**9})
check("keyframe interval clamped DOWN to MAX", subk.keyframe_interval_ms == C.MAX_KEYFRAME_INTERVAL_MS)

# non-numeric / null / inf cadences coerce to defaults instead of raising (a bare
# int("abc") would escape apply_subscribe and drop the whole connection)
subc = C.Subscription()
subc.apply_subscribe({
    "panes": ["%1"], "cadence_idle_ms": "abc",
    "cadence_focused_ms": None, "keyframe_interval_ms": float("inf"),
})
check("non-numeric idle coerces to default", subc.cadence_idle_ms == C.DEFAULT_IDLE_MS)
check("null focused coerces to default", subc.cadence_focused_ms == C.DEFAULT_FOCUSED_MS)
check("inf keyframe coerces to default (no OverflowError)",
      subc.keyframe_interval_ms == C.DEFAULT_KEYFRAME_INTERVAL_MS)

# subscribed-pane count is capped at MAX_SUBSCRIBED_PANES — the only bound on the
# roster-subscribe path (the router does not cap the discovered roster)
big_panes = ["%%%d" % i for i in range(C.MAX_SUBSCRIBED_PANES + 50)]
subp = C.Subscription()
accepted_big = subp.apply_subscribe({"panes": big_panes})
check("apply_subscribe caps pane count at MAX_SUBSCRIBED_PANES",
      len(subp.panes) == C.MAX_SUBSCRIBED_PANES and len(accepted_big) == C.MAX_SUBSCRIBED_PANES)

sub.set_focus("%1")
check("cadence_for focused pane", sub.cadence_for("%1") == sub.cadence_focused_ms)
check("cadence_for idle pane", sub.cadence_for("%2") == sub.cadence_idle_ms)
check("next_tick uses min cadence when focused", sub.next_tick_ms() == sub.cadence_focused_ms)

sub.request_keyframe("%2")
check("request_keyframe adds to force", "%2" in sub.force)
check("frame_id monotonic per pane",
      sub.next_frame_id("%1") == 1 and sub.next_frame_id("%1") == 2 and sub.next_frame_id("%2") == 1)

# re-subscribing to a narrower set drops stale per-pane state + focus
sub.apply_subscribe({"panes": ["%2"]})
check("re-subscribe drops unsubscribed pane state", "%1" not in sub._pane)
check("re-subscribe clears focus when focused pane dropped", sub.focused_pane is None)

# --- content split (t1045): status (panes) vs content (content_panes) -------
sc = C.Subscription()
sc.apply_subscribe({"panes": ["%1", "%2"]})
check("content_all defaults True when content_panes absent (legacy)", sc.content_all is True)
check("legacy: streams_content True for every roster pane",
      sc.streams_content("%1") and sc.streams_content("%2"))
check("legacy: streams_content False for a pane outside the roster",
      sc.streams_content("%9") is False)

sc2 = C.Subscription()
sc2.apply_subscribe({"panes": ["%1", "%2", "%3"], "content_panes": ["%2", "%9"]})
check("content_panes present -> content_all False", sc2.content_all is False)
check("content_panes intersected with roster (drops out-of-roster %9)", sc2.content_panes == {"%2"})
check("streams_content: content pane streams", sc2.streams_content("%2") is True)
check("streams_content: status-only pane does NOT stream", sc2.streams_content("%1") is False)
check("streams_content: pane outside roster does NOT stream", sc2.streams_content("%9") is False)

# set_focus promotes the focused pane in split mode (forces a keyframe)...
sc2.force.clear()
sc2.set_focus("%1")
check("split mode: set_focus forces a keyframe for the newly-focused pane", "%1" in sc2.force)
check("split mode: focused pane now streams content", sc2.streams_content("%1") is True)
# ...but in legacy content_all mode it adds no force (the pane already streams).
sc3 = C.Subscription()
sc3.apply_subscribe({"panes": ["%1", "%2"]})
sc3.force.clear()
sc3.set_focus("%1")
check("legacy mode: set_focus adds no force (pane already content)", "%1" not in sc3.force)

# an empty content_panes list -> no pane streams until focus picks one
sc4 = C.Subscription()
sc4.apply_subscribe({"panes": ["%1", "%2"], "content_panes": []})
check("content_panes:[] -> content_all False, empty content set, nothing streams",
      sc4.content_all is False and sc4.content_panes == set()
      and not sc4.streams_content("%1") and not sc4.streams_content("%2"))

# --- history_rows: scrollback with negative row_ids (t1057) -----------------
# Each line's text == its absolute capture index, so the expected row is read
# straight from the line list (independent ground truth, not the function).
hist_lines = [f"L{i}" for i in range(10)]
hist_content = "\n".join(hist_lines) + "\n"
H = 3
base = len(hist_lines) - H  # = 7; capture index of viewport row 0

def hist_text(rows):
    return {rid: "".join(s[0] for s in spans) for rid, spans in rows}

rows, osc8 = C.history_rows(hist_content, H, 0, 3)
got = hist_text(rows)
check("history_rows before_line=0 numbers rows -1..-3", [r for r, _ in rows] == [-1, -2, -3])
check("history_rows -j == lines[base+before_line-j] (ground truth)",
      all(got[-j] == hist_lines[base + 0 - j] for j in (1, 2, 3)))
check("history_rows osc8 empty when no hyperlinks", osc8 == {})

rows, _ = C.history_rows(hist_content, H, -2, 2)  # a deeper scrollback page
got = hist_text(rows)
check("history_rows negative before_line maps via base+before_line-j",
      [r for r, _ in rows] == [-1, -2]
      and all(got[-j] == hist_lines[base + (-2) - j] for j in (1, 2)))

rows, _ = C.history_rows(hist_content, H, 2, 2)  # anchor inside the viewport
got = hist_text(rows)
check("history_rows positive in-viewport before_line anchors correctly",
      all(got[-j] == hist_lines[base + 2 - j] for j in (1, 2)))

rows, _ = C.history_rows(hist_content, H, 0, 50)  # count exceeds retained scrollback
ids = [r for r, _ in rows]
check("history_rows clips at buffer top -> contiguous -1..-m, m<count",
      ids == list(range(-1, -(base + 1), -1)) and len(ids) == base)

rows, _ = C.history_rows(hist_content, H, 99, 5)  # anchor past the buffer
check("history_rows far-positive before_line -> empty (never sparse)", rows == [])

# osc8 sidecar is flat-offset over the EMITTED history rows
osc_lines = ["plain0", "\x1b]8;;https://ex\x07link\x1b]8;;\x07", "plain2", "v0", "v1"]
osc_content = "\n".join(osc_lines) + "\n"
# H=2 -> viewport=(v0,v1); base=3; before_line=0: -1->plain2, -2->hyperlink line
rows, osc8 = C.history_rows(osc_content, 2, 0, 3)
check("history_rows osc8 keyed by flat offset over history rows",
      list(osc8.values()) == ["https://ex"])

# --- Subscription history queue (t1057) ------------------------------------
hs = C.Subscription()
hs.apply_subscribe({"panes": ["%1", "%2"]})
tok1 = hs.request_history("%1", 0, 100)
check("request_history returns a token", isinstance(tok1, str) and bool(tok1))
check("has_pending_history true after request", hs.has_pending_history() is True)
tok2 = hs.request_history("%1", -50, 100)  # same pane -> coalesce (last wins)
check("request_history coalesces to one entry per pane", len(hs._pending_history) == 1)
check("coalesced entry keeps latest before_line + new token",
      hs._pending_history[0][1] == -50 and hs._pending_history[0][3] == tok2 and tok2 != tok1)
hs.request_history("%2", 0, 10)
drained = hs.take_pending_history()
check("take_pending_history returns all and clears the queue",
      len(drained) == 2 and hs.has_pending_history() is False)
hs.request_history("%1", 0, 5)
hs.request_history("%2", 0, 5)
hs.apply_subscribe({"panes": ["%2"]})  # %1 dropped
check("re-subscribe prunes pending history for unsubscribed panes",
      [r[0] for r in hs._pending_history] == ["%2"])

print(f"\nALL PASSED ({PASS} checks)")
PYEOF
