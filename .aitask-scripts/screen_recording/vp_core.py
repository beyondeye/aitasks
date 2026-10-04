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

# --------------------------------------------------------------------------- #
# ffmpeg log parsing

_SHOWINFO = re.compile(
    r"\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:\s*(-?\d+(?:\.\d+)?(?:e[-+]?\d+)?)"
)


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


# --------------------------------------------------------------------------- #
# bug mode: which frames are worth looking at

@dataclass
class Pick:
    index: int          # position in the kept-frame list
    t: float            # pts_time, seconds
    dwell: float        # seconds this picture stayed on screen
    reasons: list[str]  # start / state / motion / brief / end


_PRIORITY = {"start": 4, "end": 4, "state": 3, "brief": 2, "motion": 1}


def dwell_times(times: list[float], end_t: float) -> list[float]:
    """How long each kept frame stayed on screen: the gap to the next kept frame.

    mpdecimate dropped the near-duplicates in between, so a long gap means the
    picture sat still for that long."""
    n = len(times)
    return [max(0.0, (times[i + 1] if i + 1 < n else end_t) - times[i]) for i in range(n)]


def select_key_frames(times, end_t, *, min_dwell=0.4, interval=1.0, brief_max=0.12,
                      max_frames=40):
    """Pick the frames that summarise a recording, from mpdecimate's kept frames.

    - state:  dwell >= min_dwell, a screen that settled long enough to be seen
    - motion: inside a run of short-dwell frames (scrolling, long animations),
              one frame per `interval` seconds since the previous pick
    - brief:  a whole short-dwell run lasting <= brief_max (a flash, a glitch, a
              very quick transition) that interval sampling would step over
    - start / end: the first and last kept frame

    Returns (picks, dropped); `dropped` counts picks removed to honour max_frames
    (motion samples go first, then briefs, then the shortest-lived states).
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

    picks = [Pick(k, times[k], dwell[k], reasons[k]) for k in sorted(reasons)]
    if len(picks) <= max_frames:
        return picks, 0
    ranked = sorted(picks, key=lambda p: (max(_PRIORITY[r] for r in p.reasons), p.dwell),
                    reverse=True)
    keep = sorted(ranked[:max_frames], key=lambda p: p.index)
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
    t0_lo, t0_hi = t_first - 8 * dt, t_first
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


def analyze_frames(times, frames, w, h, *, signal="auto", nominal_dt=1 / 60):
    """Measure one motion window. frames[0] must be the still picture before the
    motion and frames[-1] the settled picture after it.

    Returns a dict with per-frame measurements, the chosen progress signal,
    visible timing and fits; see video_prep.py for how it is reported.
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
        dt = _frame_interval(times, fm, lm + 1 if lm + 1 < n else lm, nominal_dt)
        out.update(kind="returns", signal=None, progress=None, fits=[], first_moving=fm,
                   last_moving=lm, frame_interval=dt,
                   visible_duration=(times[min(lm + 1, n - 1)] - (times[fm] - dt)))
        out["warnings"].append("the picture returns to where it started (press feedback, "
                               "shake, ripple?): no progress curve, read the sheet")
        return out

    lm = max(i for i in range(n) if me[i].count > 0 or me[i].mad / se.mad > 0.02)
    lm = min(lm, n - 2)
    dt = _frame_interval(times, fm, lm + 1, nominal_dt)
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
