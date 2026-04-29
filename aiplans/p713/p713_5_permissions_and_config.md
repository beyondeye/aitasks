---
Task: t713_5_permissions_and_config.md
Parent Task: aitasks/t713_ait_syncer_tui_for_remote_desync_tracking.md
Sibling Tasks: aitasks/t713/t713_1_desync_state_helper.md, aitasks/t713/t713_2_syncer_entrypoint_and_tui.md, aitasks/t713/t713_3_sync_actions_failure_handling.md, aitasks/t713/t713_4_tmux_switcher_monitor_integration.md, aitasks/t713/t713_6_website_syncer_docs.md
Archived Sibling Plans: aiplans/archived/p713/p713_*_*.md
Worktree: .
Branch: main
Base branch: main
---

## Summary

Add config defaults and permission whitelist coverage for the new syncer helper script.

## Implementation Steps

1. Add `.aitask-scripts/aitask_syncer.sh` to all required helper-script whitelist touchpoints:
   - `.claude/settings.local.json`
   - `.gemini/policies/aitasks-whitelist.toml`
   - `seed/claude_settings.local.json`
   - `seed/geminicli_policies/aitasks-whitelist.toml`
   - `seed/opencode_config.seed.json`
2. Do not add Codex allowlist entries; Codex uses the prompt/forbidden model documented in `CLAUDE.md`.
3. Document `tmux.syncer.autostart` in `seed/project_config.yaml`.
   - Default: `false`.
   - Explain that `ait ide` launches a singleton syncer window when enabled.
4. Add or rely on loader default for `aitasks/metadata/project_config.yaml`.
   - Prefer no runtime project-config mutation unless tests or manual verification need the explicit key.
5. Confirm runtime TUI save paths do not auto-commit or push project config.

## Verification

- Search all five whitelist/config seed locations for `aitask_syncer.sh`.
- Validate JSON/TOML/YAML syntax with available repo tests or language tools.
- Confirm omitted `tmux.syncer.autostart` defaults to false.

