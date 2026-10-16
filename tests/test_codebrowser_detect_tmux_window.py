"""`CodeBrowserApp._detect_tmux_window` reads THIS pane's window (t2039).

An untargeted `tmux display-message -p '#{window_index}'` resolves to the
session's CURRENT window, not the window the calling pane is in (measured on
tmux 3.8). The probe pre-selects the "split into the caller's window" target of
the create-task dialog, so it must name `$TMUX_PANE`.

`subprocess.run` is patched; no tmux call leaves the test.

Run: python3 tests/test_codebrowser_detect_tmux_window.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "codebrowser"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import codebrowser_app as cba  # noqa: E402


def _ok(stdout: str = "4\n") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


class DetectTmuxWindowTests(unittest.TestCase):

    def _detect(self, env: dict) -> tuple[str | None, list]:
        with patch.dict(os.environ, env, clear=False), \
             patch.object(cba.subprocess, "run", return_value=_ok()) as run:
            for key in ("TMUX", "TMUX_PANE"):
                if key not in env:
                    os.environ.pop(key, None)
            result = cba.CodeBrowserApp._detect_tmux_window()
        return result, [c.args[0] for c in run.call_args_list]

    def test_targets_the_own_pane(self):
        result, calls = self._detect({"TMUX": "/tmp/s,1,0", "TMUX_PANE": "%7"})
        self.assertEqual("4", result)
        self.assertEqual(
            [["tmux", "display-message", "-p", "-t", "%7", "#{window_index}"]], calls)

    def test_without_a_pane_id_the_read_stays_untargeted(self):
        result, calls = self._detect({"TMUX": "/tmp/s,1,0"})
        self.assertEqual("4", result)
        self.assertEqual([["tmux", "display-message", "-p", "#{window_index}"]], calls)

    def test_outside_tmux_nothing_runs(self):
        result, calls = self._detect({"TMUX_PANE": "%7"})
        self.assertIsNone(result)
        self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
