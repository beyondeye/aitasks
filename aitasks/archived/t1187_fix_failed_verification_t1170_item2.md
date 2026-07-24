---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: [1167]
issue_type: bug
status: Done
labels: [verification, bug]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1158
implemented_with: claudecode/opus4_8
created_at: 2026-07-20 18:08
updated_at: 2026-07-24 10:56
completed_at: 2026-07-24 10:56
boardcol: bug_fixes
boardidx: 20
---

## Failed verification item from t1167

> Spawn a Codex shadow via minimonitor `e` on a plan review at a narrow pane width (~55 cols), with a concern whose region is a long full path

### Source

- **Manual-verification task:** `aitasks/t1170_manual_verification_concern_parser_wrap_tolerant_marker_foll.md` (item #2)
- **Origin feature task:** t1167
- **Origin archived plan:** `aiplans/archived/p1167_concern_parser_wrap_tolerant_marker.md`

### Commits that introduced the failing behavior

- 9d3122eb8 bug: Rejoin hard-wrapped concern markers within a bounded envelope (t1167)

### Files touched by those commits

- .aitask-scripts/monitor/concern_parser.py
- .claude/skills/aitask-shadow/concern-format.md
- tests/test_concern_parser.py

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1170 item #2.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-22T15:40:57Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-24T07:35:02Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-24T07:56:49Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:f2493192b4ae6491

> **✅ gate:risk_evaluated** run=2026-07-24T07:56:49Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1187/risk_evaluated_2026-07-24T07:56:49Z-risk_evaluated-a1.log`
