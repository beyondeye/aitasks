"""End-to-end tests of aitask-screen-recording: synthetic recordings through the
real CLI (needs ffmpeg; skipped without it).

Ground truth comes from tests/screen_recording_synth.py. Timing tolerances are one frame at 60 fps
(16.7 ms) for visible durations and 12 ms for fitted tween durations unless noted.

Run: python3 tests/test_screen_recording_cli.py
"""
from __future__ import annotations

import contextlib
import csv
import html.parser
import os
import functools
import hashlib
import io
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from unittest import mock
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / ".aitask-scripts" / "screen_recording" / "video_prep.py"
WRAPPER = HERE.parent / ".aitask-scripts" / "aitask_screen_recording.sh"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SCRIPT.parent))
import screen_recording_synth as synth  # noqa: E402
import vp_core as core  # noqa: E402
import vp_pick as pick  # noqa: E402

HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
HAVE_MAGICK = bool(shutil.which("magick"))
FRAME_MS = 1000 / 60


def run_cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True)


def best_named_tween(fit):
    return next(f for f in fit["fits"] if f["family"] == "tween"
                and f["name"] != "custom cubic-bezier")


class _VideoCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="vp-test-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def video(self, name, frames, *, vfr=False):
        """Encode once per class; `frames` may be a zero-argument callable so a
        cached video is not drawn again."""
        path = self.tmp / f"{name}.mp4"
        if not path.exists():
            synth.encode(path, frames() if callable(frames) else frames, vfr=vfr)
        return path

    def cli_ok(self, *args):
        cp = run_cli(*args)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertIn("SUMMARY:", cp.stdout)
        return cp


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe not installed")
class AnimMode(_VideoCase):
    def anim(self, name, frames, *extra, vfr=False, out_name=None):
        video = self.video(name, frames, vfr=vfr)
        out = self.tmp / f"{out_name or name}-out"
        self.cli_ok("anim", video, "--out", out, *extra)
        fits = [json.loads(p.read_text()) for p in sorted(out.glob("*/fit.json"))]
        return out, fits

    @staticmethod
    def curve_rows(out, label):
        with open(out / label / "curve.tsv", newline="") as fh:
            return list(csv.DictReader(fh, delimiter="\t"))

    def assert_tween(self, fit, name, dur_ms, *, frame_ms=FRAME_MS, fit_tol=12.0):
        # The visible change can miss the faint first/last frames of slow-in/slow-out
        # curves (they move < 1 px or change < 2 %), so it may read up to 2 frames
        # short and at most 1 frame long. The fitted duration models those tails.
        vis = fit["visible_duration_ms"]
        self.assertGreaterEqual(vis, dur_ms - 2 * frame_ms - 0.5, fit)
        self.assertLessEqual(vis, dur_ms + frame_ms + 0.5, fit)
        best = best_named_tween(fit)
        self.assertEqual(best["name"], name, fit["fits"][:4])
        self.assertAlmostEqual(best["duration_ms"], dur_ms, delta=fit_tol)

    @staticmethod
    def slide_right():
        return synth.card_frames(synth.tween(synth.EASE_OUT, 0.5, 0.3), 1.4, "right")

    def test_slide_right_ease_out(self):
        out, fits = self.anim("slide_right", self.slide_right())
        self.assertEqual(len(fits), 1)
        fit = fits[0]
        self.assertEqual((fit["kind"], fit["signal"]), ("edge+-x", "edge"))
        self.assertAlmostEqual(fit["travel_source_px"], 160, delta=4)
        self.assertLess(fit["travel_spread"], 0.1)
        self.assert_tween(fit, "CSS ease-out", 300)
        self.assertEqual(fit["warnings"], [])
        summary = (out / "summary.md").read_text()
        self.assertIn("| s01 |", summary)
        self.assertTrue((out / "s01" / "curve.tsv").exists())
        # an edge track exists, so curve.tsv carries both signals and the summary says so
        rows = self.curve_rows(out, "s01")
        self.assertTrue(all(row["p_edge"] for row in rows), rows[:3])
        self.assertIn("- fitted signal: edge (both signals are in curve.tsv)", summary)
        if HAVE_MAGICK:
            self.assertTrue((out / "s01" / "sheet_01.png").exists())
            self.assertTrue((out / "s01" / "plot.png").exists())

    def strip_run(self, *extra):
        """anim on a 40x800 --roi strip the card crosses (one segment)."""
        out, fits = self.anim("strip_down", lambda: synth.card_frames(
            synth.tween(synth.EASE_OUT, 0.5, 0.3), 1.3, "down"),
            "--roi", "160,0,40,800", *extra,
            out_name="strip_down" + "".join(extra).replace("-", "_"))
        self.assertEqual(len(fits), 1)
        frames = sorted((out / "s01" / "frames").glob("f*.png"))
        return out, json.loads((out / "run.json").read_text()), frames

    @staticmethod
    def pre_t2219_layout(n, w, h, label_h=40, edge=1600):
        """(cols, cell_w, cell_h) the bug/anim sheets used before t2219: sized
        from the image alone, whatever the labels (the removed sheet_layout)."""
        best = None
        for cols in range(1, n + 1):
            rows = math.ceil(n / cols)
            s = min((edge - 8 * cols) / (cols * w), (edge - (label_h + 8) * rows) / (rows * h),
                    4.0)
            if best is None or s > best[0] + 1e-9:
                best = (s, cols)
        s, cols = best
        return cols, max(1, int(w * s)), max(1, int(h * s))

    @unittest.skipUnless(HAVE_MAGICK, "ImageMagick (magick) not installed")
    def test_narrow_roi_sheet_labels_stay_inside_their_cells(self):
        """A 40 px --roi strip at the default --per-sheet: the image-only layout
        made cells narrower than the 'fNNN 0.000s' labels, which then spilled
        over their neighbours; cells now widen to the labels."""
        out, run, frames = self.strip_run()
        (t,) = run["sheet_tiles"]                     # every saved frame on one sheet
        self.assertEqual(t["count"], len(frames))
        self.assertGreater(t["cols"], 1)
        self.assertEqual(dirty_borders(out / t["sheet"], t["cell_w"], t["cols"]), [], t)

        # premise: the layout the old code computed for this many frames, drawn
        # with these frames and their real first label line, does overflow
        cols, tw, th = self.pre_t2219_layout(len(frames), 40, 800)
        self.assertGreater(cols, 1)
        self.assertLess(tw, t["cell_w"])
        labels = []
        for f in frames:
            m = re.fullmatch(r"(f\d{3})_(\d+\.\d{3})s\.png", f.name)
            labels += ["-label", f"{m[1]} {m[2]}s\n+0ms", f]
        bad = self.tmp / "strip-old-layout.png"
        subprocess.run(["magick", "montage", "-background", "#1e1e1e", "-fill", "#f2f2f2",
                        "-pointsize", "15", *labels, "-tile", f"{cols}x",
                        "-geometry", f"{tw}x{th}+4+4", bad], check=True)
        self.assertNotEqual(dirty_borders(bad, tw, cols), [])

    @unittest.skipUnless(HAVE_MAGICK, "ImageMagick (magick) not installed")
    def test_narrow_roi_sheets_list_the_frames_they_hold(self):
        out, run, frames = self.strip_run("--per-sheet", "7")
        tiles = run["sheet_tiles"]
        self.assertGreaterEqual(len(tiles), 2)
        # the ranges cut the frames actually saved, in order, sheet by sheet
        saved = [int(f.name[1:4]) for f in frames]
        self.assertEqual(sum(t["count"] for t in tiles), len(saved))
        k = 0
        for t in tiles:
            self.assertEqual((t["first"], t["last"]), (saved[k], saved[k + t["count"] - 1]), t)
            k += t["count"]
            self.assertEqual(dirty_borders(out / t["sheet"], t["cell_w"], t["cols"]), [], t)
        summary = (out / "summary.md").read_text()
        self.assertIn("- sheets: " + ", ".join(
            f"{t['sheet']} f{t['first']:03d}-f{t['last']:03d}" for t in tiles) + "\n", summary)

    def test_slide_left_fast_out_slow_in(self):
        _, fits = self.anim("slide_left", synth.card_frames(
            synth.tween(synth.FAST_OUT_SLOW_IN, 0.5, 0.4), 1.5, "left"))
        self.assertEqual(fits[0]["kind"], "edge--x")
        self.assert_tween(fits[0], "FastOutSlowIn (Compose tween default, M2 standard)", 400)

    def test_slide_down_linear(self):
        _, fits = self.anim("slide_down", synth.card_frames(
            synth.tween(synth.LINEAR, 0.5, 0.25), 1.3, "down"))
        self.assertEqual(fits[0]["kind"], "edge+-y")
        self.assert_tween(fits[0], "linear", 250)

    def test_fade_uses_blend_signal(self):
        out, fits = self.anim("fade", synth.card_frames(
            synth.tween(synth.EASE_IN_OUT, 0.5, 0.3), 1.4, "fade"))
        self.assertEqual((fits[0]["kind"], fits[0]["signal"]), ("fade/blend", "blend"))
        self.assert_tween(fits[0], "CSS ease-in-out / iOS easeInOut", 300)
        # a fade has no edge track: p_edge is blank in every row, and the summary
        # must not claim curve.tsv holds both signals
        rows = self.curve_rows(out, "s01")
        self.assertTrue(rows)
        self.assertEqual({row["p_edge"] for row in rows}, {""})
        self.assertTrue(all(row["p_blend"] for row in rows), rows[:3])
        summary = (out / "summary.md").read_text()
        self.assertIn("- fitted signal: blend (p_blend in curve.tsv; no edge track, so "
                      "p_edge is blank)", summary)
        self.assertNotIn("both signals are in curve.tsv", summary)

    def test_spring_with_overshoot(self):
        _, fits = self.anim("spring", synth.card_frames(
            synth.spring_progress(400.0, 0.5, 0.5), 2.0, "right"))
        self.assertEqual(len(fits), 1)
        fit = fits[0]
        self.assertEqual((fit["kind"], fit["signal"]), ("edge+-x", "edge"))
        best = fit["fits"][0]
        self.assertEqual(best["family"], "spring", fit["fits"][:3])
        k, z = best["params"]
        self.assertAlmostEqual(k, 400, delta=60)
        self.assertAlmostEqual(z, 0.5, delta=0.07)
        self.assertAlmostEqual(fit["overshoot"], 0.163, delta=0.03)
        self.assertIn("Spring.StiffnessMediumLow", best["compose"])

    def test_centred_grow_is_approximate_but_timed(self):
        _, fits = self.anim("grow", synth.card_frames(
            synth.tween(synth.EASE_OUT, 0.5, 0.3), 1.4, "grow"))
        self.assertTrue(fits[0]["kind"].startswith("grow-"), fits[0]["kind"])
        self.assertAlmostEqual(fits[0]["visible_duration_ms"], 300, delta=FRAME_MS + 0.5)
        self.assertAlmostEqual(best_named_tween(fits[0])["duration_ms"], 300, delta=30)

    def test_variable_frame_rate_recording(self):
        # duplicates dropped like Android's screenrecord: the still picture before the
        # motion lies outside the analysis window and must be fetched separately
        _, fits = self.anim("slide_right_vfr", self.slide_right(), vfr=True)
        self.assertEqual(len(fits), 1)
        self.assert_tween(fits[0], "CSS ease-out", 300)

    def test_time_scale_converts_slowed_recording(self):
        _, fits = self.anim("slow5x", synth.card_frames(
            synth.tween(synth.EASE_OUT, 0.5, 1.5), 2.6, "right"), "--time-scale", "5")
        self.assertEqual(fits[0]["time_scale"], 5.0)
        self.assert_tween(fits[0], "CSS ease-out", 300, frame_ms=FRAME_MS / 5, fit_tol=5)

    def test_window_option(self):
        _, fits = self.anim("slide_right", self.slide_right, "--window", "0.3-1.2",
                            out_name="slide_right_window")
        self.assertEqual(fits[0]["label"], "w01")
        self.assert_tween(fits[0], "CSS ease-out", 300)

    def test_two_segments_in_order(self):
        progress = synth.chain(synth.tween(synth.EASE_OUT, 0.5, 0.3),
                               synth.tween(synth.LINEAR, 1.5, 0.3))
        frames = synth.card_frames(lambda t: progress(t) / 2, 2.4, "right")
        _, fits = self.anim("two", frames)
        self.assertEqual([f["label"] for f in fits], ["s01", "s02"])
        self.assertAlmostEqual(fits[0]["window_s"][0], 0.517 - 0.25, delta=0.02)
        self.assertAlmostEqual(fits[1]["window_s"][0], 1.517 - 0.25, delta=0.02)
        self.assert_tween(fits[0], "CSS ease-out", 300)
        self.assert_tween(fits[1], "linear", 300)

    def test_status_bar_clock_is_a_cut_until_cropped(self):
        frames = synth.card_frames(synth.tween(synth.EASE_OUT, 0.5, 0.3), 1.6, "right",
                                   clock_ticks=(0.2, 1.3))
        out, fits = self.anim("clock", frames)
        self.assertEqual(len(fits), 1)
        self.assertIn("2 at 0.200, 1.300 s", (out / "summary.md").read_text())
        out, fits = self.anim("clock", frames, "--crop-top", "24", out_name="clock-cropped")
        self.assertEqual(len(fits), 1)
        self.assertNotIn("single-frame changes", (out / "summary.md").read_text())
        self.assert_tween(fits[0], "CSS ease-out", 300)

    def test_still_video_has_no_segments(self):
        out, fits = self.anim("still", synth.card_frames(lambda t: 0.0, 1.0, "still"))
        self.assertEqual(fits, [])
        self.assertIn("0 motion segment(s)", (out / "summary.md").read_text())

    # A segment's window ends --pad (0.25 s) after its last change, clamped to the end
    # of the video. These clips settle at 0.8 s and end at 0.9 s, so the clamp decides.
    SLIDE_TO_END_S = 0.9

    def slide_to_end(self):
        return self.video("slide_to_end", lambda: synth.card_frames(
            synth.tween(synth.EASE_OUT, 0.5, 0.3), self.SLIDE_TO_END_S, "right"))

    def anim_run(self, video, out_name, *extra):
        out = self.tmp / out_name
        self.cli_ok("anim", video, "--out", out, *extra)
        fits = [json.loads(p.read_text()) for p in sorted(out.glob("*/fit.json"))]
        return fits, json.loads((out / "run.json").read_text())

    def test_window_end_is_clamped_to_the_video_end(self):
        # premise control: start_time 0 and no audio, so the container end is the video
        # end too; this passes with or without the normalised end
        video = self.slide_to_end()
        # fixture guard: mpdecimate (as scan() runs it) keeps a change late enough that
        # the pad alone would run past the last frame
        cp = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(video), "-an",
                             "-vf", "mpdecimate,showinfo", "-fps_mode", "passthrough",
                             "-f", "null", "-"], capture_output=True, text=True, check=True)
        last_kept = float(cp.stderr.split(" pts_time:")[-1].split()[0])
        self.assertGreater(last_kept + 0.25, self.SLIDE_TO_END_S + 0.02,
                           "fixture no longer reaches the video end")
        (fit,), run = self.anim_run(video, "slide-to-end-out")
        self.assertAlmostEqual(run["video"]["start_time"], 0.0, delta=1e-6)
        self.assertAlmostEqual(fit["window_s"][1], self.SLIDE_TO_END_S, delta=0.002)

    def test_nonzero_start_time_window_end(self):
        path = self.tmp / "slide_to_end_ts5.mp4"
        synth.encode(path, synth.card_frames(synth.tween(synth.EASE_OUT, 0.5, 0.3),
                                             self.SLIDE_TO_END_S, "right"), ts_offset=5)
        (fit,), run = self.anim_run(path, "slide-to-end-ts5")
        self.assertAlmostEqual(run["video"]["start_time"], 5.0, delta=0.05)  # fixture guard
        self.assertAlmostEqual(fit["window_s"][1], self.SLIDE_TO_END_S, delta=0.002)
        # --range still bounds the window once the video end is past it
        (fit,), _ = self.anim_run(path, "slide-to-end-ts5-ranged", "--range", "0-0.85")
        self.assertAlmostEqual(fit["window_s"][1], 0.85, delta=1e-6)

    def test_window_end_ignores_longer_audio(self):
        video = synth.mux_tone(self.slide_to_end(), self.tmp / "slide_to_end_long_audio.mp4",
                               duration=3, shortest=False)
        (fit,), run = self.anim_run(video, "slide-to-end-long-audio")
        # fixture guard: the container duration is the 3 s audio track's
        self.assertAlmostEqual(run["video"]["duration"], 3.0, delta=0.05)
        self.assertAlmostEqual(fit["window_s"][1], self.SLIDE_TO_END_S, delta=0.002)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe not installed")
