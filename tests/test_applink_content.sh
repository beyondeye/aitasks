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

print(f"\nALL PASSED ({PASS} checks)")
PYEOF
