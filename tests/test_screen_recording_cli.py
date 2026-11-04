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
