---
priority: medium
effort: high
depends: [t713_8]
issue_type: feature
status: Implementing
labels: [tui, scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-29 09:43
updated_at: 2026-04-30 13:08
---

## Context

Parent t713 needs the syncer to not only display desync, but also provide actions to resolve it. This child wires the core sync/pull/push actions into the TUI and keeps the task-data behavior aligned with the existing board TUI sync implementation.

`aitask-data` must reuse the existing `ait sync` machinery. Do not create a parallel task-data sync algorithm unless it is only a thin wrapper around `.aitask-scripts/aitask_sync.sh --batch`.

## Key Files to Modify

- `.aitask-scripts/syncer/syncer_app.py`: action handlers, dialogs, and status updates.
- `.aitask-scripts/lib/desync_state.py`: add action subcommands if t713_1 left placeholders.
- `.aitask-scripts/lib/agent_launch_utils.py`: reuse existing launch helpers if needed for code-agent escape hatch; avoid broad refactors.

## Reference Files for Patterns

- `.aitask-scripts/board/aitask_board.py` `BoardApp.action_sync_remote`: manual sync entrypoint pattern.
- `.aitask-scripts/board/aitask_board.py` `BoardApp._run_sync`: exact `aitask_sync.sh --batch` invocation and status parsing.
- `.aitask-scripts/board/aitask_board.py` `BoardApp._show_conflict_dialog`: conflict modal flow.
- `.aitask-scripts/board/aitask_board.py` `BoardApp._run_interactive_sync`: fallback to `./ait sync` in a terminal or suspended TUI.
- `.aitask-scripts/board/aitask_board.py` `SyncConflictScreen`: modal UI reference.
- `.aitask-scripts/aitask_sync.sh`: authoritative task-data sync behavior and batch statuses.
- `.aitask-scripts/aitask_companion_cleanup.sh` and `agent_launch_utils.maybe_spawn_minimonitor`: companion pane lifecycle patterns.

## Implementation Plan

1. Add action handlers in the syncer for the selected branch row.
2. For `aitask-data`:
   - Run `.aitask-scripts/aitask_sync.sh --batch`.
   - Parse the same statuses used by the board: `CONFLICT:`, `NO_NETWORK`, `NO_REMOTE`, `NOTHING`, `AUTOMERGED`, `PUSHED`, `PULLED`, `SYNCED`, and `ERROR:`.
   - On `CONFLICT:` or other actionable failure, offer the same interactive `./ait sync` fallback as board.
3. For `main`:
   - Provide explicit pull and push actions against the source worktree.
   - Do not auto-commit source changes.
   - On non-fast-forward, merge conflict, auth, or network failure, show the captured error in the TUI.
4. Add a code-agent escape hatch for failed operations:
   - Launch a sibling tmux pane/window scoped to the current project/session.
   - Prompt the agent with the failed branch, command, stderr/stdout summary, and instruction to resolve interactively with the user.
   - Use companion-pane cleanup patterns; never kill the full tmux window.
5. After any sync action, refresh the desync snapshot immediately.

## Verification Steps

- Re-run `bash tests/test_sync.sh` to ensure task-data sync behavior remains compatible.
- Add focused tests for action-status parsing if implemented as a pure helper.
- Manually trigger an `aitask-data` conflict in a scratch clone and verify the syncer offers `./ait sync` and agent fallback.
- Manually verify `main` pull/push failure reporting in a scratch remote.
