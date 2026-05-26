"""stale_entry_modal - Modal for prune/repoint of a STALE registry entry.

Pushed by tui_switcher when the user activates a registry entry whose
project root no longer holds aitasks/metadata/project_config.yaml --
either selected directly from the switcher's Session: row or detected
after a spawn_session_detached BOOTSTRAP_FAILED:stale_path race signal.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class RegistryRefresh(Message):
    """Posted by StaleEntryModal after a successful prune/repoint so the
    parent overlay can re-run discover_aitasks_sessions() and rebuild
    the Session: row.
    """


class _RepointInputScreen(ModalScreen):
    """Small text-input modal pushed by StaleEntryModal on Repoint."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    DEFAULT_CSS = """
    _RepointInputScreen { align: center middle; }
    #repoint_dialog {
        width: 70;
        height: 9;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #repoint_title {
        text-align: center;
        padding: 0 0 1 0;
    }
    #repoint_buttons {
        height: 3;
        align: center middle;
    }
    #repoint_buttons Button { margin: 0 1; }
    """

    def __init__(self, name: str, current_path: str) -> None:
        super().__init__()
        self._name = name
        self._current_path = current_path

    def compose(self) -> ComposeResult:
        with Container(id="repoint_dialog"):
            yield Label(
                f"Repoint [bold]{self._name}[/]\n[dim]{self._current_path}[/]",
                id="repoint_title",
            )
            yield Input(placeholder="New project path", id="repoint_input")
            with Horizontal(id="repoint_buttons"):
                yield Button("OK", variant="success", id="btn_repoint_ok")
                yield Button("Cancel", variant="default", id="btn_repoint_cancel")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    @on(Button.Pressed, "#btn_repoint_ok")
    def _submit(self) -> None:
        val = self.query_one("#repoint_input", Input).value.strip()
        self.dismiss(val or None)

    @on(Button.Pressed, "#btn_repoint_cancel")
    def _cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class StaleEntryModal(ModalScreen):
    """Prune / Repoint / Cancel modal for a STALE registry entry.

    Self-contained CSS because modals under lib/ are pushed by multiple
    Apps (ait ide, board, monitor, ...) and cannot rely on App-level CSS
    for focus / button height / dialog sizing.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("p", "prune", "Prune", show=False),
        Binding("r", "repoint", "Repoint", show=False),
        Binding("c", "cancel", "Cancel", show=False),
    ]

    DEFAULT_CSS = """
    StaleEntryModal { align: center middle; }
    #stale_dialog {
        width: 60;
        height: 13;
        background: $surface;
        border: thick $warning;
        padding: 1 2;
    }
    #stale_title {
        text-align: center;
        text-style: bold;
        padding: 0 0 1 0;
    }
    #stale_path {
        text-align: center;
        color: $text-muted;
        padding: 0 0 1 0;
    }
    #stale_actions {
        height: 3;
        align: center middle;
        padding: 1 0 0 0;
    }
    #stale_actions Button { margin: 0 1; }
    """

    # Path to aitask_projects.sh, resolved once. Class attribute so tests
    # can monkeypatch to point at a stub script.
    PROJECTS_SH: str = str(
        Path(__file__).resolve().parent.parent / "aitask_projects.sh"
    )

    def __init__(self, name: str, project_root: Path) -> None:
        super().__init__()
        self._name = name
        self._project_root = project_root

    def compose(self) -> ComposeResult:
        with Container(id="stale_dialog"):
            yield Label(
                f"Stale registry entry: [bold]{self._name}[/]",
                id="stale_title",
            )
            yield Label(str(self._project_root), id="stale_path")
            with Horizontal(id="stale_actions"):
                yield Button("(P)rune", variant="error", id="btn_stale_prune")
                yield Button(
                    "(R)epoint", variant="primary", id="btn_stale_repoint",
                )
                yield Button(
                    "(C)ancel", variant="default", id="btn_stale_cancel",
                )

    # --- Actions --------------------------------------------------------

    def action_prune(self) -> None:
        self._do_prune()

    def action_repoint(self) -> None:
        self._do_repoint()

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn_stale_prune")
    def _on_prune(self) -> None:
        self._do_prune()

    @on(Button.Pressed, "#btn_stale_repoint")
    def _on_repoint(self) -> None:
        self._do_repoint()

    @on(Button.Pressed, "#btn_stale_cancel")
    def _on_cancel(self) -> None:
        self.dismiss(None)

    # --- Subprocess helpers --------------------------------------------

    def _do_prune(self) -> None:
        try:
            result = subprocess.run(
                [self.PROJECTS_SH, "remove", self._name, "--force"],
                capture_output=True, text=True, timeout=10,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            self.app.notify(f"Prune failed: {exc}", severity="error")
            self.dismiss(None)
            return
        if result.returncode != 0:
            self.app.notify(
                f"Prune failed: {(result.stderr or '').strip() or 'unknown error'}",
                severity="error",
            )
            self.dismiss(None)
            return
        self.app.notify(f"Removed {self._name} from registry")
        self.post_message(RegistryRefresh())
        self.dismiss("pruned")

    def _do_repoint(self) -> None:
        self.app.push_screen(
            _RepointInputScreen(self._name, str(self._project_root)),
            callback=self._apply_repoint,
        )

    def _apply_repoint(self, new_path: str | None) -> None:
        if not new_path:
            return
        try:
            result = subprocess.run(
                [self.PROJECTS_SH, "update", self._name, new_path],
                capture_output=True, text=True, timeout=10,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            self.app.notify(f"Repoint failed: {exc}", severity="error")
            return
        if result.returncode != 0:
            self.app.notify(
                f"Repoint failed: {(result.stderr or '').strip() or 'unknown error'}",
                severity="error",
            )
            return
        self.app.notify(f"Repointed {self._name} -> {new_path}")
        self.post_message(RegistryRefresh())
        self.dismiss("repointed")
