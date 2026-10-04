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


def encode(path, frames, *, w=W, h=H, fps=FPS, vfr=False, crf=18):
    """Encode raw gray frames to H.264. vfr=True drops exact duplicates and keeps
    the original timestamps, like Android's screenrecord does for a still screen."""
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
           "-pix_fmt", "gray", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
    if vfr:
        cmd += ["-vf", "mpdecimate=hi=1:lo=1:frac=0", "-fps_mode", "vfr"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
            "-pix_fmt", "yuv420p", str(path)]
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
