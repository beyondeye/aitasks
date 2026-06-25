"""applink data-plane content encoding (t822_8).

Pure SGR -> styled-span parser for ``tmux capture-pane -e`` output, the
MessagePack frame encoders (``keyframe``/``cursor``/``dim``), and the
per-connection :class:`Subscription` state that drives the push scheduler
(``pusher.py``). The wire format is **fixed** by
``aidocs/applink/content_transport.md`` — this module *consumes* it, it does not
redefine it.

Stage 1 (t822_8) implemented ``keyframe`` (0x01), ``cursor`` (0x04) and ``dim``
(0x05). Stage 2 (t822_9) adds ``delta`` (0x02): :func:`deltify` /
:func:`row_signature` / :func:`build_osc8` collect the changed rows against the
per-connection baseline (``Subscription.PaneState.row_sigs``) and
:func:`encode_delta` frames them. ``append`` (0x03, t822_10) reuses the same
parser and per-pane frame state: :func:`detect_append` spots a pure bottom-growth
scroll against the same ``row_sigs`` baseline and :func:`encode_append` frames the
new bottom rows.

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


def parse_snapshot(content: str, viewport_height: Optional[int] = None):
    """Parse a ``PaneSnapshot.content`` blob into a list of ``(row_id, spans, urls)``.

    ``spans`` is the list of fixed-arity ``[text, fg, bg, attrs, width]`` arrays
    for the row; ``urls`` is the parallel per-span OSC8 hyperlink list (``""``
    when not a hyperlink). This is the low-level parse that retains per-span URLs
    so a delta can build its ``osc8`` sidecar over a *subset* of rows
    (:func:`build_osc8`).

    When ``viewport_height`` is given (the **live push path**, ``pusher.py``),
    only the **live viewport** — the trailing ``viewport_height`` rows of the
    capture — is parsed, and those rows are renumbered ``0..viewport_height-1``
    so ``row_id`` 0 == top of the **visible viewport** (content_transport.md
    §Row schema). The capture carries ~200 scrollback rows above the viewport
    (``-S -<capture_lines>``); those are dropped from live frames — history is
    served separately via the (future) history RPC with negative row_ids. Every
    downstream live frame (keyframe ``full_rows``, the delta ``row_sigs``
    baseline, :func:`deltify`, :func:`detect_append`, :func:`build_osc8`) derives
    from this list, so passing the height here makes them all viewport-only at
    once.

    ``viewport_height=None`` (default) parses every captured row from 0 — the
    legacy/full behavior used by :func:`snapshot_to_rows` (and its tests). When
    ``viewport_height`` exceeds the captured row count, all rows are returned
    (renumbered from 0); ``viewport_height=0`` yields no rows.
    """
    parsed: list = []
    lines = content.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]  # drop the trailing empty cell from a final newline
    if viewport_height is not None:
        # Trim to the live viewport (trailing N rows). The `> 0` guard matters:
        # `lines[-0:]` is `lines[:]` (the whole list), so a zero-height pane must
        # short-circuit to no rows rather than emit the full capture.
        lines = lines[-viewport_height:] if viewport_height > 0 else []
    for row_id, line in enumerate(lines):  # enumerate from 0 == top of viewport
        spans, urls = parse_sgr_line(line)
        parsed.append((row_id, spans, urls))
    return parsed


def build_osc8(parsed) -> dict:
    """Frame-level OSC8 sidecar ``{flat_span_offset: url}`` over a parsed row list.

    ``parsed`` is a list of ``(row_id, spans, urls)`` (full snapshot or a delta's
    changed subset). The flat span offset is **row-major over the given list** —
    so a delta passing only its changed rows gets offsets relative to its own
    ``rows`` array, exactly as the keyframe gets frame-global offsets when passed
    the full snapshot. Only spans carrying a hyperlink are recorded.
    """
    osc8: dict = {}
    idx = 0
    for _row_id, _spans, urls in parsed:
        for url in urls:
            if url:
                osc8[idx] = url
            idx += 1
    return osc8


def row_signature(spans) -> int:
    """In-process-stable hash of one row's spans, for delta change detection.

    Stable for the lifetime of a connection's :class:`PaneState` (same basis as
    t822_8's whole-pane ``hash(snap.content)``); not persisted across processes.
    """
    return hash(tuple((s[0], s[1], s[2], s[3], s[4]) for s in spans))


def deltify(prev_sigs, parsed):
    """Collect the rows that changed vs the client's last-sent baseline.

    Returns ``(changed_wire, removed_ids, new_sigs, changed_subset)``:
      * ``changed_wire`` — ``[[row_id, spans], ...]`` for rows whose signature is
        new or changed.
      * ``removed_ids`` — row_ids present in ``prev_sigs`` but absent now (the
        client holds them; they must be cleared, see the convergence note below).
      * ``new_sigs`` — ``{row_id: sig}`` for the full current snapshot (the new
        baseline to store).
      * ``changed_subset`` — ``(row_id, spans, urls)`` for the changed rows (the
        :func:`build_osc8` source for the delta's sidecar).

    **Requires a prior keyframe baseline** — ``prev_sigs`` must not be ``None``;
    the caller routes the first / forced frame through the keyframe path. A
    ``removed`` row is emitted by the caller as ``[row_id, []]`` (empty spans),
    which clears the row on the client: delta semantics retain *unlisted* rows, so
    a row that went from content to absent within fixed dims must be explicitly
    cleared or the client would diverge from a fresh keyframe.
    """
    assert prev_sigs is not None, "deltify requires a prior keyframe baseline"
    new_sigs: dict = {}
    changed_subset: list = []
    for row_id, spans, urls in parsed:
        sig = row_signature(spans)
        new_sigs[row_id] = sig
        if prev_sigs.get(row_id) != sig:
            changed_subset.append((row_id, spans, urls))
    removed = [row_id for row_id in prev_sigs if row_id not in new_sigs]
    changed_wire = [[row_id, spans] for row_id, spans, _urls in changed_subset]
    return changed_wire, removed, new_sigs, changed_subset


def detect_append(prev_sigs, new_sigs):
    """Detect a pure bottom-growth scroll for the ``append`` (0x03) fast path.

    Returns ``k`` (``>= 1``) when the new grid is the baseline scrolled **up** by
    ``k`` rows with ``k`` brand-new rows at the bottom, else ``None`` (the caller
    falls back to :func:`deltify`). ``prev_sigs`` / ``new_sigs`` are
    ``{row_id: sig}`` over a *full* snapshot each (contiguous ``0..H-1``, as
    :func:`parse_snapshot` produces). Requires equal row counts ``H`` (a clean
    scroll keeps the viewport height) and ``1 <= k < H`` (at least one shared row;
    a full replacement is a keyframe, not an append).

    The check is the cheap prefix comparison the design doc calls for:
    ``new[i] == prev[i+k]`` for all ``i`` in ``[0, H-1-k]``. The smallest matching
    ``k`` is returned and is the correct one — the shift condition is fully
    verified for it, so a client that drops ``k`` top rows, shifts up, and appends
    the new bottom ``k`` rows converges exactly to ``new`` (``content_transport.md``
    §append). Cursor / alt-screen / hyperlink gating is the caller's
    responsibility (``pusher._push_pane``); this is pure signature math.
    """
    if prev_sigs is None:
        return None
    H = len(new_sigs)
    if H == 0 or len(prev_sigs) != H:
        return None
    for k in range(1, H):
        if all(new_sigs.get(i) == prev_sigs.get(i + k) for i in range(H - k)):
            return k
    return None


def snapshot_to_rows(content: str):
    """Parse a ``PaneSnapshot.content`` blob into ``(rows, osc8)`` for a keyframe.

    ``rows`` is a list of ``[row_id, [span, ...]]`` (``row_id`` 0 == top of the
    captured buffer — **all** captured rows, scrollback included). ``osc8`` is the
    frame-global sidecar map ``{flat_span_offset: url}`` (row-major over all
    rows). Thin wrapper over :func:`parse_snapshot` + :func:`build_osc8` —
    byte-for-byte identical output to the pre-t822_9 implementation.

    **Not the live push path.** This helper does not trim scrollback. The live
    push path (``pusher._push_pane``) must call ``parse_snapshot(content,
    viewport_height)`` so frames carry only the visible viewport per
    content_transport.md §Row schema (t1054); a caller that streams the output of
    this helper would re-emit scrollback rows with the wrong row-id basis.
    """
    parsed = parse_snapshot(content)
    rows = [[row_id, spans] for row_id, spans, _urls in parsed]
    return rows, build_osc8(parsed)


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


def encode_delta(pane_id, frame_id, prev_frame_id, cursor, row_list, osc8=None) -> bytes:
    """``delta`` (0x02): changed rows only, computed against ``prev_frame_id``.

    ``row_list`` is the list of ``[row_id, spans]`` changed rows (a row with an
    empty spans list clears that row on the client); ``cursor`` is
    ``[row, col, visible, style]``; ``osc8`` is the optional sidecar built over
    the changed rows (omitted from the wire when falsy). Wire array per
    content_transport.md §delta:
    ``[pane_id, frame_id, prev_frame_id, cursor, row_list, osc8?]``."""
    arr = [pane_id, frame_id, prev_frame_id, cursor, row_list]
    if osc8:
        arr.append(osc8)
    return bytes([FRAME_DELTA]) + _packb(arr)


def encode_append(pane_id, frame_id, row_list) -> bytes:
    """``append`` (0x03): rows appended at the bottom of the client buffer; the
    client drops the topmost rows to keep the row count from the latest keyframe.

    Carries **no** ``prev_frame_id`` (each ``append`` stacks on the latest visible
    state) and **no** ``osc8`` sidecar — the caller (``pusher._push_pane``) emits a
    ``delta`` instead whenever an appended row carries a hyperlink, and likewise
    sends no ``append`` when the cursor changed (``append`` has no cursor field).
    Wire array per ``content_transport.md`` §append:
    ``[pane_id, frame_id, row_list]``."""
    return bytes([FRAME_APPEND]) + _packb([pane_id, frame_id, row_list])


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
    # Per-row signatures the client currently holds ({row_id: sig}); ``None`` means
    # no baseline yet -> the next frame must be a keyframe (t822_9 delta engine).
    row_sigs: Optional[dict] = None
    # Full cursor [row, col, visible, style] at the last sent frame; ``None`` until
    # the first send. The ``append`` fast path (t822_10) fires only when the cursor
    # is unchanged from this, since ``append`` carries no cursor of its own.
    last_cursor: Optional[list] = None


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
