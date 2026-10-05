---
title: "Recording Tips"
linkTitle: "Recording Tips"
weight: 30
description: "Capture a screen recording that analyses well, on Android, iOS and desktop"
depth: [intermediate]
---

A good recording beats any amount of analysis. Hand the person recording the part that fits their situation.

## For any recording

- **Keep still around the action.** Leave the screen still for about half a second before and after it; that gives clean start and end pictures.
- **One thing per recording** when measuring an animation.
- **Turn on Do Not Disturb.** A notification sliding in during an animation corrupts the measurement.
- **Record at 60 fps or more.** Frame rate matters more than resolution.
- **Measure from source when you can.** Compose Animation Preview in Android Studio, and the Animations panel in Chrome DevTools, show the real durations and curves. A curve fitted from video is the fallback when there is no source.

## Android

```bash
adb shell settings put system show_touches 1          # draw taps (bug reports)
adb shell screenrecord --bit-rate 8M /sdcard/rec.mp4  # Ctrl-C to stop
adb pull /sdcard/rec.mp4
adb shell settings put system show_touches 0
```

- **Length and size.** `screenrecord` stops after 180 seconds by default; `--time-limit N` sets another limit, and from Android 14 `--time-limit 0` removes it. `--size WxH` lowers the resolution, which is fine for bug reports.
- **Avoid `--bugreport` for this tool.** It burns the wall-clock time and a frame counter into every frame, so every frame registers as a change unless you crop the overlay out with `--roi` or the crop flags. It also adds an info page to the recording.
- **From the desktop:** `scrcpy --record rec.mp4 --show-touches` records the device screen from your computer, with timestamps captured on the device.
- **Slowed animations, for exact timing.** Set the scale, record, set it back to 1, and analyse with `--time-scale 5`:

  ```bash
  adb shell settings put global animator_duration_scale 5
  # record the animation
  adb shell settings put global animator_duration_scale 1
  ```

  Some animation systems ignore the scale. If the result looks about 5× too fast, the app's animations did not follow it; analyse without `--time-scale`. See [Slowed capture]({{< relref "/docs/workflows/screen-recordings/animation" >}}#slowed-capture) for which outputs the factor converts.
- **Logs alongside, for bug reports:**

  ```bash
  adb logcat -c && adb logcat -v threadtime,epoch,usec > log.txt &
  ```

  Running `adb shell date +%s.%N` right before you start recording gives an *approximate* start time for lining frames up with log lines — see [Audio and logs]({{< relref "/docs/workflows/screen-recordings/bug-report" >}}#6-audio-and-logs) for why it is approximate.
- **Jank or design?** Stutter can be dropped frames rather than the intended motion. A Perfetto trace with the `android.surfaceflinger.frametimeline` data source (Android 12 and later) shows expected against actual frame timing.

## iOS

- **On a device:** Control Center → Screen Recording.
- **In the Simulator:** `xcrun simctl io booted recordVideo rec.mov`.
- **Slowed animations:** Simulator → Debug → Slow Animations slows things by a fixed factor. Measure an animation whose duration you know first, to confirm the factor before using `--time-scale`.

## Desktop and web

- Any recorder that writes MP4 or WebM at 60 fps works: OBS, `wf-recorder`, or `ffmpeg -f x11grab`.
- For web animations, the Chrome DevTools Animations panel gives exact values. Slowing playback there (25 % or 10 %) also helps when you record.

## See also

- [Bug Report from a Recording]({{< relref "/docs/workflows/screen-recordings/bug-report" >}})
- [Animation from a Prototype Recording]({{< relref "/docs/workflows/screen-recordings/animation" >}})
- [`/aitask-screen-recording`]({{< relref "/docs/skills/aitask-screen-recording" >}})
