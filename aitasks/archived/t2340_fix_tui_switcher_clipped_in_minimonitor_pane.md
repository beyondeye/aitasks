---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [tui, tui_switcher]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2278
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-20 09:01
updated_at: 2026-11-22 17:47
completed_at: 2026-11-22 17:47
---

## Origin

Spawned from t2278_5 (docs screenshots). First left out of t2339 because a
fix was thought to cost two or three columns of content; the user then saw
that the clip cuts actual content and decided (2026-11-20) it must be fixed.

## Upstream defect

- `.aitask-scripts/lib/tui_switcher.py:556 — the switcher dialog has a fixed width of 44, so in the 40-column minimonitor pane it is clipped on the right: the right border is missing and the hint rows lose text ("(S)ettings" shows as "(S)etting", "(G)it" as "(G)i")`

## Diagnostic context

Opening the TUI switcher (`j`) from a minimonitor in its usual 40-column
split draws a dialog wider than the pane. The switcher already has a narrow
mode (`_switcher_narrow()` is True for minimonitor, passed as `narrow=`), but
the dialog's CSS width stays 44, so the rightmost cells fall outside the pane.

What is cut today, at 40 columns:
- the dialog's right border on every row;
- the ends of the two widest hint rows:
  `(B)oard  (M)onitor  (C)ode  (S)ettings` and
  `s(T)ats  s(Y)ncer  b(R)ainstorm  (G)it`.
The TUI list rows and the Code Agents rows fit.

See it: `website/static/imgs/aitasks_tui_switcher_from_minimonitor.svg`, or
live with
`website/screenshots.sh replay --scene tui_switcher_from_minimonitor --png`
(real minimonitor beside a stand-in agent, on a sample project).

## Requirement

In a narrow host pane no switcher content may be cut: every row's text and
the dialog border must be inside the pane. The wide layout (board, monitor,
other TUIs) should stay as it is.

## Suggested fix

In narrow mode size the dialog to the pane (for example `width: 100%` or a
max-width bound to the screen) and re-flow the hint rows so each fits the
narrower width (one more row, or shorter spacing). Check with a test that
boots the switcher at 40 columns and asserts the full hint texts are on
screen; `t2338` (sitrep in the switcher and minimonitor hint line) adds rows
here, so coordinate with it.

## After the fix

Refresh the docs image:
`/aitask-docs-screenshots tui_switcher_from_minimonitor`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-22T09:47:06Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-22T15:41:51Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-22T15:47:56Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:4d5fc1197b3c172e

> **✅ gate:risk_evaluated** run=2026-11-22T15:47:56Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2340/risk_evaluated_2026-11-22T15:47:56Z-risk_evaluated-a1.log`
