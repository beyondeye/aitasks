"""Production wiring for the `@aitask_monitor_kind` pane marker (t1451).

Every *guard* test in this suite starts from a pane that is already marked, so a
missed import, an unset constructor flag, or a dropped lifecycle call would
leave all of them green while production never writes a marker at all and the
whole feature is inert. This file pins the writing side end to end:

* both `main()`s pass `mark_pane=True` — the link `test_monitor_rename_gate.py`
  notably does *not* cover for its own `rename_window` flag, and exactly where a
  flag gets dropped;
* both `on_mount`s stamp `<kind>:<os.getpid()>`, and the value they write is fed
  straight back through `monitor_marker_state` so a writer can never emit
  something its own readers classify as unparseable;
* both `on_unmount`s clear it;
* a default (test-style) construction does **neither**, even with $TMUX /
  $TMUX_PANE pointing at a live pane — the t1240 isolation invariant that keeps
  the rest of the suite from writing to the running agent's own pane.

Mount-level structure follows `tests/test_monitor_rename_gate.py`: a scrubbed
env with a fake tmux pane, `_start_monitoring` neutralized, and every gateway
call recorded so no tmux call is ever made.

Run: python3 tests/test_monitor_pane_marker_wiring.py
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

import agent_launch_utils  # noqa: E402
import monitor.minimonitor_app as mm  # noqa: E402
import monitor.monitor_app as ma  # noqa: E402
from agent_launch_utils import MONITOR_KIND_OPTION  # noqa: E402
from monitor.minimonitor_app import MiniMonitorApp  # noqa: E402
from monitor.monitor_app import MonitorApp  # noqa: E402
from monitor_marker import STATE_PRESENT, monitor_marker_state  # noqa: E402

FAKE_TMUX_ENV = {"TMUX": "/tmp/fake-tmux-sock,1,0", "TMUX_PANE": "%99"}


class _RecordingTmux:
    """Stands in for `agent_launch_utils._TMUX`; records, never executes."""

    def __init__(self):
        self.calls: list[list[str]] = []

    def run(self, args, timeout=5.0):
        self.calls.append(list(args))
        return (0, "")

    def spawn(self, args, **kwargs):
        self.calls.append(list(args))


# (app class, its module, the kind it must stamp). Both apps are driven by the
# SAME assertions via subTest rather than by a test-defining base class two
# subclasses inherit — that shape silently re-collects every test per subclass
# (see tests/test_collection_structure.py).
APP_SPECS = [
    (MiniMonitorApp, mm, "minimonitor"),
    (MonitorApp, ma, "monitor"),
]


def _marker_writes(calls):
    return [c for c in calls
            if c and c[0] == "set-option" and MONITOR_KIND_OPTION in c
            and "-pu" not in c]


def _marker_clears(calls):
    return [c for c in calls
            if c and c[0] == "set-option" and MONITOR_KIND_OPTION in c
            and "-pu" in c]


class MarkerWiringTests(unittest.IsolatedAsyncioTestCase):

    async def _mount_and_capture(self, app_cls, module, env,
                                 **app_kwargs) -> list[list[str]]:
        tmux = _RecordingTmux()
        scrubbed = {k: v for k, v in os.environ.items()
                    if k not in ("TMUX", "TMUX_PANE")}
        with mock.patch.dict(os.environ, {**scrubbed, **env}, clear=True), \
                mock.patch.object(agent_launch_utils, "_TMUX", tmux), \
                mock.patch.object(module.subprocess, "run",
                                  lambda *a, **k: mock.Mock(
                                      returncode=0, stdout="", stderr="")), \
                mock.patch.object(app_cls, "_start_monitoring",
                                  lambda self: None):
            app = app_cls(session="demo", project_root=REPO_ROOT, **app_kwargs)
            async with app.run_test(size=(120, 40)):
                pass
        return tmux.calls

    async def test_production_flag_stamps_own_pane(self):
        for app_cls, module, kind in APP_SPECS:
            with self.subTest(kind=kind):
                calls = await self._mount_and_capture(
                    app_cls, module, FAKE_TMUX_ENV, mark_pane=True
                )
                writes = _marker_writes(calls)
                self.assertEqual(len(writes), 1,
                                 f"expected one stamp, got {writes}")
                argv = writes[0]
                self.assertEqual(
                    argv[:5],
                    ["set-option", "-p", "-t", "%99", MONITOR_KIND_OPTION],
                )
                self.assertEqual(argv[5], f"{kind}:{os.getpid()}")

    async def test_written_value_is_readable_by_our_own_reader(self):
        """Close the writer/reader loop: whatever we stamp must classify as
        `present`. A writer emitting something the guards call unparseable
        would block spawns forever and could never be self-healed."""
        for app_cls, module, kind in APP_SPECS:
            with self.subTest(kind=kind):
                calls = await self._mount_and_capture(
                    app_cls, module, FAKE_TMUX_ENV, mark_pane=True
                )
                value = _marker_writes(calls)[0][5]
                self.assertEqual(monitor_marker_state(value), STATE_PRESENT)

    async def test_unmount_clears_the_marker(self):
        for app_cls, module, kind in APP_SPECS:
            with self.subTest(kind=kind):
                calls = await self._mount_and_capture(
                    app_cls, module, FAKE_TMUX_ENV, mark_pane=True
                )
                clears = _marker_clears(calls)
                self.assertEqual(len(clears), 1,
                                 f"expected one clear, got {clears}")
                self.assertEqual(
                    clears[0],
                    ["set-option", "-pu", "-t", "%99", MONITOR_KIND_OPTION],
                )

    async def test_default_mount_never_touches_the_marker(self):
        """Isolation invariant (t1240): a run_test() mount inherits the running
        agent's $TMUX_PANE, so an ungated stamp would write to a live pane."""
        for app_cls, module, kind in APP_SPECS:
            with self.subTest(kind=kind):
                calls = await self._mount_and_capture(
                    app_cls, module, FAKE_TMUX_ENV
                )
                self.assertEqual(_marker_writes(calls), [])
                self.assertEqual(_marker_clears(calls), [])

    async def test_production_flag_without_pane_is_failsafe(self):
        """Without $TMUX_PANE there is no own-pane target; write nothing."""
        for app_cls, module, kind in APP_SPECS:
            with self.subTest(kind=kind):
                calls = await self._mount_and_capture(
                    app_cls, module, {"TMUX": FAKE_TMUX_ENV["TMUX"]},
                    mark_pane=True,
                )
                self.assertEqual(_marker_writes(calls), [])
                self.assertEqual(_marker_clears(calls), [])

    async def test_outside_tmux_marks_nothing(self):
        for app_cls, module, kind in APP_SPECS:
            with self.subTest(kind=kind):
                calls = await self._mount_and_capture(app_cls, module, {},
                                                      mark_pane=True)
                self.assertEqual(_marker_writes(calls), [])


