"""Live tests for the stats TUI keyboard focus fixes (t2155).

Two defects reported from the aitasks_go port:

  * `PaneSelectorModal.on_key` treated EVERY Enter as "save", so Enter on the
    focused Cancel button saved the selection instead of cancelling.
  * `StatsApp`'s Tab panel cycle never ran. Its guard (`self.screen is not
    self`) was always true, and — the larger half — the App's non-priority
    `tab` binding never fired at all: the Screen's own `tab -> app.focus_next`
    sits earlier in the binding chain and consumed the key first.

The cycle tests use a REAL `DataTable` (the `backlog.level` pane): the default
focus chain used to be the only keyboard route into a content table, so the
fixed cycle must keep the content pane as one of its slots.

`App.run_test` is headless and in-process (no tmux, no boot budget), so this
module stays in the parallel lane, like `test_stats_backlog_panes_live.py`.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_DIR / ".aitask-scripts"
for _p in (str(SCRIPTS), str(SCRIPTS / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from textual.app import App  # noqa: E402
from textual.widgets import DataTable, ListView  # noqa: E402

import keybinding_registry  # noqa: E402
from agent_launch_utils import AitasksSession  # noqa: E402
from stats import stats_app as sa  # noqa: E402
from stats.modals.pane_selector import PaneSelectorModal  # noqa: E402

from test_stats_backlog_panes_live import _fixture  # noqa: E402

TERMINAL = (120, 40)
_UNSET = object()


def _sess(name):
    return AitasksSession(
        session=name,
        project_root=Path("/tmp/" + name),
        project_name=name,
        is_live=True,
        is_stale=False,
        project_group="g",
    )


class _FixtureStatsApp(sa.StatsApp):
    """StatsApp on the in-memory fixture instead of a real archive scan, with a
    spy on the panel cycle so a test can tell the cycle ran from the default
    focus chain happening to land on the same widget."""

    def __init__(self) -> None:
        super().__init__()
        self.cycle_calls: list[bool] = []

    def _load_data(self) -> None:
        self.stats_data = _fixture()

    def _cycle_focus(self, forward: bool) -> None:
        self.cycle_calls.append(forward)
        super()._cycle_focus(forward)


def _make_app(sessions=()):
    # Bindings resolve at construction; with no user overrides the tests'
    # literal tab/shift+tab are the panel-cycle keys whatever userconfig holds.
    with patch.object(sa, "discover_stats_sessions", return_value=list(sessions)), \
            patch.object(keybinding_registry, "load_user_overrides", return_value={}):
        return _FixtureStatsApp()


def _name(widget) -> str:
    if isinstance(widget, DataTable):
        return "DataTable"
    return getattr(widget, "id", None) or type(widget).__name__


class _PaneSelectorHost(App):
    def __init__(self) -> None:
        super().__init__()
        self.result = _UNSET

    def on_mount(self) -> None:
        self.push_screen(PaneSelectorModal("x", []), self._done)

    def _done(self, value) -> None:
        self.result = value


class TestPaneSelectorEnter(unittest.IsolatedAsyncioTestCase):
    async def _run(self, *keys):
        app = _PaneSelectorHost()
        async with app.run_test(size=TERMINAL) as pilot:
            await pilot.pause()
            for key in keys:
                await pilot.press(key)
                await pilot.pause()
        return app.result

    async def test_enter_on_focused_cancel_cancels(self):
        # space toggles the first pane; tab -> Save, tab -> Cancel.
        self.assertIsNone(await self._run("space", "tab", "tab", "enter"))

    async def test_enter_on_focused_save_saves(self):
        result = await self._run("space", "tab", "enter")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    async def test_enter_in_list_still_saves(self):
        result = await self._run("space", "enter")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)


class TestPanelCycle(unittest.IsolatedAsyncioTestCase):
    async def _walk(self, app, pilot, keys):
        seen = []
        for key in keys:
            await pilot.press(key)
            await pilot.pause()
            seen.append(_name(app.focused))
        return seen

    async def _boot(self, app, pilot, pane):
        app._show_pane(pane)
        await pilot.pause()
        app.query_one("#sidebar", ListView).focus()
        await pilot.pause()

    async def test_tab_routes_through_the_panel_cycle(self):
        app = _make_app()
        async with app.run_test(size=TERMINAL) as pilot:
            await self._boot(app, pilot, "backlog.level")
            await self._walk(app, pilot, ["tab", "tab", "shift+tab"])
        self.assertEqual(app.cycle_calls, [True, True, False])

    async def test_cycle_enters_and_leaves_a_real_content_table(self):
        app = _make_app()
        async with app.run_test(size=TERMINAL) as pilot:
            await self._boot(app, pilot, "backlog.level")
            self.assertEqual(
                await self._walk(app, pilot, ["tab", "tab"]),
                ["layout_list", "DataTable"],
            )
            table = app.focused
            before = table.cursor_row
            await pilot.press("down")
            await pilot.pause()
            self.assertEqual(table.cursor_row, before + 1, "keys must reach the table")
            self.assertEqual(await self._walk(app, pilot, ["shift+tab"]), ["layout_list"])
            self.assertEqual(
                await self._walk(app, pilot, ["tab", "tab"]), ["DataTable", "sidebar"]
            )
            # Wrap-around backwards: sidebar is first, the content slot is last.
            self.assertEqual(await self._walk(app, pilot, ["shift+tab"]), ["DataTable"])

    async def test_pane_without_focusable_content_is_skipped(self):
        app = _make_app()
        async with app.run_test(size=TERMINAL) as pilot:
            await self._boot(app, pilot, "overview.summary")
            self.assertEqual(
                await self._walk(app, pilot, ["tab", "tab"]), ["layout_list", "sidebar"]
            )

    async def test_multi_session_order(self):
        app = _make_app([_sess("sA"), _sess("sB")])
        self.assertTrue(app.multi_session)
        async with app.run_test(size=TERMINAL) as pilot:
            await self._boot(app, pilot, "backlog.level")
            self.assertEqual(
                await self._walk(app, pilot, ["tab", "tab", "tab", "tab"]),
                ["layout_list", "DataTable", "session_list", "sidebar"],
            )

    async def test_tab_in_a_modal_stays_in_the_modal(self):
        app = _make_app()
        async with app.run_test(size=TERMINAL) as pilot:
            await self._boot(app, pilot, "backlog.level")
            app.push_screen(PaneSelectorModal("x", []))
            await pilot.pause()
            self.assertEqual(app.screen.focused.id, "pane_selector_list")
            await pilot.press("tab")
            await pilot.pause()
            self.assertEqual(app.screen.focused.id, "btn_save")
        self.assertEqual(app.cycle_calls, [])


if __name__ == "__main__":
    unittest.main()
