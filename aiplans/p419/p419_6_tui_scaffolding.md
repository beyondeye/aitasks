---
Task: t419_6_tui_scaffolding.md
Parent Task: aitasks/t419_ait_brainstorm_architecture_design.md
Sibling Tasks: aitasks/t419/t419_1_*.md, aitasks/t419/t419_2_*.md, aitasks/t419/t419_3_*.md, aitasks/t419/t419_4_*.md, aitasks/t419/t419_5_*.md
Archived Sibling Plans: aiplans/archived/p419/p419_1_*.md, aiplans/archived/p419/p419_3_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: TUI Scaffolding

## Context
Scaffold the brainstorm TUI — a Textual app for interactive orchestration. Based on the crew dashboard pattern. Depends on t419_1 (spec) and t419_3 (DAG library). This is scaffolding only — full interactive logic comes in follow-up tasks.

## Steps

### Step 1: Bash Wrapper (aitask_brainstorm_tui.sh)
Copy pattern from `.aitask-scripts/aitask_crew_dashboard.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/terminal_compat.sh"

VENV_PYTHON="$HOME/.aitask/venv/bin/python"

if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="${PYTHON:-python3}"
    # ... package checks for textual, pyyaml
fi

ait_warn_if_incapable_terminal

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: ait brainstorm <task_num>"
    echo "Launch the brainstorm TUI for interactive design exploration."
    exit 0
fi

exec "$PYTHON" "$SCRIPT_DIR/brainstorm/brainstorm_app.py" "$@"
```

### Step 2: BrainstormApp (brainstorm_app.py)

```python
"""Brainstorm TUI: interactive design space exploration with Textual."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "board"))

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, Static

# Placeholder imports (will be implemented in follow-up tasks)
# from brainstorm_dag import ...
# from brainstorm_session import ...
# from brainstorm_crew import ...

STATUS_COLORS = {
    "active": "#50FA7B",
    "paused": "#FFB86C",
    "completed": "#6272A4",
    "archived": "#888888",
}


class DAGScreen(Screen):
    """Placeholder: DAG visualization of proposal nodes."""
    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("DAG View — coming in follow-up tasks", id="placeholder")
        yield Footer()


class NodeDetailScreen(Screen):
    """Placeholder: Single node metadata and proposal viewer."""
    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Node Detail — coming in follow-up tasks", id="placeholder")
        yield Footer()


class CompareScreen(Screen):
    """Placeholder: Side-by-side comparison with diff viewer."""
    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Compare View — coming in follow-up tasks", id="placeholder")
        yield Footer()


class ActionScreen(Screen):
    """Placeholder: Available operations (explore, compare, hybridize, detail)."""
    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Actions — coming in follow-up tasks", id="placeholder")
        yield Footer()


class BrainstormApp(App):
    TITLE = "ait brainstorm"
    CSS = """
    #placeholder {
        width: 100%;
        height: 100%;
        content-align: center middle;
        text-style: italic;
        color: #888888;
    }
    """
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "dag", "DAG View"),
        Binding("n", "node", "Node Detail"),
        Binding("c", "compare", "Compare"),
        Binding("a", "actions", "Actions"),
        Binding("?", "help", "Help"),
    ]

    SCREENS = {
        "dag": DAGScreen,
        "node": NodeDetailScreen,
        "compare": CompareScreen,
        "actions": ActionScreen,
    }

    def __init__(self, task_num: str):
        super().__init__()
        self.task_num = task_num

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Label(f"Brainstorm session for task t{self.task_num}"),
            Label("Press 'd' for DAG view, 'a' for actions, '?' for help"),
            Label("Full interactive functionality coming in follow-up tasks."),
        )
        yield Footer()

    def action_dag(self) -> None:
        self.push_screen("dag")

    def action_node(self) -> None:
        self.push_screen("node")

    def action_compare(self) -> None:
        self.push_screen("compare")

    def action_actions(self) -> None:
        self.push_screen("actions")

    def action_help(self) -> None:
        self.notify("Help: d=DAG, n=Node, c=Compare, a=Actions, q=Quit")


if __name__ == "__main__":
    task_num = sys.argv[1] if len(sys.argv) > 1 else "0"
    app = BrainstormApp(task_num)
    app.run()
```

### Step 3: Dispatcher Entry
Ensure `ait brainstorm <task_num>` (numeric argument) routes to the TUI via `aitask_brainstorm_tui.sh`. This should already be handled by t419_4's dispatcher integration.

### Step 4: Verify Launch
Test that the TUI starts, shows placeholder screens, and responds to keybindings.

## Key Files
- `.aitask-scripts/aitask_brainstorm_tui.sh` — new bash wrapper
- `.aitask-scripts/brainstorm/brainstorm_app.py` — new Textual app
- `.aitask-scripts/agentcrew/agentcrew_dashboard.py` — reference for patterns
- `.aitask-scripts/aitask_crew_dashboard.sh` — reference for bash wrapper

## Verification
- `ait brainstorm 999` launches the TUI (after session init)
- TUI shows app title "ait brainstorm"
- Key bindings switch between placeholder screens (d, n, c, a)
- q exits cleanly
- No import errors
- shellcheck passes on bash wrapper

## Post-Implementation
- Step 9: archive task, push changes
