"""monitor_shared - Shared widgets and utilities for monitor TUIs.

Provides reusable components used by both the full monitor (monitor_app.py)
and the mini monitor. Extracted to avoid code duplication.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Set up import paths before any local imports
_SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SCRIPT_DIR))
sys.path.insert(0, str(_SCRIPT_DIR / "lib"))
sys.path.insert(0, str(_SCRIPT_DIR / "board"))

# `PaneSnapshot` + the task-context symbols moved to monitor_core (t822_6);
# re-exported here so `from monitor.monitor_shared import TaskInfo, …` keeps
# working for monitor_app / minimonitor_app / tests.
from monitor.monitor_core import (  # noqa: E402,F401
    PaneSnapshot,
    _TASK_ID_RE,
    GateSummaryCache,
    TaskInfo,
    TaskInfoCache,
)

from textual.binding import Binding  # noqa: E402
from textual.containers import Container, VerticalScroll  # noqa: E402
from textual.screen import ModalScreen  # noqa: E402
from textual.widgets import Button, Label, Markdown, Static  # noqa: E402
from textual.app import ComposeResult  # noqa: E402
from rich.text import Text  # noqa: E402


# Dark background for terminal preview — hard-coded because we're rendering
# actual tmux terminal content (always dark) regardless of the TUI theme.
_DARK_BG_ANSI = "\033[48;2;26;26;26m"
_ANSI_RESET_RE = re.compile(r'\033\[0?m')
_ANSI_DEFAULT_BG_RE = re.compile(r'\033\[49m')


# Idle-detection compare-mode pseudo-icons used in agent cards across both
# the full monitor and the minimonitor. Single column wide so the compact
# minimonitor layout stays compact.
COMPARE_MODE_ICONS = {
    "stripped": "≈",   # ≈ — fuzzy / ANSI-stripped equality (default)
    "raw": "=",             # = — strict byte-equal
}


def format_compare_mode_glyph(mode: str, is_override: bool) -> str:
    glyph = COMPARE_MODE_ICONS.get(mode, "?")
    color = "yellow" if is_override else "dim"
    return f"[{color}]{glyph}[/]"


def format_pane_status(snap: PaneSnapshot) -> str:
    """Render a pane's status badge with awaiting_input > is_idle > active priority."""
    if getattr(snap, "awaiting_input", False):
        return f"[bold magenta]PROMPT {int(snap.idle_seconds)}s[/]"
    if snap.is_idle:
        return f"[yellow]IDLE {int(snap.idle_seconds)}s[/]"
    return "[green]Active[/]"


def _ansi_to_rich_text(ansi_str: str) -> Text:
    """Convert ANSI text to Rich Text with a forced dark background.

    Pre-processes the raw ANSI to inject a dark background (#1a1a1a) at the
    start and after every SGR reset, so areas that would otherwise show the
    terminal's default background render correctly in the TUI preview.
    """
    # Set dark bg at start of every line
    lines = ansi_str.split("\n")
    patched = []
    for line in lines:
        # Inject dark bg at start
        line = _DARK_BG_ANSI + line
        # After every reset (\033[0m or \033[m), re-apply dark bg
        line = _ANSI_RESET_RE.sub(lambda m: m.group(0) + _DARK_BG_ANSI, line)
        # Replace default-bg-only (\033[49m) with our dark bg
        line = _ANSI_DEFAULT_BG_RE.sub(_DARK_BG_ANSI, line)
        patched.append(line)
    text = Text.from_ansi("\n".join(patched))
    return text


