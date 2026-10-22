"""sync_failure_screen - Failure and needs-assistance modals for the syncer TUI."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from rich.text import Text
from textual import on
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Label, Static

_LIB_DIR = str(Path(__file__).resolve().parent.parent / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from guarded_dismiss import GuardedModalScreen  # noqa: E402
from sync_action_runner import (  # noqa: E402
    CONFLICT_CHOICE_AGENT,
    describe_main_conflict_reason,
)


@dataclass
class SyncFailureContext:
    ref_name: str
    action: str
    command: str
    status: str
    stderr_tail: str
    raw_output: str = ""
    # Absolute root of the repo the failed action targeted; None = the launch
    # repo (legacy single-repo semantics). Used to root the resolution agent.
    repo_root: str | None = None


class SyncFailureScreen(GuardedModalScreen):
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


class MainConflictScreen(GuardedModalScreen):
    """"Automatic update needs assistance": a main-branch pull or push the
    syncer stopped — local and upstream diverged, or a pull deferred because
    of recursive submodules (t2126).

    Dismisses with CONFLICT_CHOICE_AGENT or None (Dismiss / escape) — the same
    closed set as SyncConflictScreen, dispatched by equality (t1911). It only
    offers: launching the agent is the host's job.
    """

    DEFAULT_CSS = """
    #main_conflict_dialog {
        width: 80%;
        min-width: 60;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $warning;
        padding: 1 2;
    }
    #main_conflict_title {
        text-align: center;
        padding: 0 0 1 0;
        text-style: bold;
    }
    #main_conflict_body {
        padding: 0 1;
        height: auto;
        max-height: 20;
    }
    #main_conflict_buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(
        self,
        action: str,
        reason: str,
        branch: str,
        upstream: str,
        repo_root: str,
        output_tail: str,
        repo_label: str = "",
    ):
        super().__init__()
        self.action = action
        self.reason = reason
        self.branch = branch
        # The remote branch involved — for a pull, the configured upstream,
        # which need not be origin/<branch>.
        self.upstream = upstream
        self.repo_root = repo_root
        self.output_tail = output_tail
        self.repo_label = repo_label

    def compose(self):
        title = "Automatic update needs assistance"
        if self.repo_label:
            title = f"{title} — {self.repo_label}"
        parts = [
            ("Repository: ", "bold"), self.repo_root, "\n",
            ("Operation: ", "bold"), f"{self.action} of {self.branch}", "\n",
            ("Upstream: ", "bold"), self.upstream, "\n\n",
            ("Reason: ", "bold"),
            describe_main_conflict_reason(
                self.action, self.reason, self.branch, self.upstream),
        ]
        if self.output_tail:
            parts += ["\n\n", ("Git output (tail):", "bold"), "\n", self.output_tail]
        parts.append("\n\nLaunch a code agent to finish it?")
        with Container(id="main_conflict_dialog"):
            yield Label(title, id="main_conflict_title", markup=False)
            with VerticalScroll(id="main_conflict_body"):
                yield Static(Text.assemble(*parts))
            with Horizontal(id="main_conflict_buttons"):
                yield Button("Launch agent", variant="warning",
                             id="btn_main_conflict_agent")
                yield Button("Dismiss", variant="default", id="btn_main_conflict_dismiss")

    @on(Button.Pressed, "#btn_main_conflict_agent")
    def _on_agent(self):
        self.dismiss(CONFLICT_CHOICE_AGENT)

    @on(Button.Pressed, "#btn_main_conflict_dismiss")
    def _on_dismiss(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)
