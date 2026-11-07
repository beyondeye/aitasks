---
Task: t1893_6_image_folder_input_mode.md
Parent Task: aitasks/t1893_screen_recording_skill_expansion.md
Sibling Tasks: aitasks/t1893/t1893_7_*.md … aitasks/t1893/t1893_14_*.md
Archived Sibling Plans: aiplans/archived/p1893/p1893_*_*.md
Base branch: main
Output branch: main
---

# t1893_6 — Image-folder input for `bug` and `anim`

## Context

The user wants manual preprocessing to work end to end (note 1c on t1888): extract
frames, curate or delete some, then run bug review or anim measurement on the
curated **folder of images** instead of the video. The building blocks already
exist: `frames` writes `t<ms>.png` (t1893_3), `sheet` reads any folder (t1893_4),
and `vp_core.parse_frame_name(..., allow_suffix=True)` reads times from names.
Today `bug`/`anim` accept only a file (`main()` rejects anything else) and every
decode goes through `["-i", video]`.

### Approach (measured during planning, ffmpeg n9.0.2 here, read-only spike)

Feed the folder to the **existing ffmpeg pipelines** through an ffconcat script, so
mpdecimate / freezedetect / blackdetect / trim / select behave exactly as for a
video, with no second analysis path:

- each image is one `file` entry with `option framerate 1000000` and a
  `duration` → the concat stream gets time base 1/1000000 and every frame's pts is
  the cumulative duration in µs, **exact** (spike: durations 7 ms / 16.7 ms / 33.3 ms
  came out as pts 7047000, 7063700, 7097000);
- **without** the `option` line the time base is the image demuxer's default 1/25 and
  times are quantised to 40 ms (spike: four frames landed on pts 0, 0, 1, 1). The
  option is therefore mandatory, and checked at run time (below);
- `-itsoffset <t0>` before `-i` puts the first image at its named time (spike:
  first pts 7040000 with `-itsoffset 7.04`), so `--range`, `--window`, names and
  summaries all use recording time, as in video mode;
- mixed sizes decode, but the ffmpeg CLI **reinitialises the filter graph** at each
  change of a decoded frame property. The `ffmpeg` manual for `-reinit_filter`
  names frame resolution and pixel format, and says filter state and buffered
  frames are lost. The spike printed a fresh `config in time_base` showinfo line
  per size change. For mpdecimate, freezedetect and blackdetect that is a silent
  state reset: in the review's probe, three identical black PNGs alternating
  RGB/gray/RGB kept 3 frames and reported no freeze, while all-RGB kept 1 and
  reported a freeze. Hence the single-configuration rule below.

The concat demuxer requires one codec across files, so the inputs are **staged**:
a temp dir holds `img_NNNNNN.<fmt>` symlinks (format sniffed from magic bytes) plus
`list.ffconcat`. When codecs are mixed, non-PNG images are converted to PNG in
the stage. The per-file `option` directive is refused under concat's default
`safe=1` ("Line 3: option not allowed if safe", reproduced). The input therefore
passes **`-safe 0`**, while the list keeps only generated, relative,
portable-charset names (`img_000001.png`), so no user path is ever parsed by the
demuxer. Nothing is written into the input folder or the repository. The stage
dir is removed when the run ends.

**Runtime guard (fail closed, covers ffmpeg version variance, minimum 5.1):** an
enumeration pass (`showinfo`, `-f null`) must return exactly N frames whose pts
equal the planned µs times in order. Any other result is a `PrepError`: too many
frames points to an animated image (named by mapping the frame's pts back to its
file span), and a pts mismatch reads "this ffmpeg's concat demuxer does not keep
the image times". The same pass gives each image's size and pixel format.

**Single-configuration rule (stateful detectors must see one uninterrupted
graph):**
- the enumeration pass counts showinfo's `config in time_base` lines: one per
  filter-graph configuration (`core.count_showinfo_configs`);
- more than one means some decoded property changed, whichever it was (size,
  pixel format, or any other reinit trigger), and the inputs are **normalised**;
- normalisation is one ffmpeg pass over the concat list (`-fps_mode
  passthrough`) writing uniform PNGs `norm/%06d.png` into the stage. Filters: the
  bug letterbox `pad` when sizes differ, then `format=<target>`, where the target
  is `rgba` if any frame's showinfo `fmt:` has alpha (`rgba`, `bgra`, `argb`,
  `abgr`, `ya*`, `yuva*`, `gbrap*`, `pal8`), else `rgb24`. The pass itself may
  reinit freely; its filters are stateless;
