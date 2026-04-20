"""Small text-input modal used by ConfigModal for naming a custom layout."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class NameInputModal(ModalScreen):
    """Prompt for a single string value; returns the trimmed value or None."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    CSS = """
    NameInputModal {
        align: center middle;
    }
    #name_input_dialog {
        width: 50;
        height: auto;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #name_input_buttons {
        padding: 1 0 0 0;
        height: auto;
    }
    #name_input_buttons Button { margin: 0 1; }
    """

    def __init__(self, prompt: str = "Layout name:", initial: str = "") -> None:
        super().__init__()
        self.prompt = prompt
        self.initial = initial

    def compose(self) -> ComposeResult:
        with Container(id="name_input_dialog"):
            yield Label(self.prompt)
            yield Input(value=self.initial, id="name_input")
            with Horizontal(id="name_input_buttons"):
                yield Button("OK", id="btn_ok", variant="primary")
                yield Button("Cancel", id="btn_cancel")

    def on_mount(self) -> None:
        self.query_one("#name_input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_ok":
            self._submit()
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _submit(self) -> None:
        name = self.query_one("#name_input", Input).value.strip()
        self.dismiss(name or None)
