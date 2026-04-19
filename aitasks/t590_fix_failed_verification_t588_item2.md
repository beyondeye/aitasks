---
priority: medium
effort: medium
depends: [583_1]
issue_type: bug
status: Ready
labels: [verification, bug]
created_at: 2026-04-19 12:36
updated_at: 2026-04-19 12:36
---

## Failed verification item from t583_1

> sanity check beta

### Commits that introduced the failing behavior

- 715b08a2 feature: Add verification parser (t583_1)

### Files touched by those commits

- .aitask-scripts/aitask_verification_parse.py
- .aitask-scripts/aitask_verification_parse.sh
- .claude/settings.local.json
- .gemini/policies/aitasks-whitelist.toml
- seed/claude_settings.local.json
- seed/geminicli_policies/aitasks-whitelist.toml
- seed/opencode_config.seed.json
- tests/test_verification_parse.py

### Next steps

Reproduce the failure locally, identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t588 item #2.
