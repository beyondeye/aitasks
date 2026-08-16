"""Live-tmux smoke for minimonitor's shadow concern capture path (t1187).

Every other concern test stubs ``capture_shadow_text`` and feeds the parser a
synthetic string, so the whole suite can pass while the real pipeline still
produces no auto-offer — which is exactly how the t1170 item-#2 live failure
slipped through. This module exercises the real chain end-to-end:

    real tmux pane -> aitask_shadow_capture.sh -> capture_shadow_text
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
import re
import shutil
import subprocess
import sys
import tempfile
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

#: The auto-offer toast, matched on its stable shape rather than a literal
#: substring — the wording now interpolates counts (t1274).
OFFER_RE = re.compile(r"Shadow raised \d+ concern", re.IGNORECASE)

# Per-PID socket AND session (t1354_3). Both used to be fixed names on the
# shared `/tmp/tmux-$UID` server, with an unconditional `kill-session` /
# `kill-server` — unsafe even against a second concurrent suite run today, and a
# hard blocker for the parallel test lane, where each xdist worker is its own
# process. The per-PID socket is the model used by
# tests/test_board_header_row_live.py:40; the private TMUX_TMPDIR set up in
# setUpClass is the one from tests/lib/tmux_isolation.sh (require_isolated_tmux)
# and tests/lib/tmux_socket_containment.py.
SOCKET = f"ait_t1187_smoke_{os.getpid()}"
SESSION = f"t1187_concern_smoke_{os.getpid()}"
PANE_WIDTH = 55      # the narrow width from the failing scenario
PANE_HEIGHT = 10     # pinned so the capture-window arithmetic is deterministic

# A minimal Claude-shaped composer, for the injection smoke below (t1525).
#
# `cat` was enough while delivery was two adjacent send_keys, but the delivery
# now READS THE PANE BACK between them: it authorises the Enter only on a
# composer positively holding the typed text (SHADOW_BUSY) and then verifies
# that the text left the composer. Those are exactly the two behaviours a `cat`
# pane does not have. This stub has them and nothing else — it is a fixture for
# the delivery protocol, not an emulation of any agent's input handling.
#
# ❯ = ❯, and the pad after it is NBSP (`_CLAUDE_COMPOSER_RE` keys on it).
_COMPOSER_STUB = r'''
import sys, tty

buf = ""


def draw():
    sys.stdout.write("\r\x1b[K❯ " + buf)
    sys.stdout.flush()


draw()
tty.setraw(sys.stdin.fileno())
while True:
    ch = sys.stdin.read(1)
    if ch in ("\r", "\n"):
        # Submit: echo into the scrollback the way a real TUI does, then clear.
        sys.stdout.write("\r\x1b[K" + buf + "\r\n")
        buf = ""
    elif ch == "\x03":
        break
    elif ch == "\x7f":
        buf = buf[:-1]
    else:
        buf += ch
    draw()
'''

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
    return SimpleNamespace(
        pane=SimpleNamespace(pane_id=pane_id, current_command="claude",
                             session_name="s", history_size=None,
                             width=100, height=30),
        content="", awaiting_input=False, awaiting_input_kind="",
    )


@unittest.skipUnless(shutil.which("tmux"), "tmux not available")
class ConcernCaptureSmokeTests(unittest.TestCase):
    pane_id: str | None = None

    @classmethod
    def setUpClass(cls):
        # Private tmux tmpdir, set in the ENVIRONMENT (not merely passed to one
        # subprocess) because the production path under test —
        # aitask_shadow_capture.sh -> lib/tmux_exec.sh — spawns its own tmux and
        # inherits os.environ. Must be in place before the first _tmux() call.
        # Cleanups run after tearDownClass, so the server is killed first.
        tmpdir = tempfile.mkdtemp(prefix="ait_t1187_tmux_")
        prev_tmpdir = os.environ.get("TMUX_TMPDIR")
        os.environ["TMUX_TMPDIR"] = tmpdir
        cls.addClassCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        if prev_tmpdir is None:
            cls.addClassCleanup(os.environ.pop, "TMUX_TMPDIR", None)
        else:
            cls.addClassCleanup(os.environ.__setitem__, "TMUX_TMPDIR", prev_tmpdir)

        payload = _pane_payload().replace("'", "")
        # No pre-emptive kill-session: SESSION is per-PID, so there is nothing
        # pre-existing to kill, and killing by a shared name is what made this
        # module unsafe to run alongside anything else.
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

    def _patch(self, obj, name, value):
        """Rebind a module attribute for one test, restoring it at teardown."""
        self.addCleanup(setattr, obj, name, getattr(obj, name))
        setattr(obj, name, value)

    def _app(self, lines: int):
        """A minimonitor whose capture is REAL, at a pinned scrollback depth."""
        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        app._monitor = _FakeMon()
        app._last_concern_block_payload = {}
        app._truncation_warned = set()
        app._unparsed_warned = set()
        # Review-loop state normally set by __init__ (t1159_2): the loop
        # service runs on every _maybe_offer_concerns tick (disarmed here).
        app._review_loop = mm.review_loop.ReviewLoopController()
        app._loop_banner_text = ""
        app._loop_baseline = None
        app._loop_shadow_hash = None
        app._loop_shadow_hash_streak = 0
        # Post-interaction settle latch + injectable clock (t1509).
        app._loop_shadow_settle_until = None
        app._loop_now = lambda: 1000.0
        app._loop_stale_false_pending = False
        app._session = "s"
        app._own_window_name = "agent-x"
        app.spy_notify: list = []
        app.notify = lambda msg, **kw: app.spy_notify.append(
            (msg, kw.get("severity", "information"))
        )
        app._find_own_agent_snapshot = lambda: _snap("%99")
        # The delegating seams are gone (t1289): `_maybe_offer_concerns` resolves
        # both helpers from `minimonitor_app`'s globals, so the stubs are module
        # attributes now. The capture wrapper still calls the REAL helper — only
        # the scrollback depth is pinned, which is the whole point of this smoke.
        # The lookup seam is the info form since t1159_2.
        self._patch(mm, "find_shadow_pane_info_async",
                    _async_pane_info(self.pane_id))
        real_capture = mm.capture_shadow_text
        self._patch(
            mm, "capture_shadow_text",
            lambda pane, *, _r=real_capture: _r(pane, lines=lines),
        )
        return app

    def test_deep_window_reaches_the_block_and_notifies(self):
        app = self._app(DEEP_LINES)
        text = asyncio.run(mm.capture_shadow_text(self.pane_id))
        self.assertIn(OPEN, text)
        self.assertIn(CLOSE, text)

        asyncio.run(app._maybe_offer_concerns())
        self.assertTrue(
            any(OFFER_RE.search(m) for m, _ in app.spy_notify),
            f"auto-offer did not fire; notifies={app.spy_notify}",
        )
        self.assertEqual(app._truncation_warned, set())

    def test_shallow_window_reports_truncation_not_silence(self):
        app = self._app(SHALLOW_LINES)
        # Assert the INTERMEDIATE shape first: if the row arithmetic ever drifts
        # this fails loudly here instead of the test passing for a wrong reason.
        text = asyncio.run(mm.capture_shadow_text(self.pane_id))
        self.assertIn(CLOSE, text, "shallow window did not reach the closing fence")
        self.assertNotIn(OPEN, text, "shallow window was not shallow enough")

        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(app.spy_notify, [(mm._SHADOW_TRUNCATED_MSG, "warning")])
        self.assertFalse(any(OFFER_RE.search(m) for m, _ in app.spy_notify))


def _async_pane(pane_id):
    async def _coro(*args, **kwargs):
        return pane_id
    return _coro


def _async_pane_info(pane_id):
    async def _coro(*args, **kwargs):
        # (ok, pane, command, pid): a verified claude shadow, but the loop
        # stays disarmed in these tests so only the pane id is consumed. The
        # pid field arrived with t1509 (Codex reports `node`, so the agent key
        # needs the pid-driven second rung).
        return (True, pane_id, "claude", 4242)
    return _coro


@unittest.skipUnless(shutil.which("tmux"), "tmux not available")
class RecheckInjectionSmokeTests(unittest.TestCase):
    """Live injection smoke (t1159_2): `_fire_shadow_recheck` against a REAL
    tmux pane, through the real TmuxMonitor.send_keys gateway — the recheck
    line must arrive in the pane verbatim.

    The pane renders a Claude-shaped empty composer line (`❯` + NBSP) and then
    runs `cat`, so the pre-send readiness revalidation genuinely passes and
    the terminal echo makes the delivered line capturable.

    **This smoke does NOT cover the t1525 submit verifier, and must not be
    stretched to try.** The pane prints `❯`+NBSP followed by a newline, so the
    tty echo of the typed line lands *below* the composer; `_composer_state`
    scans bottom-up for `^❯(\\u00a0.*)?$`, never matches the echoed line, and
    reads the still-empty `❯` line — so `_claude_state` returned
    `SHADOW_READY` at every point in the delivery, and the entire
    verify-and-retry block could have been deleted with the test still green.
    Dropping the `\\n` does not fix it either: the echo would then land on the
    composer line, but `cat` never clears it, so the post-Enter capture would
    read `SHADOW_BUSY` forever and the retry budget would exhaust. **A `cat`
    pane cannot emulate a composer, so the pane is a ~20-line stub TUI
    instead** (`_COMPOSER_STUB`): it holds typed bytes on the `❯` line and, on
    `\\r`, echoes the submitted line into the scrollback and clears the
    composer — the two behaviours the delivery reads back. That makes this the
    one test covering the drain, the `SHADOW_BUSY` pre-Enter gate and the
    post-Enter verification against a REAL pane through the REAL
    `TmuxMonitor.send_keys` gateway. It is still not an agent: per-CLI input
    coalescing (the actual t1525 bug) is measured live in the task's pre-phase
    sweep, not here.
    """

    @classmethod
    def setUpClass(cls):
        tmpdir = tempfile.mkdtemp(prefix="ait_t1159_inject_")
        prev_tmpdir = os.environ.get("TMUX_TMPDIR")
        os.environ["TMUX_TMPDIR"] = tmpdir
        cls.addClassCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        if prev_tmpdir is None:
            cls.addClassCleanup(os.environ.pop, "TMUX_TMPDIR", None)
        else:
            cls.addClassCleanup(os.environ.__setitem__, "TMUX_TMPDIR", prev_tmpdir)
        stub = os.path.join(tmpdir, "composer_stub.py")
        with open(stub, "w") as fh:
            fh.write(_COMPOSER_STUB)
        # 120 columns so the ~92-char recheck line never soft-wraps: a wrapped
        # composer would still classify BUSY, but the `-J` verbatim assertion
        # below is clearer without reflow in play.
        res = _tmux(
            "new-session", "-d", "-s", f"{SESSION}_inject",
            "-x", "120", "-y", "10", sys.executable, stub,
        )
        if res.returncode != 0:
            raise unittest.SkipTest(f"could not start tmux session: {res.stderr}")
        panes = _tmux("list-panes", "-t", f"{SESSION}_inject",
                      "-F", "#{pane_id}")
        cls.pane_id = (panes.stdout.strip().splitlines()[0]
                       if panes.stdout.strip() else None)
        if not cls.pane_id:
            raise unittest.SkipTest("could not resolve the composer pane id")
        # Wait for the composer line to render — capturing before it exists
        # makes the tick baseline differ from the fire-time fresh capture,
        # which the revalidation rightly refuses.
        for _ in range(50):
            out = _tmux("capture-pane", "-p", "-t", cls.pane_id)
            if "❯" in out.stdout:
                break
            time.sleep(0.1)
        else:
            raise unittest.SkipTest("composer pane never finished rendering")

    @classmethod
    def tearDownClass(cls):
        _tmux("kill-server")

    def setUp(self):
        self._prev_socket = os.environ.get("AITASKS_TMUX_SOCKET")
        os.environ["AITASKS_TMUX_SOCKET"] = SOCKET

    def tearDown(self):
        if self._prev_socket is None:
            os.environ.pop("AITASKS_TMUX_SOCKET", None)
        else:
            os.environ["AITASKS_TMUX_SOCKET"] = self._prev_socket

    def test_fire_delivers_the_recheck_line_verbatim(self):
        from monitor.monitor_core import TmuxMonitor, capture_raw_tail
        from monitor import review_loop as rl

        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        monitor = TmuxMonitor(session=f"{SESSION}_inject")
        app._monitor = monitor
        app._review_loop = rl.ReviewLoopController()
        app._task_cache = SimpleNamespace(
            get_task_id_for_pane=lambda pane: None)
        # Post-interaction settle latch state, normally set by __init__ (t1509).
        # The delivery-time revalidation consults it, so this live-tmux smoke
        # needs it too. Clock frozen: this test drives one clean delivery, and
        # the latch starts clear, so no deadline is ever consulted.
        app._loop_shadow_settle_until = None
        app._loop_now = lambda: 1000.0
        # The delivery can emit a "could not be verified" warning (t1525), and
        # this app is hand-assembled via __new__ with no running Textual app
        # behind it — without a notify spy that branch would raise inside a
        # real-tmux run rather than surfacing the warning.
        app.spy_notify: list = []
        app.notify = lambda msg, **kw: app.spy_notify.append(
            (msg, kw.get("severity", "information")))

        ctrl = app._review_loop
        ctrl.arm(pending_work=True)
        for i in range(rl.DEBOUNCE_TICKS):
            action = ctrl.tick(
                agent_present=True, shadow_present=True, awaiting_input=True,
                stale=True, work_signal=rl.NO_CHANGE, shadow_ready=True,
                modal_open=False, now=float(i))
        self.assertEqual(action, rl.ACTION_FIRE)
        token = ctrl.delivery_token

        tick_raw = asyncio.run(capture_raw_tail(monitor, self.pane_id))
        self.assertIsNotNone(tick_raw, "raw tail capture failed")
        tick_text = (
            f"{OPEN}\nRound: 1 @ 2026-08-12T10:00:00Z\n"
            f"- [low | smoke] x.\n{CLOSE}\n")
        outcome, prompt = asyncio.run(app._fire_shadow_recheck(
            self.pane_id, _snap(self.pane_id), "claude", tick_raw,
            tick_text, token))
        self.assertEqual(outcome, "sent", prompt)
        self.assertTrue(prompt.startswith("refetch and recheck round 2"))

        # The typed line reaches the pane verbatim (terminal echo of `cat`'s
        # stdin; -J joins the soft-wrapped line at the 80-column width).
        for _ in range(30):
            cap = _tmux("capture-pane", "-p", "-J", "-t", self.pane_id)
            if prompt in cap.stdout:
                break
            time.sleep(0.1)
        self.assertIn(prompt, cap.stdout, cap.stdout)


if __name__ == "__main__":
    unittest.main()
