"""Live-terminal smoke test for the board's header row (t1278).

The freshness banner shipped invisible because every guard was headless. Under
`run_test()` the occluded `Header` reported `display=True`, `visible=True` and
a correct `region`, and appeared in the compositor's `visible_widgets` — so no
property assertion could have caught it. `tests/test_board_bytrail_view.py`
now asserts on the composited frame, which does catch it, but "the composited
frame" is still the app rendering into a buffer it controls.

This test is the independent ground truth: boot the real `ait board` in a real
tmux pane and read row 0 back with `capture-pane`. It is the only check here
that would survive a compositor-level mistake.

Isolation: a throwaway per-process socket, with `AITASKS_TMUX_SOCKET` exported
into the child so the board's own gateway calls stay on it. Neither the user's
default server nor the dedicated `ait` server is touched, and `kill-server`
only ever reaches our own. Raw `tmux` is correct in `tests/` —
`tests/test_no_raw_tmux.sh` scopes its guard to `.aitask-scripts/`.

`aidocs/framework/tui_conventions.md` warns that tmux-manipulating tests must
not run from inside the user's aitasks session. This one is safe there and was
verified nested: `new-session -d` on a private socket starts a separate server,
and tmux rewrites `TMUX` in the pane it creates, so the board never sees the
outer session. The teardown can therefore only reach the server we started.

The board is only observed: no keys are sent, and a full boot leaves
`aitasks/metadata/board_config.json` byte-identical.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SOCKET = f"ait_t1278_hdr_{os.getpid()}"
SESSION = "t1278_header_row"
PANE_WIDTH = 120
PANE_HEIGHT = 30

#: Boot budget. A cold board settles in ~3s here; the ceiling is generous so a
#: loaded machine does not flake, and exceeding it is a FAILURE (see the class
#: docstring on skip-vs-fail), not a skip.
BOOT_TIMEOUT_S = 45.0
POLL_INTERVAL_S = 0.25


def _tmux(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["tmux", "-L", SOCKET, *args],
                          capture_output=True, text=True, check=False)


@unittest.skipUnless(shutil.which("tmux"), "tmux not available")
class BoardHeaderRowLiveTests(unittest.TestCase):
    """Row 0 of a real board pane must carry the app title and sub_title.

    **Skip vs fail.** `SkipTest` is reserved for *environment unavailability*:
    no `tmux` binary, or a session/pane that never came into existence. Once a
    pane exists, a board that never renders is a startup crash or a blank
    board — precisely the regression this test exists to catch — so it fails
    with the final capture attached rather than skipping green.
    """

    pane_id: str | None = None

    @classmethod
    def setUpClass(cls):
        env = dict(os.environ, AITASKS_TMUX_SOCKET=SOCKET)
        res = subprocess.run(
            ["tmux", "-L", SOCKET, "new-session", "-d", "-s", SESSION,
             "-x", str(PANE_WIDTH), "-y", str(PANE_HEIGHT),
             "-c", str(REPO_ROOT), "./ait board"],
            capture_output=True, text=True, check=False, env=env,
        )
        if res.returncode != 0:
            raise unittest.SkipTest(
                f"could not start tmux session: {res.stderr.strip()}")
        panes = _tmux("list-panes", "-t", SESSION, "-F", "#{pane_id}")
        cls.pane_id = (panes.stdout.strip().splitlines() or [""])[0]
        if not cls.pane_id:
            raise unittest.SkipTest("could not resolve the board pane id")

    @classmethod
    def tearDownClass(cls):
        _tmux("kill-server")

    def _capture(self) -> str:
        return _tmux("capture-pane", "-p", "-t", self.pane_id or "").stdout

    def _wait_for_board(self) -> list[str]:
        """Poll until the board has painted, then return its rows.

        Settling is detected on the filter row rather than the header: the
        header is the thing under test, so waiting for it would turn the
        assertion below into a tautology (the poll would either find it and
        pass, or time out with a message about a missing header instead of a
        failed assertion about a wrong one).
        """
        deadline = time.monotonic() + BOOT_TIMEOUT_S
        out = ""
        while time.monotonic() < deadline:
            out = self._capture()
            if "Task filter" in out:
                # Painted. One more beat so row 0 is not caught mid-frame.
                time.sleep(POLL_INTERVAL_S)
                return self._capture().splitlines()
            time.sleep(POLL_INTERVAL_S)
        self.fail(
            f"board never rendered within {BOOT_TIMEOUT_S:g}s — startup crash "
            f"or blank board. Final capture:\n{out}")

    def test_header_row_is_drawn_in_a_real_pane(self):
        rows = self._wait_for_board()
        self.assertTrue(rows, "empty capture from a live board pane")
        row0 = rows[0]
        # The app title proves the Header owns row 0 at all...
        self.assertIn("aitasks board", row0,
                      f"header row not drawn in a real terminal: {row0!r}")
        # ...and sub_title proves the surface every banner writes to is the
        # one actually on screen. Pre-fix this row read ' Task filter'.
        self.assertIn("Auto-refresh", row0,
                      f"sub_title absent from the header row: {row0!r}")

    def test_filter_row_moved_below_the_header(self):
        """The filter row must still be drawn, one row down — not replaced."""
        rows = self._wait_for_board()
        self.assertNotIn("Task filter", rows[0],
                         "filter row is still occupying row 0")
        self.assertIn("Task filter", rows[1],
                      f"filter row not directly below the header: {rows[1]!r}")


if __name__ == "__main__":
    unittest.main()
