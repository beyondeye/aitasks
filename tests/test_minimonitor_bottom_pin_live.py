"""Live acceptance for minimonitor's bottom-of-list pin (t1653).

**A headless test cannot stand in for this one.** `App.run_test` settles layout
synchronously, so a synthesised drag always lands exactly on `max_scroll_y` and
Textual re-arms its anchor on its own; the arming mechanism is therefore
invisible to it. Measured: `_restore_list_scroll` ran at `attempt=0` against
final geometry and produced ZERO shortfall at N = 6/12/24/48/96 cards.

WHAT THIS DRIVES. A real `MiniMonitorApp` (via `tests/lib/minimonitor_live_harness.py`,
which subclasses `_RefreshHost` — the real app with only its tmux-facing
collaborators stubbed) in a real tmux pane under a real pty, scrolled by a real
SGR mouse gesture: button press on the thumb, motion to the trough end, release.
`minimonitor_app.main()`'s tmux detection and config load are NOT exercised;
`MiniPaneList`, `_capture_list_scroll`, `_rebuild_pane_list` and
`_restore_list_scroll` all are. That is the boundary claimed, and no more.

NOTHING IS ASSUMED ABOUT GEOMETRY. The pane size is pinned server-side, and the
gesture's coordinates are then computed from what the app itself reports through
the compositor (`app.screen.find_widget(bar).region`), not from constants. A
hard-coded SGR coordinate that misses the thumb produces a silent no-op drag that
BOTH the fixed and the control run would "pass". Two assertions close that hole —
the harness emits a `grab` event, and `test_3b` checks the list actually moved —
and between them they caught five real fixture faults while this was built, each
of which had first presented as "the fix does not work":

* `split-window` with stdout redirected to a file left the app at the default
  80x24 inside a 40x40 pane, with no SIGWINCH and every coordinate off;
* a 30-card list at 40x40 gave `virtual_h == container_h` and never overflowed;
* geometry sampled straight after `await _refresh_data()` reads a mid-rebuild
  `max_scroll_y` of 0, so it was never published at all;
* a single motion event is dropped when it lands mid-rebuild (5 failures / 12);
* a press row scaled by `thumb_size` misses when the churn resizes the thumb
  between reading the geometry and sending the press (1 failure / 12).

THE NEGATIVE CONTROL IS EXECUTABLE. `AIT_T1653_LEGACY_PIN=1` restores the pre-fix
world: the `at_bottom` geometry snapshot applied once via
`scroll_end(immediate=True, force=True)`, AND `_anchored` cleared so Textual's
anchor is not holding the offset. Both halves are required — a control that
undoes only the app's capture/restore measures the FIX, reports a zero gap, and
makes the whole comparison vacuous (observed). With both, the control reproduces
the reported symptom: the view sticks and never returns to the bottom, with the
gap growing to 146 rows as the content grows — the reporter's "the distance
jumped is larger on a longer list".

Raw `tmux` is correct in `tests/`: `tests/test_no_raw_tmux.sh` scopes its guard to
`.aitask-scripts/` and explicitly exempts fixtures. Isolation follows
`tests/test_board_startup_focus_live.py` — a throwaway per-process socket with
`AITASKS_TMUX_SOCKET` exported into the pane through an `env` prefix on the
command, so the app's own gateway calls stay on it and `kill-server` can only
reach the server we started.

Skip-vs-fail: `SkipTest` only for environment unavailability (no tmux binary, no
server, no pane). Once a pane exists, a lost pin — or a missed gesture — is a
FAILURE.

Run: python3 tests/test_minimonitor_bottom_pin_live.py
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
HARNESS = REPO_ROOT / "tests" / "lib" / "minimonitor_live_harness.py"

#: The interpreter the framework installs its Textual into.
PYTHON = Path.home() / ".aitask" / "venv" / "bin" / "python"

#: Pinned server-side so the pane's coordinate space and the app's agree. A
#: mismatch is what makes a synthesised mouse event land somewhere else entirely.
WINDOW_W, WINDOW_H = 120, 40
PANE_W = 40
AGENTS = 40

#: Boot budget. The harness publishes `geometry.json` as soon as the list has
#: laid out and overflows; a cold start settles in ~3s. Exceeding this is a
#: FAILURE, not a skip.
BOOT_TIMEOUT_S = 45.0
POLL_INTERVAL_S = 0.5


#: Seconds of post-drag observation. At the harness's 0.5s tick this is ~18
#: samples, comfortably over the 10 the acceptance criteria ask for.
OBSERVE_S = 9.0

#: Samples discarded after the release. The scroll the release triggered is still
#: animating when the next tick fires, so that one sample is in flight rather than
#: settled — measured at a 50-row gap in BOTH the fixed and the control run, which
#: is exactly why it must not count for either of them. Everything before the
#: release is already excluded: see `drag_thumb_to_the_end`.
SETTLE_SAMPLES = 1

#: Minimum steady-state samples required, per the acceptance criteria.
MIN_SAMPLES = 10


def _tmux(socket, *args, check=True):
    return subprocess.run(["tmux", "-L", socket, *args],
                          capture_output=True, text=True, check=check)


class _PaneRun:
    """One harness run in its own tmux server; a context manager."""

    def __init__(self, out_dir: Path, legacy: bool) -> None:
        self.out_dir = out_dir
        self.legacy = legacy
        self.socket = f"ait_t1653_{'leg' if legacy else 'cur'}_{os.getpid()}"
        self.pane = None

    def __enter__(self):
        self.out_dir.mkdir(parents=True, exist_ok=True)
        _tmux(self.socket, "new-session", "-d", "-s", "pin",
              "-x", str(WINDOW_W), "-y", str(WINDOW_H))
        # `-u COLUMNS -u LINES` is load-bearing, not hygiene. Rich (and so
        # Textual) honours those variables OVER the real pty size, pytest exports
        # them for its own terminal writer, and the tmux server inherits the
        # environment of the client that started it — so the pane's app came up
        # 80x24 inside a 40x40 pane whenever this file ran under pytest, which is
        # how the suite runs it. Every mouse coordinate computed from the pane
        # then lands somewhere else. Measured: 6 errors under `pytest`, 0 when the
        # same file was run directly, until these were unset.
        envs = f"-u COLUMNS -u LINES AITASKS_TMUX_SOCKET={self.socket}"
        if self.legacy:
            envs += " AIT_T1653_LEGACY_PIN=1"
        # A second pane is mandatory, not cosmetic: minimonitor auto-closes when
        # it is alone in its window.
        #
        # stdout MUST stay on the tty. Redirecting it to a file leaves Textual
        # with no terminal size and no SIGWINCH — measured, the app then ran at
        # the default 80x24 inside a 40x40 pane and every mouse coordinate was
        # off by the difference.
        cmd = (f"env {envs} {PYTHON} {HARNESS} --out-dir {self.out_dir} "
               f"--agents {AGENTS} 2>{self.out_dir / 'err.log'}")
        res = _tmux(self.socket, "split-window", "-h", "-l", str(PANE_W),
                    "-P", "-F", "#{pane_id}", cmd)
        self.pane = res.stdout.strip()
        return self

    def __exit__(self, *exc):
        _tmux(self.socket, "kill-server", check=False)
        return False

    # -- driving -------------------------------------------------------------

    def await_geometry(self):
        """Wait for geometry that MATCHES THE PANE, not merely for a file.

        A process started by `split-window` can read its terminal size before
        tmux has sized the pane, and then never hears about it: measured, the app
        came up 80x24 inside a 40x40 pane, and every mouse coordinate computed
        from the pane would have been off by the difference. Keeping stdout on
        the tty removed the systematic case, but the race survives under load —
        it reappeared once in a full-suite run while 15 standalone runs were
        clean.

        So this polls until the app REPORTS the pane's width rather than
        accepting the first geometry published. That check is what caught the
        `COLUMNS` inheritance described in `__enter__`, and its failure message
        carries the app's own view of its size, whether stdout is a tty, and the
        `TERM` / `COLUMNS` it was given — enough to tell "the pane is the wrong
        size" from "the app was told the wrong size", which look identical from
        the outside.
        """
        deadline = time.monotonic() + BOOT_TIMEOUT_S
        path = self.out_dir / "geometry.json"
        last = None
        while time.monotonic() < deadline:
            if path.exists():
                try:
                    last = json.loads(path.read_text())
                except json.JSONDecodeError:
                    last = None                 # mid-rewrite; try again
                if last is not None and last["list_region"][2] == PANE_W:
                    return last
            time.sleep(POLL_INTERVAL_S)
        raise AssertionError(
            f"{'legacy' if self.legacy else 'current'} run never published "
            f"geometry matching the {PANE_W}-column pane within "
            f"{BOOT_TIMEOUT_S}s (last={last}). The harness records why it could "
            f"not: {self._deferrals()}")

    def _deferrals(self):
        trace = self.out_dir / "trace.jsonl"
        if not trace.exists():
            return "no trace at all — the harness never started"
        return [r for r in self._rows() if r.get("event") == "geometry_deferred"][-3:]

    def _rows(self):
        trace = self.out_dir / "trace.jsonl"
        if not trace.exists():
            return []
        return [json.loads(line) for line in
                trace.read_text().splitlines() if line.strip()]

    def send(self, text: str) -> None:
        _tmux(self.socket, "send-keys", "-t", self.pane, "-l", text)

    def drag_thumb_to_the_end(self):
        """Press on the thumb, drag past the trough end, release.

        Re-reads the geometry rather than reusing the boot snapshot: the harness
        republishes it every tick because the content churns, and a stale
        `thumb_top` / `thumb_size` aims the press at the trough instead of the
        thumb.

