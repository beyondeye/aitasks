---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: [t822_2]
issue_type: bug
status: Implementing
labels: [verification, bug, applink]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-15 18:01
updated_at: 2026-07-02 08:48
boardidx: 260
---

## Failed verification item from t822_2

> [t822_2] `shellcheck .aitask-scripts/aitask_applink.sh` reports no warnings

### Source

- **Manual-verification task:** `aitasks/t822/t822_4_manual_verification_new_ait_bridge_tui.md` (item #2)
- **Origin feature task:** t822_2
- **Origin archived plan:** `aiplans/archived/p822/p822_2_applink_tui_qr.md`

### Commits that introduced the failing behavior

- 68d803caf feature: Add ait applink TUI for QR-based mobile pairing (t822_2)

### Files touched by those commits

- .aitask-scripts/aitask_applink.sh
- .aitask-scripts/aitask_setup.sh
- .aitask-scripts/applink/__init__.py
- .aitask-scripts/applink/applink_app.py
- .aitask-scripts/applink/pairing.py
- .aitask-scripts/applink/qr_widget.py
- .aitask-scripts/lib/tui_registry.py
- .aitask-scripts/lib/tui_switcher.py
- tests/test_applink_smoke.sh
- website/content/docs/tuis/_index.md
- website/content/docs/tuis/applink/_index.md
- website/content/docs/tuis/applink/how-to.md
- website/content/docs/tuis/applink/reference.md

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t822_4 item #2.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-02T05:48:18Z status=pass attempt=1 type=human
