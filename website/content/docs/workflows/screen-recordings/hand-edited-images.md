---
title: "Prepare Images by Hand, Then Feed Them to the Agent"
linkTitle: "Hand-Edited Images"
weight: 27
description: "Extract frames, crop, annotate or delete them in any tool, and hand the folder back as labelled contact sheets"
depth: [intermediate]
---

Sometimes the frames the agent should look at are best chosen by you. Perhaps only a corner of the screen matters, a circle around the glitch says more than a paragraph, or most frames of a span are noise. The flow has four steps: extract the frames, edit them in any image tool, turn the folder into labelled contact sheets with `sheet`, and let the agent read the sheets. The labels keep the timing: each one shows the frame's time and the time since the previous image, so a frame you deleted still shows up as a gap.

```
recording.mp4 ──▶ frames --range ──▶ frames/t<ms>.png ──▶ you: crop, annotate, delete
                                                                     │
                       agent reads ◀── sheet_01.png … ◀── sheet frames/
```

`sheet` works on any folder of png, jpg or webp images, not only on extracted frames. Images whose names carry no time are still drawn, after the others and without a time.

## 1. Extract

Write every frame of the span you care about at full resolution, or the frames on screen at a few times (see [Extract Exact Frames for Close Inspection]({{< relref "/docs/workflows/screen-recordings/exact-frames" >}})):

```bash
./.aitask-scripts/aitask_screen_recording.sh frames repro.mp4 --range 7-7.5 --out /tmp/video-prep/repro-frames
```

The frames land in `/tmp/video-prep/repro-frames/frames/`, named by their presentation time in milliseconds: `t00007040.png` is the frame at 7.040 s.

## 2. Edit

Open the frames in any tool and:

- **crop** to the part that matters;
- **annotate**: arrows, circles, a word of explanation;
- **delete** frames you do not need.

**Keep the time at the start of each file name.** Saving over the file keeps it. A "save as" copy may add a suffix, and that is fine: `t00007040_annotated.png`, `t00007040-crop.png` and `t00007040 (1).jpg` all still carry 7.040 s. The suffix must start with `_`, `-`, `.`, a space or `(`. The same holds for the names `bug` and `anim` write, such as `04_5.500s.png` and `f013_0.483s.png`. A renamed file such as `glitch.png` carries no time: it is still drawn, but last and without a time.

Leave `frames.tsv` in the folder. It does no harm, and `sheet` uses it to tell edited frames from untouched ones (step 4).

## 3. Build the sheets

```bash
./.aitask-scripts/aitask_screen_recording.sh sheet /tmp/video-prep/repro-frames/frames --out /tmp/video-prep/repro-sheet
```

`sheet` reads the folder's top level and writes `sheet_01.png`, `sheet_02.png` and so on, with `summary.md`, `tiles.tsv` and `run.json` beside them. `--per-sheet` (8 by default) sets the most images on one sheet. The last stdout line is `SUMMARY: <path>`; the line before it gives the sheets' approximate image-token cost. `sheet` needs ImageMagick 7 (`magick`) and no ffmpeg.

Images of different sizes, as cropping leaves them, are letterboxed into equal cells: each keeps its aspect ratio and is scaled to fit, never stretched.

## 4. Read the labels

Each tile carries two lines:

```
#4 t00007100_annotated.png
7.100 s +66 ms
```

- `#4` is the image's place in the order, and the file name follows. A name too long for its cell is shortened in the middle with `...`; `tiles.tsv` has the full name.
- `7.100 s` is the time the name carries.
- `+66 ms` is the time since the previous image with a time. At 60 fps consecutive frames are about 17 ms apart, so `+66 ms` means frames were deleted, or the screen stayed still in a variable-frame-rate recording. The value comes from the rounded milliseconds in the names, so it is accurate to ±1 ms.
- `first` replaces the `+` step on the first image with a time, and `no time in name` replaces the whole line for an image without one.
- `edited` is appended when the image no longer matches its SHA-256 in the folder's `frames.tsv`. Its pixels changed, so the recorded geometry (where its pixels came from in the recording) no longer applies. An untouched frame has no marker, and `tiles.tsv` records it as `match`. The match is by file name, so a renamed copy has no row and gets no marker either way.

The summary's **Gaps** section lists the steps over 1.5 times the median step. It is a hint, not a verdict: a gap is either frames you deleted, or a screen that held still.

## 5. Hand it to the agent

Point the agent at the summary, or let the skill run `sheet` itself when you tell it where the folder is. The agent reads `summary.md` first, then the sheets, and cites tiles as `#4 at 7.100 s`. When it needs one image in detail, it reads that file directly. The file is full resolution and costs more, as [step 3 of the exact-frames walkthrough]({{< relref "/docs/workflows/screen-recordings/exact-frames" >}}#3-check-the-cost-before-reading) explains.

## What the summary warns about

- **Images with no time in their names.** They come last, in name order, labelled by index.
- **Names of different kinds** (`t…`, `NN_…s`, `f…_…s`). Fine when they come from one recording.
- **Images that could not be read.** They are left out and listed, and the `+` steps skip them.
- **Animated images.** Only their first frame is drawn.
- **Ignored entries.** Hidden files, subfolders and non-image files.
- **Fewer images on a sheet than `--per-sheet`.** Every cell is made wide enough for its label, so a long label can leave room for fewer images on a sheet. The images then go onto more sheets; none is dropped.

## Reference

Every option, the output layout and the `tiles.tsv` columns are on the [skill page]({{< relref "/docs/skills/aitask-screen-recording" >}}#sheet).
