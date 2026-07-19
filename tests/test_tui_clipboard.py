"""Tests for the canonical TUI clipboard seam (``lib/tui_clipboard.py``).

Pins the dual-path contract of ``copy_to_system_clipboard``: the Textual
OSC 52 copy always happens, and the tmux-gateway forward (``load-buffer -w``)
happens exactly when the process runs inside tmux (``$TMUX`` set). The gateway
forward is what makes copies from non-visible tmux panes reach the system
clipboard — plain OSC 52 from a hidden pane is stored as a tmux buffer and
never forwarded to the outer terminal.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = REPO_ROOT / ".aitask-scripts" / "lib"
sys.path.insert(0, str(LIB_DIR))

import tui_clipboard  # noqa: E402
from tui_clipboard import copy_to_system_clipboard  # noqa: E402


class _StubApp:
    """Minimal stand-in for a Textual App — records OSC 52 copy calls."""

    def __init__(self):
        self.copied: list[str] = []

    def copy_to_clipboard(self, text: str) -> None:
        self.copied.append(text)


class TestCopyToSystemClipboard(unittest.TestCase):
    def test_inside_tmux_forwards_through_gateway(self):
        app = _StubApp()
        with patch.dict(os.environ, {"TMUX": "/tmp/tmux-1000/ait,42,0"}), \
                patch.object(tui_clipboard._TMUX, "set_clipboard",
                             return_value=True) as fwd:
            copy_to_system_clipboard(app, "hello")
        self.assertEqual(app.copied, ["hello"])
        fwd.assert_called_once_with("hello")

    def test_outside_tmux_is_osc52_only(self):
        app = _StubApp()
        env = patch.dict(os.environ, {}, clear=False)
        env.start()
        try:
            os.environ.pop("TMUX", None)
            with patch.object(tui_clipboard._TMUX, "set_clipboard") as fwd:
                copy_to_system_clipboard(app, "hello")
        finally:
            env.stop()
        self.assertEqual(app.copied, ["hello"])
        fwd.assert_not_called()

    def test_gateway_failure_is_best_effort(self):
        # A failed tmux forward (rc != 0 → False) must not raise or block the
        # OSC 52 copy that already happened.
        app = _StubApp()
        with patch.dict(os.environ, {"TMUX": "/tmp/tmux-1000/ait,42,0"}), \
                patch.object(tui_clipboard._TMUX, "set_clipboard",
                             return_value=False):
            copy_to_system_clipboard(app, "hello")
        self.assertEqual(app.copied, ["hello"])


if __name__ == "__main__":
    unittest.main()
