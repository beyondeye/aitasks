---
title: "Extract Exact Frames for Close Inspection"
linkTitle: "Exact Frames"
weight: 25
description: "Write the exact native frames of a moment at full resolution, with a manifest that records where each image came from"
depth: [intermediate]
---

`bug` and `anim` save a few downscaled frames chosen for you, which is right for reading a whole recording. Sometimes you need the opposite: one exact moment at full resolution, to read small text or check a few pixels. Or you want every frame of a short span, to crop, annotate or delete by hand before handing them back to the agent. `frames` does that. It writes exact native frames from the recording, named by their presentation time, and adds a manifest that records where each image came from.

## 1. Find the moment

Start with `bug` or `anim`. Their summaries cite times: a pick at `5.500 s`, a black interval at `5.000 s`, a segment window. An `anim` summary may already give the command. When a segment's saved frames were thinned, its line ends with `every native frame at full resolution: frames <video> --range A-B`.

## 2. Extract

The frame on screen at one or more times:

```bash
./.aitask-scripts/aitask_screen_recording.sh frames repro.mp4 --at 5.5,7.04 --out /tmp/video-prep/repro-frames
```

Every frame of a span:

```bash
./.aitask-scripts/aitask_screen_recording.sh frames repro.mp4 --range 7-7.5 --out /tmp/video-prep/repro-frames
```

- `--at T` writes the frame on screen at T: the latest frame presented at or before it. Several times that land on the same frame give one file. A time before the first frame is an error, and so is a time at or after the end of the video's last frame when the video proves where that end is. When it cannot (a raw stream without timestamps, for example), the frame is still written, and the summary and `run.json` mark it as not proven to be on screen.
- `--range A-B` writes every native frame presented from A up to, but not including, B. Frames are decoded with `-fps_mode passthrough`, so none is dropped or repeated. A variable-frame-rate recording, as Android's screen recorder writes, has no frames while the screen is still. A range inside such a stretch is an error whose message points to `--at A`, the picture on screen at A.
- `--roi X,Y,W,H`, or `--crop-top` / `--crop-bottom`, crops the written images to the part that matters. The box is in source pixels, in display orientation, and it is honoured exactly, odd offsets and sizes included. In `bug` the same flags only change what change detection looks at; here they change the images.

Files land in `<out>/frames/` as `t<ms>.png`: `t00007040.png` is the frame presented at 7.040 s. The time comes from the frame's own timestamp (pts × the stream's time base), never from its position times the frame rate, so a variable-frame-rate recording is named correctly. The millisecond is rounded to the nearest one, and the times in the summary are rounded too. Selection, though, compares exact times. A rounded time passed back as `--at` can therefore pick the neighbouring frame: `t00000033.png` is the frame at 33.33 ms, and `--at 0.033` selects the frame before it. To get a particular frame, give a time that clearly falls inside its interval on screen.

## 3. Check the cost before reading

Full-resolution frames are expensive to read. `summary.md`, and a line on stdout, give each frame's cost in image tokens (about ⌈width / 28⌉ × ⌈height / 28⌉) and the total. They warn when a frame crosses a limit:

| Warning | What it means |
|---------|---------------|
| over the standard tier's limit (1568 px, 1568 tokens) | Claude models before Claude 4.7 see a downscaled frame |
| over the high-resolution tier's limit too (2576 px, 4784 tokens) | Every model sees a downscaled frame |
| over 3000 px on a side | A request carrying more than 20 images rejects it. Earlier images in the conversation count |

A 1080×2400 phone frame is about 3354 tokens: several times a contact sheet, and downscaled on the standard tier. Read only the frames you need, and crop with `--roi` to the detail that matters. A cropped frame is cheaper and keeps its full sharpness.

## 4. Read `frames.tsv`

`frames/frames.tsv` has one row per image. It records the image's time (`t_ms`, rounded, as in the name) and its exact `pts`, and where its pixels came from:

- `src_w × src_h`, the source size;
- the crop box `crop_x`, `crop_y`, `crop_w`, `crop_h`;
- `out_w × out_h`, the written size, read from the file;
- the scale, `out / crop`.

It also records the image's `sha256`.

A point in the image maps back to the source as `crop_x + x / scale_x`, and the same for y. That is how a region you read off a frame becomes a `--roi` for another run. `bug` and `anim` write the same manifest beside the frames they save. Their frames are downscaled, so their scale is below 1.

**The geometry is valid only for an unedited frame.** It describes the file whose hash is `sha256`. Once you crop, resize, annotate or otherwise edit a frame, its hash no longer matches and its geometry is unknown. The frame is still fine to look at, but nothing should map its pixels back to the source through this record. Keep the file name unchanged when you edit a frame, so its time stays readable from it.

## 5. Past the cap

`--max-frames` (60 by default, one second at 60 fps) caps how many frames one run writes. It keeps the earliest ones and never thins, so what was written is still every native frame from the start of the range. The summary then says how many frames were left out and over which span, and gives the `--range` that continues. That range starts strictly after the last frame written and no later than the first one left out, so following the hints run after run writes each frame exactly once. `run.json` sets `cap_hit` and records `omitted`. Narrow the range or run the continuation, rather than raising the cap and reading everything at once.

## Recordings that change size

A video stream can change its frame size partway through. ffmpeg would then rescale the later frames to the first one's size, so `frames` refuses any request that includes a frame of another size than the probed one. Frames from before the change still work. `bug` and `anim` run on such recordings but write no `frames.tsv`, and their summaries say why.

## Reference

Every flag, the full output layout and the `frames.tsv` columns are on the [skill page]({{< relref "/docs/skills/aitask-screen-recording" >}}#frames).
