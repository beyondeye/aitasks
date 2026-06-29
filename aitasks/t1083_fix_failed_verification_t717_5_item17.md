---
priority: medium
effort: medium
depends: [t717_4]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 717
created_at: 2026-06-27 23:19
updated_at: 2026-06-27 23:19
boardidx: 230
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
