"""Pure analysis core of the aitask-screen-recording skill (Python stdlib only).

Everything here works on plain values (timestamps, 8-bit grayscale frames as
`bytes`, bounding boxes), so it is unit-testable without ffmpeg. The ffmpeg
plumbing and file output live in video_prep.py.
"""
from __future__ import annotations

import bisect
import math
import re
import statistics
from dataclasses import dataclass, field
from fractions import Fraction

# --------------------------------------------------------------------------- #
# image budgets
#
# Claude vision limits, from platform.claude.com "Vision" ("Resolution and token
# cost", "Request limits"), checked 2026-11-04. An image larger than a tier's long
# edge or token limit is downscaled before the model sees it. A request carrying
# more than 20 images applies a stricter per-image dimension limit to all of them
# and rejects images over it; neither dimension above 3000 px is safe everywhere.

TOKEN_TILE = 28            # visual tokens = ceil(w / 28) * ceil(h / 28)
READER_TIERS = (("standard", 1568, 1568),
                ("high-resolution (Claude 4.7+)", 2576, 4784))  # name, long edge, tokens
MANY_IMAGE_SAFE_PX = 3000


def image_tokens(w: int, h: int) -> int:
    return math.ceil(w / TOKEN_TILE) * math.ceil(h / TOKEN_TILE)


def image_budget(w: int, h: int) -> dict:
    """Token cost of one w x h image and the reader limits it crosses."""
    tokens = image_tokens(w, h)
    long_edge = max(w, h)
    exceeds = [name for name, px, tok in READER_TIERS if long_edge > px or tokens > tok]
    if long_edge > MANY_IMAGE_SAFE_PX:
        exceeds.append("many-image")
    return {"width": w, "height": h, "tokens": tokens, "long_edge": long_edge,
            "exceeds": exceeds}


def png_size(head: bytes) -> tuple[int, int] | None:
    """(width, height) from a PNG file's first 24 bytes, or None if not a PNG."""
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return None
    w, h = int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
    return (w, h) if w > 0 and h > 0 else None


# --------------------------------------------------------------------------- #
# exact frame times and file names
#
# A frame's time is pts x time_base, exact as a Fraction. Comparisons (which
# frame is on screen at T, which frames fall in a range) use that exact value;
# integer milliseconds are rounded and serve only as names and labels.

_DECIMAL = re.compile(r"\d+(?:\.\d+)?")


def seconds_exact(text: str) -> Fraction:
    """A non-negative decimal number of seconds, exactly ("0.033" -> 33/1000)."""
    text = text.strip()
    if not _DECIMAL.fullmatch(text):
        raise ValueError(f"not a non-negative decimal number of seconds: {text!r}")
    return Fraction(text)


def ms_round(t: Fraction) -> int:
    """Nearest integer millisecond, halves rounded up. ValueError when negative."""
    if t < 0:
        raise ValueError(f"negative time {float(t):.6f} s")
    return math.floor(t * 1000 + Fraction(1, 2))


def pts_ms(pts: int, tb: Fraction) -> int:
    return ms_round(pts * tb)


def time_ms(t: float) -> int:
    """The milliseconds that f"{t:.3f}" prints (the bug/anim file-name time)."""
    s = f"{t:.3f}"
    sign = -1 if s.startswith("-") else 1
    whole, frac = s.lstrip("-").split(".")
    return sign * (int(whole) * 1000 + int(frac))


def frames_name(ms: int) -> str:
    return f"t{ms:08d}.png"


def bug_frame_name(k: int, t: float) -> str:
    return f"{k:02d}_{t:.3f}s.png"


def anim_frame_name(i: int, t: float) -> str:
    return f"f{i:03d}_{t:.3f}s.png"


IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")


@dataclass(frozen=True)
class FrameName:
    ms: int                 # integer milliseconds carried by the name (rounded)
    form: str               # "frames" (t<ms>), "bug" (NN_<s>s), "anim" (fNNN_<s>s)
    index: int | None       # the bug pick number / anim frame index
    suffix: str = ""        # text after the canonical name (allow_suffix only)


_NAME_FORMS = (
    ("frames", r"t(\d{8,})"),
    ("bug", r"(\d{2,})_(\d+)\.(\d{3})s"),
    ("anim", r"f(\d{3,})_(\d+)\.(\d{3})s"),
)
_SUFFIX = r"(?P<sfx>[-_ .(].*)?"
_NAME_RX = {False: [(f, re.compile(rx)) for f, rx in _NAME_FORMS],
            True: [(f, re.compile(rx + _SUFFIX, re.S)) for f, rx in _NAME_FORMS]}


def parse_frame_name(name: str, *, allow_suffix: bool = False) -> FrameName | None:
    """The time a frame file name carries, or None when the name carries none.

    Accepts exactly the names this helper writes (t00007040.png, 04_5.500s.png,
    f013_0.483s.png) with a png/jpg/jpeg/webp extension; anything else is
    rejected rather than guessed at. With allow_suffix, such a name may go on
    after a separator (_ - . space or '('), as an editor's "save as" leaves it:
    t00007040_annotated.png, f013_0.483s (1).png."""
    stem, dot, ext = name.rpartition(".")
    if not dot or f".{ext.lower()}" not in IMAGE_EXTS:
        return None
    for form, rx in _NAME_RX[allow_suffix]:
        m = rx.fullmatch(stem)
        if not m:
            continue
        sfx = (m.groupdict().get("sfx") or "")
        if form == "frames":
            return FrameName(int(m.group(1)), form, None, sfx)
        return FrameName(int(m.group(2)) * 1000 + int(m.group(3)), form, int(m.group(1)), sfx)
    return None


# --------------------------------------------------------------------------- #
# sheet mode: any folder of images, ordered by the time in their names

_DIGITS = re.compile(r"(\d+)")


def natural_key(name: str) -> tuple:
    """Digit-aware sort key: b2 before b10. Ties fall back to the plain name."""
    parts = _DIGITS.split(name)
    return (tuple((0, int(p), "") if i % 2 else (1, 0, p) for i, p in enumerate(parts)), name)


@dataclass(frozen=True)
class SheetItem:
    name: str
    order: int                  # 1-based position on the sheets
    ms: int | None              # time from the name; None = the name carries none
    form: str | None            # frames / bug / anim, None when untimed
    suffix: str
    delta_ms: int | None        # ms since the previous timed image; None for the first


@dataclass
class SheetPlan:
    items: list[SheetItem]
    untimed: list[str]
    forms: list[str]
    gaps: list[SheetItem]       # heuristic: delta > GAP_FACTOR x the median delta
    median_delta_ms: float | None


GAP_FACTOR = 1.5