- a second concat list over `norm/` (same µs times) is enumerated again, and it
  **must** show exactly one configuration and N frames. Otherwise `PrepError`
  ("could not give the images one uniform format: …"), so no analysis runs on a
  reset graph;
- uniform folders, the common `frames` output, skip the pass and pay only for the
  enumeration;
- normalisation is recorded in run.json (`normalized: {pix_fmt, reason,
  formats_seen}`) and as a summary line. 16-bit or alpha precision beyond the
  target is noted as reduced.

## Behaviour (the contract)

1. **Input:** `bug DIR` / `anim DIR`. Only the top level of DIR; only
   png/jpg/jpeg/webp by extension (like `sheet`). Non-images (`frames.tsv`,
   `run.json`, …) are ignored. Errors (exit 1, `PrepError`):
   - no images, with the hint "pass DIR/frames" when DIR has a `frames/` subdir;
   - fewer than 2 images;
   - an image whose bytes are not png/jpeg/webp (named).
2. **Timing:**
   - **Filenames** (default): every name must carry a time per
     `parse_frame_name(name, allow_suffix=True)`, the same rule `sheet` uses, so
     edited names like `t00007040_annotated.png` keep their time. Order is by
     time. Errors:
     - some names untimed (list up to 10, suggest renaming or `--fps` for a
       fully untimed set);
     - none timed and no `--fps` ("names carry no times; give --fps N");
     - two images with the same time (name both).

     Resolution is 1 ms (names carry rounded ms, ±0.5 ms). frames.tsv `pts`
     cannot be converted (it has no time base, per t1893_3's note), so it is not
     used.
   - **`--fps N`** (new flag in `common()`, positive decimal, parsed exactly with
     `Fraction`): only for fully untimed sets. Order is natural (`natural_key`),
     `t_k = k/N` from 0. The summary says "timing assumed from --fps N, not
     measured". Errors: `--fps` with a video ("--fps applies only to a folder of
     images"), and `--fps` when any name carries a time (refused, so no evidence
     is discarded silently).
   - The last image's display time is unknown: it is assumed to be one base
     interval (below). Such a span end is always `proven=False`, with a note.
   - Concat durations are differences of the **rounded cumulative µs times**, so
     `--fps 30` over 3000 images does not drift.
