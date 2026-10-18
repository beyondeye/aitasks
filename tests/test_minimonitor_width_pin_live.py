"""Live acceptance for minimonitor's companion width pin (t2050).

THE CASE. `ait ide` restores frozen agents BEFORE `tmux attach`, so each
restored window is created detached at tmux's default 80x24 and the companion
is split there with `-l 40` (39 | 40). The window is resized only when a client
first views it, and growing 80 -> 270 spreads the extra columns over both panes:
the companion lands at ~135. The t978 pin exists to undo exactly that, but it
read `self.size` inside `on_resize`, which Textual 8.2.7 has not updated yet, so
it saw 40 and did nothing.

WHAT THIS DRIVES. A real `MiniMonitorApp` (via
`tests/lib/minimonitor_width_pin_harness.py`) in a real tmux pane under a real
pty, split at 40 into a detached 80-column window, which is then grown to 270.
The SIGWINCH, the Resize dispatch, the pin decision and the gateway's
`resize-pane` are all real. `resize-window` stands in for the first client view
(both go through tmux's layout resize). `minimonitor_app.main()`, its config load
and the frozen-restore coordinator are NOT exercised — that is the boundary.

THE NEGATIVE CONTROL IS EXECUTABLE. `AIT_T2050_LEGACY_PIN=1` restores the
pre-fix decision (`self.size.width`). The control must keep the companion wide
for the whole settle window — it is what proves this fixture reproduces the
reported drift, so the fixed run's 40 is evidence rather than a coincidence of
the setup.

Raw `tmux` is correct in `tests/`: `tests/test_no_raw_tmux.sh` scopes its guard
to `.aitask-scripts/`. Isolation follows `tests/test_minimonitor_bottom_pin_live.py`
— a throwaway per-process socket, with `AITASKS_TMUX_SOCKET` exported into the
pane so the app's gateway call stays on it and `kill-server` can only reach the
server we started.

Skip-vs-fail: `SkipTest` only for environment unavailability (no tmux binary, no
venv interpreter). Once a pane exists, a missed boot or a wrong width is a
FAILURE.

Run: python3 tests/test_minimonitor_width_pin_live.py
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS = REPO_ROOT / "tests" / "lib" / "minimonitor_width_pin_harness.py"

#: The interpreter the framework installs its Textual into.
PYTHON = Path.home() / ".aitask" / "venv" / "bin" / "python"

#: tmux's default detached size — the geometry a restored window is split in.
DETACHED_W, DETACHED_H = 80, 24
#: The first client view in the report.
VIEWED_W = 270
TARGET = 40

#: Boot budget; a cold start settles in ~2-3s. Exceeding it is a FAILURE.
BOOT_TIMEOUT_S = 45.0
#: How long the fixed run may take to pin back after the growth.
PIN_TIMEOUT_S = 10.0
#: How long the control is watched for an (unexpected) correction.
SETTLE_S = 4.0
POLL_INTERVAL_S = 0.2

#: The control must stay at least this wide. The report measured 135; anything
#: at or below 2x the target would mean the fixture no longer reproduces it.
CONTROL_MIN_WIDTH = 2 * TARGET


def _tmux(socket, *args, check=True):
    return subprocess.run(["tmux", "-L", socket, *args],
                          capture_output=True, text=True, check=check)


class _PaneRun:
    """One harness run in its own tmux server; a context manager."""

    def __init__(self, out_dir: Path, legacy: bool) -> None:
        self.out_dir = out_dir
        self.legacy = legacy
        self.socket = f"ait_t2050_{'leg' if legacy else 'cur'}_{os.getpid()}"
        self.window = None
        self.pane = None

    def __enter__(self):
        self.out_dir.mkdir(parents=True, exist_ok=True)
        _tmux(self.socket, "-f", "/dev/null", "new-session", "-d", "-s", "pin",
              "-x", str(DETACHED_W), "-y", str(DETACHED_H))
        # `-u COLUMNS -u LINES`: Rich honours those over the real pty size and
        # pytest exports them; the tmux server inherits them from this process.
        # See tests/test_minimonitor_bottom_pin_live.py for the measurement.
        argv = ["env", "-u", "COLUMNS", "-u", "LINES",
                f"AITASKS_TMUX_SOCKET={self.socket}"]
        if self.legacy:
            argv.append("AIT_T2050_LEGACY_PIN=1")
        argv += [str(PYTHON), str(HARNESS), "--out-dir", str(self.out_dir)]
        # tmux hands the command to a shell, so every path is quoted — a temp
        # dir or home with a space in it would otherwise never start the harness.
        # stdout stays on the tty: without it Textual gets no terminal size and
        # no SIGWINCH, which is the very event under test.
        cmd = (f"{shlex.join(argv)} "
               f"2>{shlex.quote(str(self.out_dir / 'err.log'))}")
        res = _tmux(self.socket, "split-window", "-h", "-l", str(TARGET),
                    "-P", "-F", "#{window_id} #{pane_id}", cmd)
        self.window, self.pane = res.stdout.split()
        return self

    def __exit__(self, *exc):
        _tmux(self.socket, "kill-server", check=False)
        return False

    def width(self) -> int:
        res = _tmux(self.socket, "display-message", "-p", "-t", self.pane,
                    "#{pane_width}")
        return int(res.stdout.strip())

    def window_width(self) -> int:
        res = _tmux(self.socket, "display-message", "-p", "-t", self.pane,
                    "#{window_width}")
        return int(res.stdout.strip())

    def rows(self) -> list[dict]:
        trace = self.out_dir / "trace.jsonl"
        if not trace.exists():
            return []
        return [json.loads(line) for line in trace.read_text().splitlines()
                if line.strip()]

    def await_ready(self) -> None:
        deadline = time.monotonic() + BOOT_TIMEOUT_S
        while time.monotonic() < deadline:
            if any(r.get("event") == "ready" for r in self.rows()):
                return
            time.sleep(POLL_INTERVAL_S)
        err = self.out_dir / "err.log"
        raise AssertionError(
            f"{'legacy' if self.legacy else 'current'} harness never reported "
            f"ready within {BOOT_TIMEOUT_S}s; stderr: "
            f"{err.read_text()[-2000:] if err.exists() else '(none)'}")

    def grow(self) -> None:
        _tmux(self.socket, "resize-window", "-t", self.window,
              "-x", str(VIEWED_W), "-y", str(DETACHED_H))


@unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
@unittest.skipUnless(PYTHON.exists(), f"framework venv missing: {PYTHON}")
class RestoredWindowGrowthLiveTests(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ait_t2050_")
        self.addCleanup(self._tmp.cleanup)

    def _boot(self, legacy: bool) -> _PaneRun:
        run = _PaneRun(Path(self._tmp.name) / ("leg" if legacy else "cur"), legacy)
        # Cleanup BEFORE entering: if `new-session` succeeds and `split-window`
        # then raises, the server must still be killed. `kill-server` on a
        # server that never started is a harmless check=False no-op.
        self.addCleanup(run.__exit__, None, None, None)
        run.__enter__()
        run.await_ready()
        # The precondition both runs depend on: split at the target inside a
        # window that has not been viewed yet.
        self.assertEqual(run.window_width(), DETACHED_W)
        self.assertEqual(run.width(), TARGET)
        return run

    def test_a_restored_window_is_pinned_back_on_first_view(self):
        run = self._boot(legacy=False)
        run.grow()
        self.assertEqual(run.window_width(), VIEWED_W)
        deadline = time.monotonic() + PIN_TIMEOUT_S
        width = run.width()
        while width != TARGET and time.monotonic() < deadline:
            time.sleep(POLL_INTERVAL_S)
            width = run.width()
        pins = [r for r in run.rows() if r.get("event") == "pin"]
        self.assertEqual(
            width, TARGET,
            f"companion is {width} cols after the window grew to {VIEWED_W}; "
            f"pin calls seen: {pins}")
        self.assertTrue(
            any(r["width"] > TARGET for r in pins),
            f"the pin never saw the grown width — the fixture did not deliver "
            f"the growth it claims to: {pins}")

    def test_the_pre_fix_pin_leaves_the_companion_wide(self):
        """Negative control: the reported ~135 must reproduce under the old read."""
        run = self._boot(legacy=True)
        run.grow()
        self.assertEqual(run.window_width(), VIEWED_W)
        widths = []
        deadline = time.monotonic() + SETTLE_S
        while time.monotonic() < deadline:
            widths.append(run.width())
            time.sleep(POLL_INTERVAL_S)
        pins = [r for r in run.rows() if r.get("event") == "pin"]
        self.assertTrue(
            pins, "the control's pin was never called — it proves nothing")
        self.assertGreaterEqual(
            min(widths), CONTROL_MIN_WIDTH,
            f"the pre-fix pin corrected the companion (widths {widths}); the "
            f"fixture no longer reproduces the t2050 drift, so the fixed run's "
            f"pass is not evidence. Pin calls: {pins}")
        self.assertTrue(
            any(r["stale"] < r["width"] for r in pins),
            f"no pin call saw a stale self.size — the drift was reproduced for "
            f"some other reason: {pins}")


if __name__ == "__main__":
    unittest.main()
