---
title: "Spot a Hang, a Black Flash or a Silent Gap"
linkTitle: "Hang, Black Flash, Silence"
weight: 15
description: "Use the freeze, black and silence rows of bug mode to find a frozen screen, a black frame or a silent stretch in a recording"
depth: [intermediate]
---

Some bugs show up as something *missing*: the app stops responding and the screen stops changing, a screen flashes black for a frame, or the sound drops out. `bug` mode looks for all three with ffmpeg's own detectors and lists every interval it finds next to the key frames, so a hang or a one-frame black flash is never lost among the other picks.

## 1. Run bug mode

The triage rows are part of every `bug` run; there is nothing extra to switch on:

```bash
./.aitask-scripts/aitask_screen_recording.sh bug repro.mp4 --out /tmp/video-prep/repro-bug
```

If the status bar shows a clock, crop it with `--crop-top`. The detectors look at the same region as change detection, and a ticking clock would keep breaking every freeze. A visible status bar can also stop a black screen from counting as black (see below). The [Bug Report walkthrough]({{< relref "/docs/workflows/screen-recordings/bug-report" >}}) covers the crop flags.

## 2. Read the rows

`summary.md` has a top line counting the rows (`- triage: N freeze, M black, K silence`) and a **Freeze, black and silence** section with one table row per interval:

| Kind | Detector and settings | What it means |
|------|-----------------------|---------------|
| `freeze` | `freezedetect`, noise floor −60 dB, at least `--freeze-min` (2 s) | Nothing in the analysed region changed by more than the noise floor for that long. A small change, such as a toggled checkbox, can sit inside a freeze; the frame picks still show it |
| `black` | `blackdetect`, `pic_th` 0.98, `pix_th` 0.10, every run (`--black-min` 0) | At least 98 % of the pixels were near black, for any length of time, including a single frame |
| `silence` | `silencedetect`, −60 dB, at least 2 s | The audio stayed below −60 dB for that long. Only checked when the recording has an audio track; otherwise the summary says `silence not checked (no audio stream)` |

The same rows are in `timeline.tsv` (with `kind` `freeze`, `black` or `silence`, a start in `time_s` and an end in `end_s`), and in `run.json` under `intervals`.

**A freeze is not a bug by itself.** A screen that stays still for 2 s is often just the user reading. It is a hang only when the frames show the user acting — a tap shown by "show touches", a keyboard press — and nothing answering. Say which it is in the report, and cite the frames that show it.

**A dark screen can count as black.** blackdetect measures brightness, not intent: a dark-mode screen that is almost entirely near black is a `black` row too. Look at the interval's frame before calling it a black flash.

**Recordings with a variable frame rate still work.** Android's screenrecord writes no frames while the screen is still, so a hang is a gap between two frames rather than a run of identical ones. freezedetect measures from the frames' timestamps and reports that gap as a freeze.

## 3. Ends that were not observed

An end is **observed** only when the detector marked it on a real frame (or audio frame): the first frame that is no longer black, the first frame that changes again, the moment sound returns. When the state is still on as the analysed span ends, the end cannot be known:

- the table shows the end as `≥ <t> s (span ended)` and the duration as `≥ …`;
- `timeline.tsv` notes `end not observed` in `why`, and `end_s` is a lower bound;
- `run.json` has `"end_observed": false`.

"The analysed span" is the video stream itself, or the `--range` you passed. For silence, it is the audio track. A longer audio track never stretches a black or frozen screen past the end of the video.

## 4. Why every black interval is represented

A black frame may be the whole bug, so the helper never loses one:

- **Every interval keeps its row**, whatever the frame budget.
- **Each black interval gets its own frame**: the first black frame, taken from inside the interval. This holds even when change detection dropped that frame as a near-duplicate of the frame before it, as happens when a dark screen gets slightly darker. Change detection never measured such a frame, so its "shown for" is the length of the black run, marked `(black run)` in the summary.
- **Black frames are ranked high** within `--max-frames`: below the first and last frame, above every other pick.

## 5. When images run out

If a recording has more black intervals than `--max-frames` leaves room for, the extra intervals keep their rows but get no image. The summary ends with:

```
Warning: N black intervals have no image (--max-frames M reached). All are listed above and in timeline.tsv; narrow with --range around them to see their frames.
```

`run.json` records `cap_hit: true` and the count in `black_images_omitted`. Rather than raising `--max-frames`, take the listed times and run `bug` again with `--range START-END` around the ones you need to see.

## Related

- [`/aitask-screen-recording`]({{< relref "/docs/skills/aitask-screen-recording" >}}) — every flag, the output layout, and the warnings
- [Bug Report from a Recording]({{< relref "/docs/workflows/screen-recordings/bug-report" >}}) — turn the rows and frames into a numbered report
- [Recording Tips]({{< relref "/docs/workflows/screen-recordings/recording-tips" >}}) — capture a recording that analyses well
