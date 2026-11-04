---
Task: t1893_2_triage_rows_freeze_black_silence.md
Parent Task: aitasks/t1893_screen_recording_skill_expansion.md
Sibling Tasks: aitasks/t1893/t1893_3_*.md … aitasks/t1893/t1893_14_*.md
Archived Sibling Plans: aiplans/archived/p1893/p1893_*_*.md
Base branch: main
Output branch: main
---

# Plan: triage rows for freeze / black / silence in `bug` mode (t1893_2)

## Context

Bug recordings often show a hung app, a black flash or a silent gap. `bug` mode
picks frames by dwell only, so none of these is labelled. This task runs three
ffmpeg detectors in `bug` mode and adds one row per detected interval to
`timeline.tsv`, `summary.md` and `run.json`.

Black intervals are never lost:

- every interval gets a row;
- each gets one **detector-qualified** frame from inside the interval, ranked high
  inside `--max-frames`;
- any overflow is reported, never silent.

**User decisions (planning, 2026-11-04):**
- The `blackdetect` default reports every black run (`--black-min 0`, so a
  1-frame flash is included). Measured on ffmpeg 9.0.2: the task's `d=0.1` drops
  a 1-frame flash entirely.
- Ranking under `--max-frames`: **start/end > black > state > brief > motion**.

**Plan-review findings addressed (both reproduced locally on ffmpeg 9.0.2):**

1. *The black representative must come from inside the interval.* A 60 fps
   luma-39 clip with one luma-37 frame at 0.5 s logs `black_start:0.5`, but
   mpdecimate keeps only the luma-39 frame at t=0. A "nearest kept frame" mapping
   would therefore attach a non-black image and count the interval as represented.
   **Fix:** use the detector's own per-frame metadata, which gives the exact pts
   of the first black frame regardless of duplicate removal.
2. *Do not infer the end from proximity to EOF.*
   - A black run over frames 30–58 followed by a gray final frame logs the same
     `black_end:0.983333` as a black run over frames 30–59 to EOF.
   - Likewise, `silence_end: 8` is printed both for a real end and for an EOF
     closure.
   **Fix:** an end counts as **observed** only when the detector put the end key
   on a real frame or audio frame. Otherwise the end is reported as a lower bound,
   "still <kind> when the analysed span ended".

**Facts (re-verified 2026-11-04 on ffmpeg n9.0.2 with lavfi sources; the metadata
paths were checked in the FFmpeg `release/5.1` source):**

- **`blackdetect`**
  - It sets `lavfi.black_start` on the first black frame and `lavfi.black_end`
    on the first non-black frame, for **every** run whatever `d` is.
  - Its EOF path (`uninit`) logs `black_end = last_picref_pts` but sets **no**
    metadata. The source carries a `FIXME` saying the end should include the last
    frame's duration.
  - In a ranged VFR case, the log read `black_duration:0` for a run that `--range`
    had truncated.
