"""The `ait trails` focus mailbox against a REAL tmux server (t1957_2).

`test_trails_focus_writer.py` pins the helpers' argv and parsing against a
stubbed gateway; this file pins the tmux behaviour that parsing relies on,
which a stub can only assume:

* an unset pane user option reads back as an empty request, and a MISSING
  pane — which `show-options -q` and `display-message` both answer with rc 0
  and no output — reads as a failure, not as "no request";
* `#{@aitask_trails_app}` in a `list-panes -s` format names each pane's own
  stamp, so the writer picks the stamped pane and only it;
* the request option survives the read (nobody clears it) and the stamp is
  removed by `unmark_trails_receiver`;
* `pane_on_gateway_server` accepts the server's own socket and refuses another.

Runs on a throwaway server: `AITASKS_TMUX_SOCKET` names a private socket under
a short private `TMUX_TMPDIR`, and `agent_launch_utils._TMUX` is rebuilt inside
that environment (the import-time client is cached — see
tests/lib/tmux_socket_containment.py). Skipped when tmux is not installed.

Run: ~/.aitask/venv/bin/python -m pytest tests/test_trails_focus_mailbox_live.py -q
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

HANDLE = "art:trail-live"
SESSION = "t1957probe"


@unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
class LiveMailboxTests(unittest.TestCase):

    def setUp(self):
        # Short on purpose: a unix socket path is capped near 108 bytes.
        self.tmpdir = tempfile.mkdtemp(prefix="ait1957_", dir="/tmp")
        self.addCleanup(shutil.rmtree, self.tmpdir, True)
        env = patch.dict(os.environ, {"TMUX_TMPDIR": self.tmpdir,
                                      "AITASKS_TMUX_SOCKET": "ait1957"})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("TMUX", None)
        os.environ.pop("TMUX_PANE", None)
        self.client = TmuxClient()
        self.assertEqual(self.client.socket_args, ["-L", "ait1957"])
        swap = patch.object(alu, "_TMUX", self.client)
        swap.start()
        self.addCleanup(swap.stop)
        rc, _ = self.client.run(["new-session", "-d", "-s", SESSION,
                                 "-x", "80", "-y", "24", "sleep 600"])
        self.assertEqual(rc, 0, "could not start the private tmux server")
        self.addCleanup(self.client.run, ["kill-server"])
        rc, _ = self.client.run(["new-window", "-t", f"={SESSION}:",
                                 "sleep 600"])
        self.assertEqual(rc, 0)
        rc, out = self.client.run(["list-panes", "-s", "-t", f"={SESSION}:",
                                   "-F", "#{pane_id}"])
        self.panes = out.split()
        self.assertEqual(len(self.panes), 2, out)

    def test_unset_request_is_empty_and_missing_pane_is_a_failure(self):
        first = self.panes[0]
        self.assertEqual(alu.read_trails_focus_request(first), "")
        self.assertIsNone(alu.read_trails_focus_request("%9999"))
        # The control: the probe these reads replace cannot tell them apart.
        self.assertEqual(
            self.client.run(["show-options", "-p", "-q", "-v", "-t", "%9999",
                             alu.TRAILS_FOCUS_OPTION]), (0, ""))

    def test_writer_targets_the_stamped_pane_and_the_request_persists(self):
        first, second = self.panes
        self.assertTrue(alu.mark_trails_receiver(second))   # our live pid
        ok, err = alu.launch_or_focus_trails(SESSION, Path(self.tmpdir),
                                             HANDLE)
        self.assertEqual((ok, err), (True, None))
        self.assertEqual(alu.read_trails_focus_request(first), "")
        value = alu.read_trails_focus_request(second)
        parsed = alu.parse_trails_focus_request(value)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed[1], HANDLE)
        # Reading does not consume it.
        self.assertEqual(alu.read_trails_focus_request(second), value)
        rc, out = self.client.run(["display-message", "-p", "-t", second,
                                   "#{pane_active}"])
        self.assertEqual(out.strip(), "1")

    def test_unstamp_removes_only_the_stamp(self):
        pane = self.panes[0]
        self.assertTrue(alu.mark_trails_receiver(pane))
        self.client.run(["set-option", "-p", "-t", pane,
                         alu.TRAILS_FOCUS_OPTION, f"{'a' * 32} {HANDLE}"])
        rc, out = self.client.run(["list-panes", "-s", "-t", f"={SESSION}:",
                                   "-F", "#{pane_id} #{@aitask_trails_app}"])
        self.assertIn(f"{pane} {os.getpid()}", out.splitlines())
        self.assertTrue(alu.unmark_trails_receiver(pane))
        rc, out = self.client.run(["list-panes", "-s", "-t", f"={SESSION}:",
                                   "-F", "#{pane_id} #{@aitask_trails_app}"])
        self.assertIn(f"{pane} ", out.splitlines())
        self.assertEqual(alu.read_trails_focus_request(pane),
                         f"{'a' * 32} {HANDLE}")

    def test_no_receiver_opens_a_trails_window(self):
        # A controlled `./ait` in the project root: it records its argv and
        # stays alive, so the window is still there when it is looked for (a
        # missing or failing command would close it, racing the assertion).
        root = Path(self.tmpdir) / "proj"
        root.mkdir()
        argv_file = root / "argv.txt"
        stub = root / "ait"
        stub.write_text('#!/bin/sh\n'
                        'printf "%s\\n" "$@" > argv.tmp && mv argv.tmp argv.txt\n'
                        'exec sleep 600\n')
        stub.chmod(0o755)
        ok, err = alu.launch_or_focus_trails(SESSION, root, HANDLE)
        self.assertEqual((ok, err), (True, None))
        deadline = time.monotonic() + 10
        while not argv_file.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(argv_file.read_text().splitlines(),
                         ["trails", "--trail", HANDLE])
        rc, out = self.client.run(["list-windows", "-t", f"={SESSION}",
                                   "-F", "#{window_name}"])
        self.assertIn("trails", out.split())

    def test_server_identity_against_the_real_socket(self):
        rc, sock = self.client.run(["display-message", "-p", "-t",
                                    self.panes[0], "#{socket_path}"])
        sock = sock.strip()
        self.assertTrue(sock)
        self.assertTrue(alu.pane_on_gateway_server(self.panes[0],
                                                   f"{sock},1,0"))
        self.assertFalse(alu.pane_on_gateway_server(
            self.panes[0], f"{self.tmpdir}/other,1,0"))
        self.assertFalse(alu.pane_on_gateway_server("%9999", f"{sock},1,0"))


if __name__ == "__main__":
    unittest.main()
