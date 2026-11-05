---
Task: t1893_3_frames_subcommand_exact_drilldown.md
Parent Task: aitasks/t1893_screen_recording_skill_expansion.md
Sibling Tasks: aitasks/t1893/t1893_4_*.md, aitasks/t1893/t1893_5_*.md, aitasks/t1893/t1893_6_*.md, aitasks/t1893/t1893_7_*.md … t1893_14
Archived Sibling Plans: aiplans/archived/p1893/p1893_*_*.md
Base branch: main
Output branch: main
---

# Plan: `frames` subcommand — exact drill-down with geometry provenance (t1893_3)

## Context

Today the screen-recording helper only writes the frames it picks itself, downscaled:
`bug` writes ≤ `--max-frames` picks at 1000 px and `anim` writes the motion ±2 frames,
thinned to `--max-view-frames`, at 800 px. The user wants to **extract frames, edit
them by hand (crop, annotate, delete) and feed them back to the agent**. This task
adds the foundation for that:

- a `frames` subcommand that writes every native frame of a range (or the frame on
  screen at given times) at full resolution, named by integer milliseconds taken
  from each frame's pts;
- a per-directory `frames.tsv` manifest that binds each image's geometry (source
  size, crop box, scale) to its SHA-256;
- `cap_hit` reporting in every mode;
- one shared filename-timestamp parser;
- an image-budget estimate with warnings.

t1893_4 (`sheet`), t1893_5 (`pick`, which trusts geometry only while the hash
matches) and t1893_6 (folder input) build on all of this.

Advisory note from t1893_1 (acknowledged): the docs are split. Reference tables
go on `website/content/docs/skills/aitask-screen-recording.md`; walkthroughs go in
`website/content/docs/workflows/screen-recordings/`, listed in that section's
`_index.md` and in the "Screen Recordings" group of `workflows/_index.md`.

## Facts re-checked (2026-11-04)

- **ffmpeg here is n9.0.2**, so `-fps_mode passthrough` works; `-vsync` is gone.
- **showinfo** prints `config in time_base: N/D` and per-frame `pts:<int> pts_time:<…>`
  (probed). ffmpeg 9 prints pts_time with 6 decimals. Older versions use `%.6g`
  (6 significant digits, per the existing `_close()` comment), which loses ms
  precision past 1000 s. **So `t<ms>` comes from `pts × time_base`**, computed
  exactly with `Fraction`. pts_time is a labelled fallback, used only if the
  time_base line is missing.
- **Claude vision limits** (platform.claude.com, Vision page):
  - standard tier: long edge 1568 px, 1568 visual tokens;
  - high-resolution tier (Claude 4.7 and later): 2576 px, 4784 tokens;
  - cost = ⌈w/28⌉·⌈h/28⌉.
  - Example: a 1080×2400 frame is 39·86 = 3354 tokens, so the standard tier
    downscales it.
  - **Changed since the task was written:** a request with more than 20 images
    now applies a stricter limit that "states the current limit in pixels", and
    the page says neither dimension above **3000 px** is safe on all platforms.
    The task's "≤ 2000 px" is stale; use 3000.

- **ffmpeg `crop` without `exact=1` does not honour odd boxes on yuv420p**
  (probed, ffmpeg 9.0.2, 8×8 test frame): `crop=4:4:1:1` takes pixels from (0,0),
  and `crop=5:5:1:1` comes out 4×4. With `exact=1` both are honoured. Today's
  `crop_filter` omits `exact=1`, so an odd `--roi`/`--crop-top` silently analyses
  and writes a shifted or shrunk region. PNG dimensions cannot detect an offset
  shift, and the hash would bind the wrong box.

## Design decisions

- **Exact crop is a precondition of recording a box.**
  - `crop_filter` emits `crop=…:exact=1` for `--roi` and the crop flags, in every
    mode, so the region analysed, written and recorded is the one requested.
  - `extract_views` inserts `format=rgb24` before the crop, so the written PNG is
    whole-pixel exact in every channel, chroma included. The output is RGB PNG
    anyway.
  - The odd-geometry fixture (Tests) proves the offset and size in both axes
    through image content, not dimensions alone.
- **Times compare at native precision; integer ms is for names and display only.**
  - Each frame's time is `pts × time_base` as a `Fraction`.
  - `--at` values and `--range` bounds are parsed from their decimal text into
    `Fraction`s.
  - All selection uses exact comparisons: `--at` picks the latest frame with
    `t ≤ T`; `--range` picks frames with `A ≤ t < B`.
  - Enumeration's `trim` is widened by 1 ms on each side only to bound the
    decode; the exact filter decides.
  - Consequence (documented as a limit, with no shortcut offered): a name's ms
    and every displayed time are rounded. They are labels, not exact selectors.
    Passing a rounded time back as `--at` can select a neighbouring frame
    (`t00000033` for 33.33 ms selects the 16.67 ms frame). No fixed offset is
    safe: "+1 ms" picks the next frame at ≥ 1000 fps, and can cross the video
    end on the last frame. The task does not require round-trip extraction from
    rounded names, so no mechanism is added. The summary and run.json show each
    request's resolved time, also rounded and labelled as such.