def plan_sheet(names: list[str]) -> SheetPlan:
    """Order images for contact sheets: those whose names carry a time first, by
    time (ties by natural name order), then the rest by natural name order with
    no time. delta_ms is from the previous timed image, from the rounded ms the
    names carry (so +-1 ms)."""
    timed, untimed = [], []
    for n in names:
        fn = parse_frame_name(n, allow_suffix=True)
        (timed if fn else untimed).append((n, fn))
    timed.sort(key=lambda r: (r[1].ms, natural_key(r[0])))
    untimed.sort(key=lambda r: natural_key(r[0]))
    items, prev = [], None
    for n, fn in timed:
        items.append(SheetItem(n, len(items) + 1, fn.ms, fn.form, fn.suffix,
                               None if prev is None else fn.ms - prev))
        prev = fn.ms
    for n, _ in untimed:
        items.append(SheetItem(n, len(items) + 1, None, None, "", None))
    deltas = [it.delta_ms for it in items if it.delta_ms]
    median = statistics.median(deltas) if deltas else None
    gaps = ([it for it in items if it.delta_ms is not None and it.delta_ms > GAP_FACTOR * median]
            if median is not None and len(timed) >= 3 else [])
    return SheetPlan(items, [n for n, _ in untimed],
                     sorted({fn.form for _, fn in timed}), gaps, median)


def im_label(text: str) -> str:
    """Text for ImageMagick's -label / label:, shown literally: IM expands
    %-escapes and a backslash-n in it."""
    return text.replace("\\", "\\\\").replace("%", "%%")


def truncate_middle(text: str, n: int) -> str:
    """At most n characters, keeping the head and the tail around '...'."""
    if len(text) <= n:
        return text
    if n <= 3:
        return text[:n]
    keep = n - 3
    head = (keep + 1) // 2
    tail = keep - head
    return text[:head] + "..." + (text[-tail:] if tail else "")


MIN_TILE_PX = 64     # a tile's image keeps at least this long edge (tiny originals: 4x theirs)
MAX_ENLARGE = 4.0    # the enlargement cap of every sheet layout


def label_safe_layout(n: int, w: int, h: int, need_w: int, max_edge: int,
                      label_h: int = 40, border: int = 8):
    """(cols, cell_w, th, scale) for n tiles of a w x h box on one sheet, with
    every cell at least need_w wide so its label fits, or None when no column
    count fits. Cells wider than the image letterbox it."""
    floor_px = min(MIN_TILE_PX, MAX_ENLARGE * max(w, h))
    best = None
    for cols in range(1, n + 1):
        if cols * (need_w + border) > max_edge:
            break
        rows = math.ceil(n / cols)
        s = min((max_edge - border * cols) / (cols * w),
                (max_edge - (label_h + border) * rows) / (rows * h), MAX_ENLARGE)
        if s <= 0:
            continue
        iw, th = max(1, int(w * s)), max(1, int(h * s))
        cell_w = max(need_w, iw)
        if (s * max(w, h) + 1e-9 < floor_px or cols * (cell_w + border) > max_edge
                or rows * (th + label_h + border) > max_edge):
            continue
        if best is None or s > best[3] + 1e-9:
            best = (cols, cell_w, th, s)
    return best


