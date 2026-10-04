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

`info` only probes the file (size, frame rate, duration, audio).

## Run it

```bash
./.aitask-scripts/aitask_screen_recording.sh bug  rec.mp4 --out <scratchpad>/video-prep/rec-bug
./.aitask-scripts/aitask_screen_recording.sh anim rec.mp4 --out <scratchpad>/video-prep/rec-anim
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
  sheets and plots; without it you still get frames and data.

## Read the results in this order

1. **`summary.md`.** Always first: what was found, which files to open, and
   warnings.
2. **Contact sheets** (`sheet_*.png`). One Read each; they are sized to stay
   under the image downscale limit, and the summary gives their approximate
   token cost.
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
5× and passing `--time-scale 5` gives five times the samples per curve.

Ask the user to confirm suspicious numbers. If every duration looks two to ten
times too long, the device may have had a non-default animator duration scale
during recording.

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
  one-frame flash.

Run them after changing anything under `.aitask-scripts/screen_recording/`.
