---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [claudeskills, python]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1887
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-05 23:27
updated_at: 2026-11-04 12:41
completed_at: 2026-11-04 12:41
---

## Origin

Spawned from t1893_1 during Step 8b review.

## Upstream defect

- `.aitask-scripts/screen_recording/video_prep.py:710` — anim summary always prints "fitted signal: <signal> (both signals are in curve.tsv)", even when no edge track exists and the `p_edge` column of `curve.tsv` is blank (misleading output text)

## Diagnostic context

While documenting `/aitask-screen-recording` (t1893_1), code review found the docs' claim "curve.tsv always holds both signals" was wrong: `vp_core.analyze_frames()` sets `p_edge` to `None` when `edge_tracks()` finds no track (fades, cross-fades), and `_write_curve_tsv()` then writes empty cells. A fade probe produced numeric `p_blend` values and blank `p_edge` cells in every row. The docs and `references/animation.md` §3 were corrected in t1893_1; the helper's own summary line in `_write_anim_summary()` still states "(both signals are in curve.tsv)" unconditionally.

## Suggested fix

Print the parenthetical only when `p_edge` is available (`r.get("p_edge") is not None`); otherwise say e.g. "(p_blend in curve.tsv; no edge track, so p_edge is blank)". Add a fade-fixture assertion in `tests/test_screen_recording_cli.py` on the summary text.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-04T10:19:49Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-04T10:39:05Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-04T10:41:19Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:3223a95c93721897

> **✅ gate:risk_evaluated** run=2026-11-04T10:41:19Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1896/risk_evaluated_2026-11-04T10:41:19Z-risk_evaluated-a1.log`