class BugMode(_VideoCase):
    def timeline(self, out):
        with open(out / "timeline.tsv") as fh:
            return [(float(r["time_s"]), set(r["why"].split("+")), r["file"])
                    for r in csv.DictReader(fh, delimiter="\t") if r["kind"] == "frame"]

    def assert_matches_expected(self, rows):
        expected = synth.BUG_TIMELINE["picks"]
        self.assertEqual(len(rows), len(expected), rows)
        for (t, why, _), (t_exp, why_exp) in zip(rows, expected):
            self.assertAlmostEqual(t, t_exp, delta=0.02, msg=rows)
            self.assertEqual(why, why_exp, rows)

    def test_states_scroll_toggle_and_flash(self):
        video = self.video("bug", synth.bug_frames)
        out = self.tmp / "bug-out"
        self.cli_ok("bug", video, "--out", out)
        rows = self.timeline(out)
        self.assert_matches_expected(rows)
        for _, _, f in rows:
            self.assertTrue((out / f).exists(), f)
        summary = (out / "summary.md").read_text()
        if HAVE_MAGICK:
            self.assertTrue((out / "sheet_01.png").exists())
            run = json.loads((out / "run.json").read_text())
            self.assertEqual([(t["sheet"], t["first"], t["last"]) for t in run["sheet_tiles"]],
                             [("sheet_01.png", 1, 7)])
            self.assertIn("- sheet_01.png: frames #1-#7\n", summary)
            self.assertFalse(run["per_sheet_reduced"])
        self.assertIn("picked 7 frames", summary)
        self.assertIn("audio: none", summary)

    @unittest.skipUnless(HAVE_MAGICK, "ImageMagick (magick) not installed")
    def test_layout_reduced_sheets_list_the_frames_they_hold(self):
        """A sheet cut short so its labels fit: the summary and run.json give the
        frames each sheet really holds, not --per-sheet arithmetic. ffmpeg cannot
        extract the ~130+ frames a 1600 px sheet needs before it must reduce (its
        select expression fails past ~110 picks), so the real bug pipeline runs
        in-process with a 500 px sheet edge: the layout, montage and summary code
        are the shipped ones, only the size budget is smaller."""
        import video_prep as vp
        video = self.video("slide_linear_2s", lambda: synth.card_frames(
            synth.tween(synth.LINEAR, 0.0, 2.0), 2.0, "right"))
        out = self.tmp / "bug-reduced"
        per_sheet = 40
        with mock.patch.object(vp, "SHEET_MAX_EDGE", 500), \
                contextlib.redirect_stdout(io.StringIO()):
            rc = vp.main([str(a) for a in (
                "bug", video, "--out", out, "--interval", "0.05", "--max-frames", "40",
                "--per-sheet", per_sheet, "--view-size", "100")])
        self.assertEqual(rc, 0)
        run = json.loads((out / "run.json").read_text())
        summary = (out / "summary.md").read_text()
        tiles = run["sheet_tiles"]
        n = len(self.timeline(out))
        saved = sorted((out / "frames").glob("*.png"))
        # premise: every pick saved, and all of them requested on one sheet
        self.assertEqual((len(saved), run["picks"]), (n, n))
        self.assertLessEqual(n, per_sheet)
        self.assertTrue(run["per_sheet_reduced"])
        self.assertGreaterEqual(len(tiles), 2)
        self.assertTrue(all(t["count"] < per_sheet for t in tiles), tiles)
        self.assertEqual(run["sheets"], [t["sheet"] for t in tiles])
        # every summary range is its sheet's real range, one line per sheet, in order
        listed = re.findall(r"^- (sheet_\d+\.png): frames #(\d+)-#(\d+)$", summary, re.M)
        self.assertEqual([(s, int(a), int(b)) for s, a, b in listed],
                         [(t["sheet"], t["first"], t["last"]) for t in tiles])
        # the ranges partition #1..#n, the frames actually saved
        self.assertEqual(tiles[0]["first"], 1)
        self.assertEqual(tiles[-1]["last"], n)
        for prev, nxt in zip(tiles, tiles[1:]):
            self.assertEqual(nxt["first"], prev["last"] + 1, tiles)
        for t in tiles:
            self.assertEqual(t["count"], t["last"] - t["first"] + 1, t)
            path = out / t["sheet"]
            with open(path, "rb") as fh:
                w, _ = core.png_size(fh.read(24))
            # the tile count actually drawn per row, and no label over a border
            self.assertEqual(w, min(t["count"], t["cols"]) * (t["cell_w"] + 8), t)
            self.assertEqual(dirty_borders(path, t["cell_w"], t["cols"]), [], t)
        self.assertIn(f"- note: --per-sheet {per_sheet} does not fit with readable labels "
                      f"(at most {max(t['count'] for t in tiles)} frames a sheet here)\n",
                      summary)

    def test_status_bar_clock_needs_crop(self):
        video = self.video("bug_clock", lambda: synth.bug_frames(clock=True))
        out = self.tmp / "bug-clock-out"
        self.cli_ok("bug", video, "--out", out)
        self.assertGreater(len(self.timeline(out)), len(synth.BUG_TIMELINE["picks"]))
        out = self.tmp / "bug-clock-cropped"
        self.cli_ok("bug", video, "--out", out, "--crop-top", "24")
        self.assert_matches_expected(self.timeline(out))

    def test_max_frames_cap_reports_drops(self):
        video = self.video("bug", synth.bug_frames)
        out = self.tmp / "bug-capped"
        self.cli_ok("bug", video, "--out", out, "--max-frames", "4")
        rows = self.timeline(out)
        self.assertEqual(len(rows), 4)
        self.assertNotIn("motion", set().union(*(why for _, why, _ in rows)))
        self.assertIn("3 more dropped", (out / "summary.md").read_text())

    def test_still_video(self):
        video = self.video("still", lambda: synth.card_frames(lambda t: 0.0, 1.0, "still"))
        out = self.tmp / "bug-still"
        self.cli_ok("bug", video, "--out", out)
        rows = self.timeline(out)
        self.assertEqual([(t, why) for t, why, _ in rows], [(0.0, {"start", "state", "end"})])


def gray_mean(png: Path) -> float:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(png), "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    return sum(raw) / len(raw)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe not installed")
class TriageRows(_VideoCase):
    """Freeze / black / silence rows in bug mode. Every end is checked for its
    evidence: observed only when the detector marked it on a frame, else a lower
    bound at the end of the analysed video span (from video packets, on the
    detectors' timeline)."""

    def bug(self, video, out_name, *extra):
        out = self.tmp / out_name
        self.cli_ok("bug", video, "--out", out, *extra)
        with open(out / "timeline.tsv", newline="") as fh:
            rows = list(csv.DictReader(fh, delimiter="\t"))
        return out, rows, json.loads((out / "run.json").read_text())

    @staticmethod
    def intervals(run, kind):
        return [iv for iv in run["intervals"] if iv["kind"] == kind]

    def assert_span(self, iv, start, end, *, observed, tol=FRAME_MS / 1000 + 1e-3):
        self.assertAlmostEqual(iv["start_s"], start, delta=tol, msg=iv)
        self.assertAlmostEqual(iv["end_s"], end, delta=tol, msg=iv)
        self.assertEqual(iv["end_observed"], observed, iv)

    def test_freeze_and_black_within_a_frame(self):
        for vfr in (False, True):
            with self.subTest(vfr=vfr):
                video = self.video(f"triage{'_vfr' if vfr else ''}", synth.triage_frames,
                                   vfr=vfr)
                out, rows, run = self.bug(video, f"triage-out-{vfr}")
                truth = synth.TRIAGE_TRUTH
                for kind in ("freeze", "black"):
                    got = self.intervals(run, kind)
                    self.assertEqual(len(got), len(truth[kind]), got)
                    for iv, (a, b) in zip(got, truth[kind]):
                        self.assert_span(iv, a, b, observed=True)
                for iv in self.intervals(run, "black"):
                    self.assertTrue(iv["file"] and (out / iv["file"]).exists(), iv)
                # run.json and timeline.tsv carry the same intervals
                tsv = [(r["kind"], float(r["time_s"]), float(r["end_s"]), r["file"] or None)
                       for r in rows if r["kind"] != "frame"]
                self.assertEqual(tsv, [(iv["kind"], round(iv["start_s"], 3),
                                        round(iv["end_s"], 3), iv["file"])
                                       for iv in run["intervals"]])
                self.assertEqual(self.intervals(run, "silence"), [])
                self.assertIsNone(run["detectors"]["silence"])
                summary = (out / "summary.md").read_text()
                self.assertIn("silence not checked (no audio stream)", summary)
                self.assertIn("## Freeze, black and silence", summary)

    def test_black_frame_comes_from_inside_the_interval(self):
        video = self.video("dark_flash", synth.dark_flash_frames)
        # fixture guard: mpdecimate drops the black frame, so the nearest kept
        # frame (t=0) is not black -- the hazard this test exists for
        cp = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(video), "-an",
                             "-vf", "mpdecimate,showinfo", "-f", "null", "-"],
                            capture_output=True, text=True)
        self.assertEqual(cp.stderr.count(" pts_time:"), 1, "fixture no longer has the hazard")
        out, rows, run = self.bug(video, "dark-out")
        (iv,) = self.intervals(run, "black")
        self.assert_span(iv, 0.5, 0.5 + 1 / 60, observed=True)
        self.assertTrue(iv["file"].endswith("_0.500s.png"), iv)
        start_png = next(out.glob("frames/01_0.000s.png"))
        black, start = gray_mean(out / iv["file"]), gray_mean(start_png)
        self.assertLess(black, start - 2, (black, start))
        self.assertLessEqual(black, 24.5, black)   # blackdetect's pix_th in full range ~25.5
        # duration consistency: the picture's "shown for" is the black run, never the
        # 0.5 s until the next kept frame
        (frame_row,) = [r for r in rows if r["kind"] == "frame" and r["file"] == iv["file"]]
        (iv_row,) = [r for r in rows if r["kind"] == "black"]
        for d in (float(frame_row["shown_for_s"]),
                  float(iv_row["end_s"]) - float(iv_row["time_s"]), iv["duration_s"]):
            self.assertAlmostEqual(d, 1 / 60, delta=FRAME_MS / 1000, msg=(frame_row, iv_row))
        self.assertIn("0.017 s (black run)", (out / "summary.md").read_text())

    def test_trailing_vs_final_frame_recovery(self):
        for vfr in (False, True):
            with self.subTest(vfr=vfr):
                cut = self.video(f"tail_cut_{vfr}", lambda: synth.tail_frames(recover=False),
                                 vfr=vfr)
                _, _, run = self.bug(cut, f"tail-cut-{vfr}")
                (iv,) = self.intervals(run, "black")
                self.assertTrue(run["video_end_proven"], run["video_end_note"])
                self.assertFalse(iv["end_observed"], iv)
                self.assertAlmostEqual(iv["start_s"], 0.5, delta=1e-3)
                self.assertAlmostEqual(iv["end_s"], run["video_end_s"], delta=1e-6)
                rec = self.video(f"tail_rec_{vfr}", lambda: synth.tail_frames(recover=True),
                                 vfr=vfr)
                _, _, run = self.bug(rec, f"tail-rec-{vfr}")
                (iv,) = self.intervals(run, "black")
                self.assert_span(iv, 0.5, 59 / 60, observed=True)

    def test_range_truncation_is_not_an_observed_end(self):
        cut = self.video("tail_cut_False", lambda: synth.tail_frames(recover=False))
        _, _, run = self.bug(cut, "tail-ranged", "--range", "0-0.8")
        (iv,) = self.intervals(run, "black")
        self.assertFalse(iv["end_observed"], iv)
        self.assertAlmostEqual(iv["end_s"], 0.8, delta=1e-6)
        self.assertEqual((run["video_end_s"], run["video_end_proven"]), (0.8, True))
        rec = self.video("tail_rec_False", lambda: synth.tail_frames(recover=True))
        _, _, run = self.bug(rec, "tail-rec-ranged", "--range", "0-1.0")
        (iv,) = self.intervals(run, "black")
        self.assert_span(iv, 0.5, 59 / 60, observed=True)

    def test_video_end_ignores_longer_audio(self):
        cut = self.video("tail_cut_False", lambda: synth.tail_frames(recover=False))
        video = synth.mux_tone(cut, self.tmp / "tail_long_audio.mp4", duration=3,
                               shortest=False)
        out, rows, run = self.bug(video, "tail-long-audio")
        # fixture guard: the container duration is the 3 s audio track's
        self.assertAlmostEqual(run["video"]["duration"], 3.0, delta=0.05)
        (iv,) = self.intervals(run, "black")
        self.assertFalse(iv["end_observed"], iv)
        self.assertTrue(run["video_end_proven"])
        self.assertAlmostEqual(iv["end_s"], 1.0, delta=FRAME_MS / 1000)
        self.assertAlmostEqual(iv["duration_s"], 0.5, delta=FRAME_MS / 1000)
        last = [r for r in rows if r["kind"] == "frame"][-1]
        self.assertLessEqual(float(last["shown_for_s"]), 0.5 + FRAME_MS / 1000, last)
        _, _, run = self.bug(video, "tail-long-audio-ranged", "--range", "0-0.8")
        (iv,) = self.intervals(run, "black")
        self.assertAlmostEqual(iv["end_s"], 0.8, delta=1e-6)

    def test_nonzero_start_time_shares_the_detector_origin(self):
        path = self.tmp / "tail_ts5.mp4"
        synth.encode(path, synth.tail_frames(recover=False), ts_offset=5)
        out, _, run = self.bug(path, "tail-ts5")
        self.assertAlmostEqual(run["video"]["start_time"], 5.0, delta=0.05)  # fixture guard
        (iv,) = self.intervals(run, "black")
        self.assertTrue(run["video_end_proven"], run["video_end_note"])
        self.assert_span(iv, 0.5, 1.0, observed=False)
        self.assertAlmostEqual(iv["duration_s"], 0.5, delta=FRAME_MS / 1000)
        self.assertTrue(iv["file"].endswith("_0.500s.png") and (out / iv["file"]).exists(), iv)
        _, _, run = self.bug(path, "tail-ts5-ranged", "--range", "0-0.8")
        (iv,) = self.intervals(run, "black")
        self.assertAlmostEqual(iv["end_s"], 0.8, delta=1e-6)

    def test_bframe_reordering_keeps_the_last_frame(self):
        path = self.tmp / "tail_bframes.mp4"
        synth.encode(path, synth.tail_frames(recover=False), x264_params="b-adapt=0:bframes=3")
        listing = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                  "-show_entries", "packet=pts_time", "-of", "csv=p=0",
                                  str(path)], capture_output=True, text=True, check=True).stdout
        pts = [float(x.strip(",")) for x in listing.split()]
        self.assertLess(pts[-1], max(pts), "fixture no longer reorders packets")  # guard
        _, _, run = self.bug(path, "tail-bframes")
        self.assertTrue(run["video_end_proven"], run["video_end_note"])
        self.assertAlmostEqual(run["video_end_s"], 1.0, delta=0.002)
        (iv,) = self.intervals(run, "black")
        self.assertAlmostEqual(iv["duration_s"], 0.5, delta=0.002)

    def test_one_video_stream_for_every_measurement(self):
        """Two video tracks: a 1 s still first track and a 3 s default second track,
        black from 0.5 s to its end. The default track is analysed, and its packets,
        not the first track's, bound the trailing black run."""
        first = self.tmp / "mt_first.mp4"
        synth.encode(first, synth.card_frames(lambda t: 0.0, 1.0, "still"))
        tail = synth.tail_frames(recover=False)
        second = self.tmp / "mt_second.mp4"
        synth.encode(second, tail[:30] + [tail[-1]] * 150)
        video = self.tmp / "multitrack.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(first), "-i", str(second),
                        "-map", "0:v", "-map", "1:v", "-c", "copy", "-disposition:v:0", "0",
                        "-disposition:v:1", "default", str(video)], check=True)
        listing = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v",
                                  "-show_entries", "stream=index,duration:stream_disposition=default",
                                  "-of", "compact=p=0", str(video)],
                                 capture_output=True, text=True, check=True).stdout.splitlines()
        # fixture guard: the default track is not the first, and lasts longer
        self.assertEqual(listing, ["index=0|duration=1.000000|disposition:default=0",
                                   "index=1|duration=3.000000|disposition:default=1"])
        out, _, run = self.bug(video, "multitrack-out")
        self.assertEqual((run["video"]["vindex"], run["video"]["video_streams"]), (1, 2))
        self.assertTrue(run["video_end_proven"], run["video_end_note"])
        self.assertAlmostEqual(run["video_end_s"], 3.0, delta=0.002)
        (iv,) = self.intervals(run, "black")
        self.assert_span(iv, 0.5, 3.0, observed=False)
        self.assertLess(gray_mean(out / iv["file"]), 30)   # the black frame, from track 1
        self.assertIn("video stream #1 of 2", (out / "summary.md").read_text())

    def test_silence_gap_and_trailing_silence(self):
        """Silence boundaries are checked within 50 ms: an AAC frame is 1024 samples
        (21 ms at 48 kHz), plus encoder smear around the muted edges."""
        base = self.video("triage", synth.triage_frames)
        gap = synth.mux_tone(base, self.tmp / "triage_gap.mp4", duration=7, silent=(2.0, 4.5))
        _, _, run = self.bug(gap, "triage-gap")
        (iv,) = self.intervals(run, "silence")
        self.assert_span(iv, 2.0, 4.5, observed=True, tol=0.05)
        self.assertIsNotNone(run["detectors"]["silence"])
        tail = synth.mux_tone(base, self.tmp / "triage_tail.mp4", duration=7,
                              silent=(4.5, 7.0))
        _, _, run = self.bug(tail, "triage-tail")
        (iv,) = self.intervals(run, "silence")
        self.assertFalse(iv["end_observed"], iv)
        self.assertAlmostEqual(iv["start_s"], 4.5, delta=0.05)
        self.assertAlmostEqual(iv["end_s"], 7.0, delta=0.05)

    def test_more_black_intervals_than_budget(self):
        video = self.video("black_flashes", lambda: synth.black_flash_frames(6))
        out, rows, run = self.bug(video, "black-budget", "--max-frames", "4")
        blacks = [r for r in rows if r["kind"] == "black"]
        self.assertEqual(len(blacks), 6)
        self.assertLessEqual(len(list((out / "frames").glob("*.png"))), 4)
        self.assertTrue(run["cap_hit"])
        no_image = sum(1 for r in blacks if not r["file"])
        self.assertEqual(run["black_images_omitted"], no_image)
        # start + end + two black frames fill the budget: the ranking is pinned
        self.assertEqual(no_image, 4)
        self.assertTrue(all("no image: --max-frames 4 reached" in r["why"]
                            for r in blacks if not r["file"]))
        self.assertIn("Warning: 4 black intervals have no image (--max-frames 4 reached)",
                      (out / "summary.md").read_text())


@functools.lru_cache(maxsize=None)
def showinfo_prints_duration() -> bool:
    """Whether this ffmpeg's showinfo reports frame durations (ffmpeg 9 does, 5.1
    does not), which decides how exactly the end of a video is known."""
    log = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-f", "lavfi", "-i",
                          "testsrc=size=16x16:rate=10:duration=0.3", "-vf", "showinfo",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    frames = core.parse_showinfo_frames(log)
    assert frames, log[-500:]
    return any(f.duration for f in frames)


def png_gray(png: Path) -> tuple[bytes, int, int]:
    """The 8-bit gray pixels of a PNG, with its size (read from the file)."""
    w, h = core.png_size(png.read_bytes()[:24])
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(png), "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    assert len(raw) == w * h, (png, len(raw), w, h)
    return raw, w, h


def mad(a: bytes, b: bytes) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def region(gray: bytes, w: int, box) -> bytes:
    x, y, cw, ch = box
    return b"".join(gray[(y + r) * w + x:(y + r) * w + x + cw] for r in range(ch))


def rot90(gray: bytes, w: int, h: int, clockwise: bool) -> bytes:
    """gray (w x h) turned a quarter turn: the result is h x w."""
    out = bytearray(w * h)
    for yy in range(w):
        for xx in range(h):
            src = (h - 1 - xx) * w + yy if clockwise else xx * w + (w - 1 - yy)
            out[yy * h + xx] = gray[src]
    return bytes(out)


