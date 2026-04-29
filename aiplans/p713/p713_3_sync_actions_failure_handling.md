---
Task: t713_3_sync_actions_failure_handling.md
Parent Task: aitasks/t713_ait_syncer_tui_for_remote_desync_tracking.md
Sibling Tasks: aitasks/t713/t713_1_desync_state_helper.md, aitasks/t713/t713_2_syncer_entrypoint_and_tui.md, aitasks/t713/t713_4_tmux_switcher_monitor_integration.md, aitasks/t713/t713_5_permissions_and_config.md, aitasks/t713/t713_6_website_syncer_docs.md
Archived Sibling Plans: aiplans/archived/p713/p713_*_*.md
Worktree: .
Branch: main
Base branch: main
---

## Summary

Wire sync/pull/push actions into the syncer and preserve existing board behavior for task-data sync. This child must not invent a parallel task-data sync flow.

## Existing Board References

Use `.aitask-scripts/board/aitask_board.py` as the reference for `aitask-data` sync behavior:

- `BoardApp.action_sync_remote`
- `BoardApp._run_sync`
- `BoardApp._show_conflict_dialog`
- `BoardApp._run_interactive_sync`
- `SyncConflictScreen`

The syncer must handle the same `.aitask-scripts/aitask_sync.sh --batch` statuses: `CONFLICT:`, `NO_NETWORK`, `NO_REMOTE`, `NOTHING`, `AUTOMERGED`, `PUSHED`, `PULLED`, `SYNCED`, and `ERROR:`.

## Implementation Steps

1. Add selected-row action handlers in `syncer_app.py`.
2. For `aitask-data`, call `.aitask-scripts/aitask_sync.sh --batch`.
   - Match board status parsing and user-facing outcomes.
   - On conflicts, offer the same interactive `./ait sync` fallback.
3. For `main`, provide explicit pull and push actions in the source worktree.
   - Do not auto-commit source files.
   - Capture and display non-fast-forward, merge conflict, auth, and network failures.
4. Add a code-agent escape hatch for failed operations.
   - Launch in the current project tmux session using existing `agent_launch_utils` patterns.
   - Include branch, command, stdout/stderr summary, and resolution instructions in the prompt.
   - Use companion-pane cleanup patterns; never kill a whole tmux window.
5. Refresh the desync snapshot immediately after every action.

## Verification

- `bash tests/test_sync.sh`
- Unit tests for pure status parsing if factored out.
- Manual scratch-repo conflict for `aitask-data` showing interactive `./ait sync` fallback.
- Manual scratch-repo pull/push failure for `main` showing error details and agent fallback.

