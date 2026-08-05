---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: enhancement
status: Done
labels: [shadow, aitask_monitormini]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1426]
assigned_to: dario-e@beyond-eye.com
anchor: 1037
implemented_with: claudecode/opus5
created_at: 2026-07-28 12:56
updated_at: 2026-08-05 11:40
completed_at: 2026-08-05 11:40
boardidx: 65536
---

## Origin

Risk-mitigation ("after") follow-up for t1274, created at Step 8d after
implementation landed.

## Risk addressed

Goal-achievement — unrecovered markers are reported but not recoverable, and
narrower widths are unverified:

> The untitled-row symptom is now reproduced and the fix verified against the
> real modal at 40×24, so the main delivery risk is retired. Residual: rows can
> still lose content at widths narrower than the 40 columns measured, and an
> over-bound split marker is still not *recovered* — only reported ·
> severity: medium

## Goal

t1274 made the losses **visible** — `concern_parser.unrecovered_markers()`
reports marker-looking lines that yielded no concern, the picker shows
`⚠ N line(s) in this block could not be parsed`, and a block that parses to
nothing warns instead of reporting "no concerns". What it does not do is let the
user *see what was lost* or prove the layout holds below 40 columns. Both are
this follow-up's job.

1. **Inspect the raw block.** Add an affordance behind the unrecovered-marker
   banner — a key in `ConcernPickerModal`, or a modal push — that shows the
   offending lines (`unrecovered_markers()` already returns them, the count is
   all that reaches the UI today) and ideally the raw block region, so the user
   can tell an over-bound split from a producer typo and file a real bug against
   the shadow procedure. Also reachable when the picker has **no** rows to show
   the banner beside (the all-malformed case, which currently only toasts).

2. **Extend the rendered-viewport layout tests below 40 columns.** The
   `ConcernPickerNarrowLayoutTests` in `tests/test_concern_picker_modal.py`
   assert the composited screen (`app.screen._compositor.render_strips()`) at
   `size=(40, 30)` — the measured minimonitor companion width. Nothing pins
   behaviour at 30 or 24 columns, where `#concern-dialog`'s `min-width: 30` and
   the two-line row's `_NARROW_PREFIX_COLS = 8` budget both start to bind. Add
   cases at the narrower widths and decide what the contract is there (a further
   fallback layout, or a documented floor below which the picker is not
   supported).

Note the existing precedent for a width floor: `concern_parser._SENTINEL_SAFE_COLS`
(24) is the width below which the block's own fences wrap.

## Verification

- Unit/render tests for the new inspect affordance, including the no-rows case.
- Composited-screen assertions at each supported width, each with a negative
  control proving the assertion discriminates (see t1274's
  `test_single_line_layout_is_what_lost_them` for the pattern).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-05T07:40:30Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-05T08:38:32Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-05T08:40:56Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:ae682210cecaa76f

> **✅ gate:risk_evaluated** run=2026-08-05T08:40:56Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1293/risk_evaluated_2026-08-05T08:40:56Z-risk_evaluated-a1.log`