def read_manifest(frames_dir: Path) -> list[dict]:
    with open(frames_dir / "frames.tsv", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def size_changing_video(tmp: Path) -> Path:
    """A stream whose frames change size mid-way (160x96 for 0.1 s, then 200x120),
    the probe reporting only the first size."""
    path = tmp / "size_change.mp4"
    if not path.exists():
        parts = []
        for i, (w, h) in enumerate([(160, 96), (200, 120)]):
            part = tmp / f"size_part{i}.h264"
            # no B-frames: a raw stream's generated timestamps then follow decode order
            synth.encode(part, [synth.code_frame(k + 6 * i, w=w, h=h) for k in range(6)],
                         w=w, h=h, x264_params="bframes=0")
            parts.append(part.read_bytes())
        joined = tmp / "size_change.h264"
        joined.write_bytes(b"".join(parts))
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-r", "60",
                        "-i", str(joined), "-c", "copy", str(path)], check=True)
    return path


class _ManifestChecks:
    def assert_manifest_binds_files(self, frames_dir: Path, rows: list[dict], *, src, box):
        """Every row names a written PNG whose size, hash and name time it records."""
        self.assertTrue(rows)
        for r in rows:
            path = frames_dir / r["file"]
            data = path.read_bytes()
            ow, oh = core.png_size(data[:24])
            self.assertEqual(r["sha256"], hashlib.sha256(data).hexdigest(), r["file"])
            self.assertEqual((int(r["out_w"]), int(r["out_h"])), (ow, oh), r["file"])
            self.assertEqual((int(r["src_w"]), int(r["src_h"])), src)
            self.assertEqual(tuple(int(r[k]) for k in ("crop_x", "crop_y", "crop_w", "crop_h")),
                             box)
            self.assertEqual(r["scale_x"], f"{ow / box[2]:.6f}")
            self.assertEqual(r["scale_y"], f"{oh / box[3]:.6f}")
            self.assertEqual(core.parse_frame_name(r["file"]).ms, int(r["t_ms"]), r["file"])


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe not installed")
class FramesMode(_VideoCase, _ManifestChecks):
    """`frames`: every native frame (or the frame on screen at T) at full resolution.
    Each fixture frame carries its own code in pixels, so which source frame an
    image is never depends on its file name."""

    def numbered(self):
        return self.video("numbered", lambda: synth.numbered_frames(120))

    def held_vfr(self):
        return self.video("held_vfr", synth.held_numbered_frames, vfr=True)

    def frames(self, video, out_name, *extra):
        out = self.tmp / out_name
        cp = self.cli_ok("frames", video, "--out", out, *extra)
        return out, read_manifest(out / "frames"), json.loads((out / "run.json").read_text()), cp

    def codes(self, out, rows):
        return [synth.decode_code(*png_gray(out / "frames" / r["file"])) for r in rows]

    def test_range_writes_every_native_frame_named_by_its_pts(self):
        out, rows, run, cp = self.frames(self.numbered(), "fr-range", "--range", "0.5-1.0")
        self.assertEqual(len(rows), 30)
        codes = self.codes(out, rows)
        self.assertEqual(codes, list(range(30, 60)))          # every frame, in order
        for r, code in zip(rows, codes):
            ms = core.ms_round(Fraction(code, synth.FPS))
            self.assertEqual((int(r["t_ms"]), r["file"]), (ms, core.frames_name(ms)))
            self.assertEqual(r["time_source"], "pts*time_base")
        self.assertEqual((rows[0]["file"], rows[-1]["file"]), ("t00000500.png", "t00000983.png"))
        # the pixels are the generator's frame, not a neighbour's
        for r, code in list(zip(rows, codes))[::7]:
            gray, _, _ = png_gray(out / "frames" / r["file"])
            self.assertLess(mad(gray, synth.code_frame(code)), 3, r["file"])
            self.assertGreater(mad(gray, synth.code_frame(code - 1)), 10)
            self.assertGreater(mad(gray, synth.code_frame(code + 1)), 10)
        self.assert_manifest_binds_files(out / "frames", rows, src=(360, 800),
                                         box=(0, 0, 360, 800))
        self.assertFalse(run["cap_hit"])
        self.assertEqual((run["frames"], run["omitted"]), (30, 0))
        self.assertEqual(run["manifest"], "frames/frames.tsv")
        self.assertIn("about 377 image tokens each", cp.stdout)

    def test_vfr_names_carry_real_pts_not_index_times_rate(self):
        video = self.held_vfr()
        info = json.loads(run_cli("info", video).stdout)
        starts = [Fraction(s, synth.FPS) for s in synth.NUMBERED_STARTS]
        # fixture guard: index x the average frame interval misplaces some frames
        self.assertTrue(any(abs(k / info["avg_fps"] - float(s)) > 1 / synth.FPS
                            for k, s in enumerate(starts)), info["avg_fps"])
        out, rows, _, _ = self.frames(video, "fr-vfr", "--range", "0-1")
        codes = self.codes(out, rows)
        self.assertEqual(codes, list(range(len(starts))))
        for r, code in zip(rows, codes):
            self.assertEqual(int(r["t_ms"]), core.ms_round(starts[code]), r)
            self.assertEqual(core.parse_frame_name(r["file"]).ms, core.ms_round(starts[code]))

    def test_at_resolves_the_frame_on_screen(self):
        # code 4 is presented at 9/60 = 0.15 s and held to 0.3 s; code 3 from 7/60 s
        out, rows, run, _ = self.frames(self.held_vfr(), "fr-at", "--at", "0.2,0.15,0.1499,0.2")
        self.assertEqual(self.codes(out, rows), [3, 4])
        self.assertEqual([r["file"] for r in rows], ["t00000117.png", "t00000150.png"])
        self.assertEqual([(q["at"], q["file"]) for q in run["requested"]], [
            ("0.2", "frames/t00000150.png"), ("0.15", "frames/t00000150.png"),
            ("0.1499", "frames/t00000117.png"), ("0.2", "frames/t00000150.png")])
        self.assertTrue(all(q["on_screen_proven"] for q in run["requested"]))

    def test_exact_time_boundaries_not_rounded_milliseconds(self):
        video = self.numbered()
        # the 1/30 s frame's name rounds to 33 ms, but it is not on screen at 0.033 s
        out, rows, _, _ = self.frames(video, "fr-b033", "--at", "0.033")
        self.assertEqual((self.codes(out, rows), rows[0]["file"]), ([1], "t00000017.png"))
        out, rows, _, _ = self.frames(video, "fr-b034", "--at", "0.034")
        self.assertEqual(self.codes(out, rows), [2])
        # 1/60 s (16.667 ms) is before 0.017: excluded, although its name says 17
        out, rows, _, _ = self.frames(video, "fr-brange", "--range", "0.017-0.034")
        self.assertEqual(self.codes(out, rows), [2])

    def test_video_end_is_exclusive_and_only_a_proven_end_rejects(self):
        video = self.video("numbered_1s", lambda: synth.numbered_frames(60))   # ends at 1.000 s
        # on any ffmpeg: well inside the last frame is proven, well past the end rejected
        out, rows, run, _ = self.frames(video, "fr-end-in", "--at", "0.99")
        self.assertEqual(self.codes(out, rows), [59])
        self.assertTrue(run["requested"][0]["on_screen_proven"])
        cp = run_cli("frames", video, "--at", "1.5", "--out", self.tmp / "fr-end-far")
        self.assertEqual(cp.returncode, 1, cp.stderr)
        self.assertIn("is past the video end: the last frame is presented at 0.983333 s until "
                      "1.000000 s", cp.stderr)
        self.assertFalse((self.tmp / "fr-end-far").exists())
        if not showinfo_prints_duration():
            # the end is known only from packets, to 6 decimals: these are undecided
            # (ShowinfoWithoutDuration pins that band on every host)
            for i, t in enumerate(("0.999999", "1", "1.0000005")):
                with self.subTest(at=t):
                    _, _, run, _ = self.frames(video, f"fr-end-band{i}", "--at", t)
                    self.assertFalse(run["requested"][0]["on_screen_proven"])
            return
        # the last frame's own exact duration decides, its end exclusive
        _, _, run, _ = self.frames(video, "fr-end-just-in", "--at", "0.999999")
        self.assertTrue(run["requested"][0]["on_screen_proven"])
        for t in ("1", "1.0000005"):
            with self.subTest(at=t):
                cp = run_cli("frames", video, "--at", t, "--out", self.tmp / "fr-end-past")
                self.assertEqual(cp.returncode, 1, cp.stderr)
                self.assertIn("is past the video end: the last frame is presented at "
                              "0.983333 s until 1.000000 s", cp.stderr)
                self.assertFalse((self.tmp / "fr-end-past").exists())

    def test_unproven_end_is_labelled_never_used_to_reject(self):
        raw = self.tmp / "numbered_1s.h264"
        if not raw.exists():
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i",
                            str(self.video("numbered_1s", lambda: synth.numbered_frames(60))),
                            "-c", "copy", "-bsf:v", "h264_mp4toannexb", str(raw)], check=True)
        # fixture guard: a raw stream has no container duration and no packet times
        fmt = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", str(raw)], capture_output=True, text=True)
        self.assertEqual(fmt.stdout.strip(), "N/A")
        out, rows, run, _ = self.frames(raw, "fr-raw", "--at", "0.2,5")
        self.assertEqual(len(rows), 2)
        inside, past = run["requested"]
        self.assertTrue(inside["on_screen_proven"])          # within its own duration
        self.assertFalse(past["on_screen_proven"])           # not provably past the end either
        self.assertIn("whether a later frame exists is not known", past["unproven_because"])
        self.assertIn("on screen at 5 s not proven", (out / "summary.md").read_text())

    def test_mid_stream_size_change_is_refused_not_rescaled(self):
        video = size_changing_video(self.tmp)
        info = json.loads(run_cli("info", video).stdout)
        self.assertEqual((info["width"], info["height"]), (160, 96))      # fixture guard
        log = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(video), "-vf",
                              "showinfo", "-f", "null", "-"], capture_output=True, text=True)
        self.assertIn("s:200x120", log.stderr)                             # fixture guard
        out = self.tmp / "fr-sizechg"
        cp = run_cli("frames", video, "--range", "0-1", "--out", out)
        self.assertEqual(cp.returncode, 1, cp.stderr)
        self.assertIn("is 200x120, but the video was probed as 160x96: the frame size changes "
                      "mid-stream", cp.stderr)
        self.assertFalse(out.exists())
        # frames from before the change are still fine
        out, rows, _, _ = self.frames(video, "fr-sizechg-early", "--range", "0-0.05")
        self.assertEqual(self.codes(out, rows), [0, 1, 2])
        self.assert_manifest_binds_files(out / "frames", rows, src=(160, 96), box=(0, 0, 160, 96))

    def marker_centroids(self, png: Path, box):
        gray, w, h = png_gray(png)
        x0, y0, cw, ch = box
        got = []
        for mx, my in synth.MARKERS:
            if x0 <= mx and mx + synth.MARKER <= x0 + cw and y0 <= my and my + synth.MARKER <= y0 + ch:
                want = (mx - x0 + 2.5, my - y0 + 2.5)
                got.append((want, synth.dark_centroid(gray, w, h, *want)))
        return (w, h), got

    def assert_centroids(self, got, n):
        self.assertEqual(len(got), n)
        for want, c in got:
            self.assertIsNotNone(c, want)
            self.assertAlmostEqual(c[0], want[0], delta=0.3, msg=(want, c))
            self.assertAlmostEqual(c[1], want[1], delta=0.3, msg=(want, c))

    def test_odd_roi_and_crop_are_pixel_exact(self):
        video = self.video("markers", synth.marker_frames)
        # premise: uncropped, every marker sits where it was drawn
        out, rows, _, _ = self.frames(video, "fr-mk-full", "--at", "0")
        size, got = self.marker_centroids(out / "frames" / rows[0]["file"], (0, 0, 360, 800))
        self.assertEqual(size, (360, 800))
        self.assert_centroids(got, len(synth.MARKERS))
        # an odd offset and an odd size in both axes
        box = (37, 151, 201, 243)
        out, rows, _, _ = self.frames(video, "fr-mk-roi", "--at", "0", "--roi",
                                      ",".join(map(str, box)))
        size, got = self.marker_centroids(out / "frames" / rows[0]["file"], box)
        self.assertEqual(size, (201, 243))
        self.assert_centroids(got, 3)
        self.assert_manifest_binds_files(out / "frames", rows, src=(360, 800), box=box)
        self.assertEqual((rows[0]["scale_x"], rows[0]["scale_y"]), ("1.000000", "1.000000"))
        # odd crop flags
        out, rows, _, _ = self.frames(video, "fr-mk-crop", "--at", "0", "--crop-top", "23",
                                      "--crop-bottom", "11")
        size, got = self.marker_centroids(out / "frames" / rows[0]["file"], (0, 23, 360, 766))
        self.assertEqual(size, (360, 766))
        self.assert_centroids(got, len(synth.MARKERS))
        self.assert_manifest_binds_files(out / "frames", rows, src=(360, 800),
                                         box=(0, 23, 360, 766))

    def test_max_frames_truncation_sets_cap_hit(self):
        out, rows, run, _ = self.frames(self.numbered(), "fr-cap", "--range", "0-1",
                                        "--max-frames", "10")
        self.assertEqual([r["file"] for r in rows], [core.frames_name(core.ms_round(
            Fraction(i, synth.FPS))) for i in range(10)])
        self.assertTrue(run["cap_hit"])
        self.assertEqual((run["frames"], run["omitted"]), (10, 50))
        self.assertEqual((run["omitted_from_s"], run["omitted_to_s"]), ("0.166667", "0.983333"))
        summary = (out / "summary.md").read_text()
        self.assertIn("50 more frames presented from 0.166667 s to 0.983333 s", summary)
        # the shortest decimal after the last written frame (0.150) and no later than
        # the first omitted one (0.1667)
        self.assertIn("Continue with --range 0.151-1", summary)

    def test_continuation_range_always_moves_past_the_written_frames(self):
        # three frames 0, 1.49 and 1.51 ms apart-ish, with distinct ms names
        video = self.tmp / "close_pts.mp4"
        if not video.exists():
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                            "-i", "testsrc=size=64x64:rate=100", "-frames:v", "3", "-vf",
                            "settb=1/100000,setpts='if(eq(N\\,0)\\,0\\,if(eq(N\\,1)\\,149\\,151))'",
                            "-fps_mode", "passthrough", "-enc_time_base", "1/100000",
                            "-video_track_timescale", "100000", "-c:v", "libx264", "-bf", "0",
                            str(video)], check=True)
        pk = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "packet=pts", "-of",
                             "csv=p=0", str(video)], capture_output=True, text=True, check=True)
        self.assertEqual(pk.stdout.split(), ["0", "149", "151"])   # fixture guard
        rng, written = "0-0.01", []
        for i in range(5):
            out, rows, _, _ = self.frames(video, f"fr-cont{i}", "--range", rng,
                                          "--max-frames", "1")
            written += [int(r["pts"]) for r in rows]
            m = re.search(r"Continue with --range (\S+)", (out / "summary.md").read_text())
            if not m:
                break
            rng = m.group(1).rstrip(",")
        self.assertEqual(written, [0, 149, 151])        # each frame once, then it stops

    def test_image_budget_for_a_phone_frame(self):
        video = self.tmp / "phone.mp4"     # self.video() encodes at the default size only
        if not video.exists():
            synth.encode(video, synth.numbered_frames(3, w=1080, h=2400), w=1080, h=2400)
        out, rows, run, cp = self.frames(video, "fr-phone", "--at", "0")
        self.assertEqual(self.codes(out, rows), [0])
        self.assertEqual((run["image_budget"]["tokens"], run["image_budget"]["exceeds"]),
                         (3354, ["standard"]))
        summary = (out / "summary.md").read_text()
        self.assertIn("each frame is 1080x2400, about 3354 image tokens", summary)
        self.assertIn("over the standard tier's limit (long edge 1568 px, 1568 visual tokens)",
                      summary)
        self.assertNotIn("high-resolution tier's limit", summary)
        self.assertNotIn("many-image", summary)
        self.assertIn("about 3354 image tokens each; over the standard limit", cp.stdout)

    def test_rotated_recording_geometry_is_in_display_orientation(self):
        src = self.numbered()
        rot = self.tmp / "numbered_rot90.mp4"
        if not rot.exists():
            cp = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                                 "-display_rotation", "90", "-i", str(src), "-c", "copy",
                                 str(rot)], capture_output=True, text=True)
            if cp.returncode:
                self.skipTest(f"this ffmpeg cannot write a display matrix: {cp.stderr[-200:]}")
        info = json.loads(run_cli("info", rot).stdout)
        if info["rotation"] % 180 == 0:
            self.skipTest("no rotation side data in the remuxed file")
        self.assertEqual((info["width"], info["height"]), (800, 360))   # display orientation
        out, rows, _, _ = self.frames(rot, "fr-rot", "--at", "0.05")
        self.assertEqual(int(rows[0]["t_ms"]), 50)                       # same time as unrotated
        gray, w, h = png_gray(out / "frames" / rows[0]["file"])
        self.assertEqual((w, h), (800, 360))
        turns = {cw: rot90(synth.code_frame(3), 360, 800, cw) for cw in (True, False)}
        cw = min(turns, key=lambda k: mad(gray, turns[k]))
        self.assertLess(mad(gray, turns[cw]), 3)                         # frame 3, turned
        self.assertGreater(mad(gray, rot90(synth.code_frame(2), 360, 800, cw)), 10)
        self.assert_manifest_binds_files(out / "frames", rows, src=(800, 360),
                                         box=(0, 0, 800, 360))
        # a ROI in display coordinates, odd in both axes
        box = (101, 37, 203, 151)
        out, rows, _, _ = self.frames(rot, "fr-rot-roi", "--at", "0.05", "--roi",
                                      ",".join(map(str, box)))
        crop, cw_, ch_ = png_gray(out / "frames" / rows[0]["file"])
        self.assertEqual((cw_, ch_), (203, 151))
        self.assertLess(mad(crop, region(turns[cw], 800, box)), 3)
        self.assert_manifest_binds_files(out / "frames", rows, src=(800, 360), box=box)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe not installed")
