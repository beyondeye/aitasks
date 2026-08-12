#!/usr/bin/env python3
"""Board adoption of the multi-row footer (t1418).

`tests/test_multirow_footer.py` covers the widget itself. This module covers the
board's side of the change: that it mounts the widget at all, that the four keys
hidden only for lack of footer room are now footer-visible, that the keys the
`ViewSelector` already surfaces stayed hidden, and that `check_action` gating
still reaches the rendered footer.

Footer assertions are keyed by **action**, not by key, so a user's shortcut remap
cannot break them — the same rule `tests/test_syncer_rows.py` follows.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402
from multirow_footer import MultiRowFooter, OverflowHint  # noqa: E402
from textual.widgets._footer import FooterKey  # noqa: E402

#: Hidden by t1243_7 and friends *only* because the single-row footer was full.
UNHIDDEN = {
    "move_to_column",
    "toggle_column_collapsed",
    "move_task_top",
    "move_task_bottom",
}

#: Already rendered by the ViewSelector filter row — a footer entry would
#: duplicate, not reveal.
STAY_HIDDEN = {
    "view_all",
    "view_locked",
    "view_free",
    "view_inflight",
    "view_bytopic",
    "view_bytrail",
    "view_git",
    "view_type",
}


class BoardMultiRowFooterTests(bf.FixtureBoardTestBase, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.KanbanApp = cls.ab.KanbanApp
        cls.TaskCard = cls.ab.TaskCard

    def _run(self, coro):
        return asyncio.run(coro)

    @staticmethod
    def _rendered_actions(app) -> set[str]:
        """Actions with a FooterKey actually mounted in the footer."""
        return {key.action for key in app.query(FooterKey)}

    def _declared(self, action):
        return next(
            b
            for b in self.KanbanApp.BINDINGS
            if getattr(b, "action", None) == action
        )

    def test_fixture_facts(self):
        """Preconditions, so the assertions below cannot pass vacuously."""

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 48)) as pilot:
                await pilot.pause()
                self.assertTrue(
                    list(app.query(self.TaskCard)),
                    "fixture must render at least one task card",
                )
                self.assertTrue(
                    list(app.query(FooterKey)),
                    "fixture must render footer keys",
                )

        self._run(go())

    def test_the_board_mounts_the_multi_row_footer(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 48)) as pilot:
                await pilot.pause()
                footer = app.query_one(MultiRowFooter)
                self.assertFalse(footer.can_focus)

        self._run(go())

    def test_the_footer_wraps_at_200_columns(self):
        """The whole point: the board's key set no longer fits on one row."""

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 48)) as pilot:
                await pilot.pause()
                self.assertGreater(app.query_one(MultiRowFooter).size.height, 1)

        self._run(go())

    def test_no_footer_key_is_clipped(self):
        async def go():
            for width in (200, 160, 120):
                app = self.KanbanApp()
                async with app.run_test(size=(width, 48)) as pilot:
                    await pilot.pause()
                    for key in app.query(FooterKey):
                        self.assertLessEqual(
                            key.region.right,
                            width,
                            f"{key.key} clipped at {width} cols",
                        )

        self._run(go())

    def test_the_four_previously_hidden_keys_are_declared_shown(self):
        for action in UNHIDDEN:
            self.assertTrue(
                self._declared(action).show,
                f"{action} should be footer-visible after t1418",
            )

    def test_the_four_previously_hidden_keys_reach_the_rendered_footer(self):
        """Declared `show=True` is necessary but not sufficient — check render.

        `move_to_column` is gated by `check_action` on a focused card, so focus
        one first; the other three are ungated.
        """

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 48)) as pilot:
                await pilot.pause()
                card = next(c for c in app.query(self.TaskCard) if not c.is_child)
                card.focus()
                await pilot.pause()
                rendered = self._rendered_actions(app)
                for action in sorted(UNHIDDEN):
                    self.assertIn(action, rendered, f"{action} missing from footer")

        self._run(go())

    def test_view_filter_keys_stay_hidden(self):
        """The ViewSelector renders these; a footer copy would duplicate."""
        for action in STAY_HIDDEN:
            self.assertFalse(
                self._declared(action).show,
                f"{action} is surfaced by ViewSelector and must stay hidden",
            )

    def test_plain_navigation_keys_stay_hidden(self):
        for action in ("nav_up", "nav_down", "nav_left", "nav_right",
                       "focus_search", "focus_board"):
            self.assertFalse(self._declared(action).show, f"{action} should stay hidden")

    def test_check_action_gating_still_reaches_the_footer(self):
        """A shown binding must still disappear when its gate says False.

        Assert the hidden half FIRST: a gate that never hides anything would let
        the "shown" half pass on its own.
        """

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 48)) as pilot:
                await pilot.pause()
                # Blur explicitly to reach the no-focused-card case. It used to
                # be the boot state, but since t1491 the board claims startup
                # focus, so relying on boot would silently test the SHOWN half
                # twice and never exercise the gate's False branch.
                app.screen.set_focus(None)
                await pilot.pause()
                self.assertNotIn("move_to_column", self._rendered_actions(app))

                card = next(c for c in app.query(self.TaskCard) if not c.is_child)
                card.focus()
                await pilot.pause()
                self.assertIn("move_to_column", self._rendered_actions(app))

                app._set_base_filter("bytopic")
                await pilot.pause()
                self.assertNotIn("move_to_column", self._rendered_actions(app))

        self._run(go())

    def test_the_overflow_hint_names_the_editor_key_the_footer_shows(self):
        """The hint must agree with the rendered editor binding, whatever it is.

        Asserted as an *agreement* between two surfaces rather than against the
        literal `?`, so it stays true under a rebind. The widget derives the
        display from the composed binding (Textual already resolved it through
        `app.get_key_display`); a `resolve_key("board", "open_shortcuts_editor")`
        lookup could not, because that action is registered under the `shared`
        scope and is deliberately not shadowed into the app scope.
        """

        async def go():
            app = self.KanbanApp()
            # 70 rather than 80: wide enough to still render the editor key,
            # narrow enough that the hint survives a key or two leaving the
            # board's shown set, so this test fails for its own reason only.
            async with app.run_test(size=(70, 48)) as pilot:
                await pilot.pause()
                hints = list(app.query(OverflowHint))
                self.assertTrue(hints, "expected an overflow hint at 70 cols")
                editor = [
                    k
                    for k in app.query(FooterKey)
                    if k.action == "open_shortcuts_editor"
                ]
                self.assertTrue(editor, "editor binding must be footer-visible")
                self.assertIn(f"({editor[0].key_display})", str(hints[0].content))

        self._run(go())


if __name__ == "__main__":
    unittest.main(verbosity=2)
