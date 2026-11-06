---
title: "Pick Frames Visually and Hand Them to the Agent"
linkTitle: "Pick Frames Visually"
weight: 28
description: "Choose the frames that matter on a page in your browser, mark a span or a region, and paste the selection back to the agent"
depth: [intermediate]
---

An extraction often writes more frames than matter. You can usually tell at a glance which ones show the glitch, or where an animation really starts. `pick` turns a run's frames into a page in your browser. You click the frames that matter, optionally mark a start and an end frame or drag a rectangle, press **Copy**, and paste the text back to the agent. The agent then reads exactly those frames.

```
bug / anim / frames run ──▶ pick --open ──▶ index.html in your browser
                                                  │  click, shift-click, s / e, drag
       agent reads the listed frames ◀── paste ◀──┘  Copy
```

The page is a single file with no server behind it. Nothing is uploaded.

## 1. Extract, then let the agent ask

After an extraction that wrote frames (`bug`, `anim` or `frames`), the agent asks whether you want to pick the frames yourself. It also asks when you say so first. Answer yes, and it runs:

```bash
./.aitask-scripts/aitask_screen_recording.sh pick /tmp/video-prep/rec-anim --open --out /tmp/video-prep/rec-pick
```

`pick` accepts a run directory, a `frames/` directory or any folder of images:

- **`bug` and `frames` runs** give their `frames/`. A `bug` run's contact sheets are never taken for frames.
- **`anim` runs** give each segment's `sNN/frames/`, or `w01/frames/` after `--window`, as a group of its own.

Before anything else, every image is copied into the picker's own `src/` directory and hashed there. The page then shows exactly the bytes it checked, even if you go on editing the originals.

## 2. Choose on the page

| To… | Do this |
|-----|---------|
| select a frame, or deselect it | click it, or press <kbd>Space</kbd> on the focused frame |
| select a run of frames | click the first, then shift-click the last (or <kbd>Shift</kbd>+arrows) |
| move between frames | <kbd>←</kbd> <kbd>→</kbd> <kbd>↑</kbd> <kbd>↓</kbd>, <kbd>Home</kbd>, <kbd>End</kbd> |
| mark the start / end of a span | <kbd>s</kbd> / <kbd>e</kbd> on the focused frame; <kbd>x</kbd> clears both marks |
| mark a region | drag on the large preview; <kbd>Esc</kbd> clears it |
| say something about a frame | type in the note field under the preview |
| copy the result | **Copy**, or <kbd>c</kbd> |

Each thumbnail shows the time its file name carries and the step since the previous frame. The browser remembers your selection for these exact images: reopen the page and it is still there. A page rebuilt from changed images starts empty.

## 3. Paste the block

**Copy** puts a plain-text block on the clipboard. When the browser does not allow that, the page selects the text so you can copy it with <kbd>Ctrl</kbd>+<kbd>C</kbd> (<kbd>Cmd</kbd>+<kbd>C</kbd> on a Mac). Paste it into the agent:

```
# 2 frames picked in /tmp/video-prep/rec-pick/index.html (set 1a2b3c4d)
# viewing range: 0.483-0.600 s (first to last selected frame; a viewing range, not a measurement window)
/tmp/video-prep/rec-pick/src/s01/f013_0.483s.png	t=483 ms	first	note: button starts to move
/tmp/video-prep/rec-pick/src/s01/f020_0.600s.png	t=600 ms	+117 ms
# --window 0.4825-0.6005  (user-marked endpoints (unverified): start f013_0.483s.png at 483 ms, end f020_0.600s.png at 600 ms; check the anim run's own endpoint diagnostics before trusting it)
# source: anim run of /home/me/rec.mp4
```

Every frame line starts with an absolute path. That works with every agent: it reads the files it is given, whichever agent you use.

## A selection is a viewing range, not a measurement

The picker looks at no pixels. It never decides that a frame is still, or that a motion has settled: from pixels alone, a settled frame, the turning point of a spring, subpixel motion and a duplicated capture frame can look the same. So:

- **By default** the block calls your first to last frame a **viewing range**. It shows the agent where to look, and nothing more.
- **Mark a start frame and an end frame** (<kbd>s</kbd>, <kbd>e</kbd>) when you mean a span to measure. Only then does the block add `--window A-B`, labelled **user-marked endpoints (unverified)**.
  - The bounds sit half a millisecond outside the two frames' times, so `anim --window` starts at your start frame and ends at your end frame.
  - "Unverified" means just that: the agent runs `anim` on that window and trusts it only if `anim`'s own endpoint diagnostics agree. The motion must not already be under way at the window's second frame, and it must settle before the window's last frame.

## When the region stays in image pixels

A rectangle you drag becomes `--roi X,Y,W,H` in the recording's own pixels only when the frame is unedited. That means its snapshot's SHA-256 equals the one its `frames.tsv` row recorded at extraction (see [`frames.tsv`]({{< relref "/docs/skills/aitask-screen-recording" >}}#framestsv)). The row then says exactly which part of the recording the image shows, and at what scale.

The page shows the reason under the preview, and the block gives the rectangle in the image's own pixels, labelled as such, when:

- the folder has **no `frames.tsv`**, or no row for the image: nothing records where it came from;
- the image **was edited**. Any change alters the hash, even a crop resized back to the original size or a shift inside the same canvas, and an edited image's geometry is unknown. There is no way to supply a corrected transform. Draw the region on an unedited frame instead, or extract it with `frames --roi`.

## No display

`--open` opens the page with the system's opener: `xdg-open` on Linux, `open` on macOS, `wslview` (or `explorer.exe`) on WSL. It does not try in an SSH session, or on Linux without a graphical display. Then it prints `OPEN: not opened:` with the reason, still writes the page, and names it on the `PAGE:` line. The agent then chooses the frames itself. Open the page from a machine with a browser if you still want to pick.

## Related

- [`pick` reference]({{< relref "/docs/skills/aitask-screen-recording" >}}#pick): what it reads, the copy block line by line, and the warnings
- [Animation from a Prototype Recording]({{< relref "/docs/workflows/screen-recordings/animation" >}}): measuring the span you marked
- [Extract Exact Frames for Close Inspection]({{< relref "/docs/workflows/screen-recordings/exact-frames" >}}): full-resolution frames of a span, to pick from