- **Layout.** Every directory of frames carries a `frames.tsv` describing its own
  images (`file` is the basename):
  - `frames` writes `<out>/frames/t00007040.png …` and `<out>/frames/frames.tsv`,
    plus `summary.md` and `run.json`;
  - `bug` writes `<out>/frames/frames.tsv`;
  - `anim` writes `<out>/sNN/frames/frames.tsv`.

  So `sheet DIR` / `pick DIR` always find the manifest beside the images.
- **`--range A-B`** writes every frame presented at A ≤ t < B (trim semantics, the
  same as `bug --range`), up to `--max-frames` (**default 60**, 1 s at 60 fps).
  Truncation keeps the **first N contiguous frames** and never thins, because
  "every native frame" must stay true for what is written. The summary names the
  omitted count and time span, and gives the exact `--range` that continues from
  the first omitted frame.
- **`--at T[,T…]`** writes the frame on screen at T: the latest frame whose exact
  presentation time is ≤ T.
  - Duplicates collapse into one file; the summary lists every T.
  - T before the first frame, or past the proven video end, is an error.
  - If the end is not proven (`core.video_span`), a T after the last frame is
    resolved but labelled `on_screen_proven: false`.
  - With more distinct frames than `--max-frames`, keep the earliest N and set
    `cap_hit`.
- **A range with no frames** (VFR still) is an error. The message points to
  `--at A` for the picture on screen at A.
- **Crop flags** (`--roi`, `--crop-top/--crop-bottom`) crop the *written image* in
  `frames`. In `bug` they only affect change detection. The docs state this
  difference. Output scale is always 1.
- **Names.**
  - `frames` names are `t{ms:08d}.png`.
  - Negative times, or two frames rounding to the same ms (above about 1000 fps),
    are a `PrepError`. Nothing is guessed.
  - bug/anim names are unchanged (`NN_5.500s.png`, `fNNN_5.500s.png`) but now
    come from shared formatters in `vp_core`. Their manifest `t_ms` equals the
    ms the parser reads from the name.
- **Manifest columns:**
  `file  t_ms  pts  time_source  src_w  src_h  crop_x  crop_y  crop_w  crop_h  out_w  out_h  scale_x  scale_y  sha256`
  - `src_*` are the display dimensions after rotation, the space `--roi` takes.
  - `out_*` are read from the written PNG's IHDR, never assumed.
  - `scale_* = out/crop`.
  - `sha256` is computed after the file reaches its final name.
  - Mapping: `src = crop_off + img_px · crop/out`.
- **`cap_hit`** in `run.json`:
  - `frames`: `--max-frames` truncated the request.
  - `bug`: unchanged (`dropped > 0`).
  - `anim`: new. `--max-segments` skipped segments, or `--max-view-frames`
    thinned any segment. Details go under `caps`, and the summary says what was
    omitted and how to narrow. For a thinned segment the hint is
    `frames VIDEO --range A-B` for every native frame.
- **Image budget** (`frames` only; bug and anim frames are ≤ 1000 px, under every
  limit):
  - a per-frame token estimate and the total, in `summary.md` and on stdout
    before the `SUMMARY:` line, and under `image_budget` in `run.json`;
  - a warning for each limit crossed: standard tier, high-resolution tier, and
    the many-image 3000 px limit.
  - `TOKEN_TILE` moves to `vp_core`, still one constant, and `video_prep` uses
    `core.TOKEN_TILE`.

## Implementation steps

### 1. `vp_core.py`: pure helpers (unit-testable)
- Move `TOKEN_TILE = 28` here. Add `READER_TIERS = (("standard", 1568, 1568),
  ("high-resolution (Claude 4.7+)", 2576, 4784))` and `MANY_IMAGE_SAFE_PX = 3000`,
  with a source and date comment.
- `image_tokens(w, h) -> int`, and `image_budget(w, h) -> dict` (`tokens`, a
  `long_edge`, and an `exceeds` list of tier names, plus `"many-image"` when
  `max(w, h) > MANY_IMAGE_SAFE_PX`).
- `parse_showinfo_timebase(log) -> Fraction | None`, from the first
  `config in time_base: a/b` line on a showinfo tag (`0/0` → None).
