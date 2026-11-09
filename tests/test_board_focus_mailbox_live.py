"""The `ait board` focus mailbox against a REAL tmux server (t2211_3).

The board twin of `test_trails_focus_mailbox_live.py`, on the generalized
primitives (`read_pane_request` & co.). `test_board_focus_writer.py` pins the
argv against a stub; this file pins the tmux behaviour that argv relies on:

* an unset `@aitask_board_focus` reads back as an empty request, and a MISSING
  pane -- answered with rc 0 and no output -- reads as a failure;
* `#{@aitask_board_app}` in a `list-panes -s` format names each pane's own
  stamp, so `launch_or_focus_board` writes only to the stamped pane (and a
  trails stamp on another pane is not a board receiver);
* the request survives the read, and unmark removes only the stamp;
* with no receiver and no `board` window, a `board` window runs
  `./ait board --focus <id>`; with a `board` window but no receiver, that
  window is selected and nothing new is started.

Runs on a throwaway server: `AITASKS_TMUX_SOCKET` names a private socket under
a short private `TMUX_TMPDIR`, `agent_launch_utils._TMUX` is swapped for a
client built inside that environment, and the server starts with
`-f /dev/null`. Skipped when tmux is not installed.

Run: ~/.aitask/venv/bin/python -m pytest tests/test_board_focus_mailbox_live.py -q
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_launch_utils as alu  # noqa: E402
from tmux_exec import TmuxClient  # noqa: E402

SESSION = "t2211probe"


@unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
class LiveBoardMailboxTests(unittest.TestCase):

    def setUp(self):
        # Short on purpose: a unix socket path is capped near 108 bytes.
        self.tmpdir = tempfile.mkdtemp(prefix="ait2211_", dir="/tmp")
        self.addCleanup(shutil.rmtree, self.tmpdir, True)
        env = patch.dict(os.environ, {"TMUX_TMPDIR": self.tmpdir,
                                      "AITASKS_TMUX_SOCKET": "ait2211"})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("TMUX", None)
        os.environ.pop("TMUX_PANE", None)
        self.client = TmuxClient()
        self.assertEqual(self.client.socket_args, ["-L", "ait2211"])
        swap = patch.object(alu, "_TMUX", self.client)
        swap.start()
        self.addCleanup(swap.stop)
        rc, _ = self.client.run(["-f", "/dev/null", "new-session", "-d",
                                 "-s", SESSION, "-x", "80", "-y", "24", "sleep 600"])
        self.assertEqual(rc, 0, "could not start the private tmux server")
        self.addCleanup(self.client.run, ["kill-server"])
        rc, _ = self.client.run(["new-window", "-t", f"={SESSION}:", "sleep 600"])
        self.assertEqual(rc, 0)
        rc, out = self.client.run(["list-panes", "-s", "-t", f"={SESSION}:",
                                   "-F", "#{pane_id}"])
        self.panes = out.split()
        self.assertEqual(len(self.panes), 2, out)

    def window_names(self) -> list:
        _rc, out = self.client.run(["list-windows", "-t", f"={SESSION}",
                                    "-F", "#{window_name}"])
        return out.split()

    def test_unset_request_is_empty_and_missing_pane_is_a_failure(self):
        self.assertEqual(alu.read_board_focus_request(self.panes[0]), "")
        self.assertIsNone(alu.read_board_focus_request("%9999"))
        self.assertEqual(
            self.client.run(["show-options", "-p", "-q", "-v", "-t", "%9999",
                             alu.BOARD_FOCUS_OPTION]), (0, ""),
            "control: the probe these reads replace cannot tell them apart")

    def test_writer_targets_only_the_stamped_pane_and_the_request_persists(self):
        first, second = self.panes
        # A TRAILS receiver on the first pane is not a board receiver.
        self.assertTrue(alu.mark_trails_receiver(first))
        self.assertTrue(alu.mark_board_receiver(second))
        names_before = self.window_names()
        self.assertEqual(alu.launch_or_focus_board(SESSION, Path(self.tmpdir), "12_3"),
                         (True, None))
        self.assertEqual(alu.read_board_focus_request(first), "")
        value = alu.read_board_focus_request(second)
        parsed = alu.parse_board_focus_request(value)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed[1], "12_3")
        self.assertEqual(alu.read_board_focus_request(second), value, "not consumed")
        _rc, out = self.client.run(["display-message", "-p", "-t", second,
                                    "#{pane_active}"])
        self.assertEqual(out.strip(), "1")
        self.assertEqual(self.window_names(), names_before, "no window was started")

    def test_unstamp_removes_only_the_stamp(self):
        pane = self.panes[0]
        self.assertTrue(alu.mark_board_receiver(pane))
        self.client.run(["set-option", "-p", "-t", pane, alu.BOARD_FOCUS_OPTION,
                         f"{'a' * 32} 7"])
        _rc, out = self.client.run(["list-panes", "-s", "-t", f"={SESSION}:",
                                    "-F", "#{pane_id} #{@aitask_board_app}"])
        self.assertIn(f"{pane} {os.getpid()}", out.splitlines())
        self.assertTrue(alu.unmark_board_receiver(pane))
        _rc, out = self.client.run(["list-panes", "-s", "-t", f"={SESSION}:",
                                    "-F", "#{pane_id} #{@aitask_board_app}"])
        self.assertIn(f"{pane} ", out.splitlines())
        self.assertEqual(alu.read_board_focus_request(pane), f"{'a' * 32} 7")

    def test_no_board_opens_one_with_the_focus_argv(self):
        root = Path(self.tmpdir) / "proj"
        root.mkdir()
        argv_file = root / "argv.txt"
        stub = root / "ait"
        stub.write_text('#!/bin/sh\n'
                        'printf "%s\\n" "$@" > argv.tmp && mv argv.tmp argv.txt\n'
                        'exec sleep 600\n')
        stub.chmod(0o755)
        self.assertEqual(alu.launch_or_focus_board(SESSION, root, "12"), (True, None))
        deadline = time.monotonic() + 10
        while not argv_file.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(argv_file.read_text().splitlines(), ["board", "--focus", "12"])
        self.assertIn("board", self.window_names())

    def test_a_board_window_without_a_receiver_is_selected_not_doubled(self):
        rc, _ = self.client.run(["new-window", "-d", "-t", f"={SESSION}:", "-n", "board",
                                 "sleep 600"])
        self.assertEqual(rc, 0)
        ok, warning = alu.launch_or_focus_board(SESSION, Path(self.tmpdir), "12")
        self.assertTrue(ok)
        self.assertIn("cannot take focus requests", warning)
        self.assertEqual(self.window_names().count("board"), 1)
        _rc, out = self.client.run(["display-message", "-p", "-t", f"={SESSION}:",
                                    "#{window_name}"])
        self.assertEqual(out.strip(), "board", "the existing board window is selected")


if __name__ == "__main__":
    unittest.main()
