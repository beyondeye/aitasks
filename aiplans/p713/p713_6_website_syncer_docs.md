---
Task: t713_6_website_syncer_docs.md
Parent Task: aitasks/t713_ait_syncer_tui_for_remote_desync_tracking.md
Sibling Tasks: aitasks/t713/t713_1_desync_state_helper.md, aitasks/t713/t713_2_syncer_entrypoint_and_tui.md, aitasks/t713/t713_3_sync_actions_failure_handling.md, aitasks/t713/t713_4_tmux_switcher_monitor_integration.md, aitasks/t713/t713_5_permissions_and_config.md
Archived Sibling Plans: aiplans/archived/p713/p713_*_*.md
Worktree: .
Branch: main
Base branch: main
---

## Summary

Update the website documentation for the new syncer command and integrations, and add a dedicated Syncer TUI page.

## Implementation Steps

1. Locate website docs mentioning:
   - `ait sync`
   - TUI switcher shortcuts
   - tmux / `ait ide`
   - monitor and minimonitor
   - `project_config.yaml` tmux settings
2. Add a dedicated Syncer TUI page.
   - Command: `ait syncer`.
   - Purpose: visible remote desync tracking.
   - Branches shown: `main` and `aitask-data`.
   - Polling and manual refresh.
   - Relationship to existing `ait sync` for task-data sync.
   - Pull/push actions and failure handling.
   - Switcher key `y`.
   - `tmux.syncer.autostart`.
3. Update affected docs to cross-link to the Syncer TUI page.
4. Add the page to website navigation/sidebar.
5. Follow `CLAUDE.md` documentation rules: describe current behavior only, with no history/correction framing.

## Verification

- Run the repo’s website build command from `website/` when dependencies are available: `hugo build --gc --minify`.
- If full build dependencies are unavailable, run the strongest available static validation and record the limitation.
- Manually inspect website navigation to confirm the Syncer TUI page is reachable.

