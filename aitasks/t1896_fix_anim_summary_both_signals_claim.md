---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [claudeskills, python]
gates: [risk_evaluated]
anchor: 1887
followup_kind: upstream_defect
created_at: 2026-10-05 23:27
updated_at: 2026-10-05 23:27
---

## Origin

Spawned from t1893_1 during Step 8b review.

## Upstream defect

- `.aitask-scripts/screen_recording/video_prep.py:710` — anim summary always prints "fitted signal: <signal> (both signals are in curve.tsv)", even when no edge track exists and the `p_edge` column of `curve.tsv` is blank (misleading output text)

## Diagnostic context

While documenting `/aitask-screen-recording` (t1893_1), code review found the docs' claim "curve.tsv always holds both signals" was wrong: `vp_core.analyze_frames()` sets `p_edge` to `None` when `edge_tracks()` finds no track (fades, cross-fades), and `_write_curve_tsv()` then writes empty cells. A fade probe produced numeric `p_blend` values and blank `p_edge` cells in every row. The docs and `references/animation.md` §3 were corrected in t1893_1; the helper's own summary line in `_write_anim_summary()` still states "(both signals are in curve.tsv)" unconditionally.

## Suggested fix

Print the parenthetical only when `p_edge` is available (`r.get("p_edge") is not None`); otherwise say e.g. "(p_blend in curve.tsv; no edge track, so p_edge is blank)". Add a fade-fixture assertion in `tests/test_screen_recording_cli.py` on the summary text.
