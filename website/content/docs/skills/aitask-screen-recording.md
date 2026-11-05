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
./.aitask-scripts/aitask_screen_recording.sh frames VIDEO (--range START-END | --at T[,T...]) [options]
./.aitask-scripts/aitask_screen_recording.sh <mode> --help
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

For end-to-end walkthroughs of the two use cases, see the [Screen Recordings workflow]({{< relref "/docs/workflows/screen-recordings" >}}).

## Step-by-Step

This is the flow for `bug` and `anim`. `info` is a one-shot probe: it prints the video's properties and writes no directory and no `summary.md`. `frames` is the drill-down once you know the moment: it writes exact native frames at full resolution (see [Frames](#frames)).

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
| `bug` | You want to know what happened: a bug reproduced, a flow described | Picks the key screens — every screen that stayed up, brief flashes, samples of long motion — and writes them as frames, sheets and a timeline. Also lists every freeze, black interval and silent gap the ffmpeg detectors find, with a frame for each black interval |
| `anim` | You want to know how something moves, usually to implement it | Finds each motion, measures its progress frame by frame, and fits named easing curves, a custom cubic-bezier and a spring |
| `frames` | You want a close look at an exact moment, or frames to edit by hand and hand back | Writes every native frame of a range, or the frame on screen at given times, at full resolution, named by each frame's presentation time, with a `frames.tsv` manifest of their geometry |

For a bug *inside* an animation, run `bug` first to find the moment, then `anim --window START-END` around it. For detail too small to read in a sheet, run `frames --at T` at the time `bug` or `anim` reported.

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
| `--max-frames N` | 40 | Cap on picks; extra picks are dropped and reported. Black frames rank below the first and last frame and above every other pick |
| `--per-sheet N` | 8 | Frames per contact sheet |
| `--view-size PX` | 1000 | Long edge of saved frames |
| `--extract-audio` | off | Also write a 16 kHz mono `audio.wav` when the audio track is not silent |
| `--freeze-min S` | 2 | No visible change for this long is a `freeze` row |
| `--black-min S` | 0 | Shortest black run to report; `0` reports every black frame. A run whose end was not observed is always reported |

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

### `frames`

`frames` takes its own set of flags; it shares none of `bug`'s or `anim`'s analysis options. Exactly one of `--range` and `--at` is required.

| Flag | Default | Effect |
|------|---------|--------|
| `--range START-END` | — | Every native frame presented from START up to, not including, END, e.g. `7-7.5`. Decoded with `-fps_mode passthrough`, so no frame is dropped or repeated |
| `--at T[,T...]` | — | The frame on screen at each time: the latest frame presented at or before it. Times that land on the same frame give one file |
| `--roi X,Y,W,H` | — | Write only this region, in source pixels in display orientation |
| `--crop-top PX` | 0 | Cut this many pixels off the top of the written frames |
| `--crop-bottom PX` | 0 | Cut this many pixels off the bottom |
| `--max-frames N` | 60 | Write at most this many frames, the earliest; the rest are reported with the `--range` that continues |
| `--out DIR` | `$TMPDIR/video-prep/<name>-frames` | Output directory |

In `frames` the crop flags crop the *written image*. In `bug` the same flags only change what change detection looks at; `bug` frames always show the full screen. Frames are written at full resolution (scale 1).

Selection compares each frame's exact presentation time (pts × the stream's time base) with the requested times. The milliseconds in a file name, and every time the summary prints, are rounded, so they are labels rather than selectors: a rounded time passed back as `--at` can select the neighbouring frame.

## Output layout

Every `bug` and `anim` run writes a directory and prints its summary path as the last line of stdout: `SUMMARY: <path>`.

The default location is `$TMPDIR/video-prep/<name>-<mode>` (`/tmp/video-prep/…` when `TMPDIR` is unset), where `<name>` is the video's file name without extension. `--out` overrides it. An existing non-empty directory is never overwritten: the helper writes to `<dir>-2`, `<dir>-3`, and so on instead.

**`bug`:**

```
<out>/
├── summary.md          # read first: findings, files to open, warnings
├── run.json            # options, probed video, intervals, video end, cap_hit
├── timeline.tsv        # idx, time_s, shown_for_s, why, file, kind, end_s
├── sheet_01.png …      # labelled contact sheets (needs ImageMagick)
├── frames/01_0.000s.png …   # one full-screen frame per pick
├── frames/frames.tsv   # time, pts, geometry and SHA-256 of each frame (see frames.tsv)
└── audio.wav           # only with --extract-audio and a non-silent track
```