def sheet_capacity_bound(need_w: int, max_edge: int, label_h: int = 40,
                         border: int = 8) -> int:
    """No sheet holds more tiles than this, whatever their size: each column is at
    least need_w + border wide, each row at least 1 + label_h + border high."""
    return max(1, (max_edge // (need_w + border)) * (max_edge // (1 + label_h + border)))


def chunk_sheets(boxes: list[tuple[int, int]], per_sheet: int, need_w, max_edge: int,
                 label_h: int = 40) -> list[tuple[int, int, bool, tuple]]:
    """Split tiles into sheets of at most per_sheet, fewer where labels and the
    sheet size would not fit. Returns (start, count, reduced, layout) per sheet;
    reduced means the layout, not running out of tiles, cut the sheet short.
    need_w: the label width each tile needs (a list, one per box), or one int.

    Each sheet tries at most sheet_capacity_bound() tiles first (a larger count
    can never fit), and the running maxima of the candidate prefix are kept in
    arrays, so a rejected count costs one layout call and no rescan."""
    if per_sheet < 1:
        raise ValueError("per_sheet must be at least 1")
    needs = [need_w] * len(boxes) if isinstance(need_w, int) else list(need_w)
    if len(needs) != len(boxes):
        raise ValueError("need_w must give one width per box")
    out, i = [], 0
    while i < len(boxes):
        want = min(per_sheet, len(boxes) - i)
        top = min(want, sheet_capacity_bound(needs[i], max_edge, label_h))
        pw, ph, pn = [], [], []           # prefix maxima of width, height, label width
        for b, nw in zip(boxes[i:i + top], needs[i:i + top]):
            pw.append(max(b[0], pw[-1]) if pw else b[0])
            ph.append(max(b[1], ph[-1]) if ph else b[1])
            pn.append(max(nw, pn[-1]) if pn else nw)
        k = top
        while True:
            lay = label_safe_layout(k, pw[k - 1], ph[k - 1], pn[k - 1], max_edge, label_h)
            if lay is not None:
                break
            if k == 1:
                raise ValueError(f"a label {pn[0]} px wide does not fit a {max_edge} px sheet")
            k -= 1
        out.append((i, k, k < want, lay))
        i += k
    return out


def decimal_between(lo: Fraction, hi: Fraction, max_digits: int = 9) -> str | None:
    """The shortest decimal d (at least 3 places) with lo < d <= hi, as text, or
    None when no decimal with up to max_digits places fits. Used to restart a
    range strictly after one frame and no later than the next."""
    for k in range(3, max_digits + 1):
        scale = 10 ** k
        d = Fraction(math.floor(lo * scale) + 1, scale)
        if d <= hi:
            whole, frac = divmod(d.numerator * (scale // d.denominator), scale)
            return f"{whole}.{frac:0{k}d}"
    return None


def range_arg(t_lo: float, t_hi: float) -> str:
    """A --range START-END (ms precision) that contains both frame times: START
    rounded down, END one ms past t_hi rounded up (END is exclusive)."""
    a = math.floor(t_lo * 1000) / 1000
    b = (math.floor(t_hi * 1000) + 1) / 1000
    return f"{a:.3f}-{b:.3f}"


# --------------------------------------------------------------------------- #
# ffmpeg log parsing

_SHOWINFO = re.compile(
    r"\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:\s*(-?\d+(?:\.\d+)?(?:e[-+]?\d+)?)"
)
_SHOWINFO_TB = re.compile(r"\bconfig in time_base:\s*(\d+)/(\d+)")


def parse_showinfo(log: str) -> list[tuple[int, int, float]]:
    """(n, pts, pts_time) for every frame line printed by ffmpeg's showinfo filter."""
    frames = []
    for line in log.splitlines():
        if "showinfo" not in line:
            continue
        m = _SHOWINFO.search(line)
        if m:
            frames.append((int(m.group(1)), int(m.group(2)), float(m.group(3))))
    return frames


_SHOWINFO_TAG = re.compile(r"^\[Parsed_showinfo_(\d+) @")
_SHOWINFO_SIZE = re.compile(r"\bs:(\d+)x(\d+)\b")
_SHOWINFO_DUR = re.compile(r"\bduration:\s*(-?\d+)\b")
_SHOWINFO_FMT = re.compile(r"\bfmt:(\w+)")


@dataclass(frozen=True)
class ShowinfoFrame:
    instance: int | None          # N of "Parsed_showinfo_N": which showinfo in the chain
    pts: int
    pts_time: str                 # as printed, for exact arithmetic
    size: tuple[int, int] | None  # the frame's size where this showinfo sits
    duration: int | None          # frame duration in the time base, when reported
    fmt: str | None = None        # the frame's pixel format where this showinfo sits


def parse_showinfo_frames(log: str) -> list[ShowinfoFrame]:
    """Every showinfo frame line with its instance, pts, printed pts_time, frame
    size and duration. With two showinfo filters in one chain the instance number
    tells them apart (the lower one sits earlier in the chain)."""
    out = []
    for line in log.splitlines():
        if "showinfo" not in line:
            continue
        m = _SHOWINFO.search(line)
        if not m:
            continue
        tag = _SHOWINFO_TAG.search(line)
        size = _SHOWINFO_SIZE.search(line)
        dur = _SHOWINFO_DUR.search(line)
        fmt = _SHOWINFO_FMT.search(line)
        out.append(ShowinfoFrame(
            int(tag.group(1)) if tag else None, int(m.group(2)), m.group(3),
            (int(size.group(1)), int(size.group(2))) if size else None,
            int(dur.group(1)) if dur and int(dur.group(1)) > 0 else None,
            fmt.group(1) if fmt else None))
    return out


def count_showinfo_configs(log: str) -> int:
    """How many times a showinfo filter was configured: one "config in time_base"
    line per filter-graph configuration. The ffmpeg CLI rebuilds the graph when a
    decoded frame's properties change (size, pixel format, ...), which resets
    every stateful filter in it (mpdecimate, freezedetect, blackdetect)."""
    return sum(1 for line in log.splitlines()
               if "showinfo" in line and _SHOWINFO_TB.search(line))


def parse_showinfo_timebase(log: str) -> Fraction | None:
    """The input time base showinfo reports ("config in time_base: 1/15360"); None
    when it is absent or 0/0."""
    for line in log.splitlines():
        if "showinfo" not in line:
            continue
        m = _SHOWINFO_TB.search(line)
        if m:
            num, den = int(m.group(1)), int(m.group(2))
            return Fraction(num, den) if num and den else None
    return None


# --------------------------------------------------------------------------- #
# bug mode triage: freeze / black / silence intervals
#
# Evidence model. blackdetect, freezedetect and silencedetect put their keys on
# the frame (or audio frame) where a state starts or ends, and
# `metadata=mode=print` / `ametadata=mode=print` log those frames with their pts.
# An end is *observed* only when its key sits on a real frame: at EOF, or where
# --range cuts the stream, blackdetect and silencedetect still log an end line
# but attach no metadata (FFmpeg release/5.1 uninit paths), and freezedetect
# logs nothing. Such an interval is reported with end_observed=False and its end
# as a lower bound.

_NUM = r"-?\d+(?:\.\d+)?(?:e[-+]?\d+)?"
_META_HEAD = re.compile(rf"\bframe:\s*\d+\s+pts:\s*(-?\d+)\s+pts_time:\s*({_NUM})")
_META_KEY = re.compile(r"\]\s*(lavfi\.[\w.]+)=(.*)$")
_SILENCE_END_LOG = re.compile(rf"\bsilence_end:\s*({_NUM})")


def _tag(line: str) -> str:
    return line.split("]", 1)[0] if line.startswith("[") else ""


def parse_metadata_print(log: str) -> list[tuple[int, float, dict[str, str]]]:
    """(pts, pts_time, {key: raw value}) for each frame printed by ffmpeg's
    metadata=mode=print / ametadata=mode=print filters."""
    blocks: list[tuple[int, float, dict[str, str]]] = []
    for line in log.splitlines():
        if "metadata_" not in _tag(line):
            continue
        m = _META_HEAD.search(line)
        if m:
            blocks.append((int(m.group(1)), float(m.group(2)), {}))
            continue
        k = _META_KEY.search(line)
        if k and blocks:
            blocks[-1][2][k.group(1)] = k.group(2).strip()
    return blocks


@dataclass
class Interval:
    kind: str                  # freeze / black / silence
    start: float               # seconds, same timeline as showinfo
    end: float                 # observed end, or a lower bound when not end_observed
    end_observed: bool         # True only when the detector marked the end on a frame
    frame_pts: int | None = None   # black: the first black frame (detector-qualified)
    frame_t: float | None = None

    @property
    def duration(self) -> float:
        return self.end - self.start


def triage_intervals(video_log: str, audio_log: str, span_end: float, *,
                     black_min: float = 0.0) -> list[Interval]:
    """Freeze, black and silence intervals from the detector metadata.

    span_end is the end of the analysed video span: the lower bound for a freeze
    or black run still going when the span ended. A trailing silence takes the
    audio stream's own end (silencedetect's EOF log line) instead. Black runs
    shorter than black_min are dropped only when their end was observed; a run
    whose end was not observed is kept, since nothing proves it short.
    """
    out: list[Interval] = []
    black = None    # (t, pts) of the open black run's first frame
    freeze = None   # start time of the open freeze
    for pts, t, kv in parse_metadata_print(video_log):
        if "lavfi.black_end" in kv and black is not None:
            iv = Interval("black", black[0], t, True, black[1], black[0])
            if iv.duration >= black_min:
                out.append(iv)
            black = None
        if "lavfi.black_start" in kv and black is None:
            black = (t, pts)
        # freezedetect reports a freeze only once it has lasted d, so the frame that
        # first proves the duration can also be the one that ends it: both keys on
        # one frame. Open before closing.
        if "lavfi.freezedetect.freeze_start" in kv and freeze is None:
            freeze = float(kv["lavfi.freezedetect.freeze_start"])
        if "lavfi.freezedetect.freeze_end" in kv and freeze is not None:
            out.append(Interval("freeze", freeze,
                                float(kv["lavfi.freezedetect.freeze_end"]), True))
            freeze = None
    if black is not None:
        out.append(Interval("black", black[0], max(span_end, black[0]), False,
                            black[1], black[0]))
    if freeze is not None:
        out.append(Interval("freeze", freeze, max(span_end, freeze), False))

    silence = None
    observed_ends = set()
    for _, _, kv in parse_metadata_print(audio_log):
        # silencedetect walks samples: one audio frame can both reach d (start)
        # and hear the sound resume (end). Open before closing.
        if "lavfi.silence_start" in kv and silence is None:
            silence = float(kv["lavfi.silence_start"])
        if "lavfi.silence_end" in kv and silence is not None:
            observed_ends.add(kv["lavfi.silence_end"])
            out.append(Interval("silence", silence, float(kv["lavfi.silence_end"]), True))
            silence = None
    if silence is not None:
        # silencedetect closes a trailing silence at EOF with a log line only; its
        # value is the audio stream's end (byte-exact match keeps observed ends out)
        eof = [m.group(1) for line in audio_log.splitlines()
               if "silencedetect" in _tag(line)
               for m in [_SILENCE_END_LOG.search(line)] if m
               and m.group(1) not in observed_ends]
        end = float(eof[-1]) if eof else span_end
        out.append(Interval("silence", silence, max(end, silence), False))
    return sorted(out, key=lambda iv: (iv.start, iv.kind))


def _num_or_none(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None


def parse_packets(text: str) -> list[tuple[float | None, float | None]]:
    """(pts_time, duration_time) per packet from
    `ffprobe -show_entries packet=pts_time,duration_time -of compact=p=0`
    (lines like `pts_time=0.983333|duration_time=0.016667`); N/A becomes None."""
    out = []
    for line in text.splitlines():
        fields = dict(f.split("=", 1) for f in line.strip().split("|") if "=" in f)
        if "pts_time" not in fields:
            continue
        out.append((_num_or_none(fields["pts_time"]),
                    _num_or_none(fields.get("duration_time", "N/A"))))
    return out


@dataclass
class Span:
    end_t: float               # end used for dwell ("shown for") of the last kept frame
    interval_end: float        # lower bound for a freeze/black run still going at the end
    proven: bool               # both values are proven video coverage
    max_pts: float | None      # latest presentation time of a video packet (normalised)
    note: str = ""             # why the end is not proven


def _close(a: float, b: float) -> bool:
    # showinfo prints pts_time with 6 significant digits
    return abs(a - b) <= max(1e-3, 1e-5 * abs(b))


def video_span(packets, origin: float, *, range_end: float | None, ranged: bool,
               first_kept_t: float, last_kept_t: float, container_end: float) -> Span:
    """End of the analysed video span, on the detector's timeline.

    ffmpeg subtracts the input's format start_time (`origin`) before filtering, but
    ffprobe packet times are raw, so every packet pts is normalised first. Packets
    come in demux order, so coverage is taken at the packet with the latest
    presentation time: its pts + duration, proven only when that duration is known
    and every packet has a pts. --range ending before the last frame is proven by
    that later frame. The origin is confirmed against the first kept frame's
    showinfo time; when it cannot be, nothing derived from packets is used.
    """
    pts = [(None if p is None else p - origin, d) for p, d in packets]
    known = [(p, d) for p, d in pts if p is not None]
    container = container_end if range_end is None else min(container_end, range_end)
    origin_ok = bool(known) and any(_close(p, first_kept_t) for p, _ in known) and (
        ranged or _close(min(p for p, _ in known), first_kept_t))
    if not origin_ok:
        return Span(container, max(last_kept_t, first_kept_t), False, None,
                    "video timeline origin could not be confirmed")
    p_max, d_max = max(known, key=lambda pd: (pd[0], pd[1] or 0.0))
    if range_end is not None and range_end <= p_max:
        return Span(range_end, range_end, True, p_max)
    if len(known) == len(pts) and d_max and d_max > 0:
        cov = p_max + d_max
        end = cov if range_end is None else min(cov, range_end)
        return Span(end, end, True, p_max)
    why = ("a video packet has no timestamp" if len(known) < len(pts)
           else "the last frame's duration is unknown")
    return Span(container, p_max, False, p_max,
                f"video coverage after the last frame at {p_max:.3f} s not established ({why})")


# --------------------------------------------------------------------------- #
# bug mode: which frames are worth looking at

@dataclass
class Pick:
    index: int | None   # position in the kept-frame list; None for a frame mpdecimate
                        # dropped (added through a Mark, identified by `ref`)
    t: float            # pts_time, seconds
    dwell: float        # seconds, read according to dwell_basis
    reasons: list[str]  # start / state / motion / brief / black / end
    ref: object = None  # caller's handle (the pts) for a frame outside the kept list
    dwell_basis: str = "decimate"  # "decimate": until the next visible change;
                                   # "black run" / "black run, lower bound": blackdetect


@dataclass
class Mark:
    """A frame the caller wants picked for `reason`. With `index`, it is that kept
    frame; without, it is a frame mpdecimate dropped, whose duration the caller
    knows from other evidence (`dwell`, `dwell_basis`)."""
    t: float
    reason: str
    index: int | None = None
    ref: object = None
    dwell: float = 0.0
    dwell_basis: str = "decimate"


_PRIORITY = {"start": 4, "end": 4, "black": 3.5, "state": 3, "brief": 2, "motion": 1}


def dwell_times(times: list[float], end_t: float) -> list[float]:
    """How long each kept frame stayed on screen: the gap to the next kept frame.

    mpdecimate dropped the near-duplicates in between, so a long gap means the
    picture sat still for that long."""
    n = len(times)
    return [max(0.0, (times[i + 1] if i + 1 < n else end_t) - times[i]) for i in range(n)]


def select_key_frames(times, end_t, *, min_dwell=0.4, interval=1.0, brief_max=0.12,
                      max_frames=40, marks=()):
    """Pick the frames that summarise a recording, from mpdecimate's kept frames.

    - state:  dwell >= min_dwell, a screen that settled long enough to be seen
    - motion: inside a run of short-dwell frames (scrolling, long animations),
              one frame per `interval` seconds since the previous pick
    - brief:  a whole short-dwell run lasting <= brief_max (a flash, a glitch, a
              very quick transition) that interval sampling would step over
    - start / end: the first and last kept frame

    - marks:  extra picks requested by the caller (Mark), e.g. a black frame; a
              mark on a kept frame merges its reason, a mark without an index adds
              a frame mpdecimate dropped, with the caller's dwell

    Returns (picks, dropped) in time order; `dropped` counts picks removed to
    honour max_frames (motion samples go first, then briefs, then the
    shortest-lived states, then black frames; start and end go last).
    """
    n = len(times)
    if n == 0:
        return [], 0
    dwell = dwell_times(times, end_t)
    reasons: dict[int, list[str]] = {}

    def add(i, why):
        lst = reasons.setdefault(i, [])
        if why not in lst:
            lst.append(why)

    add(0, "start")
    last_pick_t = times[0]
    i = 0
    while i < n:
        if dwell[i] >= min_dwell:
            add(i, "state")
            last_pick_t = times[i]
            i += 1
            continue
        j = i
        while j + 1 < n and dwell[j + 1] < min_dwell:
            j += 1
        run_len = times[j] + dwell[j] - times[i]
        if run_len <= brief_max:
            add(i, "brief")
            last_pick_t = times[i]
        else:
            # count the interval from the start of the run, so an ordinary
            # transition out of a long-lived state is not sampled
            last_pick_t = times[i]
            for k in range(i + 1, j + 1):
                if times[k] - last_pick_t >= interval:
                    add(k, "motion")
                    last_pick_t = times[k]
        i = j + 1
    add(n - 1, "end")

    extra = []
    for m in marks:
        if m.index is not None:
            add(m.index, m.reason)
        else:
            extra.append(Pick(None, m.t, m.dwell, [m.reason], m.ref, m.dwell_basis))
    picks = [Pick(k, times[k], dwell[k], reasons[k]) for k in sorted(reasons)]
    picks = sorted(picks + extra, key=lambda p: p.t)   # stable: kept frame first on ties
    if len(picks) <= max_frames:
        return picks, 0
    ranked = sorted(picks, key=lambda p: (max(_PRIORITY[r] for r in p.reasons), p.dwell),
                    reverse=True)
    keep = sorted(ranked[:max_frames], key=lambda p: p.t)
    return keep, len(picks) - len(keep)


# --------------------------------------------------------------------------- #
# anim mode: where does something move

def motion_segments(times: list[float], gap_max: float) -> list[tuple[int, int]]:
    """Group kept-frame timestamps into runs of continuous change.

    times[0] is the opening picture. A segment starts at the first kept frame
    after a pause longer than gap_max and ends at the last kept frame before the
    next such pause. Returns (first, last) index pairs; first == 0 means the
    video started mid-motion, so there is no still picture before it.
    """
    segs = []
    n = len(times)
    i = 1
    while i < n:
        j = i
        while j + 1 < n and times[j + 1] - times[j] <= gap_max:
            j += 1
        first = 0 if (i == 1 and times[1] - times[0] <= gap_max) else i
        segs.append((first, j))
        i = j + 1
    return segs


@dataclass
class Diff:
    mad: float                 # mean absolute difference over all pixels, 0..255
    maxd: int                  # largest single-pixel difference
    count: int                 # pixels differing by more than the threshold
    bbox: tuple | None         # (x0, y0, x1, y1) inclusive, of those pixels


def diff_stats(a: bytes, b: bytes, w: int, h: int, thr: int) -> Diff:
    """Compare two w*h grayscale frames."""
    total = 0
    maxd = 0
    count = 0
    x0, x1, y0, y1 = w, -1, -1, -1
    for y in range(h):
        s = y * w
        ra = a[s:s + w]
        rb = b[s:s + w]
        if ra == rb:
            continue
        d = [p - q if p > q else q - p for p, q in zip(ra, rb)]
        total += sum(d)
        m = max(d)
        if m > maxd:
            maxd = m
        if m <= thr:
            continue
        hits = [k for k, v in enumerate(d) if v > thr]
        count += len(hits)
        if y0 < 0:
            y0 = y
        y1 = y
        if hits[0] < x0:
            x0 = hits[0]
        if hits[-1] > x1:
            x1 = hits[-1]
    return Diff(total / (w * h), maxd, count, (x0, y0, x1, y1) if y0 >= 0 else None)


@dataclass
class EdgeTrack:
    axis: str              # "x" or "y"
    kind: str              # edge+ / edge- / grow / shrink
    magnitude: float       # travel (edge±) or size change (grow/shrink), analysis px
    progress: list         # per frame: 0 = start picture, 1 = end picture
    spread: float | None   # edge± only: 80th-percentile deviation of the per-frame
                           # travel estimate, relative to the travel (~0 = one rigid element)
    exact: bool            # False for grow/shrink (anchored on the first/last moving frame)


def edge_tracks(bS: list, bE: list, bSE: tuple | None, w: int, h: int) -> list[EdgeTrack]:
    """Progress along each axis, read off the change bounding boxes.

    bS[i] / bE[i]: bbox of where frame i differs from the start / end picture
    (None when identical); bSE: start-vs-end bbox. For one rigid element moving
    over a static background, bS spans start..current position and bE spans
    current..end, so one edge of bS stays put while the opposite one leads; the
    leading edge's distance to its final position, over the total travel, is the
    progress (overshoot included). The derivation is in
    .claude/skills/aitask-screen-recording/references/animation.md.
    """
    if bSE is None:
        return []
    mid = [i for i in range(len(bS)) if bS[i] is not None and bE[i] is not None]
    if len(mid) < 2:
        return []
    tracks = []
    for axis, lo, hi, size in (("x", 0, 2, w), ("y", 1, 3, h)):
        tol = max(2.0, 0.01 * size)
        loS = [bS[i][lo] for i in mid]
        hiS = [bS[i][hi] for i in mid]
        loE = [bE[i][lo] for i in mid]
        hiE = [bE[i][hi] for i in mid]

        def varies(s):
            return max(s) - min(s) > tol

        spread = None
        exact = True
        if varies(hiS) and not varies(loS):
            sums = [(le - ls) + (he - hs) for ls, hs, le, he in zip(loS, hiS, loE, hiE)]
            travel = statistics.median(sums)
            if travel <= tol:
                continue
            end = bSE[hi]
            p_mid = [1 + (v - end) / travel for v in hiS]
            kind, magnitude = "edge+", travel
            spread = _robust_spread(sums, travel)
        elif varies(loS) and not varies(hiS):
            sums = [(ls - le) + (hs - he) for ls, hs, le, he in zip(loS, hiS, loE, hiE)]
            travel = statistics.median(sums)
            if travel <= tol:
                continue
            end = bSE[lo]
            p_mid = [1 + (end - v) / travel for v in loS]
            kind, magnitude = "edge-", travel
            spread = _robust_spread(sums, travel)
        elif varies(loS) and varies(hiS):
            sizes = [b - a for a, b in zip(loS, hiS)]
            final, first = bSE[hi] - bSE[lo], sizes[0]
            if final - first <= tol:
                continue
            p_mid = [(s - first) / (final - first) for s in sizes]
            kind, magnitude, exact = "grow", final - first, False
        elif varies(loE) and varies(hiE):
            sizes = [b - a for a, b in zip(loE, hiE)]
            start, last = bSE[hi] - bSE[lo], sizes[-1]
            if start - last <= tol:
                continue
            p_mid = [(start - s) / (start - last) for s in sizes]
            kind, magnitude, exact = "shrink", start - last, False
        else:
            continue
        it = iter(p_mid)
        progress = []
        for i in range(len(bS)):
            if bS[i] is None:
                progress.append(0.0)
            elif bE[i] is None:
                progress.append(1.0)
            else:
                progress.append(next(it))
        tracks.append(EdgeTrack(axis, kind, float(magnitude), progress, spread, exact))
    return sorted(tracks, key=lambda tr: tr.magnitude, reverse=True)


def _robust_spread(sums, travel):
    """How far the per-frame travel estimates stray from the median, ignoring the
    worst 20 %: frames within a pixel of the end position differ from it only by an
    anti-aliased sliver, which makes their own estimate meaningless."""
    dev = sorted(abs(v - travel) for v in sums)
    return dev[int(0.8 * (len(dev) - 1))] / travel


# --------------------------------------------------------------------------- #
# easing models

class CubicBezier:
    """CSS-style cubic-bezier(x1, y1, x2, y2) easing, evaluated via a lookup table."""

    def __init__(self, x1, y1, x2, y2, samples=512):
        if not (0.0 <= x1 <= 1.0 and 0.0 <= x2 <= 1.0):
            raise ValueError("cubic-bezier x control points must lie in [0, 1]")
        self.params = (x1, y1, x2, y2)
        xs, ys = [], []
        for k in range(samples + 1):
            u = k / samples
            a = 3 * (1 - u) * (1 - u) * u
            b = 3 * (1 - u) * u * u
            c = u * u * u
            xs.append(a * x1 + b * x2 + c)
            ys.append(a * y1 + b * y2 + c)
        self._xs, self._ys = xs, ys

    def __call__(self, x: float) -> float:
        if x <= 0.0:
            return 0.0
        if x >= 1.0:
            return 1.0
        xs = self._xs
        k = bisect.bisect_left(xs, x)
        xa, xb = xs[k - 1], xs[k]
        ya, yb = self._ys[k - 1], self._ys[k]
        if xb == xa:
            return yb
        return ya + (yb - ya) * (x - xa) / (xb - xa)


# Named curves an implementation is likely to use. Compose and Material names are
# what you would type in code; CSS names double as the iOS/CA defaults.
NAMED_TWEENS = [
    ("linear", (0.0, 0.0, 1.0, 1.0)),
    ("CSS ease / CA default", (0.25, 0.1, 0.25, 1.0)),
    ("CSS ease-in", (0.42, 0.0, 1.0, 1.0)),
    ("CSS ease-out", (0.0, 0.0, 0.58, 1.0)),
    ("CSS ease-in-out / iOS easeInOut", (0.42, 0.0, 0.58, 1.0)),
    ("FastOutSlowIn (Compose tween default, M2 standard)", (0.4, 0.0, 0.2, 1.0)),
    ("LinearOutSlowIn (M2 decelerate)", (0.0, 0.0, 0.2, 1.0)),
    ("FastOutLinearIn (M2 accelerate)", (0.4, 0.0, 1.0, 1.0)),
    ("M3 standard", (0.2, 0.0, 0.0, 1.0)),
    ("M3 standard decelerate", (0.0, 0.0, 0.0, 1.0)),
    ("M3 standard accelerate", (0.3, 0.0, 1.0, 1.0)),
    ("M3 emphasized decelerate", (0.05, 0.7, 0.1, 1.0)),
    ("M3 emphasized accelerate", (0.3, 0.0, 0.8, 0.15)),
]

COMPOSE_STIFFNESS = [("StiffnessVeryLow", 50.0), ("StiffnessLow", 200.0),
                     ("StiffnessMediumLow", 400.0), ("StiffnessMedium", 1500.0),
                     ("StiffnessHigh", 10000.0)]
COMPOSE_DAMPING = [("DampingRatioHighBouncy", 0.2), ("DampingRatioMediumBouncy", 0.5),
                   ("DampingRatioLowBouncy", 0.75), ("DampingRatioNoBouncy", 1.0)]


def spring(t: float, stiffness: float, damping: float) -> float:
    """Unit-mass spring from 0 to 1 with zero initial velocity (Compose semantics)."""
    if t <= 0.0:
        return 0.0
    w0 = math.sqrt(stiffness)
    z = damping
    if z < 1.0 - 1e-9:
        wd = w0 * math.sqrt(1.0 - z * z)
        return 1.0 - math.exp(-z * w0 * t) * (math.cos(wd * t) + z * w0 / wd * math.sin(wd * t))
    if z <= 1.0 + 1e-9:
        return 1.0 - math.exp(-w0 * t) * (1.0 + w0 * t)
    s = math.sqrt(z * z - 1.0)
    r1, r2 = -w0 * (z - s), -w0 * (z + s)
    return 1.0 - (r2 * math.exp(r1 * t) - r1 * math.exp(r2 * t)) / (r2 - r1)


def spring_settle_time(stiffness: float, damping: float, tol: float = 0.01) -> float:
    """Time after which the spring stays within `tol` of its target."""
    w0 = math.sqrt(stiffness)
    horizon = max(0.05, 12.0 / (min(damping, 1.0) * w0))
    step = horizon / 4000
    last_out = 0.0
    t = 0.0
    while t <= horizon:
        if abs(spring(t, stiffness, damping) - 1.0) > tol:
            last_out = t
        t += step
    return last_out + step


def nearest_compose_spring(stiffness: float, damping: float) -> str:
    sname, sval = min(COMPOSE_STIFFNESS, key=lambda kv: abs(math.log(stiffness / kv[1])))
    dname, dval = min(COMPOSE_DAMPING, key=lambda kv: abs(damping - kv[1]))
    near_s = abs(math.log(stiffness / sval)) <= math.log(1.35)
    near_d = abs(damping - dval) <= 0.08
    s_txt = f"Spring.{sname}" if near_s else f"{stiffness:.0f}f"
    d_txt = f"Spring.{dname}" if near_d else f"{damping:.2f}f"
    return f"spring(dampingRatio = {d_txt}, stiffness = {s_txt})"


# --------------------------------------------------------------------------- #
# fitting

@dataclass
class Fit:
    family: str           # "tween" or "spring"
    name: str             # named preset, "custom cubic-bezier" or "spring"
    params: tuple         # tween: (x1, y1, x2, y2); spring: (stiffness, damping_ratio)
    t0: float             # fitted start time, seconds (recording clock)
    duration: float       # tween: T; spring: time until it stays within 1 % of the end
    rmse: float           # over the fitted frames, in progress units
    extra: dict = field(default_factory=dict)


def _sse_tween(ts, ps, f, t0, T):
    inv = 1.0 / T
    s = 0.0
    for t, p in zip(ts, ps):
        x = (t - t0) * inv
        m = 0.0 if x <= 0.0 else (1.0 if x >= 1.0 else f(x))
        d = m - p
        s += d * d
    return s


def _sse_spring(ts, ps, k, z, t0):
    s = 0.0
    for t, p in zip(ts, ps):
        d = spring(t - t0, k, z) - p
        s += d * d
    return s


def _pattern_search(fn, x0, steps, lower, upper, min_scale=1 / 32, max_evals=1500):
    """Derivative-free coordinate search; shrinks the step when nothing improves."""
    x = list(x0)
    best = fn(x)
    scale = 1.0
    evals = 0
    while scale >= min_scale and evals < max_evals:
        improved = False
        for k in range(len(x)):
            for sgn in (1.0, -1.0):
                y = list(x)
                y[k] = min(upper[k], max(lower[k], y[k] + sgn * steps[k] * scale))
                if y[k] == x[k]:
                    continue
                v = fn(y)
                evals += 1
                if v < best:
                    best, x, improved = v, y, True
        if not improved:
            scale *= 0.5
    return x, best


# how far before the first changed frame fit_motion looks for the motion's onset,
# in frame intervals; fit_onset_reachable tells callers when that is not enough
ONSET_SEARCH_INTERVALS = 8


def fit_onset_reachable(t_prev: float, t_first: float, dt: float) -> bool:
    """Whether fit_motion's onset search reaches back to t_prev, the last frame
    known to show the start picture. When it does not (frames missing before the
    motion), the motion may have begun before anything the fitter can place it at,
    and the fitted durations may come out short with a low rmse."""
    return t_first - t_prev <= ONSET_SEARCH_INTERVALS * dt + 1e-9


def fit_motion(ts, ps, *, t_first, t_settled, dt, families=("tween", "spring")):
    """Fit named tweens, a free cubic-bezier and a spring to progress samples.

    ts/ps: frame times and progress (0 = start picture, 1 = end picture), including
    a few still frames on each side so the start time and the end are anchored.
    t_first: first frame that differs from the start picture (the animation began
    within one frame interval `dt` before it). t_settled: first frame equal to the
    end picture. Returns fits sorted by RMSE.
    """
    n = len(ts)
    if n < 3:
        return []
    t_vis = max(dt, t_settled - (t_first - dt))
    t0_grid = [t_first - dt * j / 4 for j in range(1, 25)]           # 6 frames back
    T_grid = [t_vis * (0.6 + 1.9 * j / 49) for j in range(50)]       # 0.6x .. 2.5x
    t0_lo, t0_hi = t_first - ONSET_SEARCH_INTERVALS * dt, t_first
    T_lo, T_hi = max(dt / 2, 0.3 * t_vis), 3.0 * t_vis

    def rmse(sse):
        return math.sqrt(sse / n)

    fits: list[Fit] = []
    if "tween" in families:
        for name, cp in NAMED_TWEENS:
            f = CubicBezier(*cp)
            best = min((_sse_tween(ts, ps, f, t0, T), t0, T) for t0 in t0_grid for T in T_grid)
            (t0, T), sse = _pattern_search(
                lambda v: _sse_tween(ts, ps, f, v[0], v[1]),
                [best[1], best[2]], [dt / 4, dt / 2], [t0_lo, T_lo], [t0_hi, T_hi])
            fits.append(Fit("tween", name, cp, t0, T, rmse(sse)))
        seed = min(fits, key=lambda f_: f_.rmse)

        def custom_sse(v):
            return _sse_tween(ts, ps, CubicBezier(v[0], v[1], v[2], v[3], samples=256), v[4], v[5])

        v, sse = _pattern_search(
            custom_sse, [*seed.params, seed.t0, seed.duration],
            [0.1, 0.1, 0.1, 0.1, dt / 2, dt],
            [0.0, -1.0, 0.0, -1.0, t0_lo, T_lo], [1.0, 2.0, 1.0, 2.0, t0_hi, T_hi],
            max_evals=900)
        cp = tuple(round(c, 3) for c in v[:4])
        fits.append(Fit("tween", "custom cubic-bezier", cp, v[4], v[5], rmse(sse)))

    if "spring" in families:
        ks = [15.0 * (2000.0 ** (j / 44)) for j in range(45)]           # 15 .. 30000
        zs = [0.1 + 0.05 * j for j in range(29)]                        # 0.10 .. 1.50
        t0s = [t_first - dt * j / 4 for j in range(1, 17)]
        best = min((_sse_spring(ts, ps, k, z, t0), k, z, t0)
                   for k in ks for z in zs for t0 in t0s)
        (k, z, t0), sse = _pattern_search(
            lambda v: _sse_spring(ts, ps, v[0], v[1], v[2]),
            [best[1], best[2], best[3]], [best[1] * 0.15, 0.05, dt / 4],
            [5.0, 0.05, t0_lo], [60000.0, 3.0, t0_hi])
        fits.append(Fit("spring", "spring", (round(k, 1), round(z, 3)), t0,
                        spring_settle_time(k, z), rmse(sse),
                        {"compose": nearest_compose_spring(k, z),
                         "swiftui_response_s": round(2 * math.pi / math.sqrt(k), 3)}))
    return sorted(fits, key=lambda f_: f_.rmse)


def scale_fit_time(fit: Fit, time_scale: float) -> Fit:
    """Convert a fit measured on a slowed-down recording back to real time.

    Recording with animator duration scale s stretches time by s: tween durations
    divide by s and spring stiffness multiplies by s^2 (omega scales by s)."""
    if time_scale == 1.0:
        return fit
    if fit.family == "tween":
        return Fit(fit.family, fit.name, fit.params, fit.t0, fit.duration / time_scale,
                   fit.rmse, dict(fit.extra))
    k, z = fit.params
    k2 = k * time_scale * time_scale
    extra = dict(fit.extra)
    extra["compose"] = nearest_compose_spring(k2, z)
    extra["swiftui_response_s"] = round(2 * math.pi / math.sqrt(k2), 3)
    return Fit(fit.family, fit.name, (round(k2, 1), z), fit.t0, fit.duration / time_scale,
               fit.rmse, extra)


# --------------------------------------------------------------------------- #
# per-segment analysis

def analysis_threshold(maxd: int) -> int:
    """Per-pixel change threshold: 30 % of the strongest start-vs-end contrast,
    clamped so compression noise stays below it and faint elements stay above it."""
    return int(min(40, max(8, round(0.3 * maxd))))


def analyze_frames(times, frames, w, h, *, signal="auto", nominal_dt=1 / 60,
                   frame_interval: float | None = None):
    """Measure one motion window. frames[0] must be the still picture before the
    motion and frames[-1] the settled picture after it.

    Returns a dict with per-frame measurements, the chosen progress signal,
    visible timing and fits; see video_prep.py for how it is reported.

    frame_interval: the native frame interval when the caller knows it better
    than the window's own median (an image folder with frames missing); None
    measures it from the window, as for a video.
    """
    n = len(frames)
    S, E = frames[0], frames[-1]
    probe = diff_stats(S, E, w, h, 255)
    thr = analysis_threshold(probe.maxd) if probe.maxd else 8
    se = diff_stats(S, E, w, h, thr)
    ms = [diff_stats(f, S, w, h, thr) for f in frames]
    me = [diff_stats(f, E, w, h, thr) for f in frames]
    out = {"threshold": thr, "n_frames": n, "warnings": [],
           "mad_s": [m.mad for m in ms], "mad_e": [m.mad for m in me],
           "bbox_s": [m.bbox for m in ms], "bbox_e": [m.bbox for m in me]}

    moving = [i for i in range(n) if ms[i].count > 0 or (se.mad and ms[i].mad / se.mad > 0.02)]
    if not moving:
        out.update(kind="still", signal=None, progress=None, fits=[])
        return out
    fm = moving[0]

    if se.count == 0:
        # Ends where it started: press feedback, a shake, a ripple. No progress curve.
        lm = max(i for i in range(n) if ms[i].count > 0) if any(m.count for m in ms) else fm
        dt = frame_interval or _frame_interval(times, fm, lm + 1 if lm + 1 < n else lm,
                                               nominal_dt)
        out.update(kind="returns", signal=None, progress=None, fits=[], first_moving=fm,
                   last_moving=lm, frame_interval=dt,
                   visible_duration=(times[min(lm + 1, n - 1)] - (times[fm] - dt)))
        out["warnings"].append("the picture returns to where it started (press feedback, "
                               "shake, ripple?): no progress curve, read the sheet")
        return out

    lm = max(i for i in range(n) if me[i].count > 0 or me[i].mad / se.mad > 0.02)
    lm = min(lm, n - 2)
    dt = frame_interval or _frame_interval(times, fm, lm + 1, nominal_dt)
    p_blend = [1.0 - m.mad / se.mad for m in me]
    tracks = edge_tracks(out["bbox_s"], out["bbox_e"], se.bbox, w, h)
    track = tracks[0] if tracks else None

    if signal == "blend" or (signal == "auto" and (
            track is None or (track.spread is not None and track.spread > 0.25))):
        chosen, progress = "blend", p_blend
    else:
        if track is None:
            out["warnings"].append("no edge motion found; falling back to the blend signal")
            chosen, progress = "blend", p_blend
        else:
            chosen, progress = "edge", track.progress

    if track is not None and track.spread is not None and track.spread > 0.1:
        out["warnings"].append(
            f"travel estimate varies by {track.spread:.0%} across frames: probably more than "
            "one moving thing, or a fade combined with the move; narrow it with --roi")
    if track is None and chosen == "blend" and se.bbox is not None:
        x0, y0, x1, y1 = se.bbox
        if (x1 - x0 + 1) * (y1 - y0 + 1) > 0.8 * w * h:
            out["warnings"].append(
                "the change covers almost the whole region (full-screen transition?): timing "
                "is reliable, the curve shape is only a proxy unless it is a cross-fade")

    lo, hi = max(0, fm - 6), min(n - 1, lm + 7)
    fits = fit_motion(times[lo:hi + 1], progress[lo:hi + 1],
                      t_first=times[fm], t_settled=times[lm + 1], dt=dt)
    out.update(
        kind=(track.kind + "-" + track.axis) if (track and chosen == "edge") else
        ("fade/blend" if chosen == "blend" else "edge"),
        signal=chosen, progress=progress, p_blend=p_blend,
        p_edge=track.progress if track else None, track=track, tracks=tracks,
        first_moving=fm, last_moving=lm, frame_interval=dt,
        visible_duration=times[lm + 1] - (times[fm] - dt),
        overshoot=max(0.0, max(progress) - 1.0),
        fits=fits, fit_range=(lo, hi))
    return out


def _frame_interval(times, a, b, nominal):
    gaps = [times[k + 1] - times[k] for k in range(a, b) if times[k + 1] > times[k]]
    gaps = [g for g in gaps if g < 0.1]
    return statistics.median(gaps) if gaps else nominal


# --------------------------------------------------------------------------- #
# image-folder input (bug DIR / anim DIR): order, timing and gaps of a curated
# sequence of images, fed to ffmpeg as one stream by video_prep.py

ALPHA_PIX_FMT_PREFIXES = ("rgba", "bgra", "argb", "abgr", "ya", "yuva", "gbrap")


def has_alpha(fmt: str | None) -> bool:
    """Whether an ffmpeg pixel format name carries alpha (pal8 may)."""
    return bool(fmt) and (fmt == "pal8" or fmt.startswith(ALPHA_PIX_FMT_PREFIXES))


@dataclass(frozen=True)
class SeqImage:
    name: str
    t: Fraction             # seconds, exact: the name's ms / 1000, or k / fps
    form: str | None        # frames / bug / anim, None when timed by --fps


@dataclass
class ImageSeqPlan:
    images: list[SeqImage]  # in presentation order
    source: str             # "filenames" | "fps"
    fps: Fraction | None
    forms: list[str]


def plan_image_sequence(names: list[str], fps: Fraction | None = None) -> ImageSeqPlan:
    """Order and time a folder's images, or raise ValueError saying why not.

    Without fps every name must carry a time (parse_frame_name with
    allow_suffix, as `sheet` reads them, so an edited t00007040_note.png keeps its
    time); two images at one time are refused. With fps no name may carry a time
    (a time in a name is evidence that --fps would silently discard); the images
    are taken in natural name order at k / fps."""
    if len(names) < 2:
        raise ValueError(f"need at least 2 images, found {len(names)}")
    parsed = [(n, parse_frame_name(n, allow_suffix=True)) for n in names]
    timed = [(n, fn) for n, fn in parsed if fn is not None]
    untimed = sorted((n for n, fn in parsed if fn is None), key=natural_key)
    if fps is not None:
        if fps <= 0:
            raise ValueError("--fps must be a positive number")
        if timed:
            raise ValueError(
                f"--fps is only for images whose names carry no time, but {len(timed)} of "
                f"{len(names)} do (e.g. {timed[0][0]}); drop --fps to use their times")
        order = sorted(names, key=natural_key)
        return ImageSeqPlan([SeqImage(n, Fraction(k) / fps, None) for k, n in enumerate(order)],
                            "fps", fps, [])
    if not timed:
        raise ValueError("the image names carry no times (t<ms>.png, NN_<s>s.png or "
                         "fNNN_<s>s.png); give --fps N to time them in natural name order")
    if untimed:
        shown = ", ".join(untimed[:10]) + (", ..." if len(untimed) > 10 else "")
        raise ValueError(f"{len(untimed)} of {len(names)} image names carry no time: {shown}; "
                         "rename them like the others (t<ms>.png) or move them out")
    timed.sort(key=lambda r: (r[1].ms, natural_key(r[0])))
    for (a, fa), (b, fb) in zip(timed, timed[1:]):
        if fa.ms == fb.ms:
            raise ValueError(f"{a} and {b} carry the same time ({fa.ms} ms); keep one of them")
    return ImageSeqPlan([SeqImage(n, Fraction(fn.ms, 1000), fn.form) for n, fn in timed],
                        "filenames", None, sorted({fn.form for _, fn in timed}))


def base_interval(times) -> float | None:
    """The native frame interval of a sequence that may have frames missing.

    The lower quartile of the positive steps (the smallest one below 4 steps)
    finds the native cluster; the result is the mean of the steps in that cluster
    (those up to GAP_FACTOR x the quartile), so names rounded to whole ms (60 fps
    reads 16, 17, 17 ms) give 16.67 ms rather than 16. The median would not do:
    with every third frame deleted the steps alternate 1 and 2 frames, the median
    is 1.5 frames and a 2-frame step stays under 1.5 x it. Only a sequence where
    fewer than a quarter of the steps are native, such as one with every second
    frame deleted, reads as a slower native rate."""
    d = sorted(float(b - a) for a, b in zip(times, times[1:]) if b > a)
    if not d:
        return None
    q = d[0] if len(d) < 4 else statistics.quantiles(d, n=4, method="inclusive")[0]
    return statistics.fmean(x for x in d if x <= GAP_FACTOR * q)


@dataclass(frozen=True)
class Gap:
    index: int              # the image right after the gap
    at: float               # time of the image right before it, s
    delta: float            # the step across the gap, s
    est_missing: int        # about how many frames are missing


def sequence_gaps(times, base: float | None) -> list[Gap]:
    """Steps longer than GAP_FACTOR x the base interval (heuristic: frames were
    deleted, or the recorder emitted none while the screen was still)."""
    if not base:
        return []
    out = []
    for i in range(1, len(times)):
        d = float(times[i] - times[i - 1])
        if d > GAP_FACTOR * base:
            out.append(Gap(i, float(times[i - 1]), d, max(1, round(d / base) - 1)))
    return out


def concat_starts_us(times) -> list[int]:
    """Each image's start in integer microseconds, rounded from its exact time.
    The concat script's durations are differences of these, so the cumulative
    start of image k is exactly round(t_k), with no drift over a long sequence."""
    return [math.floor(Fraction(t) * 1_000_000 + Fraction(1, 2)) for t in times]
