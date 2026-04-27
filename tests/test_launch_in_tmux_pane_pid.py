"""Tests for launch_in_tmux pane_pid capture (t675)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = REPO_ROOT / ".aitask-scripts" / "lib"

sys.path.insert(0, str(LIB_DIR))
import agent_launch_utils  # noqa: E402
from agent_launch_utils import (  # noqa: E402
    TmuxLaunchConfig,
    _parse_pane_pid,
    launch_in_tmux,
    tmux_session_target,
    tmux_window_target,
)


class TestParsePanePid(unittest.TestCase):
    def test_single_line(self):
        self.assertEqual(_parse_pane_pid("12345\n"), 12345)

    def test_no_trailing_newline(self):
        self.assertEqual(_parse_pane_pid("12345"), 12345)

    def test_empty(self):
        self.assertIsNone(_parse_pane_pid(""))

    def test_whitespace_only(self):
        self.assertIsNone(_parse_pane_pid("   \n"))

    def test_non_numeric(self):
        self.assertIsNone(_parse_pane_pid("not-a-pid\n"))

    def test_first_line_only(self):
        # tmux -P -F outputs one line per pane; we always take the first.
        self.assertEqual(_parse_pane_pid("99\n100\n"), 99)


class _FakeRunResult:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestLaunchInTmuxNewWindow(unittest.TestCase):
    def setUp(self):
        self.config = TmuxLaunchConfig(
            session="testsess", window="testwin",
            new_session=False, new_window=True,
        )

    def test_success_returns_pane_pid(self):
        with patch.object(subprocess, "run",
                          return_value=_FakeRunResult(0, "54321\n", "")):
            pid, err = launch_in_tmux("echo hi", self.config)
        self.assertEqual(pid, 54321)
        self.assertIsNone(err)

    def test_success_empty_stdout_returns_none_pid(self):
        # Launch succeeded but pid was uncapturable; runner should warn
        # and write 0.
        with patch.object(subprocess, "run",
                          return_value=_FakeRunResult(0, "", "")):
            pid, err = launch_in_tmux("echo hi", self.config)
        self.assertIsNone(pid)
        self.assertIsNone(err)

    def test_failure_returns_error(self):
        with patch.object(subprocess, "run",
                          return_value=_FakeRunResult(
                              1, "", "no server running\n")):
            pid, err = launch_in_tmux("echo hi", self.config)
        self.assertIsNone(pid)
        self.assertIsNotNone(err)
        self.assertIn("tmux new-window failed", err or "")

    def test_pid_format_in_argv(self):
        # The new-window command must include -P -F "#{pane_pid}".
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            return _FakeRunResult(0, "1\n", "")

        with patch.object(subprocess, "run", side_effect=fake_run):
            launch_in_tmux("echo hi", self.config)
        argv = captured["argv"]
        self.assertIn("-P", argv)
        idx = argv.index("-F")
        self.assertEqual(argv[idx + 1], "#{pane_pid}")


class TestLaunchInTmuxSplitWindow(unittest.TestCase):
    def setUp(self):
        self.config = TmuxLaunchConfig(
            session="testsess", window="testwin",
            new_session=False, new_window=False,
        )

    def test_success_returns_pane_pid(self):
        # split-window also issues a follow-up Popen for select-window.
        # We patch subprocess.run for the split-window call and
        # subprocess.Popen for the select-window call.
        with patch.object(subprocess, "run",
                          return_value=_FakeRunResult(0, "77777\n", "")), \
             patch.object(subprocess, "Popen") as fake_popen:
            pid, err = launch_in_tmux("echo hi", self.config)
        self.assertEqual(pid, 77777)
        self.assertIsNone(err)
        fake_popen.assert_called_once()

    def test_failure_returns_error(self):
        with patch.object(subprocess, "run",
                          return_value=_FakeRunResult(
                              1, "", "boom\n")), \
             patch.object(subprocess, "Popen"):
            pid, err = launch_in_tmux("echo hi", self.config)
        self.assertIsNone(pid)
        self.assertIn("tmux split-window failed", err or "")

    def test_pid_format_in_argv(self):
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            return _FakeRunResult(0, "1\n", "")

        with patch.object(subprocess, "run", side_effect=fake_run), \
             patch.object(subprocess, "Popen"):
            launch_in_tmux("echo hi", self.config)
        argv = captured["argv"]
        self.assertIn("-P", argv)
        idx = argv.index("-F")
        self.assertEqual(argv[idx + 1], "#{pane_pid}")


class TestLaunchInTmuxNewSession(unittest.TestCase):
    def setUp(self):
        self.config = TmuxLaunchConfig(
            session="testsess", window="testwin",
            new_session=True, new_window=True,
        )

    def test_success_queries_pane_pid(self):
        # new-session uses Popen + wait; pane pid is queried via a
        # follow-up subprocess.run("tmux list-panes …").
        class _FakePopen:
            returncode = 0
            stderr = None

            def wait(self):
                pass

        # Patch list-panes to return a known pid.
        # Also patch the optional switch-client Popen call (no-op).
        with patch.object(subprocess, "Popen", return_value=_FakePopen()), \
             patch.object(subprocess, "run",
                          return_value=_FakeRunResult(0, "42424\n", "")):
            # Drop TMUX env so switch-client branch is skipped (irrelevant
            # to pid capture but keeps the assertion simple).
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("TMUX", None)
                pid, err = launch_in_tmux("echo hi", self.config)
        self.assertEqual(pid, 42424)
        self.assertIsNone(err)

    def test_failure_returns_error(self):
        class _FakePopenErr:
            returncode = 1

            class _Stderr:
                def read(self):
                    return b"create-session failed"

            stderr = _Stderr()

            def wait(self):
                pass

        with patch.object(subprocess, "Popen", return_value=_FakePopenErr()):
            pid, err = launch_in_tmux("echo hi", self.config)
        self.assertIsNone(pid)
        self.assertIn("tmux new-session failed", err or "")


@unittest.skipIf(shutil.which("tmux") is None, "tmux not installed")
class TestLaunchInTmuxIntegration(unittest.TestCase):
    """Live tmux integration: spawn sleep, verify pid alive."""

    SESSION = "_t675_pid_integration"

    def setUp(self):
        # Tear down any pre-existing test session.
        subprocess.run(
            ["tmux", "kill-session", "-t", tmux_session_target(self.SESSION)],
            capture_output=True,
        )

    def tearDown(self):
        subprocess.run(
            ["tmux", "kill-session", "-t", tmux_session_target(self.SESSION)],
            capture_output=True,
        )

    def test_new_session_pane_pid_alive(self):
        config = TmuxLaunchConfig(
            session=self.SESSION, window="w0",
            new_session=True, new_window=True,
        )
        pid, err = launch_in_tmux("sleep 30", config)
        self.assertIsNone(err)
        self.assertIsNotNone(pid)
        # Give tmux a moment to fork-exec.
        time.sleep(0.2)
        try:
            os.kill(int(pid), 0)
        except ProcessLookupError:
            self.fail(f"pane pid {pid} not alive immediately after launch")

    def test_new_window_pane_pid_alive(self):
        # First create the session.
        cfg_session = TmuxLaunchConfig(
            session=self.SESSION, window="w0",
            new_session=True, new_window=True,
        )
        _, err = launch_in_tmux("sleep 30", cfg_session)
        self.assertIsNone(err)
        # Now add a window.
        cfg_window = TmuxLaunchConfig(
            session=self.SESSION, window="w1",
            new_session=False, new_window=True,
        )
        pid, err = launch_in_tmux("sleep 30", cfg_window)
        self.assertIsNone(err)
        self.assertIsNotNone(pid)
        time.sleep(0.2)
        try:
            os.kill(int(pid), 0)
        except ProcessLookupError:
            self.fail(f"pane pid {pid} not alive immediately after launch")


if __name__ == "__main__":
    unittest.main()
