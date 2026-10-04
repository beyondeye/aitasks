"""Unit tests for .aitask-scripts/screen_recording/vp_core.py (aitask-screen-recording):
pure functions, no ffmpeg needed.

Run: python3 tests/test_screen_recording_core.py
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".aitask-scripts"
                       / "screen_recording"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vp_core as core  # noqa: E402
from screen_recording_synth import Canvas  # noqa: E402


class ParseShowinfo(unittest.TestCase):
    def test_parses_frame_lines_and_ignores_config_lines(self):
        log = (
            "[Parsed_showinfo_1 @ 0x5555] config in time_base: 1/15360, frame_rate: 60/1\n"
            "[Parsed_showinfo_1 @ 0x5555] n:   0 pts:      0 pts_time:0       duration:256\n"
            "[Parsed_showinfo_1 @ 0x5555] n:  12 pts:  15616 pts_time:1.01667 duration:256\n"
            "[Parsed_showinfo_1 @ 0x5555]  checksum:ABCDEF plane_checksum:[1 2 3]\n"
            "frame=  42 fps=0.0 q=-0.0 size=N/A\n")
        self.assertEqual(core.parse_showinfo(log), [(0, 0, 0.0), (12, 15616, 1.01667)])


class SelectKeyFrames(unittest.TestCase):
    def picks(self, times, end_t, **kw):
        picks, dropped = core.select_key_frames(times, end_t, **kw)
        return [(round(p.t, 3), tuple(p.reasons)) for p in picks], dropped

    def test_states_transitions_and_end(self):
        # still 0-1 s, a 0.3 s transition (frames every 1/60 s), still 1.3-3 s
        times = [0.0] + [1.0 + k / 60 for k in range(1, 18)] + [1.3]
        picks, dropped = self.picks(times, 3.0)
        self.assertEqual(dropped, 0)
        # the 0.3 s transition is not sampled: interval counts from the run start
        self.assertEqual(picks, [(0.0, ("start", "state")), (1.3, ("state", "end"))])

    def test_long_motion_is_sampled_per_interval(self):
        times = [0.0] + [1.0 + k / 60 for k in range(0, 150)] + [3.6]  # 2.5 s scroll
        picks, _ = self.picks(times, 5.0, interval=1.0)
        motion = [t for t, r in picks if "motion" in r]
        self.assertEqual(motion, [2.0, 3.0])

    def test_brief_flash_is_kept(self):
        times = [0.0, 2.0, 2.0 + 1 / 60]
        picks, _ = self.picks(times, 4.0)
        self.assertEqual(picks, [(0.0, ("start", "state")), (2.0, ("brief",)),
                                 (2.017, ("state", "end"))])

    def test_cap_drops_motion_before_states(self):
        times = [0.0] + [1.0 + k / 60 for k in range(0, 600)] + [12.0, 14.0, 16.0]
        # uncapped: start, 9 motion samples (2.0 .. 10.0), the run's last frame (a
        # state: it stays 1.017 s), states at 12 / 14 and the end at 16 -> 14 picks
        self.assertEqual(len(self.picks(times, 18.0)[0]), 14)
        picks, dropped = self.picks(times, 18.0, max_frames=4)
        self.assertEqual(dropped, 10)
        self.assertEqual(picks, [(0.0, ("start", "state")), (12.0, ("state",)),
                                 (14.0, ("state",)), (16.0, ("state", "end"))])

    def test_empty(self):
        self.assertEqual(core.select_key_frames([], 1.0), ([], 0))


class MotionSegments(unittest.TestCase):
    def test_groups_runs_split_by_pauses(self):
        times = [0.0, 1.0, 1.016, 1.033, 1.05, 2.0, 3.0, 3.016]
        self.assertEqual(core.motion_segments(times, 0.12), [(1, 4), (5, 5), (6, 7)])

    def test_video_starting_mid_motion(self):
        self.assertEqual(core.motion_segments([0.0, 0.016, 0.033, 2.0], 0.12), [(0, 2), (3, 3)])

    def test_no_change(self):
        self.assertEqual(core.motion_segments([0.0], 0.12), [])


class DiffStats(unittest.TestCase):
    def test_bbox_count_and_mad(self):
        a = Canvas(10, 6, 0)
        b = Canvas(10, 6, 0)
        b.rect(2, 1, 5, 3, 100)       # 3x2 block
        b.rect(9, 5, 10, 6, 5)        # below threshold
        d = core.diff_stats(a.bytes(), b.bytes(), 10, 6, thr=10)
        self.assertEqual(d.bbox, (2, 1, 4, 2))
        self.assertEqual(d.count, 6)
        self.assertEqual(d.maxd, 100)
        self.assertAlmostEqual(d.mad, (600 + 5) / 60)

    def test_identical(self):
        a = Canvas(8, 8, 7).bytes()
        d = core.diff_stats(a, a, 8, 8, 10)
        self.assertEqual((d.bbox, d.count, d.mad), (None, 0, 0.0))


def _slide_boxes(ds, D, s=10, w=20, y=(5, 9), axis_x=True, sign=+1):
    """bS/bE/bSE for an element of width w moving by d (sign = direction)."""
    def box(lo, hi):
        return (lo, y[0], hi, y[1]) if axis_x else (y[0], lo, y[1], hi)

    def span(a, b):  # union of two [x, x+w-1] intervals
        return min(a, b), max(a, b) + w - 1

    start, end = s, s + sign * D
    bS, bE = [], []
    for d in ds:
        cur = s + sign * d
        bS.append(None if d == 0 else box(*span(start, cur)))
        bE.append(None if d == D else box(*span(cur, end)))
    return bS, bE, box(*span(start, end))


class EdgeTracks(unittest.TestCase):
    def check(self, ds, D, expected, **kw):
        bS, bE, bSE = _slide_boxes(ds, D, **kw)
        tracks = core.edge_tracks(bS, bE, bSE, 200, 200)
        self.assertTrue(tracks, "no track found")
        tr = tracks[0]
        for got, want in zip(tr.progress, expected):
            self.assertAlmostEqual(got, want, places=6)
        return tr

    def test_rightward_slide_is_exact(self):
        tr = self.check([0, 5, 20, 40, 50], 50, [0, 0.1, 0.4, 0.8, 1])
        self.assertEqual((tr.axis, tr.kind, tr.magnitude, tr.spread), ("x", "edge+", 50.0, 0.0))

    def test_leftward_slide_is_exact(self):
        tr = self.check([0, 5, 20, 40, 50], 50, [0, 0.1, 0.4, 0.8, 1], s=100, sign=-1)
        self.assertEqual(tr.kind, "edge-")

    def test_vertical_slide(self):
        tr = self.check([0, 10, 30, 50], 50, [0, 0.2, 0.6, 1], axis_x=False)
        self.assertEqual(tr.axis, "y")

    def test_overshoot_is_measured_not_clipped(self):
        self.check([0, 20, 60, 45, 50], 50, [0, 0.4, 1.2, 0.9, 1])

    def test_sub_pixel_sliver_near_the_end_does_not_inflate_spread(self):
        # regression: within a pixel of the end, frame-vs-end differs only in one
        # anti-aliased column, so that frame's travel estimate is garbage
        ds = [0, 5, 10, 20, 30, 40, 45, 48, 50]
        bS, bE, bSE = _slide_boxes(ds, 50)
        bE[-2] = (bSE[2], 5, bSE[2], 9)          # sliver at the end position's right edge
        tr = core.edge_tracks(bS, bE, bSE, 200, 200)[0]
        self.assertLess(tr.spread, 0.05)
        self.assertAlmostEqual(tr.progress[-2], 48 / 50)

    def test_centred_grow_is_anchored_on_first_moving_frame(self):
        # square centred at 100 growing 20 -> 60 px; sizes at mid frames 30, 40, 50.
        # The start size is not observable from a bbox, so the first moving frame
        # (30 px) anchors 0: 40 px -> (40-30)/(60-30) = 1/3.
        def box(sz):
            return (100 - sz // 2, 100 - sz // 2, 100 + sz // 2 - 1, 100 + sz // 2 - 1)
        sizes = [20, 30, 40, 50, 60]
        bS = [None] + [box(s) for s in sizes[1:]]
        bE = [box(60) for _ in sizes[:-1]] + [None]
        tr = core.edge_tracks(bS, bE, box(60), 200, 200)[0]
        self.assertEqual(tr.kind, "grow")
        self.assertFalse(tr.exact)
        self.assertEqual([round(p, 3) for p in tr.progress], [0, 0, 0.333, 0.667, 1])

    def test_no_geometry_change(self):
        same = (10, 10, 30, 30)
        self.assertEqual(core.edge_tracks([None, same, same, None], [same, same, same, None],
                                          same, 100, 100), [])


class Easing(unittest.TestCase):
    def test_linear_is_identity(self):
        f = core.CubicBezier(0, 0, 1, 1)
        for x in (0.1, 0.25, 0.5, 0.9):
            self.assertAlmostEqual(f(x), x, places=4)

    def test_symmetry_of_css_curves(self):
        ease_in, ease_out = core.CubicBezier(0.42, 0, 1, 1), core.CubicBezier(0, 0, 0.58, 1)
        in_out = core.CubicBezier(0.42, 0, 0.58, 1)
        self.assertAlmostEqual(in_out(0.5), 0.5, places=4)
        for x in (0.1, 0.3, 0.6, 0.85):
            self.assertAlmostEqual(ease_in(x) + ease_out(1 - x), 1.0, places=3)

    def test_rejects_non_function_curves(self):
        with self.assertRaises(ValueError):
            core.CubicBezier(1.2, 0, 0.5, 1)

    def test_spring_overshoot_matches_closed_form(self):
        k, z = 400.0, 0.5
        peak = max(core.spring(t / 2000, k, z) for t in range(4000))
        self.assertAlmostEqual(peak, 1 + math.exp(-z * math.pi / math.sqrt(1 - z * z)), places=3)

    def test_critically_and_over_damped_springs_do_not_overshoot(self):
        for z in (1.0, 1.4):
            vals = [core.spring(t / 1000, 1500, z) for t in range(2000)]
            self.assertTrue(all(b >= a - 1e-12 for a, b in zip(vals, vals[1:])))
            self.assertLessEqual(max(vals), 1.0 + 1e-9)

    def test_settle_time(self):
        # critically damped: 1 - e^{-wt}(1 + wt) = 0.99 at wt ~= 6.64
        self.assertAlmostEqual(core.spring_settle_time(1500, 1.0), 6.638 / math.sqrt(1500),
                               delta=0.002)

    def test_compose_preset_naming(self):
        self.assertEqual(core.nearest_compose_spring(1500, 1.0),
                         "spring(dampingRatio = Spring.DampingRatioNoBouncy, "
                         "stiffness = Spring.StiffnessMedium)")
        self.assertIn("stiffness = 900f", core.nearest_compose_spring(900, 0.5))


def _samples(fn, t0, n=40, dt=1 / 60):
    ts = [t0 - 0.1 + k * dt for k in range(n)]
    return ts, [fn(t) for t in ts]


class FitMotion(unittest.TestCase):
    def test_recovers_named_tween_and_timing(self):
        for name, cp in (("CSS ease-out", (0, 0, 0.58, 1)),
                         ("FastOutSlowIn (Compose tween default, M2 standard)", (0.4, 0, 0.2, 1)),
                         ("linear", (0, 0, 1, 1))):
            f = core.CubicBezier(*cp)
            ts, ps = _samples(lambda t: f((t - 0.5) / 0.3), 0.5)
            first = next(t for t, p in zip(ts, ps) if p > 0)
            settled = next(t for t, p in zip(ts, ps) if p >= 1)
            fits = core.fit_motion(ts, ps, t_first=first, t_settled=settled, dt=1 / 60)
            named = [x for x in fits if x.name != "custom cubic-bezier"]
            with self.subTest(curve=name):
                self.assertEqual(named[0].name, name)
                self.assertAlmostEqual(named[0].duration, 0.3, delta=0.004)
                self.assertAlmostEqual(named[0].t0, 0.5, delta=0.004)
                self.assertLess(named[0].rmse, 0.005)

    def test_recovers_spring_parameters(self):
        ts, ps = _samples(lambda t: core.spring(t - 0.5, 400.0, 0.5), 0.5, n=60)
        first = next(t for t, p in zip(ts, ps) if p > 0)
        fits = core.fit_motion(ts, ps, t_first=first, t_settled=ts[-1], dt=1 / 60)
        self.assertEqual(fits[0].family, "spring")
        k, z = fits[0].params
        self.assertAlmostEqual(k, 400, delta=20)
        self.assertAlmostEqual(z, 0.5, delta=0.03)
        self.assertIn("Spring.StiffnessMediumLow", fits[0].extra["compose"])
        self.assertIn("Spring.DampingRatioMediumBouncy", fits[0].extra["compose"])

    def test_tween_beats_spring_on_tween_data(self):
        f = core.CubicBezier(0.42, 0, 0.58, 1)
        ts, ps = _samples(lambda t: f((t - 0.5) / 0.4), 0.5, n=50)
        fits = core.fit_motion(ts, ps, t_first=0.5 + 1 / 60, t_settled=0.9, dt=1 / 60)
        self.assertEqual(fits[0].family, "tween")

    def test_time_scale_conversion(self):
        tw = core.Fit("tween", "linear", (0, 0, 1, 1), 1.0, 1.5, 0.01)
        self.assertAlmostEqual(core.scale_fit_time(tw, 5).duration, 0.3)
        sp = core.Fit("spring", "spring", (16.0, 0.5), 1.0, 2.0, 0.01, {})
        conv = core.scale_fit_time(sp, 5)
        self.assertEqual(conv.params, (400.0, 0.5))
        self.assertAlmostEqual(conv.duration, 0.4)
        self.assertIn("Spring.StiffnessMediumLow", conv.extra["compose"])


class AnalyzeFrames(unittest.TestCase):
    """analyze_frames on hand-drawn frames (no codec): an 8 px box sliding 40 px."""

    def frames(self, progress, n=40, w=80, h=24):
        out = []
        for i in range(n):
            c = Canvas(w, h, 230)
            x = 10 + 40 * progress(i / 60)
            c.rect(x, 8, x + 8, 16, 20)
            out.append(c.bytes())
        return [i / 60 for i in range(n)], out

    def test_linear_slide(self):
        ts, fr = self.frames(lambda t: min(1.0, max(0.0, (t - 0.1) / 0.3)))
        res = core.analyze_frames(ts, fr, 80, 24)
        self.assertEqual(res["kind"], "edge+-x")
        self.assertEqual(res["signal"], "edge")
        self.assertAlmostEqual(res["visible_duration"], 0.3, delta=1 / 60 + 1e-9)
        best = [f for f in res["fits"] if f.family == "tween"][0]
        self.assertAlmostEqual(best.duration, 0.3, delta=0.02)

    def test_box_that_returns_to_start(self):
        ts, fr = self.frames(lambda t: 0.5 if 0.1 < t < 0.3 else 0.0)
        res = core.analyze_frames(ts, fr, 80, 24)
        self.assertEqual(res["kind"], "returns")
        self.assertEqual(res["fits"], [])

    def test_still(self):
        ts, fr = self.frames(lambda t: 0.0)
        self.assertEqual(core.analyze_frames(ts, fr, 80, 24)["kind"], "still")


if __name__ == "__main__":
    unittest.main()
