"""sync_failure_screen - Failure summary modal for the syncer TUI."""
from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


@dataclass
class SyncFailureContext:
    ref_name: str
    action: str
    command: str
    status: str
    stderr_tail: str
    raw_output: str = ""


class SyncFailureScreen(ModalScreen):
    """Show a sync-action failure summary; user picks Launch agent or Dismiss."""

    DEFAULT_CSS = """
    #sync_failure_dialog {
        width: 80%;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $error;
        padding: 1 2;
    }
    #sync_failure_title {
        text-align: center;
        padding: 0 0 1 0;
        text-style: bold;
    }
    #sync_failure_body {
        padding: 0 1;
        height: auto;
        max-height: 20;
    }
    #sync_failure_buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, ctx: SyncFailureContext):
        super().__init__()
        self.ctx = ctx

    def compose(self):
        ctx = self.ctx
        body = (
            f"[b]Branch:[/b] {ctx.ref_name}\n"
            f"[b]Command:[/b] {ctx.command}\n"
            f"[b]Status:[/b] {ctx.status}\n\n"
            f"[b]Output (tail):[/b]\n{ctx.stderr_tail or '(empty)'}"
        )
        with Container(id="sync_failure_dialog"):
            yield Label(
                f"Sync action failed: {ctx.action} on {ctx.ref_name}",
                id="sync_failure_title",
            )
            with VerticalScroll(id="sync_failure_body"):
                yield Static(body)
            with Horizontal(id="sync_failure_buttons"):
                yield Button(
                    "Launch agent to resolve",
                    variant="warning",
                    id="btn_failure_launch",
                )
                yield Button("Dismiss", variant="default", id="btn_failure_dismiss")

    @on(Button.Pressed, "#btn_failure_launch")
    def _on_launch(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn_failure_dismiss")
    def _on_dismiss(self):
        self.dismiss(False)

    def action_cancel(self):
        self.dismiss(False)
