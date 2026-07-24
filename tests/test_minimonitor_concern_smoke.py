"""Live-tmux smoke for minimonitor's shadow concern capture path (t1187).

Every other concern test stubs ``_capture_shadow_text`` and feeds the parser a
synthetic string, so the whole suite can pass while the real pipeline still
produces no auto-offer — which is exactly how the t1170 item-#2 live failure
slipped through. This module exercises the real chain end-to-end:

    real tmux pane -> aitask_shadow_capture.sh -> _capture_shadow_text
        -> has_concern_block -> notify

Only the two tmux *lookups* are stubbed (which pane is the agent, which pane is
its shadow); the capture itself is the production code path.

**Not** covered here, and deliberately so — these stay live-only and are the
acceptance signal for the feature: the minimonitor ``e`` launch and its
``@aitask_shadow_target`` binding, the Codex CLI renderer's real wrapping at ~55
columns, and refresh-tick timing. The fixture pane substitutes hand-built text
for the renderer, so this proves the plumbing, not that Codex's output survives
it.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m unittest tests.test_minimonitor_concern_smoke
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

from monitor import minimonitor_app as mm  # noqa: E402

OPEN = "===AITASK-CONCERNS==="
CLOSE = "===END-CONCERNS==="

SOCKET = "ait_t1187_smoke"
SESSION = "t1187_concern_smoke"
PANE_WIDTH = 55      # the narrow width from the failing scenario
PANE_HEIGHT = 10     # pinned so the capture-window arithmetic is deterministic

# Row budget, counted from the bottom of the pane. With PANE_HEIGHT pinned,
# `capture-pane -S -N` yields roughly the last (N + PANE_HEIGHT) rows, so:
#   TAIL rows        -> 1..5
#   closing fence    -> 6
#   item rows        -> 7..66
#   opening fence    -> 67
# A window of SHALLOW_LINES + PANE_HEIGHT = 40 therefore reaches the closing
# fence but not the opening one, and a 400-line window reaches everything. The
# ~27-row margin absorbs an extra blank row or a tmux height adjustment; the
# shallow test additionally asserts the resulting capture shape, so drift fails
# loudly instead of passing vacuously.
HEAD_FILLER = 30
ITEM_ROWS = 60
TAIL_FILLER = 5
SHALLOW_LINES = 30
DEEP_LINES = 400


def _pane_payload() -> str:
    """The fixture pane's content: a plan-review-sized concern block."""
    lines = [f"FILLER-{i:04d} shadow prose before the block" for i in range(HEAD_FILLER)]
    lines.append(OPEN)
    # A Codex-style marker whose bracket was hard-wrapped mid full-path region
    # (the t1167 shape) — proves the rejoin still works through the live path.
    lines.append("- [medium | .claude/skills/aitask-shadow/impl-review-")
    lines.append("angles.md:12] The angle list is not exhaustive.")
    for i in range(ITEM_ROWS - 2):
        lines.append(f"- [low | region{i:03d}] Concern body number {i:03d}.")
    lines.append(CLOSE)
    lines.extend(f"TAIL-{i:04d}" for i in range(TAIL_FILLER))
    return "\n".join(lines)


def _tmux(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["tmux", "-L", SOCKET, *args],
        capture_output=True, text=True, check=False,
    )


class _FakeMon:
    """Stub monitor. Has no ``get_pane_option``, so the shadow-freshness check
    returns immediately — this smoke is about the capture path only."""


def _snap(pane_id="%1"):
    return SimpleNamespace(pane=SimpleNamespace(pane_id=pane_id))


@unittest.skipUnless(shutil.which("tmux"), "tmux not available")
class ConcernCaptureSmokeTests(unittest.TestCase):
    pane_id: str | None = None

    @classmethod
    def setUpClass(cls):
        payload = _pane_payload().replace("'", "")
        _tmux("kill-session", "-t", SESSION)
        res = _tmux(
            "new-session", "-d", "-s", SESSION,
            "-x", str(PANE_WIDTH), "-y", str(PANE_HEIGHT),
            "bash", "-c", f"printf '%s\\n' '{payload}'; sleep 300",
        )
        if res.returncode != 0:
            raise unittest.SkipTest(f"could not start tmux session: {res.stderr}")
        panes = _tmux("list-panes", "-t", SESSION, "-F", "#{pane_id}")
        cls.pane_id = panes.stdout.strip().splitlines()[0] if panes.stdout.strip() else None
        if not cls.pane_id:
            raise unittest.SkipTest("could not resolve the fixture pane id")
        # Wait for the pane to finish rendering (the tail is printed last).
        for _ in range(50):
            out = _tmux("capture-pane", "-p", "-t", cls.pane_id)
            if f"TAIL-{TAIL_FILLER - 1:04d}" in out.stdout:
                break
            time.sleep(0.1)
        else:
            raise unittest.SkipTest("fixture pane never finished rendering")

    @classmethod
    def tearDownClass(cls):
        _tmux("kill-server")

    def setUp(self):
        # Route the production capture helper at our disposable socket.
        self._prev_socket = os.environ.get("AITASKS_TMUX_SOCKET")
        os.environ["AITASKS_TMUX_SOCKET"] = SOCKET

    def tearDown(self):
        if self._prev_socket is None:
            os.environ.pop("AITASKS_TMUX_SOCKET", None)
        else:
            os.environ["AITASKS_TMUX_SOCKET"] = self._prev_socket

    def _app(self, lines: int):
        """A minimonitor whose capture is REAL, at a pinned scrollback depth."""
        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        app._monitor = _FakeMon()
        app._last_concern_block_payload = {}
        app._truncation_warned = set()
        app.spy_notify: list = []
        app.notify = lambda msg, **kw: app.spy_notify.append(
            (msg, kw.get("severity", "information"))
        )
        app._find_own_agent_snapshot = lambda: _snap("%99")
        app._find_shadow_pane_for = _async_pane(self.pane_id)
        real_capture = app._capture_shadow_text
        app._capture_shadow_text = (
            lambda pane, *, _r=real_capture: _r(pane, lines=lines)
        )
        return app

    def test_deep_window_reaches_the_block_and_notifies(self):
        app = self._app(DEEP_LINES)
        text = asyncio.run(app._capture_shadow_text(self.pane_id))
        self.assertIn(OPEN, text)
        self.assertIn(CLOSE, text)

        asyncio.run(app._maybe_offer_concerns())
        self.assertTrue(
            any("raised concerns" in m for m, _ in app.spy_notify),
            f"auto-offer did not fire; notifies={app.spy_notify}",
        )
        self.assertEqual(app._truncation_warned, set())

    def test_shallow_window_reports_truncation_not_silence(self):
        app = self._app(SHALLOW_LINES)
        # Assert the INTERMEDIATE shape first: if the row arithmetic ever drifts
        # this fails loudly here instead of the test passing for a wrong reason.
        text = asyncio.run(app._capture_shadow_text(self.pane_id))
        self.assertIn(CLOSE, text, "shallow window did not reach the closing fence")
        self.assertNotIn(OPEN, text, "shallow window was not shallow enough")

        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(app.spy_notify, [(mm._SHADOW_TRUNCATED_MSG, "warning")])
        self.assertFalse(any("raised concerns" in m for m, _ in app.spy_notify))


def _async_pane(pane_id):
    async def _coro(*args, **kwargs):
        return pane_id
    return _coro


if __name__ == "__main__":
    unittest.main()
