"""Regression tests for sync tmux calls on the monitor refresh path.

t1111_3 moves refresh-loop tmux round-trips onto async gateway calls so a slow
tmux response does not block Textual's event-loop thread.

t1622 extends the same rule to the one non-tmux subprocess left on that path:
the session bar's desync summary, which spawns a fresh Python interpreter. It is
now pre-fetched by `_refresh_data` through `get_desync_summary_async` and handed
to `_rebuild_session_bar`; the keypress-driven rebuild reads the cache instead.
Both tests below patch `desync_summary._fetch` / `_fetch_async` to RAISE, so a
call site that regresses to the blocking reader fails loudly rather than merely
running slower.

Positive controls (run by hand; each must FAIL this suite):

| mutation | must fail |
|---|---|
| `_refresh_data` back to `self._rebuild_session_bar(attached_session)` | `test_the_session_bar_desync_string_is_prefetched_asynchronously` |
| `_rebuild_session_bar`'s `desync is None` branch back to `get_desync_summary` | `test_the_keypress_rebuild_reads_the_cache_and_never_spawns` |
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

# Belt-and-braces for t1240: MonitorApp only renames its tmux window when
# constructed with rename_window=True (production launcher), but scrub the
# ambient tmux env too so on_mount takes the deterministic not-inside-tmux
# path regardless of where the suite runs.
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

import monitor.monitor_core as monitor_core  # noqa: E402
from agent_launch_utils import AitasksSession  # noqa: E402
import monitor.monitor_app as monitor_app  # noqa: E402
from monitor import desync_summary  # noqa: E402
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
        self._gen = 0

    @property
    def capture_generation(self) -> int:
        return self._gen

    def get_shadow_snapshot(self, followed_pane_id):
        # Mirrors TmuxMonitor.get_shadow_snapshot (t1133): no shadow panes in
        # these fixtures (shadow coverage lives in test_monitor_shadow_status.py).
        return None

    async def capture_all_classified_async(self):
        # Two-phase produce (t1111_4): reserve a generation and return opaque
        # classified entries; this fake's commit_snapshots returns the pre-built
        # snapshots, so the payload content is irrelevant.
        self._gen += 1
        classified = [(s.pane, s.content, None) for s in self.snapshots.values()]
        return self._gen, classified

    def commit_snapshots(self, gen, classified):
        if gen != self._gen:
            return None
        return dict(self.snapshots)

    async def capture_all_async(self) -> dict[str, PaneSnapshot] | None:
        gen, classified = await self.capture_all_classified_async()
        return self.commit_snapshots(gen, classified)

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
                        # `_LIST_PANES_FORMAT` order, 11 fields (t1686):
                        # …\t<shadow_target>\t<history_size>\t<monitor_kind>
                        "0\tagent-1\t0\t%1\t12345\tbash\t80\t24\t\t0\t",
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


class SessionBarDesyncTests(unittest.TestCase):
    """The desync summary must never be computed from a render path."""

    #: Distinctive enough that finding it in the bar cannot be a coincidence,
    #: and shaped like the real markup so nothing downstream mis-parses it.
    SENTINEL = " · [yellow]desync: sentinel-ref 7↓[/]"

    def setUp(self) -> None:
        # `_cache` is module state shared with every other suite in this process.
        self._saved_cache = dict(desync_summary._cache)
        self.addCleanup(self._restore_cache)

        def spawned(*a, **k):
            raise AssertionError(
                "the blocking desync reader was called from a Textual path"
            )

        self._real_fetch = desync_summary._fetch
        self._real_fetch_async = desync_summary._fetch_async
        desync_summary._fetch = spawned
        desync_summary._fetch_async = spawned
        self.addCleanup(self._restore_fetchers)

    def _restore_cache(self) -> None:
        desync_summary._cache.clear()
        desync_summary._cache.update(self._saved_cache)

    def _restore_fetchers(self) -> None:
        desync_summary._fetch = self._real_fetch
        desync_summary._fetch_async = self._real_fetch_async

    def test_the_session_bar_desync_string_is_prefetched_asynchronously(self):
        """`_refresh_data` fetches; `_rebuild_session_bar` only renders."""
        async def runner():
            awaited: list[bool] = []

            async def fake_async(project_root, *, compact=False):
                awaited.append(compact)
                return self.SENTINEL

            real, monitor_app._get_desync_summary_async = (
                monitor_app._get_desync_summary_async, fake_async
            )
            try:
                app = MonitorApp(session="demo", project_root=REPO_ROOT)
                async with app.run_test(size=(100, 30)):
                    app._monitor = _FakeRefreshMonitor()
                    await app._refresh_data()

                    bar = app.query_one("#session-bar")
                    self.assertIn(
                        "sentinel-ref 7↓", str(bar.content),
                        "the pre-fetched summary never reached the bar — the "
                        "builder is still computing its own",
                    )
                self.assertEqual(
                    awaited, [False],
                    "the refresh path did not await the async reader exactly "
                    "once for the full (non-compact) variant",
                )
            finally:
                monitor_app._get_desync_summary_async = real

        self._run(runner())

    def test_the_keypress_rebuild_reads_the_cache_and_never_spawns(self):
        """A synchronous handler has no business starting a subprocess.

        `action_toggle_auto_switch` rebuilds the bar from a keypress with no
        summary of its own, so it must serve whatever the last refresh stored.

        **The seeded entry is deliberately TTL-EXPIRED**, and that is what makes
        this test discriminating. A fresh entry is served by the blocking
        `get_desync_summary` too, so the regression would pass; an expired one
        splits them — the cached-only reader ignores the TTL by design and still
        returns it, while the blocking reader falls through to `_fetch`, which
        this suite has replaced with a raise.
        """
        async def runner():
            desync_summary._cache[str(Path.cwd())] = (
                time.monotonic() - desync_summary._TTL_SECONDS - 1,
                self.SENTINEL,
                "full",
            )
            app = MonitorApp(session="demo", project_root=REPO_ROOT)
            async with app.run_test(size=(100, 30)) as pilot:
                fake = _FakeRefreshMonitor()
                app._monitor = fake
                app._snapshots = fake.snapshots

                app.action_toggle_auto_switch()
                await pilot.pause()

                bar = app.query_one("#session-bar")
                self.assertIn(
                    "sentinel-ref 7↓", str(bar.content),
                    "the keypress rebuild dropped the cached summary — the bar "
                    "blanks a still-true desync warning on every keypress",
                )

        self._run(runner())

    def _run(self, coro):
        return asyncio.run(coro)


if __name__ == "__main__":
    unittest.main()
