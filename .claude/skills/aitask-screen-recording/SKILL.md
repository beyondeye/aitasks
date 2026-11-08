---
name: aitask-screen-recording
description: Turn a screen-recording video (.mp4, .mov, .webm, .mkv from a phone, emulator or desktop) into labelled contact sheets, key frames, a timeline, and measured animation timing and easing, because coding agents can read images but not video files. Use this whenever the user gives, attaches or mentions a video or screen recording, including a bug-report recording ("see repro.mp4", "here's a capture of the glitch"), a design or motion prototype to implement ("match this transition", "what duration/easing is this", "implement the animation in the video"), or any request to watch, analyse, describe or compare a video, even if they never ask for frames.
---

# Screen recordings, made readable

Coding agents read images, not video. `./.aitask-scripts/aitask_screen_recording.sh`
turns a recording into
three things:

- a few **labelled contact sheets** to look at;
- **individual frames** for close-ups;
- **numbers**: timestamps, how long each screen stayed up, and for animations
  the measured progress curve with fitted easing.

Use the images for *what* is on screen and the numbers for *when* and *how
fast*. Your eyes cannot judge a 17 ms difference or tell CSS ease-out from M3
standard; the measurements can.

## Pick a mode

| The user wants… | Mode |
|---|---|
| what happened, a bug reproduced, a flow described | `bug` |
| how something moves (duration, easing, spring), usually to implement it | `anim` |
| a bug *in* an animation | `bug` first, then `anim --window` around that moment |
| a close look at an exact moment at full resolution, or frames to edit by hand | `frames` (usually after `bug`/`anim` has pointed at the moment) |
| a folder of images the user already has, for example frames they edited by hand | `sheet DIR` |
| the bug review or the animation measurement of a curated folder of images (frames kept after deleting some, or screenshots) | `bug DIR` / `anim DIR` (see Image folder input) |
| the user wants to choose the frames you read, by eye | `pick` on the run (see Pick frames visually) |

`info` only probes the file (size, frame rate, duration, audio).

## Run it

```bash
./.aitask-scripts/aitask_screen_recording.sh bug  rec.mp4 --out <scratchpad>/video-prep/rec-bug
./.aitask-scripts/aitask_screen_recording.sh anim rec.mp4 --out <scratchpad>/video-prep/rec-anim
./.aitask-scripts/aitask_screen_recording.sh frames rec.mp4 --at 5.5 --out <scratchpad>/video-prep/rec-frames
./.aitask-scripts/aitask_screen_recording.sh anim <frames-folder> --out <scratchpad>/video-prep/curated-anim
./.aitask-scripts/aitask_screen_recording.sh sheet <folder> --out <scratchpad>/video-prep/edited-sheet
./.aitask-scripts/aitask_screen_recording.sh pick <run-dir> --open --out <scratchpad>/video-prep/rec-pick
```

Run it from the repository root; `<mode> --help` lists every option.

- **Output location:** put `--out` in the session scratchpad, never inside the
  user's repository, and never copy the recording into the repo. Recordings
  often contain personal data. Without `--out` it writes to
  `$TMPDIR/video-prep/`.
- **Never overwrites:** an existing non-empty directory gets `-2`, `-3`, … The
  last stdout line is `SUMMARY: <path>`.
- **Uploading:** don't send a recording to any external service (for example a
  video-capable model API) unless the user explicitly agrees for that file.
- **Requirements:** ffmpeg 5.1+ on PATH (not installed by `ait setup`; if it is
  missing, tell the user to install it). ImageMagick 7 (`magick`) is needed for
  sheets and plots; without it you still get frames and data, and `sheet`
  refuses to run. `pick` needs only a browser.

## Read the results in this order

1. **`summary.md`.** Always first: what was found, which files to open, and
   warnings.
2. **Contact sheets** (`sheet_*.png`). One Read each; they are sized to stay
   under the image downscale limit, and the summary gives their approximate
   token cost. Every label fits its cell, so a sheet may hold fewer than
   `--per-sheet` frames; the summary lists the frames on each sheet.
3. **Single frames**, only the ones you need in detail. Each costs roughly as
   much as a sheet, so don't read them all.
4. **Data:** `timeline.tsv` (bug), `curve.tsv` and `fit.json` (anim) when you
   need exact values.

## Bug mode

ffmpeg's `mpdecimate` drops every frame that doesn't visibly differ from the
last kept one. Each kept frame therefore marks a change, and the gap to the next
kept frame is how long that picture stayed on screen ("shown for"). Picks:

- **start / end:** the first and last picture.
- **state:** stayed at least `--min-dwell` (0.4 s). These are the screens the
  user actually saw.