The press row is offset from the thumb's TOP, not from its middle, and
        that distinction is load-bearing. `thumb_top` is
        `position * window_size / virtual`, so it is 0 for as long as `scroll_y`
        is 0 — the state the list boots in and stays in until this gesture, which
        the caller asserts. `thumb_size` is `window_size**2 / virtual` and the
        churn moves it between 5 and 19 rows, so an offset scaled by it can be
        stale by the time the press is sent: aiming at the middle of a 19-row
        thumb misses a 5-row one entirely. Measured: 1 failure in 12 runs, on the
        grab. One row below the top is inside the thumb for every size the churn
        can produce.

        Row 0 is avoided deliberately — pressing it grabbed the thumb but moved
        the list on only 7 of 12 runs, before the motion stream below was
        introduced.

        Returns `(pre_mark, post_mark, geometry, scroll_y_before)` — two
        boundaries because the two things being observed have different windows:
        the grab/release EVENTS happen during the gesture, while the scroll
        SAMPLES only mean anything after it.
        """
        geometry = json.loads((self.out_dir / "geometry.json").read_text())
        rows = self._rows()
        pre_mark = len(rows)
        samples = [r for r in rows if "tick" in r and "max_scroll_y" in r]
        before = samples[-1]["scroll_y"] if samples else None
        x, y, _w, _h = geometry["scrollbar_region"]
        col = x + 1                                     # SGR is 1-based
        press = y + geometry["thumb_top"] + (1 if geometry["thumb_size"] > 1 else 0) + 1
        end = y + geometry["window_size"]
        self.send(f"\033[<0;{col};{press}M")            # button 1 down
        time.sleep(0.2)
        # MANY motion events, not one. `Widget._on_scroll_to` drops a `ScrollTo`
        # outright when `_allow_scroll` is False, and on a `VerticalScroll` that
        # tracks `show_vertical_scrollbar` — which is False for the part of every
        # tick when the container is childless mid-rebuild. A single motion that
        # happens to land in that window is silently discarded, and the run then
        # looks like a lost pin instead of a lost gesture (measured: 5 of 12 runs
        # with one motion event). A real drag emits a stream of them, and so does
        # this: the later ones all target the trough end, so whichever lands
        # outside the rebuild window is the one that counts.
        for row in (press + (end - press) // 2, end, end, end, end):
            self.send(f"\033[<32;{col};{row}M")         # motion, button held
            time.sleep(0.2)
        self.send(f"\033[<0;{col};{end}m")              # release
        # The window starts at the RELEASE, not at the press. The gesture above
        # spans ~1.2s — two or three ticks at TICK_SECONDS — and a sample taken
        # while the user is still dragging is not a steady state by definition;
        # counting it would measure the drag rather than the pin, and would make
        # the discard count below a magic number that has to track the gesture's
        # length.
        return pre_mark, len(self._rows()), geometry, before

    def observe(self, pre_mark: int, post_mark: int):
        time.sleep(OBSERVE_S)
        rows = self._rows()
        events = [r["event"] for r in rows[pre_mark:] if "event" in r]
        samples = [r for r in rows[post_mark:]
                   if "tick" in r and "max_scroll_y" in r]
        return events, samples


def _run_one(out_dir: Path, legacy: bool):
    with _PaneRun(out_dir, legacy) as run:
        run.await_geometry()
        pre_mark, post_mark, geometry, before = run.drag_thumb_to_the_end()
        events, samples = run.observe(pre_mark, post_mark)
    return geometry, events, samples, before


class BottomPinLiveTests(unittest.TestCase):
    """AC1/AC2/AC5 — and the pre-fix control that makes them mean something."""

    maxDiff = None

    @classmethod
    def setUpClass(cls):
        if shutil.which("tmux") is None:
            raise unittest.SkipTest("tmux not available")
        if not PYTHON.exists():
            raise unittest.SkipTest(f"framework interpreter missing: {PYTHON}")
        try:
            subprocess.run(["tmux", "-V"], capture_output=True, check=True)
        except Exception as exc:                        # noqa: BLE001
            raise unittest.SkipTest(f"tmux unusable: {exc}")

        import tempfile
        cls._tmp = tempfile.TemporaryDirectory(prefix="t1653_live_")
        root = Path(cls._tmp.name)
        cls.cur = _run_one(root / "current", legacy=False)
        cls.legacy = _run_one(root / "legacy", legacy=True)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "_tmp"):
            cls._tmp.cleanup()

    # -- the assertions, in order; each gates the next --------------------

    def test_1_the_fixture_overflows(self):
        for label, (geometry, _e, _s, before) in (("current", self.cur),
                                                  ("legacy", self.legacy)):
            self.assertEqual(
                before, 0,
                f"{label}: the list was not at the top when the gesture was "
                f"aimed (scroll_y={before}), so the press row is not guaranteed "
                "to be on the thumb — see drag_thumb_to_the_end")
            self.assertGreater(
                geometry["max_scroll_y"], 0,
                f"{label}: the list never overflowed, so there was no thumb to "
                f"drag and every assertion below would be vacuous: {geometry}")
            self.assertEqual(
                geometry["list_region"][2], PANE_W,
                f"{label}: the app's own width ({geometry['list_region'][2]}) "
                f"disagrees with the pane's ({PANE_W}) — the mouse coordinate "
                "spaces do not match and the gesture cannot be aimed")

    def test_2_the_press_hit_the_thumb(self):
        for label, (geometry, events, _s, _b) in (("current", self.cur),
                                                  ("legacy", self.legacy)):
            x, y, _w, _h = geometry["scrollbar_region"]
            self.assertIn(
                "grab", events,
                f"{label}: the synthesised press missed the thumb — no grab was "
                f"observed. Computed col={x + 1}, "
                f"row={y + geometry['thumb_top'] + (1 if geometry['thumb_size'] > 1 else 0) + 1} from "
                f"scrollbar_region={geometry['scrollbar_region']} "
                f"(thumb_size={geometry['thumb_size']} at press time). A run "
                f"without a real drag proves nothing about the pin. "
                f"Events seen: {events}")

    def test_3_the_two_runs_are_comparable(self):
        keys = ("list_region", "scrollbar_region", "window_size", "agents")
        cur = {k: self.cur[0][k] for k in keys}
        legacy = {k: self.legacy[0][k] for k in keys}
        self.assertEqual(
            cur, legacy,
            "the fixed and control runs did not get the same geometry, so any "
            "difference between them could be the fixture rather than the fix")

    def test_3b_the_gesture_actually_scrolled_the_list(self):
        """A press that misses the thumb, or a drag tmux swallowed, leaves the
        list exactly where it was — which looks identical to "the pin was lost"
        in the trace. Separating the two is the difference between a fixture
        fault and a product fault, and this fixture has produced both."""
        for label, (_g, _e, samples, before) in (("current", self.cur),
                                                 ("legacy", self.legacy)):
            moved = [s for s in samples if s["scroll_y"] != before]
            self.assertTrue(
                moved,
                f"{label}: the drag never moved the list — scroll_y stayed at "
                f"{before} for all {len(samples)} samples. The gesture did not "
                "land; this run says nothing about the bottom pin.")

    def test_4_the_control_reproduces_the_reported_drift(self):
        """Without this the test below could pass against a fixture in which the
        bug never occurs — which is exactly what happened twice while building
        it."""
        _g, _e, samples, _b = self.legacy
        steady = samples[SETTLE_SAMPLES:]
        self.assertGreaterEqual(
            len(steady), MIN_SAMPLES,
            f"control produced only {len(steady)} steady-state samples")
        gaps = [s["max_scroll_y"] - s["scroll_y"] for s in steady]
        self.assertGreater(
            max(gaps), 1,
            "the PRE-FIX control held the bottom pin, so this fixture does not "
            "reproduce the reported bug and the fixed run below proves nothing. "
            f"gaps={gaps}")

    def test_5_the_pin_holds_across_every_settled_tick(self):
        """AC1 and AC2: the pin survives card-height churn AND agents coming and
        going, with no further user gesture after the drag."""
        _g, _e, samples, _b = self.cur
        steady = samples[SETTLE_SAMPLES:]
        self.assertGreaterEqual(
            len(steady), MIN_SAMPLES,
            f"only {len(steady)} steady-state samples; the acceptance criteria "
            f"ask for at least {MIN_SAMPLES}")
        heights = {s["virtual_h"] for s in steady}
        self.assertGreater(
            len(heights), 1,
            f"the content height never changed ({heights}) — the churn that "
            "causes the bug did not happen, so this run is vacuous")
        offenders = [(s["tick"], s["scroll_y"], s["max_scroll_y"])
                     for s in steady if s["max_scroll_y"] - s["scroll_y"] != 0]
        self.assertEqual(
            offenders, [],
            "the bottom-pinned list drifted off the bottom on "
            f"{len(offenders)} of {len(steady)} settled ticks "
            "(tick, scroll_y, max_scroll_y): " + repr(offenders))


if __name__ == "__main__":
    unittest.main(verbosity=2)
