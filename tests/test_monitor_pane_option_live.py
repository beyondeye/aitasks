"""`TmuxMonitor.get_pane_option` against a REAL tmux server (t1971).

`test_shadow_seam.py::GetPaneOptionContractTests` pins the method's argv and
branching against a scripted gateway; this file pins the tmux behaviour that
branching relies on, which a stub can only assume. Every read case runs twice:
against the async ``get_pane_option`` and its sync twin
``get_pane_option_sync`` (t2057, the pick flows' kill-time frozen re-check):

* a set pane option reads back ``(True, value)`` and an unset one ``(True, "")``;
* a MISSING pane — which ``show-options -q`` answers with rc 0 and no output,
  exactly like an unset option — reads ``(False, "")``, a failed read, never a
  verified "unset";
* the read stays **pane-local**: a window-scoped value does not leak into it,
  although a ``#{@opt}`` format would return the inherited one;
* end to end, ``compute_shadow_staleness`` on a vanished shadow pane is
  ``(None, None)`` ("preserve"), not ``(False, None)`` ("never analyzed").

Runs on a throwaway server: ``AITASKS_TMUX_SOCKET`` names a private socket under
a short private ``TMUX_TMPDIR``, and the monitor is built inside that
environment because its ``TmuxClient`` resolves the socket once, at
construction. The server starts with ``-f /dev/null`` so the developer's tmux
config cannot add panes or options. Skipped when tmux is not installed.

Run: ~/.aitask/venv/bin/python -m pytest tests/test_monitor_pane_option_live.py -q
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from monitor.monitor_core import TmuxMonitor, compute_shadow_staleness  # noqa: E402

SOCKET = "ait1971"
SESSION = "t1971probe"
OPTION = "@ait_t1971_opt"
MISSING = "%9999"


class _LivePaneOptionContract:
    """The private-server cases, shared by one sibling per reader (t2057).

    Subclasses implement `_read(pane)`. Running the cases once per reader IS
    the mechanism (allowlisted in `tests/test_collection_structure.py`).
    """

    def _read(self, pane: str) -> tuple[bool, str]:
        raise NotImplementedError

    def setUp(self):
        # Short on purpose: a unix socket path is capped near 108 bytes.
        self.tmpdir = tempfile.mkdtemp(prefix="ait1971_", dir="/tmp")
        self.addCleanup(shutil.rmtree, self.tmpdir, True)
        env = patch.dict(os.environ, {"TMUX_TMPDIR": self.tmpdir,
                                      "AITASKS_TMUX_SOCKET": SOCKET})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("TMUX", None)
        os.environ.pop("TMUX_PANE", None)
        self.mon = TmuxMonitor(session=SESSION)
        self.client = self.mon._tmux
        self.assertEqual(self.client.socket_args, ["-L", SOCKET])
        # `-f` is a global flag, read only by the command that starts the server.
        rc, _ = self.client.run(["-f", "/dev/null", "new-session", "-d",
                                 "-s", SESSION, "-x", "80", "-y", "24",
                                 "sleep 600"])
        self.assertEqual(rc, 0, "could not start the private tmux server")
        self.addCleanup(self.client.run, ["kill-server"])
        rc, out = self.client.run(["list-panes", "-s", "-t", f"={SESSION}:",
                                   "-F", "#{pane_id}"])
        panes = out.split()
        self.assertEqual(len(panes), 1, out)
        self.pane = panes[0]

    def test_set_option_reads_back(self):
        rc, _ = self.client.run(["set-option", "-p", "-t", self.pane,
                                 OPTION, "1000"])
        self.assertEqual(rc, 0)
        self.assertEqual(self._read(self.pane), (True, "1000"))

    def test_unset_option_on_a_live_pane_is_a_verified_empty(self):
        self.assertEqual(self._read(self.pane), (True, ""))

    def test_missing_pane_is_a_failed_read(self):
        self.assertEqual(self._read(MISSING), (False, ""))
        # The control: the probe alone answers a missing pane like an unset option.
        self.assertEqual(
            self.client.run(["show-options", "-p", "-q", "-v", "-t", MISSING,
                             OPTION]), (0, ""))

    def test_read_is_pane_local_not_inherited(self):
        rc, _ = self.client.run(["set-option", "-w", "-t", self.pane,
                                 OPTION, "win"])
        self.assertEqual(rc, 0)
        self.assertEqual(self._read(self.pane), (True, ""))
        # The control: a format read returns the inherited window value.
        rc, out = self.client.run(["display-message", "-p", "-t", self.pane,
                                   f"#{{{OPTION}}}"])
        self.assertEqual((rc, out.strip()), (0, "win"))

    def test_vanished_shadow_pane_preserves_staleness(self):
        self.assertEqual(
            asyncio.run(compute_shadow_staleness(self.mon, MISSING, self.pane,
                                                 3.0)),
            (None, None))


@unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
class LivePaneOptionTests(_LivePaneOptionContract, unittest.TestCase):
    """The async sibling — ``get_pane_option``."""

    def _read(self, pane: str) -> tuple[bool, str]:
        return asyncio.run(self.mon.get_pane_option(pane, OPTION))


@unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
class LivePaneOptionSyncTests(_LivePaneOptionContract, unittest.TestCase):
    """The sync sibling — ``get_pane_option_sync`` (t2057)."""

    def _read(self, pane: str) -> tuple[bool, str]:
        return self.mon.get_pane_option_sync(pane, OPTION)


if __name__ == "__main__":
    unittest.main()