3. **Gaps (anim; also recorded for bug):**
   - **base interval** = the lower quartile of positive Δt (≥4 deltas), else the
     minimum.
   - A gap is Δt > `core.GAP_FACTOR` (1.5) × base, with an estimated
     `missing ≈ round(Δt/base) − 1`.
   - Deviation from the task's literal "median": with every third frame deleted,
     Δt alternates 1 and 2 native frames, the median is 1.5 frames, and 2 < 1.5 ×
     1.5, so a median rule finds **no** gaps in the task's own test. The lower
     quartile is still the native interval as long as ≥25 % of the intervals are
     native. A sequence with every second frame deleted is indistinguishable
     from a half-rate recording; the docs state this.
   - The anim summary carries a heuristic warning naming where the gaps are (time,
     file before/after, Δt, ≈missing): "frames may be missing (deleted, or the
     recorder emitted none while the screen was still)". The timing is never
     called native-frame accurate when gaps exist.
   - **Uncertainty widening** per segment, image input only:
     - `frame_interval` passed to `analyze_frames` is the base interval (new kwarg
       `frame_interval=`, default None, so video behaviour is unchanged);
     - visible-duration uncertainty = max(base, Δt before the first moving frame,
       Δt into the settled frame). The motion started somewhere in (t[fm−1],
       t[fm]] and ended in (t[lm], t[lm+1]];
     - the summary shows `(±X)` from it. fit.json gains
       `visible_duration_uncertainty_ms`; video mode sets it equal to
       `frame_interval_ms`, so no video number changes;
     - warnings: "duration uncertainty widened to ±X ms by a gap at the
       start/end", and "N gap(s) inside this motion (at …): fewer points there, the
       fit is less constrained".
   - **Fitted-duration reliability guard** (image input). The widened ± covers
     the *visible* duration only; fitted durations come from `fit_motion`, which
     searches the onset only back to `t_first − ONSET_SEARCH_INTERVALS·dt`
     (8 intervals, `t0_lo`):
     - when the boundary interval `t[fm] − t[fm−1]` (last unchanged image →
       first changed image) is longer than that search, the true onset can lie
       outside it. The fitter then returns a too-short duration with a low RMSE
       (the review's probe: a known 400 ms motion fitted at about 333 ms);
     - such a segment is marked `fits_reliable: false`, with
       `fits_unreliable_reason` in fit.json;
     - in the summary, the overview's "best fit" cell reads `unreliable (gap
       before the motion)` instead of a name and duration, and the per-segment
       fit table is preceded by "warning: fitted durations are unreliable: the
       motion may have started up to X ms before the first changed image, beyond
       the fitter's onset search (8 frame intervals); use the visible duration
       ±X instead";
     - the fits stay in fit.json, for inspection only.

     The fitter is not changed. The guard is image-input only: in a video the
     recorder emits a frame as soon as the picture changes, so the onset is
     within one native frame of `t_first`. `ONSET_SEARCH_INTERVALS` becomes a
     `vp_core` constant, used by both `fit_motion` (replacing the literal 8 in
     `t0_lo`) and the guard, so they cannot drift.
4. **Sizes:**
   - **anim** needs one size. Otherwise `PrepError`: "anim needs images of one
     size: WxH (n images); differ: a.png 1080x2340, …" (up to 10, majority size
     first).
   - **bug** accepts mixed sizes by **letterboxing**:
     - the normalisation pass (Approach) adds a `pad`: every image, centred and
       unscaled, on a canvas of max W × max H in mid-grey (`0x808080`, so padding
       never reads as black);
     - bug then runs on a uniform, single-configuration stream;
     - no `frames.tsv` is written (`manifest: null`, `manifest_note`: "mixed image
       sizes letterboxed onto a WxH canvas: frame pixels map to no single source
       geometry");
     - the summary notes that the padding is part of what change and black
       detection see;
     - `--roi` / `--crop-*` with mixed sizes is refused (it would be in canvas
       pixels).

     Contact sheets are uniform because the frames are.
   - With one size, the geometry manifest works as for video: `src_w/src_h` = the
     image size, and `time_source` = `filename` or `fps`. This holds even when only
     the pixel format was normalised, since pixel positions are unchanged.
5. **Not applicable with images:**
   - audio: `has_audio False`, so silence is "not checked (no audio: image
     folder)", and `--extract-audio` is an error;
   - the `frames VIDEO --range` hint for thinned anim views becomes "the originals
     of this span are in DIR".
6. **run.json:**
   - every bug/anim run.json gains `input: "video"|"images"`;
   - image runs add `input_dir_abspath`, `images` (count), and
     `timing: {source: "filenames"|"fps", fps, resolution_ms: 1|null,
     base_interval_s, last_image_assumed_s}`, and `normalized: {pix_fmt, reason,
     formats_seen}|null`;
   - they also add `gaps: [{after, before, at_s, delta_s, est_missing}]`,
     `sizes` ({"WxH": n}) and `letterboxed: canvas|null`;
   - `video_abspath` and `video_size` are null for image runs.

   **Consumer fix:** `vp_pick.source_info` handles `input == "images"`. Its
   `# source:` line says the run read the image folder `<abs dir>` (no video), and
   never re-resolves a path.

## Implementation steps

### Pre-phase (risk mitigations)
1. [capture_video_baseline] **Before editing any code**, use the current tree to
   encode three synthetic videos with `screen_recording_synth` into the
   scratchpad: the slide-right tween, `bug_frames()` and `triage_frames()`. Then
   run, with fixed `--out` dirs under the scratchpad:
   - `anim slide.mp4`;
   - `anim slide.mp4 --window 0.4-1.0`;
   - `bug bug.mp4`;
   - `bug triage.mp4`.

   Copy each run's `summary.md`, `timeline.tsv`, `run.json`, every `*/fit.json`
   and `*/curve.tsv`, and `frames/frames.tsv` into
   `<scratchpad>/baseline/<run>/`. Record `sha256sum` of the four encoded videos,
   so the post-phase reuses the identical inputs and does not re-encode.

### 1. `vp_core.py` (pure, unit-testable)
- `plan_image_sequence(names, fps: Fraction | None) -> ImageSeqPlan`:
  - `ImageSeqPlan` holds items `(name, t: Fraction, form)`, `source`, `forms`, and
    the sorted order;
  - it raises `ValueError` with the messages above (untimed / none timed /
    duplicate / fps-with-timed / <2 images).
- `base_interval(times) -> float` and `sequence_gaps(times, base) -> list[Gap]`
  (dataclass `index, at, delta, est_missing`).
- `concat_starts_us(times) -> list[int]` (round to µs) and the durations derived
  from them.
- `ONSET_SEARCH_INTERVALS = 8`, replacing the literal in `fit_motion`'s
  `t0_lo` (same value, so the video baseline is unchanged), and
  `fit_onset_reachable(t_prev, t_first, dt) -> bool` (`t_first − t_prev ≤
  ONSET_SEARCH_INTERVALS·dt`).
