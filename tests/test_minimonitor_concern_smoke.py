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
# The captured-frame fixtures live beside this file (t1518). Resolved against
# THIS directory rather than the cwd — the suite chdirs in ~39 modules.
sys.path.insert(0, str(Path(__file__).resolve().parent))

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


# A pane that repaints whatever a file contains. Enough to put a REAL captured
# agent frame on a REAL pane, which is all the followed-pane path reads.
# Tall enough to hold the largest captured fixture (113 rows) in its VISIBLE
# area. That is the whole trick: if a frame does not fit, the overflow goes to
# tmux history, and history persists across paints — `clear-history` does not
# help because the rows still on screen get scrolled into the freshly-emptied
# history by the next `\x1b[2J` (measured: a 61-row frame came back as 90, and
# respawning the pane made it 189). With the frame bottom-aligned inside a pane
# that fits it, nothing ever scrolls and each capture is exactly one frame.
FRAME_PANE_H = 130
FRAME_PANE_W = 120

_FRAME_STUB = r'''
import os, sys, time
path = sys.argv[1]
last = None
while True:
    # Keyed on MTIME, not on content: the same frame is painted more than once
    # across the class, and a content-keyed stub would skip the redraw.
    try:
        cur = os.stat(path).st_mtime_ns
    except OSError:
        cur = None
    if cur is not None and cur != last:
        try:
            rows = open(path, "r", encoding="utf-8").read().split("\n")
        except OSError:
            rows = []
        # Overwrite IN PLACE — absolute cursor addressing, erase-to-EOL, and NO
        # newlines anywhere. `\x1b[2J` and a trailing newline both SCROLL, and
        # tmux pushes scrolled rows into history, so either one makes every
        # repaint append ~a pane-height of history that `capture-pane -S -200`
        # then returns (measured: 130-row frames coming back as 329 rows).
        out = []
        for i, row in enumerate(rows[:int(sys.argv[2])]):
            out.append("\x1b[" + str(i + 1) + ";1H\x1b[2K" + row)
        sys.stdout.write("".join(out))
        sys.stdout.flush()
        last = cur
    time.sleep(0.1)
'''