- **`freezedetect`**
  - It logs `lavfi.freezedetect.freeze_start: 1` and sets the same key as
    metadata on the frame where the threshold is reached (value = the reference
    frame's time).
  - It sets `freeze_end` only on the frame that differs. A freeze running to EOF,
    or cut off by `--range`, has no end.
  - It detects VFR gaps: it measures from the reference frame's pts.
  - It survives x264 noise at `n=-60dB`.
- **`silencedetect`**
  - It sets `lavfi.silence_start` and `lavfi.silence_end` metadata on audio frames
    for real starts and ends.
  - Its EOF `uninit` logs `silence_end: <stream end>` with **no** metadata. This
    was checked both for a trailing silence and for one truncated by `atrim`.
- **Printing.** `metadata=mode=print` / `ametadata=mode=print` print only frames
  that carry metadata, as
  `frame:30   pts:30      pts_time:0.5` followed by `lavfi.black_start=0.5`.
  `trim` / `atrim` / `crop` keep source pts (`frame:30 pts:60`), so a printed pts
  feeds straight into `extract_views`' `eq(pts,P)` select.
- **Matching.** Values are `av_ts2timestr` strings, identical in the log line and
  in the metadata. Silence ends are therefore matched **byte-exact**, with no
  numeric tolerance.

**Second review round (both addressed):**

3. *The end of the analysed span must come from video evidence, not from the
   container duration.* `probe()`'s `duration` is the format duration, which is
   the longest stream. With 1 s of video and 3 s of audio, a trailing black run
   would otherwise read `end_s=3`. **Fix:** derive the video span end from the
   video stream's own packets (`last pts + duration`, demux-only `ffprobe`) and
   intersect it with `--range`. When the last packet has no duration, the end is
   flagged as not established. The same corrected end also feeds the last pick's
   "shown for". This is a deliberate small fix of v1: the last frame's dwell no
   longer absorbs a longer audio track's tail.
4. *An inserted black pick's duration comes from the detector.* mpdecimate never
   measured a frame it dropped, so "time until the next kept frame" (0.5 s in the
   dark-flash case) is not that image's duration. **Fix:** such a pick's
   `shown_for` is the black run's duration from blackdetect (17 ms there). It is
   left empty, with a `≥` lower bound in the summary, when the run's end was not
   observed. Picks that are kept frames keep their mpdecimate dwell, which is a
   measured quantity.

**Third review round (both addressed; reproduced locally):**

5. *Packet times have a different origin.* ffmpeg (without `-copyts`) subtracts
   the input's format `start_time` before filtering, but ffprobe packet times are
   raw. Measured on an mpegts clip with `start_time=1.433333`: the packets span
   1.4333–2.4333 s, while showinfo and `lavfi.black_start` start at 0. **Fix:**
   convert packet times to the detector's origin (`pts_time − format start_time`)
   before computing coverage or intersecting `--range`. A runtime cross-check
   fails closed. The same origin fix replaces v1's `start_time + duration`
   fallback with `duration`.
6. *ffprobe lists packets in demux order, not presentation order* (H.264
   B-frames). **Fix:** coverage comes from the packet with the **highest
   presentation pts**, never from the last row. If that packet has no duration,
   or any packet has no pts, coverage is not established.

## Design

- **Video span end** (pure `core.span_end(packets, origin, range_end)`):
  - `packets` is `[(pts_time | None, duration_time | None)]` for `v:0`, parsed
    from `ffprobe -select_streams v:0 -show_entries packet=pts_time,duration_time -of csv=p=0`
    (demux only, no decode). Only the first two CSV fields are read, because rows
    can carry a trailing empty field. `N/A` becomes `None`.
  - `origin` is the format `start_time` (`probe()["start_time"]`), the value ffmpeg
    subtracts. Every pts is normalised as `pts − origin` first.
  - Take `p_max`, the packet with the maximum normalised pts. If any pts is `None`,
    presentation order is unknown, so coverage is not established. Otherwise
    `coverage = p_max.pts + p_max.dur`, which is **proven**. When `p_max.dur` is
    missing or 0, `coverage = p_max.pts`, not established.
  - `end = min(coverage, range_end)`. It is proven when coverage is proven, or when
    `range_end <= p_max.pts`: a later frame exists, so the last analysed picture
    stayed up at least until `range_end`.
  - **Origin cross-check** (in `cmd_bug`, fail closed): the first kept frame's
    showinfo time must equal some normalised packet pts within 1 ms. With no
    `--range`, it must be the minimum one. Otherwise the end is not established,
    and the summary says `video timeline origin could not be confirmed`.
  - `cmd_bug` uses this `end_t` both for the dwells and for unobserved interval
    ends. When it is not established, the dwells fall back to the container value
    on the same origin (`duration`, intersected with `--range`), labelled
    `video end from container duration (not proven)` in the summary. Unobserved interval ends then read `≥ last frame at <t> s (video
    coverage after it not established)`.
- **One video decode pass:**
  `<trim>,<crop>,freezedetect=n=-60dB:d=F,blackdetect=d=0:pic_th=0.98:pix_th=0.10,metadata=mode=print,mpdecimate,showinfo`.
  - The detectors see every frame, and `metadata=print` records their keys before
    mpdecimate drops duplicates.
  - Same region as change detection (`--crop-*` / `--roi`). A ticking status-bar
    clock would otherwise break every freeze, and a visible status bar would keep a
    black screen under `pic_th=0.98`.
  - `blackdetect` runs with `d=0`, and `--black-min` is applied by us. The
    metadata marks every run anyway, and ffmpeg's own EOF duration is wrong for
    truncated runs.
- **Audio pass**, only when `probe()` reports audio:
  `-vn -af [atrim=…,]silencedetect=n=-60dB:d=2,ametadata=mode=print -f null -`.
  - Without audio there are no silence rows and no error; the summary says
    "not checked (no audio stream)".
- **Intervals from evidence** (pure code in `vp_core`):
  - **black**: `start` / `frame_pts` come from the `lavfi.black_start` frame.
    `end` is the `lavfi.black_end` frame's time when present (`end_observed=True`);
    otherwise it is the end of the analysed span (`end_observed=False`). A run is
    dropped only when its end is observed and it is shorter than `--black-min`; a
    run with an unobserved end is always kept, because nothing proves it short.
  - **freeze**: `start` = the `freeze_start` value; `end` = `freeze_end` when
    present (observed), else the end of the analysed span (unobserved). The
    threshold is freezedetect's `d` (`--freeze-min`).
  - **silence**: `start` = the `lavfi.silence_start` value.
    - When the `lavfi.silence_end` metadata value exists, it is the observed end.
    - Otherwise the end is unobserved. Its value is the EOF log value (the end of
      the audio stream, so a short audio track is never reported as silent beyond
      its end), else the end of the analysed span.
  - An unobserved end is always a **lower bound**:
    - TSV `why` gets `; end not observed: still <kind> when the analysed span ended (real end unknown)`;
    - the summary end cell reads `≥ <t> s (span ended)`;
    - `run.json` sets `"end_observed": false`.
- **Black frames in the budget.** Each black interval's `frame_pts` becomes a
  candidate:
  - if that pts is a kept frame, `black` is added to that kept frame's reasons;
  - otherwise it is a new pick, outside the kept list, carrying the pts as `ref`.
    Its `dwell` is the black run's duration and `dwell_basis` is `"black run"`.
    When the run's end was not observed, `dwell_basis` is
    `"black run, lower bound"`: the TSV `shown_for_s` is empty, the summary shows
    `≥ X s (black run, span ended)`, and the sheet label reads `black ≥X s`.
    Ranking ties use that value.
  - `_PRIORITY["black"] = 3.5`. All candidates are ranked together, so start/end >
    black > state > brief > motion.
- **After selection:**
  - each black interval's `file` = the pick whose pts equals its `frame_pts`, else
    empty with `no image: --max-frames N reached`;
  - `black_images_omitted` = that count;
  - `cap_hit` = `dropped > 0`.

## Implementation steps

1. **`.aitask-scripts/screen_recording/vp_core.py`** (pure). Add a new section,
   `# triage intervals`, containing:
   - `@dataclass Interval(kind, start, end, end_observed, frame_pts=None, frame_t=None)`.
   - `parse_metadata_print(log) -> list[tuple[int, float, dict[str, str]]]`:
     - reads only lines whose bracket tag contains `metadata_`;
     - a header regex `frame:\s*\d+\s+pts:\s*(-?\d+)\s+pts_time:\s*(NUM)` opens a
       block;
     - each following `(lavfi\.[\w.]+)=(.*)` line adds a key to that block;
     - values are kept as the raw strings.
   - `triage_intervals(video_log, audio_log, end_t, black_min) -> list[Interval]`:
     - builds the intervals by the rules above, sorted by `(start, kind)`;
     - matches silence EOF closures from the audio log's `silence_end: X` lines
       whose `X` string is not a metadata `lavfi.silence_end` value (byte-exact);
     - pairs starts with ends in order; an unmatched start becomes unobserved.
   - `parse_packets(csv_text) -> list[(pts | None, dur | None)]` and
     `span_end(packets, origin, range_end) -> (end, proven, max_pts)`, per the
     Design. Both work on normalised times.
   - `Pick` gains `ref: object = None` and `dwell_basis: str = "decimate"`, and
     `index` becomes `int | None`.
   - `select_key_frames(..., marks=())`:
     - each mark is `(t, reason, index_or_None, ref, dwell, dwell_basis)`;
     - a mark with an index adds its reason to that kept frame and keeps the kept
       frame's mpdecimate dwell;
     - a mark without an index adds a new pick with the mark's own `dwell` /
       `dwell_basis` (the black run). It never uses a gap computed from the kept
       frames;
     - add `"black": 3.5` to `_PRIORITY`;
     - the final ordering is by `t`; behaviour without marks is unchanged;
     - update the docstring's drop order.
2. **`.aitask-scripts/screen_recording/video_prep.py`**:
   - Add the constants `FREEZE_NOISE="-60dB"`, `BLACK_PIC_TH=0.98`,
     `BLACK_PIX_TH=0.10`, `SILENCE_NOISE="-60dB"`, `SILENCE_MIN=2.0`.
   - Add `scan(video, head, decimate, pre=()) -> (kept, log)`. `kept_frames()`
     becomes `scan(...)[0]`, so `anim` is unchanged.
   - Add `silence_log(video, span) -> str` and `video_packets(video)` (the ffprobe
     packet listing; its pure parsing lives in core).
   - `cmd_bug` computes `end_t` via `core.span_end` instead of
     `start_time + duration`. `run.json` records `video_end_s` and
     `video_end_proven`.
   - Frame-row writers (TSV `shown_for_s`, summary "shown for", sheet labels) take
     `dwell_basis` into account: a lower-bound basis is never printed as a plain
     duration.
   - `cmd_bug`:
     - validate `--freeze-min > 0` and `--black-min >= 0` as PrepError, before
       `make_out_dir`;
     - run the scan, plus the audio pass when there is audio;
     - call `core.triage_intervals(...)`;
     - build the marks from black intervals: `index` = the kept position whose
       pts == `frame_pts`, else `None` with `ref=frame_pts`;
     - call `select_key_frames(..., marks=marks)`;
     - for each pick, `pts = kept[p.index][0] if p.index is not None else p.ref`;
     - resolve each black interval's file or omitted note.
   - **`timeline.tsv`**: the columns become
     `idx, time_s, shown_for_s, why, file, kind, end_s`. The new columns are
     appended, so positional readers of the old five keep working.
     - Frame rows: `kind=frame`, `end_s` empty.
     - Interval rows:
       - `idx` and `shown_for_s` empty;
       - `time_s` = start, `end_s` = end;
       - `why` = the detector spec, plus the end-not-observed / no-image notes;
       - `file` = the black frame, or empty.
     - Rows are sorted by `(time_s, kind != "frame")`.
   - **`summary.md`**:
     - a top bullet: `- triage: N freeze, M black, K silence | silence not checked (no audio stream)`;
     - a new `## Freeze, black and silence` section after Timeline:
       - the detector settings, with one line on what each kind means (a freeze is
         a hang only if the user was acting; a dark screen can count as black);
       - a table `| kind | start | end | duration | frame |`, or `- none found`;
       - the `≥ … (span ended)` cells for unobserved ends;
     - when `black_images_omitted > 0`:
       `Warning: N black intervals have no image (--max-frames M reached). All are listed above and in timeline.tsv; narrow with --range around them to see their frames.`
   - **`run.json`** extra:
     - `"intervals": [{kind, start_s, end_s, end_observed, duration_s, frame_time_s, file}]`.
       When `end_observed` is false, `duration_s` is a lower bound;
     - `"detectors": {freeze, black, silence|null}` (spec strings);
     - `"black_images_omitted"` and `"cap_hit"`.
   - New parser flags:
     - `--freeze-min` (float, 2.0): "no visible change for this long (s) is a freeze row";
     - `--black-min` (float, 0.0): "shortest black run (s) to report; 0 = every black frame".
3. **`tests/screen_recording_synth.py`** (ground truth beside each scene):
   - `triage_frames()`, 7 s:
     - a 20 px bar that moves 1 px per frame, so nothing is still by accident;
     - frozen on its t=2.0 picture for [2.0, 4.5);
     - black for [5.0, 5.25);
     - a 1-frame black at 6.0;
     - `TRIAGE_TRUTH` records these intervals.
   - `dark_flash_frames()`, 1 s, flat dark gray:
     - full-range v=29 (≈Y 41, not black) everywhere;
     - one v=24 frame (≈Y 36.6, black) at 0.5 s;
     - this is the review's hazard: the difference is under mpdecimate's `lo`.
   - `tail_frames(recover: bool)`, 1 s: the moving bar, then black from 0.5 s,
     either to EOF or with a final non-black frame.
   - `black_flash_frames(n=6)`: 3-frame flashes at 0.5, 1.0, … s.
   - `encode()` gains `ts_offset=None` (`-output_ts_offset`) and
     `x264_params=None` (`-x264-params`). The defaults leave existing encodes
     unchanged.
   - `mux_tone(video, out, silent=(a, b))`: `aevalsrc` 440 Hz muted on [a, b),
     where b may equal the end; AAC, `-c:v copy -shortest`.
4. **`tests/test_screen_recording_core.py`**:
   - `ParseMetadataPrint` and `TriageIntervals`, using **verbatim ffmpeg 9 output**
     captured during planning (the C1, C2a/C2b, d=0.1, freeze and silence
     recovery/trailing/atrim logs), interleaved with showinfo/config noise. They
     assert, per case:
     - the exact `frame_pts`;
     - `end_observed` true for recovery on the final frame and false for EOF or
       `--range` truncation;
     - the silence EOF value used as the lower bound;
     - a `--black-min` drop only for short observed runs;
     - unobserved short runs kept.
   - `SpanEnd`, where each case pins the exact endpoint (a one-frame loss fails):
     - **reordered packets**, whose last row is not the maximum pts (the review's
       B-frame shape: the last row is 0.966667, the max is 0.983333, dur 0.016667)
       → proven 1.0, not 0.983;
     - a missing or 0 duration on the maximum-pts packet → not proven, with
       `max_pts` returned;
     - any `None` pts → not proven;
     - a nonzero origin (1.433333) → normalised;
     - `range_end` before `max_pts` → proven `range_end`;
     - `range_end` after coverage → coverage.
   - `ParsePackets`: verbatim ffprobe CSV, including a trailing empty field and
     `N/A`.
   - `SelectKeyFrames`:
     - marks without an index are inserted in time order with the defined dwell;
     - marks with an index merge their reason;
     - under the cap the order is start/end, then black, then state;
     - without marks the results equal the current ones.
5. **`tests/test_screen_recording_cli.py`**:
   - Make the `BugMode.timeline()` helper filter `kind == "frame"`. The existing
     assertions stay as they are, as the regression check that the extra filters
     do not change frame picks.
   - New class `TriageRows` (`skipUnless(HAVE_FFMPEG)`):
     - `test_freeze_and_black_within_a_frame`, run on CFR and `vfr=True` encodes:
       - each truth interval is matched within ±1 frame, with observed ends;
       - each black row has a file;
       - `run.json` intervals equal the TSV rows;
       - there are no silence rows, and the summary says `not checked (no audio stream)`.
     - `test_black_frame_comes_from_inside_the_interval` (finding 1):
       - **fixture guard**: a direct mpdecimate+showinfo run on the clip keeps no
         frame at 0.5 s, so the hazard is really present;
       - the black row's file name timestamp is 0.500 ± 1 frame;
       - the saved PNG decodes (via ffmpeg to gray) to a mean of at least 3 levels
         below the start frame's image, and below the black threshold;
       - **duration consistency** (finding 4): the black frame row's
         `shown_for_s`, the interval row's `end_s − time_s`, and `run.json`'s
         `duration_s` all equal ≈ 1 frame (16.7 ms ± 1 frame), never the 0.5 s
         gap to the next kept frame. The summary timeline cell says
         `(black run)`.
     - `test_video_end_ignores_longer_audio` (finding 3):
       - `tail_frames(recover=False)` (1 s of video) is muxed with 3 s of audio;
       - **fixture guard**: `run.json`'s probed `video.duration` ≈ 3, so the
         hazard is present;
       - the black row has `end_observed` false and `end_s` ≈ 1.0 (± 1 frame), not 3;
       - `duration_s` ≈ 0.5, with `video_end_proven` true;
       - the last frame row's `shown_for_s` is ≤ 0.5 + 1 frame;
       - the same clip with `--range 0-0.8` gives `end_s` ≈ 0.8 (proven by the
         later frame).
     - `test_nonzero_start_time_shares_the_detector_origin` (finding 5):
       - `tail_frames(recover=False)` is encoded with `-output_ts_offset 5`
         (`synth.encode(..., ts_offset=5)`);
       - **fixture guard**: the probed `start_time` ≈ 5;
       - the black interval's `start_s` ≈ 0.5 and `end_s` ≈ 1.0 (± 1 frame);
         `video_end_proven` is true and `end_observed` false;
       - `duration_s` ≈ 0.5, never ≈ 5.5;
       - the black frame file exists and is named `…_0.500s.png`;
       - `--range 0-0.8` gives `end_s` ≈ 0.8.
     - `test_bframe_reordering_keeps_the_last_frame` (finding 6):
       - encoded with `synth.encode(..., x264_params="b-adapt=0:bframes=3")`;
       - **fixture guard**: in the raw ffprobe packet listing, the last row's pts
         is below the maximum pts (the reordering is present);
       - `video_end_s` = 1.0 within 2 ms;
       - the trailing black run's `duration_s` = 0.5 within 2 ms. A one-frame loss
         (16.7 ms) fails.
     - `test_trailing_vs_final_frame_recovery` (finding 2), on CFR and VFR:
       - `tail_frames(recover=False)` gives `end_observed` false and `end_s` = the
         span end from `run.json`'s video duration;
       - `tail_frames(recover=True)` gives `end_observed` true and `end_s` = the
         final frame's time ± 1 frame.
     - `test_range_truncation_is_not_an_observed_end`:
       - with `--range` ending inside the black run, the end is unobserved and
         `end_s` = the range end;
       - with `--range` ending after the recovery frame, the end is observed.
     - `test_silence_gap_and_trailing_silence`:
       - a muted [2.0, 4.5) gap is observed within ±50 ms. An AAC frame is 1024
         samples ≈ 21 ms, plus encoder smear; this is stated in the docstring;
       - a muted tail to the end is unobserved.
     - `test_more_black_intervals_than_budget`, with `black_flash_frames(6)` and
       `--max-frames 4`:
       - all 6 black rows are present;
       - image files ≤ 4;
       - `cap_hit` is true;
       - `black_images_omitted` equals the count of empty-file black rows, and is
         exactly 4 (start + end + 2 black, which pins the ranking);
       - the summary warning has the count.
   - In `InfoAndErrors.test_bad_inputs_fail_cleanly`, add `--freeze-min 0` and
     `--black-min -1` (exit 1, nothing written).
6. **Docs (website).** Per t1893_1's note, use cases go in workflow subpages and
   flags/outputs go in the reference tables.
   - New `website/content/docs/workflows/screen-recordings/hang-black-silence.md`,
     "Spot a Hang, a Black Flash or a Silent Gap" (weight 15). It covers:
     - how to run it;
     - the row kinds and their detectors and thresholds;
     - why a freeze is not a bug by itself;
     - VFR still works;
     - cropping the status bar;
     - dark screens can read as black;
     - silence only with audio;
     - observed vs "≥ … (span ended)" ends;
     - why black is always represented (an in-interval frame, ranked high, every
       row kept);
     - what to do on `cap_hit` / omitted images (`--range`).
     All internal links use `{{< relref >}}`.
   - List the page in `screen-recordings/_index.md` Walkthroughs and in the
     "Screen Recordings" group of `website/content/docs/workflows/_index.md`.
   - `skills/aitask-screen-recording.md`:
     - Modes bug row;
     - `bug` only: `--freeze-min S` 2, `--black-min S` 0;
     - Output layout: the `timeline.tsv` columns and the new `run.json` keys;
     - Warnings: the black-omitted string, and the dropped-picks row's new drop
       order.
   - `bug-report.md`: one pointer sentence in "What the picks mean".
7. **Skill text.** `.claude/skills/aitask-screen-recording/SKILL.md` Bug mode:
   - a paragraph on the triage rows: what they mean; cite them like frames; a
     `≥` end is a lower bound; never call a freeze a hang without visible user
     action;
   - a symptom-table row for the black-omitted warning.
   Check that the `.agents/` / `.opencode/` wrappers are still thin pointers (no
   edit expected).
8. **Out of scope, but record it.** `cmd_anim`'s `end_t = start_time + duration`
   has the same origin mismatch: it clamps segment windows on the normalised
   timeline. Record it under "Upstream defects identified" in the Final
   Implementation Notes, so Step 8b can offer a follow-up. `anim` is not changed
   here.
9. **Step 9 (Post-Implementation):**
   - commit as
     `feature: Add freeze/black/silence triage rows to screen-recording bug mode (t1893_2)`;
   - commit the plan via `aitask_task_commit.sh`;
   - archive through the task-workflow Step 9 flow;
   - Step 8d creates the confirmed "after" mitigation.

## Verification

- `python3 tests/test_screen_recording_core.py` and
  `python3 tests/test_screen_recording_cli.py` pass on ffmpeg 9.0.2.
- Then run `bash tests/run_all_python_tests.sh --test-dir tests` and read only the
  last line, with `pipefail`.
- **Mutants.** Each is a scratch edit, reverted with Edit (never `git restore`),
  and each must turn its own test red:
  1. Map black intervals to the last kept frame instead of `frame_pts`:
     `test_black_frame_comes_from_inside_the_interval` fails on content and
     timestamp.
  2. Treat a logged end within 1.5 frames of EOF as unobserved: the recovery
     cases fail. Treat every logged end as observed: the trailing and range cases
     fail.
  3. Rank black below state: the pinned "exactly 4 omitted" fails.
  4. Revert `end_t` to `start_time + duration`:
     `test_video_end_ignores_longer_audio` fails.
  5. Give inserted picks the gap to the next kept frame as dwell: the
     dark-flash duration-consistency assertion fails.
  6. Drop the origin subtraction: the nonzero-start test fails.
  7. Use the last packet row instead of the maximum pts: the B-frame test and the
     reordered `SpanEnd` case fail.
- **Flag check:** every `--flag` in the new and edited pages and in SKILL.md
  appears in that mode's `--help`; `--freeze-min` and `--black-min` appear in
  `bug --help` only.
- **Writer check:** every claim about rows, columns, `run.json` keys and warning
  strings is checked against `cmd_bug` and one real run's output.
- `cd website && python3 check_links.py --build` and `hugo build --gc --minify`
  pass; `./.aitask-scripts/aitask_skill_verify.sh` passes.

## Risk

### Code-health risk: low
- `select_key_frames` and the bug-mode scan pass are shared by every bug run.
  - A ranking or filter-chain mistake could change existing picks.
  - Bounded: `marks` defaults to empty, the added filters pass frames through
    unchanged, and the existing `BugMode` assertions are kept as the regression
    check.
  - `Pick.index` becoming optional is handled at the single call site.
  · severity: low · → mitigation: none
- `timeline.tsv` gains two columns. They are appended, so positional readers of
  the existing five columns are unaffected · severity: low · → mitigation: none
- `bug`'s `end_t` moves from the container duration to video packet coverage.
  - This changes the last pick's "shown for" whenever the audio outlasts the video
    (intended), and adds one demux-only ffprobe pass.
  - When packet durations are missing, the v1 value is kept with a "not proven"
    label, so dwell classification never sees a zero-length last frame.
  - The existing `BugMode` timings, which have equal stream durations, guard
    against unintended drift.
  · severity: low · → mitigation: none

### Goal-achievement risk: medium
- The detector thresholds (`freezedetect -60dB`, `blackdetect pic_th 0.98 pix_th 0.10`,
  `silencedetect -60dB`) are validated only on synthetic x264/AAC fixtures.
  - On real device recordings, dark-mode screens can read as black, and noisy
    encoders or the always-on status bar could suppress freezes.
  - The docs and the summary label these rows as detector candidates and state
    their settings, but real-world accuracy is unverified.
  · severity: medium · → mitigation: t2203
- The metadata-based evidence depends on detector behaviour verified on ffmpeg
  9.0.2 runs and on the FFmpeg `release/5.1` source. Versions in between are
  assumed to match; the `release/5.1` source shows the same code paths
  · severity: low · → mitigation: none

### Planned mitigations
- timing: after | name: real_recording_triage_check | type: manual_verification | priority: medium | effort: low | inline_risk: low | added_complexity: medium | addresses: detector thresholds unvalidated on real device recordings (goal-achievement) | desc: Run bug mode on 2-3 real recordings (dark-mode app, a real hang, a black flash, audio with a gap) and check each freeze/black/silence row against the frames; record threshold adjustments as a follow-up if they misfire | created: t2203

## Post-Review Changes

### Change Request 1 (2026-11-04 17:20)
- **Requested by user:** four review findings:
  1. (medium, blocking) `video_packets` hard-coded `v:0`, while ffmpeg decoded its own default video track. A file whose default track is not the first got packet coverage from the wrong track (reproduced: `video_end_s=1` for a 3 s default track).
  2. (low, blocking) `--black-min nan` passed validation and silently dropped every observed black run.
  3. (low, blocking) the new `workflows/_index.md` link used a hand-written relative path instead of `relref`.
  4. (low, follow-up) the silence and peak-volume audio passes decode the audio twice.
- **Changes made:**
  - `probe()` resolves one video stream (the default-disposition track, else the first) and records `vindex` / `video_streams`. Every video ffmpeg call (`scan`, `kept_frames`, `decode_gray`, `extract_views`, in both bug and anim) maps `0:<vindex>`, and `video_packets` selects the same index. `video_line` names the stream when there are several.
  - `--freeze-min` / `--black-min` reject non-finite values with `math.isfinite`.
  - The link was converted to `relref`.
  - Finding 4 was left for a follow-up task, as its disposition asks.
  - Added regressions:
    - `TriageRows.test_one_video_stream_for_every_measurement`: a 1 s still first track plus a 3 s default second track with a trailing black run. A fixture guard checks the stream layout. The test asserts `vindex=1`, `video_end_s=3.0` proven, the black run 0.5–3.0 unobserved with its frame decoded from track 1, and the summary note;
    - `nan` / `inf` bad-input cases.
  - Mutants 8 (packets from `v:0`) and 9 (no `isfinite`) both turned the new tests red, and both were reverted.
- **Files affected:** `.aitask-scripts/screen_recording/video_prep.py`, `tests/test_screen_recording_cli.py`, `website/content/docs/workflows/_index.md`, `website/content/docs/skills/aitask-screen-recording.md`.

## Final Implementation Notes
- **Actual work done:**
  - `bug` mode runs `freezedetect` and `blackdetect` (`d=0`), each followed by `metadata=mode=print`, in the existing mpdecimate pass. When the video has audio it runs `silencedetect` + `ametadata=mode=print` in a separate audio pass.
  - Pure `vp_core` adds:
    - `parse_metadata_print`;
    - `triage_intervals`: an end is observed only from a frame/sample metadata key; otherwise the end is a lower bound at the analysed-span end, and for silence it is the audio EOF value;
    - `parse_packets` and `video_span`: video coverage from the maximum-presentation-pts packet, normalised by the format `start_time` and confirmed against the first kept frame, fail-closed;
    - `Mark`, plus `Pick.ref` / `Pick.dwell_basis`;
    - `"black": 3.5` in the ranking.
  - Each black interval's representative is the detector's own first black frame (exact pts). It is merged into a kept pick, or inserted with the black run as its duration.
  - Outputs:
    - `timeline.tsv` gains appended `kind` and `end_s` columns, plus interval rows;
    - `summary.md` gains a triage line and a "Freeze, black and silence" section with `≥ … (span ended)` cells and the black-omitted warning;
    - `run.json` gains `intervals`, `detectors`, `video_end_s` / `_proven` / `_note`, `cap_hit` and `black_images_omitted`.
  - New flags: `--freeze-min` (2) and `--black-min` (0); both reject non-finite values.
  - `probe()` resolves one video stream (default disposition, else the first), and every video ffmpeg/ffprobe call in bug and anim maps it.
  - Docs:
    - a new walkthrough `workflows/screen-recordings/hang-black-silence.md`, listed in both indexes;
    - the reference tables, the bug-report page and the SKILL.md bug section are updated.
- **Deviations from plan:**
  - freezedetect, and potentially silencedetect, put the start **and** end keys on one frame when the frame that proves duration `d` also ends the state. The pairing loop therefore opens before it closes. The existing `bug_frames` fixture exposed this: a 4.5–6.5 s freeze had read as open.
  - The `black_flash_frames` fixture was changed from a moving bar to a still screen. With motion only, black frames competed only with `motion` picks, so a black-below-state mutant stayed green end to end.
  - The trailing-silence fixture uses a 2.5 s muted tail: a tail of exactly `d` (2.0 s) is not reported.
  - The video-stream resolution (review round 4) also covers anim mode's decode calls, since they share the helpers.
- **Issues encountered:**
  - Three plan-review rounds, six findings, all reproduced locally and fixed in the design:
    - a predecessor frame used as the black image;
    - EOF-proximity end inference;
    - container vs video duration;
    - inserted-frame dwell;
    - the packet timestamp origin;
    - B-frame packet order.
  - One implementation review: the multi-track stream mismatch, NaN thresholds and a `relref` link were fixed; the audio double-decode was split off as a follow-up.
  - The full Python suite had one failure, `tests/test_sitrep_window.py::MatcherTests::test_booting_companion_without_a_marker_does_not_match` (t2175_4's module). It passes in isolation and this change does not touch it, so it is load-dependent.
- **Key decisions:**
  - The user chose `--black-min 0` and the ranking start/end > black > state > brief > motion.
  - `cap_hit` means `dropped > 0`; `black_images_omitted` is reported separately.
  - Truncated runs are always kept: nothing proves they are short.
  - Kept-frame picks keep their mpdecimate dwell. Only inserted black frames use the black-run duration, marked `(black run)`.
  - Verification used 9 mutants, each scratch-edited and reverted with Edit, each turning its own test red. Every new CLI fixture has a guard asserting that its hazard is present.
- **Upstream defects identified:**
  - `.aitask-scripts/screen_recording/video_prep.py:575` — `cmd_anim` sets `end_t = start_time + duration`. Its windows are on ffmpeg's normalised timeline (format `start_time` subtracted), and the container duration can be a longer audio track's. So anim segment windows clamp to the wrong end for a nonzero `start_time` or when the audio outlasts the video.
- **Notes for sibling tasks:**
  - ffmpeg detector evidence: use `metadata=mode=print` / `ametadata=mode=print` right after the detector. They give the exact pts of the frame carrying each key. EOF and `--range` closures appear only as log lines, never as metadata.
  - Timelines:
    - showinfo, metadata and `trim` all use ffmpeg's normalised time (format `start_time` subtracted), while ffprobe packet times are raw;
    - ffprobe lists packets in demux order; take the max pts;
    - map the stream explicitly (`probe()["vindex"]`, `_vmap()`) for any new decode path.
  - Fixtures that encode their own premise (`dark_flash_frames`, `tail_frames`, the B-frame and `ts_offset` encodes) should keep their guards. The `encode()` keyword arguments `ts_offset=` and `x264_params=` are available.
  - New outputs go in the reference tables and use cases in workflow subpages, per t1893_1. The `workflows/_index.md` entries should use `relref`.
