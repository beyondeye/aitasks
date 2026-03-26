---
Task: t468_1_shared_agent_command_screen_and_utils.md
Parent Task: aitasks/t468_better_codeagent_launching.md
Sibling Tasks: aitasks/t468/t468_2_migrate_board_to_shared_components.md, aitasks/t468/t468_3_add_launch_modal_to_codebrowser.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: Create Shared AgentCommandScreen and Utilities

## Overview

Extract the board TUI's `PickCommandScreen` modal and supporting utilities into reusable shared modules in `.aitask-scripts/lib/`.

## Step 1: Create `.aitask-scripts/lib/agent_launch_utils.py`

Non-UI utility module. No Textual dependency.

```python
"""Shared utilities for launching code agents from TUI screens."""

import os
import shutil
import subprocess
from pathlib import Path


def find_terminal() -> str | None:
    """Find an available terminal emulator, or return None."""
    terminal = os.environ.get("TERMINAL")
    if terminal and shutil.which(terminal):
        return terminal
    for term in [
        "alacritty", "kitty", "ghostty", "foot",
        "x-terminal-emulator", "xdg-terminal-exec", "gnome-terminal",
        "konsole", "xfce4-terminal", "lxterminal", "mate-terminal", "xterm",
    ]:
        if shutil.which(term):
            return term
    return None


def resolve_dry_run_command(
    project_root: Path, operation: str, *args: str
) -> str | None:
    """Resolve the full agent command via --dry-run.

    Calls aitask_codeagent.sh --dry-run invoke <operation> <args> and parses
    the DRY_RUN: <cmd> output. Returns the command string or None on failure.
    """
    wrapper = str(project_root / ".aitask-scripts" / "aitask_codeagent.sh")
    cmd = [wrapper, "--dry-run", "invoke", operation] + list(args)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
            cwd=str(project_root),
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if output.startswith("DRY_RUN: "):
                return output[len("DRY_RUN: "):]
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
```

Key differences from board's `_resolve_pick_command()`:
- Takes `project_root` as Path (not hardcoded to cwd)
- Generic over `operation` (pick, explain, qa)
- Accepts `*args` for flexible arguments
- Passes `cwd` to subprocess

## Step 2: Create `.aitask-scripts/lib/agent_command_screen.py`

Textual modal widget, generalized from `PickCommandScreen`.

```python
"""Shared modal dialog for displaying and launching code agent commands."""

from textual import on
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class AgentCommandScreen(ModalScreen):
    """Dialog showing an agent command for copying or running."""

    DEFAULT_CSS = """
    #agent_cmd_dialog {
        width: 70%;
        height: auto;
        max-height: 50%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #agent_cmd_title {
        text-align: center;
        padding: 0 0 1 0;
        text-style: bold;
    }
    #agent_cmd_full, #agent_cmd_prompt {
        padding: 0 1;
        width: 1fr;
    }
    .agent-cmd-copy-row {
        height: 3;
        width: 100%;
        align: left middle;
    }
    .agent-cmd-copy-row Button {
        width: auto;
        min-width: 12;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("c", "copy_command", "Copy Command", show=False),
        Binding("C", "copy_command", "Copy Command", show=False),
        Binding("p", "copy_prompt", "Copy Prompt", show=False),
        Binding("P", "copy_prompt", "Copy Prompt", show=False),
        Binding("r", "run_terminal", "Run in Terminal", show=False),
        Binding("R", "run_terminal", "Run in Terminal", show=False),
    ]

    def __init__(self, title: str, full_command: str, prompt_str: str):
        super().__init__()
        self.title_text = title
        self.full_command = full_command
        self.prompt_str = prompt_str

    def compose(self):
        with Container(id="agent_cmd_dialog"):
            yield Label(self.title_text, id="agent_cmd_title")
            yield Label("Full command:")
            with Horizontal(classes="agent-cmd-copy-row"):
                yield Label(self.full_command, id="agent_cmd_full")
                yield Button("(C)opy", variant="primary", id="btn_copy_command")
            yield Label("Prompt only:")
            with Horizontal(classes="agent-cmd-copy-row"):
                yield Label(self.prompt_str, id="agent_cmd_prompt")
                yield Button("Copy (P)rompt", variant="primary", id="btn_copy_prompt")
            with Horizontal(id="detail_buttons"):
                yield Button("(R)un in new terminal", variant="warning", id="btn_run_terminal")
                yield Button("Cancel", variant="default", id="btn_agent_cancel")

    @on(Button.Pressed, "#btn_copy_command")
    def copy_command(self):
        self.app.copy_to_clipboard(self.full_command)
        self.app.notify("Command copied to clipboard")

    @on(Button.Pressed, "#btn_copy_prompt")
    def copy_prompt(self):
        self.app.copy_to_clipboard(self.prompt_str)
        self.app.notify("Prompt copied to clipboard")

    @on(Button.Pressed, "#btn_run_terminal")
    def run_terminal(self):
        self.dismiss("run")

    @on(Button.Pressed, "#btn_agent_cancel")
    def cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)

    def action_copy_command(self):
        self.copy_command()

    def action_copy_prompt(self):
        self.copy_prompt()

    def action_run_terminal(self):
        self.dismiss("run")
```

