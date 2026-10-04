# Getting a better recording

Hand the user the part that fits their situation. A good recording beats any
amount of analysis.

## For any recording

- **Keep still around the action.** Leave the screen still for about half a
  second before and after it; that gives clean start and end pictures.
- **One thing per recording** when measuring an animation.
- **Do Not Disturb on.** A notification sliding in during the animation corrupts
  the measurement.
- **60 fps or more.** Resolution matters less than frame rate.
- **Measure from source when you can.** Compose Animation Preview in Android
  Studio, and the Animations panel in Chrome DevTools for web, show the real
  durations and curves. A curve fitted from video is the fallback when there is
  no source (designer prototypes, competitor apps, production builds).

## Android

```bash
adb shell settings put system show_touches 1        # draw taps (bug reports)
adb shell screenrecord --bit-rate 8M /sdcard/rec.mp4   # Ctrl-C to stop; default limit 180 s
adb pull /sdcard/rec.mp4
adb shell settings put system show_touches 0
```

- **Size:** `--size WxH` lowers resolution (fine for bug reports), and
  `--time-limit N` caps the length. Recent Android versions accept 0 for no
  limit.
- **Avoid `--bugreport` for this tool.** It burns a frame-time overlay into the
  video. The overlay changes every frame, so every frame registers as a change
  unless it is cropped out with `--roi`/`--crop-*`. It also turns on an info
  page.
- **Desktop alternative:** `scrcpy --record rec.mp4 --show-touches` (timestamps
  are captured on the device).
- **Slowed animations, for exact timing.** Set the scale, record, then put it
  back to 1 and analyse with `--time-scale 5`:

  ```bash
  adb shell settings put global animator_duration_scale 5
  # record the animation
  adb shell settings put global animator_duration_scale 1
  ```

  Some animation systems ignore the scale. If the result looks about 5× too
  fast, the app's animations didn't follow it, so analyse without
  `--time-scale`.
- **Logs alongside, for bug reports:**

  ```bash
  adb logcat -c && adb logcat -v epoch,usec > log.txt &
  ```

  Note the wall-clock time when the recording starts; `adb shell date +%s.%N`
  right before you start helps line frames up with log lines.
- **Jank vs design:** stutter can be dropped frames rather than the intended
  motion. A Perfetto trace with the `android.surfaceflinger.frametimeline` data
  source (Android 12+) shows expected vs actual frame timing.

## iOS

- **Device:** Control Center → Screen Recording.
- **Simulator:** `xcrun simctl io booted recordVideo rec.mov`.
- Slowed animations (Simulator → Debug → Slow Animations) slow things by a fixed
  factor. Measure a known animation first to confirm the factor before using
  `--time-scale`.

## Desktop and web

- Any recorder that writes MP4 or WebM at 60 fps works (OBS, `wf-recorder`,
  `ffmpeg -f x11grab`).
- For web animations, the Chrome DevTools Animations panel gives exact values;
  slowing playback there (25 % / 10 %) also helps when recording.
