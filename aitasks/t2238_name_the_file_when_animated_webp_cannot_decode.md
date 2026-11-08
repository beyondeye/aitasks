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
created_at: 2026-11-08 10:47
updated_at: 2026-11-08 11:31
---

## Origin

Spawned from t2229 during Step 8b review.

## Upstream defect

- `.aitask-scripts/screen_recording/video_prep.py:642-651` — `ImageInput._require_one_frame` (and `_enumerate` for an all-WebP folder) surfaces ffmpeg's raw decode-failure tail when this ffmpeg cannot decode an animated WebP (5.1.1, 7.0.2). It fails closed but never names the user's file or says the image is animated.

## Diagnostic context

t2229 ran `bug DIR` / `anim DIR` under static FFmpeg 5.1.1 and 7.0.2 builds on a PATH shim. The folder held a PNG plus an animated WebP (`t00001000.webp`, 2 frames, written by the native n9.0.2 with `libwebp_anim`, which those versions can encode but not decode). Both versions exit 1 and write no output dir (fail closed, correct). But the PrepError is the generic `run()` tail:

- 5.1.1: `error: ffmpeg failed (1): … [webp] skipping unsupported chunk: ANIM … image data not found … Conversion failed!`
- 7.0.2: `error: ffmpeg failed (69): … Decode error rate 1 exceeds maximum 0.666667 … Could not open encoder before EOF`

Neither names the user's file (the input path falls outside the 12-line tail). On n9.0.2 the same folder gives the intended `t00001000.webp decodes to more than one frame (an animated image?); keep still images only`. The test `ImageFolderInput.test_animated_image_beside_other_codecs_is_refused` skips on 5.1.1/7.0.2 (decoder premise), so this path has no test there.

The same applies to an all-WebP folder: no mixed codecs means no `_require_one_frame`, so the failure surfaces from `_enumerate`'s concat pass instead.

## Suggested fix

Catch the decode failure in `_require_one_frame` / `_enumerate` and re-raise it naming the image (`<name>: this ffmpeg could not decode it — an animated WebP needs a newer ffmpeg; keep still images only`). Do not state a specific version unless it is measured. Cover it with a test that runs on any ffmpeg: feed a WebP whose ANIM chunks this ffmpeg rejects, or mock `ffmpeg()` to fail, and assert that the file is named.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-08T09:31:44Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-08T10:26:18Z status=pass attempt=1 type=human
