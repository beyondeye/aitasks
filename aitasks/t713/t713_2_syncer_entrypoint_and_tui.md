---
priority: medium
effort: high
depends: [t713_1]
issue_type: feature
status: Implementing
labels: [tui, scripts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-29 09:40
updated_at: 2026-04-30 10:32
---

## Context

Parent t713 adds an `ait syncer` TUI for remote desync tracking. This child builds the command entrypoint and the core Textual UI shell on top of the desync state helper from t713_1.

The TUI tracks only two rows:
- `main`: source-code branch state.
- `aitask-data`: task/plan data branch state.

`aitask-locks` and `aitask-ids` are out of scope.

## Key Files to Modify

- `ait`: add `syncer` to usage text, update-check skip list, and dispatcher.
- `.aitask-scripts/aitask_syncer.sh`: new TUI entrypoint.
- `.aitask-scripts/syncer/syncer_app.py`: new Textual app.
- `.aitask-scripts/lib/tui_registry.py`: register the `syncer` TUI name if not already handled by a later integration child.

## Reference Files for Patterns

- `.aitask-scripts/aitask_board.sh` and `.aitask-scripts/aitask_codebrowser.sh`: TUI entrypoint dependency checks and terminal capability warning.
- `.aitask-scripts/board/aitask_board.py`: Textual structure, modal/loading patterns, and command palette conventions.
- `.aitask-scripts/board/aitask_board.py` `LoadingOverlay`: reference pattern for long-running sync actions.
- `.aitask-scripts/lib/tui_switcher.py`: current launcher/switcher expectations for TUI names.

## Implementation Plan

1. Add root `ait syncer` command path:
   - Usage under TUI commands.
   - Dispatcher case executing `.aitask-scripts/aitask_syncer.sh`.
   - Update-check skip list so launching the TUI is not delayed by release checks.
2. Create `.aitask-scripts/aitask_syncer.sh` following existing TUI wrappers:
   - Resolve framework Python with `require_ait_python`.
   - Check `textual` and `yaml` imports.
   - Run `ait_warn_if_incapable_terminal`.
   - Exec `.aitask-scripts/syncer/syncer_app.py`.
3. Create `syncer_app.py` with a first usable layout:
   - Left/top branch rows for `main` and `aitask-data`.
   - Detail pane with ahead/behind counts, commit subjects, changed paths, and errors.
   - Footer bindings for refresh, sync/pull/push, switcher, and quit.
4. Poll `desync_state.py snapshot --fetch --json` on a configurable interval, defaulting to 30 seconds.
5. Add manual refresh that runs immediately without waiting for the next interval.
6. Keep rendering behavior resilient: unavailable branches stay visible with an error/status line rather than crashing the app.

## Verification Steps

- Run `bash -n .aitask-scripts/aitask_syncer.sh`.
- Run `python3 -m py_compile .aitask-scripts/syncer/syncer_app.py`.
- Run `./ait syncer --help` or the app’s help path if implemented.
- Launch `ait syncer` locally inside tmux to confirm it renders the two branch rows.
