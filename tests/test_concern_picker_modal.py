"""Tests for the shadow concern-picker modal (t1037_3).

Exercises ConcernPickerModal's pure-UI contract (no clipboard backend):
- N concerns render as N focusable rows, first focused;
- space toggles a row's selection (☐ ↔ ☑);
- ``a`` selects all / deselects all;
- OK / Enter dismiss with exactly the selected Concerns, in order;
- ``A`` (copy ALL) dismisses with every concern regardless of toggles;
- Esc / Cancel dismiss with ``None``.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m unittest tests.test_concern_picker_modal
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

from textual.app import App, ComposeResult  # noqa: E402
from textual.widgets import Label  # noqa: E402

from monitor.concern_parser import Concern  # noqa: E402
from monitor.monitor_shared import ConcernPickerModal, _ConcernRow  # noqa: E402


def _sample_concerns() -> list[Concern]:
    return [
        Concern("high", "Step 7 ownership guard", "Guard double-commits the lock."),
        Concern("medium", "parser module", "Multi-block accumulation is undefined."),
        Concern("low", "docs", "A stray [bracket] in the body must not break markup."),
    ]


class _Host(App):
    """Minimal host App that pushes the modal and captures its dismiss value."""

    _UNSET = object()

    def __init__(self, concerns: list[Concern], narrow: bool = False) -> None:
        super().__init__()
        self._concerns = concerns
        self._narrow = narrow
        self.result = self._UNSET

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        def _capture(value) -> None:
            self.result = value

        self.push_screen(
            ConcernPickerModal(self._concerns, narrow=self._narrow), _capture
        )


class ConcernPickerModalTests(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def test_rows_rendered_and_first_focused(self):
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                rows = list(app.screen.query(_ConcernRow))
                self.assertEqual(len(rows), 3)
                self.assertIsInstance(app.screen.focused, _ConcernRow)
                self.assertIs(app.screen.focused, rows[0])

        self._run(runner())

    def test_space_toggles_focused_row_glyph(self):
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                row = list(app.screen.query(_ConcernRow))[0]
                self.assertFalse(row.selected)
                self.assertIn("☐", row.render())

                await pilot.press("space")
                await pilot.pause()
                self.assertTrue(row.selected)
                self.assertIn("☑", row.render())

                await pilot.press("space")
                await pilot.pause()
                self.assertFalse(row.selected)
                self.assertIn("☐", row.render())

        self._run(runner())

    def test_select_all_toggles_every_row(self):
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                rows = list(app.screen.query(_ConcernRow))

                await pilot.press("a")
                await pilot.pause()
                self.assertTrue(all(r.selected for r in rows))

                await pilot.press("a")
                await pilot.pause()
                self.assertTrue(not any(r.selected for r in rows))

        self._run(runner())

    def test_ok_dismisses_with_selected_in_order(self):
        async def runner():
            concerns = _sample_concerns()
            app = _Host(concerns)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                # Select row 0, skip row 1, select row 2.
                await pilot.press("space")   # row 0 selected (focused on mount)
                await pilot.press("down")    # focus row 1
                await pilot.press("down")    # focus row 2
                await pilot.press("space")   # row 2 selected
                await pilot.press("enter")   # confirm
                await pilot.pause()
                self.assertEqual(app.result, [concerns[0], concerns[2]])

        self._run(runner())

    def test_copy_all_dismisses_with_every_concern(self):
        async def runner():
            concerns = _sample_concerns()
            app = _Host(concerns)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                # Toggle one row on first to prove "copy ALL" ignores prior state.
                await pilot.press("space")
                await pilot.press("A")       # copy ALL
                await pilot.pause()
                self.assertEqual(app.result, concerns)

        self._run(runner())

    def test_escape_dismisses_with_none(self):
        async def runner():
            app = _Host(_sample_concerns())
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("escape")
                await pilot.pause()
                self.assertIsNone(app.result)

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
