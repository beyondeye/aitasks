"""Brainstorm TUI: interactive design space exploration with Textual."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow importing sibling packages (brainstorm, agentcrew)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Label

from brainstorm.brainstorm_session import crew_worktree

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AIT_PATH = str(Path(__file__).resolve().parent.parent.parent / "ait")

STATUS_COLORS = {
    "active": "#50FA7B",
    "paused": "#FFB86C",
    "completed": "#6272A4",
    "archived": "#888888",
}


# ---------------------------------------------------------------------------
# Placeholder Screens
# ---------------------------------------------------------------------------


class DAGScreen(Screen):
    """Placeholder: DAG visualization of proposal nodes."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("DAG View \u2014 coming in follow-up tasks", id="placeholder")
        yield Footer()


class NodeDetailScreen(Screen):
    """Placeholder: Single node metadata and proposal viewer."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Node Detail \u2014 coming in follow-up tasks", id="placeholder")
        yield Footer()


class CompareScreen(Screen):
    """Placeholder: Side-by-side comparison with diff viewer."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Compare View \u2014 coming in follow-up tasks", id="placeholder")
        yield Footer()


class ActionScreen(Screen):
    """Placeholder: Available operations (explore, compare, hybridize, detail, finalize)."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Actions \u2014 coming in follow-up tasks", id="placeholder")
        yield Footer()


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------


class BrainstormApp(App):
    """Textual app for interactive brainstorm session orchestration."""

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
        Binding("question_mark", "help_keys", "Help"),
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
        self.session_path = crew_worktree(task_num)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(f"Brainstorm session for task t{self.task_num}")
        yield Label("Press 'd' for DAG view, 'a' for actions, '?' for help")
        yield Label("Full interactive functionality coming in follow-up tasks.")
        yield Footer()

    def action_dag(self) -> None:
        self.push_screen("dag")

    def action_node(self) -> None:
        self.push_screen("node")

    def action_compare(self) -> None:
        self.push_screen("compare")

    def action_actions(self) -> None:
        self.push_screen("actions")

    def action_help_keys(self) -> None:
        self.notify("Help: d=DAG, n=Node, c=Compare, a=Actions, q=Quit")


if __name__ == "__main__":
    task_num = sys.argv[1] if len(sys.argv) > 1 else "0"
    app = BrainstormApp(task_num)
    app.run()
