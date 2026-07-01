---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: [t717_4]
issue_type: bug
status: Done
labels: [verification, bug]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 717
implemented_with: claudecode/opus4_8
created_at: 2026-06-27 23:19
updated_at: 2026-07-01 16:43
completed_at: 2026-07-01 16:43
boardidx: 240
---

## Failed verification item from t717_4

> [t717_4] Open `./ait stats tui`, navigate to verified pane. Press `]` repeatedly

### Source

- **Manual-verification task:** `aitasks/t717/t717_5_manual_verification_codeagent_usage_stats.md` (item #17)
- **Origin feature task:** t717_4
- **Origin archived plan:** `aiplans/archived/p717/p717_4_stats_tui_window_selector_usage_pane.md`

### Commits that introduced the failing behavior

- 735ba9d51 feature: Add recent/prev_month windows to verified rankings + new usage pane (t717_4)

### Files touched by those commits

- .aitask-scripts/aitask_stats.py
- .aitask-scripts/stats/panes/agents.py
- .aitask-scripts/stats/stats_app.py
- .aitask-scripts/stats/stats_config.py
- .aitask-scripts/stats/stats_data.py

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t717_5 item #17.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-01T13:27:37Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-01T13:38:08Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-01T13:43:27Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:7e1b7399f0ca6eaf

> **✅ gate:risk_evaluated** run=2026-07-01T13:43:27Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1083/risk_evaluated_2026-07-01T13:43:27Z-risk_evaluated-a1.log`
