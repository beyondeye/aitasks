"""Canonical clipboard-copy seam for all Textual TUIs.

Every TUI copy action MUST go through :func:`copy_to_system_clipboard` instead
of calling ``app.copy_to_clipboard`` directly (enforced by
``tests/test_tui_clipboard_seam.sh``).

Why: Textual's ``App.copy_to_clipboard`` emits a bare OSC 52 escape. Inside
tmux that escape only reaches the outer terminal (and thus the system
clipboard) when the emitting pane is in the client's *visible* window — from a
background window, or a session with no attached terminal client, tmux stores
it as an internal paste buffer and the system clipboard is silently left
untouched. The user-visible symptom is "copied to clipboard" notifications
followed by an empty paste. This helper keeps the OSC 52 path (it is what
works outside tmux) and, when running inside tmux, additionally routes the
text through the tmux server with ``load-buffer -w``, which forwards to
attached clients regardless of pane visibility.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from tmux_exec import TmuxClient

if TYPE_CHECKING:
    from textual.app import App

_TMUX = TmuxClient()


def copy_to_system_clipboard(app: "App", text: str) -> None:
    """Copy ``text`` to the system clipboard from a Textual app.

    Always performs the Textual OSC 52 copy (covers non-tmux terminals and
    keeps Textual's internal ``_clipboard`` mirror in sync). When the process
    runs inside tmux (``$TMUX`` set), also pushes the text through the tmux
    gateway so the copy survives the pane being in a non-visible window.
    Best-effort: a failed tmux forward is not surfaced — the OSC 52 copy has
    already happened.
    """
    app.copy_to_clipboard(text)
    if os.environ.get("TMUX"):
        _TMUX.set_clipboard(text)
