---
title: "Animation from a Prototype Recording"
linkTitle: "Animation"
weight: 20
description: "Measure an animation's duration and easing from a recording, choose a curve, and translate it to Compose, CSS or SwiftUI"
depth: [intermediate]
---

A designer sends a prototype clip, or you want to match how a competitor's sheet slides in. "Make it feel like this" needs numbers: a duration and an easing curve. This walkthrough measures them from the recording and turns them into code.

## Before you start

- **Measure from source when you can.** Compose Animation Preview in Android Studio, or the Animations panel in Chrome DevTools, shows the real durations and curves. A curve fitted from video is the answer when there is no source: a designer's prototype, a competitor's app, a production build.
- **One motion per recording**, with the screen still for about half a second before and after it.
- **60 fps or more.** For the most precise timing, record with animations slowed down — see [Slowed capture](#slowed-capture).

More capture advice is in [Recording Tips]({{< relref "/docs/workflows/screen-recordings/recording-tips" >}}).

## 1. Run anim mode

Mention the recording and ask for the animation's timing; the agent runs the helper. To run it yourself:

```bash
./.aitask-scripts/aitask_screen_recording.sh anim prototype.mp4 --out /tmp/video-prep/prototype-anim
```

## 2. How it measures

1. **Find the motion.** Runs of change separated by a pause longer than `--gap` (0.12 s) become motion segments `s01`, `s02`, … in time order. Changes lasting a single frame — instant cuts, clock ticks, cursor blinks — are listed as cuts and not analysed.
2. **Decode every frame.** Each segment is re-decoded at its native frame rate, plus `--pad` (0.25 s) on each side.
3. **Measure progress.** Each frame gets a progress value from 0 (the still picture before the motion) to 1 (the settled picture after it). Overshoot reads above 1.
4. **Fit curves.** Named easing curves, a free cubic-bezier and a spring are each fitted to that progress.

## 3. Check the segment

First confirm it is the animation you meant: look at the segment's contact sheet. Then read its geometry line in `summary.md`:

| Kind | What moves | Example | How exact |
|------|-----------|---------|-----------|
| `edge+` / `edge-` along x or y | One edge leads | A slide; a bottom sheet entering; a bar growing from one side | Exact, including overshoot |
| `grow` / `shrink` | Both edges, centred | A centred scale-up or scale-down | Approximate near the ends |
| `fade/blend` | No geometry change | Opacity, a cross-fade, a colour change | Exact for fades; for a full-screen push or slide, the timing is right but the curve is only a proxy |
| `returns` | The picture ends where it started | Press feedback, a shake, a ripple | No curve; read the sheet. The visible duration is still given |

`--signal edge` or `--signal blend` forces one progress signal. `curve.tsv` has a column for each (`p_blend`, `p_edge`), but `p_edge` is filled only when a moving edge can be tracked: for a fade or cross-fade its cells are blank, which is normal. A `still` or `returns` segment has no progress values at all. Act on any warning before trusting the fit — the [warnings table]({{< relref "/docs/skills/aitask-screen-recording" >}}#warnings-and-limits) says what each one means.

## 4. Read the duration

The summary gives two durations, and they differ on purpose:

- **Visible duration** runs from the first changed frame to the settled frame, ± one frame. It reads short when the start or the end of the curve is so slow that it moves less than a pixel per frame, which is common for ease-in-out and Material 3 decelerate curves.
- **Fitted duration** comes from the model, which accounts for those slow tails. **Implement the fitted duration.**

Real animations are aligned to the display refresh, so report "about 300 ms". Snap to a design-token duration only when it lies within one frame of the fitted value.

## 5. Choose a curve

The fit table is sorted by RMSE, the fitting error in progress units (1.0 is the whole movement):

- **Fits within about 0.005 RMSE of each other are indistinguishable** at this resolution. Pick the one the target platform names: Compose or Material 3 tokens for Android, CSS keywords for the web, the iOS defaults.
- **Use the custom cubic-bezier only if it clearly wins:** its RMSE is under half the best named curve's, *and* more than 0.01 lower.
- **Overshoot above about 2 %** (reported in the summary) means a spring. Use the spring fit, which also names the nearest Compose preset and gives a SwiftUI `response`.

## 6. Translate it to code

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

## 7. Isolate one element or one span

| Situation | What to do |
|-----------|-----------|
| Several things move at once (a "travel spread" warning) | `--roi X,Y,W,H` around the one element, in source pixels. The summary gives the factor and offset to convert coordinates read off a saved frame. Repeat per element |
| The automatic segments are wrong, or you want an exact span | `--window START-END` analyses exactly that span as one motion. Its first frame must be still *before* the motion and its last frame still *after* it |
| The recording holds several animations and you want one | `--range START-END` limits segment detection to that span |
| A fade is combined with a move | Fit `--signal blend` for the opacity, then `--roi` with `--signal edge` for the motion, and report both |
| The motion is only a few pixels | A tight `--roi` raises the analysis resolution; so does `--analysis-pixels 400000` |
| A full-screen push or slide | The timing is right; for the curve, `--roi` on a strip that only the incoming edge crosses |

## Slowed capture

A 60 fps recording times an animation to ±17 ms, and phone screen recorders drop frames under load. Slowing the animation down while recording gives proportionally more samples per curve.

1. On Android, set the animator duration scale, record, and set it back:

   ```bash
   adb shell settings put global animator_duration_scale 5
   # record the animation
   adb shell settings put global animator_duration_scale 1
   ```

2. Analyse with `--time-scale` set to the same factor:

   ```bash
   ./.aitask-scripts/aitask_screen_recording.sh anim slow.mp4 --time-scale 5 --out /tmp/video-prep/slow-anim
   ```

**What `--time-scale` converts.** Durations and fits are divided by the factor, and spring stiffness is multiplied by its square, so the numbers you implement are in real time. So are the ± ms offsets on contact-sheet labels and the plot's time axis. Everything that locates a moment *in the recording* stays in recording time: segment start times and windows, the timestamps on the "visible change" line, `curve.tsv` (both `time_s` and `t_rel_ms`), `fit.json`'s `window_s` and `frame_interval_ms`, frame file names, and the `--window` / `--range` values you pass. The [time-basis table]({{< relref "/docs/skills/aitask-screen-recording" >}}#time-basis-under---time-scale) lists every field.

**Worked example.** A 300 ms CSS ease-out recorded at scale 5 takes 1.5 s of the recording, starting at about 0.5 s:

| Where | What it shows | Time basis |
|-------|---------------|------------|
| `summary.md` segment row | starts `0.517 s`, visible duration `293 ms (±3)`, best fit `302 ms` | start: recording; durations: real |
| `summary.md` "visible change" line | first changed frame `0.517 s`, settled at `1.967 s`, frame interval `16.7 ms` → `293 ms` | timestamps and interval: recording; result: real |
| `fit.json` | `visible_duration_ms` 293.3, CSS ease-out `duration_ms` 302.4 | real |
| `fit.json` | `window_s` [0.267, 2.217], `frame_interval_ms` 16.67 | recording |
| `curve.tsv` | the settled frame at `t_rel_ms` ≈ 1467 | recording |

Implement **about 300 ms** with CSS ease-out — not 1467 ms. To re-measure the same motion as an exact span, pass recording seconds: `--window 0.3-2.3`.

`curve.tsv` holds every decoded frame, including the still context before and after the motion, so its `t_rel_ms` column runs from about −233 to +1717 here. Its full extent is not the motion's duration: the motion runs from 0 (one frame before the first changed frame) to the settled frame.

**Sanity checks:**

- If the result looks about N× **too fast**, the app's animations ignored the scale. Analyse again without `--time-scale`.
- If every duration looks two to ten times **too long** on a recording you thought was normal speed, the device may have had a non-default animator duration scale left on.
- On iOS, the Simulator's Slow Animations setting slows by a fixed factor. Measure an animation whose duration you know first, to confirm the factor before using `--time-scale`.

## Precision

Timing is precise to about one frame: ±17 ms at 60 fps. A large frame interval in the summary means dropped frames and coarser timing. If the numbers look suspicious, re-record — at a higher frame rate, or slowed — rather than trusting a fit to noisy data.

## See also

- [`/aitask-screen-recording`]({{< relref "/docs/skills/aitask-screen-recording" >}}) — every option, the output layout, the time-basis table, and what each warning means
- [Bug Report from a Recording]({{< relref "/docs/workflows/screen-recordings/bug-report" >}}) — when the animation is part of a bug
- [Recording Tips]({{< relref "/docs/workflows/screen-recordings/recording-tips" >}})
