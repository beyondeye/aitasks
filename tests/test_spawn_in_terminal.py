"""Tests for spawn_in_terminal detachment (t974).

The terminal-spawn path used by the TUIs (board, codebrowser, syncer) must
detach the spawned terminal into its own session so the agent inside it
survives the launching TUI's exit — especially when the TUI is NOT running
inside tmux. spawn_in_terminal() guarantees this via start_new_session=True.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = REPO_ROOT / ".aitask-scripts" / "lib"

sys.path.insert(0, str(LIB_DIR))
from agent_launch_utils import spawn_in_terminal  # noqa: E402


class TestSpawnInTerminal(unittest.TestCase):
    def _capture(self, *args, **kwargs):
        captured = {}

        def fake_popen(argv, **popen_kwargs):
            captured["argv"] = argv
            captured["kwargs"] = popen_kwargs
            return object()

        with patch.object(subprocess, "Popen", side_effect=fake_popen):
            spawn_in_terminal(*args, **kwargs)
        return captured

    def test_detaches_with_new_session(self):
        captured = self._capture("alacritty", ["./ait", "sync"])
        self.assertTrue(captured["kwargs"].get("start_new_session"))

    def test_argv_wraps_cmd_after_separator(self):
        captured = self._capture("foot", ["wrapper", "invoke", "pick", "42"])
        self.assertEqual(
            captured["argv"],
            ["foot", "--", "wrapper", "invoke", "pick", "42"],
        )

    def test_forwards_popen_kwargs(self):
        captured = self._capture(
            "kitty", ["./ait", "sync"], cwd="/some/project/root",
        )
        self.assertEqual(captured["kwargs"].get("cwd"), "/some/project/root")
        # Detachment is still applied alongside forwarded kwargs.
        self.assertTrue(captured["kwargs"].get("start_new_session"))

    def test_empty_cmd_still_detaches(self):
        captured = self._capture("xterm", [])
        self.assertEqual(captured["argv"], ["xterm", "--"])
        self.assertTrue(captured["kwargs"].get("start_new_session"))


if __name__ == "__main__":
    unittest.main()
