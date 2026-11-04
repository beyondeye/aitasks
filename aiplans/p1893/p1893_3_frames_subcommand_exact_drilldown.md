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
  - Consequence (documented): a name's ms is rounded to nearest, so passing a
    name that rounded *down* back as `--at` (e.g. `t00000033` for 33.33 ms)
    selects the previous frame. To re-extract a named frame, add 1 ms. The
    summary and run.json show each request's resolved exact time (6 decimals).

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