- **motion:** one frame per `--interval` (1 s) of continuous change, such as
  scrolling or long animations, counted from the start of the change. An
  ordinary 300 ms transition is not sampled; you see the screens before and
  after it.
- **brief:** a change that was over within `--brief-max` (0.12 s), such as a
  flash, a glitch frame or a very quick transition. These are often the bug, so
  look at them.

- **black:** the first frame of each black interval (below), even one that
  change detection dropped as a near-duplicate. It ranks below start/end and
  above every other pick under `--max-frames`.

The summary's **Freeze, black and silence** section lists every interval
ffmpeg's detectors found, also in `timeline.tsv` (`kind` freeze / black /
silence, `time_s`–`end_s`) and `run.json` (`intervals`):

- **freeze:** no change above freezedetect's noise floor for `--freeze-min`
  (2 s). Small changes such as a toggled checkbox can sit inside one. It is a
  hang only if the frames show the user acting and nothing answering; otherwise
  it is just a still screen. Never call it a hang without that evidence.
- **black:** ≥ 98 % of pixels near black, any length (`--black-min` 0). A dark
  screen counts too, so look at the interval's frame first.
- **silence:** audio below −60 dB for 2 s, only when there is an audio track.
- An end shown as `≥ … (span ended)` (`end_observed: false`) was not observed:
  the state was still on when the analysed span ended, so the duration is a
  lower bound. Report it as such.

Cite intervals like frames (`freeze 2.000–4.500 s`, `black at 5.000 s,
frames/04_5.000s.png`).

When you report, reconstruct the flow as numbered steps, each citing time and
frame (`#4 at 5.50 s, frames/04_5.500s.png: the checkbox becomes checked`).
Separate what is visible from what you infer about the cause. A frame shows what
was on screen, not why. Audio is detected and reported but not transcribed. The
container `creation_time` is low-confidence for lining frames up with logs, so
ask for the recording's start time if precise alignment matters.

| Symptom | Fix |
|---|---|
| Clock, battery or notification icons create extra picks | `--crop-top <px>` (Android status bar is about 3–4 % of the height); `--crop-bottom` for the navigation bar |
| Too many motion picks | `--interval 2`, or `--range START-END` around the interesting part |
| Only part of the screen matters | `--roi X,Y,W,H` in source pixels (the summary gives the frame-to-source factor) |
| A small change (toggle, badge) is not detected | more sensitive detection: `--decimate hi=256:lo=128:frac=0.1` |
| "N more dropped by --max-frames" | narrow with `--range` rather than raising the cap |
| "N black intervals have no image" | every interval is still listed; rerun with `--range` around the listed times to see their frames |
| A clock in the status bar breaks every freeze | `--crop-top <px>`: the detectors use the same region as change detection |

## Anim mode

`anim` does this in four steps:

1. Finds **motion segments**: runs of change separated by a pause longer than
   `--gap` (0.12 s). Single-frame changes are listed as cuts, not analysed.
2. Decodes every native frame of each segment plus `--pad` (0.25 s) on both
   sides.
3. Measures each frame's **progress** from the still picture before the motion
   (0) to the settled picture after it (1). Overshoot reads above 1.
4. Fits named easing curves, a free cubic-bezier and a spring to that progress.

Work through a segment like this:

1. **Confirm it's the right animation.** Check the segment's sheet against what
   the user asked about; segments are numbered in time order.
2. **Check the geometry and signal lines** in the summary:
   - `edge+`/`edge-` along x or y: one edge leads, as in a slide, or a growth
     anchored on the opposite side. Exact, including overshoot.
   - `grow`/`shrink`: centred scaling. Approximate near the ends.
   - `fade/blend`: no geometry change, as in an opacity cross-fade. Exact for
     fades. For a full-screen push or slide the *timing* is still right but the
     curve shape is only a proxy.
3. **Act on warnings.**
   - A *travel spread* warning means more than one thing moves, or a fade is
     combined with the move. Rerun with `--roi` around the one element.
   - `--window START-END` analyses an exact span as a single motion. The first
     frame must be still before the motion and the last frame still after it.
4. **Read durations correctly.**
   - *Visible duration* runs from the first changed frame to the settled frame,
     ± one frame. It reads short when the start or end is so slow that it moves
     less than a pixel.
   - The *fitted duration* models those tails, so implement the fitted value.