- `count_showinfo_configs(log) -> int` (the number of `config in time_base` lines)
  and `ALPHA_PIX_FMTS` with a `has_alpha(fmt)` helper.
- `analyze_frames(..., frame_interval=None)`: when given, use it instead of
  `_frame_interval(...)` at both call sites (the `returns` and the main path).

### 2. `video_prep.py`
- `_ffin(src) -> list[str]`: `src.ffin` for an `ImageInput`, else `["-i", src]`.
  Replace `"-i", video` in `scan`, `decode_gray` and `extract_views`.
  `kept_frames` uses `scan`. `enumerate_frames`, `silence_log` and
  `audio_peak_db` stay video-only. bug/anim never call them for images.
- `sniff_image(path) -> "png"|"jpeg"|"webp"|None` (12 magic bytes).
- `class ImageInput` (context manager), built by `open_image_folder(dir, fps,
  mode, args)`:
  1. list the images and plan them (`core.plan_image_sequence`), mapping
     `ValueError` to `PrepError`;
  2. sniff the formats; stage symlinks (or PNG conversions when mixed) in
     `tempfile.mkdtemp(prefix="vp-images-")`;
  3. write `list.ffconcat`: header, then `file img_…`, `option framerate 1000000`
     and `duration <µs as %.6f>` for each image;
  4. set `ffin = ["-itsoffset", f"{t0:.6f}", "-f", "concat", "-safe", "0", "-i",
     list]` (`-safe 0` is required by the `option` lines; the names are generated);
  5. run the enumeration guard (counts, pts, sizes, `fmt:`, configuration count);
  6. apply the size policy (anim: error on mixed sizes). If the configuration
     count is above 1, or bug sizes differ, run the normalisation pass (pad for
     bug + `format=`), switch `ffin` to the `norm/` list, and re-enumerate,
     requiring exactly one configuration and N frames at the same pts;
  7. build the `info` dict with the probe's keys: `width`/`height` (canvas),
     `rotation` 0, `duration`, `start_time` 0, `avg_fps`/`r_fps` = 1/base,
     `nb_frames`, `codec`, `has_audio` False, `vindex` None, `video_streams` 1,
     `creation_time` None, plus `input: "images"`;
  8. expose `time_source`, `base`, `gaps`, `sizes`, `canvas`, `span_end`
     (last t + base) and `run_extra()` for run.json.

  `__exit__` removes the stage.
- `open_input(args, mode)`: for a dir, `ImageInput`. For a file, a null context
  yielding the path, with `info = probe(path)`. `--fps` with a file is an error.
- `_span(src, info, span, times)`: video goes through the unchanged
  `video_packets` + `core.video_span`. Images return a `core.Span`:
  - a `--range` end before the last image is proven by that later image;
  - otherwise `end_t = span_end` (capped by the range), `interval_end =` the last
    image's time, `proven=False`, and the note "image folder: the last image's
    display time is assumed (one frame interval)".
- `cmd_bug` / `cmd_anim`:
  - wrap the body in `with open_input(...) as src`, and pass `src` to the decode
    helpers;
  - use `make_out_dir(..., name=Path(dir).resolve().name)` for dirs (dotted
    folder names, as t1893_4 did);
  - `time_source` goes into the manifest rows;
  - image-specific summary lines: `input:` line via `video_line` (branch on
    `info["input"]`), timing source, gaps, letterbox note, no-audio text;
  - anim passes `frame_interval=src.base` and computes the uncertainty and gap
    warnings per segment.
- `_write_run_json`: branch on input (fields in Behaviour 6).
- `build_parser`/`main`:
  - help text: `video` = "recording, or (bug/anim) a folder of images";
  - add `--fps` in `common()`;
  - `main()` accepts a dir for bug/anim only (`info`/`frames` still require a
    file).
- Docstring usage lines updated.

### 3. `vp_pick.py`
- `source_info`: `input == "images"` → `video None`, and why = "the run read a
  folder of images (<input_dir_abspath>), not a video". `source_line` is
  unchanged.

### 4. Tests (`tests/test_screen_recording_core.py`, `tests/test_screen_recording_cli.py`)

Fixtures from `screen_recording_synth`. Each fixture asserts its own premise.

**Core:**
- plan: timed and suffixed names in time order; untimed, none-timed, duplicate and
  fps-with-timed errors; fps natural order (`img2` before `img10`) with exact
  `k/N`;
- `base_interval` on every-third deletion = the native interval; the median
  control shows the median rule would miss it;
