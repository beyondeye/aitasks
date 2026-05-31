"""Pilot tests for in-pane expand/collapse of DimensionRow (t873_3).

A long dimension value is clipped to a single line by the row's ``height: 1``
CSS. Pressing ``space`` toggles ``height: auto`` so the full value wraps and
becomes readable, and toggles back to clipped. Enter must still post
``Activated`` (the proposal jump) with no key collision.

Run via ``bash tests/run_all_python_tests.sh`` or directly with unittest.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from textual import on  # noqa: E402
from textual.app import App, ComposeResult  # noqa: E402

from brainstorm.brainstorm_app import DimensionRow  # noqa: E402


# Long enough to wrap across several rows in a narrow test viewport.
_LONG_VALUE = (
    "This dimension captures a deliberately long, multi-sentence description "
    "that easily exceeds a single terminal row. It exists so the collapsed "
    "row clips it to one line while the expanded row wraps it across several "
    "lines, which is exactly the behaviour under test here."
)


class _HostApp(App):
    """Mounts a single focusable DimensionRow and records Activated posts."""

    def __init__(self) -> None:
        super().__init__()
        self.activations: list[str] = []

    def compose(self) -> ComposeResult:
        yield DimensionRow(
            "perf", _LONG_VALUE, "requirements_perf", section_count=2,
            id="row",
        )

    def on_mount(self) -> None:
        self.set_focus(self.query_one(DimensionRow))

    @on(DimensionRow.Activated)
    def _record(self, event: DimensionRow.Activated) -> None:
        self.activations.append(event.dim_key)


class TestDimensionRowExpand(unittest.TestCase):

    def _run(self, coro):
        return asyncio.run(coro)

    def test_space_toggles_expansion(self):
        async def runner():
            app = _HostApp()
            async with app.run_test(size=(60, 24)) as pilot:
                await pilot.pause()
                await pilot.pause()
                row = app.query_one(DimensionRow)

                # Collapsed by default: clipped to one visible row.
                self.assertFalse(row.expanded)
                self.assertEqual(row.size.height, 1)

                # Expand: row grows to wrap the full value.
                await pilot.press("space")
                await pilot.pause()
                await pilot.pause()
                self.assertTrue(row.expanded)
                self.assertGreater(row.size.height, 1)

                # Collapse again: back to a single clipped row.
                await pilot.press("space")
                await pilot.pause()
                await pilot.pause()
                self.assertFalse(row.expanded)
                self.assertEqual(row.size.height, 1)

        self._run(runner())

    def test_enter_still_activates_without_toggling(self):
        async def runner():
            app = _HostApp()
            async with app.run_test(size=(60, 24)) as pilot:
                await pilot.pause()
                row = app.query_one(DimensionRow)

                app.activations.clear()
                await pilot.press("enter")
                await pilot.pause()

                # Enter posts the proposal-jump message and leaves the row
                # collapsed (no collision with the space toggle).
                self.assertEqual(app.activations, ["requirements_perf"])
                self.assertFalse(row.expanded)

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
