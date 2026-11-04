"""Synthetic screen recordings with known ground truth, for the
test_screen_recording_*.py tests.

Frames are drawn in pure Python (8-bit grayscale, anti-aliased rectangles) and
encoded with ffmpeg/libx264, so the recordings carry real compression noise.
Times are exact: frame i is shown at i / FPS.
"""
from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".aitask-scripts"
                       / "screen_recording"))
from vp_core import CubicBezier, spring  # noqa: E402

W, H, FPS = 360, 800, 60
BG, FG = 245, 40

EASE_OUT = (0.0, 0.0, 0.58, 1.0)
EASE_IN_OUT = (0.42, 0.0, 0.58, 1.0)
FAST_OUT_SLOW_IN = (0.4, 0.0, 0.2, 1.0)
LINEAR = (0.0, 0.0, 1.0, 1.0)


class Canvas:
    def __init__(self, w=W, h=H, bg=BG):
        self.w, self.h = w, h
        self.buf = bytearray([bg]) * (w * h)

    def rect(self, x0, y0, x1, y1, val, alpha=1.0):
        """Fill [x0, x1) x [y0, y1) (floats) with `val`, blending partial pixels."""
        x0, y0 = max(0.0, x0), max(0.0, y0)
        x1, y1 = min(float(self.w), x1), min(float(self.h), y1)
        if x1 <= x0 or y1 <= y0 or alpha <= 0:
            return
        xa, xb = math.floor(x0), math.ceil(x1)
        covx = [min(x + 1, x1) - max(x, x0) for x in range(xa, xb)]
        # columns every row covers fully: filled directly when the row is opaque
        fa, fb = math.ceil(x0), math.floor(x1)
        solid = bytes([val]) * max(0, fb - fa)
        for y in range(math.floor(y0), math.ceil(y1)):
            cy = min(y + 1, y1) - max(y, y0)
            s = y * self.w + xa
            if alpha * cy == 1.0 and fb > fa:
                self.buf[y * self.w + fa:y * self.w + fb] = solid
                edges = [k for k in range(xa, xb) if not fa <= k < fb]
            else:
                edges = range(xa, xb)
            for k in edges:
                o = self.buf[y * self.w + k]
                self.buf[y * self.w + k] = int(round(o + (val - o) * alpha * covx[k - xa] * cy))

    def fill(self, val):
        self.buf[:] = bytes([val]) * (self.w * self.h)

    def bytes(self):
        return bytes(self.buf)


