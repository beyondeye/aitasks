---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [python, claudeskills]
gates: [risk_evaluated]
anchor: 1887
followup_kind: upstream_defect
created_at: 2026-11-08 11:25
updated_at: 2026-11-08 11:25
---

## Origin

Spawned from t2219 during Step 8b review.

## Upstream defect

- `.aitask-scripts/screen_recording/video_prep.py:244 — extract_views() builds one select expression with an eq(pts,…) term per wanted frame; ffmpeg (n9.0.2) fails with "Cannot allocate memory" somewhere between 100 and 120 terms, so `bug --max-frames` above ~110 (and any extraction that large) aborts the run.`

## Diagnostic context

- Found while t2219 tried to force a layout-driven contact-sheet reduction
  through the `bug` CLI. That needs about 126+ frames on one requested sheet.
- Bisected with a 5 s synth slide video (`synth.card_frames(tween(LINEAR, 0, 5),
  5.0, "right")`), run as
  `bug --interval 0.01 --per-sheet 400 --view-size 100 --max-frames N`:
  - N = 40, 60, 80 and 100 → exit 0;
  - N = 120, 160, 200 and 250 → exit 1, with
    `Error opening output file …/frames/.extract_tmp/%05d.png. Error opening
    output files: Cannot allocate memory`.
- The failure happens in ffmpeg's setup, before any frame is written. The
  `select='eq(pts,a)+eq(pts,b)+…'` expression is one sum with a term per
  frame, and ffmpeg's expression parser runs out at that depth.
- The image-folder input (`bug DIR` / `anim DIR`) and `anim
  --max-view-frames` go through the same `extract_views`, so they share the
  limit. `--max-frames` (bug, default 40) and `--max-view-frames` (anim,
  default 30) accept larger values than extraction can honour.
- t2219 worked around it in its test: the bug reduction test runs in-process
  with a smaller `SHEET_MAX_EDGE`.

## Suggested fix

- Extract in batches of at most ~60–80 pts per ffmpeg call, merging the
  showinfo results; or select by a range/`between()` form that does not grow
  with the frame count.
- Add a regression test with more than 120 wanted frames.
- Check that the two-showinfo instance parsing still holds per batch.