Key changes from `PickCommandScreen`:
- `title_text` parameter replaces `task_num` — callers pass "Pick Task t42", "Explain src/foo.py", etc.
- Widget IDs: `pick_command_*` → `agent_cmd_*`
- CSS class: `pick-copy-row` → `agent-cmd-copy-row`
- Cancel button ID: `btn_pick_cancel` → `btn_agent_cancel`
- CSS embedded as `DEFAULT_CSS` on the widget (auto-loaded by Textual)
- `detail_buttons` ID kept as-is (shared layout style from board's CSS)

## Verification

1. Import test: `cd .aitask-scripts/lib && python -c "from agent_command_screen import AgentCommandScreen; print('OK')"`
2. Import test: `cd .aitask-scripts/lib && python -c "from agent_launch_utils import find_terminal, resolve_dry_run_command; print('OK')"`
3. Dry-run test: `python -c "import sys; sys.path.insert(0, '.aitask-scripts/lib'); from agent_launch_utils import resolve_dry_run_command; from pathlib import Path; r = resolve_dry_run_command(Path('.'), 'pick', '1'); print(r or 'None (expected if no task 1)')"`

## Final Implementation Notes

- **Actual work done:** Created two shared modules as planned, but significantly expanded scope to include full tmux integration (tabbed Direct/tmux modes in the dialog, tmux session/window/pane management utilities, config loading from project_config.yaml). Original plan only had simple direct-run modal.
- **Deviations from plan:** Constructor gained `default_window_name` and `project_root` parameters. Dialog now uses `Input` widget for editable command (was `Label` in original plan). Added `TabbedContent` with Direct/tmux tabs. Dismiss result can now be `TmuxLaunchConfig` dataclass in addition to `"run"` or `None`.
- **Issues encountered:** None — all imports and utility tests passed on first try. tmux detection works correctly.
- **Key decisions:**
  - Command `Input` sits above tabs (shared between both modes) rather than duplicated in each tab
  - `t` key binding for tmux tab handled via `on_key` to avoid conflicts with `Input` text entry
  - Class-level `_last_session`/`_last_window` for cross-dialog-open memory within same TUI session
  - `load_tmux_defaults()` uses YAML with `try/except` fallback — no hard dependency on config existing
- **Notes for sibling tasks:**
  - t468_2 (board migration): Replace `PickCommandScreen` import with `AgentCommandScreen`, change constructor from `(task_num, full_command, prompt_str)` to `(title, full_command, prompt_str, default_window_name, project_root)`. Handle `TmuxLaunchConfig` dismiss result in callback by calling `launch_in_tmux()`. Remove board's `_find_terminal()`, `_resolve_pick_command()` and pick command CSS — all now in shared modules.
  - t468_3 (codebrowser): Import `AgentCommandScreen` from `lib/`, use same pattern. Codebrowser's `agent_utils.py:find_terminal()` can be replaced with the shared one.
  - t468_4 (settings tab): Add `tmux:` section to `PROJECT_CONFIG_SCHEMA` in settings_app.py. Use `_TAB_SHORTCUTS["t"] = "tab_tmux"` pattern. Settings: `default_session`, `default_split`, `use_for_create`.
  - t468_5 (board create refactor): Read `tmux.use_for_create` from config, optionally route `action_create_task()` through tmux launch.

## Step 9 (Post-Implementation)

Commit code, create t468_4 and t468_5 sibling tasks, update plan, archive task per workflow.
