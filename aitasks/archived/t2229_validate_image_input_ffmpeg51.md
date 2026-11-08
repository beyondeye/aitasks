---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: test
status: Done
labels: [python, claudeskills]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1887
followup_kind: risk_mitigation
implemented_with: claudecode/opus5_5
created_at: 2026-11-07 22:18
updated_at: 2026-11-08 10:50
completed_at: 2026-11-08 10:50
---

## Origin

Risk-mitigation ("after") follow-up for t1893_6, created at Step 8d after implementation landed.

## Risk addressed

addresses: concat option framerate / -itsoffset measured only on ffmpeg n9.0.2

- The concat approach rests on `option framerate` and `-itsoffset` behaving as measured on ffmpeg n9.0.2. The documented minimum is 5.1, which was not run. The enumeration guard fails closed if timing differs, so a wrong timing is never reported, but on an older ffmpeg the feature could refuse to run. · severity: medium · → mitigation: validate_image_input_ffmpeg51

## Goal

Run the image-folder input (`bug DIR` / `anim DIR`, added by t1893_6 in commit a00121816) under FFmpeg 5.1, the documented minimum, and under one 6.x or 7.x build. Use static builds on a PATH shim (as t1893_3 did for its durationless-ffmpeg shim). Never install them system-wide.

- Run `python3 -m unittest tests.test_screen_recording_cli.ImageFolderInput` (and the whole `tests/test_screen_recording_cli.py`) with each build first on PATH.
- Confirm, or refute, on each version:
  - the concat demuxer's per-file `option framerate 1000000` directive gives a 1/1000000 time base and exact µs pts;
  - `-itsoffset` shifts the first image to its named time;
  - `-safe 0` accepts the `option` lines;
  - the single-configuration rule works: showinfo prints one `config in time_base` line per graph configuration, and the normalisation pass renders uniform PNGs;
  - `-update 1`, `-frames:v 2` and `-start_number 0` are accepted on the conversion and normalisation paths.
- Where a version fails, the enumeration guard must refuse with "this ffmpeg's concat demuxer does not keep the image times". Then document the real minimum for image input on the skill page's Requirements and in `.claude/skills/aitask-screen-recording/SKILL.md`. Make the tests skip, with a reason, below that version instead of failing.
- On FFmpeg 5.1 the animated-WebP fixture skips (its decoder lacks animation); confirm it skips and does not fail.

Key files: `.aitask-scripts/screen_recording/video_prep.py` (`ImageInput`), `tests/test_screen_recording_cli.py` (`ImageFolderInput`), `website/content/docs/skills/aitask-screen-recording.md` (Requirements). The archived plan `aiplans/archived/p1893/p1893_6_*.md` has the design and the measured spike.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-08T07:52:33Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-08T08:42:43Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-08T08:49:58Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:ad99be302f4359ce

> **✅ gate:risk_evaluated** run=2026-11-08T08:49:58Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2229/risk_evaluated_2026-11-08T08:49:58Z-risk_evaluated-a1.log`