class TaskDetailDialog(ModalScreen):
    """Read-only dialog showing task content and optional plan."""

    BINDINGS = [
        Binding("escape", "dismiss_dialog", "Close", show=False),
        Binding("q", "dismiss_dialog", "Close", show=False),
        Binding("p", "toggle_plan", "Plan/Task", show=True),
    ]

    DEFAULT_CSS = """
    TaskDetailDialog { align: center middle; }
    #task-detail-dialog {
        width: 90%;
        height: 85%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #task-detail-header { text-style: bold; margin: 0 0 1 0; }
    #task-detail-meta { margin: 0 0 1 0; color: $text-muted; }
    #task-detail-scroll { height: 1fr; }
    #task-detail-footer { dock: bottom; height: 1; color: $text-muted; }
    """

    def __init__(self, info: TaskInfo) -> None:
        super().__init__()
        self._info = info
        self._showing_plan = False

    def compose(self) -> ComposeResult:
        info = self._info
        with Container(id="task-detail-dialog"):
            yield Static(
                f"[bold]t{info.task_id}: {info.title}[/]",
                id="task-detail-header",
            )
            yield Static(
                f"Priority: {info.priority}  Effort: {info.effort}  "
                f"Type: {info.issue_type}  Status: {info.status}",
                id="task-detail-meta",
            )
            yield VerticalScroll(
                Markdown(info.body or "*No content*"),
                id="task-detail-scroll",
            )
            plan_hint = "  [dim]p: switch plan/task[/]" if info.plan_content else ""
            yield Static(
                f"[dim]q/Esc: close[/]{plan_hint}",
                id="task-detail-footer",
            )

    def action_dismiss_dialog(self) -> None:
        self.dismiss()

    def action_toggle_plan(self) -> None:
        if not self._info.plan_content:
            self.app.notify("No plan file found", severity="warning")
            return
        self._showing_plan = not self._showing_plan
        content = self._info.plan_content if self._showing_plan else self._info.body
        label = "Plan" if self._showing_plan else "Task"

        scroll = self.query_one("#task-detail-scroll", VerticalScroll)
        for child in list(scroll.children):
            child.remove()
        scroll.mount(Markdown(content or "*No content*"))

        header = self.query_one("#task-detail-header", Static)
        header.update(f"[bold]t{self._info.task_id}: {self._info.title}[/] [{label}]")


class KillConfirmDialog(ModalScreen):
    """Confirmation dialog before killing a tmux pane."""

    BINDINGS = [
        Binding("escape", "dismiss_dialog", "Close", show=False),
    ]

    DEFAULT_CSS = """
    KillConfirmDialog { align: center middle; }
    #kill-dialog {
        width: 80%;
        min-width: 28;
        height: auto;
        max-height: 85%;
        background: $surface;
        border: thick $error;
        padding: 1 2;
    }
    #kill-header { text-style: bold; color: $error; margin: 0 0 1 0; }
    #kill-details { margin: 0 0 1 0; }
    #kill-preview-label { text-style: bold; color: $text-muted; margin: 1 0 0 0; }
    #kill-preview { max-height: 17; margin: 0 0 1 0; background: #1a1a1a; color: #d4d4d4; padding: 0 1; }
    #kill-buttons { width: 100%; height: 3; layout: horizontal; align: center middle; }
    #kill-buttons Button { width: auto; min-width: 10; margin: 0; }
    """

    def __init__(
        self,
        snap: PaneSnapshot,
        task_info: TaskInfo | None,
        show_preview: bool = True,
    ) -> None:
        super().__init__()
        self._snap = snap
        self._task_info = task_info
        self._show_preview = show_preview

    def compose(self) -> ComposeResult:
        snap = self._snap
        pane = snap.pane

        status = format_pane_status(snap)

        with Container(id="kill-dialog"):
            yield Static(
                "[bold red]Kill Agent Confirmation[/]",
                id="kill-header",
            )

            detail_parts = [
                f"Window:   [bold]{pane.window_index}:{pane.window_name}[/] (pane {pane.pane_index})",
            ]
            if self._task_info:
                info = self._task_info
                detail_parts.append(
                    f"Task:     [bold]t{info.task_id}[/]: {info.title}"
                )
                detail_parts.append(
                    f"          Priority: {info.priority}  Status: {info.status}"
                )
            detail_parts.append(f"Status:   {status}")
            detail_parts.append(f"Process:  {pane.current_command} (PID {pane.pane_pid})")

            yield Static("\n".join(detail_parts), id="kill-details")

            if self._show_preview:
                lines = snap.content.rstrip().splitlines()
                preview_lines = lines[-15:] if len(lines) > 15 else lines
                if preview_lines:
                    preview_content = _ansi_to_rich_text("\n".join(preview_lines))
                else:
                    preview_content = "(empty)"

                yield Static("[bold]Window Content Preview:[/]", id="kill-preview-label")
                yield Static(preview_content, id="kill-preview")

            with Container(id="kill-buttons"):
                yield Button("Kill", variant="error", id="btn-kill")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-kill":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_dismiss_dialog(self) -> None:
        self.dismiss(False)


