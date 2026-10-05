---
title: "Screen Recordings"
linkTitle: "Screen Recordings"
weight: 77
description: "Hand your agent a screen recording: reproduce a bug or implement an animation from it"
depth: [intermediate]
---

A screen recording is often the clearest description of a bug or a design: the glitch is right there, and so is the transition the designer wants. Coding agents read images, though, and most cannot open a video file. The [`/aitask-screen-recording`]({{< relref "/docs/skills/aitask-screen-recording" >}}) skill bridges the gap. Mention or attach a recording and the agent runs a helper that turns it into a few labelled contact sheets, individual frames, and measured numbers, then reads those instead.

```
recording.mp4 ──▶ aitask_screen_recording.sh bug|anim ──▶ summary.md
                                                           contact sheets
                                                           key frames
                                                           timeline / timing curves
                                                                │
                                         agent reads ◀──────────┘
                                                │
                    numbered bug report ◀───────┴───────▶ duration + easing, in code
```

## Choose a mode

| You have… | You want… | Mode | Walkthrough |
|-----------|-----------|------|-------------|
| A clip of a bug | What happened, step by step, with the glitch frame | `bug` | [Bug Report from a Recording]({{< relref "/docs/workflows/screen-recordings/bug-report" >}}) |
| A prototype or competitor clip | The duration and easing to implement | `anim` | [Animation from a Prototype Recording]({{< relref "/docs/workflows/screen-recordings/animation" >}}) |
| A glitch inside an animation | Both | `bug`, then `anim --window` | Start with the bug report |

## Read the results in order

1. **`summary.md`** — always first: what was found, which files to open, and warnings
2. **Contact sheets** — one read each; the summary estimates their token cost
3. **Single frames** — only the ones you need in detail; each costs about as much as a sheet
4. **Data** — `timeline.tsv` for bugs, `curve.tsv` and `fit.json` for animations, when you need exact values

Use the images for *what* is on screen and the numbers for *when* and *how fast*.

## Privacy

Recordings often contain personal data. The skill writes its output to a scratch directory outside the repository and never copies the recording into it, and the helper uploads nothing.

## Requirements

ffmpeg and ffprobe 5.1 or later must be on `PATH`; `ait setup` does not install them. ImageMagick 7 (`magick`) is optional and adds the contact sheets. See [Requirements]({{< relref "/docs/skills/aitask-screen-recording" >}}#requirements).

## Walkthroughs

- [Bug Report from a Recording]({{< relref "/docs/workflows/screen-recordings/bug-report" >}}) — key screens, brief glitch frames, and a report that cites them
- [Animation from a Prototype Recording]({{< relref "/docs/workflows/screen-recordings/animation" >}}) — measured duration, easing and spring fits, translated to code
- [Recording Tips]({{< relref "/docs/workflows/screen-recordings/recording-tips" >}}) — capture a recording that analyses well on Android, iOS and desktop

## More use cases

Further walkthroughs are added here as the skill grows.
