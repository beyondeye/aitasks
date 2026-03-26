---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [codebrowser, ui]
created_at: 2026-03-26 09:54
updated_at: 2026-03-26 09:54
---

## Context

The board TUI (`ait board`) has an improved modal dialog (`PickCommandScreen`) for launching code agent sessions. It shows the full command to run, a prompt string for copying, and lets the user choose to copy or run in a new terminal. The codebrowser TUI (`ait codebrowser`) still launches agents directly without any modal.

This child task extracts the board's pattern into reusable shared components in `.aitask-scripts/lib/` so both TUIs can use it.

## Key Files to Modify

### Files to Create

1. **`.aitask-scripts/lib/agent_command_screen.py`** — Generalized `ModalScreen` widget
   - Extract from `PickCommandScreen` in `.aitask-scripts/board/aitask_board.py` (lines 1616-1679)
   - Constructor: `__init__(self, title: str, full_command: str, prompt_str: str)` — generic `title` replaces task-specific `task_num`
   - `DEFAULT_CSS` class variable carries the dialog CSS (currently in board app CSS at lines 2727-2752), so consuming apps don't need to duplicate it
   - Same key bindings: escape (cancel), c/C (copy command), p/P (copy prompt), r/R (run in terminal)
   - Same button handlers and action methods
   - Widget IDs renamed from `pick_command_*` to `agent_cmd_*` to reflect generic usage
   - Dismisses with `"run"` on run button or `None` on cancel

2. **`.aitask-scripts/lib/agent_launch_utils.py`** — Shared non-UI utilities
   - `find_terminal() -> str | None` — Consolidated from both TUI implementations. Use the codebrowser's expanded list which is a superset: `$TERMINAL` env, then alacritty, kitty, ghostty, foot, x-terminal-emulator, xdg-terminal-exec, gnome-terminal, konsole, xfce4-terminal, lxterminal, mate-terminal, xterm
   - `resolve_dry_run_command(project_root: Path, operation: str, *args: str) -> str | None` — Generalized from board's `_resolve_pick_command()` (lines 3389-3404). Calls `aitask_codeagent.sh --dry-run invoke <operation> <args>`, parses `DRY_RUN: <cmd>` output, returns command string or None

## Reference Files for Patterns

- `.aitask-scripts/board/aitask_board.py:1616-1679` — `PickCommandScreen` class to extract from
- `.aitask-scripts/board/aitask_board.py:2727-2752` — CSS styles to move to `DEFAULT_CSS`
- `.aitask-scripts/board/aitask_board.py:3389-3404` — `_resolve_pick_command()` to generalize
- `.aitask-scripts/codebrowser/agent_utils.py:9-21` — `find_terminal()` (superset terminal list to use)
- `.aitask-scripts/lib/config_utils.py` — Example of existing shared Python module in `lib/`

## Implementation Plan

1. Create `.aitask-scripts/lib/agent_launch_utils.py`:
   - Copy `find_terminal()` from `codebrowser/agent_utils.py` (it has the fuller terminal list)
   - Create `resolve_dry_run_command(project_root, operation, *args)` generalized from board's `_resolve_pick_command()`
   - Keep this module UI-framework-free (no Textual imports)

2. Create `.aitask-scripts/lib/agent_command_screen.py`:
   - Import from textual: `ModalScreen`, `Container`, `Horizontal`, `Label`, `Button`, `Binding`, `on`
   - Create `AgentCommandScreen(ModalScreen)` class:
     - `DEFAULT_CSS` with the dialog styling (adapted from board lines 2727-2752, renaming IDs from `pick_command_*` to `agent_cmd_*`)
     - `__init__(self, title, full_command, prompt_str)` storing all three
     - `compose()` method building the dialog layout with generic title
     - Button handlers for copy command, copy prompt, run, cancel
     - Action methods for keyboard shortcuts
   - The widget should be a drop-in replacement for `PickCommandScreen` with only the constructor signature changed

## Verification Steps

1. Run `python -c "from agent_command_screen import AgentCommandScreen"` from the `lib/` directory to verify imports work
2. Run `python -c "from agent_launch_utils import find_terminal, resolve_dry_run_command"` to verify utility imports
3. Verify `resolve_dry_run_command` works: `python -c "from pathlib import Path; from agent_launch_utils import resolve_dry_run_command; print(resolve_dry_run_command(Path('.'), 'pick', '1'))"` from the project root
