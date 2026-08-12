"""Live-terminal pin: a fresh codebrowser must answer its own `q` (t1495).

`CodeBrowserApp` set no `AUTO_FOCUS`, so it inherited ``App.AUTO_FOCUS = "*"``
— applied in ``Screen._compose``, before ``on_mount``. In the non-git-repo
compose branch (``get_project_root()`` raises, so the sidebar is a bare
``Container`` holding one non-focusable ``Static``) the first focusable widget
on the screen is ``Input#file_search_input``. Every non-``priority`` binding,
``q`` (Quit) included, then arrived as *search text*.

Reproduced in a tmux pane before the fix: a focus trace showed auto-focus
landing on the Input, and after a bare ``q`` ``#{pane_current_command}`` was
still the interpreter with a literal ``q`` sitting in the search box. Same
defect the board carried in t1491.

**What this test can and cannot fail on.** It pins the *composite*,
user-visible defect — a codebrowser that cannot be quit — and fails only when
**both** layers of the fix are absent:

* remove ``CodeBrowserScreen.AUTO_FOCUS = ""`` alone and it still passes: the
  deferred claim lands ~240ms in, long before any key this test can deliver, so
  focus is off the Input by then;
* remove ``CodeBrowserApp._claim_startup_focus`` alone and it still passes too:
  with auto-focus disabled the screen is merely *unfocused*, and an unfocused
  screen routes keys straight to the App bindings, so ``q`` quits.

Each layer is therefore pinned individually — and headlessly — in
``tests/test_codebrowser_startup_focus.py``. Do not "strengthen" this file by
asserting a layer it structurally cannot see.

Unlike t1491's board, the headless module *can* reproduce this one: measured at
Textual 8.2.7, ``App.run_test`` picks ``Input#file_search_input`` in the non-git
branch exactly as a real terminal does — that branch has too few focusable
widgets for the drivers to diverge. This module ships anyway, because the real
terminal is the ground truth for a defect defined by what a keystroke does.

Isolation follows `tests/test_board_startup_focus_live.py`: a throwaway
per-process socket, so `kill-server` can only reach the server we started, and
an interactive **shell** in the pane (no command argument to `new-session`) so
keys can be sent to it. Verified safe when nested inside the user's own tmux
session — `new-session -d` on a private socket starts a separate server.
Raw `tmux` is correct in `tests/`; `tests/test_no_raw_tmux.sh` scopes its guard
to `.aitask-scripts/`.

The fixture is deliberately **not** a git repo: that is the branch that carries
the defect. It is also never the real repo, so nothing here touches
`.git/index.lock`.

Skip-vs-fail: `SkipTest` only for environment unavailability (no tmux binary,
no session, no pane). Once a pane exists, a codebrowser that will not quit is a
FAILURE.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SOCKET = f"ait_t1495_cbfocus_{os.getpid()}"
#: Two sessions on one throwaway server: the non-git branch carries the startup
#: defect, while the hot-handoff route needs a real repo to have a file to open.
SESSION_NOGIT = "t1495_cb_nogit"
SESSION_GIT = "t1495_cb_git"
PANE_WIDTH = 200
PANE_HEIGHT = 50

#: Boot budget, matching the other live modules: a cold codebrowser settles in
#: ~2s and the ceiling is generous so a loaded machine does not flake.
#: Exceeding it is a FAILURE, not a skip.
BOOT_TIMEOUT_S = 45.0
#: Budget for the pane to fall back to the shell after `q`.
QUIT_TIMEOUT_S = 20.0
POLL_INTERVAL_S = 0.25

#: What this compose branch renders — see `codebrowser_app.py`'s `compose()`
#: `RuntimeError` arm. Doubles as the proof that the fixture really drove the
#: non-git branch rather than finding a repo somewhere above it.
BOOT_MARKER = "not inside a git repository"

#: The search box's placeholder. Present only while the box is empty, so its
#: disappearance is what a swallowed keystroke looks like.
SEARCH_PLACEHOLDER = "Search files..."

#: What the git fixture renders once booted (the sidebar's own header).
GIT_BOOT_MARKER = "Recent Files"

#: The hot-handoff request and the info-bar text that proves it landed.
#: `alpha.py` is 8 lines and line 4 is requested, so "Line 4/8" is neither the
#: default cursor (line 1) nor a clamp to EOF — the assertion discriminates.
HANDOFF_REQUEST = "src/alpha.py:4"
HANDOFF_EVIDENCE = "alpha.py — 8 lines | Line 4/8"

#: `_consume_and_apply_focus` is polled once per second (`set_interval(1.0, …)`),
#: then `_apply_focus_range` lands behind a 0.15s timer. Budget several polls so
#: a loaded machine does not flake.
HANDOFF_TIMEOUT_S = 20.0

ALPHA_SOURCE = (
    "def alpha():\n"
    "    a = 1\n"
    "    b = 2\n"
    "    c = 3\n"
    "    d = 4\n"
    "    e = 5\n"
    "    return a + b + c + d + e\n"
    "# trailing\n"
)


def _tmux(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["tmux", "-L", SOCKET, *args],
                          capture_output=True, text=True, check=False)


@unittest.skipUnless(shutil.which("tmux"), "tmux not available")
class CodebrowserStartupFocusLiveTests(unittest.TestCase):
    """A codebrowser launched outside a git repo quits on a bare `q`."""

    tmpdir: Path
    fixture_nogit: Path
    fixture_git: Path
    pane_nogit: str
    pane_git: str

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import tempfile

        tmp = tempfile.TemporaryDirectory(prefix="aitask_t1495_cb_live_")
        cls.addClassCleanup(tmp.cleanup)
        cls.tmpdir = Path(tmp.name)
        cls.fixture_nogit = cls._build_fixture(cls.tmpdir / "nogit", want_git=False)
        cls.fixture_git = cls._build_fixture(cls.tmpdir / "withgit", want_git=True)

        first = True
        for session, fixture in ((SESSION_NOGIT, cls.fixture_nogit),
                                 (SESSION_GIT, cls.fixture_git)):
            res = subprocess.run(
                ["tmux", "-L", SOCKET, "new-session", "-d", "-s", session,
                 "-x", str(PANE_WIDTH), "-y", str(PANE_HEIGHT), "-c", str(fixture)],
                capture_output=True, text=True, check=False,
            )
            if res.returncode != 0:
                raise unittest.SkipTest(
                    f"tmux new-session failed: {res.stderr.strip()}")
            if first:
                # Registered after the first session exists, so a later failure
                # still tears the server down.
                cls.addClassCleanup(lambda: _tmux("kill-server"))
                first = False

            panes = _tmux("list-panes", "-t", session, "-F", "#{pane_id}")
            pane_ids = [p for p in panes.stdout.split() if p]
            if not pane_ids:
                raise unittest.SkipTest(f"no pane in session {session}")
            if session == SESSION_NOGIT:
                cls.pane_nogit = pane_ids[0]
            else:
                cls.pane_git = pane_ids[0]

    # --- fixture ------------------------------------------------------------

    @staticmethod
    def _build_fixture(root: Path, want_git: bool) -> Path:
        """A minimal standalone `ait` project, with or without a git repo.

        `ait` cds to its own directory (`ait:4-9`), so a copy of `ait` beside a
        `.aitask-scripts` SYMLINK is enough: cwd resolves inside this tree while
        the 13 MB script tree is not copied. The symlink is mandatory — a `cp -r`
        snapshot silently runs stale code after the next edit (t1491).

        `want_git=False` is what makes `get_project_root()` raise and drives the
        compose branch carrying the startup-focus defect. `want_git=True` gives
        the hot-handoff test a real repo with a file to open.
        """
        root.mkdir(parents=True)
        shutil.copy2(REPO_ROOT / "ait", root / "ait")
        (root / "ait").chmod(0o755)
        (root / ".aitask-scripts").symlink_to(REPO_ROOT / ".aitask-scripts")

        meta = root / "aitasks" / "metadata"
        meta.mkdir(parents=True)
        (meta / "project_config.yaml").write_text(
            "project:\n  name: aitasks\n", encoding="utf-8")

        if want_git:
            (root / "src").mkdir()
            (root / "src" / "alpha.py").write_text(ALPHA_SOURCE, encoding="utf-8")
            for args in (["init", "-q"],
                         ["config", "user.email", "t1495@example.invalid"],
                         ["config", "user.name", "t1495"],
                         ["add", "-A"],
                         ["commit", "-qm", "fixture"]):
                subprocess.run(["git", "-C", str(root), *args],
                               check=True, capture_output=True)
        return root

    # --- pane helpers -------------------------------------------------------

    def _capture(self, pane: str) -> str:
        return _tmux("capture-pane", "-p", "-t", pane).stdout

    def _pane_command(self, pane: str) -> str:
        return _tmux("display-message", "-p", "-t", pane,
                     "#{pane_current_command}").stdout.strip()

    def _send(self, pane: str, *keys: str) -> None:
        _tmux("send-keys", "-t", pane, *keys)

    def _search_region(self, capture: str) -> str:
        """The rows around the search box — where a swallowed key shows up.

        A window rather than a single row: the box is drawn as a bordered
        widget, so a swallowed `q` lands on the row *below* the one carrying
        the placeholder or the branch marker. Returning only the anchor row
        would show the failure without its evidence.
        """
        lines = capture.splitlines()
        for i, line in enumerate(lines):
            if SEARCH_PLACEHOLDER in line or BOOT_MARKER in line:
                return "\n".join(x.rstrip() for x in lines[i:i + 4])
        return "<search box not found on screen>"

    def _launch(self, pane: str, marker: str, socket_env: bool = False) -> str:
        # stderr is deliberately left on the tty: Textual writes rendered frames
        # there, and redirecting it leaves capture-pane blank (t1319).
        #
        # AITASKS_TMUX_SOCKET must be passed as an `env` PREFIX, not via
        # `tmux set-environment`: the session environment is applied to panes
        # tmux spawns itself, and this pane's shell is already running, so a
        # command typed with send-keys inherits none of it. Without it the
        # app's gateway calls would target the shared `ait` socket instead of
        # this throwaway server.
        prefix = f"env AITASKS_TMUX_SOCKET='{SOCKET}' " if socket_env else ""
        self._send(pane, f"{prefix}./ait codebrowser", "Enter")
        deadline = time.monotonic() + BOOT_TIMEOUT_S
        while time.monotonic() < deadline:
            capture = self._capture(pane)
            if marker in capture:
                # One more interval so the deferred focus claim has landed and
                # row 0 is not caught mid-frame.
                time.sleep(POLL_INTERVAL_S * 4)
                return self._capture(pane)
            time.sleep(POLL_INTERVAL_S)
        self.fail(f"codebrowser did not boot within {BOOT_TIMEOUT_S}s.\n"
                  f"--- pane ---\n{self._capture(pane)}")

    def _wait_for_shell(self, pane: str) -> None:
        """Poll until the pane leaves the interpreter, else FAIL with the cause.

        The message carries the search row, not just a timeout: a bare "still
        python" says the app did not quit, while the search row says WHY — the
        keystroke is sitting in the search box.
        """
        deadline = time.monotonic() + QUIT_TIMEOUT_S
        while time.monotonic() < deadline:
            command = self._pane_command(pane)
            if command and command not in ("python", "python3", "pypy", "pypy3"):
                return
            time.sleep(POLL_INTERVAL_S)
        capture = self._capture(pane)
        self.fail(
            f"`q` did not quit the codebrowser within {QUIT_TIMEOUT_S}s — "
            f"pane_current_command is still {self._pane_command(pane)!r}. The "
            "keystroke was swallowed by the search box instead of reaching the "
            "`q` binding (t1495).\n"
            f"--- search box region ---\n{self._search_region(capture)}\n"
            f"--- pane ---\n{capture}")

    # --- the pins -----------------------------------------------------------

    def test_bare_q_quits_a_codebrowser_launched_outside_a_git_repo(self):
        pane = self.pane_nogit
        capture = self._launch(pane, BOOT_MARKER)
        self.assertIn(
            BOOT_MARKER, capture,
            f"the fixture did not drive the non-git compose branch:\n{capture}")

        # The defect: with focus left on `#file_search_input`, this `q` becomes
        # search text and the app keeps running.
        self._send(pane, "q")
        self._wait_for_shell(pane)

        # The keystroke reached the binding rather than the box. Asserted on the
        # post-quit capture too, so a pane that exited for some *other* reason
        # (a crash, say) is not mistaken for the key having worked.
        final = self._capture(pane)
        self.assertNotIn(
            f"{SEARCH_PLACEHOLDER}\n", final,
            "the app is gone but the search box is still on screen")

    def test_hot_handoff_still_lands_its_file_and_line_after_the_claim(self):
        """`AITASK_CODEBROWSER_FOCUS` survives the new startup focus claim.

        The second entry route into the focus mechanism, and the one the
        headless module structurally cannot reach: `_consume_codebrowser_focus`
        returns `None` without a real `self._tmux_session`, so every headless
        assertion about it would pass vacuously against an early return.

        It matters to t1495 because `on_mount` queues
        `call_after_refresh(self._consume_and_apply_focus)` on the **same
        refresh** as `_claim_startup_focus` — and the request lands through a
        further `set_timer` in `_apply_focus_range`. A claim that ran in the
        wrong order, or that displaced the viewer state those callbacks write,
        would break this route while leaving the cold-launch `--focus` flag
        working.

        Driven through the documented seam — the real tmux session env var the
        production writer sets — not a stub.
        """
        pane = self.pane_git
        capture = self._launch(pane, GIT_BOOT_MARKER, socket_env=True)
        self.assertIn(GIT_BOOT_MARKER, capture,
                      f"the git fixture did not boot its sidebar:\n{capture}")
        self.assertNotIn(
            HANDOFF_EVIDENCE, capture,
            "the fixture already showed the requested file before the handoff "
            "— this test would pass without the mechanism working")

        _tmux("set-environment", "-t", SESSION_GIT,
              "AITASK_CODEBROWSER_FOCUS", HANDOFF_REQUEST)

        deadline = time.monotonic() + HANDOFF_TIMEOUT_S
        landed = ""
        while time.monotonic() < deadline:
            landed = self._capture(pane)
            if HANDOFF_EVIDENCE in landed:
                break
            time.sleep(POLL_INTERVAL_S)
        else:
            self.fail(
                f"the hot handoff {HANDOFF_REQUEST!r} did not land within "
                f"{HANDOFF_TIMEOUT_S}s — expected {HANDOFF_EVIDENCE!r} in the "
                "info bar. Either _consume_and_apply_focus never fired, or "
                "_apply_focus_range did not set the cursor.\n"
                f"--- pane ---\n{landed}")

        # The app is still usable afterwards: the handoff must not have left the
        # keyboard somewhere that swallows `q`.
        self._send(pane, "q")
        self._wait_for_shell(pane)


if __name__ == "__main__":
    unittest.main()
