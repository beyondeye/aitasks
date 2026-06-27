---
priority: medium
effort: medium
depends: [717_3]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 717
created_at: 2026-06-27 23:17
updated_at: 2026-06-27 23:17
---

## Failed verification item from t717_3

> [t717_3] In "Top verified models (recent)" mode, confirm rankings reflect recent-window scores not all-time (a model with high all-time but no recent runs falls below a model with recent activity).

### Source

- **Manual-verification task:** `aitasks/t717/t717_5_manual_verification_codeagent_usage_stats.md` (item #12)
- **Origin feature task:** t717_3
- **Origin archived plan:** `aiplans/archived/p717/p717_3_agent_picker_recent_modes.md`

### Commits that introduced the failing behavior

- 856df4739 feature: Add recent-window modes to agent_model_picker (t717_3)

### Files touched by those commits

- .aitask-scripts/lib/agent_model_picker.py

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t717_5 item #12.
