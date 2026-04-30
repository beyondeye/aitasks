"""sync_action_runner - Shared task-data sync runner and conflict modal for Textual TUIs.

Encapsulates the parsing/dispatch glue around `.aitask-scripts/aitask_sync.sh --batch`
so multiple TUIs (board, syncer) can trigger a sync, classify the result, and offer
the same conflict-resolution UX without re-implementing it.

Three layers exposed:

- `parse_sync_output(stdout)` — pure string-to-`SyncResult` parser. No subprocess,
  no Textual import. Easy to unit-test.
- `run_sync_batch(timeout)` — blocking subprocess invocation that returns a
  `SyncResult`. Designed to be called from inside a `@work(thread=True)` worker.
- `SyncConflictScreen` (Textual `ModalScreen`) — modal listing conflicted files
  with "Resolve Interactively" / "Dismiss" buttons. Self-contained CSS.
- `run_interactive_sync(app, on_done)` — terminal-spawn-or-suspend fallback that
  runs `./ait sync` interactively.

Status-to-notification wording is left to each caller; this module only owns
parsing, dispatch, the modal, and the interactive fallback.

Usage (from a host App's worker):

    from sync_action_runner import (
        SyncConflictScreen, run_sync_batch, run_interactive_sync,
        STATUS_CONFLICT, STATUS_PUSHED, ...,
    )

    @work(thread=True, exclusive=True)
    def _sync_worker(self):
        result = run_sync_batch()
        if result.status == STATUS_CONFLICT:
            self.app.call_from_thread(
                self.push_screen, SyncConflictScreen(result.conflicted_files), on_resolve)
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from textual import on
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label

_LIB_DIR = str(Path(__file__).resolve().parent)
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from agent_launch_utils import find_terminal  # noqa: E402


# --- Wire-protocol status constants (must match aitask_sync.sh --batch exactly) ---
STATUS_SYNCED = "SYNCED"
STATUS_PUSHED = "PUSHED"
STATUS_PULLED = "PULLED"
STATUS_NOTHING = "NOTHING"
STATUS_AUTOMERGED = "AUTOMERGED"
STATUS_CONFLICT = "CONFLICT"
STATUS_NO_NETWORK = "NO_NETWORK"
STATUS_NO_REMOTE = "NO_REMOTE"
STATUS_ERROR = "ERROR"

# --- Synthetic statuses owned by run_sync_batch ---
STATUS_TIMEOUT = "TIMEOUT"
STATUS_NOT_FOUND = "NOT_FOUND"

# Wall-clock cap on the whole batch invocation. The underlying aitask_sync.sh
# applies its own NETWORK_TIMEOUT=10 to each fetch/push, so 30s leaves headroom
# for auto-merge attempts on top of the network calls.
DEFAULT_SYNC_TIMEOUT_SECONDS = 30

_SYNC_SCRIPT = "./.aitask-scripts/aitask_sync.sh"


@dataclass
class SyncResult:
    status: str
    conflicted_files: list[str] = field(default_factory=list)
    error_message: str | None = None
    raw_output: str = ""


def parse_sync_output(stdout: str) -> SyncResult:
    """Parse the first non-empty line of `aitask_sync.sh --batch` stdout.

    Pure function — no subprocess, no Textual. Mirrors the parsing previously
    inlined in `aitask_board.py:_run_sync` so behavior is identical for every
    documented status, including the bare `CONFLICT:` edge case (which yields
    `[""]` because `"".split(",")` does, matching the historical board path).
    """
    raw = stdout
    line = ""
    for candidate in stdout.splitlines():
        stripped = candidate.strip()
        if stripped:
            line = stripped
            break

    if not line:
        return SyncResult(
            status=STATUS_ERROR,
            error_message="empty output from sync script",
            raw_output=raw,
        )

    if line.startswith("CONFLICT:"):
        suffix = line[len("CONFLICT:"):]
        return SyncResult(
            status=STATUS_CONFLICT,
            conflicted_files=suffix.split(","),
            raw_output=raw,
        )

    if line.startswith("ERROR:"):
        return SyncResult(
            status=STATUS_ERROR,
            error_message=line[len("ERROR:"):],
            raw_output=raw,
        )

    if line in (
        STATUS_SYNCED,
        STATUS_PUSHED,
        STATUS_PULLED,
        STATUS_NOTHING,
        STATUS_AUTOMERGED,
        STATUS_NO_NETWORK,
        STATUS_NO_REMOTE,
    ):
        return SyncResult(status=line, raw_output=raw)

    return SyncResult(
        status=STATUS_ERROR,
        error_message=f"unknown status: {line}",
        raw_output=raw,
    )


def run_sync_batch(timeout: float = DEFAULT_SYNC_TIMEOUT_SECONDS) -> SyncResult:
    """Invoke `aitask_sync.sh --batch` and return a parsed `SyncResult`.

    Blocking — designed to be called from inside a `@work(thread=True)` worker.
    Owns subprocess error mapping: timeouts become `STATUS_TIMEOUT`, missing
    script becomes `STATUS_NOT_FOUND`. Otherwise hands off to
    `parse_sync_output`.
    """
    try:
        result = subprocess.run(
            [_SYNC_SCRIPT, "--batch"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return SyncResult(
            status=STATUS_TIMEOUT,
            error_message=f"sync timed out after {timeout:g}s",
        )
    except FileNotFoundError:
        return SyncResult(
            status=STATUS_NOT_FOUND,
            error_message="sync script not found",
        )

    return parse_sync_output(result.stdout)


class SyncConflictScreen(ModalScreen):
    """Modal dialog shown when `ait sync` detects merge conflicts.

    Self-contained: ships its own CSS via `DEFAULT_CSS` so it renders correctly
    in any host App (board, syncer) without depending on app-level styling.
    """

    DEFAULT_CSS = """
    #sync_conflict_dialog {
        width: 60%;
        height: auto;
        max-height: 50%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #sync_conflict_title {
        text-align: center;
        padding: 0 0 1 0;
        text-style: bold;
    }
    #sync_conflict_files {
        padding: 0 1;
        color: $text-muted;
    }
    #sync_conflict_buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, conflicted_files: list[str]):
        super().__init__()
        self.conflicted_files = conflicted_files

    def compose(self):
        file_list = "\n".join(f"  - {f}" for f in self.conflicted_files)
        with Container(id="sync_conflict_dialog"):
            yield Label("Sync Conflict Detected", id="sync_conflict_title")
            yield Label(
                f"Conflicts between local and remote task data:\n\n{file_list}\n\n"
                "Open interactive terminal to resolve?",
                id="sync_conflict_files",
            )
            with Horizontal(id="sync_conflict_buttons"):
                yield Button("Resolve Interactively", variant="warning", id="btn_sync_resolve")
                yield Button("Dismiss", variant="default", id="btn_sync_dismiss")

    @on(Button.Pressed, "#btn_sync_resolve")
    def resolve(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn_sync_dismiss")
    def dismiss_dialog(self):
        self.dismiss(False)

    def action_cancel(self):
        self.dismiss(False)


def run_interactive_sync(app, on_done: Callable[[], None] | None = None) -> None:
    """Launch interactive `./ait sync` for conflict resolution.

    Two paths:
    - If a terminal emulator is available (`find_terminal()`), spawn it
      detached running `./ait sync`. Fire-and-forget — `on_done` is NOT
      invoked because we cannot observe the spawned terminal's exit. This
      matches the board's pre-extraction behavior.
    - Otherwise, suspend the Textual app and run `./ait sync` inline. After
      the inline call returns, invoke `on_done` (if provided) so the host
      app can refresh its state.

    The no-terminal path uses `app.suspend()`, which blocks; call this from a
    worker context (e.g., `@work(exclusive=True)`) to avoid stalling the
    event loop. The terminal-spawn path is non-blocking and safe from any
    context.
    """
    terminal = find_terminal()
    if terminal:
        subprocess.Popen([terminal, "--", "./ait", "sync"])
        return

    with app.suspend():
        subprocess.call(["./ait", "sync"])
    if on_done is not None:
        on_done()
