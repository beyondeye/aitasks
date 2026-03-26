---
priority: medium
effort: low
depends: [t468_1, t468_4]
issue_type: refactor
status: Ready
labels: [ui, board]
created_at: 2026-03-26 12:54
updated_at: 2026-03-26 12:54
---

## Context

Child task 1 (t468_1) created shared `agent_launch_utils.py` with `launch_in_tmux()` and `load_tmux_defaults()`. Child task 4 (t468_4) adds a "Tmux" settings tab to `ait settings` with `tmux.use_for_create` setting. This task refactors the board's task creation launch to optionally use tmux instead of a new terminal window, based on that setting.

Depends on: t468_1 (shared launch utilities), t468_4 (tmux settings with use_for_create)

## Key Files to Modify

1. **`.aitask-scripts/board/aitask_board.py`** — Board TUI, specifically `action_create_task()` method (lines ~3426-3435)
   - Currently launches `aitask_create.sh` via `Popen([terminal, "--", ...])` or suspend+call
   - Should check `tmux.use_for_create` from `project_config.yaml` and route through `launch_in_tmux()` when enabled

## Reference Files for Patterns

- `.aitask-scripts/lib/agent_launch_utils.py` — `launch_in_tmux()`, `load_tmux_defaults()`, `TmuxLaunchConfig`
- `.aitask-scripts/board/aitask_board.py:3407-3423` — `run_aitask_pick()` for the existing terminal launch pattern
- `aitasks/metadata/project_config.yaml` — `tmux.use_for_create` setting

## Implementation Plan

1. Import `launch_in_tmux`, `load_tmux_defaults`, `TmuxLaunchConfig` from `agent_launch_utils` in the board app
2. In `action_create_task()`:
   - Load tmux defaults: `defaults = load_tmux_defaults(Path("."))`
   - If `defaults["use_for_create"]` is True and tmux is available:
     - Build command string: `./.aitask-scripts/aitask_create.sh`
     - Create `TmuxLaunchConfig(session=defaults["default_session"], window="create-task", new_session=False, new_window=True)`
     - If the configured session doesn't exist, create it (new_session=True)
     - Call `launch_in_tmux(command, config)`
   - Otherwise: keep existing terminal/suspend behavior

## Verification Steps

1. Set `tmux.use_for_create: true` in `project_config.yaml`
2. Run `ait board`, press `n` to create task
3. Verify task creation runs in tmux session instead of new terminal
4. Set `tmux.use_for_create: false`, verify original behavior
