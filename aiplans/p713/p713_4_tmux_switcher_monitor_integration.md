---
Task: t713_4_tmux_switcher_monitor_integration.md
Parent Task: aitasks/t713_ait_syncer_tui_for_remote_desync_tracking.md
Sibling Tasks: aitasks/t713/t713_1_desync_state_helper.md, aitasks/t713/t713_2_syncer_entrypoint_and_tui.md, aitasks/t713/t713_3_sync_actions_failure_handling.md, aitasks/t713/t713_5_permissions_and_config.md, aitasks/t713/t713_6_website_syncer_docs.md
Archived Sibling Plans: aiplans/archived/p713/p713_*_*.md
Worktree: .
Branch: main
Base branch: main
---

## Summary

Integrate syncer into existing tmux and TUI surfaces: TUI registry, switcher shortcut/info, `ait ide` autostart, monitor summary, and minimonitor summary.

## Implementation Steps

1. Add `syncer` to `.aitask-scripts/lib/tui_registry.py`.
   - Label: `Syncer`.
   - Command: `ait syncer`.
   - Switcher-visible.
2. Add switcher shortcut `y`.
   - Update `_TUI_SHORTCUTS`, bindings, shortcut handler, and footer hint.
   - Do not use `n`; it remains reserved for create-task.
   - Preserve shortcut-on-selected-session semantics.
3. Add switcher desync info.
   - Use the selected session’s project root.
   - Display concise state such as `main: 1 behind · aitask-data: 3 behind`.
   - Treat helper failures as muted/unavailable info.
4. Add `tmux.syncer.autostart: false` support to `ait ide`.
   - When enabled, ensure a singleton `syncer` window exists.
   - Use exact tmux session targets and project cwd.
   - Preserve existing monitor startup behavior.
5. Add compact desync summaries to monitor and minimonitor.
   - Use `desync_state.py snapshot --json` without fetch on every refresh tick.
   - Cache or throttle to avoid blocking monitor refresh.
   - Scope multi-session summaries to each session’s project root.

## Verification

- `python3 -m pytest tests/test_git_tui_config.py`
- Add or update tests for `syncer` registry/switcher membership.
- Manual switcher test: `j`, then `y`, launches/focuses syncer.
- Manual `ait ide` test with `tmux.syncer.autostart: true`.
- Manual monitor/minimonitor summary rendering check.

