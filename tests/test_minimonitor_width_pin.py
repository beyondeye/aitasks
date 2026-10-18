"""The minimonitor width pin must decide from the NEW size (t2050).

`MiniMonitorApp.on_resize` re-pins the companion pane to `target_width` when it
has grown wider (t978). It used to read `self.size.width`, and in Textual 8.2.7
a subclass's public `on_resize` runs BEFORE `App._on_resize` stores the event's
size — so `self.size` inside the handler is the PREVIOUS size. A 40 -> 135
growth (an `ait ide`-restored window split at 80 columns, first viewed at 270)
read as 40, took the early return, and the companion stayed 135 wide.

WHAT THIS DRIVES. The real `MiniMonitorApp`, booted with `TMUX` scrubbed so its
`on_mount` takes the "Not inside tmux" early return, and resized through
`Pilot.resize_terminal` — which posts a real `events.Resize` through the App's
own dispatch. That is what makes `self.size` genuinely stale inside the handler,
so a test here fails on the pre-fix code instead of passing vacuously. Only
`_monitor` is replaced, by a fake that records `resize_pane` calls; the tmux side
of the pin is exercised live by `tests/test_minimonitor_width_pin_live.py`.

Behaviour pinned: "correct only when wider" (t978) — a pane narrower than the
target is left alone, whatever narrowed it.

Run: python3 tests/test_minimonitor_width_pin.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

# Nothing here may touch the pane the suite runs in, and the scrubbed `TMUX` is
# what sends `on_mount` down its early return (no tmux detection, no marker
# stamping, no refresh timer).
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from monitor import minimonitor_app as mm  # noqa: E402

OWN_PANE = "%9"
TARGET = 40
BOOT_SIZE = (TARGET, 14)


class _RecordingMonitor:
    """Stands in for `TmuxMonitor`; only `resize_pane` is reachable from the pin."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int | None]] = []

    def resize_pane(self, pane, *, x=None, y=None, timeout=2.0):
        self.calls.append((pane, x))
        return (0, "")


class _Host(mm.MiniMonitorApp):
    """The REAL app; only `__init__` is narrowed to the arguments without defaults."""

    def __init__(self) -> None:
        super().__init__(session="t2050", project_root=REPO_ROOT,
                         target_width=TARGET)


class WidthPinTests(unittest.TestCase):

    def _resize(self, width: int, *, pane: str | None = OWN_PANE,
                with_monitor: bool = True) -> tuple[list, int]:
        """Boot at the target width, then resize the terminal to `width`.

        Returns the recorded `resize_pane` calls and the app's `size.width` as
        seen at the START of the handler — captured so each test can prove the
        stale-size precondition it depends on actually held.
        """
        seen_stale: list[int] = []

        async def go():
            app = _Host()
            async with app.run_test(size=BOOT_SIZE) as pilot:
                monitor = _RecordingMonitor()
                if with_monitor:
                    app._monitor = monitor
                original = app._maybe_pin_width

                def spy(w):
                    seen_stale.append(app.size.width)
                    return original(w)

                app._maybe_pin_width = spy
                env = {} if pane is None else {"TMUX_PANE": pane}
                with mock.patch.dict(os.environ, env):
                    if pane is None:
                        os.environ.pop("TMUX_PANE", None)
                    await pilot.resize_terminal(width, BOOT_SIZE[1])
                    await pilot.pause()
                return monitor.calls

        calls = asyncio.run(go())
        self.assertTrue(seen_stale, "on_resize never reached the pin — the test is inert")
        return calls, seen_stale[0]

    def test_growth_is_pinned_back_to_the_target(self):
        calls, stale = self._resize(55)
        # The precondition that made the pre-fix pin miss: inside the handler
        # the app still reports the boot width.
        self.assertEqual(stale, TARGET, "self.size was not stale — this no longer "
                         "reproduces the t2050 ordering")
        self.assertEqual(calls, [(OWN_PANE, TARGET)])

    def test_restored_window_growth_is_pinned_back(self):
        """The reported shape: 80 -> 270 spreads 95 columns into a 40-col pane."""
        calls, _ = self._resize(135)
        self.assertEqual(calls, [(OWN_PANE, TARGET)])

    def test_exactly_the_target_issues_no_resize(self):
        # Boot is already at the target, so resize away and back is the only way
        # to deliver a Resize AT the target; a no-op resize posts nothing.
        async def go():
            app = _Host()
            async with app.run_test(size=(55, 14)) as pilot:
                monitor = _RecordingMonitor()
                app._monitor = monitor
                with mock.patch.dict(os.environ, {"TMUX_PANE": OWN_PANE}):
                    await pilot.resize_terminal(TARGET, 14)
                    await pilot.pause()
                return monitor.calls

        self.assertEqual(asyncio.run(go()), [])

    def test_a_narrower_pane_is_left_alone(self):
        calls, _ = self._resize(20)
        self.assertEqual(calls, [], "the pin corrects only when wider (t978)")

    def test_no_own_pane_issues_no_resize(self):
        calls, _ = self._resize(135, pane=None)
        self.assertEqual(calls, [])

    def test_no_monitor_is_a_no_op(self):
        # Must not raise either: `_monitor` is None until `_start_monitoring`.
        calls, _ = self._resize(135, with_monitor=False)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