- `seconds_exact(text) -> Fraction`, from a decimal string via `Fraction(text)`.
  Finite and non-negative; anything else raises ValueError.
- `pts_ms(pts, tb: Fraction) -> int`: exact, half-up; ValueError if negative.
  Used **only** for names and the `t_ms` column.
  `time_ms(t: float) -> int`: the ms that `f"{t:.3f}"` prints, via the string, so
  it matches the existing names byte for byte.
- Name formatters: `frames_name(ms)` → `t{ms:08d}.png`;
  `bug_frame_name(k, t)` → `f"{k:02d}_{t:.3f}s.png"`;
  `anim_frame_name(i, t)` → `f"f{i:03d}_{t:.3f}s.png"`.
- `FrameName(ms, form, index)` dataclass, and `parse_frame_name(name) -> FrameName | None`:
  - full-match regexes on the stem, with an image extension `.png/.jpg/.jpeg/.webp`
    (case-insensitive);
  - `t(\d{8,})` → form `frames`;
  - `(\d{2,})_(\d+)\.(\d{3})s` → `bug`;
  - `f(\d{3,})_(\d+)\.(\d{3})s` → `anim`;
  - ms is built from the digit groups as integers (no float);
  - anything else, e.g. `t7040.png`, `01_5.5s.png`, `sheet_01.png`, a `.txt`, a
    leading space, `x01_…`, → None.
- `png_size(head: bytes) -> tuple[int, int] | None`: checks the PNG signature and
  IHDR, and returns the big-endian width and height.
- `range_arg(t_lo, t_hi) -> str`: an `A-B` with A floored and B ceiled to ms past
  t_hi, so `--range` includes both frames.

### 2. `video_prep.py`: shared plumbing
- `region_box(args, info) -> (x, y, w, h)` holds `crop_filter`'s validation.
  `crop_filter` builds its filter from it as
  `crop={w}:{h}:{x}:{y}:exact=1`, for `--roi` and the crop flags alike. Its
  signature, return shape and messages are unchanged.
- `extract_views(...)` gains:
  - keyword-only `head: str | None = None`, prepended before `select` to bound
    the decode;
  - `vw=vh=None`, meaning no scale filter;
  - `format=rgb24` inserted before `crop` whenever a crop is given.

  Existing callers are otherwise unchanged.
- `enumerate_frames(video, head, stream) -> list[Frame(pts, t: Fraction, ms, time_source)]`:
  decodes `head,showinfo` with `-fps_mode passthrough` to `-f null`.
  - With a parsed time_base: `t = pts × tb` and `ms = pts_ms`.
  - Without one: `t = Fraction(pts_time text)` and `ms = time_ms`, labelled
    `time_source = pts_time`.
- `write_frame_manifest(frames_dir, rows, info, box)`: per row, reads the PNG
  header (`core.png_size`, fails closed on a mismatch or a non-PNG) and streams
  a SHA-256. Writes `frames.tsv` and returns the per-file records, which
  run.json embeds as `manifest` (a path).
- `token_estimate` uses `core.image_tokens`.

### 3. `cmd_frames` + parser
- In the parser, `frames` takes: `video`, `--out`, `--crop-top`, `--crop-bottom`,
  `--roi`, a required mutually exclusive group (`--range` | `--at`), and
  `--max-frames` (int, default 60). No `--decimate`.
- Validate before anything is written:
  - `--max-frames ≥ 1`;
  - `--at` parses as finite, ≥ 0, comma-separated (`--at takes T[,T...] in seconds`);
  - `--range` via `parse_span`;
  - probe, `crop_filter`, enumeration, and the end and first-frame checks.
- Then `make_out_dir(args.out, video, "frames")`, then `frames/`. Extract via
  `extract_views(wanted, crop, None, None, head=<trim>)` and write the manifest.
- `summary.md` sections:
  - header lines: video, request semantics, region and "full resolution, scale 1",
    count and time source;
  - a cap warning, with the omitted count, span and continuation `--range`;
  - `## Image budget`: tokens per frame and in total, and the warnings;
  - `## Frames`: a table of file / time / requested-at (for `--at`), with the
    unproven-on-screen label;
  - `## Geometry (frames/frames.tsv)`: the column meanings, the mapping, and
    "valid only while the image still hashes to `sha256`; an edited frame has no
    trusted geometry".
