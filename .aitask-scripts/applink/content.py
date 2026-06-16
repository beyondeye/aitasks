"""applink data-plane content encoding (t822_8).

Pure SGR -> styled-span parser for ``tmux capture-pane -e`` output, the
MessagePack frame encoders (``keyframe``/``cursor``/``dim``), and the
per-connection :class:`Subscription` state that drives the push scheduler
(``pusher.py``). The wire format is **fixed** by
``aidocs/applink/content_transport.md`` — this module *consumes* it, it does not
redefine it.

Stage 1 (this task) implements ``keyframe`` (0x01), ``cursor`` (0x04) and
``dim`` (0x05). ``delta`` (0x02, t822_9) and ``append`` (0x03, t822_10) reuse
this module's parser and the per-pane frame state already tracked on
:class:`Subscription`.

``msgpack`` is imported **lazily** inside the ``encode_*`` functions so importing
the parser / :class:`Subscription` (e.g. from the router unit test) needs no
dependency — only the encoders do.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

# -- Frame type tags (content_transport.md §Frame types) ----------------------
FRAME_KEYFRAME = 0x01
FRAME_DELTA = 0x02      # reserved for t822_9
FRAME_APPEND = 0x03     # reserved for t822_10
FRAME_CURSOR = 0x04
FRAME_DIM = 0x05

# -- attrs bitfield (content_transport.md §Attrs bitfield) --------------------
ATTR_BOLD = 1 << 0
ATTR_ITALIC = 1 << 1
ATTR_UNDERLINE = 1 << 2
ATTR_REVERSE = 1 << 3
ATTR_STRIKE = 1 << 4
ATTR_BLINK = 1 << 5
ATTR_DIM = 1 << 6
ATTR_HYPERLINK = 1 << 7

# -- Cadence policy floors / defaults -----------------------------------------
# The server clamps client-requested cadences UP to these floors (the existing
# control-client throughput is the binding constraint, not the wire).
FLOOR_FOCUSED_MS = 200
FLOOR_IDLE_MS = 500
DEFAULT_IDLE_MS = 3000        # desktop main refresh (monitor_port_design.md)
DEFAULT_FOCUSED_MS = 300      # desktop fast-preview refresh
DEFAULT_KEYFRAME_INTERVAL_MS = 30000
MIN_KEYFRAME_INTERVAL_MS = 1000


# -- SGR / OSC8 parser ---------------------------------------------------------
#
# Input is `tmux capture-pane -e` output: already-rendered lines whose only
# escape sequences are SGR colour/attribute runs and OSC8 hyperlinks (tmux has
# resolved cursor movement / scroll regions / alt-screen). So an ad-hoc SGR
# state machine suffices — no pyte / terminal emulator.

# CSI sequence: ESC [ <params> <final byte>. We only act on the SGR final 'm';
# any other CSI in the input is dropped (should not appear in capture -e).
_CSI_SEQ = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
# OSC sequence: ESC ] <body> ST, where ST is BEL (\x07) or ESC \ .
_OSC_SEQ = re.compile(r"\x1b\](.*?)(?:\x07|\x1b\\)", re.S)


def char_width(ch: str) -> int:
    """Display width of one character (tmux-compatible, best-effort).

    Combining / zero-width / format chars -> 0; East Asian Wide/Fullwidth -> 2;
    everything else -> 1. Best-effort parity with tmux's width tables: the server
    is the authoritative width source and the mobile client uses the value
    verbatim (content_transport.md design goal 5), so self-consistency matters
    more than exact tmux parity in rare edge cases.
    """
    o = ord(ch)
    if o == 0:
        return 0
    if unicodedata.combining(ch):
        return 0
    if unicodedata.category(ch) in ("Mn", "Me", "Cf"):
        return 0
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1


def _ext_color(nums: list[int], i: int):
    """Resolve an extended-colour run starting at ``nums[i]`` (38 or 48).

    Returns ``(color_value, last_index_consumed)``:
      * ``38;5;n`` / ``48;5;n`` -> palette index ``n``.
      * ``38;2;r;g;b`` / ``48;2;r;g;b`` -> packed-negative truecolor per
        content_transport.md: ``-((0xFF<<24) | (r<<16) | (g<<8) | b)``.
    Returns ``(None, i)`` (no advance) when the run is malformed.
    """
    if i + 1 < len(nums):
        mode = nums[i + 1]
        if mode == 5 and i + 2 < len(nums):
            return nums[i + 2], i + 2
        if mode == 2 and i + 4 < len(nums):
            r, g, b = nums[i + 2], nums[i + 3], nums[i + 4]
            packed = -(((0xFF) << 24) | (r << 16) | (g << 8) | b)
            return packed, i + 4
    return None, i


def _apply_sgr(param_str, fg, bg, attrs):
    """Fold one ``ESC[<params>m`` run into the current ``(fg, bg, attrs)``."""
    if param_str == "":
        return None, None, 0  # bare ESC[m == reset
    tokens = [t for t in param_str.replace(":", ";").split(";") if t != ""]
    nums: list[int] = []
    for t in tokens:
        try:
            nums.append(int(t))
        except ValueError:
            nums.append(0)
    if not nums:
        return None, None, 0
    i = 0
    while i < len(nums):
        c = nums[i]
        if c == 0:
            fg, bg, attrs = None, None, 0
        elif c == 1:
            attrs |= ATTR_BOLD
        elif c == 2:
            attrs |= ATTR_DIM
        elif c == 3:
            attrs |= ATTR_ITALIC
        elif c == 4:
            attrs |= ATTR_UNDERLINE
        elif c == 5:
            attrs |= ATTR_BLINK
        elif c == 7:
            attrs |= ATTR_REVERSE
        elif c == 9:
            attrs |= ATTR_STRIKE
        elif c == 22:
            attrs &= ~(ATTR_BOLD | ATTR_DIM)
        elif c == 23:
            attrs &= ~ATTR_ITALIC
        elif c == 24:
            attrs &= ~ATTR_UNDERLINE
        elif c == 25:
            attrs &= ~ATTR_BLINK
        elif c == 27:
            attrs &= ~ATTR_REVERSE
        elif c == 29:
            attrs &= ~ATTR_STRIKE
        elif 30 <= c <= 37:
            fg = c - 30
        elif c == 38:
            fg, i = _ext_color(nums, i)
        elif c == 39:
            fg = None
        elif 40 <= c <= 47:
            bg = c - 40
        elif c == 48:
            bg, i = _ext_color(nums, i)
        elif c == 49:
            bg = None
        elif 90 <= c <= 97:
            fg = c - 90 + 8
        elif 100 <= c <= 107:
            bg = c - 100 + 8
        # any other code (e.g. 8 conceal) is ignored
        i += 1
    return fg, bg, attrs


def parse_sgr_line(line: str):
    """Parse one ``capture-pane -e`` line into styled spans.

    Returns ``(spans, urls)`` where ``spans`` is a list of fixed-arity
    ``[text, fg, bg, attrs, width]`` arrays (content_transport.md §Span schema)
    and ``urls`` is a parallel list giving each span's OSC8 hyperlink URL (``""``
    when not a hyperlink). No ANSI escape survives into ``text``. SGR state is
    reset at the start of each line (capture -e re-emits styling per line).
    """
    spans: list = []
    urls: list = []
    fg = None
    bg = None
    attrs = 0
    cur_url = ""
    buf: list[str] = []
    buf_w = 0

    def flush():
        nonlocal buf, buf_w
        if buf:
            a = attrs | (ATTR_HYPERLINK if cur_url else 0)
            spans.append(["".join(buf), fg, bg, a, buf_w])
            urls.append(cur_url)
            buf = []
            buf_w = 0

    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == "\x1b" and i + 1 < n:
            nxt = line[i + 1]
            if nxt == "[":
                m = _CSI_SEQ.match(line, i)
                if m:
                    seq = m.group(0)
                    if seq[-1] == "m":
                        flush()
                        fg, bg, attrs = _apply_sgr(seq[2:-1], fg, bg, attrs)
                    i = m.end()
                    continue
                i += 1
                continue
            if nxt == "]":
                m = _OSC_SEQ.match(line, i)
                if m:
                    body = m.group(1)
                    if body.startswith("8;"):
                        flush()
                        # body == "8;<params>;<uri>" — uri may be empty (close).
                        parts = body.split(";", 2)
                        cur_url = parts[2] if len(parts) >= 3 else ""
                    i = m.end()
                    continue
                i += 1
                continue
            # other two-char ESC sequence — drop it
            i += 2
            continue
        buf.append(ch)
        buf_w += char_width(ch)
        i += 1
    flush()
    return spans, urls


def snapshot_to_rows(content: str):
    """Parse a ``PaneSnapshot.content`` blob into ``(rows, osc8)``.

    ``rows`` is a list of ``[row_id, [span, ...]]`` (``row_id`` 0 == top of the
    captured viewport). ``osc8`` is the frame-level sidecar map
    ``{flat_span_offset: url}`` (offset is frame-global, row-major) — populated
    only for spans carrying a hyperlink.
    """
    rows: list = []
    osc8: dict = {}
    span_index = 0
    lines = content.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]  # drop the trailing empty cell from a final newline
    for row_id, line in enumerate(lines):
        spans, urls = parse_sgr_line(line)
        for url in urls:
            if url:
                osc8[span_index] = url
            span_index += 1
        rows.append([row_id, spans])
    return rows, osc8


# -- Frame encoders (lazy msgpack) --------------------------------------------

def _packb(obj) -> bytes:
    import msgpack
    return msgpack.packb(obj, use_bin_type=True)


def encode_keyframe(pane_id, frame_id, cols, rows, cursor, row_list, osc8=None) -> bytes:
    """``keyframe`` (0x01): full grid. ``cursor`` is ``[row, col, visible, style]``;
    ``row_list`` is the list of ``[row_id, spans]`` from :func:`snapshot_to_rows`;
    ``osc8`` is the optional sidecar map (omitted from the wire when falsy)."""
    arr = [pane_id, frame_id, cols, rows, cursor, row_list]
    if osc8:
        arr.append(osc8)
    return bytes([FRAME_KEYFRAME]) + _packb(arr)


def encode_cursor(pane_id, frame_id, cursor) -> bytes:
    """``cursor`` (0x04): cursor-only update."""
    return bytes([FRAME_CURSOR]) + _packb([pane_id, frame_id, cursor])


def encode_dim(pane_id, cols, rows, palette_hash=0) -> bytes:
    """``dim`` (0x05): dimensions / palette change. Stage 1 sends ``palette_hash=0``
    (resize-driven only)."""
    return bytes([FRAME_DIM]) + _packb([pane_id, cols, rows, palette_hash])


# -- Subscription state --------------------------------------------------------

def clamp_cadences(idle_ms, focused_ms, keyframe_interval_ms):
    """Clamp client-requested cadences up to the server policy floors."""
    idle = max(int(idle_ms), FLOOR_IDLE_MS)
    focused = max(int(focused_ms), FLOOR_FOCUSED_MS)
    kf = max(int(keyframe_interval_ms), MIN_KEYFRAME_INTERVAL_MS)
    return idle, focused, kf


@dataclass
class PaneState:
    """Per-(pane, connection) push state. ``frame_id`` is the monotonic u32 the
    wire spec keys per (pane, session); the rest gate change/cadence detection."""
    frame_id: int = 0
    last_hash: Optional[int] = None
    last_dims: Optional[tuple] = None
    last_keyframe_t: float = 0.0
    last_send_t: float = 0.0
    last_status_t: float = 0.0


class Subscription:
    """Pure per-connection subscription state mutated by the router and consumed
    by :class:`pusher.PushScheduler`. No sockets / asyncio / msgpack here."""

    def __init__(self) -> None:
        self.panes: set[str] = set()
        self.cadence_idle_ms = DEFAULT_IDLE_MS
        self.cadence_focused_ms = DEFAULT_FOCUSED_MS
        self.keyframe_interval_ms = DEFAULT_KEYFRAME_INTERVAL_MS
        self.focused_pane: Optional[str] = None
        self.viewport_hint = None  # stored, ignored until Stage 4 clipping
        self.force: set[str] = set()
        self._pane: dict[str, PaneState] = {}

    def apply_subscribe(self, payload: dict) -> set[str]:
        """Apply a ``subscribe`` payload; returns the accepted pane set.

        Replaces the pane set, clamps the cadences, seeds the force set so every
        subscribed pane gets an initial keyframe, and drops stale per-pane state.
        """
        panes = payload.get("panes")
        if isinstance(panes, list):
            self.panes = {p for p in panes if isinstance(p, str) and p}
        self.cadence_idle_ms, self.cadence_focused_ms, self.keyframe_interval_ms = (
            clamp_cadences(
                payload.get("cadence_idle_ms", self.cadence_idle_ms),
                payload.get("cadence_focused_ms", self.cadence_focused_ms),
                payload.get("keyframe_interval_ms", self.keyframe_interval_ms),
            )
        )
        self.viewport_hint = payload.get("viewport_hint")
        self.force |= set(self.panes)
        for pid in list(self._pane):
            if pid not in self.panes:
                del self._pane[pid]
        if self.focused_pane not in self.panes:
            self.focused_pane = None
        return set(self.panes)

    def request_keyframe(self, pane_id: str) -> None:
        self.force.add(pane_id)

    def set_focus(self, pane_id: str) -> None:
        self.focused_pane = pane_id

    def cadence_for(self, pane_id: str) -> int:
        if pane_id == self.focused_pane:
            return self.cadence_focused_ms
        return self.cadence_idle_ms

    def next_tick_ms(self) -> int:
        if self.focused_pane is not None and self.focused_pane in self.panes:
            return min(self.cadence_focused_ms, self.cadence_idle_ms)
        return self.cadence_idle_ms

    def state_for(self, pane_id: str) -> PaneState:
        st = self._pane.get(pane_id)
        if st is None:
            st = PaneState()
            self._pane[pane_id] = st
        return st

    def next_frame_id(self, pane_id: str) -> int:
        st = self.state_for(pane_id)
        st.frame_id += 1
        return st.frame_id