class _AppRecorder:
    """Replaces the App class in a module's namespace during main()."""

    kwargs: dict = {}

    def __init__(self, **kwargs):
        type(self).kwargs = kwargs

    def run(self):
        pass


class MainPassesMarkPaneTests(unittest.TestCase):
    """The `main()` link — where a flag silently gets dropped.

    Driven for real rather than grepped: a source-text search cannot tell a live
    call from a comment or a dead branch.
    """

    def _drive(self, module, app_attr: str) -> dict:
        _AppRecorder.kwargs = {}
        with mock.patch.object(module, app_attr, _AppRecorder), \
                mock.patch.object(module, "_detect_tmux_session",
                                  lambda: "demo"), \
                mock.patch.object(sys, "argv", ["app.py", "--session", "demo"]):
            module.main()
        return _AppRecorder.kwargs

    def test_minimonitor_main_passes_mark_pane(self):
        kwargs = self._drive(mm, "MiniMonitorApp")
        self.assertIs(kwargs.get("mark_pane"), True)

    def test_monitor_main_passes_mark_pane(self):
        kwargs = self._drive(ma, "MonitorApp")
        self.assertIs(kwargs.get("mark_pane"), True)
        # The pre-existing production flag must survive alongside it.
        self.assertIs(kwargs.get("rename_window"), True)


if __name__ == "__main__":
    unittest.main()