5. **Choose the curve.** RMSE is in progress units (1.0 = the whole movement).
   - Fits within about 0.005 RMSE of each other are indistinguishable at this
     resolution. Pick the one the target platform names: Compose or M3 tokens
     for Android, CSS keywords for web, iOS defaults.
   - Use the custom cubic-bezier only if it beats every named curve clearly
     (RMSE under half, and more than 0.01 better).
   - Overshoot above about 2 % means a spring; use the spring fit, which also
     gives the nearest Compose preset and a SwiftUI response.
6. **Round with care.** Real animations are aligned to vsync, so report "about
   300 ms". Snap to a design-token duration only if it lies within one frame.

Translating a fit into code:

```kotlin
// Compose
tween(durationMillis = 300, easing = CubicBezierEasing(0f, 0f, 0.58f, 1f))
spring(dampingRatio = Spring.DampingRatioMediumBouncy, stiffness = Spring.StiffnessMediumLow)
```
```css
transition: transform 300ms cubic-bezier(0, 0, 0.58, 1);
```
```swift
.animation(.timingCurve(0, 0, 0.58, 1, duration: 0.3), value: x)
.animation(.spring(response: 0.314, dampingFraction: 0.5), value: x)
```

Precision is limited by the recording. A 60 fps capture times to ±17 ms.
Phone screen recorders often drop frames under load, so a large frame interval
in the summary means coarser timing. When precision matters and the user can
re-record, read
`.claude/skills/aitask-screen-recording/references/recording.md`. Recording at animator duration scale
5× and passing `--time-scale 5` gives five times the samples per curve. Only
durations and fits are converted to real time. Timestamps, `curve.tsv` and the
`--window`/`--range` arguments stay in recording time.

Ask the user to confirm suspicious numbers. If every duration looks two to ten
times too long, the device may have had a non-default animator duration scale
during recording.

