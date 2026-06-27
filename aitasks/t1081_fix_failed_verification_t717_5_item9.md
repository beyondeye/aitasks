---
priority: medium
effort: medium
depends: [717_2]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 717
created_at: 2026-06-27 23:16
updated_at: 2026-06-27 23:16
---

## Failed verification item from t717_2

> [t717_2] Verify all 5 whitelist touchpoints contain the new entry: `.claude/settings.local.json`, `.gemini/policies/aitasks-whitelist.toml`, `seed/claude_settings.local.json`, `seed/geminicli_policies/aitasks-whitelist.toml`, `seed/opencode_config.seed.json`.

### Source

- **Manual-verification task:** `aitasks/t717/t717_5_manual_verification_codeagent_usage_stats.md` (item #9)
- **Origin feature task:** t717_2
- **Origin archived plan:** `aiplans/archived/p717/p717_2_usagestats_live_hook.md`

### Commits that introduced the failing behavior

- 2952aadac feature: Add usagestats live hook + aitask_usage_update.sh (t717_2)

### Files touched by those commits

- .aitask-scripts/aitask_usage_update.sh
- .aitask-scripts/aitask_verified_update.sh
- .aitask-scripts/lib/verified_update_lib.sh
- .claude/settings.local.json
- .claude/skills/task-workflow/SKILL.md
- .claude/skills/task-workflow/satisfaction-feedback.md
- .gemini/policies/aitasks-whitelist.toml
- CLAUDE.md
- seed/claude_settings.local.json
- seed/geminicli_policies/aitasks-whitelist.toml
- seed/opencode_config.seed.json
- tests/test_usage_update.sh
- tests/test_verified_update.sh

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t717_5 item #9.
