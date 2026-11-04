---
Task: t2202_fix_anim_end_on_normalised_video_timeline.md
Base branch: main
Output branch: main
---

# t2202 — anim segment windows clamp to the video's real end

## Context

`cmd_anim` (`.aitask-scripts/screen_recording/video_prep.py:575`) sets
`end_t = info["start_time"] + info["duration"]` and uses it to clamp each motion
segment's window end (`b = min(b, end_t)`, line 604). That value sits on the raw
container timeline and covers the longest stream. The kept-frame times it clamps
are on ffmpeg's normalised timeline, which starts at 0 because the format
`start_time` is subtracted. Two cases go wrong:

- **nonzero `start_time`** (e.g. 5 s): `end_t` is 5 s too late, so the clamp never
  applies.
- **audio longer than the video** (1 s of video, 3 s of audio): the container
  duration is 3 s, so the clamp again never applies.

In both cases the last segment's window, shown in `summary.md`'s
`## sNN (window a-b s)` heading and in `fit.json` `window_s`, can end up to
`--pad` (0.25 s) after the last video frame. t1893_2 fixed the same bug in `bug`
mode with `core.video_span()` (`vp_core.py:182`) and left `anim` alone. This task
moves `anim` onto the same helper.

## Implementation

### 1. `video_prep.py` — `cmd_anim`

- Delete `end_t = info["start_time"] + info["duration"]` (line 575).
- In the scan branch (`else:` of `if window:`), delete `end_t = min(end_t, b)`
  (line 590). `video_span` already bounds the end by `--range` through
  `range_end`.
- After `segs = core.motion_segments(times, args.gap)`, compute the end as
  `cmd_bug` does (lines 378-381):

  ```python
  # the video's own end on the kept frames' (normalised) timeline: the container
  # end is raw (start_time not subtracted) and can be a longer audio track's
  end_t = core.video_span(video_packets(args.video, info["vindex"]), info["start_time"],
                          range_end=span[1] if span else None, ranged=span is not None,
                          first_kept_t=times[0], last_kept_t=times[-1],
                          container_end=info["duration"]).end_t if segs else None
  ```

  The `if segs` guard keeps `times[0]` safe when no frames were kept. It also
  skips the extra ffprobe pass when there is no segment to clamp. `end_t` is read
  only inside the segment loop, and with an empty `segs` that loop never runs.
- The `--window` path never used `end_t` and does not change.
- When the end cannot be proven, `video_span` falls back to
  `min(container duration, range end)`. That is the normalised container length,
  which is already better than the old raw-timeline sum. This is a fallback for
  clamping the window only, so no new summary or run.json output is added.
  (`bug` mode reports this case because its dwell times and interval lower bounds
  depend on the end; the anim window end is only how far the frame decode is
  trimmed.)

### 2. `tests/test_screen_recording_cli.py` — `AnimMode` regressions

Fixture `slide_to_end`: `synth.card_frames(synth.tween(synth.EASE_OUT, 0.5, 0.3),
0.9, "right")`. That is 54 frames, the card settles at 0.8 s, and the video ends
at 0.9 s, so the 0.25 s pad reaches past the last frame and the clamp is what
decides the window end. A small helper runs the CLI and returns `(fits, run_json)`.

- `test_window_end_is_clamped_to_the_video_end` (**premise control**: passes
  before and after the fix):
  - **fixture guard**: run `ffmpeg -an -vf mpdecimate,showinfo -fps_mode
    passthrough -f null -` on the clip (the same decode as `scan()` with the
    default `--decimate`), parse the last ` pts_time:`, and assert
    `last + 0.25 > 0.9 + 0.02`. This proves the pad would overrun without the
    clamp, so the test is not vacuous.
  - assert `run["video"]["start_time"] ≈ 0`, one segment, and
    `fit["window_s"][1] ≈ 0.9` (delta 0.002).
- `test_nonzero_start_time_window_end` (**red before the fix**):
  `synth.encode(..., ts_offset=5)`.
  - fixture guard: `run["video"]["start_time"] ≈ 5.0`
  - `window_s[1] ≈ 0.9` (delta 0.002); before the fix it is ≈ last kept + 0.25
  - also on that clip, `--range 0-0.85` gives `window_s[1] ≈ 0.85` (delta 1e-6).
    This keeps the `--range` bound working after the `min(end_t, b)` line is
    removed.
- `test_window_end_ignores_longer_audio` (**red before the fix**):
  `synth.mux_tone(base, ..., duration=3, shortest=False)`.
  - fixture guard: `run["video"]["duration"] ≈ 3.0` (delta 0.05)
  - `window_s[1] ≈ 0.9` (delta 0.002).

Use `self.video(...)` for the cached base clip and write the offset and audio
variants under `self.tmp`, following `TriageRows`' pattern.

### 3. Step 9 (Post-Implementation)

Commit the code and tests (`bug: … (t2202)`), then archive per task-workflow Step 9.

## Verification

1. **Red proof without touching the worktree**: copy `git show
   HEAD:.aitask-scripts/screen_recording/video_prep.py` and the current
   `vp_core.py` into a scratchpad dir. Run that pre-fix CLI with `anim` on the
   ts5 and long-audio fixtures. Expect `window_s[1]` to be about the last kept
   frame + 0.25 (≈ 1.0), not 0.9. Record the numbers in the plan's final notes.
2. `python3 tests/test_screen_recording_cli.py` (whole file; the bug-mode
   `TriageRows` tests must stay green).
3. `python3 tests/test_screen_recording_core.py`.
4. `bash tests/run_all_python_tests.sh --test-dir tests` is optional. These two
   files cover the change; read only the final verdict line.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
