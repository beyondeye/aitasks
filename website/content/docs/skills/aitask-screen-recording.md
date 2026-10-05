---
title: "/aitask-screen-recording"
linkTitle: "/aitask-screen-recording"
weight: 115
description: "Turn a screen recording into contact sheets, key frames, a timeline and measured animation timing an agent can read"
maturity: [experimental]
depth: [intermediate]
---

Turns a screen recording — `.mp4`, `.mov`, `.webm` or `.mkv` from a phone, an emulator or a desktop — into things a coding agent can actually read: a few labelled **contact sheets**, **individual frames** for close-ups, and **numbers** (timestamps, how long each screen stayed up, and for animations the measured progress curve with fitted easing). Coding agents read images; most cannot open a video file. Some agent CLIs may accept video directly, but that is unverified, and the skill does not depend on it.

Use the images for *what* is on screen and the numbers for *when* and *how fast*. An agent looking at frames cannot judge a 17 ms difference or tell CSS ease-out from Material 3 standard easing; the measurements can.

You rarely invoke the skill by name: it triggers when you mention or attach a recording ("see repro.mp4", "match this transition"). The work is done by a helper script you can also run yourself.

**Usage:**
```
/aitask-screen-recording                      # or just mention/attach a recording
./.aitask-scripts/aitask_screen_recording.sh info VIDEO
./.aitask-scripts/aitask_screen_recording.sh bug  VIDEO [--out DIR] [options]
./.aitask-scripts/aitask_screen_recording.sh anim VIDEO [--out DIR] [options]
./.aitask-scripts/aitask_screen_recording.sh <mode> --help
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

For end-to-end walkthroughs of the two use cases, see the [Screen Recordings workflow]({{< relref "/docs/workflows/screen-recordings" >}}).

## Step-by-Step

This is the flow for `bug` and `anim`. `info` is a one-shot probe: it prints the video's properties and writes no directory and no `summary.md`.

1. **Pick a mode** — `bug` for what happened, `anim` for how something moves (see [Modes](#modes))
2. **Run the helper** — with `--out` pointing at a scratch location outside the repository
3. **Read `summary.md` first** — what was found, which files to open, and any warnings
4. **Read the contact sheets** — one read each; they are sized to stay small, and the summary estimates their image-token cost
5. **Read single frames only as needed** — each costs about as much as a whole sheet
6. **Read the data files** — `timeline.tsv` (bug) or `curve.tsv` and `fit.json` (anim), when exact values matter
7. **Report** — a bug as numbered steps citing time and frame, an animation as a duration and a named curve

## Modes

| Mode | Use it when | What it does |
|------|-------------|--------------|
| `info` | You only need the file's properties | Probes the video. Prints JSON (size, rotation, duration, frame rate, codec, audio, `creation_time`) to stdout and a one-line summary to stderr. Takes no options and writes no files |
| `bug` | You want to know what happened: a bug reproduced, a flow described | Picks the key screens — every screen that stayed up, brief flashes, samples of long motion — and writes them as frames, sheets and a timeline |
| `anim` | You want to know how something moves, usually to implement it | Finds each motion, measures its progress frame by frame, and fits named easing curves, a custom cubic-bezier and a spring |

For a bug *inside* an animation, run `bug` first to find the moment, then `anim --window START-END` around it.

## Options

Every flag below appears in the helper's `<mode> --help`. Times are in seconds of the recording.

### Shared by `bug` and `anim`

These do not apply to `info`.

| Flag | Default | Effect |
|------|---------|--------|
| `--out DIR` | `$TMPDIR/video-prep/<name>-<mode>` | Output directory (see [Output layout](#output-layout)) |
| `--crop-top PX` | 0 | Ignore this many pixels at the top (status bar) when detecting change |
| `--crop-bottom PX` | 0 | Ignore this many pixels at the bottom (navigation bar) |
| `--roi X,Y,W,H` | — | Analyse only this region instead |
| `--range START-END` | whole video | Analyse only this span, e.g. `3-9.5` |
| `--decimate OPTS` | ffmpeg defaults | Change-detection sensitivity, passed to ffmpeg's `mpdecimate`, e.g. `hi=256:lo=128:frac=0.1` |

`--roi` takes source pixels in display orientation (after any rotation), and takes precedence over `--crop-top` / `--crop-bottom`. The summary prints the factor between saved-frame and source coordinates, so you can read a region off a frame and convert it.

### `bug` only

| Flag | Default | Effect |
|------|---------|--------|
| `--min-dwell S` | 0.4 | A screen shown at least this long is a `state` pick |
| `--interval S` | 1.0 | During continuous change, one `motion` pick per this many seconds |
| `--brief-max S` | 0.12 | A change over within this long is a `brief` pick (flash, glitch, very quick transition) |
| `--max-frames N` | 40 | Cap on picks; extra picks are dropped and reported |
| `--per-sheet N` | 8 | Frames per contact sheet |
| `--view-size PX` | 1000 | Long edge of saved frames |
| `--extract-audio` | off | Also write a 16 kHz mono `audio.wav` when the audio track is not silent |

### `anim` only

| Flag | Default | Effect |
|------|---------|--------|
| `--window START-END` | — | Analyse exactly this span as one motion; its first frame must be still before the motion and its last frame still after it |
| `--time-scale N` | 1 | The recording was made with animations slowed N× (see [Time basis](#time-basis-under---time-scale)) |
| `--signal auto\|edge\|blend` | `auto` | Which progress signal to fit. `curve.tsv` has a column for each, but `p_edge` is blank when no moving edge can be tracked (fades, cross-fades) |
| `--gap S` | 0.12 | A pause longer than this splits motion segments |
| `--pad S` | 0.25 | Seconds of context decoded around each segment |
| `--min-frames N` | 2 | Segments with fewer changed frames are listed as cuts, not analysed |
| `--max-segments N` | 8 | Cap on analysed segments; later ones are skipped and reported |
| `--max-view-frames N` | 30 | Sampling target for saved frames per segment. Long segments are thinned evenly to about this many, plus the boundary frames that are always kept (the first and last frames shown, and the first and last moving frames with their neighbours), so a segment can save a few more |
| `--per-sheet N` | 30 | Frames per contact sheet |
| `--view-size PX` | 800 | Long edge of saved frames |
| `--analysis-pixels N` | 160000 | Pixel budget per frame for measuring (more is finer and slower) |

## Output layout

Every `bug` and `anim` run writes a directory and prints its summary path as the last line of stdout: `SUMMARY: <path>`.

The default location is `$TMPDIR/video-prep/<name>-<mode>` (`/tmp/video-prep/…` when `TMPDIR` is unset), where `<name>` is the video's file name without extension. `--out` overrides it. An existing non-empty directory is never overwritten: the helper writes to `<dir>-2`, `<dir>-3`, and so on instead.

**`bug`:**

```
<out>/
├── summary.md          # read first: findings, files to open, warnings
├── run.json            # options and probed video properties
├── timeline.tsv        # idx, time_s, shown_for_s, why, file
├── sheet_01.png …      # labelled contact sheets (needs ImageMagick)
├── frames/01_0.000s.png …   # one full-screen frame per pick
└── audio.wav           # only with --extract-audio and a non-silent track
```

**`anim`:**

```
<out>/
├── summary.md          # read first: one row per segment, fits, warnings
├── run.json
└── s01/ … (or w01/ with --window)
    ├── frames/f013_0.483s.png …   # the motion plus two frames of context
    ├── sheet_01.png …             # labelled contact sheets (needs ImageMagick)
    ├── curve.tsv       # every decoded frame: progress signals, bounding boxes
    ├── fit.json        # kind, durations, travel, overshoot, all fits, warnings
    └── plot.png        # measured progress with the best fits (plot.svg without ImageMagick)
