---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [python, claudeskills]
anchor: 1887
followup_kind: risk_mitigation
created_at: 2026-11-04 18:09
updated_at: 2026-11-04 18:09
---

## Origin

Risk-mitigation ("after") follow-up for t1893_2, created at Step 8d after implementation landed.

## Risk addressed

The detector thresholds have not been validated on real device recordings (goal-achievement).

> The detector thresholds (`freezedetect -60dB`, `blackdetect pic_th 0.98 pix_th 0.10`,
> `silencedetect -60dB`) are validated only on synthetic x264/AAC fixtures. On real
> device recordings, dark-mode screens can read as black, and noisy encoders or the
> always-on status bar could suppress freezes. The docs and the summary label these
> rows as detector candidates and state their settings, but real-world accuracy is
> unverified. · severity: medium

## Goal

Run `./.aitask-scripts/aitask_screen_recording.sh bug <video> --out <scratch>` on two
or three real recordings and check every freeze, black and silence row in
`summary.md` (section "Freeze, black and silence") against the frames:

- **true positives:** a real hang, a black flash and a silent gap are each listed,
  with start and end within about one frame;
- **false positives:** for example a dark-mode screen reported as black, or a still
  reading pause reported as a freeze. Note whether the summary's wording ("a hang
  only if the frames show the user acting", "a dark screen counts too") is enough
  to keep a reader from mistaking them;
- **misses:** for example status-bar noise breaking a freeze when `--crop-top` was
  not given.

Keep recordings outside the repository and upload nothing. If a threshold misfires,
record the measured case and file a follow-up task with the proposed adjustment.

## Verification Checklist

- [ ] Real Android recording with an app hang (≥ 2 s, user tapping): a freeze row covers the hang
- [ ] Recording with a black flash (1–3 frames): a black row with its own frame image, which shows black
- [ ] Dark-mode app recording: note any black rows on ordinary dark screens, and judge whether the summary text prevents misreading them
- [ ] Recording with narration or app sound and a silent gap ≥ 2 s: a silence row within about 50 ms of the gap
- [ ] Status-bar clock visible: compare freeze rows with and without --crop-top
- [ ] Record outcomes; create a follow-up task for any threshold that misfires