def encode(path, frames, *, w=W, h=H, fps=FPS, vfr=False, crf=18, ts_offset=None,
           x264_params=None):
    """Encode raw gray frames to H.264. vfr=True drops exact duplicates and keeps
    the original timestamps, like Android's screenrecord does for a still screen.
    ts_offset shifts every timestamp (a nonzero container start_time);
    x264_params is passed to -x264-params (e.g. B-frames that reorder packets)."""
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
           "-pix_fmt", "gray", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
    if vfr:
        cmd += ["-vf", "mpdecimate=hi=1:lo=1:frac=0", "-fps_mode", "vfr"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
            "-pix_fmt", "yuv420p"]
    if x264_params:
        cmd += ["-x264-params", x264_params]
    if ts_offset is not None:
        cmd += ["-output_ts_offset", str(ts_offset)]
    cmd += [str(path)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(f)
    p.stdin.close()
    if p.wait():
        raise RuntimeError(f"ffmpeg failed encoding {path}")
    return path


# --------------------------------------------------------------------------- #
# progress functions: t (s) -> progress

def tween(cp, t0, dur):
    f = CubicBezier(*cp)
    return lambda t: f((t - t0) / dur)


def spring_progress(k, z, t0):
    return lambda t: spring(t - t0, k, z)


def chain(*parts):
    """Run several (start, progress_fn) motions back to back: the value is the sum."""
    return lambda t: sum(fn(t) for fn in parts)


# --------------------------------------------------------------------------- #
# scenes

def card_frames(progress, total, mode, *, clock_ticks=(), fps=FPS):
    """One 120x120 card animated by `progress` (0..1, may overshoot).

    mode: right (x 40->200), left (x 200->40), down (y 200->400), fade (alpha 0->1),
    grow (centred square 40->120 px). clock_ticks: times at which a small "status
    bar clock" in the top 24 px changes, to test status-bar cropping.
    """
    frames = []
    for i in range(round(total * fps)):
        t = i / fps
        p = progress(t)
        c = Canvas()
        if mode == "right":
            x = 40 + 160 * p
            c.rect(x, 300, x + 120, 420, FG)
        elif mode == "left":
            x = 200 - 160 * p
            c.rect(x, 300, x + 120, 420, FG)
        elif mode == "down":
            y = 200 + 200 * p
            c.rect(120, y, 240, y + 120, FG)
        elif mode == "fade":
            c.rect(120, 300, 240, 420, FG, alpha=min(1.0, max(0.0, p)))
        elif mode == "grow":
            s = 40 + 80 * p
            c.rect(180 - s / 2, 360 - s / 2, 180 + s / 2, 360 + s / 2, FG)
        elif mode == "still":
            c.rect(120, 300, 240, 420, FG)
        else:
            raise ValueError(mode)
        ticks = sum(1 for tt in clock_ticks if t >= tt)
        c.rect(290, 4, 350, 20, 60 if ticks % 2 else 150)
        frames.append(c.bytes())
    return frames


def _screen(c, kind, xoff=0.0, scroll=0.0, checkbox=False):
    if kind == "A":
        for k in range(3):
            c.rect(20 + xoff, 100 + k * 120, 340 + xoff, 190 + k * 120, 200)
        c.rect(120 + xoff, 600, 240 + xoff, 660, 60)
        c.rect(0 + xoff, 0, 360 + xoff, 60, 90)
    else:  # B, scrollable list
        c.rect(0 + xoff, 0, 360 + xoff, 800, BG)
        for k in range(9):
            y = 90 + k * 100 - scroll
            c.rect(20 + xoff, y, 340 + xoff, y + 70, 150 + (k % 2) * 50)
            c.rect(30 + xoff, y + 10, 90 + xoff, y + 60, 70)
        c.rect(0 + xoff, 0, 360 + xoff, 60, 30)
        if checkbox:
            c.rect(310 + xoff, 720, 330 + xoff, 740, 20)


BUG_TIMELINE = {
    # expected picks: (time s, reasons) — see bug_frames()
    "picks": [(0.0, {"start", "state"}), (1.3, {"state"}), (3.517, {"motion"}),
              (4.5, {"state"}), (5.5, {"state"}), (6.5, {"brief"}), (6.517, {"state", "end"})],
}


def bug_frames(*, clock=False, fps=FPS):
    """A bug-report-like recording, 7.5 s:
    0-1.0 screen A; 1.0-1.3 push transition to B; 1.3-2.5 B still; 2.5-4.5 B scrolls
    300 px (linear); 4.5-5.5 still; 5.5 a 20 px checkbox fills; 6.5 a one-frame white
    flash; then still to the end. clock=True adds a status-bar clock ticking every 0.5 s.
    """
    push = CubicBezier(*FAST_OUT_SLOW_IN)
    frames = []
    for i in range(round(7.5 * fps)):
        t = i / fps
        c = Canvas()
        if abs(t - 6.5) < 0.5 / fps:
            c.fill(255)
        elif t < 1.0:
            _screen(c, "A")
        elif t < 1.3:
            p = push((t - 1.0) / 0.3)
            _screen(c, "A", xoff=-360 * p)
            _screen(c, "B", xoff=360 * (1 - p))
        else:
            scroll = 300 * min(1.0, max(0.0, (t - 2.5) / 2.0))
            _screen(c, "B", scroll=scroll, checkbox=t >= 5.5)
        if clock:
            c.rect(290, 4, 350, 20, 60 if int(t / 0.5) % 2 else 150)
        frames.append(c.bytes())
    return frames


# --------------------------------------------------------------------------- #
# bug-mode triage scenes (freeze / black / silence). A small bar moves 1 px per
# frame, so no span is still unless the scene freezes it on purpose.

def _bar(c, i):
    x = 20 + i % 300
    c.rect(x, 380, x + 20, 420, FG)


TRIAGE_TRUTH = {
    # (start s, end s) of each interval in triage_frames()
    "freeze": [(2.0, 4.5)],
    "black": [(5.0, 5.25), (6.0, 6.0 + 1 / FPS)],
}


def triage_frames(*, fps=FPS):
    """7 s: the moving bar, held on its t=2.0 picture for [2.0, 4.5) (a hang), a
    black span [5.0, 5.25) and a single black frame at 6.0."""
    frames = []
    for i in range(7 * fps):
        t = i / fps
        c = Canvas()
        if 5.0 <= t < 5.25 or i == 6 * fps:
            c.fill(0)
        else:
            _bar(c, 2 * fps if 2.0 <= t < 4.5 else i)
        frames.append(c.bytes())
    return frames


DARK_GRAY, DARK_BLACK = 27, 23   # full-range gray: Y ~39 (not black) / Y ~36 (black)


def dark_flash_frames(*, fps=FPS):
    """1 s of a flat dark-gray screen with one slightly darker frame at 0.5 s.
    blackdetect (pix_th 0.10: limited-range Y <= ~37) counts only that frame as
    black, while mpdecimate sees it as a duplicate of the frame before it and
    drops it: the nearest kept frame is the non-black one at t=0."""
    frames = []
    for i in range(fps):
        c = Canvas(bg=DARK_BLACK if i == fps // 2 else DARK_GRAY)
        frames.append(c.bytes())
    return frames


def tail_frames(*, recover, fps=FPS):
    """1 s: the moving bar, then black from 0.5 s. recover=False: black to the last
    frame (the run is cut by EOF); recover=True: the last frame shows the bar again
    (an observed end on the final frame)."""
    frames = []
    for i in range(fps):
        c = Canvas()
        if i >= fps // 2 and not (recover and i == fps - 1):
            c.fill(0)
        else:
            _bar(c, i)
        frames.append(c.bytes())
    return frames


def black_flash_frames(n=6, *, fps=FPS):
    """A still screen with n three-frame black flashes, at 0.5, 1.0, ... s. Each
    return to the screen stays up 0.45 s, a 'state' pick, so the black frames
    compete with states (not only with motion) for the --max-frames budget."""
    starts = {round(0.5 * k * fps) for k in range(1, n + 1)}
    frames = []
    for i in range(round(0.5 * (n + 1) * fps)):
        c = Canvas()
        if any(s <= i < s + 3 for s in starts):
            c.fill(0)
        else:
            _bar(c, 0)
        frames.append(c.bytes())
    return frames


def mux_tone(video, out, *, duration, silent=None, shortest=True):
    """Copy `video` and add a 440 Hz AAC tone of `duration` s, muted on the
    [a, b] span `silent` (sample-exact before encoding)."""
    expr = "sin(2*PI*440*t)"
    if silent:
        a, b = silent
        expr = f"if(between(t\\,{a}\\,{b})\\,0\\,{expr})"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
           "-f", "lavfi", "-i", f"aevalsrc='{expr}':s=48000:d={duration}",
           "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac"]
    if shortest:
        cmd += ["-shortest"]
    cmd += [str(out)]
    subprocess.run(cmd, check=True)
    return out