```

`anim` frames show the analysed region (after `--roi` or the crop flags). `bug` frames always show the full screen, because the status bar can matter to a bug report even when it is excluded from change detection.

### Time basis under `--time-scale`

`--time-scale N` converts the numbers you implement into real time. Everything that locates a moment *in the recording* stays in recording time, so you can find it in the video and pass it back as `--window` or `--range`.

| Converted to real time (÷ N; spring stiffness × N²) | Left in recording time |
|---|---|
| `summary.md`: the visible duration and its ± frame interval in the segment table, the result after `->` on the "visible change" line, and every fit row (tween duration, spring settle time, stiffness, Compose preset, SwiftUI response) | `summary.md`: the "starts" column, the window in each segment heading, the first-changed and settled timestamps and the frame interval on the "visible change" line, and the cut times |
| `fit.json`: `visible_duration_ms` and every `fits[]` entry (`duration_ms`, spring parameters, `compose`, `swiftui_response_s`) | `fit.json`: `window_s`, `frame_interval_ms` |
| Sheet labels: the second line, the ± ms offset from the motion start | Sheet labels: the first line, the `<t>s` timestamp |
| The plot's time axis ("ms since fitted start (real time, /N)") | `curve.tsv`: both `time_s` and `t_rel_ms` |
| | Frame file names (`f013_0.483s.png`), and the `--window` / `--range` values you pass |

Implement the converted numbers; choose `--window` and `--range` spans from the recording-time ones. The [animation walkthrough]({{< relref "/docs/workflows/screen-recordings/animation" >}}#slowed-capture) has a worked example.

## Warnings and limits

Each line below is printed in `summary.md` (anim warnings also appear in `fit.json`), or on stderr for errors.

| Mode | What you see | What it means | What to do |
|------|--------------|---------------|------------|
| bug | `Warning: N picks were dropped. Narrow with --range, …` | More picks than `--max-frames`; motion samples went first, then brief picks, then the shortest-lived states | Narrow with `--range`, or raise `--interval` / `--min-dwell`, rather than raising `--max-frames` |
| bug | `Nothing on screen changed in the analysed region.` | No visible change was detected | Check `--range` and the crop flags; for a small change, a more sensitive `--decimate` |
| bug | ``(no sheets: ImageMagick `magick` not found; read frames/ directly)`` | ImageMagick is not installed. In `anim` the sheets are simply absent from each segment's file list | Read `frames/` directly, or install ImageMagick 7 |
| anim | `travel estimate varies by N% across frames: …` | More than one thing moves, or a fade is combined with the move | Rerun with `--roi` around the one element |
| anim | `the change covers almost the whole region (full-screen transition?): …` | A full-screen push or slide; the timing is reliable, the curve shape is only a proxy unless it is a cross-fade | `--roi` on a strip only the incoming edge crosses |
| anim | `the picture returns to where it started (press feedback, shake, ripple?): …` | The motion ends where it began; there is no progress curve | Read the sheet; the visible duration is still given |
| anim | `no edge motion found; falling back to the blend signal` | `--signal edge` was requested but no moving edge was found | Use the blend fit, or isolate the element with `--roi` |
| anim | `note: video starts mid-motion: …` | The recording starts during the motion, so progress is relative to frame 0 | Re-record with a still second before the animation |
| anim | `N later segments skipped (--max-segments N)` | More motion segments than the cap | Narrow with `--range`, or raise `--max-segments` |
| anim | `fewer than 3 frames in the window` (segment table) | The segment or `--window` is too short to measure | Widen `--window`, or check the frame rate |
| anim | `single-frame changes (instant cuts, clock ticks, cursor blinks; not analysed)` | Changes lasting one frame are listed, not measured | Usually noise; crop the status bar if they are clock ticks |
| anim | `nothing changed between the first and last frame of the window` | The `--window` span has no net change | Move the window onto the motion |

Other known limits:

- **Several elements animating at once** give a mixed curve. Run once per element with `--roi`.
- **A fade combined with movement** — fit `--signal blend` for the opacity, and `--roi` with `--signal edge` for the motion, and report both.
- **Low frame rate or dropped frames** (a large frame interval in the summary) make the timing coarser. Precision is ±1 frame: ±17 ms at 60 fps. A slowed capture with `--time-scale` gives proportionally more samples.
- **Tiny motion** (a few pixels) is quantised. A tight `--roi` raises the analysis resolution, and so does `--analysis-pixels 400000`.
- **Material 3 emphasized easing** is a path, not a cubic-bezier, so it cannot be fitted; expect it to land between M3 standard and the custom fit.
- **Image budgets.** Contact sheets are sized to stay under the size at which models commonly downscale an image, and the summary estimates their token cost. Each single frame costs about as much as a sheet, so read frames selectively.

## Requirements

- **ffmpeg and ffprobe 5.1 or later** on `PATH` — required. They are not installed by `ait setup`; install them with your system's package manager.
- **ImageMagick 7** (`magick`) — optional. Without it there are no contact sheets and the animation plot is written as `plot.svg` only; frames and data files are unaffected.
- The helper itself is Python standard library only and runs on the framework's interpreter.

## Privacy

Recordings often show personal data.

- Point `--out` at a scratch location outside the repository.
- Never copy the recording into the repository.
- The helper uploads nothing. The skill does not send a recording to any external service unless you explicitly agree for that file.

## Workflows

- [Screen Recordings]({{< relref "/docs/workflows/screen-recordings" >}}) — overview: choosing a mode, reading order, privacy
- [Bug Report from a Recording]({{< relref "/docs/workflows/screen-recordings/bug-report" >}})
- [Animation from a Prototype Recording]({{< relref "/docs/workflows/screen-recordings/animation" >}})
- [Recording Tips]({{< relref "/docs/workflows/screen-recordings/recording-tips" >}})

## Related

- [`/aitask-explore`]({{< relref "/docs/skills/aitask-explore" >}}) — investigate a bug you reconstructed from a recording, then create a task
- [`/aitask-create`]({{< relref "/docs/skills/aitask-create" >}}) — file a task directly from the report
- [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}) — implement the task, with the recording's frames and numbers as context
