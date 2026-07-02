"""Regression tests for sync tmux calls on the monitor refresh path.

t1111_3 moves refresh-loop tmux round-trips onto async gateway calls so a slow
tmux response does not block Textual's event-loop thread.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

import monitor.monitor_core as monitor_core  # noqa: E402
from agent_launch_utils import AitasksSession  # noqa: E402
from monitor.monitor_app import MonitorApp  # noqa: E402
from monitor.monitor_core import TmuxMonitor  # noqa: E402
from monitor.tmux_control import TmuxControlState  # noqa: E402
from monitor.tmux_monitor import (  # noqa: E402
    PaneCategory,
    PaneSnapshot,
    TmuxPaneInfo,
)


def _snapshot(pane_id: str, window_name: str, session_name: str) -> PaneSnapshot:
    idx = int(pane_id.lstrip("%"))
    pane = TmuxPaneInfo(
        window_index=str(idx),
        window_name=window_name,
        pane_index="0",
        pane_id=pane_id,
        pane_pid=20_000 + idx,
        current_command="bash",
        width=80,
        height=24,
        category=PaneCategory.AGENT,
        session_name=session_name,
    )
    return PaneSnapshot(
        pane=pane,
        content=f"{window_name}\nready",
        timestamp=0.0,
        idle_seconds=0.0,
        is_idle=False,
    )


class _FakeRefreshMonitor:
    multi_session = True

    def __init__(self) -> None:
        self.snapshots = {
            "%1": _snapshot("%1", "agent-1", "demo"),
            "%2": _snapshot("%2", "agent-2", "other"),
        }
        self.async_calls: list[tuple[str, ...]] = []
        self.mapping_async_called = False

    async def capture_all_async(self) -> dict[str, PaneSnapshot]:
        return dict(self.snapshots)

    def get_session_to_project_mapping(self) -> dict[str, Path]:
        raise AssertionError("sync session mapping called during refresh")

    async def get_session_to_project_mapping_async(self) -> dict[str, Path]:
        self.mapping_async_called = True
        return {"demo": REPO_ROOT, "other": REPO_ROOT}

    def tmux_run(self, args, timeout=5.0):
        raise AssertionError(f"sync tmux_run called during refresh: {args}")

    async def tmux_run_async(self, args, timeout=5.0):
        self.async_calls.append(tuple(args))
        if args[:1] == ["show-environment"]:
            return 0, "AITASK_MONITOR_FOCUS_WINDOW=agent-2\n"
        if args[:1] == ["set-environment"]:
            return 0, ""
        if args[:1] == ["display-message"]:
            return 0, "attached_demo\n"
        return 1, ""

    def control_state(self) -> TmuxControlState:
        return TmuxControlState.CONNECTED

    def get_compare_mode(self, pane_id: str) -> str:
        return "stripped"

    def is_compare_mode_overridden(self, pane_id: str) -> bool:
        return False


class MonitorRefreshNoSyncTmuxTests(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def test_refresh_uses_async_tmux_for_focus_clear_and_session_bar(self):
        async def runner():
            app = MonitorApp(session="demo", project_root=REPO_ROOT)
            async with app.run_test(size=(100, 30)) as pilot:
                fake = _FakeRefreshMonitor()
                app._monitor = fake
                app._focused_pane_id = "%1"

                await app._refresh_data()
                await pilot.pause()

                self.assertTrue(fake.mapping_async_called)
                self.assertEqual(app._focused_pane_id, "%2")
                self.assertIn(
                    (
                        "show-environment", "-t", "=demo",
                        "AITASK_MONITOR_FOCUS_WINDOW",
                    ),
                    fake.async_calls,
                )
                self.assertIn(
                    (
                        "set-environment", "-t", "=demo", "-u",
                        "AITASK_MONITOR_FOCUS_WINDOW",
                    ),
                    fake.async_calls,
                )
                self.assertIn(
                    ("display-message", "-p", "#S"),
                    fake.async_calls,
                )

        self._run(runner())

    def test_auto_switch_rebuild_session_bar_has_sync_fallback(self):
        async def runner():
            app = MonitorApp(session="demo", project_root=REPO_ROOT)
            async with app.run_test(size=(100, 30)) as pilot:
                fake = _FakeRefreshMonitor()
                app._monitor = fake
                app._snapshots = fake.snapshots

                app.action_toggle_auto_switch()
                await pilot.pause()

                bar = app.query_one("#session-bar")
                self.assertIn("attached: demo", str(bar.content))

        self._run(runner())

    def test_multi_session_capture_uses_async_session_discovery_on_cold_cache(self):
        async def runner():
            mon = TmuxMonitor(
                session="demo",
                multi_session=True,
                agent_prefixes=["agent-"],
                prompt_patterns=[],
            )
            session = AitasksSession(
                session="sessA",
                project_root=REPO_ROOT,
                project_name=REPO_ROOT.name,
            )
            async_calls: list[tuple[str, ...]] = []

            def fail_sync_discovery(*, include_registered: bool = False):
                raise AssertionError("sync discovery called during async refresh")

            async def fake_async_discovery(*, include_registered: bool = False):
                return [session]

            async def fake_tmux_async(args, timeout=5.0):
                async_calls.append(tuple(args))
                if args[:4] == ["list-panes", "-s", "-t", "=sessA"]:
                    return (
                        0,
                        "0\tagent-1\t0\t%1\t12345\tbash\t80\t24\t",
                    )
                if args[:1] == ["capture-pane"]:
                    return 0, "agent output\n"
                return 1, ""

            orig_sync = monitor_core.discover_aitasks_sessions
            orig_async = monitor_core.discover_aitasks_sessions_async
            monitor_core.discover_aitasks_sessions = fail_sync_discovery
            monitor_core.discover_aitasks_sessions_async = fake_async_discovery
            mon._tmux_async = fake_tmux_async
            try:
                snapshots = await mon.capture_all_async()
                mapping = await mon.get_session_to_project_mapping_async()
            finally:
                monitor_core.discover_aitasks_sessions = orig_sync
                monitor_core.discover_aitasks_sessions_async = orig_async

            self.assertEqual(set(snapshots), {"%1"})
            self.assertEqual(mapping, {"sessA": REPO_ROOT})
            self.assertIn(
                (
                    "list-panes", "-s", "-t", "=sessA", "-F",
                    mon._LIST_PANES_FORMAT,
                ),
                async_calls,
            )

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