class ShowinfoWithoutDuration(_VideoCase):
    """ffmpeg 5.1, the oldest supported version, prints no `duration:` field in
    showinfo (release/5.1 libavfilter/vf_showinfo.c). That format is simulated by
    removing the field from the real log through the module's own ffmpeg() call,
    so the end of the video must come from its packets instead."""

    def run_stripped(self, *args):
        import video_prep as vp
        logs = []
        orig = vp.ffmpeg

        def stripped(a, **kw):
            out, err = orig(a, **kw)
            # a no-op on an ffmpeg that already prints no duration (5.1)
            new = re.sub(r"duration:\s*-?\d+ duration_time:\S+ ", "", err)
            logs.append(new)
            return out, new
        err = io.StringIO()
        with mock.patch.object(vp, "ffmpeg", stripped), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = vp.main([str(a) for a in args])
        # premise: the code saw showinfo frame lines, none of them with a duration
        shown = [f for log in logs for f in core.parse_showinfo_frames(log)]
        self.assertTrue(shown)
        self.assertTrue(all(f.duration is None for f in shown))
        return rc, err.getvalue()

    def test_packet_end_is_used_when_frames_carry_no_duration(self):
        video = self.video("numbered_1s", lambda: synth.numbered_frames(60))   # ends at 1.000 s
        out = self.tmp / "d51-in"
        rc, err = self.run_stripped("frames", video, "--at", "0.99", "--out", out)
        self.assertEqual(rc, 0, err)
        (q,) = json.loads((out / "run.json").read_text())["requested"]
        self.assertTrue(q["on_screen_proven"])
        out = self.tmp / "d51-past"
        rc, err = self.run_stripped("frames", video, "--at", "2", "--out", out)
        self.assertEqual(rc, 1, err)
        self.assertIn("is past the video end: the last frame is presented at 0.983333 s until "
                      "1.000000 s (from the video's packets)", err)
        self.assertFalse(out.exists())
        # the packets give the end to 6 decimals: a time that close is not decided
        for i, t in enumerate(("0.999999", "1", "1.0000005")):
            with self.subTest(at=t):
                out = self.tmp / f"d51-edge{i}"
                rc, err = self.run_stripped("frames", video, "--at", t, "--out", out)
                self.assertEqual(rc, 0, err)
                (q,) = json.loads((out / "run.json").read_text())["requested"]
                self.assertFalse(q["on_screen_proven"])
                self.assertIn("within 2 µs of the video end", q["unproven_because"])

    def test_genuinely_unknown_end_stays_unproven(self):
        raw = self.tmp / "numbered_1s.h264"
        if not raw.exists():
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i",
                            str(self.video("numbered_1s", lambda: synth.numbered_frames(60))),
                            "-c", "copy", "-bsf:v", "h264_mp4toannexb", str(raw)], check=True)
        out = self.tmp / "d51-raw"
        rc, err = self.run_stripped("frames", raw, "--at", "0.2,5", "--out", out)
        self.assertEqual(rc, 0, err)
        _, past = json.loads((out / "run.json").read_text())["requested"]
        self.assertFalse(past["on_screen_proven"])
        self.assertIn("whether a later frame exists is not known", past["unproven_because"])


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe not installed")
class ManifestsAndCaps(_VideoCase, _ManifestChecks):
    """bug and anim write the same frames.tsv for the frames they save, and anim
    reports what --max-segments / --max-view-frames left out."""

    def test_bug_manifest_matches_the_written_frames(self):
        video = self.video("bug", synth.bug_frames)
        out = self.tmp / "bug-manifest"
        self.cli_ok("bug", video, "--out", out, "--view-size", "400")
        rows = read_manifest(out / "frames")
        with open(out / "timeline.tsv") as fh:
            files = [r["file"] for r in csv.DictReader(fh, delimiter="\t") if r["kind"] == "frame"]
        self.assertEqual(sorted(f"frames/{r['file']}" for r in rows), sorted(files))
        self.assert_manifest_binds_files(out / "frames", rows, src=(360, 800),
                                         box=(0, 0, 360, 800))
        self.assertEqual({(r["out_w"], r["out_h"], r["scale_x"]) for r in rows},
                         {("180", "400", "0.500000")})
        self.assertEqual(json.loads((out / "run.json").read_text())["manifest"],
                         "frames/frames.tsv")

    def test_size_change_mid_stream_records_no_geometry(self):
        video = size_changing_video(self.tmp)
        out = self.tmp / "bug-sizechg"
        self.cli_ok("bug", video, "--out", out)
        run = json.loads((out / "run.json").read_text())
        self.assertIsNone(run["manifest"])
        self.assertIn("the frame size changes mid-stream", run["manifest_note"])
        self.assertFalse((out / "frames" / "frames.tsv").exists())
        self.assertIn("- Warning: no frames/frames.tsv (no geometry is recorded): ",
                      (out / "summary.md").read_text())
        # premise control: the same check passes on a constant-size clip (see
        # test_bug_manifest_matches_the_written_frames), so this is the size change
        out = self.tmp / "anim-sizechg"
        self.cli_ok("anim", video, "--out", out)
        run = json.loads((out / "run.json").read_text())
        # fixture guard: every frame differs, so the one motion segment spans the size
        # change (from 0.1 s) and its saved frames include frames of both sizes
        self.assertEqual(run["segments"], ["s01"])
        saved = sorted((out / "s01" / "frames").glob("f*.png"))
        times = [core.parse_frame_name(p.name).ms for p in saved]
        self.assertTrue(min(times) < 100 <= max(times), times)
        # that segment is refused: no manifest, a warning naming the change, not listed
        self.assertFalse((out / "s01" / "frames" / "frames.tsv").exists())
        fit = json.loads((out / "s01" / "fit.json").read_text())
        self.assertTrue(any(w.startswith("no frames/frames.tsv (no geometry is recorded): ")
                            and "the frame size changes mid-stream" in w
                            for w in fit["warnings"]), fit["warnings"])
        self.assertEqual(run["manifests"], [])

    def test_anim_manifest_box_is_the_odd_roi_and_pixel_exact(self):
        video = self.video("markers_slide", lambda: synth.marker_frames(60, slide=True))
        out = self.tmp / "anim-markers"
        box = (37, 151, 201, 243)
        self.cli_ok("anim", video, "--out", out, "--roi", ",".join(map(str, box)))
        rows = read_manifest(out / "s01" / "frames")
        self.assert_manifest_binds_files(out / "s01" / "frames", rows, src=(360, 800), box=box)
        first = min(rows, key=lambda r: int(r["t_ms"]))
        gray, w, h = png_gray(out / "s01" / "frames" / first["file"])
        self.assertEqual((w, h), (201, 243))
        n = 0
        for mx, my in synth.MARKERS[:3]:
            want = (mx - box[0] + 2.5, my - box[1] + 2.5)
            c = synth.dark_centroid(gray, w, h, *want)
            self.assertAlmostEqual(c[0], want[0], delta=0.3, msg=(want, c))
            self.assertAlmostEqual(c[1], want[1], delta=0.3, msg=(want, c))
            n += 1
        self.assertEqual(n, 3)
        run = json.loads((out / "run.json").read_text())
        self.assertEqual(run["manifests"], ["s01/frames/frames.tsv"])
        # the analysis path crops yuv420p directly (no RGB step), so this is what
        # proves its region is the requested one: the card sweeps x [60, 220) and
        # y [250, 300) in the source, i.e. 23..182 x 99..148 (inclusive) in the ROI
        with open(out / "s01" / "curve.tsv", newline="") as fh:
            first = next(csv.DictReader(fh, delimiter="\t"))
        self.assertEqual(first["bbox_vs_end"], "23,99,182,148")

    def slide_right(self):
        return self.video("slide_right", lambda: synth.card_frames(
            synth.tween(synth.EASE_OUT, 0.5, 0.3), 1.4, "right"))

    def anim_run(self, video, name, *extra):
        out = self.tmp / name
        self.cli_ok("anim", video, "--out", out, *extra)
        return out, json.loads((out / "run.json").read_text())

    def test_default_run_is_not_capped(self):
        _, run = self.anim_run(self.slide_right(), "cap-none")
        self.assertFalse(run["cap_hit"])
        self.assertEqual(run["caps"]["max_segments"]["skipped"], 0)
        self.assertEqual(run["caps"]["max_view_frames"]["thinned"], [])

    def test_thinned_view_frames_set_cap_hit_and_give_the_frames_range(self):
        out, run = self.anim_run(self.slide_right(), "cap-view", "--max-view-frames", "5")
        self.assertTrue(run["cap_hit"])
        (th,) = run["caps"]["max_view_frames"]["thinned"]
        self.assertEqual(th["segment"], "s01")
        self.assertLess(th["saved"], th["of"])
        self.assertEqual(len(read_manifest(out / "s01" / "frames")), th["saved"])
        summary = (out / "summary.md").read_text()
        self.assertIn(f"- saved frames: {th['saved']} of {th['of']} (thinned by "
                      "--max-view-frames 5)", summary)
        self.assertIn(f"--range {th['range']}", summary)
        a, b = (float(v) for v in th["range"].split("-"))
        self.assertLess(a, 0.5)          # the motion starts at 0.5 s
        self.assertGreater(b, 0.8)       # and settles by 0.8 s

    def test_skipped_segments_set_cap_hit(self):
        progress = synth.chain(synth.tween(synth.EASE_OUT, 0.5, 0.3),
                               synth.tween(synth.LINEAR, 1.5, 0.3))
        video = self.video("two", lambda: synth.card_frames(lambda t: progress(t) / 2, 2.4,
                                                              "right"))
        out, run = self.anim_run(video, "cap-seg", "--max-segments", "1")
        self.assertTrue(run["cap_hit"])
        segs = run["caps"]["max_segments"]
        self.assertEqual(segs["skipped"], 1)
        self.assertAlmostEqual(segs["first_skipped_s"], 1.517, delta=0.02)
        self.assertIn("narrow with --range or raise --max-segments",
                      (out / "summary.md").read_text())


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe not installed")
class InfoAndErrors(_VideoCase):
    def test_info(self):
        video = self.video("still", lambda: synth.card_frames(lambda t: 0.0, 1.0, "still"))
        cp = run_cli("info", video)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        info = json.loads(cp.stdout)
        self.assertEqual((info["width"], info["height"], info["has_audio"]), (360, 800, False))
        self.assertAlmostEqual(info["avg_fps"], 60.0, delta=0.01)

    def test_wrapper_entry_point(self):
        # the skill calls the bash wrapper, which resolves the framework Python
        video = self.video("still", lambda: synth.card_frames(lambda t: 0.0, 1.0, "still"))
        cp = subprocess.run(["bash", str(WRAPPER), "info", str(video)],
                            capture_output=True, text=True)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertEqual(json.loads(cp.stdout)["width"], 360)

    def test_bad_inputs_fail_cleanly(self):
        video = self.video("still", lambda: synth.card_frames(lambda t: 0.0, 1.0, "still"))
        cases = [
            (("anim", video, "--roi", "300,0,100,100"), 1, "outside the 360x800 frame"),
            (("anim", video, "--window", "2-1"), 1, "END must be after START"),
            (("bug", video, "--crop-top", "900"), 1, "leave nothing"),
            (("bug", self.tmp / "missing.mp4"), 2, "no such file"),
            (("anim", video, "--time-scale", "0"), 2, "must be positive"),
            (("bug", video, "--freeze-min", "0"), 1, "--freeze-min must be a positive"),
            (("bug", video, "--freeze-min", "nan"), 1, "--freeze-min must be a positive"),
            (("bug", video, "--black-min", "-1"), 1, "--black-min must be a number"),
            # argparse's float() accepts these; nan would silently drop every black run
            (("bug", video, "--black-min", "nan"), 1, "--black-min must be a number"),
            (("bug", video, "--black-min", "inf"), 1, "--black-min must be a number"),
            (("frames", video), 2, "one of the arguments --range --at is required"),
            (("frames", video, "--range", "0-1", "--at", "0"), 2, "not allowed with argument"),
            (("frames", video, "--at", "0", "--max-frames", "0"), 1,
             "--max-frames must be at least 1"),
            (("frames", video, "--at", "x"), 1, "--at takes T[,T...] in seconds"),
            (("frames", video, "--at", "-1"), 1, "--at takes T[,T...] in seconds"),
            (("frames", video, "--at", "0,nan"), 1, "--at takes T[,T...] in seconds"),
            (("frames", video, "--range", "2-1"), 1, "END must be after START"),
            (("frames", video, "--range", "a-1"), 1, "--range takes START-END"),
            (("frames", video, "--range", "5-6"), 1, "no frame is presented in 5-6 s"),
            (("frames", video, "--at", "5"), 1, "is past the video end"),
            (("frames", video, "--at", "0", "--roi", "300,0,100,100"), 1,
             "outside the 360x800 frame"),
        ]
        for args, code, msg in cases:
            with self.subTest(args=args[2:]):
                cp = run_cli(*args, "--out", self.tmp / "err-out")
                self.assertEqual(cp.returncode, code, cp.stderr)
                self.assertIn(msg, cp.stderr)
                # options are validated before anything is written
                self.assertFalse((self.tmp / "err-out").exists())

    def test_existing_output_dir_is_never_overwritten(self):
        video = self.video("still", lambda: synth.card_frames(lambda t: 0.0, 1.0, "still"))
        out = self.tmp / "reuse"
        out.mkdir()
        (out / "keep.txt").write_text("user data")
        cp = self.cli_ok("bug", video, "--out", out)
        self.assertEqual((out / "keep.txt").read_text(), "user data")
        self.assertIn(str(self.tmp / "reuse-2"), cp.stdout)


# --------------------------------------------------------------------------- #
# sheet: contact sheets from any folder of images (no ffmpeg needed)

def write_png(path, w, h, pixels=None, *, fill=255):
    """An 8-bit grayscale PNG; pixels is a bytes of w*h values (default: fill)."""
    import struct
    import zlib
    data = pixels if pixels is not None else bytes([fill]) * (w * h)
    raw = b"".join(b"\x00" + data[y * w:(y + 1) * w] for y in range(h))

    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n"
                           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def square_png(path, w, h, x, y, side):
    px = bytearray([255]) * (w * h)
    for yy in range(y, y + side):
        px[yy * w + x:yy * w + x + side] = bytes(side)
    write_png(path, w, h, bytes(px))


def sheet_gray(path):
    """(w, h, bytes) of a sheet as 8-bit gray."""
    with open(path, "rb") as fh:
        w, h = core.png_size(fh.read(24))
    out = subprocess.run(["magick", str(path), "-colorspace", "gray", "-depth", "8", "gray:-"],
                         capture_output=True, check=True).stdout
    return w, h, out


def label_width(text):
    out = subprocess.run(["magick", "-pointsize", "15", f"label:{core.im_label(text)}",
                          "-format", "%w", "info:"], capture_output=True, text=True, check=True)
    return int(out.stdout)


def dirty_borders(path, cell_w, cols):
    """Cell boundaries (x) where anything brighter than the background lies in the
    8 px border between two cells: only an overflowing label can put it there."""
    w, h, g = sheet_gray(path)
    bad = []
    for k in range(1, cols):
        x0 = k * (cell_w + 8)
        if any(g[y * w + x] > 60 for x in range(x0 - 3, x0 + 3) for y in range(h)):
            bad.append(x0)
    return bad