class NextSiblingDialog(ModalScreen):
    """Dialog for picking next sibling task."""

    BINDINGS = [Binding("escape", "dismiss_dialog", "Close", show=False)]

    DEFAULT_CSS = """
    NextSiblingDialog { align: center middle; }
    #next-sib-dialog { width: 70%; height: auto; background: $surface; border: thick $warning; padding: 1 2; }
    #next-sib-header { text-style: bold; color: $warning; margin: 0 0 1 0; }
    #next-sib-details { margin: 0 0 1 0; }
    #next-sib-buttons { width: 100%; height: auto; layout: horizontal; }
    #next-sib-buttons Button { margin: 0 1; }

    /* Narrow variant (minimonitor companion pane, ~40 cols): three buttons
       cannot fit horizontally, so widen the dialog and stack them vertically. */
    NextSiblingDialog.narrow #next-sib-dialog { width: 90%; min-width: 30; }
    NextSiblingDialog.narrow #next-sib-buttons { layout: vertical; height: auto; }
    NextSiblingDialog.narrow #next-sib-buttons Button { width: 1fr; margin: 0 0 1 0; }
    """

    def __init__(
        self,
        current_task_id: str,
        current_title: str,
        current_status: str,
        suggested_id: str,
        suggested_title: str,
        parent_id: str,
        narrow: bool = False,
    ) -> None:
        super().__init__()
        self._current_task_id = current_task_id
        self._current_title = current_title
        self._current_status = current_status
        self._suggested_id = suggested_id
        self._suggested_title = suggested_title
        self._parent_id = parent_id
        self._narrow = narrow

    def compose(self) -> ComposeResult:
        if self._narrow:
            self.add_class("narrow")
        is_parent_with_children = "_" not in self._current_task_id
        will_kill = self._current_status == "Done" or is_parent_with_children
        with Container(id="next-sib-dialog"):
            yield Static("[bold yellow]Pick Next Sibling[/]", id="next-sib-header")
            lines = [
                f"Current:   [bold]t{self._current_task_id}[/]: {self._current_title}  (Status: {self._current_status})",
                f"Suggested: [bold]t{self._suggested_id}[/]: {self._suggested_title}",
            ]
            if will_kill:
                if is_parent_with_children:
                    lines.append("\n[yellow]Parent agent pane will be killed (parent is split into children)[/]")
                else:
                    lines.append("\n[yellow]Current agent pane will be killed (task is Done)[/]")
            yield Static("\n".join(lines), id="next-sib-details")
            with Container(id="next-sib-buttons"):
                yield Button(f"Pick t{self._suggested_id}", variant="warning", id="btn-pick-suggested")
                yield Button("Choose sibling", variant="primary", id="btn-choose-sibling")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-pick-suggested":
            self.dismiss(("pick", self._suggested_id))
        elif event.button.id == "btn-choose-sibling":
            self.dismiss(("choose", self._parent_id))
        else:
            self.dismiss(None)

    def action_dismiss_dialog(self) -> None:
        self.dismiss(None)


