---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [python, claudeskills]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1887
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-04 18:08
updated_at: 2026-11-04 18:52
---

## Origin

Spawned from t1893_2 during Step 8b review.

## Upstream defect

- `.aitask-scripts/screen_recording/video_prep.py:575` — `cmd_anim` sets
  `end_t = start_time + duration`. Its windows are on ffmpeg's normalised
  timeline (format `start_time` subtracted), and the container duration can be
  a longer audio track's. So anim segment windows clamp to the wrong end for a
  nonzero `start_time` or when the audio outlasts the video.

## Diagnostic context

t1893_2 (freeze/black/silence triage rows in `bug` mode) found that ffmpeg,
without `-copyts`, subtracts the input's format `start_time` before filtering.
That puts showinfo, metadata and `trim` on a normalised timeline starting at 0,
while `probe()["start_time"] + probe()["duration"]` is on the raw container
timeline. Measured: an mpegts clip with `start_time=1.433333` decodes from 0.

The container duration is also the longest stream's: 1 s of video with 3 s of
audio probes as 3.0 s.

t1893_2 fixed `bug` mode only. It added `core.video_span()` (video packets of
the resolved stream, normalised by the format `start_time`, coverage at the
maximum presentation pts, an origin cross-check that fails closed) and left
`anim` unchanged.

## Suggested fix

In `cmd_anim`, take `end_t` from `core.video_span(video_packets(args.video,
info["vindex"]), info["start_time"], ...)`, as `cmd_bug` does. Add an anim
regression with `synth.encode(..., ts_offset=5)` and one with a longer audio
track.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-04T16:52:49Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-04T17:04:08Z status=pass attempt=1 type=human