`timeline.tsv` has two kinds of row, told apart by `kind`:

- **`frame`** — one picked frame. `shown_for_s` is how long the picture stayed until the next visible change. For a black frame that mpdecimate dropped as a near-duplicate of the frame before it, `shown_for_s` is the black run's duration from blackdetect instead, and it is empty when that run's end was not observed.
- **`freeze` / `black` / `silence`** — one detected interval. `time_s` is the start and `end_s` the end. `why` names the detector and its settings, and notes when the end was not observed (then `end_s` is a lower bound) or when a black interval got no image. `file` is a black interval's frame.

`run.json` repeats the intervals under `intervals` (`start_s`, `end_s`, `end_observed`, `duration_s`, `frame_time_s`, `file`). Alongside them it records `detectors`, `video_end_s` / `video_end_proven` (the end of the analysed video span, from the video stream's own packets), `cap_hit` (`--max-frames` removed at least one pick), `black_images_omitted` and `manifest` (the path of `frames/frames.tsv`).

**`anim`:**

```
<out>/
├── summary.md          # read first: one row per segment, fits, warnings
├── run.json            # options, probed video, segments, cuts, cap_hit, caps
└── s01/ … (or w01/ with --window)
    ├── frames/f013_0.483s.png …   # the motion plus two frames of context
    ├── frames/frames.tsv          # time, pts, geometry and SHA-256 of each frame
    ├── sheet_01.png …             # labelled contact sheets (needs ImageMagick)
    ├── curve.tsv       # every decoded frame: progress signals, bounding boxes
    ├── fit.json        # kind, durations, travel, overshoot, all fits, warnings
    └── plot.png        # measured progress with the best fits (plot.svg without ImageMagick)
```

`anim` frames show the analysed region (after `--roi` or the crop flags). `bug` frames always show the full screen, because the status bar can matter to a bug report even when it is excluded from change detection.

`anim`'s `run.json` sets `cap_hit` when a cap left something out, with the details under `caps`:

- `max_segments`: `limit`, how many segments were `skipped`, and `first_skipped_s`, the start of the first skipped one;
- `max_view_frames`: `limit` and `thinned`, one entry per segment whose saved frames were thinned, with how many were `saved`, `of` how many, and the `range` to pass to `frames --range` for every native frame of it.

The summary names a thinned segment on its own line and gives that `frames` command, with the run's region flags.

**`frames`:**

```
<out>/
├── summary.md          # read first: the request, the image budget, the frames, the geometry
├── run.json            # options, probed video, cap_hit, omitted, image_budget, requested (--at)
└── frames/
    ├── t00007040.png … # one full-resolution frame each, named by its time in ms
    └── frames.tsv      # time, pts, geometry and SHA-256 of each frame
```

A file name carries the frame's presentation time in integer milliseconds, rounded to the nearest one: `t00007040.png` is the frame presented at 7.040 s. With `--at`, `run.json` lists each requested time under `requested`: the `frame_t_s` it resolved to, the `file`, `on_screen_proven` and, when that is false, `unproven_because`. A frame is proven to be on screen at T when a later frame exists, or when T falls inside the frame's own duration; that duration's end is exclusive. A time at or past the end of the last frame is an error only when the video's packets prove that frame is the last one. When ffmpeg reports no frame durations (5.1 does not), the end comes from the video's packets, which give it to 6 decimals, so a time within 2 µs of it is left unproven rather than decided. When they cannot (a raw stream without timestamps, for example), the frame is written and labelled unproven instead. `cap_hit` is set when `--max-frames` left frames out; `omitted`, `omitted_from_s` and `omitted_to_s` say which.

A recording whose frame size changes partway through is refused by `frames` when any requested frame has a size other than the probed one: ffmpeg would rescale those frames to the first frame's size, so neither their pixels nor their geometry would be true. `bug` and `anim` still run on such a recording, but write no `frames.tsv` and say why (see [Warnings and limits](#warnings-and-limits)).

### `frames.tsv`

Every `frames/` directory, in `bug`, `anim` and `frames` alike, carries a `frames.tsv` with one row per image:

| Column | Meaning |
|--------|---------|
| `file` | The image's file name, in the same directory |
| `t_ms` | Its presentation time, rounded to the nearest millisecond, the same value the file name carries |
| `pts` | Its presentation timestamp in the stream's time base, exact |
| `time_source` | `pts*time_base` when the time was computed from the time base ffmpeg reported, or `pts_time` when it came from ffmpeg's printed time instead (older ffmpeg versions print too few digits for millisecond precision past 1000 s) |
| `src_w`, `src_h` | The source video's size in display orientation, the pixels `--roi` takes |
| `crop_x`, `crop_y`, `crop_w`, `crop_h` | The region of the source the image shows |
| `out_w`, `out_h` | The image's size, read from the file |
| `scale_x`, `scale_y` | `out / crop`: 1 for `frames`, below 1 when `bug` or `anim` downscaled the frame |
| `sha256` | The SHA-256 of the image as written |

To map a point in the image back to the source: source x = `crop_x` + image x / `scale_x`, and the same for y.

**The geometry is valid only for an unedited image.** It describes the file whose hash is `sha256`. Once a frame is cropped, resized, annotated or otherwise edited, its hash changes and its geometry is unknown. A tool that maps points through this record must check the hash first.

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
| bug | `Warning: N picks were dropped. Narrow with --range, …` | More picks than `--max-frames`; motion samples went first, then brief picks, then the shortest-lived states, then black frames | Narrow with `--range`, or raise `--interval` / `--min-dwell`, rather than raising `--max-frames` |
| bug | `Warning: N black intervals have no image (--max-frames M reached). …` | More black intervals than the budget leaves room for. Every interval keeps its row in `summary.md` and `timeline.tsv`; only the image is missing | Run again with `--range` around the listed times to see their frames |
| bug | `Nothing on screen changed in the analysed region.` | No visible change was detected by mpdecimate. The triage rows may still list black frames it treated as duplicates | Check `--range` and the crop flags; for a small change, a more sensitive `--decimate` |
| bug | `video end from container duration (not proven): …` | The end of the video stream could not be read from its packets (unknown last-frame duration, missing timestamps, or an unconfirmed timeline origin) | Intervals still going at the end are reported with the last frame as their lower bound; treat their durations as approximate |
| bug | ``(no sheets: ImageMagick `magick` not found; read frames/ directly)`` | ImageMagick is not installed. In `anim` the sheets are simply absent from each segment's file list | Read `frames/` directly, or install ImageMagick 7 |
| anim | `travel estimate varies by N% across frames: …` | More than one thing moves, or a fade is combined with the move | Rerun with `--roi` around the one element |
| anim | `the change covers almost the whole region (full-screen transition?): …` | A full-screen push or slide; the timing is reliable, the curve shape is only a proxy unless it is a cross-fade | `--roi` on a strip only the incoming edge crosses |
| anim | `the picture returns to where it started (press feedback, shake, ripple?): …` | The motion ends where it began; there is no progress curve | Read the sheet; the visible duration is still given |
| anim | `no edge motion found; falling back to the blend signal` | `--signal edge` was requested but no moving edge was found | Use the blend fit, or isolate the element with `--roi` |
| anim | `note: video starts mid-motion: …` | The recording starts during the motion, so progress is relative to frame 0 | Re-record with a still second before the animation |
| anim | `N later segments skipped (--max-segments N; the first starts at T s): …` | More motion segments than the cap | Narrow with `--range`, or raise `--max-segments` |
| anim | `saved frames: N of M (thinned by --max-view-frames K); every native frame at full resolution: frames … --range A-B` | The segment's saved frames and sheet skip frames | Run the `frames` command the line gives |
| frames | `Warning: --max-frames N reached: K more frames presented from A s to B s were not written. Continue with --range …` | The range has more frames than the cap; the earliest N were written. The continuation starts strictly after the last written frame and no later than the first omitted one, so repeating it never writes a frame twice or skips one | Run the `--range` it gives for the rest, or narrow the range. When no decimal with up to 9 places fits between the two frames, the warning says so and suggests raising `--max-frames` |
| frames | `the frame at T s is WxH, but the video was probed as W0xH0: the frame size changes mid-stream …` (error) | A requested frame has another size than the probed one, and ffmpeg would rescale it | Request frames from before the change; later ones are not supported |
| bug, anim | `no frames/frames.tsv (no geometry is recorded): … the frame size changes mid-stream …` | The saved frames include one of another size, so their geometry cannot be recorded; `run.json` has `manifest: null` and the reason in `manifest_note` (anim: in the segment's warnings) | Treat those frames as possibly rescaled |
| frames | `Warning: each frame is over the standard tier's limit (long edge 1568 px, 1568 visual tokens): …` | Models before Claude 4.7 see the frame downscaled | Crop to the detail with `--roi` |
| frames | `Warning: each frame is over the high-resolution tier's limit too (long edge 2576 px, 4784 visual tokens): …` | Every model sees the frame downscaled | Crop with `--roi` |
| frames | `Warning: frames are over 3000 px on a side: …` | A request that carries more than 20 images, counting earlier images in the conversation, rejects them | Crop with `--roi`, or read only a few |
| frames | `no frame is presented in A-B s …` (error) | Nothing was presented in the range; a variable-frame-rate recording writes no frames while the screen is still | `--at A` gives the picture on screen at A |
| frames | `--at T is past the video end: the last frame is presented at A s until B s` (error; `(from the video's packets)` when ffmpeg reported no frame durations) | The video's packets prove the last frame, and T is at or after its end | Use a time before B |
| frames | `on screen at T s not proven: …` (frames table) | Nothing proves the video goes on to T: the last frame's duration is unknown, or whether a later frame exists is not known | The frame is the last one presented at or before T; check the recording's real length before relying on it |
| anim | `fewer than 3 frames in the window` (segment table) | The segment or `--window` is too short to measure | Widen `--window`, or check the frame rate |
| anim | `single-frame changes (instant cuts, clock ticks, cursor blinks; not analysed)` | Changes lasting one frame are listed, not measured | Usually noise; crop the status bar if they are clock ticks |
| anim | `nothing changed between the first and last frame of the window` | The `--window` span has no net change | Move the window onto the motion |

Other known limits:

- **Several video tracks in one file:** only one is analysed, the default-disposition track, or the first when none is marked default. The summary's video line names it (`video stream #N of M`).
- **Several elements animating at once** give a mixed curve. Run once per element with `--roi`.
- **A fade combined with movement** — fit `--signal blend` for the opacity, and `--roi` with `--signal edge` for the motion, and report both.
- **Low frame rate or dropped frames** (a large frame interval in the summary) make the timing coarser. Precision is ±1 frame: ±17 ms at 60 fps. A slowed capture with `--time-scale` gives proportionally more samples.
- **Tiny motion** (a few pixels) is quantised. A tight `--roi` raises the analysis resolution, and so does `--analysis-pixels 400000`.
- **Material 3 emphasized easing** is a path, not a cubic-bezier, so it cannot be fitted; expect it to land between M3 standard and the custom fit.
- **Image budgets.** An image costs about ⌈width / 28⌉ × ⌈height / 28⌉ visual tokens. Claude models before Claude 4.7 downscale an image whose long edge is over 1568 px or whose cost is over 1568 tokens. Claude 4.7 and later models downscale above 2576 px or 4784 tokens. A request that carries more than 20 images rejects any image over 3000 px on a side. Contact sheets are sized to stay under the standard limits, and the summary estimates their token cost. A `bug` or `anim` frame costs about as much as a sheet. A full-resolution `frames` frame can cost far more: a 1080×2400 phone frame is about 3354 tokens, and the summary warns about each limit it crosses. Read frames selectively, and crop with `--roi`.

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
- [Spot a Hang, a Black Flash or a Silent Gap]({{< relref "/docs/workflows/screen-recordings/hang-black-silence" >}})
- [Animation from a Prototype Recording]({{< relref "/docs/workflows/screen-recordings/animation" >}})
- [Extract Exact Frames for Close Inspection]({{< relref "/docs/workflows/screen-recordings/exact-frames" >}})
- [Recording Tips]({{< relref "/docs/workflows/screen-recordings/recording-tips" >}})

## Related

- [`/aitask-explore`]({{< relref "/docs/skills/aitask-explore" >}}) — investigate a bug you reconstructed from a recording, then create a task
- [`/aitask-create`]({{< relref "/docs/skills/aitask-create" >}}) — file a task directly from the report
- [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}) — implement the task, with the recording's frames and numbers as context