When a segment's line says `saved frames: N of M (thinned by
--max-view-frames …)`, the sheet skips frames. The line gives the `frames …
--range` command that writes every native frame of the segment.

## Frames mode

`frames` writes exact native frames at **full resolution**, for a close look or
for the user to edit by hand (crop, annotate, delete) and hand back.

- `--range A-B`: every frame presented from A up to, not including, B, up to
  `--max-frames` (60). The earliest frames are kept; the summary says what was
  left out and gives the `--range` that continues.
- `--at T[,T…]`: the frame on screen at each time, meaning the latest frame
  presented at or before it. A time past the proven end of the video is an
  error. When the end cannot be proven, the frame is written but marked "not
  proven" in the summary (`on_screen_proven: false` in `run.json`). Say so
  when you cite it.
- A recording whose frame size changes partway through is refused for frames
  of another size than the probed one. `bug` and `anim` then write no
  `frames.tsv` and say why.
- `--roi X,Y,W,H` or `--crop-top`/`--crop-bottom` crop the written image.
  In `bug` the same flags only steer change detection.
- Files are `frames/t<ms>.png`, where ms is the frame's presentation time
  (pts × time base) rounded to the nearest millisecond. Treat that ms as a
  label: selection compares exact times, so a rounded time passed back as
  `--at` can select the neighbouring frame.
- `frames/frames.tsv` has one row per image: `t_ms`, `pts`, the source size,
  the crop box, the written size, the scale, and the image's `sha256`.
  Source px = crop offset + image px / scale. **Trust the geometry only while
  the image still has that hash**; an edited frame has none. `bug` and `anim`
  write the same manifest beside their frames.
- **Image budget.** The summary and stdout give each frame's token cost
  (⌈w/28⌉·⌈h/28⌉) and warn when frames are over a reader's limit. A
  1080×2400 phone frame is about 3354 tokens and is downscaled for models
  before Claude 4.7. A frame over 3000 px on a side is rejected once a
  request carries more than 20 images. Read full-resolution frames
  sparingly, and crop with `--roi` to the detail that matters.

## Sheet mode

`sheet DIR` turns a folder of png/jpg/webp images (top level only) into
labelled contact sheets: the way back in for frames the user extracted with
`frames`, then cropped, annotated or deleted by hand.

- **Order and times come from the file names.** A name carries a time when it
  starts with a name this helper writes (`t00007040`, `04_5.500s`,
  `f013_0.483s`), optionally followed by `_`, `-`, `.`, a space or `(` and
  anything else (`t00007040_annotated.png`). Those come first, by time; the
  rest come last in name order with no time, and the summary warns about them.
- **Labels:** `#order name` over `time s +N ms`. `+N` is the time since the
  previous timed image, from the rounded milliseconds in the names (±1 ms), so
  a **deleted frame shows up as a larger +N**. The first timed image says
  `first`; an untimed one says `no time in name`; `edited` means the image no
  longer matches the SHA-256 in the folder's `frames.tsv`, so its geometry is
  unknown. The summary's **Gaps** list names steps over 1.5× the median; that
  is a heuristic (a deleted image, or a still screen in a variable-frame-rate
  recording), so say which it is only when you know.
- Images of different sizes are letterboxed into equal cells, never stretched;
  `tiles.tsv` gives each tile's fit scale. Labels always fit their cell, so a
  sheet may hold fewer than `--per-sheet` (8) images; the summary says when.
- Images ImageMagick cannot read are left out and listed, and `+N` skips them.
  An animated image contributes its first frame only.
- Read `summary.md`, then the sheets. `tiles.tsv` maps each tile (sheet, row,
  column) to its file.

## Image folder input

`bug DIR` and `anim DIR` run the same analysis on a folder of images as on a
recording (top level only; png/jpg/jpeg/webp; hidden files and `frames.tsv`
are ignored). Use it when the user curated frames — usually `frames --range …
--max-frames N` (default cap 60), then deleted or retouched some — or has only
screenshots.

- **Timing:** every name must carry a time, as `sheet` reads names
  (`t00007040.png`, `t00007040_note.png`, `04_5.500s.png`, `f013_0.483s.png`),
  to the millisecond. For names with no time, `--fps N` times them in natural
  name order; say that this timing is assumed, as the summary does. The tool
  refuses partly timed folders, duplicate times and `--fps` on timed names;
  relay the message, which names the files.
- **Report times in recording time.** They are the times the names carry, so
  `--window`, `--range` and the times you cite match the recording.
- **Gaps:** a step over 1.5× the estimated frame interval is a gap (a deleted
  frame, or a still screen in a variable-frame-rate recording — do not claim
  which unless you know). When gaps are listed, the timing is not native-frame
  accurate there: quote the visible duration **with its ±**, which grows to
  the longest step at the motion's ends.
- **`unreliable (gap before the motion)`** in the segment table (and
  `fits_reliable: false` in `fit.json`) means frames are missing just before
  the motion, further back than the fitter's onset search. Do **not**
  recommend those fitted durations or curves; give the visible duration and
  its ±, and suggest re-extracting that span without deletions.
- **Sizes and formats:** `anim` needs one image size and names the odd ones;
  `bug` letterboxes mixed sizes (no `frames.tsv`, no `--roi`). Mixed pixel
  formats are normalised so the detectors see one stream. There is no audio.
- **Provenance:** `run.json` has `input: images`, `input_dir_abspath`,
  `timing`, `gaps`, `sizes`, `letterboxed` and `normalized`; `video_abspath`
  is null, so `pick` on such a run names the folder, not a video.

## Pick frames visually

`pick` builds a static page (`<out>/index.html`, no server) from a run's frames.
The user selects frames in the browser, may mark a start and an end frame or
drag a rectangle, presses Copy and pastes a plain-text block back to you.

**When to ask.** After an extraction that wrote frames (`bug`, `anim` or
`frames`), ask once per recording whether the user wants to pick frames, unless
they already said which frames matter. Use AskUserQuestion, with everything
needed to answer inside the widget:

- Question: "I extracted <N> frames from <video> (<run dir>). Do you want to
  pick the ones that matter yourself? A page opens in your browser: click
  frames (shift-click for a range), optionally mark a start and an end frame or
  drag a rectangle, press Copy, and paste the text back here."
- Header: "Pick frames"
- Options: "Pick them in the browser" (description: "Open the picker page; I
  wait for the pasted selection") / "Let the agent choose" (description: "I
  choose the frames myself from the summary and sheets").

On agents whose question tool is `request_user_input` (Codex CLI: up to 3
questions with 4 options each) or `ask` (OpenCode), ask the same two-option
question. It is the user's decision, so ask it in default mode too.

**On "Pick them in the browser":**

```bash
./.aitask-scripts/aitask_screen_recording.sh pick <run-dir> --open --out <scratchpad>/video-prep/<name>-pick
```

- `OPEN: opened (...)`: tell the user to paste the copied block here, then
  stop and wait for it.
- `OPEN: not opened: <reason>` (an SSH session, no display, no opener): give
  the user the `PAGE:` path in case they can open it in a browser elsewhere,
  then choose the frames yourself. A missing display is never a failure.

**On "Let the agent choose":** choose the frames yourself as usual.

`pick` accepts a run directory (`bug`/`frames`: its `frames/`; `anim`: every
`sNN/frames/` or `w01/frames/`), a `frames/` directory, or any image folder.
It copies every image into `<out>/src/` and hashes it there first, so the
block's paths point at exactly what the user saw.

**Reading the pasted block:**

- **Frame lines** are tab-separated: the absolute path (read these files),
  `t=<ms> ms`, the step since the previous selected frame, and any `note:`.
- **`# viewing range:`** is where the user looked, not a measurement window.
  The picker checks no pixels and never calls a frame still or settled.
- **`# --window A-B (user-marked endpoints (unverified): ...)`** appears only
  when the user marked a start and an end frame. Its bounds sit 0.5 ms outside
  the two frames' times, so `anim --window` starts and ends on exactly those
  frames. It is **unverified**:
  - run `anim <video> --window A-B`, keeping the source run's `--roi`/crop
    flags;
  - trust the window only if anim's endpoint diagnostics agree (`curve.tsv`
    lists the window's frames with their times). On the "visible change" line
    the first changed frame must not be the window's second frame (the motion
    was already under way at the start frame), and the settled frame must not
    be the window's last frame (the motion may go on past it). The segment must
    not report "nothing changed" or "returns to where it started";
  - otherwise say the marks cut the motion, and widen the window or let anim
    find the segments.
- **`# --roi X,Y,W,H (source-video pixels, ... SHA-256 verified)`** is safe to
  pass to `anim`/`bug`/`frames`. A `# rectangle ... in <file>'s own pixels`
  line is **not** a `--roi`: the frame had no trusted `frames.tsv` geometry (no
  manifest, or the image changed since extraction). Use it only to describe
  where to look in that image.
- **`# source:`** names the recording when the run recorded a proven path
  (`video_abspath` + `video_size` in run.json). `<VIDEO>` means it could not
  (the reason follows); ask the user for the path before rerunning anything.
- `# no --window: <reason>` means the marks were incomplete or invalid; ask
  the user if a measured span was intended.

## More detail

- `.claude/skills/aitask-screen-recording/references/animation.md`: how progress is measured (the edge and blend
  signals and their derivation), the fitting models and named curves, and known
  limits with their workarounds. Read it before trusting an unusual result or
  explaining one to the user.
- `.claude/skills/aitask-screen-recording/references/recording.md`: how the user can capture a better recording
  (Android `screenrecord`/scrcpy flags, show taps, slowed animations, logcat
  alongside, iOS/desktop notes). Hand them the relevant part when the input is
  poor.

## Tests

```bash
python3 tests/test_screen_recording_core.py   # pure analysis, seconds
python3 tests/test_screen_recording_cli.py    # end to end, ~2 min, needs ffmpeg
```

The tests run synthetic recordings with known ground truth through the real
CLI. They cover:

- slides in each direction, fades, a centred grow and an overshooting spring;
- a variable-frame-rate encode and a slowed-down (5×) capture;
- two segments in one clip and status-bar cropping;
- a bug flow with a push transition, a scroll, a checkbox toggle and a
  one-frame flash;
- `frames` on clips whose frames carry their own number in pixels:
  - names from real pts on a variable-frame-rate clip;
  - exact `--at`/`--range` boundaries;
  - odd `--roi`/crop boxes in both axes;
  - a rotated recording;
  - the `--max-frames` cap and the image budget;
- the `frames.tsv` manifests of bug and anim, and anim's `cap_hit`;
- `sheet` on folders of generated images (no ffmpeg; needs `magick`): order
  and `+N` with a deleted frame, untimed and suffixed names, letterboxing,
  unreadable and animated files, labels that fit narrow cells, and the
  `--per-sheet` split.
- bug/anim sheets: labels that fit a narrow `anim --roi` strip, and a sheet
  cut short so its labels fit, with the summary's per-sheet frame ranges.
- `bug DIR` / `anim DIR`: a `frames` → `anim DIR` round trip against the
  video result, every third frame deleted (gap warning, widened ±, same
  curve), frames missing before the motion (fits marked unreliable), `--fps` on
  untimed names, mixed sizes (anim refuses, bug letterboxes), alternating
  gray/RGB images that keep the freeze detector's state, the concat time
  guard, and the refusals.
- `pick` (no ffmpeg needed for most): run layouts before root images (a bug
  run's sheets, `anim --window`'s `w01`), the snapshot and its hashes,
  collision-free snapshot names, JSON that cannot break out of its script
  element, the source video only from a proven path, geometry refused for
  same-size edits, outward-rounded `--roi` checked against drawn markers,
  viewing range versus marked `--window` (a round trip through `anim
  --window`), the opener with and without a display, the page's JS against
  the Python reference under node, and the page driven by real events in
  headless chromium.

Run them after changing anything under `.aitask-scripts/screen_recording/`.
