"""End-to-end tests of aitask-screen-recording: synthetic recordings through the
real CLI (needs ffmpeg; skipped without it).

Ground truth comes from tests/screen_recording_synth.py. Timing tolerances are one frame at 60 fps
(16.7 ms) for visible durations and 12 ms for fitted tween durations unless noted.

Run: python3 tests/test_screen_recording_cli.py
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / ".aitask-scripts" / "screen_recording" / "video_prep.py"
WRAPPER = HERE.parent / ".aitask-scripts" / "aitask_screen_recording.sh"
sys.path.insert(0, str(HERE))
import screen_recording_synth as synth  # noqa: E402

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
        if HAVE_MAGICK:
            self.assertTrue((out / "s01" / "sheet_01.png").exists())
            self.assertTrue((out / "s01" / "plot.png").exists())

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
        _, fits = self.anim("fade", synth.card_frames(
            synth.tween(synth.EASE_IN_OUT, 0.5, 0.3), 1.4, "fade"))
        self.assertEqual((fits[0]["kind"], fits[0]["signal"]), ("fade/blend", "blend"))
        self.assert_tween(fits[0], "CSS ease-in-out / iOS easeInOut", 300)

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


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe not installed")
class BugMode(_VideoCase):
    def timeline(self, out):
        with open(out / "timeline.tsv") as fh:
            return [(float(r["time_s"]), set(r["why"].split("+")), r["file"])
                    for r in csv.DictReader(fh, delimiter="\t")]

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
        if HAVE_MAGICK:
            self.assertTrue((out / "sheet_01.png").exists())
        summary = (out / "summary.md").read_text()
        self.assertIn("picked 7 frames", summary)
        self.assertIn("audio: none", summary)

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


if __name__ == "__main__":
    unittest.main()
