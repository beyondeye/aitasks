"""Live-terminal pin: a fresh board must answer its own single-key bindings (t1491).

`KanbanApp` set no startup focus, so Textual's ``App.AUTO_FOCUS = "*"`` — applied
in ``Screen._compose``, before ``on_mount`` — claimed the first focusable widget
in the DOM: the ``#search_box`` Input. Every non-``priority`` binding, ``q``
(Quit) included, then arrived as *search text*, and whatever landed there hid
every card while the column headers kept their unfiltered counts.

That is how the incident was originally read as "relaunching `ait board` in the
same pane renders no task cards" (t1490 → t1491): the board had never quit. The
`q` meant to quit it, and the `./ait board` typed afterwards, both went into the
search box.

The fix has two layers, and this file pins one of them. `BoardScreen.AUTO_FOCUS`
stops the Input taking focus in the first place; `KanbanApp._claim_startup_focus`
then anchors focus on a card. Removing the *claim* fails this test. Removing the
AUTO_FOCUS guard does not — the claim still lands ~130ms in, well before any key
this test can send — so that layer is pinned structurally in
`tests/test_board_startup_focus.py`.

**This test exists because a headless one cannot fail on it.**
``Screen._update_auto_focus`` picks a different widget under different drivers —
measured on the same fixture at the same size, a real terminal picks
``Input#search_box`` and ``App.run_test`` picks ``HorizontalScroll#board_container``,
where `q` quits fine. `tests/test_board_startup_focus.py` pins the positive
contract headless; only a real pty reproduces the swallowed keystroke.

Isolation follows `tests/test_board_header_row_live.py`: a throwaway per-process
socket with `AITASKS_TMUX_SOCKET` exported into the pane, so the board's own
gateway calls stay on it and `kill-server` can only reach the server we started.
Verified safe when nested inside the user's own tmux session — `new-session -d`
on a private socket starts a separate server and tmux rewrites `TMUX` in the pane
it creates. Raw `tmux` is correct in `tests/`; `tests/test_no_raw_tmux.sh` scopes
its guard to `.aitask-scripts/`.

Unlike the header-row test, the pane runs an interactive **shell** (no command
argument to `new-session`) so keys can be sent to it and the board relaunched in
place. The board runs against a synthetic fixture project, never the real repo.

Skip-vs-fail: `SkipTest` only for environment unavailability (no tmux binary, no
session, no pane). Once a pane exists, a board that will not quit is a FAILURE.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests"))

from lib.board_fixture import serialize_frontmatter  # noqa: E402

SOCKET = f"ait_t1491_focus_{os.getpid()}"
SESSION = "t1491_startup_focus"
PANE_WIDTH = 200
PANE_HEIGHT = 50

#: Boot budget, matching `test_board_header_row_live.py`: a cold board settles in
#: ~3s and the ceiling is generous so a loaded machine does not flake. Exceeding
#: it is a FAILURE, not a skip.
BOOT_TIMEOUT_S = 45.0
#: Budget for the pane to fall back to the shell after `q`. Quitting is far
#: cheaper than booting, but the interpreter still has to tear the app down.
QUIT_TIMEOUT_S = 20.0
POLL_INTERVAL_S = 0.25

#: The card title asserted on. Derived from the fixture task's slug exactly as
#: `TaskCard` renders it (underscores become spaces).
CARD_TITLE = "startup focus alpha"

#: Fixture columns: two populated, one deliberately empty, so `(empty)` has a
#: known and stable occurrence count on a correctly rendered board.
_COLUMNS = [
    {"id": "now", "title": "Now", "color": "#FF5555"},
    {"id": "next", "title": "Next", "color": "#50FA7B"},
    {"id": "backlog", "title": "Backlog", "color": "#BD93F9"},
]
_TASKS = (
    ("9100", "now", 10, "startup_focus_alpha"),
    ("9101", "now", 20, "startup_focus_beta"),
    ("9102", "next", 10, "startup_focus_gamma"),
)
_META_ORDER = ["priority", "effort", "issue_type", "status"]
_META_BASE = {"priority": "medium", "effort": "low",
              "issue_type": "chore", "status": "Ready"}


def _tmux(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["tmux", "-L", SOCKET, *args],
                          capture_output=True, text=True, check=False)


@unittest.skipUnless(shutil.which("tmux"), "tmux not available")
class BoardStartupFocusLiveTests(unittest.TestCase):
    """A freshly launched board quits on a bare `q`, and relaunches cleanly."""

    tmpdir: Path
    fixture: Path
    pane: str

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import tempfile

        tmp = tempfile.TemporaryDirectory(prefix="aitask_t1491_live_")
        cls.addClassCleanup(tmp.cleanup)
        cls.tmpdir = Path(tmp.name)
        cls.fixture = cls._build_fixture(cls.tmpdir / "project")

        env = dict(os.environ, AITASKS_TMUX_SOCKET=SOCKET)
        res = subprocess.run(
            ["tmux", "-L", SOCKET, "new-session", "-d", "-s", SESSION,
             "-x", str(PANE_WIDTH), "-y", str(PANE_HEIGHT), "-c", str(cls.fixture)],
            capture_output=True, text=True, check=False, env=env,
        )
        if res.returncode != 0:
            raise unittest.SkipTest(f"tmux new-session failed: {res.stderr.strip()}")
        cls.addClassCleanup(lambda: _tmux("kill-server"))

        # The board's own gateway calls must stay on our socket, and the pane's
        # shell is already running, so set it in the SESSION environment (it is
        # inherited by the commands `send-keys` starts).
        _tmux("set-environment", "-t", SESSION, "AITASKS_TMUX_SOCKET", SOCKET)

        panes = _tmux("list-panes", "-t", SESSION, "-F", "#{pane_id}")
        pane_ids = [p for p in panes.stdout.split() if p]
        if not pane_ids:
            raise unittest.SkipTest("no pane in the fixture session")
        cls.pane = pane_ids[0]

    # --- fixture ------------------------------------------------------------

    @staticmethod
    def _build_fixture(root: Path) -> Path:
        """A minimal standalone `ait` project the board can be launched in.

        `ait` cds to its own directory (`ait:4-9`), so a copy of `ait` beside a
        `.aitask-scripts` SYMLINK is enough: cwd — and therefore the relative
        `TASK_DIR="aitasks"` — resolves inside this tree, while the 13 MB script
        tree is not copied.
        """
        root.mkdir(parents=True)
        shutil.copy2(REPO_ROOT / "ait", root / "ait")
        (root / "ait").chmod(0o755)
        (root / ".aitask-scripts").symlink_to(REPO_ROOT / ".aitask-scripts")

        meta = root / "aitasks" / "metadata"
        meta.mkdir(parents=True)
        (meta / "board_config.json").write_text(
            json.dumps({"columns": _COLUMNS,
                        "column_order": [c["id"] for c in _COLUMNS]}, indent=2),
            encoding="utf-8")
        # auto_refresh_minutes: 0 — no timer may repaint mid-assertion.
        (meta / "board_config.local.json").write_text(
            json.dumps({"settings": {"auto_refresh_minutes": 0,
                                     "collapsed_columns": [],
                                     "sync_on_refresh": False}}, indent=2),
            encoding="utf-8")
        (meta / "project_config.yaml").write_text(
            "project:\n  name: aitasks\n", encoding="utf-8")
        # A missing gate registry silently reclassifies gate-bearing tasks.
        shutil.copy2(REPO_ROOT / ".aitask-scripts" / "gates_reference.yaml",
                     meta / "gates.yaml")

        for task_id, col, idx, slug in _TASKS:
            data = dict(_META_BASE)
            data["boardcol"] = col
            data["boardidx"] = idx
            body = f"\n## Context\n\nSynthetic fixture task {task_id}.\n"
            (root / "aitasks" / f"t{task_id}_{slug}.md").write_text(
                serialize_frontmatter(data, body, list(_META_ORDER)),
                encoding="utf-8")
        return root

    # --- pane helpers -------------------------------------------------------

    def _capture(self) -> str:
        return _tmux("capture-pane", "-p", "-t", self.pane).stdout

    def _pane_command(self) -> str:
        return _tmux("display-message", "-p", "-t", self.pane,
                     "#{pane_current_command}").stdout.strip()

    def _send(self, *keys: str) -> None:
        _tmux("send-keys", "-t", self.pane, *keys)

    def _search_box_line(self, capture: str) -> str:
        """The filter row, which is where a swallowed keystroke shows up."""
        for line in capture.splitlines():
            if "All" in line and "Locked" in line:
                return line.strip()
        return "<filter row not found>"

    def _launch_board(self, label: str) -> str:
        self._send("./ait board", "Enter")
        deadline = time.monotonic() + BOOT_TIMEOUT_S
        while time.monotonic() < deadline:
            capture = self._capture()
            if "Task filter" in capture:
                # One more interval so row 0 is not caught mid-frame.
                time.sleep(POLL_INTERVAL_S)
                return self._capture()
            time.sleep(POLL_INTERVAL_S)
        self.fail(f"[{label}] board did not boot within {BOOT_TIMEOUT_S}s.\n"
                  f"--- pane ---\n{self._capture()}")

    def _wait_for_shell(self, label: str) -> None:
        """Poll until the pane leaves the interpreter, else FAIL with the cause.

        The failure message carries the filter row, not just a timeout: a bare
        "still python" says the board did not quit, while the filter row says
        WHY — the keystroke is sitting in the search box.
        """
        deadline = time.monotonic() + QUIT_TIMEOUT_S
        while time.monotonic() < deadline:
            command = self._pane_command()
            if command and command not in ("python", "python3", "pypy", "pypy3"):
                return
            time.sleep(POLL_INTERVAL_S)
        capture = self._capture()
        self.fail(
            f"[{label}] `q` did not quit the board within {QUIT_TIMEOUT_S}s — "
            f"pane_current_command is still {self._pane_command()!r}. "
            "The keystroke was swallowed by the search box instead of reaching "
            "the `q` binding (t1491).\n"
            f"--- filter row ---\n{self._search_box_line(capture)}\n"
            f"--- pane ---\n{capture}")

    # --- the pin ------------------------------------------------------------

    def test_bare_q_quits_then_the_board_relaunches_in_the_same_pane(self):
        capture = self._launch_board("first launch")
        self.assertIn(CARD_TITLE, capture,
                      f"first launch rendered no task cards:\n{capture}")
        self.assertEqual(capture.count("(empty)"), 1,
                         "expected exactly one genuinely empty column on a "
                         f"correctly rendered board:\n{capture}")

        # The defect: with focus left on `#search_box`, this `q` becomes search
        # text, the board keeps running, and every card is filtered away.
        self._send("q")
        self._wait_for_shell("bare q")

        capture = self._launch_board("relaunch in the same pane")
        self.assertIn(CARD_TITLE, capture,
                      f"relaunch rendered no task cards:\n{capture}")
        self.assertEqual(capture.count("(empty)"), 1,
                         f"relaunch shows filtered-out columns:\n{capture}")
        self.assertNotIn("(hidden by filter)", capture,
                         f"relaunch booted with an active filter:\n{capture}")

        # Leave the pane back at the shell. A bare `q` is deliberate: after the
        # fix no Escape is needed, and sending one here would not help anyway —
        # `send-keys Escape` immediately followed by `q` reaches the pty as a
        # single ESC-prefixed `alt+q`, which is bound to nothing.
        self._send("q")
        self._wait_for_shell("teardown quit")


if __name__ == "__main__":
    unittest.main()