@unittest.skipUnless(shutil.which("tmux"), "tmux not available")
class FollowedPaneClassificationSmokeTests(unittest.TestCase):
    """Live wiring for the t1518 native-dialog boundaries.

    `test_review_loop.py` feeds captured frames straight into
    `classify_followed_change`, which is correct but cannot fail if the
    followed-pane path never reaches it with the right arguments — the agent
    key comes from `agent_keys.agent_key_from_pane` and the kind from
    `classify_content`'s scoped matching, and either can be wrong while every
    unit test stays green (the same gap t1467 built `test_prompt_scoping_live`
    for).

    So this drives REAL tmux panes whose `pane_current_command` really is
    `codex` / `opencode`, paints the REAL captured dialog frames into them, and
    classifies through `TmuxMonitor.capture_pane` — the production capture. The
    agent process is a repaint stub rather than the CLI itself: the boundary
    geometry was measured against the real CLIs in the task's pre-phase (the
    frames here ARE those captures), and what is unproven without a live pane
    is the wiring, not the geometry.

    Skip vs fail: `SkipTest` is for environment unavailability only. Once the
    panes exist, a wrong kind or verdict is the regression this exists to
    catch and fails.
    """

    tmpdir: str = ""
    panes: dict = {}

    @classmethod
    def setUpClass(cls):
        import review_loop_fixtures as rlfx
        cls.rlfx = rlfx
        cls.tmpdir = tempfile.mkdtemp(prefix="ait_t1518_follow_")
        cls.addClassCleanup(shutil.rmtree, cls.tmpdir, ignore_errors=True)
        prev_tmpdir = os.environ.get("TMUX_TMPDIR")
        os.environ["TMUX_TMPDIR"] = cls.tmpdir
        if prev_tmpdir is None:
            cls.addClassCleanup(os.environ.pop, "TMUX_TMPDIR", None)
        else:
            cls.addClassCleanup(os.environ.__setitem__, "TMUX_TMPDIR",
                                prev_tmpdir)

        stub = os.path.join(cls.tmpdir, "frame_stub.py")
        with open(stub, "w") as fh:
            fh.write(_FRAME_STUB)

        cls.panes = {}
        cls.frame_files = {}
        cls.pane_argv = {}
        cls.shadows = {}
        claude_bin = os.path.join(cls.tmpdir, "claude")
        shutil.copy2(sys.executable, claude_bin)
        os.chmod(claude_bin, 0o755)
        composer_stub = os.path.join(cls.tmpdir, "composer_stub.py")
        with open(composer_stub, "w") as fh:
            fh.write(_COMPOSER_STUB)
        # `claude` joins the set in t1540, once its tool-permission dialog got a
        # measured boundary. Its followed-pane binary is the same file the
        # shadow already uses (both are named `claude`), which is harmless:
        # the two panes are bound by `@aitask_shadow_target`, not by argv.
        for agent in ("codex", "opencode", "claude"):
            # `pane_current_command` must really be the agent name — rung 1 of
            # `agent_key_from_pane` reads it, and a `python3` pane would
            # resolve to "" and silently classify unscoped.
            fake = os.path.join(cls.tmpdir, agent)
            # `claude` already exists: it is `claude_bin` above, and by this
            # iteration the earlier agents' shadow panes are already executing
            # it, so copying over it raises ETXTBSY (racily — it depends on
            # whether those panes have exec'd yet). Reuse the file instead;
            # one binary serving both roles is fine because the followed and
            # shadow panes are bound by `@aitask_shadow_target`, not by argv.
            if not os.path.exists(fake):
                shutil.copy2(sys.executable, fake)
                os.chmod(fake, 0o755)
            frame = os.path.join(cls.tmpdir, f"{agent}.frame")
            with open(frame, "w", encoding="utf-8") as fh:
                fh.write("")
            cls.frame_files[agent] = frame
            session = f"{SESSION}_follow_{agent}"
            # Window name carries the `agent-` prefix: PaneCategory.AGENT comes
            # from it, and prompt matching runs only for AGENT panes.
            res = _tmux("new-session", "-d", "-s", session,
                        "-n", f"agent-{agent}",
                        "-x", str(FRAME_PANE_W), "-y", str(FRAME_PANE_H),
                        fake, stub, frame, str(FRAME_PANE_H))
            if res.returncode != 0:
                raise unittest.SkipTest(
                    f"could not start {agent} pane: {res.stderr}")
            panes = _tmux("list-panes", "-t", session, "-F", "#{pane_id}")
            pane_id = (panes.stdout.strip().splitlines()[0]
                       if panes.stdout.strip() else None)
            if not pane_id:
                raise unittest.SkipTest(f"could not resolve {agent} pane id")
            cls.panes[agent] = (session, pane_id)
            cls.pane_argv[agent] = (fake, stub, frame, str(FRAME_PANE_H))

            # A REAL shadow pane beside it, bound the way spawn_shadow binds
            # one. Runs the Claude-shaped composer stub under a binary named
            # `claude`, so the app's own shadow lookup + agent resolution +
            # readiness detection all run for real, and an injected recheck is
            # readable back out of the pane.
            # Its OWN WINDOW, not a split: splitting the followed pane halves
            # its height, and these fixtures are bottom-aligned inside a pane
            # tall enough to hold them (a 130-row frame came back as 65). The
            # shadow lookup is server-wide (`list-panes -a`), so a separate
            # window is found just the same.
            shadow_res = _tmux(
                "new-window", "-d", "-t", session,
                "-n", f"agent-shadow-{agent}", "-P", "-F",
                "#{pane_id}", claude_bin, composer_stub)
            shadow_id = shadow_res.stdout.strip()
            if not shadow_id:
                raise unittest.SkipTest(
                    f"could not create {agent} shadow pane: "
                    f"{shadow_res.stderr}")
            _tmux("set-option", "-p", "-t", shadow_id,
                  "@aitask_shadow_target", pane_id)
            cls.shadows[agent] = shadow_id

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

    def _pane_info(self, agent: str):
        """Live pane metadata, built the way `test_prompt_scoping_live` does.

        Deliberately NOT `TmuxMonitor.discover_panes()`: the monitor defaults
        to multi-session mode, whose discovery keeps only *aitasks-like*
        sessions (a pane whose cwd walks up to `aitasks/metadata/
        project_config.yaml`), so a synthetic fixture session is invisible to
        it and discovery returns []. The pane facts here are still entirely
        real — they come from `list-panes` on the live server.
        """
        from monitor.monitor_core import PaneCategory, TmuxPaneInfo

        session, pane_id = self.panes[agent]
        out = _tmux("list-panes", "-t", session, "-F",
                    "#{pane_id}\t#{pane_current_command}\t#{pane_pid}")
        for line in out.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) == 3 and parts[0] == pane_id:
                return TmuxPaneInfo(
                    window_index="0", window_name=f"agent-{agent}",
                    pane_index="0", pane_id=pane_id, pane_pid=int(parts[2]),
                    current_command=parts[1],
                    width=FRAME_PANE_W, height=FRAME_PANE_H,
                    category=PaneCategory.AGENT, session_name=session)
        return None

    def _paint(self, agent: str, raw: str, previous=None):
        """Put `raw` on the pane and return the production snapshot of it.

        ``previous`` is the snapshot the pane is currently showing, when there
        is one. Waiting on a *substring marker* is not enough here and the
        reason is the whole point of the fixtures: the two frames of a
        selection pair differ only in the cursor, so any marker drawn from one
        also matches the other and the wait returns the OLD frame immediately —
        which then classifies as NO_CHANGE and would have quietly turned every
        assertion below into a tautology. Wait for the content to actually
        change instead.
        """
        from monitor.monitor_core import TmuxMonitor

        session, pane_id = self.panes[agent]
        # Bottom-align the frame inside the pane so its last row is the pane's
        # last row. Two things depend on this: the frame never overflows into
        # tmux history (see FRAME_PANE_H), and `awaiting_input` detection reads
        # the bottom 6 rows, which must therefore be the dialog's footer rather
        # than terminal padding.
        rows = raw.splitlines()
        self.assertLessEqual(len(rows), FRAME_PANE_H,
                             "fixture taller than the pane would overflow "
                             "into tmux history")
        padded = "\n" * (FRAME_PANE_H - len(rows)) + raw
        with open(self.frame_files[agent], "w", encoding="utf-8") as fh:
            fh.write(padded)
        monitor = TmuxMonitor(session=session, idle_threshold=0.05)
        want = _norm(padded)
        # tmux runs a command with arguments through `sh -c`, so
        # `pane_current_command` reads `sh`/`tmux` for the first moments after
        # creation. Wait for the value under test rather than merely for the
        # pane to exist — that was the t1467 order-dependent flake.
        deadline = time.time() + 30
        seen_command = None
        got = None
        while time.time() < deadline:
            info = self._pane_info(agent)
            if info is not None:
                seen_command = info.current_command
                if seen_command == agent:
                    rc, content = monitor.tmux_run(
                        monitor._capture_args(pane_id))
                    if rc == 0:
                        got = _norm(content)
                        # Exact match, not a substring: the frames of a
                        # selection pair differ only in the cursor, so any
                        # marker taken from one also matches the other and the
                        # wait would return the OLD frame — which classifies as
                        # NO_CHANGE and turns every assertion here into a
                        # tautology.
                        if got == want:
                            return monitor._finalize_capture(info, content)
            time.sleep(0.15)
        self.fail(f"{agent} pane never rendered the frame exactly "
                  f"(command={seen_command!r}, "
                  f"want {len(want)} rows, got {len(got or [])} rows)")

    def _case(self, agent, kind, first, second, expected):
        s1 = self._paint(agent, first)
        self.assertEqual(s1.agent_key, agent,
                         "rung 1 of agent_key_from_pane must resolve the pane")
        self.assertEqual(s1.awaiting_input_kind, kind,
                         "the production classifier must report this kind")
        s2 = self._paint(agent, second, previous=s1)
        self.assertEqual(s2.awaiting_input_kind, kind)
        verdict = rl_mod().classify_followed_change(
            s1.content, s1.awaiting_input_kind,
            s2.content, s2.awaiting_input_kind,
            True, s2.agent_key,
            s1.pane.history_size, s2.pane.history_size,
            (s1.pane.width, s1.pane.height), (s2.pane.width, s2.pane.height))
        self.assertEqual(verdict, expected)
        return verdict

    def test_codex_dialog_selection_does_not_signal_work(self):
        self._case("codex", "codex_permission",
                   self.rlfx.CODEX_EXEC_APPROVAL_SEL1_RAW,
                   self.rlfx.CODEX_EXEC_APPROVAL_SEL2_RAW,
                   rl_mod().SELECTION_ONLY)

    def test_codex_output_above_the_dialog_signals_work(self):
        self._case("codex", "codex_permission",
                   self.rlfx.CODEX_EXEC_APPROVAL_SEL1_RAW,
                   self.rlfx.CODEX_EXEC_APPROVAL_LATER_RAW,
                   rl_mod().WORK)

    def test_opencode_dialog_selection_does_not_signal_work(self):
        self._case("opencode", "opencode_permission",
                   self.rlfx.OPENCODE_PERMISSION_SEL1_RAW,
                   self.rlfx.OPENCODE_PERMISSION_SEL2_RAW,
                   rl_mod().NO_CHANGE)

    def test_opencode_output_above_the_dialog_signals_work(self):
        self._case("opencode", "opencode_permission",
                   self.rlfx.OPENCODE_PERMISSION_SEL1_RAW,
                   self.rlfx.OPENCODE_PERMISSION_LATER_RAW,
                   rl_mod().WORK)

    def test_claude_dialog_selection_does_not_signal_work(self):
        """Claude's tool-permission dialog through the real capture path (t1540).

        The unit tests feed the same frames straight into
        `classify_followed_change`; what only a live pane can prove is that
        `agent_key_from_pane` resolves `claude` and that `classify_content`
        reports `claude_help_bar` for the OPTION-2 frame. That second half is
        the whole point: before t1540 widened the pattern, option 2 reported no
        kind at all and this pair classified WORK.
        """
        self._case("claude", "claude_help_bar",
                   self.rlfx.CLAUDE_PERMISSION_SEL1_RAW,
                   self.rlfx.CLAUDE_PERMISSION_SEL2_RAW,
                   rl_mod().SELECTION_ONLY)

    def test_claude_output_above_the_dialog_signals_work(self):
        self._case("claude", "claude_help_bar",
                   self.rlfx.CLAUDE_PERMISSION_SEL1_RAW,
                   self.rlfx.CLAUDE_PERMISSION_LATER_RAW,
                   rl_mod().WORK)

    def test_claude_short_pane_reports_proceed_and_does_not_signal_work(self):
        """The second rendering regime, live (t1540).

        At a short pane height Claude truncates the option list, which lifts
        `Do you want to proceed?` into the 6-line detection window and makes
        `claude_proceed` the reported kind. Driving it here is what proves the
        second boundary row is reachable through the production classifier
        rather than only through a hand-passed kind argument.
        """
        self._case("claude", "claude_proceed",
                   self.rlfx.CLAUDE_PERMISSION_SHORT_SEL1_RAW,
                   self.rlfx.CLAUDE_PERMISSION_SHORT_SEL2_RAW,
                   rl_mod().SELECTION_ONLY)

    def test_work_opens_the_latch_exactly_once(self):
        """The verdict is not the point — the loop's response to it is.

        A single WORK observation must open the work latch for ONE episode:
        `tick` grants exactly one `fire`, and no further fire follows while the
        loop stays FIRED. This is the arm-and-fire-one-round contract, driven
        off a verdict produced by the real capture path rather than a literal.
        """
        rl = rl_mod()
        verdict = self._case("codex", "codex_permission",
                             self.rlfx.CODEX_EXEC_APPROVAL_SEL1_RAW,
                             self.rlfx.CODEX_EXEC_APPROVAL_LATER_RAW,
                             rl.WORK)
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=False)
        fires = 0
        for i in range(rl.DEBOUNCE_TICKS * 3):
            action = ctrl.tick(
                agent_present=True, shadow_present=True, awaiting_input=True,
                stale=True, work_signal=verdict if i == 0 else rl.NO_CHANGE,
                shadow_ready=True, modal_open=False, now=float(i))
            if action == rl.ACTION_FIRE:
                fires += 1
                ctrl.confirm_fire(ctrl.delivery_token, float(i))
        self.assertEqual(fires, 1, "exactly one automatic round")

    def _app(self, agent, snap):
        """A MiniMonitorApp wired to the REAL monitor for `agent`'s session."""
        from monitor.monitor_core import TmuxMonitor
        from monitor import review_loop as rl

        session, _ = self.panes[agent]
        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        app._monitor = TmuxMonitor(session=session, idle_threshold=0.05)
        app._review_loop = rl.ReviewLoopController()
        app._task_cache = SimpleNamespace(get_task_id_for_pane=lambda p: None)
        # NOT stale at arm time. `action_toggle_review_loop` passes
        # `pending_work=(self._shadow_feedback_stale is True)`, so arming while
        # the shadow's feedback is already stale opens the work latch
        # immediately — deliberate in production (the keypress IS the user
        # asking for a round), but it would make the positive test below fire
        # for a reason unrelated to the boundary, and it made the negative
        # control fire outright. Staleness is switched on AFTER arming.
        app._shadow_read_recency = mm.ReadRecency(False, 100.0)
        app._loop_shadow_settle_until = None
        app._loop_shadow_hash = None
        app._loop_shadow_hash_streak = 0
        app._loop_last_service_at = None
        app._loop_stale_false_pending = False
        app._loop_baseline = None
        app._refresh_seconds = 2
        app._loop_now = time.monotonic
        app._banners: list = []
        app._set_loop_banner = lambda t: app._banners.append(t)
        app.spy_notify: list = []
        app.notify = lambda m, **k: app.spy_notify.append(
            (m, k.get("severity", "information")))
        app._find_own_agent_snapshot = lambda: snap
        return app

    def test_app_arms_and_fires_one_round_through_the_real_path(self):
        """Step 5a proper: the APPLICATION path, not the decision core.

        The tests above prove `classify_followed_change` gets the right
        arguments from a real capture — but they call it, and the controller,
        directly. An integration defect in `action_toggle_review_loop`'s shadow
        lookup, in the baseline `_service_review_loop` seeds and maintains, or
        in the fire/delivery wiring would leave every one of them green.

        So this drives the real `action_toggle_review_loop` (real server-wide
        shadow lookup via `@aitask_shadow_target`, real two-rung agent
        resolution, real readiness detection) and then the real
        `_service_review_loop`, and asserts the recheck line actually lands in
        the shadow pane — exactly once.
        """
        from monitor import review_loop as rl

        for agent in ("codex", "opencode", "claude"):
            with self.subTest(agent=agent):
                self._arm_and_fire_once(agent)

    def _arm_and_fire_once(self, agent):
        from monitor import review_loop as rl

        session, followed = self.panes[agent]
        shadow = self.shadows[agent]
        first, later = {
            "codex": (self.rlfx.CODEX_EXEC_APPROVAL_SEL1_RAW,
                      self.rlfx.CODEX_EXEC_APPROVAL_LATER_RAW),
            "opencode": (self.rlfx.OPENCODE_PERMISSION_SEL1_RAW,
                         self.rlfx.OPENCODE_PERMISSION_LATER_RAW),
            "claude": (self.rlfx.CLAUDE_PERMISSION_SEL1_RAW,
                       self.rlfx.CLAUDE_PERMISSION_LATER_RAW),
        }[agent]

        # Arm-time frame: the dialog, parked and awaiting input.
        snap = self._paint(agent, first)
        self.assertEqual(snap.agent_key, agent)
        self.assertTrue(snap.awaiting_input)
        app = self._app(agent, snap)

        asyncio.run(app.action_toggle_review_loop())
        self.assertFalse(app._review_loop.work_seen,
                         "the latch must start CLOSED, so a fire below can "
                         "only come from classified work")
        app._shadow_read_recency = mm.ReadRecency(True, 100.0)
        self.assertTrue(
            app._review_loop.armed,
            f"real arming path refused: {app.spy_notify[-1][0] if app.spy_notify else None}")
        # The shadow really was found and resolved by the app itself.
        self.assertIsNotNone(app._loop_baseline)

        # Work above the boundary, then hold. The first serviced tick sees
        # LATER against the arm-time baseline (WORK); later ticks see no
        # further change, so a second fire would be a defect, not a slow one.
        later_snap = self._paint(agent, later, previous=snap)
        self.assertTrue(later_snap.awaiting_input)

        ok, shadow_pane, shadow_cmd, shadow_pid = asyncio.run(
            mm.find_shadow_pane_info_async(app._monitor, followed))
        self.assertTrue(ok)
        self.assertEqual(shadow_pane, shadow)

        tick_text = (f"{OPEN}\nRound: 1 @ 2026-08-17T10:00:00Z\n"
                     f"- [low | smoke] x.\n{CLOSE}\n")
        for _ in range(rl.DEBOUNCE_TICKS + 3):
            # The service throttles to one committed evidence tick per half
            # refresh period; clearing the stamp keeps the test fast without
            # weakening what it drives.
            app._loop_last_service_at = None
            asyncio.run(app._service_review_loop(
                later_snap, True, shadow_pane, shadow_cmd, tick_text,
                shadow_pid))

        self.assertEqual(app._review_loop.state, rl.FIRED,
                         f"loop never fired; banners={app._banners} "
                         f"notify={app.spy_notify}")
        # ...and the round really landed in the shadow pane, once.
        deadline = time.time() + 10
        cap = ""
        while time.time() < deadline:
            cap = _tmux("capture-pane", "-p", "-J", "-t", shadow).stdout
            if "refetch and recheck" in cap:
                break
            time.sleep(0.2)
        self.assertIn("refetch and recheck", cap, cap)
        self.assertEqual(cap.count("refetch and recheck"), 1,
                         f"exactly one round should have been injected:\n{cap}")

    def test_app_does_not_fire_on_a_selection_redraw(self):
        """Negative control for the test above, through the same real path.

        Without it, an app that fired on any tick would pass — the assertion
        there is that a round landed, and this is the assertion that one does
        not land when the followed pane only redrew its cursor.

        Run for BOTH agents, because the two reach "do not fire" by DIFFERENT
        mechanisms and only one of them involves a boundary: Codex draws a `>`
        cursor, so its pair differs once stripped and classifies
        SELECTION_ONLY via the boundary; OpenCode draws selection purely as
        ANSI styling, so its pair is byte-identical once stripped and returns
        NO_CHANGE *before* any boundary is consulted. Covering only Codex would
        leave OpenCode's path unexercised through the application.
        """
        for agent in ("codex", "opencode", "claude"):
            with self.subTest(agent=agent):
                self._no_fire_on_selection(agent)

    def _no_fire_on_selection(self, agent):
        from monitor import review_loop as rl

        session, followed = self.panes[agent]
        shadow = self.shadows[agent]
        first, second = {
            "codex": (self.rlfx.CODEX_EXEC_APPROVAL_SEL1_RAW,
                      self.rlfx.CODEX_EXEC_APPROVAL_SEL2_RAW),
            "opencode": (self.rlfx.OPENCODE_PERMISSION_SEL1_RAW,
                         self.rlfx.OPENCODE_PERMISSION_SEL2_RAW),
            "claude": (self.rlfx.CLAUDE_PERMISSION_SEL1_RAW,
                       self.rlfx.CLAUDE_PERMISSION_SEL2_RAW),
        }[agent]

        snap = self._paint(agent, first)
        app = self._app(agent, snap)
        asyncio.run(app.action_toggle_review_loop())
        self.assertTrue(app._review_loop.armed)
        self.assertFalse(app._review_loop.work_seen)
        app._shadow_read_recency = mm.ReadRecency(True, 100.0)

        sel2 = self._paint(agent, second, previous=snap)
        ok, shadow_pane, shadow_cmd, shadow_pid = asyncio.run(
            mm.find_shadow_pane_info_async(app._monitor, followed))
        self.assertTrue(ok)
        self.assertEqual(shadow_pane, shadow)

        before = _tmux("capture-pane", "-p", "-J", "-t", shadow).stdout
        tick_text = (f"{OPEN}\nRound: 1 @ 2026-08-17T10:00:00Z\n"
                     f"- [low | smoke] x.\n{CLOSE}\n")
        for _ in range(rl.DEBOUNCE_TICKS + 3):
            app._loop_last_service_at = None
            asyncio.run(app._service_review_loop(
                sel2, True, shadow_pane, shadow_cmd, tick_text, shadow_pid))

        self.assertNotEqual(app._review_loop.state, rl.FIRED,
                            f"{agent}: a selection redraw must not fire")
        after = _tmux("capture-pane", "-p", "-J", "-t", shadow).stdout
        self.assertEqual(
            after.count("refetch and recheck"),
            before.count("refetch and recheck"),
            f"{agent}: nothing may be injected on a selection-only redraw")

    def test_selection_only_never_opens_the_latch(self):
        """Negative control for the test above: the same loop, fed the
        selection verdict, must never fire. Without it, a controller that fired
        on anything would pass the one-round test."""
        rl = rl_mod()
        verdict = self._case("codex", "codex_permission",
                             self.rlfx.CODEX_EXEC_APPROVAL_SEL1_RAW,
                             self.rlfx.CODEX_EXEC_APPROVAL_SEL2_RAW,
                             rl.SELECTION_ONLY)
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=False)
        for i in range(rl.DEBOUNCE_TICKS * 3):
            action = ctrl.tick(
                agent_present=True, shadow_present=True, awaiting_input=True,
                stale=True, work_signal=verdict, shadow_ready=True,
                modal_open=False, now=float(i))
            self.assertNotEqual(action, rl.ACTION_FIRE,
                                "a selection redraw must never fire")


def rl_mod():
    from monitor import review_loop as rl
    return rl


def _norm(raw: str) -> list[str]:
    """A frame reduced to comparable rows: ANSI stripped, right-trimmed, and
    with trailing blank rows dropped.

    tmux pads the pane to its full height, so a 61-row frame in a 30-row pane
    comes back with trailing blanks that are an artifact of the terminal rather
    than of the capture under test.
    """
    from monitor.ansi_utils import strip_ansi
    rows = [line.rstrip() for line in strip_ansi(raw).splitlines()]
    while rows and not rows[-1]:
        rows.pop()
    return rows


if __name__ == "__main__":
    unittest.main()
