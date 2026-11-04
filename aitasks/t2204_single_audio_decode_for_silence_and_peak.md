---
priority: low
effort: medium
depends: []
issue_type: performance
status: Ready
labels: [python, claudeskills]
gates: [risk_evaluated]
anchor: 1887
followup_kind: review_finding
created_at: 2026-11-04 18:09
updated_at: 2026-11-04 18:09
---

## Origin

Review finding on t1893_2 (implementation review, disposition: follow-up).

## Finding

`cmd_bug` in `.aitask-scripts/screen_recording/video_prep.py` now runs two separate
ffmpeg processes over the audio of every recording that has an audio track:

- `silence_log()`: `silencedetect=n=-60dB:d=2,ametadata=mode=print`, with `atrim`
  first under `--range`;
- `audio_peak_db()`: `volumedetect`, always over the whole track.

Each one decodes the audio independently.

## Goal

At least for unranged runs, collect both measurements in one decode: a single
`-af` chain, `silencedetect,ametadata=mode=print,volumedetect`, whose log both
parsers read. Keep the existing semantics:

- the peak volume (the `audio:` line, including the "track present but silent"
  threshold) stays whole-track, even when `--range` trims the silence pass. A
  ranged run may keep two passes;
- the silence evidence model is unchanged: an end is observed only when
  `lavfi.silence_end` metadata sits on an audio frame; the EOF log line is the
  lower bound.

## Verification

- `TriageRows.test_silence_gap_and_trailing_silence` and the `BugMode` audio
  summary assertions in `tests/test_screen_recording_cli.py` still pass;
- add a check that an unranged run with audio launches one audio ffmpeg pass;
- add a ranged-run check that the peak still reflects the whole track.