- gaps with `est_missing`;
- `concat_starts_us` at 30 fps × 3000 has no drift;
- `analyze_frames(frame_interval=)` override.

**CLI** (new class `ImageFolderInput`, `skipUnless(HAVE_FFMPEG)`):
1. Round trip: slide-right tween clip → `frames --range 0.3-1.1 --max-frames
   200` → `anim <out>/frames`. Compare with `anim VIDEO`:
   - the fitted best named tween and duration match within the existing 12 ms;
   - visible duration within one frame;
   - run.json has `input: images`, `timing.source: filenames`, `gaps: []`;
   - the range starts at a non-zero time, which proves `-itsoffset`: the segment
     start equals the video run's within 1 ms.
2. Delete every third frame (copy first; assert the remaining count):
   - a summary gap warning naming a file;
   - run.json `gaps` non-empty, with `est_missing` 1;
   - `visible_duration_uncertainty_ms` > the gap-free run's;
   - the best family is still `tween`, with the same named curve within tolerance.
2b. Long boundary deletion:
   - fixture: a slide-left FastOutSlowIn 400 ms clip → `frames` folder. Delete
     the first 10 moving images (the frames from the first changed one onward,
     using the gap-free run's curve.tsv). Assert the premise: the new boundary
     interval is > 8 base intervals;
   - `anim DIR` gives fit.json `fits_reliable: false` with a reason, the summary
     overview cell `unreliable (gap before the motion)`, and the warning text;
   - controls: the gap-free run and the every-third run have `fits_reliable:
     true`, and their best-fit cells show the name and duration.
3. `--fps 60` on renamed untimed copies (`img1.png …`, natural order): the
   duration matches; "assumed" is in the summary; `timing.source: fps`.
4. Mixed sizes in anim → exit 1, and the message names the odd file.
5. bug on a mixed-size folder → exit 0, `letterboxed` set, no `frames.tsv`,
   `manifest_note`, picks present, sheets uniform (if magick).
6. bug on a uniform frames folder:
   - the timeline times equal the names' times;
   - `frames.tsv` has `time_source` `filename`;
   - silence "not checked";
   - `--extract-audio` errors.
7. Errors: empty dir (with the `frames/` hint), 1 image, a non-image `.png`,
   partially untimed, duplicate time, `--fps` with video, `--fps` with timed names,
   `--roi` on mixed-size bug, `info DIR` / `frames DIR` still refused.
8a. Pixel-format changes keep detector state:
   - fixture: four identical 32×32 black PNGs at 0/1/2/3 s alternating
     RGB (color type 2) / gray (type 0). The fixture asserts the color types it
     wrote. Run `bug DIR --freeze-min 1.5`;
   - expected: one picked state frame (mpdecimate kept one), one freeze interval
     from 0 s, and run.json `normalized.pix_fmt == "rgb24"`;
   - control: an all-RGB folder gives the same picks and freeze, with no
     normalisation;
   - an anim twin (a slide clip's frames re-saved alternating rgb24/gray via
     ffmpeg `-pix_fmt`) still fits within tolerance.
8b. `-safe 0` is required: a unit-level check that the generated list contains
   only portable-charset relative names, plus a run proving the `option` lines
   are accepted (any image-folder run).
8. Guard control: patch the list writer to omit `option framerate` (an in-process
   `video_prep.main` call with `mock.patch`) → `PrepError` "does not keep the image
   times". Assert the patch was hit.
9. pick on an image-input anim run: `# source:` names the image folder, and no
   video is guessed.

**Pre-fix controls** (mutants, each red then restored, module checksum before and
after):
- gap base = median → test 2 red;
- uncertainty without the boundary Δt → test 2 red;
- the guard disabled → test 8 red;
- the reliability guard always true → test 2b red;
- normalisation skipped (configuration count ignored) → test 8a red. The fixture
  premise is re-checked: without normalisation the bug run keeps more than one
  frame;
- the re-enumeration's single-configuration check removed, with normalisation
  forced to a no-op (`format` omitted) → the `PrepError` path test red;
- `-itsoffset` dropped → test 1 red.

### 5. Docs and skill text
- New walkthrough `website/content/docs/workflows/screen-recordings/image-sequences.md`,
  "Review or Measure a Curated Image Sequence":
  - when to use it;
  - the extract → curate → `bug DIR`/`anim DIR` flow;
  - how timing is derived (names at 1 ms, `--fps` assumed, last image assumed);
  - what the gap warning means: heuristic, the widened ±, every-second-frame
    deletion is undetectable, VFR stills look like gaps;
  - when fitted durations are marked unreliable (a gap before the motion
    longer than the onset search), and that the visible duration ± is then the
    number to use;
  - mixed sizes (bug letterbox / anim refuses);
  - mixed pixel formats are normalised to one format, so the detectors see one
    uninterrupted stream (the summary line says when this happened).

  List it in `screen-recordings/_index.md` Walkthroughs and in the "Screen
  Recordings" group of `workflows/_index.md` (relref links).
- `website/content/docs/skills/aitask-screen-recording.md`:
  - usage lines, the Modes row text, and `--fps` in the shared options table;
  - run.json fields;
  - Warnings and limits rows, using the exact strings from code;
  - a Workflows link.
- `.claude/skills/aitask-screen-recording/SKILL.md`: an "Image folder input"
  section with a run example. `references/animation.md`: a gap/uncertainty
  paragraph.
- Check every documented flag against the real `bug --help` / `anim --help`.

### 6. Verification
- `python3 tests/test_screen_recording_core.py`; `python3 tests/test_screen_recording_cli.py`.
- `bash tests/run_all_python_tests.sh --test-dir tests` (or the narrowed modules),
  reading the last line for the verdict.
- `cd website && python3 check_links.py --build && hugo build --gc --minify`.
- `./.aitask-scripts/aitask_skill_verify.sh`.
- `shellcheck` is not needed (no shell changes).

### Post-phase (risk mitigations)
1. [diff_video_baseline] Re-run the same four commands from the pre-phase on the
   **same** video files (sha256 checked) into new `--out` dirs, and diff each
   captured file against `baseline/`:
   - `summary.md`, `timeline.tsv`, `curve.tsv` and `frames.tsv` must be
     byte-identical, apart from the output-directory paths in summary lines;
   - in `fit.json`, the only allowed difference is the new key
     `visible_duration_uncertainty_ms`, and it must equal `frame_interval_ms`;
   - in `run.json` (JSON-compared), the only allowed difference is the new key
     `input: "video"`.

   Any other difference is a regression. Fix it before committing, and report the
   diff in the Final Implementation Notes.

### 7. Post-implementation
Step 9 of task-workflow: commit code and docs (`feature: … (t1893_6)`), plan via
`./.aitask-scripts/aitask_task_commit.sh`, and archive.

## Risk

### Code-health risk: low
- Changing `-i video` to `_ffin(src)` in `scan` / `decode_gray` / `extract_views`, and
  adding the `frame_interval=` and run.json `input` fields, touches the
  load-bearing video path of bug and anim. A slip changes video-mode numbers
  silently: summaries and fits stay plausible, and existing tolerance-based tests
  can stay green. · severity: low (residual — addressed by inline pre-phase
  capture_video_baseline and inline post-phase diff_video_baseline) · → mitigation: inline pre-phase
  capture_video_baseline, inline post-phase diff_video_baseline
- `video_prep.py` (1771 lines) grows by a whole input class. It stays in the
  existing module/pattern (pure planning in `vp_core`, I/O in `video_prep`), so
  structure debt is bounded. · severity: low · → mitigation: none

### Goal-achievement risk: medium
- The concat approach rests on `option framerate` and `-itsoffset` behaving as
  measured on ffmpeg n9.0.2. The documented minimum is 5.1, which was not run. The
  enumeration guard fails closed if timing differs, so a wrong timing is never
  reported, but on an older ffmpeg the feature could refuse to run. · severity:
  medium · → mitigation: validate_image_input_ffmpeg51
- The gap heuristic flags VFR still pauses as "frames may be missing", and cannot
  see deletion of every second frame. Both are labelled heuristic and documented;
  that is accepted, not mitigated. · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: capture_video_baseline | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: video-path regression from the _ffin plumbing | desc: capture bug/anim outputs on fixed synthetic videos with the pre-change code
- timing: post-phase | name: diff_video_baseline | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: video-path regression from the _ffin plumbing | desc: re-run on the same videos and diff; only the new input / visible_duration_uncertainty_ms keys may differ
- timing: after | name: validate_image_input_ffmpeg51 | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | addresses: concat option framerate / -itsoffset measured only on ffmpeg n9.0.2 | desc: run the ImageFolderInput tests under FFmpeg 5.1 and one 6.x/7.x static build via a PATH shim; confirm the behaviour or document the real minimum for image input

## Post-Review Changes

### Change Request 1 (2026-11-07)
- **Requested by user:** two review findings, both reproduced locally before fixing.
  1. Mixed-codec staging converted every non-PNG input with `-frames:v 1` *before* the enumeration guard counted frames, so an animated WebP among PNGs lost its later frames silently. A WebP-only folder was already refused. Reproduced: a 2-frame WebP plus a PNG ran with exit 0.
  2. `_image_segment_checks` formatted the recommended ± in the widening warning and in `fits_unreliable_reason` without `--time-scale`, while the summary table and `visible_duration_uncertainty_ms` divide by it (with `--time-scale 5`: table ±50, warning ±250).
- **Changes made:**
  1. `ImageInput._require_one_frame`: a showinfo pass over each original that is about to be converted. More than 1 frame → "<name> decodes to more than one frame (an animated image?)"; 0 frames → an error.
  2. `_image_segment_checks(..., time_scale)`: the recommended ± is in real time (÷ N), and the observed steps stay in recording time, marked "(recording time)" when N ≠ 1.
  - The skill page's time-basis table and widening-warning row state the units.
- **Files affected:** `.aitask-scripts/screen_recording/video_prep.py`, `tests/test_screen_recording_cli.py`, `website/content/docs/skills/aitask-screen-recording.md`
- **Verification:**
  - New tests:
    - `test_animated_image_beside_other_codecs_is_refused` (bug and anim; premise: ffprobe counts 2 frames; skips when the ffmpeg cannot write an animated webp);
    - `test_recommended_uncertainty_is_in_real_time_under_time_scale` (the long-gap folder at N=5: JSON ± = N=1's ÷ 5, with the same ± in the table, the reason and the warning; steps marked as recording time).
  - Mutants M9 (per-file count removed) and M10 (unscaled ±) both red, the source restored by checksum.
  - Core OK, CLI 104 OK. The video-path baseline diff was re-run: no differences. `check_links.py --build` PASSED.

### Change Request 2 (2026-11-07)
- **Requested by user:** two findings.
  1. (Plausible, from source) the animated-WebP test skipped only when encoding failed. FFmpeg 5.1 has `libwebp_anim` but its WebP decoder does not implement animation, so the 2-frame premise would fail before the application is tested.
  2. (Confirmed, follow-up) `_require_one_frame` decoded the whole animation (60 frames in the reviewer's probe) when 2 frames already decide.
- **Changes made:**
  1. The test skips, naming the count, when ffprobe does not count 2 frames. The two-frame assertion still holds on capable builds.
  2. `-frames:v 2` on the check's showinfo pass. A 2 s, 30 fps animated webp now decodes 3 frames, not 60 (the output limit lets one more through showinfo); the 0 / 1 / more decisions are unchanged.
- **Files affected:** `.aitask-scripts/screen_recording/video_prep.py`, `tests/test_screen_recording_cli.py`
- **Verification:** the animated-WebP and mixed-codec tests pass, and M9 is still red. `ImageFolderInput` passes in full.

## Final Implementation Notes
- **Actual work done:**
  - `bug DIR` / `anim DIR` (`video_prep.ImageInput`, `open_input`, `_ffin`, `_span_of`, `_out_name`). The folder is staged as symlinks `img_NNNNNN.<fmt>` in a private temp dir; non-PNG images are converted to PNG when codecs are mixed. A generated ffconcat list carries, per image, `option framerate 1000000` and its µs `duration`; the input is `-itsoffset <t0> -f concat -safe 0 -i list`.
  - An enumeration pass guards the input. It requires exactly N frames, a 1/1e6 time base and pts equal to the planned µs starts (otherwise "does not keep the image times"), and it names an animated image. It counts graph configurations; more than one triggers normalisation (a `pad` letterbox for bug's mixed sizes, plus `format=rgb24|rgba`) and a re-enumeration that must show one.
  - The `--fps N` flag (`_fps_arg`, exact `Fraction`). `main()` accepts a folder for bug/anim only.
  - anim, image input only:
    - the base interval is passed to `analyze_frames(frame_interval=)`;
    - `duration_uncertainty` = max(base, step before the first changed image, step into the settled image);
    - warnings for gaps at the ends and inside the motion;
    - the fitted-duration reliability guard (`core.fit_onset_reachable`, shared `ONSET_SEARCH_INTERVALS`) marks `fits_reliable: false` with a reason, and the summary cell reads `unreliable (gap before the motion)`.
  - bug, image input: letterbox notes, no manifest when letterboxed, the no-audio wording, and an assumed span end.
  - run.json: `input` (both input kinds), and for image runs `input_dir_abspath`, `images`, `timing`, `gaps`, `sizes`, `letterboxed`, `normalized`, with `video_abspath`/`video_size` null. fit.json: `visible_duration_uncertainty_ms`, `fits_reliable`, `fits_unreliable_reason`.
  - `vp_core`: `plan_image_sequence`, `base_interval`, `sequence_gaps`/`Gap`, `concat_starts_us`, `count_showinfo_configs`, `has_alpha`, `ShowinfoFrame.fmt`, `ONSET_SEARCH_INTERVALS` (replacing the literal 8 in `fit_motion`), and `fit_onset_reachable`.
  - `vp_pick.source_info`: an image run says "the run read a folder of images (<dir>), not a video".
  - Docs:
    - the skill page gains usage, a Modes note, an `--fps` row, a new "Image folder input" section, run.json/fit.json fields, time-basis rows, 22 warning rows, a limit, a requirement and the Workflows link;
    - new walkthrough `workflows/screen-recordings/image-sequences.md`, listed in both indexes;
    - SKILL.md gains an "Image folder input" section, a mode row, a run example and the Tests list;
    - `references/animation.md` gains the onset search, image-folder timing and a limits row.
- **Deviations from plan:**
  - **fit.json gains 3 keys, not 1:** `fits_reliable` and `fits_unreliable_reason` sit beside `visible_duration_uncertainty_ms`, for one schema across both input kinds. The post-phase diff allowed exactly these three, and checked uncertainty == `frame_interval_ms` and `fits_reliable: true` on video.
  - **`base_interval`** is the mean of the steps up to 1.5 × the lower quartile, not the bare quartile. Names rounded to whole ms (16/17 ms at 60 fps) made the quartile read 16.0 ms.
  - **The every-third CLI fixture deletes `k % 3 == 1`.** `k % 3 == 2` leaves 16 one-frame steps against 15 two-frame steps, so a median also found the gaps; that fixture matched the assumption under test (mutant M1 stayed green on it). The test now asserts that premise.
  - **The every-third test asserts the exact expected ±.** It is computed from the image times around the first changed and settled frames. A comparison against the gap-free run let mutant M2 pass.
  - Hidden files are ignored, as in `sheet`.
  - An extra test covers mixed codecs (png + jpeg staged as PNG), with its own mutant.
- **Issues encountered:** none beyond the plan-review findings (`-safe 0`, pixel-format reinit, fitted durations across a gap before the motion), all addressed before implementation.
- **Key decisions:**
  - one analysis path: images go through the same ffmpeg pipelines via concat, with no Python re-implementation of the detectors;
  - fail closed on any timing or configuration anomaly;
  - gap detection stays heuristic and image-input only; the video path is unchanged.
- **Verification:**
  - Pre-phase baseline + post-phase diff: 18 files from 4 video runs (anim, anim `--window`, bug, bug triage) on the same sha256-checked videos showed 0 differences beyond the allowed keys. A negative control (a perturbed `timeline.tsv` and `fit.json`) was flagged.
  - Mutants, all red, the source restored by checksum:
    - M1 median base;
    - M2 no boundary widening;
    - M3 time guard off;
    - M4 reliability guard always true;
    - M5 configuration count ignored (4 picks, no freeze: the review's probe reproduced);
    - M6 re-enumeration check removed;
    - M7 `-itsoffset` dropped;
    - M8 mixed-codec conversion off ("ffmpeg decoded 2 of the 3 images");
  - M9 / M10: see Post-Review Changes.
  - Tests: core 123 OK; CLI 104 OK (17 new in `ImageFolderInput`, after Change Request 1).
  - `aitask_skill_verify.sh` OK; `check_links.py --build` PASSED; `hugo build --gc --minify` OK.
  - `bug --help` / `anim --help` both list `--fps`. The walkthrough's sample lines were re-checked against current output.
- **Upstream defects identified:**
  - `tests/test_board_movement.py:1291 — IsolationNegativeControlTests.test_in_process_task_dir_override_reads_the_real_repo asserts no real task file ends in `_fixture.md`, but the live tree now holds t2226_stop_sync_fixture_copying_pycache_into_every_fixture.md (added in 92559489d by another session), so the control fails on every run regardless of the code under test (reproduced alone: 1 failed in 0.36s)`
- **Notes for sibling tasks:**
  - `ImageInput` is the reusable seam for any mode that should read a folder (`frames DIR` is not supported). Pass it wherever a video path went; `_ffin(src)` builds the input arguments.
  - t1893_12 (other agents): the image-folder warnings and the `unreliable (gap before the motion)` cell are what an agent must relay. The SKILL.md section says not to recommend those fits.
  - t1893_11 (work dir + clean): image runs default to `make_out_dir(..., name=<folder name>)`. The stage dir lives in the system temp and is removed on exit.