class _SiblingRow(Static):
    """A focusable sibling row inside ChooseSiblingModal."""

    can_focus = True

    DEFAULT_CSS = """
    _SiblingRow {
        height: 1;
        padding: 0 1;
    }
    _SiblingRow:focus {
        background: $accent 30%;
    }
    """

    def __init__(self, sib_id: str, title: str, blocking_ids: list[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self._sib_id = sib_id
        self._title = title
        self._blocking_ids = blocking_ids

    @property
    def sib_id(self) -> str:
        return self._sib_id

    def render(self) -> str:
        base = f"  [bold #7aa2f7]t{self._sib_id}[/]  {self._title}"
        if self._blocking_ids:
            blockers = " ".join(f"t{b}" for b in self._blocking_ids)
            base += f"  [bold red]⛔ blocked by {blockers}[/]"
        return base

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.screen.dismiss(self._sib_id)
            event.prevent_default()
            event.stop()
        elif event.key == "down":
            self._focus_neighbor(1)
            event.prevent_default()
            event.stop()
        elif event.key == "up":
            self._focus_neighbor(-1)
            event.prevent_default()
            event.stop()

    def _focus_neighbor(self, delta: int) -> None:
        parent = self.parent
        if parent is None:
            return
        rows = [w for w in parent.children if isinstance(w, _SiblingRow)]
        try:
            idx = rows.index(self)
        except ValueError:
            return
        new_idx = max(0, min(len(rows) - 1, idx + delta))
        if new_idx != idx:
            rows[new_idx].focus()
            rows[new_idx].scroll_visible()


class ChooseSiblingModal(ModalScreen):
    """Modal dialog letting the user pick a Ready sibling task by name."""

    BINDINGS = [Binding("escape", "dismiss_dialog", "Close", show=False)]

    DEFAULT_CSS = """
    ChooseSiblingModal { align: center middle; }
    #choose-sib-dialog {
        width: 70%;
        max-height: 80%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #choose-sib-header { text-style: bold; color: $accent; margin: 0 0 1 0; }
    #choose-sib-context { color: $text-muted; margin: 0 0 1 0; }
    #choose-sib-list { height: 1fr; min-height: 3; margin: 0 0 1 0; }
    #choose-sib-help { color: $text-muted; margin: 0 0 1 0; }
    #choose-sib-buttons { width: 100%; height: auto; layout: horizontal; }
    #choose-sib-buttons Button { margin: 0 1; }

    /* Narrow variant (minimonitor companion pane, ~40 cols): widen the dialog
       so the header, sibling rows, and OK/Cancel render fully. The two short
       buttons still fit horizontally within the widened pane. */
    ChooseSiblingModal.narrow #choose-sib-dialog { width: 90%; min-width: 30; }
    """

    def __init__(
        self,
        parent_id: str,
        siblings: list[tuple[str, str, list[str]]],
        narrow: bool = False,
    ) -> None:
        super().__init__()
        self._parent_id = parent_id
        self._siblings = siblings
        self._narrow = narrow

    def compose(self) -> ComposeResult:
        if self._narrow:
            self.add_class("narrow")
        with Container(id="choose-sib-dialog"):
            yield Static("[bold]Choose Sibling[/]", id="choose-sib-header")
            yield Static(
                f"Parent: [bold]t{self._parent_id}[/]  ·  {len(self._siblings)} Ready sibling(s)",
                id="choose-sib-context",
            )
            with VerticalScroll(id="choose-sib-list"):
                for sib_id, title, blocking_ids in self._siblings:
                    yield _SiblingRow(sib_id, title, blocking_ids)
            yield Static(
                "[dim]\\[↑/↓] navigate  \\[Enter/OK] select  \\[Esc] cancel[/]",
                id="choose-sib-help",
            )
            with Container(id="choose-sib-buttons"):
                yield Button("OK", variant="primary", id="btn-ok")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_mount(self) -> None:
        rows = list(self.query(_SiblingRow))
        if rows:
            rows[0].focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-ok":
            focused = self.focused
            if isinstance(focused, _SiblingRow):
                self.dismiss(focused.sib_id)
                return
            rows = list(self.query(_SiblingRow))
            if rows:
                self.dismiss(rows[0].sib_id)
            else:
                self.dismiss(None)
        else:
            self.dismiss(None)

    def action_dismiss_dialog(self) -> None:
        self.dismiss(None)
