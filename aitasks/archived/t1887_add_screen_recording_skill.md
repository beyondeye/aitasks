---
priority: medium
effort: high
depends: []
issue_type: feature
status: Done
labels: [claudeskills, skills, python, tests, whitelists]
implemented_with: claudecode/opus5_5
created_at: 2026-10-04 15:46
updated_at: 2026-10-04 15:47
completed_at: 2026-10-04 15:47
---

Add the `aitask-screen-recording` skill. Coding agents can read images but not
video files, so the skill turns a device/desktop screen recording into
something an agent can read:

- **bug mode**: the screens that stayed up (states), one frame per second of
  continuous change (motion), sub-120 ms changes (brief: flashes, glitches),
  first/last frame, with a timeline, labelled contact sheets and full frames.
- **anim mode**: motion segments, every native frame of each segment, a
  per-frame progress curve (bounding-box edge signal for slides incl.
  overshoot, blend signal for fades), and fits of 13 named tweens (CSS,
  Compose, M2/M3 tokens), a free cubic-bezier and a spring (nearest Compose
  preset, SwiftUI response). `--time-scale` handles slowed-down captures.

Entry point `./.aitask-scripts/aitask_screen_recording.sh` (stdlib Python on
the framework venv, over ffmpeg; ImageMagick optional), whitelisted in all 5
helper touchpoints; thin wrappers for Codex (.agents) and OpenCode. 52 tests
run synthetic recordings with known ground truth through the real CLI.

Design review of existing third-party and in-repo resources, with a ranked
expansion list: `aidocs/screen_recording_skill_design_review.md`.
