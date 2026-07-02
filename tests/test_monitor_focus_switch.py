"""Regression tests for monitor focus-switch render and selected-card costs.

t1111_2 removes a duplicate preview render on PaneCard focus and replaces the
selected-card full scan with targeted updates except after actual remounts.
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

from monitor.monitor_app import MonitorApp, PaneCard  # noqa: E402
from monitor.tmux_control import TmuxControlState  # noqa: E402
from monitor.tmux_monitor import (  # noqa: E402
    PaneCategory,
    PaneSnapshot,
    TmuxPaneInfo,
)


class _FakeMonitor:
    multi_session = False

    def __init__(self, snapshots: dict[str, PaneSnapshot]) -> None:
        self.snapshots = snapshots

    async def capture_all_async(self) -> dict[str, PaneSnapshot]:
        return dict(self.snapshots)

    def get_session_to_project_mapping(self) -> dict[str, Path]:
        return {}

    def control_state(self) -> TmuxControlState:
        return TmuxControlState.CONNECTED

    def get_compare_mode(self, pane_id: str) -> str:
        return "stripped"

    def is_compare_mode_overridden(self, pane_id: str) -> bool:
        return False


def _snapshot(
    pane_id: str,
    window_name: str,
    *,
    content: str | None = None,
    idle: bool = False,
) -> PaneSnapshot:
    idx = int(pane_id.lstrip("%"))
    pane = TmuxPaneInfo(
        window_index="0",
        window_name=window_name,
        pane_index=str(idx),
        pane_id=pane_id,
        pane_pid=10_000 + idx,
        current_command="bash",
        width=80,
        height=24,
        category=PaneCategory.AGENT,
        session_name="demo",
    )
    return PaneSnapshot(
        pane=pane,
        content=content if content is not None else f"{window_name}\nready",
        timestamp=0.0,
        idle_seconds=10.0 if idle else 0.0,
        is_idle=idle,
    )


def _snapshots(*pane_ids: str) -> dict[str, PaneSnapshot]:
    return {
        pane_id: _snapshot(pane_id, f"agent-{pane_id.lstrip('%')}")
        for pane_id in pane_ids
    }


def _selected_cards(app: MonitorApp) -> set[str]:
    return {
        card.pane_id
        for card in app.query("#pane-list PaneCard")
        if card.has_class("selected")
    }


class MonitorFocusSwitchTests(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    async def _mounted_app(
        self, pilot, *, pane_ids: tuple[str, ...] = ("%1", "%2")
    ) -> MonitorApp:
        app = pilot.app
        snapshots = _snapshots(*pane_ids)
        app._monitor = _FakeMonitor(snapshots)
        app._snapshots = snapshots
        app._focused_pane_id = pane_ids[0]
        app._consume_focus_request = lambda: None
        rebuilt = app._rebuild_pane_list()
        self.assertTrue(rebuilt)
        await pilot.pause()
        app._update_selected_card_indicator(full=True)
        self.assertEqual(_selected_cards(app), {pane_ids[0]})
        return app

    def test_focus_switch_renders_preview_once_and_targets_two_cards(self):
        async def runner():
            app = MonitorApp(session="demo", project_root=REPO_ROOT)
            async with app.run_test(size=(100, 30)) as pilot:
                app = await self._mounted_app(pilot)

                preview_calls = 0
                orig_preview = app._update_content_preview

                def count_preview():
                    nonlocal preview_calls
                    preview_calls += 1
                    return orig_preview()

                selected_calls: list[tuple[str, bool]] = []
                orig_set_class = PaneCard.set_class

                def count_set_class(card, add: bool, class_name: str):
                    if class_name == "selected":
                        selected_calls.append((card.pane_id, add))
                    return orig_set_class(card, add, class_name)

                app._update_content_preview = count_preview
                PaneCard.set_class = count_set_class
                try:
                    app._pane_cards["%2"].focus()
                    await pilot.pause()
                finally:
                    PaneCard.set_class = orig_set_class

                self.assertEqual(preview_calls, 1)
                self.assertEqual(selected_calls, [("%1", False), ("%2", True)])
                self.assertEqual(_selected_cards(app), {"%2"})

        self._run(runner())

    def test_refresh_fast_path_does_not_full_scan_selected_cards(self):
        async def runner():
            app = MonitorApp(session="demo", project_root=REPO_ROOT)
            async with app.run_test(size=(100, 30)) as pilot:
                app = await self._mounted_app(pilot)
                app._monitor.snapshots = _snapshots("%1", "%2")

                rebuild_results: list[bool] = []
                orig_rebuild = app._rebuild_pane_list

                def count_rebuild():
                    rebuilt = orig_rebuild()
                    rebuild_results.append(rebuilt)
                    return rebuilt

                full_flags: list[bool] = []
                orig_selected = app._update_selected_card_indicator

                def count_selected(full: bool = False):
                    full_flags.append(full)
                    return orig_selected(full=full)

                app._rebuild_pane_list = count_rebuild
                app._update_selected_card_indicator = count_selected

                await app._refresh_data()
                await pilot.pause()

                self.assertEqual(rebuild_results, [False])
                self.assertNotIn(True, full_flags)
                self.assertEqual(_selected_cards(app), {"%1"})

        self._run(runner())

    def test_structural_refresh_reconciles_selected_state_and_mapping(self):
        async def runner():
            app = MonitorApp(session="demo", project_root=REPO_ROOT)
            async with app.run_test(size=(100, 30)) as pilot:
                app = await self._mounted_app(pilot)
                app._pane_cards["%2"].set_class(True, "selected")
                app._selected_card_pane_id = "%2"
                app._monitor.snapshots = _snapshots("%1", "%3")

                rebuild_results: list[bool] = []
                orig_rebuild = app._rebuild_pane_list

                def count_rebuild():
                    rebuilt = orig_rebuild()
                    rebuild_results.append(rebuilt)
                    return rebuilt

                full_flags: list[bool] = []
                orig_selected = app._update_selected_card_indicator

                def count_selected(full: bool = False):
                    full_flags.append(full)
                    return orig_selected(full=full)

                app._rebuild_pane_list = count_rebuild
                app._update_selected_card_indicator = count_selected

                await app._refresh_data()
                await pilot.pause()

                self.assertEqual(rebuild_results, [True])
                self.assertIn(True, full_flags)
                self.assertEqual(app._selected_card_pane_id, "%1")
                self.assertEqual(_selected_cards(app), {"%1"})

                mounted_by_id = {
                    card.pane_id: card for card in app.query("#pane-list PaneCard")
                }
                self.assertEqual(set(app._pane_cards), {"%1", "%3"})
                for pane_id, card in app._pane_cards.items():
                    self.assertIs(card, mounted_by_id[pane_id])

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