@unittest.skipUnless(HAVE_MAGICK, "ImageMagick (magick) not installed")
class ContactSheets(unittest.TestCase):
    """contact_sheets(), the bug/anim sheet writer, at the real sheet size."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="vp-contact-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_too_many_frames_for_readable_labels_reduce_each_sheet(self):
        import video_prep
        n, per_sheet = 260, 400            # more than one 1600 px sheet can hold
        items = []
        for k in range(1, n + 1):
            path = self.tmp / f"{k:04d}.png"
            write_png(path, 45, 100)
            items.append((path, f"#{k} {k * 0.05:.3f}s\nmotion {0.05:.2f}s"))
        sheets = video_prep.contact_sheets(items, self.tmp, per_sheet, 45, 100)
        self.assertGreater(len(sheets), 1)
        self.assertTrue(any(s[3] for s in sheets))
        start = 0
        for path, s_start, count, _reduced, cols, cell_w in sheets:
            self.assertEqual(s_start, start)
            self.assertLessEqual(count, per_sheet)
            start += count
            w, h = video_prep.checked_sheet_size(path)
            self.assertLessEqual(max(w, h), video_prep.SHEET_MAX_EDGE)
            self.assertEqual(w, min(count, cols) * (cell_w + 8))
            self.assertEqual(dirty_borders(path, cell_w, cols), [], path.name)
        self.assertEqual(start, n)
        self.assertEqual(video_prep.per_sheet_note(sheets, per_sheet),
                         f"- note: --per-sheet {per_sheet} does not fit with readable labels "
                         f"(at most {max(s[2] for s in sheets)} frames a sheet here)")


@unittest.skipUnless(HAVE_MAGICK, "ImageMagick (magick) not installed")
class SheetMode(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="vp-sheet-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def folder(self, name="in"):
        d = self.tmp / name
        d.mkdir()
        return d

    def sheet(self, folder, *extra, out="out"):
        cp = run_cli("sheet", folder, "--out", self.tmp / out, *extra)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        lines = cp.stdout.strip().splitlines()
        self.assertTrue(lines[-1].startswith("SUMMARY: "), cp.stdout)
        self.assertTrue(lines[-2].startswith("tokens: "), cp.stdout)
        o = self.tmp / out
        with open(o / "tiles.tsv", newline="", encoding="utf-8",
                  errors="surrogateescape") as fh:
            tiles = list(csv.DictReader(fh, delimiter="\t"))
        return (o, tiles, (o / "summary.md").read_text(),
                json.loads((o / "run.json").read_text()))

    def assert_sheets_within_limit(self, out, run):
        for s in run["sheets"]:
            with open(out / s, "rb") as fh:
                self.assertLessEqual(max(core.png_size(fh.read(24))), 1600, s)

    def test_folder_order_deltas_gap_and_letterbox(self):
        d = self.folder()
        for ms in (0, 33, 67, 133, 167):              # t00000100 deleted
            write_png(d / f"t{ms:08d}.png", 360, 800)
        square_png(d / "t00000200_crop.png", 200, 100, 10, 10, 50)
        write_png(self.tmp / "src.png", 360, 800)
        subprocess.run(["magick", self.tmp / "src.png", d / "t00000233.jpg"], check=True)
        subprocess.run(["magick", self.tmp / "src.png", d / "t00000267.webp"], check=True)
        out, tiles, summary, run = self.sheet(d, "--per-sheet", "4")

        self.assertEqual(run["sheets"], ["sheet_01.png", "sheet_02.png"])
        self.assertEqual([t["file"] for t in tiles],
                         ["t00000000.png", "t00000033.png", "t00000067.png", "t00000133.png",
                          "t00000167.png", "t00000200_crop.png", "t00000233.jpg",
                          "t00000267.webp"])
        self.assertEqual([t["order"] for t in tiles], [str(i) for i in range(1, 9)])
        self.assertEqual([t["delta_ms"] for t in tiles],
                         ["", "33", "34", "66", "34", "33", "33", "34"])
        self.assertTrue(tiles[0]["label"].endswith("0.000 s first"))
        self.assertTrue(tiles[3]["label"].endswith("0.133 s +66 ms"), tiles[3]["label"])
        self.assertIn("- #4 t00000133.png: +66 ms", summary.split("## Gaps")[1])
        crop = tiles[5]
        self.assertEqual((crop["img_w"], crop["img_h"]), ("200", "100"))
        th_by_full = float(tiles[4]["fit_scale"]) * 800        # same sheet, full-size tile
        self.assertAlmostEqual(float(crop["fit_scale"]),
                               min(int(crop["cell_w"]) / 200, round(th_by_full) / 100), places=2)
        self.assert_sheets_within_limit(out, run)
        self.assertEqual(run["tokens"], sum(core.image_tokens(*core.png_size(
            (out / s).read_bytes()[:24])) for s in run["sheets"]))

        # letterboxed, not stretched: the square stays square on the sheet
        w, h, g = sheet_gray(out / "sheet_02.png")
        dark = [(i % w, i // w) for i, v in enumerate(g) if v < 10]
        self.assertTrue(dark, "premise: the square is on sheet 2")
        xs, ys = [p[0] for p in dark], [p[1] for p in dark]
        bw, bh = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
        self.assertGreater(bw, 50, "the crop was enlarged to fit its cell")
        self.assertLessEqual(abs(bw - bh), 1, (bw, bh))

    def test_untimed_names_come_last_with_index_labels(self):
        d = self.folder()
        for n in ("a.png", "b10.png", "b2.png", "t00000050.png"):
            write_png(d / n, 40, 40)
        out, tiles, summary, run = self.sheet(d)
        self.assertEqual([t["file"] for t in tiles],
                         ["t00000050.png", "a.png", "b2.png", "b10.png"])
        for t in tiles[1:]:
            self.assertTrue(t["label"].endswith("no time in name"), t)
            self.assertEqual((t["t_ms"], t["delta_ms"], t["time_from"]), ("", "", "none"))
        self.assertIn("Warning: 3 images carry no time in their names", summary)
        self.assertEqual(run["untimed"], ["a.png", "b2.png", "b10.png"])

    def test_frames_tsv_marks_edited_images(self):
        d = self.folder()
        write_png(d / "t00000000.png", 40, 40)
        write_png(d / "t00000033.png", 40, 40, fill=128)
        good = hashlib.sha256((d / "t00000000.png").read_bytes()).hexdigest()
        (d / "frames.tsv").write_text("file\tt_ms\tsha256\n"
                                      f"t00000000.png\t0\t{good}\n"
                                      f"t00000033.png\t33\t{'0' * 64}\n")
        _, tiles, summary, run = self.sheet(d)
        self.assertEqual([t["frames_tsv"] for t in tiles], ["match", "edited"])
        self.assertFalse(tiles[0]["label"].endswith("edited"))
        self.assertTrue(tiles[1]["label"].endswith("+33 ms edited"), tiles[1]["label"])
        self.assertIn("recorded SHA-256 matches for 1 (geometry valid), differs for 1", summary)
        self.assertNotIn("frames.tsv", run["ignored"])

    def test_hostile_names_are_staged_and_shown_safely(self):
        d = self.folder()
        names = ["t00000100_" + "x" * 80 + ".png", "t00000200 50%.png", "-x.png",
                 "t00000300[1].png", "a\\b.png"]
        for n in names:
            write_png(d / n, 60, 60)
        _, tiles, _, run = self.sheet(d)
        self.assertEqual(sorted(t["file"] for t in tiles), sorted(names))
        long = next(t for t in tiles if t["file"].startswith("t00000100_"))
        self.assertIn("...", long["label"].split(" | ")[0])
        self.assertLessEqual(label_width(long["label"].split(" | ")[0]),
                             int(long["cell_w"]) - 6)
        self.assertEqual(next(t for t in tiles if "[1]" in t["file"])["time_from"], "none")
        self.assertEqual(next(t for t in tiles if "50%" in t["file"])["t_ms"], "200")

    def test_tiles_tsv_keeps_exact_file_names(self):
        import os
        d = self.folder()
        names = ["t00000000_a\nb.png", "t00000000_a?b.png", "t00000033_tab\there.png",
                 't00000067_"quoted".png', os.fsdecode(b"t00000100_\xff.png")]
        for n in names:
            write_png(d / n, 30, 30)
        out, _, summary, run = self.sheet(d)
        with open(out / "tiles.tsv", newline="", encoding="utf-8",
                  errors="surrogateescape") as fh:
            files = [r["file"] for r in csv.DictReader(fh, delimiter="\t")]
        self.assertEqual(sorted(files), sorted(os.listdir(d)))
        self.assertEqual(len(set(files)), len(names), "two names collapsed into one")
        for f in files:
            self.assertTrue((d / f).is_file(), repr(f))
        self.assertNotIn("\nb.png", summary)            # display text stays one line

    def test_default_output_keeps_a_dotted_folder_name(self):
        d = self.folder("edited.v2")
        write_png(d / "t00000000.png", 30, 30)
        tmpdir = self.tmp / "tmpdir"
        tmpdir.mkdir()
        import os
        cp = subprocess.run([sys.executable, str(SCRIPT), "sheet", str(d)],
                            capture_output=True, text=True,
                            env={**os.environ, "TMPDIR": str(tmpdir)})
        self.assertEqual(cp.returncode, 0, cp.stderr)
        expected = tmpdir / "video-prep" / "edited.v2-sheet" / "summary.md"
        self.assertEqual(cp.stdout.strip().splitlines()[-1], f"SUMMARY: {expected}")
        self.assertTrue(expected.is_file())

    def test_unreadable_image_is_left_out_before_ordering(self):
        d = self.folder()
        write_png(d / "t00000000.png", 360, 800)
        (d / "t00000033.png").write_bytes(bytes(range(256)) * 4)    # not an image
        write_png(d / "t00000066.png", 360, 800)
        out, tiles, summary, run = self.sheet(d)
        self.assertEqual([(t["file"], t["order"], t["delta_ms"]) for t in tiles],
                         [("t00000000.png", "1", ""), ("t00000066.png", "2", "66")])
        self.assertTrue(tiles[1]["label"].endswith("0.066 s +66 ms"))
        self.assertIn("could not be read", summary)
        self.assertIn("t00000033.png", summary)
        self.assertEqual(run["unreadable"], ["t00000033.png"])
        cols = max(int(t["col"]) for t in tiles)
        with open(out / "sheet_01.png", "rb") as fh:
            sw, _ = core.png_size(fh.read(24))
        self.assertEqual(sw, cols * (int(tiles[0]["cell_w"]) + 8))
        self.assertEqual(cols, 2)

    def test_narrow_tiles_keep_labels_inside_their_cells(self):
        d = self.folder()
        for i in range(8):
            write_png(d / f"t{i * 33:08d}_annotated_by_hand.png", 40, 800)
        out, tiles, _, run = self.sheet(d)
        self.assertEqual(run["sheets"], ["sheet_01.png"])
        cell_w, cols = int(tiles[0]["cell_w"]), max(int(t["col"]) for t in tiles)
        self.assertGreater(cols, 1)
        for t in tiles:
            name_line, time_line = t["label"].split(" | ")
            self.assertGreaterEqual(cell_w - 6, label_width(time_line), t)
            self.assertGreaterEqual(cell_w - 6, label_width(name_line), t)
        self.assertEqual(dirty_borders(out / "sheet_01.png", cell_w, cols), [])

        # premise: the check sees an overflowing label (cells as narrow as the
        # images, labels as long as the real ones)
        bad = self.tmp / "bad.png"
        subprocess.run(["magick", "montage", "-background", "#1e1e1e", "-fill", "#f2f2f2",
                        "-pointsize", "15",
                        *[a for i in range(3) for a in ("-label", "#1 t00000000_annotated_by_hand"
                                                        ".png\n0.000 s first", d / sorted(
                                                            p.name for p in d.iterdir())[i])],
                        "-tile", "3x", "-geometry", "30x600+4+4", bad], check=True)
        self.assertNotEqual(dirty_borders(bad, 30, 3), [])

    def test_animated_webp_gives_one_tile(self):
        d = self.folder()
        write_png(d / "t00000000.png", 50, 50)
        write_png(d / "t00000033.png", 50, 50)
        subprocess.run(["magick", "-delay", "10", "-size", "50x50", "xc:white", "xc:black",
                        d / "t00000066.webp"], check=True)
        frames = subprocess.run(["magick", "identify", d / "t00000066.webp"],
                                capture_output=True, text=True, check=True).stdout
        self.assertEqual(len(frames.splitlines()), 2, "premise: a 2-frame webp")
        out, tiles, summary, run = self.sheet(d)
        self.assertEqual(len(tiles), 3)
        self.assertEqual(tiles[2]["frames_in_file"], "2")
        self.assertIn("first frame used for t00000066.webp", summary)
        # the sheet itself shows no second (black) frame: one file, one tile
        _, _, g = sheet_gray(out / "sheet_01.png")
        self.assertGreaterEqual(min(g), 10, "the webp's second frame was drawn as a tile")

    def test_too_many_per_sheet_is_split_with_a_warning(self):
        texts = ["0.000 s first"] + [f"{i * 10 / 1000:.3f} s +10 ms" for i in range(1, 400)]
        out = subprocess.run(["magick", "-pointsize", "15", *[f"label:{t}" for t in texts],
                              "-format", "%w\\n", "info:"],
                             capture_output=True, text=True, check=True).stdout
        w_min = min(int(x) for x in out.split())
        # 20x20 tiles: floor 64 px, so at most 1600 // (64 + 40 + 8) = 14 rows
        cap_upper = (1600 // (w_min + 6 + 8)) * (1600 // (64 + 40 + 8))
        count = cap_upper + 1
        self.assertLessEqual(count, 400, "premise: w_min was measured over these labels")
        self.assertGreater(count, cap_upper)
        d = self.folder()
        for i in range(count):
            write_png(d / f"t{i * 10:08d}.png", 20, 20)
        out, tiles, summary, run = self.sheet(d, "--per-sheet", str(count))
        self.assertGreater(len(run["sheets"]), 1)
        self.assertEqual([t["file"] for t in tiles], [f"t{i * 10:08d}.png" for i in range(count)])
        self.assertIn(f"Warning: --per-sheet {count} does not fit with readable labels", summary)
        self.assertTrue(run["per_sheet_reduced"])
        self.assertEqual(sum(run["tiles_per_sheet"]), count)
        self.assert_sheets_within_limit(out, run)
        for s in run["sheets"]:
            rows = [t for t in tiles if t["sheet"] == s]
            self.assertEqual(dirty_borders(out / s, int(rows[0]["cell_w"]),
                                           max(int(t["col"]) for t in rows)), [], s)

    def test_a_short_last_sheet_is_not_a_reduction(self):
        d = self.folder()
        for i in range(9):
            write_png(d / f"t{i * 33:08d}.png", 360, 800)
        _, _, summary, run = self.sheet(d, "--per-sheet", "8")
        self.assertEqual(run["tiles_per_sheet"], [8, 1])
        self.assertFalse(run["per_sheet_reduced"])
        self.assertNotIn("does not fit", summary)

    def test_tiny_crop_is_included(self):
        d = self.folder()
        write_png(d / "t00000100.png", 10, 10)
        out, tiles, _, run = self.sheet(d)
        self.assertEqual((run["sheets"], len(tiles)), (["sheet_01.png"], 1))
        self.assertEqual(tiles[0]["fit_scale"], "4.000000")
        self.assertGreaterEqual(int(tiles[0]["cell_w"]) - 6,
                                label_width(tiles[0]["label"].split(" | ")[1]))
        self.assert_sheets_within_limit(out, run)

    def test_bad_inputs_fail_cleanly(self):
        empty = self.folder("empty")
        (empty / "notes.txt").write_text("x")
        cases = [(("sheet", self.tmp / "missing"), 2, "no such directory"),
                 (("sheet", empty), 1, "no png, jpg or webp images"),
                 (("sheet", empty, "--per-sheet", "0"), 1, "--per-sheet must be at least 1")]
        bad = self.folder("bad")
        (bad / "t00000000.png").write_bytes(b"not a png")
        cases.append((("sheet", bad), 1, "none of the 1 images could be read"))
        for args, code, msg in cases:
            with self.subTest(args=args[1:]):
                cp = run_cli(*args, "--out", self.tmp / "err-out")
                self.assertEqual(cp.returncode, code, cp.stderr)
                self.assertIn(msg, cp.stderr)
                self.assertFalse((self.tmp / "err-out").exists())


class SheetWithoutMagick(unittest.TestCase):
    def test_refuses_before_writing_anything(self):
        import video_prep
        tmp = Path(tempfile.mkdtemp(prefix="vp-sheet-nomagick-"))
        try:
            write_png(tmp / "t00000000.png", 10, 10)
            err = io.StringIO()
            with mock.patch.object(video_prep, "have_magick", return_value=False), \
                    contextlib.redirect_stderr(err):
                rc = video_prep.main(["sheet", str(tmp), "--out", str(tmp / "out")])
            self.assertEqual(rc, 1)
            self.assertIn("ImageMagick 7", err.getvalue())
            self.assertFalse((tmp / "out").exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)



# --------------------------------------------------------------------------- #
# pick: the visual frame picker (vp_pick.py, pick_page.html, pick_*.js)

PICK_GEOM_COLS = ["file", "t_ms", "pts", "time_source", "src_w", "src_h", "crop_x", "crop_y",
                  "crop_w", "crop_h", "out_w", "out_h", "scale_x", "scale_y", "sha256"]
CHROMIUM = next((shutil.which(n) for n in ("chromium", "chromium-browser", "google-chrome",
                                            "google-chrome-stable") if shutil.which(n)), None)


def chromium_argv(profile: Path, url: str) -> list[str]:
    return [CHROMIUM, "--headless=new", "--disable-gpu", "--no-sandbox", f"--user-data-dir={profile}",
            "--allow-file-access-from-files", "--virtual-time-budget=5000", "--dump-dom", url]


@functools.lru_cache(maxsize=None)
def chromium_unusable() -> str | None:
    """Why headless chromium cannot be used on this host, or None when it renders a
    trivial page. Established independently of the picker, so that a picker page
    that hangs or crashes the browser fails its test instead of skipping it."""
    if not CHROMIUM:
        return "no chromium / google-chrome for the headless page test"
    tmp = Path(tempfile.mkdtemp(prefix="vp-chrome-probe-"))
    try:
        page = tmp / "probe.html"
        page.write_text('<!doctype html><title>probe</title><body data-probe="ok"></body>')
        try:
            cp = subprocess.run(chromium_argv(tmp / "profile", page.as_uri()),
                                capture_output=True, text=True, timeout=90)
        except subprocess.TimeoutExpired:
            return "headless chromium did not render a trivial page within 90 s"
        if 'data-probe="ok"' not in cp.stdout:
            return f"headless chromium cannot render a trivial page: {cp.stderr.strip()[-300:]}"
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_cli_in(cwd, *args, env=None):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True,
                          text=True, cwd=str(cwd), env=env)


def gradient(w, h, seed=0):
    """Gray pixels that differ everywhere, so any crop or shift changes the bytes."""
    return bytes(((x * 7 + y * 13 + seed * 31) % 251) for y in range(h) for x in range(w))


def write_frames_dir(folder: Path, times_ms, *, w=120, h=200, src=(240, 400), skip=(),
                     time_source="pts*time_base") -> list[Path]:
    """t<ms>.png gray images and a frames.tsv binding each to a whole-frame
    geometry scaled by w/src (rows for `skip` names are left out)."""
    folder.mkdir(parents=True, exist_ok=True)
    paths, rows = [], []
    for k, ms in enumerate(times_ms):
        path = folder / core.frames_name(ms)
        write_png(path, w, h, gradient(w, h, k))
        paths.append(path)
        if path.name in skip:
            continue
        rows.append([path.name, ms, ms, time_source, src[0], src[1], 0, 0, src[0], src[1], w, h,
                     f"{w / src[0]:.6f}", f"{h / src[1]:.6f}",
                     hashlib.sha256(path.read_bytes()).hexdigest()])
    with open(folder / "frames.tsv", "w", newline="") as fh:
        wr = csv.writer(fh, delimiter="\t", lineterminator="\n")
        wr.writerow(PICK_GEOM_COLS)
        wr.writerows(rows)
    return paths


class _PageScripts(html.parser.HTMLParser):
    """The raw text of every <script> as the HTML tokenizer splits it, plus a
    few attributes of interest, so tests see the page the way a browser parses it."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.scripts, self.body, self.pre, self.cards, self._in, self._pre = [], {}, "", 0, None, False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script":
            self._in = len(self.scripts)
            self.scripts.append([a.get("id"), ""])
        elif tag == "body":
            self.body = a
        elif tag == "pre" and a.get("id") == "copy-text":
            self._pre = True
        elif tag == "button" and "card" in (a.get("class") or "").split():
            self.cards += 1

    def handle_data(self, data):
        if self._in is not None:
            self.scripts[self._in][1] += data
        if self._pre:
            self.pre += data

    def handle_endtag(self, tag):
        if tag == "script":
            self._in = None
        elif tag == "pre":
            self._pre = False


def parse_page(text: str) -> _PageScripts:
    p = _PageScripts()
    p.feed(text)
    p.close()
    return p


class _PickCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="vp-pick-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def pick_ok(self, target, out_name, *extra, cwd=None, env=None):
        out = self.tmp / out_name
        cp = run_cli_in(cwd or HERE.parent, "pick", target, "--out", out, *extra, env=env)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        lines = cp.stdout.splitlines()
        self.assertTrue(lines[-1].startswith("SUMMARY: "), cp.stdout)
        self.assertTrue(lines[-2].startswith("PAGE: "), cp.stdout)
        data = json.loads((out / "pick.json").read_text())
        return out, data, cp

    @staticmethod
    def block(data, rels, **state):
        return pick.copy_block(data, {"selected": list(rels), **state})


