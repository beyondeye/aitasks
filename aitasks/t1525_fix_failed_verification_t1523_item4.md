---
priority: medium
effort: medium
depends: [1509]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 1159
followup_kind: verification_failure
created_at: 2026-08-16 10:21
updated_at: 2026-08-16 10:21
---

## Failed verification item from t1509

> Let the followed Claude agent produce output and settle at a prompt. Observe ONE automatic recheck fire: the Codex shadow receives a single-line "refetch and recheck round N" prompt plus Enter.

### Source

- **Manual-verification task:** `aitasks/t1523_manual_verification_codex_shadow_recheck_loop.md` (item #4)
- **Origin feature task:** t1509
- **Origin archived plan:** `aiplans/archived/p1509_shadow_readiness_detectors_for_non_claude_shadows.md`

### Commits that introduced the failing behavior

- a98799580 feature: Add Codex shadow readiness detection to the recheck loop (t1509)

### Files touched by those commits

- aidocs/framework/monitor_idle_and_prompt_detection.md
- aidocs/framework/shadow_agent.md
- .aitask-scripts/monitor/minimonitor_app.py
- .aitask-scripts/monitor/monitor_core.py
- .aitask-scripts/monitor/review_loop.py
- tests/review_loop_fixtures.py
- tests/test_minimonitor_concern_action.py
- tests/test_minimonitor_concern_smoke.py
- tests/test_review_loop.py

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1523 item #4.
