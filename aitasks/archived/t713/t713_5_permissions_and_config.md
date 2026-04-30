---
priority: medium
effort: medium
depends: [t713_4]
issue_type: feature
status: Done
labels: [tui, scripts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-29 10:55
updated_at: 2026-04-30 15:33
completed_at: 2026-04-30 15:33
---

## Context

Parent t713 introduces `.aitask-scripts/aitask_syncer.sh` and `tmux.syncer.autostart`. This child handles permission whitelists and project configuration defaults so the new helper works cleanly across supported code-agent environments and fresh installs.

## Key Files to Modify

- `.claude/settings.local.json`: runtime Claude whitelist.
- `.gemini/policies/aitasks-whitelist.toml`: runtime Gemini whitelist.
- `seed/claude_settings.local.json`: seed Claude whitelist.
- `seed/geminicli_policies/aitasks-whitelist.toml`: seed Gemini whitelist.
- `seed/opencode_config.seed.json`: seed OpenCode whitelist.
- `seed/project_config.yaml`: documented `tmux.syncer.autostart` default.
- `aitasks/metadata/project_config.yaml`: add current project default if needed for tests/manual verification, defaulting to false.

## Reference Files for Patterns

- `CLAUDE.md` "Adding a New Helper Script": required 5 whitelist touchpoints.
- Existing `aitask_sync.sh` entries in all whitelist/config files.
- `seed/project_config.yaml` `tmux.git_tui` documentation block: style reference for documenting new tmux keys.
- `.aitask-scripts/settings/settings_app.py`: project config editing conventions and warning that runtime TUI saves must not auto-commit project config.

## Implementation Plan

1. Add `.aitask-scripts/aitask_syncer.sh` to all 5 required helper-script whitelist touchpoints.
2. Do not add Codex allowlist entries; Codex uses a prompt/forbidden model per `CLAUDE.md`.
3. Document `tmux.syncer.autostart` in `seed/project_config.yaml`:
   - Default value is `false`.
   - Explain that `ait ide` launches a singleton syncer window when enabled.
4. Add or preserve `tmux.syncer.autostart: false` in the project config used by this repo only if the implementation/tests need the key present; otherwise rely on loader defaults.
5. Confirm no runtime TUI save path auto-commits or pushes project config.

## Verification Steps

- Search all 5 whitelist touchpoints for `aitask_syncer.sh`.
- Run JSON/TOML/YAML syntax checks where existing tests or tooling support them.
- Run any config tests touched by the change.
- Manually confirm `tmux.syncer.autostart` defaults false when omitted.