class PickFolder(_PickCase):
    """pick on folders made by the test (no ffmpeg needed)."""

    def test_manifest_snapshot_and_embedded_data(self):
        folder = self.tmp / "plain"
        write_frames_dir(folder, [0, 33, 66, 133])
        out, data, cp = self.pick_ok(folder, "plain-pick")
        self.assertIn("OPEN: not requested", cp.stdout)
        plan = core.plan_sheet([p.name for p in folder.glob("*.png")])
        self.assertEqual([f["name"] for f in data["frames"]], [it.name for it in plan.items])
        self.assertEqual([f["ms"] for f in data["frames"]], [0, 33, 66, 133])
        self.assertEqual([f["delta_ms"] for f in data["frames"]], [None, 33, 33, 67])
        self.assertEqual([f["label"] for f in data["frames"]],
                         ["0.000 s first", "0.033 s +33 ms", "0.066 s +33 ms", "0.133 s +67 ms"])
        for f in data["frames"]:
            snap = Path(f["path"])
            self.assertTrue(snap.is_absolute())
            self.assertEqual(snap.parent, (out / "src").resolve())
            self.assertEqual(f["sha256"], hashlib.sha256(snap.read_bytes()).hexdigest())
            self.assertEqual(f["geom"], {"src_w": 240, "src_h": 400, "crop_x": 0, "crop_y": 0,
                                         "crop_w": 240, "crop_h": 400, "out_w": 120,
                                         "out_h": 200})
            self.assertEqual((f["w"], f["h"]), (120, 200))
        page = parse_page((out / "index.html").read_text())
        ids = [i for i, _ in page.scripts]
        self.assertEqual(ids, ["vp-data", None, None])
        self.assertEqual(json.loads(page.scripts[0][1]), data)
        self.assertEqual(page.scripts[1][1], (SCRIPT.parent / "pick_logic.js").read_text())
        self.assertEqual(page.scripts[2][1], (SCRIPT.parent / "pick_ui.js").read_text())
        run = json.loads((out / "run.json").read_text())
        self.assertEqual((run["mode"], run["frames"], run["roi_trusted"]), ("pick", 4, 4))
        self.assertEqual(run["fingerprint"], data["fingerprint"])

    def test_no_geometry_record_disables_the_source_roi(self):
        bare = self.tmp / "bare"
        write_frames_dir(bare, [0, 33])
        (bare / "frames.tsv").unlink()
        _, data, _ = self.pick_ok(bare, "bare-pick")
        self.assertEqual({f["roi_disabled"] for f in data["frames"]},
                         {"no frames.tsv beside the image"})
        self.assertTrue(all(f["geom"] is None for f in data["frames"]))
        partial = self.tmp / "partial"
        write_frames_dir(partial, [0, 33], skip=("t00000033.png",))
        out, data, _ = self.pick_ok(partial, "partial-pick")
        by = {f["name"]: f for f in data["frames"]}
        self.assertIsNotNone(by["t00000000.png"]["geom"])
        self.assertEqual(by["t00000033.png"]["roi_disabled"],
                         "frames.tsv has no row for t00000033.png")
        self.assertIn("t00000033.png: frames.tsv has no row", (out / "summary.md").read_text())
        b = self.block(data, ["t00000033.png"],
                       rect={"rel": "t00000033.png", "x0": 1, "y0": 1, "x1": 9, "y1": 9})
        self.assertIn("# rectangle 1,1,8,8 in t00000033.png's own pixels", b)
        self.assertNotIn("# --roi", b)

    def test_same_dimension_edits_lose_the_geometry(self):
        folder = self.tmp / "edited"
        w, h = 120, 200
        paths = write_frames_dir(folder, [0, 33, 66])
        px = gradient(w, h, 1)
        # (a) crop to the middle, then resize back to the same size (nearest neighbour)
        cx, cy, cw, ch = 20, 30, 80, 140
        crop_back = bytes(px[(cy + y * ch // h) * w + cx + x * cw // w]
                          for y in range(h) for x in range(w))
        # (b) the same picture shifted by (3, 2) inside the canvas
        shifted = bytes(px[(y - 2) * w + (x - 3)] if x >= 3 and y >= 2 else 255
                        for y in range(h) for x in range(w))
        for edit in (crop_back, shifted):
            self.assertEqual(len(edit), w * h)          # premise: same dimensions
            self.assertNotEqual(edit, px)              # premise: different pixels
        write_png(paths[1], w, h, crop_back)
        write_png(paths[2], w, h, shifted)
        self.assertEqual(core.png_size(paths[1].read_bytes()[:24]), (w, h))
        _, data, _ = self.pick_ok(folder, "edited-pick")
        by = {f["name"]: f for f in data["frames"]}
        self.assertIsNotNone(by["t00000000.png"]["geom"])
        for name in ("t00000033.png", "t00000066.png"):
            self.assertIsNone(by[name]["geom"], name)
            self.assertIn("SHA-256", by[name]["roi_disabled"])
            self.assertIn("changed since extraction", by[name]["roi_disabled"])
            b = self.block(data, [name], rect={"rel": name, "x0": 0, "y0": 0, "x1": 5, "y1": 5})
            self.assertNotIn("# --roi", b)
            self.assertIn("own pixels", b)

    def test_snapshot_is_what_gets_hashed_and_trusted(self):
        import video_prep
        folder = self.tmp / "racy"
        paths = write_frames_dir(folder, [0, 33])
        originals = {p.name: p.read_bytes() for p in paths}
        real_copy = pick._copy_file

        def copy_then_rewrite(src, dest):
            real_copy(src, dest)
            write_png(src, 120, 200, gradient(120, 200, 9))     # a concurrent rewrite
        out = self.tmp / "racy-pick"
        with mock.patch.object(pick, "_copy_file", copy_then_rewrite), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(video_prep.main(["pick", str(folder), "--out", str(out)]), 0)
        data = json.loads((out / "pick.json").read_text())
        for f in data["frames"]:
            snap = Path(f["path"]).read_bytes()
            self.assertEqual(snap, originals[f["name"]])
            self.assertEqual(f["sha256"], hashlib.sha256(snap).hexdigest())
            now = (folder / f["name"]).read_bytes()
            self.assertNotEqual(hashlib.sha256(now).hexdigest(), f["sha256"])   # premise
            self.assertIsNotNone(f["geom"])        # decided on the snapshot, which matches

    def test_snapshot_names_never_collide(self):
        folder = self.tmp / "names"
        folder.mkdir()
        names = ["renamed_0001.png", "RENAMED_0002.png", "a b\n.png", "-x.png", "t00000100?.png"]
        want = {}
        for k, n in enumerate(names):
            write_png(folder / n, 8, 8, bytes([k * 40]) * 64)
            want[n] = hashlib.sha256((folder / n).read_bytes()).hexdigest()
        out, data, _ = self.pick_ok(folder, "names-pick")
        snaps = [Path(f["path"]) for f in data["frames"]]
        self.assertEqual(len(set(snaps)), len(names))
        self.assertEqual(len(list((out / "src").iterdir())), len(names))
        for f in data["frames"]:
            self.assertEqual(hashlib.sha256(Path(f["path"]).read_bytes()).hexdigest(),
                             want[f["name"]], f["name"])
        by = {f["name"]: Path(f["path"]).name for f in data["frames"]}
        self.assertEqual(by["renamed_0001.png"], "renamed_0001.png")
        self.assertEqual((out / "src" / "renamed_0001.png").read_bytes(),
                         (folder / "renamed_0001.png").read_bytes())
        generated = [by[n] for n in names[2:]]
        self.assertFalse({g.casefold() for g in generated}
                         & {"renamed_0001.png", "renamed_0002.png"})
        b = self.block(data, [f["rel"] for f in data["frames"]])
        self.assertEqual(sum(1 for ln in b.splitlines() if ln.startswith("/")), len(names))

    def test_script_breaking_data_stays_inside_the_json(self):
        base = self.tmp / "a<" / "script>b"            # ".../a</script>b": a real path
        write_frames_dir(base / "frames", [0, 33],
                         time_source="</script><img src=x onerror=alert(1)>&amp;")
        evil_video = self.tmp / "x<" / "script>y" / "clip.mp4"
        evil_video.parent.mkdir(parents=True)
        evil_video.write_bytes(b"not really a video")
        (base / "run.json").write_text(json.dumps({"mode": "frames",
                                                   "options": {"video": str(evil_video)}}))
        out, data, _ = self.pick_ok(base, "a</script>b/out-pick")   # the out dir under it too
        self.assertIn("</script>", data["page"])                        # premise: it got in
        self.assertIn("</script>", data["frames"][0]["time_source"])
        self.assertIn(str(evil_video), data["source_line"])
        self.assertIn("recorded path, unverified", data["source_line"])
        text = (out / "index.html").read_text()
        start = text.index('<script type="application/json" id="vp-data">') + 46
        payload = text[start:text.index("</script>", start)]
        self.assertFalse(any(c in payload for c in "<>&"))
        page = parse_page(text)
        self.assertEqual([i for i, _ in page.scripts], ["vp-data", None, None])
        self.assertEqual(json.loads(page.scripts[0][1]), data)
        self.assertEqual(text.count("<script"), 3)
        template = (SCRIPT.parent / "pick_page.html").read_text()
        self.assertEqual(text.count("<img"), template.count("<img"))   # none from the data
        b = self.block(data, [f["rel"] for f in data["frames"]])
        self.assertEqual(sum(1 for ln in b.splitlines() if ln.startswith("/")), 2)
        # premise control: the same page without the escaping step is cut short
        with mock.patch.object(pick, "script_json", lambda d: json.dumps(d)):
            raw = parse_page(pick.render_page(data))
        with self.assertRaises(ValueError):
            if json.loads(raw.scripts[0][1]) != data:
                raise ValueError("data changed")

    def _stub_env(self, name, display):
        bindir = self.tmp / f"{name}-bin"
        bindir.mkdir()
        log = self.tmp / f"{name}-opener.log"
        stub = bindir / "xdg-open"
        stub.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" >> "{log}"\n')
        stub.chmod(0o755)
        env = {k: v for k, v in os.environ.items()
               if k not in ("DISPLAY", "WAYLAND_DISPLAY", "SSH_CONNECTION", "SSH_CLIENT",
                            "SSH_TTY")}
        env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
        if display:
            env["DISPLAY"] = display
        return env, log

    @unittest.skipUnless(sys.platform.startswith("linux") and "microsoft" not in
                         Path("/proc/version").read_text(errors="replace").lower()
                         if Path("/proc/version").exists() else False, "Linux (not WSL) only")
    def test_open_with_and_without_a_display(self):
        folder = self.tmp / "opener"
        write_frames_dir(folder, [0, 33])
        env, log = self._stub_env("nodisplay", None)
        out, _, cp = self.pick_ok(folder, "opener-none", "--open", env=env)
        self.assertIn("OPEN: not opened: no display", cp.stdout)
        self.assertFalse(log.exists())
        self.assertIn("not opened", (out / "summary.md").read_text())
        env, log = self._stub_env("display", ":99")
        out, _, cp = self.pick_ok(folder, "opener-yes", "--open", env=env)
        self.assertIn("OPEN: opened (xdg-open)", cp.stdout)
        self.assertEqual(log.read_text().splitlines(), [str((out / "index.html").resolve())])
        self.assertTrue(json.loads((out / "run.json").read_text())["opened"])

    def test_bad_inputs_fail_cleanly(self):
        empty = self.tmp / "empty-pick-in"
        empty.mkdir()
        (empty / "notes.txt").write_text("x")
        for args, code, msg in ((("pick", self.tmp / "missing"), 2, "no such directory"),
                                (("pick", empty), 1, "no png, jpg or webp images")):
            with self.subTest(args=args):
                cp = run_cli(*args, "--out", self.tmp / "err-pick-out")
                self.assertEqual(cp.returncode, code, cp.stderr)
                self.assertIn(msg, cp.stderr)
                self.assertFalse((self.tmp / "err-pick-out").exists())

    def test_legacy_relative_video_is_never_re_resolved(self):
        a, b = self.tmp / "cwdA", self.tmp / "cwdB"
        for d, size in ((a, 100), (b, 300)):
            d.mkdir()
            (d / "clip.mp4").write_bytes(b"v" * size)
        run_dir = self.tmp / "legacy-run"
        write_frames_dir(run_dir / "frames", [0, 33])
        (run_dir / "run.json").write_text(json.dumps({
            "mode": "frames", "options": {"video": "clip.mp4"}, "video": {"path": "clip.mp4"}}))
        out, data, _ = self.pick_ok(run_dir, "legacy-pick", cwd=b)
        self.assertEqual(data["source_line"], "# source: frames run of <VIDEO> (recorded as "
                         "'clip.mp4' relative to an unknown directory)")
        self.assertNotIn(str(b), (out / "pick.json").read_text())
        self.assertNotIn(str(b), self.block(data, [f["rel"] for f in data["frames"]]))
        # an absolute legacy path is a hint, never the source
        (run_dir / "run.json").write_text(json.dumps({
            "mode": "frames", "options": {"video": str(b / "clip.mp4")}}))
        _, data, _ = self.pick_ok(run_dir, "legacy-abs-pick", cwd=a)
        self.assertEqual(data["source"]["video"], None)
        self.assertIn(f"recorded path, unverified: {b / 'clip.mp4'}", data["source_line"])
        self.assertNotIn(f"frames run of {b}", data["source_line"])

    def test_run_layouts_win_over_root_images(self):
        def layout(name, *, run=None, root_sheet=False, segs=("frames",)):
            d = self.tmp / f"lay-{name}"
            for s in segs:
                write_frames_dir(d / s if s == "frames" else d / s / "frames", [0, 33])
            if root_sheet:
                write_png(d / "sheet_01.png", 40, 40)
            if run is not None:
                (d / "run.json").write_text(json.dumps(run))
            return d
        bug = layout("bug", run={"mode": "bug"}, root_sheet=True)
        _, data, _ = self.pick_ok(bug, "lay-bug-pick")
        self.assertEqual({f["name"] for f in data["frames"]}, {"t00000000.png", "t00000033.png"})
        self.assertEqual(data["layout"], "bug run: frames/")
        no_run = layout("bug-norun", root_sheet=True)
        _, data, _ = self.pick_ok(no_run, "lay-bug-norun-pick")
        self.assertNotIn("sheet_01.png", {f["name"] for f in data["frames"]})
        win = layout("win", run={"mode": "anim"}, segs=("w01",))
        _, data, _ = self.pick_ok(win, "lay-win-pick")
        self.assertEqual({f["group"] for f in data["frames"]}, {"w01"})
        self.assertTrue(all(f["rel"].startswith("w01/") for f in data["frames"]))
        segs = layout("segs", run={"mode": "anim"}, segs=("s02", "s01"))
        _, data, _ = self.pick_ok(segs, "lay-segs-pick")
        self.assertEqual([g["label"] for g in data["groups"]], ["s01", "s02"])
        sheet = layout("sheetout", run={"mode": "sheet", "dir": "/somewhere/frames"})
        cp = run_cli("pick", sheet, "--out", self.tmp / "lay-sheet-pick")
        self.assertEqual(cp.returncode, 1)
        self.assertIn("pick the folder it was made from (/somewhere/frames)", cp.stderr)
        broken = self.tmp / "lay-broken"
        broken.mkdir()
        write_png(broken / "sheet_01.png", 40, 40)
        (broken / "run.json").write_text(json.dumps({"mode": "bug"}))
        cp = run_cli("pick", broken, "--out", self.tmp / "lay-broken-pick")
        self.assertEqual(cp.returncode, 1)
        self.assertIn(f"{broken / 'frames'} is missing", cp.stderr)
        self.assertFalse((self.tmp / "lay-broken-pick").exists())
        plain = self.tmp / "lay-plain"
        write_frames_dir(plain, [0])
        _, data, _ = self.pick_ok(plain, "lay-plain-pick")
        self.assertEqual(data["layout"], "image folder")

    # ---- post-phase [headless_ui_smoke] ----------------------------------------

    def chromium_dom(self, page: Path, hash_spec, name):
        profile = self.tmp / f"chrome-{name}"
        url = page.resolve().as_uri()
        if hash_spec is not None:
            from urllib.parse import quote
            url += "#selftest=" + quote(json.dumps(hash_spec))
        # the browser itself is known to work here (chromium_unusable), so a hang or an
        # empty result on the picker page is the page's failure, never a skip
        try:
            cp = subprocess.run(chromium_argv(profile, url), capture_output=True, text=True,
                                timeout=90)
        except subprocess.TimeoutExpired:
            self.fail(f"headless chromium hung on the picker page ({name}) for 90 s, while it "
                      "renders a trivial page")
        if not cp.stdout.strip():
            self.fail(f"headless chromium returned no DOM for the picker page ({name}), exit "
                      f"{cp.returncode}: {cp.stderr.strip()[-300:]}")
        return parse_page(cp.stdout)

    def test_page_drives_in_headless_chromium(self):
        why = chromium_unusable()
        if why:
            self.skipTest(why)
        folder = self.tmp / "ui"
        write_frames_dir(folder, [0, 33, 66, 99, 132, 165])
        out, data, _ = self.pick_ok(folder, "ui-pick")
        page = out / "index.html"
        rel = [f["rel"] for f in data["frames"]]

        # premise: without the self-test the page renders its cards and an empty block
        dom = self.chromium_dom(page, None, "plain")
        self.assertEqual(dom.cards, 6)
        self.assertEqual(dom.pre, pick.copy_block(data, {}))

        steps, expected = [], []
        st = {"selected": [], "marks": {"start": None, "end": None}, "notes": {}, "rect": None}

        def step(action, **change):
            steps.append(action)
            for k, v in change.items():
                st[k] = v
            expected.append(pick.copy_block(data, json.loads(json.dumps(st))))
        # the oracle is written down here, from the event script alone
        step({"click": 0}, selected=[rel[0]])
        step({"click": 2, "shift": True}, selected=rel[0:3])           # inclusive range
        step({"key": "ArrowRight"})                                     # focus card 4
        step({"key": " "}, selected=rel[0:4])                           # toggles card 4
        step({"key": "Home"})
        step({"key": "s"}, marks={"start": rel[0], "end": None})
        step({"key": "ArrowRight"})
        step({"key": "ArrowRight"})
        step({"key": "e"}, marks={"start": rel[0], "end": rel[2]})
        step({"key": "ArrowLeft"})
        step({"note": "edge starts"}, notes={rel[1]: "edge starts"})
        step({"key": "Home"})
        step({"drag": [10, 30, 19, 49]},
             rect={"rel": rel[0], "x0": 10, "y0": 30, "x1": 20, "y1": 50})
        dom = self.chromium_dom(page, {"steps": steps}, "steps")
        self.assertEqual(dom.body.get("data-selftest"), "done",
                         (dom.body.get("data-selftest"), dom.body.get("data-state")))
        self.assertEqual(dom.cards, 6)
        trace = json.loads(dom.body["data-trace"])
        self.assertEqual(len(trace), len(steps))
        for k, (got, want) in enumerate(zip(trace, expected)):
            self.assertEqual(got, want, f"after step {k + 1} {steps[k]}; ui state "
                                        f"{dom.body.get('data-state')}")
        frame_lines = [ln for ln in trace[1].splitlines() if ln.startswith("/")]
        self.assertEqual([Path(ln.split(chr(9))[0]).name for ln in frame_lines],
                         [Path(r).name for r in rel[0:3]])
        self.assertIn("# --window 0-0.0665  (user-marked endpoints (unverified)", trace[8])
        self.assertIn("note: edge starts", trace[10])
        self.assertIn("# --roi 20,60,20,40  (source-video pixels", trace[-1])
        self.assertEqual(dom.pre, expected[-1])

        # focus that moves without a click, and Space on an action button
        steps = [{"click": 0},                  # select card 1
                 {"focusCard": 2},              # DOM focus to card 3, no click
                 {"key": " "},                  # toggles card 3, not card 1
                 {"key": "ArrowRight"},         # from card 3 to card 4
                 {"key": "s"},                  # marks card 4
                 {"focusButton": "btn-copy"},
                 {"key": " "},                  # the button's own key: nothing selected
                 {"clickButton": "btn-copy"}]   # the activation Space would cause
        want = [{"selected": [rel[0]]},
                {"selected": [rel[0]]},
                {"selected": [rel[0], rel[2]]},
                {"selected": [rel[0], rel[2]]},
                {"selected": [rel[0], rel[2], rel[3]], "marks": {"start": rel[3]}}]
        want += [want[-1]] * 3
        dom = self.chromium_dom(page, {"steps": steps}, "focus")
        self.assertEqual(dom.body.get("data-selftest"), "done", dom.body.get("data-selftest"))
        trace = json.loads(dom.body["data-trace"])
        events = json.loads(dom.body["data-events"])
        for k, (got, st) in enumerate(zip(trace, want)):
            self.assertEqual(got, pick.copy_block(data, st), f"after step {k + 1} {steps[k]}")
        self.assertEqual([e["active"] for e in events[:5]],
                         ["card:0", "card:2", "card:2", "card:3", "card:3"])
        self.assertEqual(events[6]["active"], "btn-copy")
        self.assertIs(events[6]["cancelled"], False)     # native activation is left alone
        self.assertEqual(events[6]["status"], "")
        self.assertNotEqual(events[7]["status"], "")     # Copy ran: copied, or the fallback

        # storage that throws: the page still renders and works
        dom = self.chromium_dom(page, {"nostorage": True, "steps": [{"click": 1}]}, "nostorage")
        self.assertEqual(dom.body.get("data-selftest"), "done", dom.body.get("data-selftest"))
        self.assertEqual(json.loads(dom.body["data-trace"]),
                         [pick.copy_block(data, {"selected": [rel[1]]})])



@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe not installed")
class PickFromRuns(_VideoCase):
    """pick on real bug / frames / anim runs of synthetic recordings."""

    def pick(self, target, name, *, cwd=None):
        out = self.tmp / name
        cp = run_cli_in(cwd or HERE.parent, "pick", target, "--out", out)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        return out, json.loads((out / "pick.json").read_text())

    def markers(self):
        return self.video("markers", synth.marker_frames)

    def slide_right(self):
        return self.video("slide_right", lambda: synth.card_frames(
            synth.tween(synth.EASE_OUT, 0.5, 0.3), 1.4, "right"))

    def slide_right_vfr(self):
        return self.video("slide_right_vfr", lambda: synth.card_frames(
            synth.tween(synth.EASE_OUT, 0.5, 0.3), 1.4, "right"), vfr=True)

    def assert_roi_finds_markers(self, data, box, scale):
        """Around each marker the snapshot shows, a +-4 px rectangle in image pixels maps
        to a source --roi that contains the marker as drawn, centred on it within 1 px."""
        f = data["frames"][0]
        self.assertIsNotNone(f["geom"], f["roi_disabled"])
        gray, w, h = png_gray(Path(f["path"]))
        n = 0
        for mx, my in synth.MARKERS:
            if not (box[0] <= mx and mx + 6 <= box[0] + box[2] and box[1] <= my
                    and my + 6 <= box[1] + box[3]):
                continue
            guess = ((mx - box[0] + 2.5) * scale, (my - box[1] + 2.5) * scale)
            c = synth.dark_centroid(gray, w, h, *guess)
            self.assertIsNotNone(c, (mx, my))
            ex, ey = c[0] + 0.5, c[1] + 0.5               # pixel-edge coordinates
            rect = (math.floor(ex - 4), math.floor(ey - 4), math.ceil(ex + 4), math.ceil(ey + 4))
            x, y, rw, rh = pick.roi_to_source(rect, f["geom"])
            self.assertLessEqual(x, mx, (mx, my, x, rw))
            self.assertGreaterEqual(x + rw, mx + 6, (mx, my, x, rw))
            self.assertLessEqual(y, my, (mx, my, y, rh))
            self.assertGreaterEqual(y + rh, my + 6, (mx, my, y, rh))
            self.assertAlmostEqual(x + rw / 2, mx + 3, delta=1.0)
            self.assertAlmostEqual(y + rh / 2, my + 3, delta=1.0)
            n += 1
        return n

    def test_roi_maps_to_source_through_a_cropped_geometry(self):
        box = (37, 151, 201, 243)
        out = self.tmp / "pk-roi-crop"
        self.cli_ok("frames", self.markers(), "--at", "0", "--roi", ",".join(map(str, box)),
                    "--out", out)
        _, data = self.pick(out, "pk-roi-crop-pick")
        self.assertEqual(data["layout"], "frames run: frames/")
        self.assertEqual(self.assert_roi_finds_markers(data, box, 1.0), 3)

    def test_roi_maps_to_source_through_a_scaled_geometry(self):
        out = self.tmp / "pk-roi-scaled"
        self.cli_ok("bug", self.markers(), "--view-size", "400", "--out", out)
        _, data = self.pick(out, "pk-roi-scaled-pick")
        g = data["frames"][0]["geom"]
        self.assertEqual((g["out_w"], g["crop_w"]), (180, 360))          # premise: scale 0.5
        self.assertEqual(self.assert_roi_finds_markers(data, (0, 0, 360, 800), 0.5),
                         len(synth.MARKERS))

    @unittest.skipUnless(HAVE_MAGICK, "magick draws the bug run's contact sheets")
    def test_bug_run_with_sheets_picks_the_frames(self):
        out = self.tmp / "pk-bug"
        self.cli_ok("bug", self.markers(), "--out", out)
        self.assertTrue((out / "sheet_01.png").is_file())                # premise
        _, data = self.pick(out, "pk-bug-pick")
        rows = {r["file"]: r for r in read_manifest(out / "frames")}
        self.assertEqual({f["name"] for f in data["frames"]}, set(rows))
        self.assertFalse(any(f["name"].startswith("sheet_") for f in data["frames"]))
        for f in data["frames"]:
            self.assertEqual(f["ms"], int(rows[f["name"]]["t_ms"]))
            self.assertIsNotNone(f["geom"], f["roi_disabled"])

    def test_pick_after_an_anim_window(self):
        out = self.tmp / "pk-anim-window"
        self.cli_ok("anim", self.slide_right(), "--window", "0.2-0.9", "--out", out)
        self.assertTrue((out / "w01" / "frames").is_dir())               # premise
        self.assertFalse((out / "s01").exists())
        _, data = self.pick(out, "pk-anim-window-pick")
        self.assertEqual([g["label"] for g in data["groups"]], ["w01"])
        self.assertEqual({f["name"] for f in data["frames"]},
                         {r["file"] for r in read_manifest(out / "w01" / "frames")})
        self.assertTrue(all(f["geom"] for f in data["frames"]))

    @staticmethod
    def certifies_nothing(test, data, block):
        test.assertIn("# viewing range: ", block)
        test.assertNotIn("--window", block)
        for word in ("settled", "still"):
            test.assertNotIn(word, block)
            test.assertNotIn(word, json.dumps(data))

    def anim_run(self, video, name, *extra):
        out = self.tmp / name
        self.cli_ok("anim", video, "--out", out, *extra)
        return out

    def test_mid_motion_selection_is_a_viewing_range(self):
        out = self.anim_run(self.slide_right(), "pk-mid")
        m = re.search(r"first changed frame ([\d.]+) s, settled at ([\d.]+) s",
                      (out / "summary.md").read_text())
        lo, hi = float(m.group(1)) * 1000, float(m.group(2)) * 1000
        _, data = self.pick(out, "pk-mid-pick")
        mid = [f["rel"] for f in data["frames"] if lo < f["ms"] < hi]
        self.assertGreaterEqual(len(mid), 2)                              # premise
        self.certifies_nothing(self, data, pick.copy_block(data, {"selected": mid}))

    def test_turning_point_and_duplicate_frames_are_never_certified(self):
        spring = self.video("spring", lambda: synth.card_frames(
            synth.spring_progress(400.0, 0.5, 0.5), 2.0, "right"))
        out = self.anim_run(spring, "pk-spring")
        with open(out / "s01" / "curve.tsv", newline="") as fh:
            rows = list(csv.DictReader(fh, delimiter="\t"))
        prog = [float(r["p_fitted_signal"]) for r in rows]
        peak = max(range(len(prog)), key=prog.__getitem__)
        self.assertGreater(prog[peak], 1.05)                              # premise: overshoot
        self.assertGreater(prog[peak], prog[peak + 2])                    # ...and it turns back
        # curve.tsv names each saved frame relative to the run dir (s01/frames/<name>)
        files = [Path(rows[i]["file"]).name for i in range(peak - 3, peak + 4) if rows[i]["file"]]
        self.assertGreaterEqual(len(files), 3)
        _, data = self.pick(out, "pk-spring-pick")
        rels = [f"s01/{n}" for n in files]
        self.assertTrue(set(rels) <= {f["rel"] for f in data["frames"]})
        self.certifies_nothing(self, data, pick.copy_block(data, {"selected": rels}))

        # a duplicated capture frame: lossless, so the repeated picture decodes identically
        dup = self.tmp / "markers_lossless.mp4"
        if not dup.exists():
            synth.encode(dup, synth.marker_frames(6), crf=0)
        held = self.tmp / "pk-held"
        self.cli_ok("frames", dup, "--range", "0-0.1", "--out", held)
        _, data = self.pick(held, "pk-held-pick")
        a, b = (png_gray(Path(f["path"]))[0] for f in data["frames"][:2])
        self.assertEqual(a, b)                                            # premise: duplicates
        self.certifies_nothing(self, data, pick.copy_block(
            data, {"selected": [f["rel"] for f in data["frames"]]}))

    def window_round_trip(self, video, name):
        out = self.anim_run(video, name)
        _, data = self.pick(out, f"{name}-pick")
        frames = [f for f in data["frames"] if f["group"] == "s01"]

        def exact(f):          # 60 fps: the frame presented at k/60 s carries round(k/60 s)
            return Fraction(round(f["ms"] * 60 / 1000), 60)
        start = next(f for f in frames if exact(f) * 1000 < f["ms"])     # premise: below its ms
        end = next(f for f in frames if f["ms"] - start["ms"] >= 80)
        block = pick.copy_block(data, {"selected": [start["rel"], end["rel"]],
                                       "marks": {"start": start["rel"], "end": end["rel"]}})
        m = re.search(r"^# --window (\S+)  \(user-marked endpoints \(unverified\)", block, re.M)
        self.assertIsNotNone(m, block)
        again = self.anim_run(video, f"{name}-again", "--window", m.group(1))
        with open(again / "w01" / "curve.tsv", newline="") as fh:
            times = [float(r["time_s"]) for r in csv.DictReader(fh, delimiter="\t")]
        self.assertAlmostEqual(times[0], float(exact(start)), delta=2e-4, msg=m.group(1))
        self.assertAlmostEqual(times[-1], float(exact(end)), delta=2e-4, msg=m.group(1))
        return times, exact(start), exact(end)

    def test_marked_window_selects_exactly_the_marked_frames(self):
        times, a, b = self.window_round_trip(self.slide_right(), "pk-win")
        self.assertEqual(len(times), int((b - a) * 60) + 1)               # CFR: every frame
        self.window_round_trip(self.slide_right_vfr(), "pk-win-vfr")

    def test_source_video_comes_only_from_a_proven_path(self):
        a, b = self.tmp / "srcA", self.tmp / "srcB"
        a.mkdir()
        b.mkdir()
        shutil.copyfile(self.markers(), a / "clip.mp4")
        shutil.copyfile(self.video("numbered", lambda: synth.numbered_frames(120)),
                        b / "clip.mp4")
        self.assertNotEqual((a / "clip.mp4").stat().st_size, (b / "clip.mp4").stat().st_size)
        run = self.tmp / "pk-src-run"
        cp = run_cli_in(a, "frames", "clip.mp4", "--at", "0", "--out", run)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        rj = json.loads((run / "run.json").read_text())
        self.assertEqual(rj["options"]["video"], "clip.mp4")                # premise: relative
        self.assertEqual(rj["video_abspath"], str((a / "clip.mp4").resolve()))
        self.assertEqual(rj["video_size"], (a / "clip.mp4").stat().st_size)
        _, data = self.pick(run, "pk-src-pick", cwd=b)
        self.assertEqual(data["source_line"],
                         f"# source: frames run of {(a / 'clip.mp4').resolve()}")
        self.assertNotIn(str(b), json.dumps(data))
        shutil.copyfile(b / "clip.mp4", a / "clip.mp4")                   # replaced in place
        _, data = self.pick(run, "pk-src-pick-changed", cwd=b)
        self.assertIsNone(data["source"]["video"])
        self.assertIn("<VIDEO>", data["source_line"])
        self.assertIn("changed since extraction", data["source_line"])
        (a / "clip.mp4").unlink()
        _, data = self.pick(run, "pk-src-pick-gone", cwd=b)
        self.assertIn("<VIDEO>", data["source_line"])
        self.assertIn("is missing", data["source_line"])

    def test_run_json_records_the_video_provenance(self):
        video = self.video("markers_slide", lambda: synth.marker_frames(60, slide=True))
        for mode, extra in (("bug", ()), ("anim", ()), ("frames", ("--at", "0"))):
            out = self.tmp / f"pk-prov-{mode}"
            self.cli_ok(mode, video, "--out", out, *extra)
            rj = json.loads((out / "run.json").read_text())
            self.assertEqual(rj["video_abspath"], str(video.resolve()), mode)
            self.assertEqual(rj["video_size"], video.stat().st_size, mode)


# --------------------------------------------------------------------------- #
# bug DIR / anim DIR: a curated folder of images through the same pipelines

def write_rgb_png(path, w, h, fill=128):
    """An 8-bit RGB PNG (color type 2) of one gray level, so its pixels equal
    write_png's gray image of the same fill while its decoded pixel format differs."""
    import struct
    import zlib
    raw = b"".join(b"\x00" + bytes([fill]) * (3 * w) for _ in range(h))

    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n"
                           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def png_color_type(path) -> int:
    return Path(path).read_bytes()[25]


_SEG_START = re.compile(r"^\| s01 \| ([\d.]+) s \|", re.M)
_FIRST_CHANGED = re.compile(r"first changed frame ([\d.]+) s")


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe not installed")
class ImageFolderInput(_VideoCase):
    """bug DIR / anim DIR: a folder of images (times from the names, or --fps)
    goes through the same ffmpeg pipelines as a recording (t1893_6)."""

    def slide_right(self):     # CSS ease-out, 300 ms from 0.5 s, 60 fps
        return self.video("slide_right", lambda: synth.card_frames(
            synth.tween(synth.EASE_OUT, 0.5, 0.3), 1.4, "right"))

    def slide_left_400(self):  # FastOutSlowIn, 400 ms from 0.5 s
        return self.video("slide_left_400", lambda: synth.card_frames(
            synth.tween(synth.FAST_OUT_SLOW_IN, 0.5, 0.4), 1.5, "left"))

    def frames_dir(self, video, rng, name):
        out = self.tmp / name
        if not out.exists():
            self.cli_ok("frames", video, "--range", rng, "--max-frames", "200", "--out", out)
        return out / "frames"

    def anim_run(self, target, name, *extra):
        out = self.tmp / name
        self.cli_ok("anim", target, "--out", out, *extra)
        fits = sorted(out.glob("*/fit.json"))
        self.assertEqual(len(fits), 1, fits)
        return (out, json.loads(fits[0].read_text()), json.loads((out / "run.json").read_text()),
                (out / "summary.md").read_text())

    def copy_images(self, src_dir, name, keep):
        d = self.tmp / name
        d.mkdir()
        for k, p in enumerate(sorted(src_dir.glob("*.png"))):
            if keep(k, p):
                shutil.copy(p, d / p.name)
        return d

    def mixed_sizes(self):
        d = self.tmp / "mixed"
        if not d.exists():
            d.mkdir()
            write_png(d / "t00000000.png", 64, 48, fill=200)
            write_png(d / "t00001000.png", 48, 64, fill=60)
            write_png(d / "t00002000.png", 64, 48, fill=120)
        return d

    def pixel_formats(self, name, kinds):
        """Identical 32x32 mid-gray pictures at 0/1/2/3 s, written as RGB or gray."""
        d = self.tmp / name
        if not d.exists():
            d.mkdir()
            for k, kind in enumerate(kinds):
                path = d / core.frames_name(1000 * k)
                (write_rgb_png if kind == "rgb" else write_png)(path, 32, 32, fill=128)
                self.assertEqual(png_color_type(path), 2 if kind == "rgb" else 0)
        return d

    # -- timing -----------------------------------------------------------

    def test_round_trip_matches_the_video(self):
        video = self.slide_right()
        _, vfit, _, vsum = self.anim_run(video, "rt-video")
        folder = self.frames_dir(video, "0.3-1.1", "rt-frames")
        self.assertEqual(len(list(folder.glob("*.png"))), 48)   # every native frame of the span
        out, fit, run, summary = self.anim_run(folder, "rt-images")
        vb, ib = best_named_tween(vfit), best_named_tween(fit)
        self.assertEqual((ib["name"], vb["name"]), ("CSS ease-out", "CSS ease-out"))
        self.assertAlmostEqual(ib["duration_ms"], vb["duration_ms"], delta=12.0)
        self.assertAlmostEqual(ib["duration_ms"], 300, delta=12.0)
        self.assertAlmostEqual(fit["visible_duration_ms"], vfit["visible_duration_ms"],
                               delta=FRAME_MS)
        self.assertTrue(fit["fits_reliable"])
        self.assertEqual((run["input"], run["timing"]["source"], run["gaps"]),
                         ("images", "filenames", []))
        self.assertEqual(run["input_dir_abspath"], str(folder.resolve()))
        self.assertIsNone(run["video_abspath"])
        self.assertIsNone(run["normalized"])
        # recording time (-itsoffset), not time since the first image
        img_start = float(_SEG_START.search(summary).group(1))
        self.assertAlmostEqual(img_start, float(_SEG_START.search(vsum).group(1)), delta=0.0015)
        self.assertGreater(img_start, 0.3)
        rows = read_manifest(out / "s01" / "frames")
        self.assertTrue(rows)
        self.assertEqual({r["time_source"] for r in rows}, {"filename"})
        self.assertIn("- gaps: none", summary)

    def test_every_third_frame_deleted_warns_and_widens_the_uncertainty(self):
        folder = self.frames_dir(self.slide_right(), "0.3-1.1", "rt-frames")
        # every third frame from index 1: the 2-frame steps outnumber the 1-frame
        # ones, so a median-based interval would read 2 frames and find no gap
        third = self.copy_images(folder, "third", lambda k, p: k % 3 != 1)
        kept_ms = sorted(core.parse_frame_name(p.name).ms for p in third.glob("*.png"))
        self.assertEqual(len(kept_ms), 32)
        steps = [b - a for a, b in zip(kept_ms, kept_ms[1:])]
        self.assertGreater(sum(st > 25 for st in steps), sum(st <= 25 for st in steps))  # premise
        _, fit, run, summary = self.anim_run(third, "third-images")
        self.assertTrue(run["gaps"])
        self.assertEqual({g["est_missing"] for g in run["gaps"]}, {1})
        self.assertIn("gap(s) in the sequence", summary)
        self.assertIn(f"after {run['gaps'][0]['after']} at", summary)
        # the uncertainty is the widest of one frame and the steps around the motion's ends
        m = re.search(r"first changed frame ([\d.]+) s, settled at ([\d.]+) s", summary)
        first, settled = (round(float(v) * 1000) for v in m.groups())
        before = first - max(t for t in kept_ms if t < first)
        into = settled - max(t for t in kept_ms if t < settled)
        base_ms = run["timing"]["base_interval_s"] * 1000
        expected = max(base_ms, before, into)
        self.assertGreater(expected, core.GAP_FACTOR * base_ms)       # premise: a gap at an end
        self.assertAlmostEqual(fit["visible_duration_uncertainty_ms"], expected, delta=0.6)
        self.assertIn("duration uncertainty widened to", summary)
        self.assertEqual(fit["fits"][0]["family"], "tween")
        best = best_named_tween(fit)
        self.assertEqual(best["name"], "CSS ease-out")
        self.assertAlmostEqual(best["duration_ms"], 300, delta=12.0)
        self.assertTrue(fit["fits_reliable"])

    def long_gap_folder(self):
        """The 400 ms slide's frames with the first 10 moving images deleted, so
        the step before the first changed image exceeds the fitter's onset search."""
        long_dir = self.tmp / "long"
        if long_dir.exists():
            return long_dir
        folder = self.frames_dir(self.slide_left_400(), "0.3-1.2", "long-frames")
        _, full, _, full_sum = self.anim_run(folder, "long-full")
        self.assertTrue(full["fits_reliable"])
        self.assertNotIn("unreliable", full_sum)
        first_ms = round(float(_FIRST_CHANGED.search(full_sum).group(1)) * 1000)
        names = sorted(p.name for p in folder.glob("*.png"))
        moving = [n for n in names if core.parse_frame_name(n).ms >= first_ms]
        drop = set(moving[:10])
        self.copy_images(folder, "long", lambda k, p: p.name not in drop)
        kept_ms = [core.parse_frame_name(n).ms for n in names if n not in drop]
        prev = max(m for m in kept_ms if m < first_ms)
        nxt = min(m for m in kept_ms if m > first_ms)
        self.assertGreater(nxt - prev, core.ONSET_SEARCH_INTERVALS * FRAME_MS)   # premise
        return long_dir

    def test_frames_missing_before_the_motion_mark_the_fits_unreliable(self):
        long_dir = self.long_gap_folder()
        _, fit, run, summary = self.anim_run(long_dir, "long-images")
        self.assertFalse(fit["fits_reliable"])
        self.assertIn("beyond the fitter's onset search", fit["fits_unreliable_reason"])
        self.assertIn("unreliable (gap before the motion)", summary)
        self.assertIn("- warning: fitted durations are unreliable:", summary)
        self.assertTrue(fit["fits"])   # kept for inspection
        # the true 400 ms lies within the widened visible-duration bounds
        vis, unc = fit["visible_duration_ms"], fit["visible_duration_uncertainty_ms"]
        self.assertLessEqual(vis - unc, 400 + FRAME_MS, fit)
        self.assertGreaterEqual(vis + unc, 400 - 2 * FRAME_MS, fit)

    def test_recommended_uncertainty_is_in_real_time_under_time_scale(self):
        long_dir = self.long_gap_folder()
        _, fit1, _, _ = self.anim_run(long_dir, "long-ts1")
        _, fit5, _, summary = self.anim_run(long_dir, "long-ts5", "--time-scale", "5")
        u1, u5 = fit1["visible_duration_uncertainty_ms"], fit5["visible_duration_uncertainty_ms"]
        self.assertGreater(u1, 100)                                   # premise: a widened ±
        self.assertAlmostEqual(u5, u1 / 5, delta=0.6)
        shown = f"±{u5:.0f}"
        self.assertIn(f"({shown}) |", summary)                        # the segment table
        self.assertIn(f"use the visible duration {shown} ms instead", fit5["fits_unreliable_reason"])
        self.assertIn(f"duration uncertainty widened to {shown} ms by a", summary)
        self.assertIn("ms step (recording time) before the first changed image", summary)
        self.assertNotIn(f"±{u1:.0f} ms", summary)
        self.assertNotIn("(recording time)", fit1["fits_unreliable_reason"])

    def test_fps_times_untimed_names_in_natural_order(self):
        folder = self.frames_dir(self.slide_right(), "0.3-1.1", "rt-frames")
        d = self.tmp / "fps"
        d.mkdir()
        for k, p in enumerate(sorted(folder.glob("*.png")), start=1):
            shutil.copy(p, d / f"img{k}.png")
        names = [p.name for p in d.glob("*.png")]
        self.assertNotEqual(sorted(names), sorted(names, key=core.natural_key))   # premise
        out, fit, run, summary = self.anim_run(d, "fps-images", "--fps", "60")
        best = best_named_tween(fit)
        self.assertEqual(best["name"], "CSS ease-out")
        self.assertAlmostEqual(best["duration_ms"], 300, delta=12.0)
        self.assertIn("timing assumed from --fps 60, not measured", summary)
        self.assertEqual((run["timing"]["source"], run["timing"]["fps"]), ("fps", "60"))
        self.assertEqual({r["time_source"] for r in read_manifest(out / "s01" / "frames")},
                         {"fps"})

    # -- sizes and pixel formats --------------------------------------------

    def test_anim_refuses_mixed_sizes_naming_the_odd_file(self):
        out = self.tmp / "mixed-anim"
        cp = run_cli("anim", self.mixed_sizes(), "--out", out)
        self.assertEqual(cp.returncode, 1, cp.stderr)
        self.assertIn("anim needs images of one size: most are 64x48", cp.stderr)
        self.assertIn("t00001000.png 48x64", cp.stderr)
        self.assertFalse(out.exists())

    def test_bug_letterboxes_mixed_sizes(self):
        out = self.tmp / "mixed-bug"
        self.cli_ok("bug", self.mixed_sizes(), "--out", out)
        run = json.loads((out / "run.json").read_text())
        self.assertEqual(run["letterboxed"], "64x64")
        self.assertEqual(run["sizes"], {"64x48": 2, "48x64": 1})
        self.assertIsNone(run["manifest"])
        self.assertIn("letterboxed onto a 64x64 canvas", run["manifest_note"])
        self.assertFalse((out / "frames" / "frames.tsv").exists())
        saved = sorted((out / "frames").glob("*.png"))
        self.assertEqual(len(saved), 3)
        for p in saved:
            with open(p, "rb") as fh:
                self.assertEqual(core.png_size(fh.read(24)), (64, 64))
        if HAVE_MAGICK:
            self.assertTrue(list(out.glob("sheet_*.png")))
        cp = run_cli("bug", self.mixed_sizes(), "--roi", "0,0,10,10", "--out", self.tmp / "m-roi")
        self.assertEqual(cp.returncode, 1)
        self.assertIn("need images of one size", cp.stderr)

    def test_pixel_format_changes_keep_the_detector_state(self):
        results = {}
        for name, kinds in (("pf-mixed", ["rgb", "gray", "rgb", "gray"]),
                            ("pf-rgb", ["rgb"] * 4)):
            out = self.tmp / f"{name}-bug"
            self.cli_ok("bug", self.pixel_formats(name, kinds), "--freeze-min", "1.5",
                        "--out", out)
            run = json.loads((out / "run.json").read_text())
            freezes = [iv for iv in run["intervals"] if iv["kind"] == "freeze"]
            results[name] = (run["picks"], [iv["start_s"] for iv in freezes], run["normalized"])
        self.assertEqual(results["pf-mixed"][:2], (1, [0.0]))
        self.assertEqual(results["pf-rgb"][:2], (1, [0.0]))
        self.assertEqual(results["pf-mixed"][2]["pix_fmt"], "rgb24")
        self.assertIsNone(results["pf-rgb"][2])

    def test_anim_on_alternating_pixel_formats_still_fits(self):
        folder = self.frames_dir(self.slide_right(), "0.3-1.1", "rt-frames")
        d = self.tmp / "pf-anim"
        d.mkdir()
        for k, p in enumerate(sorted(folder.glob("*.png"))):
            if k % 2:
                subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(p),
                                "-pix_fmt", "gray", "-y", str(d / p.name)], check=True)
                self.assertEqual(png_color_type(d / p.name), 0)
            else:
                shutil.copy(p, d / p.name)
        _, fit, run, _ = self.anim_run(d, "pf-anim-out")
        self.assertIsNotNone(run["normalized"])
        best = best_named_tween(fit)
        self.assertEqual(best["name"], "CSS ease-out")
        self.assertAlmostEqual(best["duration_ms"], 300, delta=12.0)

    def test_mixed_codecs_are_staged_as_png(self):
        # concat decodes every file with the first one's codec, so a jpeg among
        # pngs is converted in the stage; the folder itself is left untouched
        d = self.tmp / "codecs"
        d.mkdir()
        write_png(d / "t00000000.png", 32, 32, fill=40)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        "color=white:s=32x32", "-frames:v", "1", "-y", str(d / "t00001000.jpg")],
                       check=True)
        write_png(d / "t00002000.png", 32, 32, fill=40)
        before = {p.name: p.read_bytes() for p in d.iterdir()}
        out = self.tmp / "codecs-bug"
        self.cli_ok("bug", d, "--out", out)
        run = json.loads((out / "run.json").read_text())
        self.assertEqual(run["images"], 3)
        self.assertEqual(run["picks"], 3)
        self.assertEqual({p.name: p.read_bytes() for p in d.iterdir()}, before)
        self.assertIn("(jpeg, png)", (out / "summary.md").read_text())

    def test_animated_image_beside_other_codecs_is_refused(self):
        # a non-PNG among PNGs is converted to one PNG frame in the stage; its
        # frames must be counted before that, or an animation's later frames vanish
        d = self.tmp / "anim-webp"
        d.mkdir()
        write_png(d / "t00000000.png", 32, 32, fill=200)
        webp = d / "t00001000.webp"
        cp = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
             "color=red:s=32x32:d=0.2:r=10", "-vf",
             "drawbox=x=0:y=0:w=16:h=16:color=blue@1:t=fill:enable='gte(t,0.1)'",
             "-loop", "0", "-c:v", "libwebp_anim", str(webp)], capture_output=True, text=True)
        if cp.returncode != 0:
            self.skipTest(f"this ffmpeg cannot write an animated webp: {cp.stderr[-200:]}")
        frames = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_entries",
                                 "stream=nb_read_frames", "-of", "csv=p=0", str(webp)],
                                capture_output=True, text=True).stdout.strip()
        # encoding and decoding differ: FFmpeg 5.1.1 and 7.0.2 write animated webp
        # but cannot decode its animation (measured, t2229), so the fixture means
        # nothing there; the CLI then stops on ffmpeg's decode error instead
        if frames != "2":
            self.skipTest(f"this ffmpeg cannot decode an animated webp (counted {frames!r})")
        self.assertEqual(frames, "2")                                  # premise: animated
        for mode in ("bug", "anim"):
            with self.subTest(mode=mode):
                cp = run_cli(mode, d, "--out", self.tmp / f"anim-webp-{mode}")
                self.assertEqual(cp.returncode, 1, cp.stderr)
                self.assertIn("t00001000.webp decodes to more than one frame", cp.stderr)

    # -- bug mode on a uniform folder -----------------------------------------

    def test_bug_on_a_uniform_folder(self):
        folder = self.tmp / "bug-folder"
        write_frames_dir(folder, [500, 1500, 1700, 1717, 4000])
        out = self.tmp / "bug-folder-out"
        self.cli_ok("bug", folder, "--out", out)
        with open(out / "timeline.tsv", newline="") as fh:
            rows = [r for r in csv.DictReader(fh, delimiter="\t") if r["kind"] == "frame"]
        self.assertEqual(rows[0]["time_s"], "0.500")
        self.assertLessEqual({r["time_s"] for r in rows},
                             {"0.500", "1.500", "1.700", "1.717", "4.000"})
        self.assertEqual({r["time_source"] for r in read_manifest(out / "frames")}, {"filename"})
        summary = (out / "summary.md").read_text()
        self.assertIn("silence not checked (no audio: image folder)", summary)
        self.assertIn("- input: 5 images in", summary)
        run = json.loads((out / "run.json").read_text())
        self.assertEqual(run["input"], "images")
        cp = run_cli("bug", folder, "--extract-audio", "--out", self.tmp / "bug-audio")
        self.assertEqual(cp.returncode, 1)
        self.assertIn("has no audio", cp.stderr)

    # -- refusals ---------------------------------------------------------------

    def test_bad_folders_fail_cleanly(self):
        def case(name, files):
            d = self.tmp / "bad" / name
            d.mkdir(parents=True)
            for fname, kind in files:
                if kind == "dir":
                    (d / fname).mkdir()
                elif kind == "text":
                    (d / fname).write_text("not an image")
                else:
                    write_png(d / fname, 16, 16, fill=100)
            return d
        cases = [
            (case("empty", [("frames", "dir")]), [], "no png/jpg/jpeg/webp images",
             "pass that"),
            (case("one", [("t00000000.png", "png")]), [], "need at least 2 images", None),
            (case("fake", [("t00000000.png", "png"), ("t00000017.png", "text")]), [],
             "t00000017.png: not a png, jpeg or webp image", None),
            (case("partial", [("t00000000.png", "png"), ("shot.png", "png"),
                              ("t00000033.png", "png")]), [], "carry no time: shot.png", None),
            (case("dup", [("t00000017.png", "png"), ("t00000017_b.png", "png")]), [],
             "carry the same time (17 ms)", None),
            (case("timed-fps", [("t00000000.png", "png"), ("t00000017.png", "png")]),
             ["--fps", "60"], "--fps is only for images whose names carry no time", None),
        ]
        for d, extra, msg, msg2 in cases:
            for mode in ("bug", "anim"):
                with self.subTest(folder=d.name, mode=mode):
                    cp = run_cli(mode, d, *extra, "--out", self.tmp / "bad-out" / f"{d.name}-{mode}")
                    self.assertEqual(cp.returncode, 1, cp.stderr)
                    self.assertIn(msg, cp.stderr)
                    if msg2:
                        self.assertIn(msg2, cp.stderr)
                    self.assertNotIn("Traceback", cp.stderr)
        video = self.slide_right()
        cp = run_cli("anim", video, "--fps", "60", "--out", self.tmp / "bad-out" / "fps-video")
        self.assertEqual(cp.returncode, 1)
        self.assertIn("--fps applies only to a folder of images", cp.stderr)
        cp = run_cli("anim", self.mixed_sizes(), "--fps", "0")
        self.assertEqual(cp.returncode, 2)
        self.assertIn("must be a positive decimal number", cp.stderr)
        for mode, extra in (("info", []), ("frames", ["--at", "0"])):
            cp = run_cli(mode, self.mixed_sizes(), *extra)
            self.assertEqual(cp.returncode, 2, mode)
            self.assertIn("no such file", cp.stderr)
        cp = run_cli("bug", self.tmp / "nowhere")
        self.assertEqual(cp.returncode, 2)
        self.assertIn("no such file or folder", cp.stderr)

    # -- the concat input itself --------------------------------------------------

    def test_concat_script_names_only_generated_files_and_is_removed(self):
        import video_prep
        folder = self.mixed_sizes()
        with video_prep.ImageInput(folder, None, "bug") as src:
            text = (src.stage / "list.ffconcat").read_text()
            stage = src.stage
            self.assertEqual(src.ffin[src.ffin.index("-safe") + 1], "0")
            self.assertTrue(stage.exists())
        files = re.findall(r"^file '(.*)'$", text, re.M)
        self.assertEqual(len(files), 3)
        for f in files:
            self.assertRegex(f, r"^img_\d{6}\.png$")
        self.assertEqual(text.count(f"option framerate {video_prep.STAGE_RATE}\n"), 3)
        self.assertFalse(stage.exists())

    def test_a_concat_demuxer_that_loses_the_times_is_refused(self):
        import video_prep
        orig, hit = video_prep.ImageInput._use_list, []

        def without_option(self_, files, list_name):
            orig(self_, files, list_name)
            path = self_.stage / list_name
            text = path.read_text()
            self.assertIn("option framerate", text)
            path.write_text(text.replace(f"option framerate {video_prep.STAGE_RATE}\n", ""))
            hit.append(list_name)

        with mock.patch.object(video_prep.ImageInput, "_use_list", without_option):
            with self.assertRaises(video_prep.PrepError) as cm:
                with video_prep.ImageInput(self.mixed_sizes(), None, "bug"):
                    pass
        self.assertTrue(hit)
        self.assertIn("does not keep the image times", str(cm.exception))

    def test_normalisation_that_leaves_two_configurations_is_refused(self):
        import video_prep

        def no_op(self_, fmts, configs):
            self_.normalized = {"pix_fmt": "rgb24", "reason": "test", "formats_seen": [],
                                "note": None}

        folder = self.pixel_formats("pf-mixed", ["rgb", "gray", "rgb", "gray"])
        with mock.patch.object(video_prep.ImageInput, "_normalize", no_op):
            with self.assertRaises(video_prep.PrepError) as cm:
                with video_prep.ImageInput(folder, None, "bug"):
                    pass
        self.assertIn("could not give the images one uniform format", str(cm.exception))

    # -- consumers ------------------------------------------------------------------

    def test_pick_names_the_image_folder_not_a_video(self):
        folder = self.frames_dir(self.slide_right(), "0.3-1.1", "rt-frames")
        run_dir = self.tmp / "pick-src"
        self.cli_ok("anim", folder, "--out", run_dir)
        out = self.tmp / "pick-images"
        cp = run_cli("pick", run_dir, "--out", out)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        data = json.loads((out / "pick.json").read_text())
        self.assertIsNone(data["source"]["video"])
        self.assertIn(f"the run read a folder of images ({folder.resolve()}), not a video",
                      data["source_line"])


if __name__ == "__main__":
    unittest.main()
