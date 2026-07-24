"""Guard tests for the MonitorApp mount-time window rename gate (t1240).

``MonitorApp.on_mount`` renames its tmux window to ``monitor`` so the TUI
switcher can find it. That rename used to fire on every mount whenever $TMUX
was set — including Textual ``run_test()`` mounts inside unit tests. A test
suite run from a coding agent's tmux pane inherits the agent's $TMUX_PANE, so
the rename relabeled the *agent's own window* as ``monitor`` on the live tmux
server.

The fix gates the rename on a ``rename_window`` constructor flag that only the
production launcher (``main()``) sets. These tests pin the gate from the mount
level:

1. Guard: a default-constructed (test-style) mount never issues a rename, even
   with $TMUX / $TMUX_PANE present.
2. Production pin: ``rename_window=True`` still issues the pinned rename argv,
   preserving switcher discovery for the real ``ait monitor`` path.
3. Fail-safe pin: ``rename_window=True`` without $TMUX_PANE issues no rename
   (the t941/t1130 empty-argv guard, exercised through on_mount).

``subprocess.run`` is patched in the monitor_app namespace, so no real tmux
call is ever made; ``_start_monitoring`` is neutralized to keep the mount
inert (the surface under test is only the rename gate).
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

import monitor.monitor_app as monitor_app  # noqa: E402
from monitor.monitor_app import MonitorApp  # noqa: E402

FAKE_TMUX_ENV = {"TMUX": "/tmp/fake-tmux-sock,1,0", "TMUX_PANE": "%99"}


class RenameGateTests(unittest.IsolatedAsyncioTestCase):

    async def _mount_and_capture(
        self, env: dict[str, str], **app_kwargs
    ) -> list[list[str]]:
        """Mount a MonitorApp under a fake tmux env and return every argv
        passed to monitor_app.subprocess.run during the mount."""
        calls: list[list[str]] = []

        def record_run(argv, *args, **kwargs):
            calls.append(list(argv))
            return mock.Mock(returncode=0, stdout=b"", stderr=b"")

        scrubbed = {k: v for k, v in os.environ.items()
                    if k not in ("TMUX", "TMUX_PANE")}
        with mock.patch.dict(os.environ, {**scrubbed, **env}, clear=True), \
                mock.patch.object(monitor_app.subprocess, "run", record_run), \
                mock.patch.object(MonitorApp, "_start_monitoring",
                                  lambda self: None):
            app = MonitorApp(session="demo", project_root=REPO_ROOT,
                             **app_kwargs)
            async with app.run_test(size=(100, 30)):
                pass
        return calls

    def _rename_calls(self, calls: list[list[str]]) -> list[list[str]]:
        return [argv for argv in calls if "rename-window" in argv]

    async def test_default_mount_never_renames(self):
        """Guard: a test-style mount (no rename_window) must not touch the
        tmux server even when $TMUX / $TMUX_PANE point at a live pane."""
        calls = await self._mount_and_capture(FAKE_TMUX_ENV)
        self.assertEqual(self._rename_calls(calls), [])

    async def test_production_flag_renames_own_pane(self):
        """Production pin: the launcher path (rename_window=True) still issues
        the pane-pinned rename so the TUI switcher can find the window."""
        calls = await self._mount_and_capture(FAKE_TMUX_ENV, rename_window=True)
        self.assertEqual(
            self._rename_calls(calls),
            [["tmux", "rename-window", "-t", "%99", "monitor"]],
        )

    async def test_production_flag_without_pane_is_failsafe(self):
        """Fail-safe pin: without $TMUX_PANE there is no reliable own-window
        target, so even the production path issues no rename (t941/t1130)."""
        calls = await self._mount_and_capture(
            {"TMUX": FAKE_TMUX_ENV["TMUX"]}, rename_window=True
        )
        self.assertEqual(self._rename_calls(calls), [])


if __name__ == "__main__":
    unittest.main()
