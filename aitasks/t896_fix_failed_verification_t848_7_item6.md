---
priority: medium
effort: medium
depends: [848_3]
issue_type: bug
status: Ready
labels: [verification, bug]
created_at: 2026-06-01 12:45
updated_at: 2026-06-01 12:45
---

## Failed verification item from t848_3

> [t848_3] Settings tab-switcher footer correctly lists current tab keys (registry-derived, not hardcoded).

### Source

- **Manual-verification task:** `aitasks/t848/t848_7_manual_verification_customizable_shortcuts.md` (item #6)
- **Origin feature task:** t848_3
- **Origin archived plan:** `aiplans/archived/p848/p848_3_sweep_remaining_tuis.md`

### Commits that introduced the failing behavior

- 663755c0 refactor: Sweep remaining TUIs onto ShortcutsMixin (t848_3)

### Files touched by those commits

- .aitask-scripts/applink/applink_app.py
- .aitask-scripts/brainstorm/brainstorm_app.py
- .aitask-scripts/brainstorm/brainstorm_dag_display.py
- .aitask-scripts/codebrowser/codebrowser_app.py
- .aitask-scripts/diffviewer/diffviewer_app.py
- .aitask-scripts/lib/agent_command_screen.py
- .aitask-scripts/lib/stale_entry_modal.py
- .aitask-scripts/lib/tui_switcher.py
- .aitask-scripts/monitor/minimonitor_app.py
- .aitask-scripts/monitor/monitor_app.py
- .aitask-scripts/settings/settings_app.py
- .aitask-scripts/stats/stats_app.py
- .aitask-scripts/syncer/syncer_app.py
- tests/test_shortcuts_registry_coverage.sh

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t848_7 item #6.
