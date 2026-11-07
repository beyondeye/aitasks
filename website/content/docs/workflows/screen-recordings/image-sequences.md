---
title: "Review or Measure a Curated Image Sequence"
linkTitle: "Curated Image Sequences"
weight: 29
description: "Run the bug review or the animation measurement on a folder of images you extracted and curated, instead of the recording"
depth: [intermediate]
---

Sometimes the recording itself is not what you want the agent to analyse. A span may hold frames that are only noise, a few frames may need retouching, or all you have is a set of screenshots. `bug` and `anim` then take a **folder of images** in place of the video and run the same analysis on it: key screens and freeze/black rows for `bug`, measured timing and fitted easing for `anim`. The times come from the image names, so the results stay in the recording's time.

```
recording.mp4 ──▶ frames --range ──▶ frames/t<ms>.png ──▶ you: delete, retouch
                                                                   │
            summary.md, sheets, fits ◀── bug|anim frames/ ◀────────┘
```

Use it when:

- you want the review or the measurement to see **only the frames you kept**;
- you have **screenshots** without a recording, named by time or taken at a known rate;
- you edited frames by hand and want a measurement of the edited sequence rather than of the original.

To look at the images yourself, as contact sheets, see [Prepare Images by Hand, Then Feed Them to the Agent]({{< relref "/docs/workflows/screen-recordings/hand-edited-images" >}}) instead.

## 1. Extract and curate

Write every frame of the span you care about (see [Extract Exact Frames for Close Inspection]({{< relref "/docs/workflows/screen-recordings/exact-frames" >}})):

```bash
./.aitask-scripts/aitask_screen_recording.sh frames prototype.mp4 --range 0.3-1.1 --max-frames 200 --out /tmp/video-prep/proto-frames
```

`frames` writes at most 60 frames unless `--max-frames` says otherwise, so raise it for spans longer than a second at 60 fps.

Then delete, crop or retouch frames in the `frames/` folder. Keep the time at the start of each name: `t00000517.png`, or `t00000517_retouched.png` for a "save as" copy. Leave `frames.tsv` where it is; it is ignored.

## 2. Run `bug` or `anim` on the folder

```bash
./.aitask-scripts/aitask_screen_recording.sh anim /tmp/video-prep/proto-frames/frames --out /tmp/video-prep/proto-anim
./.aitask-scripts/aitask_screen_recording.sh bug  /tmp/video-prep/proto-frames/frames --out /tmp/video-prep/proto-bug
```

Every other option works as it does for a recording: `--window`, `--range` and `--roi` take the same recording-time seconds and source pixels. The summary's first line describes the input:

```
- input: 48 images in /tmp/video-prep/proto-frames/frames (png), 360x800, 0.300-1.083 s, times from the file names (1 ms resolution); frame interval about 16.7 ms (the last image is assumed shown for one interval); audio: none
```

## How the timing is derived

- **From the names.** Each image is placed at the time its name carries, to the millisecond. Every name in the folder must carry one; a folder where only some do, or where two images claim the same time, is refused with the names listed.
- **From `--fps N`**, for images whose names carry no time, such as `shot1.png`, `shot2.png`, …: they are taken in natural name order (`shot2` before `shot10`) at N per second. That timing is an assumption, and the summary says `timing assumed from --fps N, not measured`.
- **The last image** has no duration of its own. It is assumed to stay on screen for one frame interval.
- **The frame interval** is estimated from the shortest steps between images, so it stays the native interval even when many frames are gone.

## What the gap warning means

A step between two images longer than 1.5 times the frame interval is a **gap**. The `anim` summary lists where the gaps are:

```
- warning: 15 gap(s) in the sequence, steps longer than 1.5 x the 17.0 ms frame interval (heuristic: frames may be missing, deleted or never emitted while the screen was still); timing is not native-frame accurate there: after t00000317.png at 0.317 s, step 33 ms (about 1 missing); …
```

It is a hint, not a verdict. A gap is either frames that were deleted, or a still screen in a variable-frame-rate recording, which emits no frames while nothing changes. When every second frame is gone, the sequence looks like a recording at half the rate, and no gap is reported.

Missing frames make the measured timing coarser, and the summary says how much:

- **At the motion's ends.** When the first changed image or the settled image follows a gap, the motion began or ended somewhere inside that step. The visible duration's ± grows to cover it, for example `300 ms (±33)`, with a line saying which step widened it. `fit.json` has the same value as `visible_duration_uncertainty_ms`.
- **Inside the motion.** Gaps there leave fewer points for the fit. The summary counts them, and the fit is less constrained there.
- **Just before the motion, further back than the fitter looks.** The fitter searches for the motion's start up to 8 frame intervals before the first changed image. When more than that is missing, a fitted duration can come out too short and still look like a close fit. The segment table then shows `unreliable (gap before the motion)` instead of the best fit, the summary says why, and `fit.json` has `fits_reliable: false`. Use the visible duration and its ± instead, or extract the span again without deleting frames there.

## Mixed sizes and formats

- `anim` measures one geometry, so it needs images of one size. It stops and lists the images whose size differs from most of the others.
- `bug` only reviews, so it accepts mixed sizes. It letterboxes them, unscaled and centred, onto a canvas as large as the largest width and height, padded in mid-grey. The padding is part of what change and black detection see, so a black image on a large canvas may not count as black. A letterboxed run records no geometry (`frames.tsv`), and refuses `--roi` and the crop flags.
- Images that decode to different pixel formats, such as gray and RGB PNGs, are converted to one format before the analysis, so the detectors see one uninterrupted stream. The summary says when this happened.

## Reference

Every flag, the `run.json` fields of an image-folder run and the exact warning strings are on the [skill page]({{< relref "/docs/skills/aitask-screen-recording" >}}#image-folder-input).
