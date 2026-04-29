---
Task: t713_2_syncer_entrypoint_and_tui.md
Parent Task: aitasks/t713_ait_syncer_tui_for_remote_desync_tracking.md
Sibling Tasks: aitasks/t713/t713_1_desync_state_helper.md, aitasks/t713/t713_3_sync_actions_failure_handling.md, aitasks/t713/t713_4_tmux_switcher_monitor_integration.md, aitasks/t713/t713_5_permissions_and_config.md, aitasks/t713/t713_6_website_syncer_docs.md
Archived Sibling Plans: aiplans/archived/p713/p713_*_*.md
Worktree: .
Branch: main
Base branch: main
---

## Summary

Add the public `ait syncer` command, entrypoint script, and first usable Textual TUI. This child depends on the desync helper from t713_1.

## Implementation Steps

1. Update root `ait`.
   - Add `syncer` to TUI usage.
   - Add `syncer` to the update-check skip list.
   - Add a dispatcher case that execs `.aitask-scripts/aitask_syncer.sh`.
2. Add `.aitask-scripts/aitask_syncer.sh`.
   - Follow `.aitask-scripts/aitask_board.sh` and `.aitask-scripts/aitask_codebrowser.sh`.
   - Resolve framework Python via `require_ait_python`.
   - Check `textual` and `yaml`.
   - Run `ait_warn_if_incapable_terminal`.
   - Exec `.aitask-scripts/syncer/syncer_app.py`.
3. Add `.aitask-scripts/syncer/syncer_app.py`.
   - Show two branch rows: `main` and `aitask-data`.
   - Show selected-row details: ahead/behind counts, commit subjects, changed paths, and errors.
   - Poll `desync_state.py snapshot --fetch --json` every 30 seconds by default.
   - Add manual refresh, quit, and TUI switcher bindings.
4. Reuse existing Textual UI patterns.
   - Use board-style loading/status affordances where applicable.
   - Keep unavailable branch states visible instead of crashing.

## Verification

- `bash -n .aitask-scripts/aitask_syncer.sh`
- `python3 -m py_compile .aitask-scripts/syncer/syncer_app.py`
- Manual launch in tmux: `ait syncer`
- Confirm the TUI renders exactly `main` and `aitask-data` rows.

