---
title: "Bug Report from a Recording"
linkTitle: "Bug Report"
weight: 10
description: "Turn a bug-report screen recording into key screens, the glitch frame, and a step-by-step report that cites them"
depth: [intermediate]
---

Someone sends you `repro.mp4`: a minute of tapping through an app, with something going wrong somewhere in it. This walkthrough gets you from the clip to a numbered, frame-cited account of what happened, ready to become a task.

## Before you start

A good recording makes everything below easier. Ask for touches to be shown, the screen to be still for a moment around the problem, and Do Not Disturb to be on — see [Recording Tips]({{< relref "/docs/workflows/screen-recordings/recording-tips" >}}).

## 1. Run bug mode

Mention or attach the recording and the agent runs the helper for you. To run it yourself:

```bash
./.aitask-scripts/aitask_screen_recording.sh bug repro.mp4 --out /tmp/video-prep/repro-bug
```

Keep `--out` outside the repository. The last line of output is `SUMMARY: <path>`.

## 2. Understand what was picked

The helper keeps only the frames that visibly differ from the one before, then picks the ones worth looking at. Each pick carries a reason:

| Reason | Meaning |
|--------|---------|
| `start` / `end` | The first and last picture |
| `state` | A screen that stayed up at least `--min-dwell` (0.4 s) — the screens the user actually saw |
| `motion` | One frame per `--interval` (1 s) of continuous change, such as scrolling or a long animation. An ordinary 300 ms transition is not sampled; you see the screens before and after it |
| `brief` | A change that was over within `--brief-max` (0.12 s): a flash, a glitch frame, a very quick transition. **These are often the bug — look at them** |

Each pick also records how long it was "shown for": the time until the next visible change.

## 3. Read the results

1. **`summary.md`** — the video's properties, the pick counts, a sheet index, and the full timeline table
2. **The contact sheets** (`sheet_01.png`, …) — eight labelled frames each, `#N <time>s` and `<reason> <shown for>s`
3. **Individual frames** (`frames/04_5.500s.png`) — only the ones you need to see in detail; each costs about as much as a whole sheet
4. **`timeline.tsv`** — the same timeline as tab-separated data: `idx`, `time_s`, `shown_for_s`, `why`, `file`

## 4. Write the report

Reconstruct the flow as numbered steps, each citing the time and the frame:

```
1. #1 at 0.00 s, frames/01_0.000s.png: the settings list is open
2. #3 at 2.40 s, frames/03_2.400s.png: "Notifications" is tapped (touch dot visible)
3. #4 at 2.53 s, frames/04_2.533s.png (brief, 0.05 s): the screen flashes white
4. #5 at 2.58 s, frames/05_2.583s.png: the notifications screen appears with the toggle off
```

Keep **what is visible** separate from **what you infer** about the cause. A frame shows what was on screen, not why.

To turn the report into tracked work, use [`/aitask-explore`]({{< relref "/docs/skills/aitask-explore" >}}) to look for the cause in the code first, or [`/aitask-create`]({{< relref "/docs/skills/aitask-create" >}}) to file it directly. Paste the numbered steps into the task description; the frame files live in a scratch directory, so describe what they show rather than linking them.

## 5. Narrow a noisy run

| Symptom | Fix |
|---------|-----|
| The clock, battery or notification icons create extra picks | `--crop-top <px>`; the Android status bar is about 3–4 % of the screen height. `--crop-bottom <px>` for the navigation bar. Saved frames still show the full screen |
| Too many `motion` picks | `--interval 2`, or `--range START-END` around the interesting part |
| Only part of the screen matters | `--roi X,Y,W,H` in source pixels; the summary gives the factor to convert from frame coordinates |
| A small change (a toggle, a badge) is not detected | A more sensitive change detector: `--decimate hi=256:lo=128:frac=0.1` |
| The summary says picks were dropped by `--max-frames` | Narrow with `--range` rather than raising the cap |

## 6. Audio and logs

- **Audio** is detected and reported — none, silent, or present with its peak level — but not transcribed. `--extract-audio` writes a 16 kHz mono `audio.wav` when the track is not silent.
- **The container's `creation_time`** is low-confidence for lining frames up with logs: depending on the recorder it marks the start or the end of the recording.
- **Approximate log alignment on Android.** Run `adb shell date +%s.%N` right before you start recording, and capture logs with epoch timestamps:

  ```bash
  adb logcat -c && adb logcat -v threadtime,epoch,usec > log.txt &
  ```

  The clock reading is *not* the first frame's wall-clock time: the command and the recorder's start-up add an offset that nothing measures. Treat any log-to-frame match made this way as approximate, and anchor it on an event that is both visible in the video and written to the log, such as a tap (shown by `show_touches`) that the app logs, before you rely on it.
- **Exact alignment** needs a timing reference shared by the video and the log that has been verified as such. The helper does not provide one.

## 7. A bug inside an animation

When the glitch is part of a transition — a stutter, a wrong curve, an element jumping — use the bug report to find the moment, then measure that span with `anim --window START-END`. See [Animation from a Prototype Recording]({{< relref "/docs/workflows/screen-recordings/animation" >}}).

## See also

- [`/aitask-screen-recording`]({{< relref "/docs/skills/aitask-screen-recording" >}}) — every option, the output layout, and what each warning means
- [Screen Recordings]({{< relref "/docs/workflows/screen-recordings" >}}) — overview
