"""Unit tests for .aitask-scripts/screen_recording/vp_core.py (aitask-screen-recording):
pure functions, no ffmpeg needed.

Run: python3 tests/test_screen_recording_core.py
"""
from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import subprocess
import sys
import unittest
from fractions import Fraction
from pathlib import Path

SR_DIR = Path(__file__).resolve().parents[1] / ".aitask-scripts" / "screen_recording"
sys.path.insert(0, str(SR_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vp_core as core  # noqa: E402
import vp_pick as pick  # noqa: E402
import video_prep  # noqa: E402
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

    def test_black_mark_on_a_kept_frame_merges_its_reason(self):
        times = [0.0, 2.0, 2.0 + 1 / 60]
        picks, _ = core.select_key_frames(times, 4.0, marks=[core.Mark(2.0, "black", index=1)])
        self.assertEqual([(round(p.t, 3), p.reasons, p.dwell_basis) for p in picks],
                         [(0.0, ["start", "state"], "decimate"),
                          (2.0, ["brief", "black"], "decimate"),
                          (2.017, ["state", "end"], "decimate")])

    def test_black_mark_off_the_kept_list_keeps_its_own_duration(self):
        # mpdecimate kept only t=0 (a 1 s still screen); the black frame at 0.5 s
        # lasted one frame: its dwell is the black run, not the 0.5 s to the end
        picks, _ = core.select_key_frames(
            [0.0], 1.0, marks=[core.Mark(0.5, "black", ref=30, dwell=1 / 60,
                                         dwell_basis="black run")])
        self.assertEqual([(p.t, p.index, p.ref, p.reasons, round(p.dwell, 4), p.dwell_basis)
                          for p in picks],
                         [(0.0, 0, None, ["start", "state", "end"], 1.0, "decimate"),
                          (0.5, None, 30, ["black"], 0.0167, "black run")])

    def test_cap_ranks_black_below_start_end_and_above_states(self):
        times = [0.0, 1.0, 2.0, 3.0, 4.0]       # five 1 s states
        marks = [core.Mark(0.5, "black", ref=1, dwell=0.05, dwell_basis="black run"),
                 core.Mark(2.5, "black", ref=2, dwell=0.05, dwell_basis="black run")]
        picks, dropped = core.select_key_frames(times, 5.0, max_frames=4, marks=marks)
        self.assertEqual(dropped, 3)
        self.assertEqual([(p.t, tuple(p.reasons)) for p in picks],
                         [(0.0, ("start", "state")), (0.5, ("black",)), (2.5, ("black",)),
                          (4.0, ("state", "end"))])

    def test_marks_do_not_change_unmarked_selection(self):
        times = [0.0] + [1.0 + k / 60 for k in range(0, 150)] + [3.6]
        self.assertEqual(core.select_key_frames(times, 5.0),
                         core.select_key_frames(times, 5.0, marks=()))


# Verbatim ffmpeg n9.0.2 output captured while planning t1893_2 (lavfi sources,
# `<detectors>,metadata=mode=print[,mpdecimate,showinfo]`), with noise lines kept.
LOG_DARK_FLASH = """\
[Parsed_showinfo_3 @ 0x7f3ee40047c0] config in time_base: 1/60, frame_rate: 60/1
[Parsed_showinfo_3 @ 0x7f3ee40047c0] n:   0 pts:      0 pts_time:0       duration:      1
[Parsed_metadata_1 @ 0x7f3ee4004280] frame:30   pts:30      pts_time:0.5
[Parsed_metadata_1 @ 0x7f3ee4004280] lavfi.black_start=0.5
[Parsed_blackdetect_0 @ 0x7f3ee4004000] black_start:0.5 black_end:0.516667 black_duration:0.0166667
[Parsed_metadata_1 @ 0x7f3ee4004280] frame:31   pts:31      pts_time:0.516667
[Parsed_metadata_1 @ 0x7f3ee4004280] lavfi.black_end=0.516667
"""
LOG_RECOVER_ON_LAST_FRAME = """\
[Parsed_metadata_1 @ 0x7fad9c004180] frame:30   pts:30      pts_time:0.5
[Parsed_metadata_1 @ 0x7fad9c004180] lavfi.black_start=0.5
[Parsed_blackdetect_0 @ 0x7fad9c003f00] black_start:0.5 black_end:0.983333 black_duration:0.483333
[Parsed_metadata_1 @ 0x7fad9c004180] frame:59   pts:59      pts_time:0.983333
[Parsed_metadata_1 @ 0x7fad9c004180] lavfi.black_end=0.983333
"""
LOG_BLACK_TO_EOF = """\
[Parsed_metadata_1 @ 0x7f785c004180] frame:30   pts:30      pts_time:0.5
[Parsed_metadata_1 @ 0x7f785c004180] lavfi.black_start=0.5
[Parsed_blackdetect_0 @ 0x7f785c003f00] black_start:0.5 black_end:0.983333 black_duration:0.483333
frame=   60 fps=0.0 q=-0.0 Lsize=N/A time=00:00:01.00 bitrate=N/A speed=80.4x
"""
LOG_BLACK_D01 = """\
[Parsed_metadata_1 @ 0x7f0b10004180] frame:10   pts:10      pts_time:0.166667
[Parsed_metadata_1 @ 0x7f0b10004180] lavfi.black_start=0.166667
[Parsed_metadata_1 @ 0x7f0b10004180] frame:11   pts:11      pts_time:0.183333
[Parsed_metadata_1 @ 0x7f0b10004180] lavfi.black_end=0.183333
[Parsed_metadata_1 @ 0x7f0b10004180] frame:30   pts:30      pts_time:0.5
[Parsed_metadata_1 @ 0x7f0b10004180] lavfi.black_start=0.5
[Parsed_blackdetect_0 @ 0x7f0b10003f00] black_start:0.5 black_end:0.766667 black_duration:0.266667
[Parsed_metadata_1 @ 0x7f0b10004180] frame:46   pts:46      pts_time:0.766667
[Parsed_metadata_1 @ 0x7f0b10004180] lavfi.black_end=0.766667
"""
LOG_FREEZES = """\
[Parsed_freezedetect_0 @ 0x7fbb8c003e40] lavfi.freezedetect.freeze_start: 1
[Parsed_metadata_1 @ 0x7fbb8c004100] frame:180  pts:180     pts_time:3
[Parsed_metadata_1 @ 0x7fbb8c004100] lavfi.freezedetect.freeze_start=1
[Parsed_freezedetect_0 @ 0x7fbb8c003e40] lavfi.freezedetect.freeze_duration: 3.016667
[Parsed_freezedetect_0 @ 0x7fbb8c003e40] lavfi.freezedetect.freeze_end: 4.016667
[Parsed_metadata_1 @ 0x7fbb8c004100] frame:241  pts:241     pts_time:4.016667
[Parsed_metadata_1 @ 0x7fbb8c004100] lavfi.freezedetect.freeze_duration=3.016667
[Parsed_metadata_1 @ 0x7fbb8c004100] lavfi.freezedetect.freeze_end=4.016667
[Parsed_freezedetect_0 @ 0x7fbb8c003e40] lavfi.freezedetect.freeze_start: 5
[Parsed_metadata_1 @ 0x7fbb8c004100] frame:420  pts:420     pts_time:7
[Parsed_metadata_1 @ 0x7fbb8c004100] lavfi.freezedetect.freeze_start=5
"""
# freezedetect on the bug_frames() fixture: the frame that proves the 2 s
# duration is also the one that ends the freeze, so both keys sit on one frame
LOG_FREEZE_ONE_FRAME = """\
[Parsed_freezedetect_0 @ 0x7fc054004040] lavfi.freezedetect.freeze_start: 4.5
[Parsed_freezedetect_0 @ 0x7fc054004040] lavfi.freezedetect.freeze_duration: 2
[Parsed_freezedetect_0 @ 0x7fc054004040] lavfi.freezedetect.freeze_end: 6.5
[Parsed_metadata_2 @ 0x7fc054004580] frame:390  pts:99840   pts_time:6.5
[Parsed_metadata_2 @ 0x7fc054004580] lavfi.freezedetect.freeze_start=4.5
[Parsed_metadata_2 @ 0x7fc054004580] lavfi.freezedetect.freeze_duration=2
[Parsed_metadata_2 @ 0x7fc054004580] lavfi.freezedetect.freeze_end=6.5
"""
LOG_SILENCE_RECOVERS = """\
[Parsed_silencedetect_0 @ 0x7f5cb8003e40] silence_start: 4.5
[Parsed_ametadata_1 @ 0x7f5cb80040c0] frame:304  pts:311296  pts_time:6.485333
[Parsed_ametadata_1 @ 0x7f5cb80040c0] lavfi.silence_start=4.5
[Parsed_silencedetect_0 @ 0x7f5cb8003e40] silence_end: 7.950021 | silence_duration: 3.450021
[Parsed_ametadata_1 @ 0x7f5cb80040c0] frame:372  pts:380928  pts_time:7.936
[Parsed_ametadata_1 @ 0x7f5cb80040c0] lavfi.silence_end=7.950021
[Parsed_ametadata_1 @ 0x7f5cb80040c0] lavfi.silence_duration=3.450021
"""
LOG_SILENCE_TO_EOF = """\
[Parsed_silencedetect_0 @ 0x7f15c0003e40] silence_start: 4.5
[Parsed_ametadata_1 @ 0x7f15c00040c0] frame:304  pts:311296  pts_time:6.485333
[Parsed_ametadata_1 @ 0x7f15c00040c0] lavfi.silence_start=4.5
[Parsed_silencedetect_0 @ 0x7f15c0003e40] silence_end: 8 | silence_duration: 3.5
"""
LOG_SILENCE_ATRIM = """\
[Parsed_silencedetect_1 @ 0x7f2698004280] silence_start: 4.5
[Parsed_ametadata_2 @ 0x7f2698004500] frame:258  pts:311296  pts_time:6.485333
[Parsed_ametadata_2 @ 0x7f2698004500] lavfi.silence_start=4.5
[Parsed_silencedetect_1 @ 0x7f2698004280] silence_end: 7 | silence_duration: 2.5
"""


class ParseMetadataPrint(unittest.TestCase):
    def test_blocks_with_pts_and_raw_values(self):
        self.assertEqual(core.parse_metadata_print(LOG_DARK_FLASH),
                         [(30, 0.5, {"lavfi.black_start": "0.5"}),
                          (31, 0.516667, {"lavfi.black_end": "0.516667"})])

    def test_audio_blocks_and_detector_lines_are_separate(self):
        blocks = core.parse_metadata_print(LOG_SILENCE_RECOVERS)
        self.assertEqual([b[0] for b in blocks], [311296, 380928])
        self.assertEqual(blocks[1][2], {"lavfi.silence_end": "7.950021",
                                        "lavfi.silence_duration": "3.450021"})


class TriageIntervals(unittest.TestCase):
    def ivs(self, video="", audio="", span_end=1.0, **kw):
        return [(iv.kind, iv.start, iv.end, iv.end_observed, iv.frame_pts)
                for iv in core.triage_intervals(video, audio, span_end, **kw)]

    def test_black_frame_is_the_detector_frame_not_a_kept_one(self):
        self.assertEqual(self.ivs(LOG_DARK_FLASH),
                         [("black", 0.5, 0.516667, True, 30)])

    def test_recovery_on_the_final_frame_is_observed(self):
        self.assertEqual(self.ivs(LOG_RECOVER_ON_LAST_FRAME),
                         [("black", 0.5, 0.983333, True, 30)])

    def test_black_cut_by_eof_is_a_lower_bound_at_the_span_end(self):
        # blackdetect logs the same black_end:0.983333 as above, but no metadata
        self.assertEqual(self.ivs(LOG_BLACK_TO_EOF, span_end=1.0),
                         [("black", 0.5, 1.0, False, 30)])

    def test_black_min_drops_only_short_observed_runs(self):
        self.assertEqual(self.ivs(LOG_BLACK_D01, black_min=0.1),
                         [("black", 0.5, 0.766667, True, 30)])
        self.assertEqual(len(self.ivs(LOG_BLACK_D01)), 2)
        # an unobserved end proves nothing about the length: kept whatever the min
        self.assertEqual(self.ivs(LOG_BLACK_TO_EOF, span_end=0.55, black_min=0.1),
                         [("black", 0.5, 0.55, False, 30)])

    def test_freeze_observed_and_open(self):
        self.assertEqual(self.ivs(LOG_FREEZES, span_end=8.0),
                         [("freeze", 1.0, 4.016667, True, None),
                          ("freeze", 5.0, 8.0, False, None)])

    def test_freeze_start_and_end_on_one_frame(self):
        self.assertEqual(self.ivs(LOG_FREEZE_ONE_FRAME, span_end=7.5),
                         [("freeze", 4.5, 6.5, True, None)])

    def test_silence_observed_end(self):
        self.assertEqual(self.ivs(audio=LOG_SILENCE_RECOVERS, span_end=8.0),
                         [("silence", 4.5, 7.950021, True, None)])

    def test_trailing_silence_ends_at_the_audio_eof_unobserved(self):
        self.assertEqual(self.ivs(audio=LOG_SILENCE_TO_EOF, span_end=9.0),
                         [("silence", 4.5, 8.0, False, None)])
        self.assertEqual(self.ivs(audio=LOG_SILENCE_ATRIM, span_end=7.0),
                         [("silence", 4.5, 7.0, False, None)])

    def test_sorted_across_kinds(self):
        got = self.ivs(LOG_FREEZES + LOG_DARK_FLASH, LOG_SILENCE_RECOVERS, span_end=8.0)
        self.assertEqual([(k, s) for k, s, *_ in got],
                         [("black", 0.5), ("freeze", 1.0), ("silence", 4.5), ("freeze", 5.0)])


# ffprobe -select_streams v:0 -show_entries packet=pts_time,duration_time
# -of compact=p=0, B-frames (bframes=3): demux order is not presentation order
PACKETS_BFRAMES = """\
pts_time=0.933333|duration_time=0.016667|
pts_time=0.983333|duration_time=0.016667|
pts_time=0.950000|duration_time=0.016667|
pts_time=0.966667|duration_time=0.016667|
"""


class ParsePackets(unittest.TestCase):
    def test_fields_and_na(self):
        self.assertEqual(core.parse_packets(PACKETS_BFRAMES + "pts_time=N/A|duration_time=N/A|\n\n"),
                         [(0.933333, 0.016667), (0.983333, 0.016667), (0.95, 0.016667),
                          (0.966667, 0.016667), (None, None)])


class VideoSpan(unittest.TestCase):
    def span(self, packets, origin=0.0, range_end=None, ranged=False, first=0.933333,
             last=0.95, container=3.0):
        s = core.video_span(packets, origin, range_end=range_end, ranged=ranged or
                            range_end is not None, first_kept_t=first, last_kept_t=last,
                            container_end=container)
        return round(s.end_t, 6), round(s.interval_end, 6), s.proven

    def test_coverage_comes_from_the_latest_presentation_time(self):
        # the last demuxed row is 0.966667; taking it would lose one frame
        self.assertEqual(self.span(core.parse_packets(PACKETS_BFRAMES)), (1.0, 1.0, True))

    def test_nonzero_origin_is_normalised(self):
        pk = [(1.433333 + p, d) for p, d in core.parse_packets(PACKETS_BFRAMES)]
        self.assertEqual(self.span(pk, origin=1.433333), (1.0, 1.0, True))

    def test_origin_mismatch_fails_closed(self):
        pk = [(5.0 + p, d) for p, d in core.parse_packets(PACKETS_BFRAMES)]
        s = core.video_span(pk, 0.0, range_end=None, ranged=False, first_kept_t=0.933333,
                            last_kept_t=0.95, container_end=3.0)
        self.assertFalse(s.proven)
        self.assertEqual((s.end_t, s.interval_end), (3.0, 0.95))
        self.assertIn("origin could not be confirmed", s.note)

    def test_missing_last_duration_is_not_proven(self):
        pk = [(0.933333, 0.016667), (0.983333, None), (0.95, 0.016667)]
        s = core.video_span(pk, 0.0, range_end=None, ranged=False, first_kept_t=0.933333,
                            last_kept_t=0.95, container_end=3.0)
        self.assertEqual((s.end_t, s.interval_end, s.proven, s.max_pts), (3.0, 0.983333, False,
                                                                           0.983333))
        self.assertIn("duration is unknown", s.note)
        pk0 = [(0.933333, 0.016667), (0.983333, 0.0)]
        self.assertFalse(core.video_span(pk0, 0.0, range_end=None, ranged=False,
                                         first_kept_t=0.933333, last_kept_t=0.95,
                                         container_end=3.0).proven)

    def test_missing_pts_is_not_proven(self):
        pk = core.parse_packets(PACKETS_BFRAMES) + [(None, 0.016667)]
        self.assertFalse(self.span(pk)[2])

    def test_range_before_the_last_frame_is_proven_by_it(self):
        self.assertEqual(self.span(core.parse_packets(PACKETS_BFRAMES), range_end=0.96),
                         (0.96, 0.96, True))

    def test_range_after_coverage_is_clipped_to_coverage(self):
        self.assertEqual(self.span(core.parse_packets(PACKETS_BFRAMES), range_end=2.0),
                         (1.0, 1.0, True))


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


class FrameNames(unittest.TestCase):
    def test_three_forms_carry_exact_milliseconds(self):
        self.assertEqual(core.parse_frame_name("t00007040.png"),
                         core.FrameName(7040, "frames", None))
        self.assertEqual(core.parse_frame_name("04_5.500s.png"), core.FrameName(5500, "bug", 4))
        self.assertEqual(core.parse_frame_name("f013_0.483s.png"),
                         core.FrameName(483, "anim", 13))
        self.assertEqual(core.parse_frame_name("123_1234.567s.png").ms, 1234567)
        self.assertEqual(core.parse_frame_name("t123456789.JPG").ms, 123456789)
        self.assertEqual(core.parse_frame_name("t00000017.webp").ms, 17)

    def test_formatters_keep_the_existing_names(self):
        # the bug/anim names are cited by SKILL.md and the docs: byte for byte unchanged
        self.assertEqual(core.bug_frame_name(4, 5.5), "04_5.500s.png")
        self.assertEqual(core.bug_frame_name(123, 0.0), "123_0.000s.png")
        self.assertEqual(core.anim_frame_name(13, 0.483333), "f013_0.483s.png")
        self.assertEqual(core.frames_name(7040), "t00007040.png")

    def test_formatter_parser_round_trip(self):
        for t in (0.0, 0.016667, 0.0175, 1.0049999, 7.04, 59.999, 1234.5675):
            with self.subTest(t=t):
                self.assertEqual(core.parse_frame_name(core.bug_frame_name(7, t)).ms,
                                 core.time_ms(t))
                self.assertEqual(core.parse_frame_name(core.anim_frame_name(7, t)).ms,
                                 core.time_ms(t))
        for ms in (0, 17, 7040, 99_999_999, 123_456_789):
            self.assertEqual(core.parse_frame_name(core.frames_name(ms)).ms, ms)

    def test_garbage_is_rejected_not_misread(self):
        for name in ["t7040.png", "t0000704.png", "01_5.5s.png", "01_5.5000s.png", "1_5.500s.png",
                     "f13_0.483s.png", "x01_5.500s.png", "sheet_01.png", "frames.tsv",
                     "t00007040.txt", "t00007040.gif", "t00007040", " t00007040.png",
                     "t00007040.png.bak", "01_-1.000s.png", "t0000704O.png", "t-0007040.png",
                     "IMG_20260101_120000.png", "frame_0001.png", "04_5.500.png",
                     "t00007040_edited.png", ".png", "t00007040..png"]:
            with self.subTest(name=name):
                self.assertIsNone(core.parse_frame_name(name))

    def test_suffix_variant_reads_edited_names(self):
        ok = {"t00007040_edited.png": (7040, "frames", "_edited"),
              "f013_0.483s (1).png": (483, "anim", " (1)"),
              "04_5.500s-crop.JPG": (5500, "bug", "-crop"),
              "t00007040.v2.webp": (7040, "frames", ".v2"),
              "t00007040.png": (7040, "frames", "")}
        for name, (ms, form, sfx) in ok.items():
            with self.subTest(name=name):
                fn = core.parse_frame_name(name, allow_suffix=True)
                self.assertEqual((fn.ms, fn.form, fn.suffix), (ms, form, sfx))
        for name in ["t00007040x.png", "t0000704_e.png", "sheet_01.png", "IMG_20260101_120000.png",
                     "t00007040[1].png", "x_t00007040.png", "t00007040_edited.txt",
                     "01_5.5s_x.png", "f13_0.483s_x.png"]:
            with self.subTest(name=name):
                self.assertIsNone(core.parse_frame_name(name, allow_suffix=True))
        # the strict default is unchanged: suffixed names carry no time there
        for name in ["t00007040_edited.png", "f013_0.483s (1).png", "04_5.500s-crop.JPG"]:
            self.assertIsNone(core.parse_frame_name(name))


class SheetPlan(unittest.TestCase):
    def test_order_by_time_with_deltas_and_a_gap(self):
        names = ["t00000133.png", "t00000000.png", "t00000067.png", "t00000033.png",
                 "t00000167.png"]          # t00000100 deleted
        plan = core.plan_sheet(names)
        self.assertEqual([it.name for it in plan.items], sorted(names))
        self.assertEqual([it.delta_ms for it in plan.items], [None, 33, 34, 66, 34])
        self.assertEqual([it.order for it in plan.items], [1, 2, 3, 4, 5])
        self.assertEqual([it.name for it in plan.gaps], ["t00000133.png"])
        self.assertEqual(plan.untimed, [])
        self.assertEqual(plan.forms, ["frames"])

    def test_equal_times_give_zero_delta_and_natural_tie_break(self):
        plan = core.plan_sheet(["t00000040_v10.png", "t00000040_v2.png", "t00000040.png"])
        self.assertEqual([it.name for it in plan.items],
                         ["t00000040.png", "t00000040_v2.png", "t00000040_v10.png"])
        self.assertEqual([it.delta_ms for it in plan.items], [None, 0, 0])

    def test_untimed_come_last_in_natural_order_without_a_time(self):
        plan = core.plan_sheet(["b10.png", "t00000100.png", "a.png", "b2.png", "t00000050.png"])
        self.assertEqual([it.name for it in plan.items],
                         ["t00000050.png", "t00000100.png", "a.png", "b2.png", "b10.png"])
        self.assertEqual([it.ms for it in plan.items], [50, 100, None, None, None])
        self.assertEqual([it.delta_ms for it in plan.items], [None, 50, None, None, None])
        self.assertEqual(plan.untimed, ["a.png", "b2.png", "b10.png"])

    def test_all_untimed(self):
        plan = core.plan_sheet(["img10.png", "img9.png", "img1.png"])
        self.assertEqual([it.name for it in plan.items], ["img1.png", "img9.png", "img10.png"])
        self.assertTrue(all(it.ms is None and it.delta_ms is None for it in plan.items))
        self.assertEqual((plan.gaps, plan.forms), ([], []))

    def test_mixed_forms_are_reported(self):
        plan = core.plan_sheet(["t00001000.png", "02_0.500s.png", "f001_0.750s.png"])
        self.assertEqual(plan.forms, ["anim", "bug", "frames"])
        self.assertEqual([it.ms for it in plan.items], [500, 750, 1000])

    def test_no_gap_with_fewer_than_three_timed_images(self):
        self.assertEqual(core.plan_sheet(["t00000000.png", "t00001000.png"]).gaps, [])


class ImLabel(unittest.TestCase):
    def test_escapes_percent_and_backslash(self):
        self.assertEqual(core.im_label("50% a\\nb"), "50%% a\\\\nb")
        self.assertEqual(core.im_label("line1\nline2"), "line1\nline2")  # a real newline stays

    def test_truncate_middle_keeps_head_and_tail(self):
        self.assertEqual(core.truncate_middle("t00007040_annotated_final.png", 15),
                         "t00007...al.png")
        self.assertEqual(core.truncate_middle("short.png", 15), "short.png")
        self.assertEqual(len(core.truncate_middle("x" * 100, 20)), 20)
        self.assertEqual(core.truncate_middle("abcdef", 3), "abc")


class LabelSafeLayout(unittest.TestCase):
    def test_narrow_tiles_get_room_for_their_labels(self):
        cols, cell_w, th, s = core.label_safe_layout(8, 200, 4000, 125, 1600)
        self.assertGreaterEqual(cell_w, 125)
        self.assertLessEqual(cols * (cell_w + 8), 1600)
        self.assertLessEqual(math.ceil(8 / cols) * (th + 48), 1600)

    def test_matches_sheet_layout_when_labels_need_no_room(self):
        sys.path.insert(0, str(Path(core.__file__).parent))
        import video_prep  # noqa: E402
        for n, w, h in [(8, 360, 800), (30, 200, 120), (4, 1080, 2400)]:
            with self.subTest(n=n, w=w, h=h):
                cols, cell_w, th, _ = core.label_safe_layout(n, w, h, 1, 1600)
                self.assertEqual((cols, cell_w, th), video_prep.sheet_layout(n, w, h))

    def test_infeasible_requests_return_none(self):
        self.assertIsNone(core.label_safe_layout(1, 100, 100, 1600, 1600))
        self.assertIsNone(core.label_safe_layout(1000, 360, 800, 125, 1600))

    def test_one_tile_always_fits(self):
        sizes = [1, 2, 10, 15, 16, 17, 40, 63, 64, 300, 1000, 1567, 1600, 2400, 4000]
        for need_w in (60, 125, 400):
            for w in sizes:
                for h in sizes:
                    lay = core.label_safe_layout(1, w, h, need_w, 1600)
                    self.assertIsNotNone(lay, (w, h, need_w))
                    self.assertLessEqual(lay[1] + 8, 1600)
                    self.assertLessEqual(lay[2] + 48, 1600)


class ChunkSheets(unittest.TestCase):
    def check(self, boxes, per_sheet, need_w):
        chunks = core.chunk_sheets(boxes, per_sheet, need_w, 1600)
        starts = [c[0] for c in chunks]
        self.assertEqual(sum(c[1] for c in chunks), len(boxes))
        self.assertEqual(starts, [sum(c[1] for c in chunks[:i]) for i in range(len(chunks))])
        for start, count, _, lay in chunks:
            part = boxes[start:start + count]
            W, H = max(b[0] for b in part), max(b[1] for b in part)
            self.assertEqual(lay, core.label_safe_layout(count, W, H, need_w, 1600))
            self.assertIsNotNone(lay)
        return chunks

    def test_an_oversized_request_is_split_not_dropped(self):
        chunks = self.check([(360, 800)] * 1000, 1000, 125)
        cap = (1600 // (125 + 8)) * (1600 // (core.MIN_TILE_PX + 48))
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(c[1] <= cap for c in chunks))
        self.assertTrue(chunks[0][2], "the first sheet was cut short by the layout")

    def test_no_false_reduction(self):
        chunks = self.check([(360, 800)] * 8, 4, 100)
        self.assertEqual([(c[1], c[2]) for c in chunks], [(4, False), (4, False)])

    def test_a_remainder_is_not_a_reduction(self):
        chunks = self.check([(360, 800)] * 9, 8, 100)
        self.assertEqual([(c[1], c[2]) for c in chunks], [(8, False), (1, False)])

    def test_tiny_originals_are_placed(self):
        (start, count, reduced, lay), = self.check([(10, 10)], 8, 125)
        self.assertEqual((count, reduced), (1, False))
        cols, cell_w, th, s = lay
        self.assertEqual((s, th, cell_w), (4.0, 40, 125))
        chunks = self.check([(1, 2000), (10, 10)], 8, 125)
        self.assertEqual(sum(c[1] for c in chunks), 2)

    def test_per_sheet_must_be_positive(self):
        with self.assertRaises(ValueError):
            core.chunk_sheets([(10, 10)], 0, 100, 1600)

    @staticmethod
    def reference(boxes, per_sheet, needs, max_edge=1600):
        """The plain algorithm: try min(N, remaining), drop one tile at a time,
        rescanning the prefix every time."""
        out, i = [], 0
        while i < len(boxes):
            want = k = min(per_sheet, len(boxes) - i)
            while True:
                part = boxes[i:i + k]
                lay = core.label_safe_layout(k, max(b[0] for b in part), max(b[1] for b in part),
                                             max(needs[i:i + k]), max_edge)
                if lay is not None:
                    break
                k -= 1
            out.append((i, k, k < want, lay))
            i += k
        return out

    def test_matches_the_plain_algorithm(self):
        import random
        rng = random.Random(1893)
        for trial in range(60):
            n = rng.randint(1, 120)
            boxes = [(rng.choice([1, 10, 40, 200, 360, 1080, 2400]),
                      rng.choice([1, 10, 100, 800, 2400, 4000])) for _ in range(n)]
            needs = [rng.choice([60, 90, 125, 300]) for _ in range(n)]
            per_sheet = rng.choice([1, 4, 8, 50, 1000])
            with self.subTest(trial=trial):
                self.assertEqual(core.chunk_sheets(boxes, per_sheet, needs, 1600),
                                 self.reference(boxes, per_sheet, needs))

    def test_capacity_bound_holds(self):
        for need_w in (1, 60, 125, 400):
            bound = core.sheet_capacity_bound(need_w, 1600)
            self.assertIsNone(core.label_safe_layout(bound + 1, 1, 1, need_w, 1600))

    def test_a_huge_request_is_fast(self):
        import time
        t0 = time.perf_counter()
        chunks = core.chunk_sheets([(360, 800)] * 10000, 10000, 125, 1600)
        elapsed = time.perf_counter() - t0
        self.assertEqual(sum(c[1] for c in chunks), 10000)
        self.assertLess(elapsed, 5.0, "rejected tile counts must not be rescanned")


class ExactTimes(unittest.TestCase):
    def test_pts_times_time_base_is_exact(self):
        tb = Fraction(1, 15360)
        self.assertEqual(core.pts_ms(256, tb), 17)        # 16.667 ms
        self.assertEqual(core.pts_ms(512, tb), 33)        # 33.333 ms
        self.assertEqual(core.pts_ms(108134, tb), 7040)   # 7.0399739... s
        # a time beyond 1000 s keeps its milliseconds (pts_time printed with 6
        # significant digits would lose them)
        self.assertEqual(core.pts_ms(1234567 * 15360 // 1000, tb), 1234567)

    def test_halves_round_up_and_negatives_raise(self):
        self.assertEqual(core.ms_round(Fraction(1, 2000)), 1)
        self.assertEqual(core.ms_round(Fraction(3, 2000)), 2)
        with self.assertRaises(ValueError):
            core.ms_round(Fraction(-1, 1000))

    def test_time_ms_matches_the_printed_name(self):
        for t in (0.0, 0.0165, 0.0175, 2.0005, 5.5, -0.017):
            with self.subTest(t=t):
                s = f"{t:.3f}"
                self.assertEqual(core.time_ms(t), round(float(s) * 1000))

    def test_seconds_exact(self):
        self.assertEqual(core.seconds_exact("0.033"), Fraction(33, 1000))
        self.assertEqual(core.seconds_exact(" 7 "), Fraction(7))
        # the exact value separates the 1/30 s frame from a request at 33 ms, which
        # rounded milliseconds would not
        self.assertLess(core.seconds_exact("0.033"), Fraction(1, 30))
        self.assertEqual(core.ms_round(Fraction(1, 30)), 33)
        for bad in ["-1", "1e3", "nan", "inf", "", ".5", "1.", "0x10", "1,5"]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                core.seconds_exact(bad)

    def test_decimal_between_restarts_strictly_after_the_last_frame(self):
        # flooring the next frame's time to ms (0.001) would land before the written
        # 0.00149 s frame, and the same continuation would repeat forever
        lo, hi = Fraction(149, 100000), Fraction(151, 100000)
        d = core.decimal_between(lo, hi)
        self.assertEqual(d, "0.0015")
        self.assertTrue(lo < core.seconds_exact(d) <= hi)
        self.assertEqual(core.decimal_between(Fraction(0), Fraction(1, 60)), "0.001")
        self.assertEqual(core.decimal_between(Fraction(1, 60), Fraction(2, 60)), "0.017")
        # the upper end is inclusive: the first omitted frame itself
        self.assertEqual(core.decimal_between(Fraction(1, 1000), Fraction(2, 1000)), "0.002")
        self.assertEqual(core.decimal_between(Fraction(7), Fraction(8)), "7.001")
        # no decimal with <= 9 places fits between two frames 1e-10 s apart
        self.assertIsNone(core.decimal_between(Fraction(1, 3), Fraction(1, 3) + Fraction(1, 10**10)))

    def test_range_arg_contains_both_frames(self):
        self.assertEqual(core.range_arg(0.016667, 0.983333), "0.016-0.984")
        a, b = (float(v) for v in core.range_arg(1.5, 2.0).split("-"))
        self.assertLessEqual(a, 1.5)
        self.assertGreater(b, 2.0)


class ShowinfoTimebase(unittest.TestCase):
    def test_reads_the_input_time_base(self):
        log = ("[Parsed_showinfo_1 @ 0x7fe5] config in time_base: 1/15360, frame_rate: 60/1\n"
               "[Parsed_showinfo_1 @ 0x7fe5] config out time_base: 0/0, frame_rate: 0/0\n"
               "[Parsed_showinfo_1 @ 0x7fe5] n:   0 pts:  74074 pts_time:1234.566667 "
               "duration:      1\n")
        self.assertEqual(core.parse_showinfo_timebase(log), Fraction(1, 15360))
        (f,) = core.parse_showinfo_frames(log)
        self.assertEqual((f.instance, f.pts, f.pts_time, f.size, f.duration),
                         (1, 74074, "1234.566667", None, 1))

    def test_frames_carry_instance_size_and_duration(self):
        # two showinfo filters in one chain (native size before a crop, output size
        # after it); a stream that changes size reports the new size natively
        log = ("[Parsed_showinfo_1 @ 0x7f1] n:   0 pts:      0 pts_time:0       duration:    512 "
               "duration_time:0.0333333 fmt:yuv420p cl:left sar:1/1 s:64x48 i:P iskey:1\n"
               "[Parsed_showinfo_3 @ 0x7f2] n:   0 pts:      0 pts_time:0       duration:    512 "
               "duration_time:0.0333333 fmt:rgb24 sar:1/1 s:32x24 i:P iskey:1\n"
               "[Parsed_showinfo_1 @ 0x7f3] n:   0 pts:    512 pts_time:0.0333333 duration:      0 "
               "duration_time:0 fmt:yuv420p sar:1/1 s:96x64 i:P iskey:1\n")
        got = [(f.instance, f.pts, f.size, f.duration) for f in core.parse_showinfo_frames(log)]
        self.assertEqual(got, [(1, 0, (64, 48), 512), (3, 0, (32, 24), 512),
                               (1, 512, (96, 64), None)])

    def test_missing_or_unset_is_none(self):
        self.assertIsNone(core.parse_showinfo_timebase(
            "[Parsed_showinfo_1 @ 0x1] n:   0 pts:      0 pts_time:0\n"))
        self.assertIsNone(core.parse_showinfo_timebase(
            "[Parsed_showinfo_1 @ 0x1] config in time_base: 0/0, frame_rate: 0/0\n"))
        # another filter's line is not showinfo's
        self.assertIsNone(core.parse_showinfo_timebase(
            "[Parsed_trim_0 @ 0x1] config in time_base: 1/60\n"))


class PngSize(unittest.TestCase):
    def test_ihdr(self):
        head = (b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR"
                + (201).to_bytes(4, "big") + (243).to_bytes(4, "big"))
        self.assertEqual(core.png_size(head), (201, 243))

    def test_not_a_png(self):
        self.assertIsNone(core.png_size(b"\xff\xd8\xff\xe0" + b"\0" * 20))
        self.assertIsNone(core.png_size(b"\x89PNG\r\n\x1a\n"))


class ImageBudget(unittest.TestCase):
    def test_phone_frame_is_downscaled_on_the_standard_tier_only(self):
        b = core.image_budget(1080, 2400)
        self.assertEqual(b["tokens"], 39 * 86)   # 3354
        self.assertEqual(b["exceeds"], ["standard"])

    def test_tiers(self):
        self.assertEqual(core.image_budget(360, 800)["exceeds"], [])
        self.assertEqual(core.image_budget(1092, 1092)["tokens"], 1521)   # Vision page table
        self.assertEqual(core.image_budget(2576, 1449)["exceeds"], ["standard"])
        self.assertEqual(core.image_budget(2577, 1000)["exceeds"],
                         ["standard", "high-resolution (Claude 4.7+)"])
        self.assertEqual(core.image_budget(3200, 1000)["exceeds"],
                         ["standard", "high-resolution (Claude 4.7+)", "many-image"])
        # token limit alone (long edge within both tiers)
        self.assertEqual(core.image_budget(1500, 1500)["exceeds"], ["standard"])



# --------------------------------------------------------------------------- #
# pick: the frame picker's rules (vp_pick.py) and their JS mirror (pick_logic.js)

GEOM_HALF = {"src_w": 240, "src_h": 400, "crop_x": 0, "crop_y": 0, "crop_w": 240, "crop_h": 400,
             "out_w": 120, "out_h": 200}
GEOM_CROP = {"src_w": 360, "src_h": 800, "crop_x": 37, "crop_y": 151, "crop_w": 201,
             "crop_h": 243, "out_w": 201, "out_h": 243}


def pick_frame(rel, ms, *, geom=None, why="no frames.tsv beside the image", w=120, h=200,
               ts="pts*time_base", group=""):
    ws, we = pick.window_bounds(ms) if ms is not None else (None, None)
    return {"rel": rel, "name": rel.rsplit("/", 1)[-1], "display_name": rel.rsplit("/", 1)[-1],
            "group": group, "order": 1, "ms": ms, "delta_ms": None, "label": "",
            "path": f"/out/src/{rel}", "url": f"src/{rel}", "sha256": "0" * 64, "w": w, "h": h,
            "geom": geom, "roi_disabled": None if geom else why, "time_source": ts,
            "window_start": ws, "window_end": we}


def pick_data(frames, *, source_line="# source: <VIDEO> (no run.json found for these frames)"):
    return {"version": pick.PICK_VERSION, "page": "/out/index.html", "out": "/out",
            "fingerprint": "1a2b3c4d5e6f7a8b", "text": pick.TEXT, "frames": frames,
            "source_line": source_line, "groups": [{"label": "", "frames": len(frames)}]}


def pick_scenarios():
    """(name, data, state) cases shared by the Python rule tests and the JS parity test."""
    frames = [pick_frame("t00000000.png", 0, geom=GEOM_HALF),
              pick_frame("t00000017.png", 17, geom=GEOM_HALF),
              pick_frame("t00000033.png", 33, geom=GEOM_HALF, ts="pts_time"),
              pick_frame("t00000050.png", 50),
              pick_frame("notime.png", None)]
    d = pick_data(frames)
    crop = pick_data([pick_frame("t00000100.png", 100, geom=GEOM_CROP, w=201, h=243)],
                     source_line="# source: frames run of /rec/clip.mp4")
    sel = ["t00000000.png", "t00000017.png", "t00000033.png"]
    return [
        ("empty", d, {}),
        ("view_only", d, {"selected": sel}),
        ("both_marks", d, {"selected": sel, "marks": {"start": "t00000000.png",
                                                      "end": "t00000017.png"}}),
        ("pts_time_end", d, {"selected": sel, "marks": {"start": "t00000017.png",
                                                        "end": "t00000033.png"}}),
        ("reversed_marks", d, {"selected": sel, "marks": {"start": "t00000033.png",
                                                          "end": "t00000000.png"}}),
        ("same_frame", d, {"selected": sel, "marks": {"start": "t00000017.png",
                                                      "end": "t00000017.png"}}),
        ("untimed_mark", d, {"selected": ["notime.png"], "marks": {"start": "t00000000.png",
                                                                   "end": "notime.png"}}),
        ("one_mark", d, {"selected": sel, "marks": {"start": "t00000000.png", "end": None}}),
        ("proto_mark", d, {"selected": sel, "marks": {"start": "__proto__",
                                                      "end": "t00000017.png"}}),
        ("rect_geom", d, {"selected": sel, "rect": {"rel": "t00000000.png", "x0": 10, "y0": 30,
                                                     "x1": 20, "y1": 50}}),
        ("rect_reversed_clamped", d, {"selected": sel, "rect": {"rel": "t00000017.png",
                                                                 "x0": 500, "y0": 7, "x1": 101,
                                                                 "y1": -9}}),
        ("rect_empty", d, {"selected": sel, "rect": {"rel": "t00000017.png", "x0": 5, "y0": 5,
                                                      "x1": 5, "y1": 9}}),
        ("rect_no_geom", d, {"selected": ["t00000050.png"],
                             "rect": {"rel": "t00000050.png", "x0": 1, "y0": 2, "x1": 31,
                                      "y1": 42}}),
        ("rect_crop", crop, {"selected": ["t00000100.png"],
                             "rect": {"rel": "t00000100.png", "x0": 3, "y0": 4, "x1": 201,
                                      "y1": 243}}),
        ("rect_text_ints", d, {"selected": sel, "rect": {"rel": "t00000000.png", "x0": " 4",
                                                          "y0": "+6", "x1": 9.9, "y1": True}}),
        ("notes", d, {"selected": sel + ["notime.png"],
                      "notes": {"t00000017.png": "  edge\tstarts\nhere  ",
                                "notime.png": "x" * 250, "t00000000.png": " \u0007 "}}),
        ("untimed_only", d, {"selected": ["notime.png"]}),
        ("bad_types", d, {"selected": "t00000000.png", "marks": [], "notes": "x", "rect": []}),
        ("non_string_selected", d, {"selected": [1, None, "t00000050.png"]}),
    ]


class PickRules(unittest.TestCase):
    def block(self, name):
        data, state = next((d, s) for n, d, s in pick_scenarios() if n == name)
        return pick.copy_block(data, state)

    def test_window_bounds_bracket_the_rounded_name_time(self):
        self.assertEqual(pick.window_bounds(483), ("0.4825", "0.4835"))
        self.assertEqual(pick.window_bounds(0), ("0", "0.0005"))
        self.assertEqual(pick.window_bounds(17), ("0.0165", "0.0175"))
        self.assertEqual(pick.window_bounds(1000), ("0.9995", "1.0005"))
        # every exact time a name's ms can stand for lies inside its own bounds
        for k in range(0, 600):
            t = Fraction(k, 60)                       # 60 fps CFR times
            ms = core.ms_round(t)
            a, b = (Fraction(x) for x in pick.window_bounds(ms))
            self.assertLessEqual(a, t * 1000 / 1000)
            self.assertGreaterEqual(b, t)

    def test_viewing_range_by_default_and_no_window(self):
        b = self.block("view_only")
        self.assertIn("# viewing range: 0.000-0.033 s (first to last selected frame; a viewing "
                      "range, not a measurement window)", b)
        self.assertNotIn("--window", b)
        self.assertNotIn("settled", b)
        self.assertNotIn("still", b)
        lines = b.splitlines()
        self.assertEqual(lines[2], "/out/src/t00000000.png\tt=0 ms\tfirst")
        self.assertEqual(lines[3], "/out/src/t00000017.png\tt=17 ms\t+17 ms")
        self.assertEqual(lines[-1], "# source: <VIDEO> (no run.json found for these frames)")

    def test_marked_endpoints_emit_an_unverified_window(self):
        b = self.block("both_marks")
        self.assertIn("# --window 0-0.0175  (user-marked endpoints (unverified): start "
                      "t00000000.png at 0 ms, end t00000017.png at 17 ms; check the anim run's "
                      "own endpoint diagnostics before trusting it)", b)
        self.assertIn("pts_time", self.block("pts_time_end"))

    def test_invalid_marks_say_why_there_is_no_window(self):
        for name, why in (("reversed_marks", pick.TEXT["why_order"]),
                          ("same_frame", pick.TEXT["why_same"]),
                          ("untimed_mark", pick.TEXT["why_untimed"]),
                          ("one_mark", pick.TEXT["why_one_mark"]),
                          ("proto_mark", pick.TEXT["why_one_mark"])):
            b = self.block(name)
            self.assertIn(f"# no --window: {why}", b, name)
            self.assertNotIn("# --window", b, name)

    def test_rectangles(self):
        self.assertIn("# --roi 20,60,20,40  (source-video pixels, mapped through the frames.tsv "
                      "geometry of t00000000.png, SHA-256 verified)", self.block("rect_geom"))
        # reversed corners are ordered and clamped to the 120x200 image
        self.assertIn("# --roi 202,0,38,14 ", self.block("rect_reversed_clamped"))
        self.assertNotIn("--roi", self.block("rect_empty"))
        b = self.block("rect_no_geom")
        self.assertIn("# rectangle 1,2,30,40 in t00000050.png's own pixels, not source-video "
                      "pixels (source --roi disabled: no frames.tsv beside the image)", b)
        self.assertNotIn("# --roi", b)
        self.assertIn("# --roi 40,155,198,239 ", self.block("rect_crop"))

    def test_notes_are_one_line(self):
        b = self.block("notes")
        self.assertIn("\tt=17 ms\t+17 ms\tnote: edge starts here\n", b)
        self.assertIn("note: " + "x" * 200 + "\n", b)
        self.assertNotIn("x" * 201, b)
        self.assertEqual(len(b.splitlines()), 2 + 4 + 1)
        self.assertIn("/out/src/t00000000.png\tt=0 ms\tfirst\n", b)   # an all-control note drops

    def test_empty_and_untimed(self):
        self.assertEqual(self.block("empty"), "# no frames selected in /out/index.html\n")
        self.assertIn("# viewing range: unknown (the selected names carry no time)",
                      self.block("untimed_only"))
        self.assertIn("/out/src/notime.png\tt=unknown", self.block("untimed_only"))

    def test_roi_always_passes_region_box(self):
        rng = random.Random(1893)
        for _ in range(3000):
            sw, sh = rng.randint(1, 900), rng.randint(1, 900)
            cw, ch = rng.randint(1, sw), rng.randint(1, sh)
            g = {"src_w": sw, "src_h": sh, "crop_x": rng.randint(0, sw - cw),
                 "crop_y": rng.randint(0, sh - ch), "crop_w": cw, "crop_h": ch,
                 "out_w": rng.randint(1, 1200), "out_h": rng.randint(1, 1200)}
            x0, y0 = rng.randint(0, g["out_w"] - 1), rng.randint(0, g["out_h"] - 1)
            r = (x0, y0, rng.randint(x0 + 1, g["out_w"]), rng.randint(y0 + 1, g["out_h"]))
            x, y, w, h = pick.roi_to_source(r, g)
            args = argparse.Namespace(roi=f"{x},{y},{w},{h}", crop_top=0, crop_bottom=0)
            self.assertEqual(video_prep.region_box(args, {"width": sw, "height": sh}),
                             (x, y, w, h))
            # it covers the rectangle's source pixels (rounded outward)
            self.assertLessEqual(x, g["crop_x"] + Fraction(r[0] * cw, g["out_w"]))
            self.assertGreaterEqual(x + w, min(sw, g["crop_x"] + Fraction(r[2] * cw, g["out_w"])))

    def test_sanitize_note(self):
        self.assertEqual(pick.sanitize_note(" a\tb\r\nc "), "a b  c")
        self.assertEqual(pick.sanitize_note(None), "")
        self.assertEqual(pick.sanitize_note("y" * 300), "y" * 200)

    def test_fingerprint_follows_the_bytes(self):
        def snap(rel, sha):
            return pick.Snap("", rel, rel, rel, Path("/x") / rel, Path("/y"), sha, None)
        a = [snap("a.png", "1" * 64), snap("b.png", "2" * 64)]
        self.assertEqual(pick.fingerprint(a), pick.fingerprint(list(reversed(a))))
        b = [snap("a.png", "1" * 64), snap("b.png", "3" * 64)]
        self.assertNotEqual(pick.fingerprint(a), pick.fingerprint(b))
        self.assertEqual(len(pick.fingerprint(a)), 16)

    def test_geometry_reasons(self):
        sha = "ab" * 32
        snap = pick.Snap("", "t00000000.png", "t00000000.png", "t00000000.png", Path("/s"),
                         Path("/o"), sha, (120, 200))
        row = {"file": "t00000000.png", "sha256": sha, **{k: str(v) for k, v in GEOM_HALF.items()}}
        self.assertEqual(pick.geometry(snap, {"t00000000.png": row}, None), (GEOM_HALF, None))
        cases = [
            (None, "no frames.tsv beside the image", "no frames.tsv"),
            ({}, None, "has no row for t00000000.png"),
            ({"t00000000.png": {**row, "crop_w": "x"}}, None, "is malformed"),
            ({"t00000000.png": {**row, "crop_x": "200"}}, None, "is malformed"),
            ({"t00000000.png": {**row, "sha256": "cd" * 32}}, None,
             "the image changed since extraction: its SHA-256 abababababab differs from "
             "frames.tsv cdcdcdcdcdcd"),
            ({"t00000000.png": {**row, "out_w": "121"}}, None, "differs from frames.tsv 121x200"),
        ]
        for rows, err, want in cases:
            geom, why = pick.geometry(snap, rows, err if rows is None else None)
            self.assertIsNone(geom, want)
            self.assertIn(want, why)
        jpg = pick.Snap("", "t00000000.png", "t00000000.png", "t00000000.png", Path("/s"),
                        Path("/o"), sha, None)
        self.assertEqual(pick.geometry(jpg, {"t00000000.png": row}, None), (None, "not a PNG"))

    def test_allocate_names_never_collides(self):
        names = ["renamed_0001.png", "RENAMED_0002.png", "a b\n.png", "-x.png",
                 "t00000100?.png", "A.png", "a.png", "ok name (1).png"]
        got = pick.allocate_names(names)
        self.assertEqual(set(got), set(names))
        dests = [d.casefold() for d in got.values()]
        self.assertEqual(len(dests), len(set(dests)))
        self.assertEqual(got["renamed_0001.png"], "renamed_0001.png")
        self.assertEqual(got["RENAMED_0002.png"], "RENAMED_0002.png")
        self.assertEqual(got["ok name (1).png"], "ok name (1).png")
        self.assertEqual(got["A.png"], "A.png")
        self.assertTrue(got["a.png"].startswith("renamed_"))   # case-folded clash with A.png
        for n in ("a b\n.png", "-x.png", "t00000100?.png"):
            self.assertRegex(got[n], r"^renamed_\d{4}\.png$")

    def test_script_json_is_inert_in_html(self):
        data = {"path": "/a</script>b/x.png", "amp": "&amp;<img src=x>", "ls": "a" + chr(0x2028)}
        payload = pick.script_json(data)
        self.assertFalse(any(c in payload for c in "<>&"))
        self.assertTrue(payload.isascii())
        self.assertEqual(json.loads(payload), data)


NODE = shutil.which("node")
NODE_RUNNER = r"""
const fs = require("fs"), vm = require("vm");
const ctx = {}; ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
const cases = JSON.parse(fs.readFileSync(0, "utf8"));
const out = cases.map(c => ({
  block: ctx.VPPick.copyBlock(c.data, c.state),
  key: ctx.VPPick.storageKey(c.data),
  rois: c.rois.map(r => ctx.VPPick.roiToSource(r[0], r[1])),
  notes: c.notes.map(n => ctx.VPPick.sanitizeNote(n)),
}));
process.stdout.write(JSON.stringify(out));
"""


@unittest.skipUnless(NODE, "node not installed")
class PickLogicJs(unittest.TestCase):
    """pick_logic.js must produce exactly what the Python reference does."""

    def test_js_matches_the_python_reference(self):
        rng = random.Random(5)
        rois = []
        for _ in range(400):
            g = dict(GEOM_CROP if rng.random() < 0.5 else GEOM_HALF)
            g["out_w"], g["out_h"] = rng.randint(1, 999), rng.randint(1, 999)
            x0, y0 = rng.randint(0, g["out_w"] - 1), rng.randint(0, g["out_h"] - 1)
            rois.append([[x0, y0, rng.randint(x0 + 1, g["out_w"]), rng.randint(y0 + 1, g["out_h"])],
                         g])
        notes = [" a\tb ", "x" * 230, "\u00e9\u0085z", " ", "a" + chr(0x2029) + "b", None, 7]
        cases = [{"name": n, "data": d, "state": s, "rois": rois, "notes": notes}
                 for n, d, s in pick_scenarios()]
        cp = subprocess.run([NODE, "-e", NODE_RUNNER, str(SR_DIR / "pick_logic.js")],
                            input=json.dumps(cases), capture_output=True, text=True)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        got = json.loads(cp.stdout)
        for c, g in zip(cases, got):
            self.assertEqual(g["block"], pick.copy_block(c["data"], c["state"]), c["name"])
            self.assertEqual(g["key"], pick.storage_key(c["data"]))
        self.assertEqual([tuple(r) for r in got[0]["rois"]],
                         [pick.roi_to_source(tuple(r), geom) for r, geom in rois])
        self.assertEqual(got[0]["notes"], [pick.sanitize_note(n) for n in notes])

    def test_ui_script_parses(self):
        cp = subprocess.run([NODE, "--check", str(SR_DIR / "pick_ui.js")],
                            capture_output=True, text=True)
        self.assertEqual(cp.returncode, 0, cp.stderr)


class PickOpener(unittest.TestCase):
    def opener(self, *, env, platform="linux", tools=("xdg-open", "open"), proc="Linux 6.1",
               rc=0, wslpath="C:\\x\\index.html"):
        calls = []

        def spawn(argv):
            calls.append(argv)
            return rc
        got = pick.open_page("/p/index.html", env=env, platform=platform,
                             which=lambda n: f"/usr/bin/{n}" if n in tools else None,
                             proc_version=proc, spawn=spawn, wslpath=lambda p: wslpath)
        return got, calls

    def test_linux_needs_a_display(self):
        (ok, why), calls = self.opener(env={})
        self.assertFalse(ok)
        self.assertIn("no display", why)
        self.assertEqual(calls, [])
        (ok, what), calls = self.opener(env={"DISPLAY": ":0"})
        self.assertTrue(ok)
        self.assertEqual(calls, [["xdg-open", "/p/index.html"]])
        (ok, _), calls = self.opener(env={"WAYLAND_DISPLAY": "wayland-1"})
        self.assertTrue(ok)

    def test_ssh_session_never_opens(self):
        for platform, proc in (("linux", "Linux"), ("darwin", None),
                               ("linux", "Linux 5.15 microsoft-standard-WSL2")):
            (ok, why), calls = self.opener(env={"SSH_CONNECTION": "1 2 3 4", "DISPLAY": ":0"},
                                           platform=platform, proc=proc,
                                           tools=("xdg-open", "open", "wslview"))
            self.assertFalse(ok, platform)
            self.assertIn("SSH", why)
            self.assertEqual(calls, [])

    def test_macos_and_wsl(self):
        (ok, _), calls = self.opener(env={}, platform="darwin")
        self.assertTrue(ok)
        self.assertEqual(calls, [["open", "/p/index.html"]])
        wsl = "Linux 5.15 Microsoft-standard-WSL2"
        (ok, _), calls = self.opener(env={}, proc=wsl, tools=("wslview",))
        self.assertEqual(calls, [["wslview", "/p/index.html"]])
        # explorer.exe exits 1 even when it opens the page: its status is ignored
        (ok, _), calls = self.opener(env={}, proc=wsl, tools=("explorer.exe", "wslpath"), rc=1)
        self.assertTrue(ok)
        self.assertEqual(calls, [["explorer.exe", "C:\\x\\index.html"]])

    def test_missing_or_failing_opener(self):
        (ok, why), calls = self.opener(env={"DISPLAY": ":0"}, tools=())
        self.assertFalse(ok)
        self.assertIn("not on PATH", why)
        (ok, why), _ = self.opener(env={"DISPLAY": ":0"}, rc=3)
        self.assertFalse(ok)
        self.assertIn("status 3", why)
        (ok, _), _ = self.opener(env={"DISPLAY": ":0"}, rc=None)   # still running: opened
        self.assertTrue(ok)
        (ok, why), _ = self.opener(env={}, platform="win32")
        self.assertFalse(ok)
        self.assertIn("win32", why)


if __name__ == "__main__":
    unittest.main()