- `run.json`: `frames`, `cap_hit`, `omitted`, `omitted_from_s`, `requested`
  (with each T's resolution), `time_source`, `image_budget`, `manifest`.
- Print a stdout budget line, then `SUMMARY:`.
- Update the module docstring and the usage comment in
  `.aitask-scripts/aitask_screen_recording.sh` (`info|bug|anim|frames`).

### 4. bug and anim: manifests and `cap_hit`
- **bug:** names via `core.bug_frame_name`. After `extract_views`, write
  `frames/frames.tsv`: box = the full frame (bug frames are always full screen),
  scale = vw/W and vh/H. Add `"manifest": "frames/frames.tsv"` to run.json.
  `cap_hit` is unchanged.
- **anim:**
  - names via `core.anim_frame_name`;
  - per segment, write `sNN/frames/frames.tsv` with box = `region_box`;
  - record `view_frames_saved`, `view_frames_total` and the thinned frames' time
    span;
  - summary: when a segment is thinned, add
    `- saved frames: N of M (thinned by --max-view-frames K); every native frame: frames VIDEO --range A-B`;
  - extend the `--max-segments` note with the first skipped segment's start time
    and "narrow with --range or raise --max-segments";
  - run.json gains `cap_hit`, `caps.max_segments {limit, skipped, first_skipped_s}`,
    `caps.max_view_frames {limit, thinned: [{segment, saved, of, range}]}`, and a
    per-segment `manifest`.

### 5. Tests
- **`tests/screen_recording_synth.py`:**
  - `numbered_frames(codes, *, fps)` draws 8 horizontal 360×80 bands (bit set →
    40, else 220), so each frame's code can be decoded from pixels;
  - `decode_code(gray, w, h)` uses the band centres;
  - `NUMBERED_HOLDS`: irregular hold lengths for a VFR fixture, with each code's
    true start time.
- **`tests/test_screen_recording_core.py`:**
  - `FrameNames`: the three forms parse to exact ms; formatter ↔ parser round trip;
    the existing literal strings (`04_5.500s.png`, `f013_0.483s.png`) are
    reproduced; garbage is rejected (the list in step 1).
  - `PtsMs`: Fraction exactness; half-up; negative raises; `time_ms` matches
    `.3f`.
  - `ShowinfoTimebase`: parses the probed log line; `0/0` and missing → None.
  - `PngSize`: a real IHDR header; a non-PNG gives None.
  - `ImageBudget`: 1080×2400 → 3354 tokens, exceeds standard only; 2576×1449 →
    within high-res; 3200×1000 → many-image; 360×800 → none.
- **`tests/test_screen_recording_cli.py`, new class `FramesMode`** (skipped
  without ffmpeg):
  - **Pixels and pts:** CFR numbered clip, `--range 0.5-1.0` → 30 files
    `t00000500 … t00000983`. Each PNG's decoded code equals the code expected
    for its ms; MAD vs the generator frame < 3 and > 10 vs either neighbour code;
    `cap_hit` false.
  - **VFR:** a premise guard that index × (1/avg_fps) ≠ the true start for ≥ 1
    frame by more than one frame. Filename ms and manifest `t_ms` equal each
    decoded code's true start ms.
  - **`--at`:** on VFR, T inside a hold resolves to the hold's first frame. A
    duplicate T collapses to one file. T past the end → exit 1, and no out dir.
  - **Exact-time boundaries** (60 fps CFR numbered clip; checked through decoded
    pixel codes, not names):
    - `--at 0.033` → code 1, the 16.67 ms frame written as `t00000017.png`. The
      33.33 ms frame's ms rounds to 33, so this case separates the rounded rule
      from the exact one.
    - `--at 0.034` → code 2;
    - `--range 0.017-0.034` → exactly code 2 (16.67 ms < 17 ms is excluded).
  - **Odd geometry, content varying in both axes:** `marker_frames()` draws 6×6
    dark squares at odd (x, y) on BG at several positions.
    - `frames --roi 37,151,201,243`: PNG is 201×243; each marker's dark-pixel
      centroid sits at `(mx − 37 + 2.5, my − 151 + 2.5)` within 0.3 px in
      **both** axes; manifest crop fields = 37, 151, 201, 243.
    - `--crop-top 23 --crop-bottom 11`: height 766; marker y shifted by 23
      exactly.
    - Premise guard: the same centroids measured on an un-cropped `frames` run
      sit at the drawn positions.
    - The same `--roi` on `anim` checks its segment manifest box and its view
      frame's markers (scaled by `scale_*`).
  - **`--roi 40,160,200,240` and `--crop-top`/`--crop-bottom`:** PNG dims equal
    the crop; the manifest crop fields and `scale_* = 1`; `sha256 ==
    hashlib(file)`; pixels match the generator's region.
  - **Cap:** `--range 0-1 --max-frames 10` → 10 files, `cap_hit` true,
    `omitted` 50, and the summary shows the continuation `--range`.
  - **Budget:** a 1080×2400 numbered clip (scaled bands) → the summary and
    run.json report 3354 tokens and the standard-tier warning only.
- **Bug/anim manifests:**
  - `bug --view-size 400` → `frames/frames.tsv` rows match the timeline files;
    out 180×400 read from the files; `scale_x` 0.5; hashes match; parsed name ms
    == `t_ms`.
  - `anim --roi …` → the segment manifest box equals the ROI.
- **Anim cap:**
  - the two-segment clip with `--max-segments 1` → `cap_hit` true, skipped 1;
  - a long slide with `--max-view-frames 5` → thinned, and the summary has the
    `frames … --range` hint;
  - a default short slide → `cap_hit` false (no false positive).
- **Errors** (added to `test_bad_inputs_fail_cleanly`):
  - frames without `--range`/`--at`, and with both → 2;
  - `--max-frames 0`, `--at x`, `--at -1`, `--range 2-1` → 1;
  - none of them leaves a directory.
- **Mutation checks during verification:** scratch-edit and revert with Edit.
  - name ms from `index × rate` → VFR red;
  - a wrong or stale digest written to `sha256` (e.g. a hash of the
    pre-extraction tmp name's bytes concatenated with a byte, or the previous
    row's digest) → the ROI test's comparison against `hashlib` of the written
    file goes red;
  - drop `exact=1` → odd-geometry red;
  - drop `format=rgb24` → check whether the odd-geometry test goes red. If it is
    not red, the luma-only markers cannot see it; say so rather than claim it
    is covered;
  - compare rounded ms in `--at` resolution → the `--at 0.033` boundary red;
  - `cap_hit` hard-coded False → cap red;
  - thinning not reported → anim-cap red.

  Before trusting each mutant, verify it actually changed the targeted output.

### 6. Skill text
`.claude/skills/aitask-screen-recording/SKILL.md`:
- add a row to "Pick a mode": "a close look at an exact moment, full resolution,
  or frames to edit by hand | `frames`";
- add a run example;
- add a short **Frames mode** section:
  - `--range` vs `--at`;
  - `t<ms>` names;
  - the `frames.tsv` meaning, and that geometry is trusted only while the image
    hashes to `sha256`;
  - the budget line and warnings: read full-res frames sparingly, and crop with
    `--roi`;
  - use it after `bug`/`anim` points at a moment;
- add a symptom row for the anim thinning hint;
- extend the Tests coverage list.

The `.agents/` and `.opencode/` wrappers are thin pointers and need no change.

### 7. Website docs
- `website/content/docs/skills/aitask-screen-recording.md`:
  - usage line and Modes row;
  - a `### frames` options table: full flag list, crop semantics, defaults;
  - `frames` output layout plus a `frames.tsv` column table;
  - `frames/frames.tsv` added to the bug and anim layouts, and anim `cap_hit` /
    `caps` added to the run.json prose;
  - warning rows: frames cap, the three budget warnings, anim thinning, and the
    extended max-segments note;
  - the "Image budgets" limit bullet updated with the tier numbers;
  - the Workflows list.
- New `website/content/docs/workflows/screen-recordings/exact-frames.md`,
  "Extract Exact Frames for Close Inspection":
  - the drill-down at an exact ms (`--at`) and over a range;
  - what `frames.tsv` means, and that geometry is valid only for unedited frames;
  - token cost and the warnings;
  - continuing past a cap.

  List it in the section `_index.md` ("Choose a mode" row and Walkthroughs) and
  in `workflows/_index.md` with `relref`. Write current state only, in
  agent-generic wording.
- Run `cd website && python3 check_links.py --build && hugo build --gc --minify`.

### Post-phase (risk mitigations)
1. [rotated_geometry_test] Add to `FramesMode` a fixture built by remuxing the
   numbered clip with `ffmpeg -display_rotation 90 -i in.mp4 -c copy rot.mp4`.
   - Skip with a reason if ffmpeg refuses, or if ffprobe shows no rotation side
     data. This premise guard asserts `probe()["rotation"] % 180 != 0`.
   - Assert for both `frames --range` and `frames --roi X,Y,W,H` (display
     coordinates):
     - `probe()` reports the swapped size (800×360);
     - the manifest `src_w`/`src_h` equal it;
     - PNG dims equal the crop box;
     - the frame times match the unrotated run;
     - the decoded content is the generator frame transposed: band codes read
       along the rotated axis, compared via MAD against the rotated generator
       frame.

### 8. Step 9 (Post-Implementation)
Commit the code, tests and docs (`feature: … (t1893_3)`), then follow Step 9 for
archival and the plan-file notes. The final notes for siblings cover: the parser
API, the manifest columns and mapping, the time_base rule, and the 3000 px fact.

## Verification
- `python3 tests/test_screen_recording_core.py`
- `python3 tests/test_screen_recording_cli.py`
- `bash tests/run_all_python_tests.sh --test-dir tests` (suite verdict, last line)
- The mutation checks above, each turning its own test red.
- Every documented flag checked against `frames --help` / `bug --help` /
  `anim --help`; claims checked against the writer code.
- `./.aitask-scripts/aitask_skill_verify.sh`; the website link check and hugo
  build.

## Risk

### Code-health risk: low
- Shared helpers (`extract_views`, `crop_filter` → `region_box`, the frame-name
  formatters) change under bug and anim. A slip changes existing outputs.
  Existing CLI tests pin names and timelines, and the formatter tests pin the
  literal strings · severity: low · → mitigation: none
- Adding `exact=1` changes bug/anim's analysed region for odd crop values. The
  new region is the requested one, which is a fix, but results on odd crops
  shift by ≤ 1 px. Existing tests use even values; the odd-geometry fixture pins
  the new behaviour · severity: low · → mitigation: none

### Goal-achievement risk: low
- Geometry under a rotated recording (display matrix) is unverified. All
  synthetic fixtures are unrotated, and t1893_5 maps ROIs through this record ·
  severity: low (residual — addressed by inline post-phase rotated_geometry_test)
  · → mitigation: inline post-phase rotated_geometry_test
- The `pts_time` fallback for an ffmpeg without the time_base line can only be
  unit-tested (this host has ffmpeg 9). It is labelled in `time_source`, never
  silent · severity: low · → mitigation: none

### Planned mitigations
- timing: post-phase | name: rotated_geometry_test | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: geometry under a rotated recording unverified | desc: Rotated-recording fixture asserting display-orientation manifest geometry, PNG dims and content for frames and frames --roi

## Post-Review Changes

### Change Request 1 (2026-11-05 08:47)
- **Requested by user:** three review findings, each verified (reproduced locally) before fixing:
  1. A stream that changes frame size mid-way: ffmpeg rescales later frames to the first one's size after the filter chain, and the manifest recorded the probed size for all of them.
  2. The end check compared against `vspan.end_t` whether or not it was proven, with a 1 µs tolerance. `--at 1` / `--at 1.0000005` on a 1 s clip resolved with `on_screen_proven: true`, and a raw H.264 stream rejected `--at 0.2` against an unproven 0 s end.
  3. The continuation `--range` floored the first omitted frame to ms. With frames at 0, 1.49 ms and 1.51 ms and `--max-frames 1`, it repeated `0.001-…` forever.
- **Changes made:**
  1. `parse_showinfo_frames` (instance, pts, printed pts_time, `s:` size, duration) replaces `parse_showinfo_raw`. `enumerate_frames` records each frame's native size and exact end, and sorts by time; decode order can differ from presentation order.
     - `frames` refuses (before writing) any chosen frame whose size differs from the probe.
     - `extract_views` puts a showinfo before and after the crop/scale and returns `{pts: (native, out)}`; `geometry_problem` checks both.
     - `frames` errors on a mismatch. `bug`/`anim` skip `frames.tsv` and write the reason: `manifest: null` + `manifest_note` in bug's run.json and a summary warning; a segment warning in anim.
  2. A frame is proven on screen at T when a later frame exists (a listed later frame, or a packet presented more than 2 µs after T), or when T < its own exact end (pts + duration, from showinfo). A time at or past the last frame's end is an error only when packets are complete on a confirmed origin. Otherwise the frame is written with `on_screen_proven: false` and an `unproven_because` reason.
  3. `core.decimal_between(lo, hi)` gives the shortest decimal (3–9 places) with lo < d ≤ hi. The continuation starts there, or the warning says no such decimal exists.
  - Docs (skill page, walkthrough, SKILL.md) describe the size-change refusal, the end semantics and the continuation guarantee. An unverified "when the device rotates" example was dropped.
- **Files affected:** `.aitask-scripts/screen_recording/video_prep.py`, `vp_core.py`, `tests/test_screen_recording_cli.py`, `tests/test_screen_recording_core.py`, `.claude/skills/aitask-screen-recording/SKILL.md`, `website/content/docs/skills/aitask-screen-recording.md`, `website/content/docs/workflows/screen-recordings/exact-frames.md`
- **Verification:**
  - New tests:
    - `test_mid_stream_size_change_is_refused_not_rescaled`
    - `test_size_change_mid_stream_records_no_geometry`
    - `test_video_end_is_exclusive_and_only_a_proven_end_rejects`
    - `test_unproven_end_is_labelled_never_used_to_reject`
    - `test_continuation_range_always_moves_past_the_written_frames`
    - core `decimal_between` / `parse_showinfo_frames`
  - Each fixture carries a guard asserting its premise.
  - Mutants, each red and then restored (module checksum matched before and after):
    - size checks disabled → both size tests red;
    - `later = True` → both end tests red;
    - the old floor → the continuation test wrote `[0, 149, 149, 149, 149]`.
  - Core 72 OK; CLI 51 OK; `check_links.py --build` PASSED; hugo build OK.
- **Not root-caused:** with a B-frame size-change fixture, one test run saw `magick failed (1)` in bug mode. It did not reproduce outside the test, and the fixture was switched to `bframes=0` (raw-stream timestamps then follow decode order).

### Change Request 2 (2026-11-05)
- **Requested by user:** two findings, both verified.
  1. FFmpeg 5.1, the documented minimum, prints no `duration:` in showinfo; confirmed from `release/5.1` `libavfilter/vf_showinfo.c`. `f.end` was then always None, so `--at 2` on a 1 s clip was written as unproven while run.json reported `video_end_proven: true`.
  2. The anim half of the size-change test skipped any segment that had a `frames.tsv`, so returning `None` from anim's geometry check stayed green.
- **Changes made:**
  1. With no frame duration, the end comes from `vspan` when it is proven (complete packet times on a confirmed origin, plus the last packet's duration).
     - T ≥ end + 2 µs is an error (`(from the video's packets)` in the message).
     - T within ±2 µs is unproven, since packets print 6 decimals.
     - Otherwise T is proven.

     A genuinely unknown end (incomplete packets, or no duration anywhere) stays unproven with its reason.
  2. The test now:
     - asserts the fixture's only segment (`s01`) spans the size change (saved frames before and after 0.1 s);
     - asserts `s01` has no `frames.tsv` and carries the warning;
     - asserts `run.json` `manifests == []`.
  - New class `ShowinfoWithoutDuration` simulates 5.1 by patching the module's `ffmpeg()` to remove the field from the real log, asserting the removal happened. It covers the packet-proven end (0.99 proven, 2 rejected, 1 undecided) and a raw stream whose end is unknown.
  - Docs: the skill page says where the end comes from when ffmpeg reports no frame durations. An unverified "before 6.0" claim was reworded to the verified "5.1 does not".
- **Verification:**
  - mutant `elif vspan.proven` → `elif False`: the packet-end test red, the unknown-end test green (as it should be);
  - mutant anim `manifest_note = None`: the size-change test red;
  - both reverted (0 `MUTANT` markers);
  - core OK, CLI 53 OK, link check PASSED.

### Change Request 3 (2026-11-05)
- **Requested by user:** test portability. `run_stripped` required that it had removed a `duration:` field, which fails on an FFmpeg whose showinfo already prints none (5.1). The FramesMode end test hard-coded the exact-duration outcomes (0.999999 proven; 1 and 1.0000005 rejected), which contradicts the packet-end uncertainty band on such a runtime. Verified by reading both tests; no production change.
- **Changes made:**
  - `run_stripped` asserts the intended format itself: the code saw showinfo frame lines and none carries a duration. The substitution is a no-op where the field is absent.
  - New `showinfo_prints_duration()` probe (cached).
  - The end test asserts what holds on every FFmpeg (0.99 proven, 1.5 rejected), then branches on the probe:
    - exact per-frame durations: 0.999999 proven, 1 and 1.0000005 rejected;
    - packets only: all three unproven.
  - `ShowinfoWithoutDuration` pins that band (0.999999 / 1 / 1.0000005) on every host.
- **Verification:**
  - A PATH-shim `ffmpeg` (scratchpad) removes showinfo's duration fields from stderr. It passes through failures (exit 254 for a missing input) and makes the probe return False.
  - The full CLI file passes natively (53/53) and under the shim (53 ok, none skipped); core OK.

## Final Implementation Notes
- **Actual work done:**
  - `frames VIDEO (--range A-B | --at T[,T…]) [--roi | --crop-top/--crop-bottom] [--max-frames 60] [--out]` writes full-resolution native frames to `<out>/frames/t<ms>.png`, together with `frames.tsv`, `summary.md` and `run.json`.
  - Times are exact (`pts × time_base` as a `Fraction`, from showinfo's `config in time_base` line, with a labelled `pts_time` fallback). Selection compares exact times; rounded ms are only names and labels.
  - Every `frames/` directory (bug, anim, frames) carries `frames.tsv`: `file t_ms pts time_source src_w src_h crop_x crop_y crop_w crop_h out_w out_h scale_x scale_y sha256`. `out_*` is read from the PNG header, and the hash is taken of the file as written.
  - `crop_filter` emits `exact=1` everywhere, and `extract_views` converts to RGB before cropping.
  - anim reports `cap_hit` plus `caps` (`max_segments` skipped and first-skipped time; `max_view_frames` thinned segments with a `frames --range` hint). bug's `cap_hit` is unchanged.
  - Image budget: `vp_core.TOKEN_TILE` (moved; still one constant), `READER_TIERS`, `MANY_IMAGE_SAFE_PX`, `image_budget()`, with summary and stdout warnings.
  - Shared pure helpers in `vp_core`:
    - `parse_frame_name` / `FrameName` and the formatters `frames_name`, `bug_frame_name`, `anim_frame_name`;
    - `seconds_exact`, `ms_round`, `pts_ms`, `time_ms`;
    - `parse_showinfo_frames` / `ShowinfoFrame`, `parse_showinfo_timebase`;
    - `png_size`, `decimal_between`, `range_arg`.
  - Docs:
    - the skill page gains a `### frames` options table, the frames output layout, a `### frames.tsv` column table, warning rows and the image-budget numbers;
    - new walkthrough `workflows/screen-recordings/exact-frames.md`, listed in both indexes;
    - SKILL.md gains a Frames mode section.
- **Deviations from plan:**
  - Plan review, before implementation:
    - added `exact=1` and RGB-before-crop, plus the odd-geometry fixture;
    - switched selection to exact times, plus the 0.033/0.034 boundary tests;
    - removed the "+1 ms" retry shortcut from the docs.
  - Code review (Change Requests 1–3):
    - refuse or skip-manifest when the frame size changes mid-stream (native vs output size from two showinfo instances);
    - an exclusive, evidence-based video end: a later frame, the frame's own duration, or the packet end when showinfo has no duration (FFmpeg 5.1). Only a proven end rejects; otherwise the frame is labelled unproven;
    - the continuation `--range` starts strictly after the last written frame;
    - tests made independent of whether showinfo prints durations.
  - The `exact=1` mutant was green for the extracted frames, because the RGB step already makes them exact. An anim analysis-path bbox assertion (`23,99,182,148`) was added, which catches it.
  - Frames are sorted by presentation time, since decode order can differ.
- **Issues encountered:**
  - The no-RGB mutant stays green: gray fixtures only test luma, so chroma alignment at odd offsets is not covered by a test.
  - One `magick failed (1)` in bug mode on a B-frame size-change fixture was not reproducible outside the test. The fixture now uses `bframes=0`.
  - The full Python suite passed once (`PYTHON SUITE: PASSED`, 10841 + 15) before the review rounds. Those rounds touched only screen-recording files, which pass natively and under a durationless-ffmpeg shim.
- **Key decisions:**
  - `--max-frames` keeps the earliest contiguous frames and never thins.
  - A mid-stream size change is refused for `frames` (fail closed). bug/anim still run but write no manifest, with `manifest: null` and `manifest_note`.
  - Unproven end → label, never error.
  - The many-image limit uses 3000 px (Vision page, 2026-11-04), not the task's stale 2000 px.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - **Parser (t1893_4/5/6):**
    - `vp_core.parse_frame_name(name)` accepts exactly `t\d{8,}`, `\d{2,}_\d+\.\d{3}s` and `f\d{3,}_\d+\.\d{3}s` with a png/jpg/jpeg/webp extension. It rejects anything else, including user suffixes such as `t00007040_edited.png`.
    - If `sheet`/folder input should accept edited names, extend the parser deliberately and keep the garbage-rejection tests.
  - **Geometry (t1893_5):**
    - Trust a `frames.tsv` row only while `sha256(file) == sha256`.
    - Source px = `crop_x + img_x / scale_x` (and the same for y). `src_*` are display-orientation pixels, which is what `--roi` takes.
    - Rotated input is tested.
  - **Times:**
    - Compare exact `Fraction`s (`seconds_exact` for user input, `pts × time_base` for frames). Never compare rounded ms.
    - FFmpeg 5.1's showinfo has no `duration:` field; ffmpeg 9 prints it.
    - ffmpeg rescales frames of a new size after the filter chain. Detect that with a showinfo before the crop (see `extract_views`' return value and `geometry_problem`).
  - **Continuations:** `decimal_between(lo, hi)` gives the shortest decimal strictly after one frame and at or before the next.
  - **Test fixtures:**
    - `synth.code_frame` / `numbered_frames` / `decode_code`: each frame identifies itself from its pixels.
    - `held_numbered_frames` + `NUMBERED_STARTS`: VFR with known starts.
    - `marker_frames` + `dark_centroid`: odd-coordinate geometry.
    - `size_changing_video(tmp)`, and the `ShowinfoWithoutDuration` patch pattern.
  - **Docs:** new outputs go in the skill page's reference tables, and how-tos go in workflow subpages listed in both indexes (relref).
