"""Board startup focus, and why a blank column body is blank (t1491).

Two contracts, both regressions of the same incident:

1. **Startup focus belongs to the board, not the search box.** `KanbanApp` used
   to set no focus at all, so Textual's ``App.AUTO_FOCUS = "*"`` — applied in
   ``Screen._compose``, *before* ``on_mount`` — landed on the first focusable
   widget in the DOM, the ``#search_box`` Input. On a real terminal that made
   every non-``priority`` single-key binding, ``q`` (Quit) included, arrive as
   search text.

   **Scope limit, stated so it is not mistaken for full coverage:** the widget
   ``AUTO_FOCUS`` picks is driver-dependent. Under ``App.run_test`` it picks
   ``#board_container``, so the *symptom* (``q`` swallowed, every card filtered
   away) does not reproduce headless — ``test_q_quits_without_a_prior_escape``
   passed before the fix too and is a forward guard, not a reproduction. The
   symptom is pinned live in ``test_board_startup_focus_live.py``. What DOES
   fail here without the fix is the positive contract below: focus lands on a
   board focus anchor.

"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.board_fixture import (  # noqa: E402
    FixtureBoardTestBase,
    FixtureTask,
)

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".aitask-scripts", "lib"))

from board_groups import group_key  # noqa: E402

#: One column per shape the placeholder label must distinguish.
#:
#:   c0 — two ungrouped cards
#:   c1 — an EXPANDED group (two members sharing `boardgroup`)
#:   c2 — a COLLAPSED group (two members; collapsed via FIXTURE_SETTINGS)
#:   c3 — deliberately EMPTY (no tasks at all)
#:
#: `boardgroup` is what `board_groups.build_column_units` buckets on; a group
#: needs >= 2 members or `KanbanColumn.compose` renders it as a plain card and
#: mounts no `GroupHeader`.
SHAPES_TOPOLOGY = (
    FixtureTask(task_id="9000", col="c0", idx=10, slug="plainone"),
    FixtureTask(task_id="9001", col="c0", idx=20, slug="plaintwo"),
    FixtureTask(task_id="9002", col="c1", idx=10, slug="expandedone",
                extra={"boardgroup": "expgroup"}),
    FixtureTask(task_id="9003", col="c1", idx=20, slug="expandedtwo",
                extra={"boardgroup": "expgroup"}),
    FixtureTask(task_id="9004", col="c2", idx=10, slug="collapsedone",
                extra={"boardgroup": "colgroup"}),
    FixtureTask(task_id="9005", col="c2", idx=20, slug="collapsedtwo",
                extra={"boardgroup": "colgroup"}),
)

#: No task matches this, so every unit on the board is hidden and every
#: non-empty column falls back to its placeholder.
NO_MATCH = "zzz-no-such-task-anywhere"


class BoardStartupFocusTest(FixtureBoardTestBase, unittest.IsolatedAsyncioTestCase):
    FIXTURE_TASKS = SHAPES_TOPOLOGY
    FIXTURE_SETTINGS = {"collapsed_groups": [group_key("c2", "colgroup")]}

    async def _settle(self, pilot, times=3):
        for _ in range(times):
            await pilot.pause()

    def _placeholder(self, app, col_id):
        for placeholder in app.query(self.ab.EmptyColumnPlaceholder):
            if placeholder.column_id == col_id:
                return placeholder
        self.fail(f"no EmptyColumnPlaceholder mounted for column {col_id!r}")

    async def test_startup_focus_is_a_board_anchor(self):
        """Focus after boot is a board focus anchor, not the search Input.

        Fails without the fix: `AUTO_FOCUS` leaves focus on `#search_box` on a
        real terminal and on `#board_container` headless — neither is an anchor.
        """
        app = self.ab.KanbanApp()
        async with app.run_test(size=(160, 48)) as pilot:
            await self._settle(pilot)
            focused = app.screen.focused
            self.assertIsInstance(
                focused,
                (self.ab.TaskCard, self.ab.GroupHeader,
                 self.ab.EmptyColumnPlaceholder),
                f"startup focus is {type(focused).__name__}"
                f"#{getattr(focused, 'id', None)}, not a board focus anchor",
            )
            self.assertNotIsInstance(focused, self.ab.Input)

    async def test_the_search_input_never_holds_focus_during_boot(self):
        """`#search_box` must not own the keyboard at ANY point before settling.

        Asserting only the settled state would leave the real defect available
        in a smaller window: Textual's auto-focus fires in `Screen._compose`,
        several message-pump cycles before `on_mount`'s deferred claim, so a
        board that merely *corrects* focus afterwards still swallows keystrokes
        in between. `BoardScreen.AUTO_FOCUS = ""` is what closes it, and this
        samples every cycle rather than the end state.
        """
        app = self.ab.KanbanApp()
        async with app.run_test(size=(160, 48)) as pilot:
            seen = []
            for _ in range(8):
                focused = app.screen.focused
                seen.append(type(focused).__name__)
                self.assertNotIsInstance(
                    focused, self.ab.Input,
                    f"search box held focus mid-boot; focus sequence: {seen}")
                await pilot.pause()

    async def test_the_board_screen_resolves_to_no_auto_focus_selector(self):
        """The selector Textual will apply to the board screen must be falsy.

        Asserted through the resolution rule `Screen._update_auto_focus` uses —
        ``app.AUTO_FOCUS if screen.AUTO_FOCUS is None else screen.AUTO_FOCUS`` —
        rather than against the literal ``""``. Two ways to re-enable the defect
        are then both caught: setting `BoardScreen.AUTO_FOCUS = None` (which
        *inherits* `App.AUTO_FOCUS`, it does not disable anything), and changing
        `App.AUTO_FOCUS` under a screen that inherits it.

        This is a structural pin by necessity. The window it guards is the few
        message-pump cycles between `Screen._compose` and `on_mount`'s deferred
        claim, and it cannot be pinned behaviourally here: under `run_test` the
        auto-focus lands on `#board_container`, not the Input, so a behavioural
        assertion would pass with the guard removed. The live pin cannot see it
        either — it would have to deliver `q` within ~130ms of compose.
        """
        app = self.ab.KanbanApp()
        async with app.run_test(size=(160, 48)) as pilot:
            await self._settle(pilot)
            screen = app.screen
            self.assertIsInstance(screen, self.ab.BoardScreen)
            resolved = (app.AUTO_FOCUS if screen.AUTO_FOCUS is None
                        else screen.AUTO_FOCUS)
            self.assertFalse(
                resolved,
                f"board screen would auto-focus {resolved!r} — the first "
                "focusable widget in this DOM is #search_box")

    async def test_startup_focus_lands_in_the_leftmost_column(self):
        """The anchor is the LEFTMOST column's, matching `action_focus_board`."""
        app = self.ab.KanbanApp()
        async with app.run_test(size=(160, 48)) as pilot:
            await self._settle(pilot)
            self.assertEqual(app.screen.focused.column_id, "c0")

    async def test_q_quits_without_a_prior_escape(self):
        """Bare `q` exits the app.

        NOTE: this already passed before the fix under `run_test`, whose driver
        makes `AUTO_FOCUS` pick `#board_container` rather than the Input. It is
        a forward guard; the reproduction lives in the live tmux pin.
        """
        app = self.ab.KanbanApp()
        async with app.run_test(size=(160, 48)) as pilot:
            await self._settle(pilot)
            await pilot.press("q")
            await self._settle(pilot)
            self.assertFalse(app.is_running, "`q` did not quit the board")

    async def test_tab_still_reaches_the_search_box(self):
        """Claiming startup focus must not break the documented Tab affordance."""
        app = self.ab.KanbanApp()
        async with app.run_test(size=(160, 48)) as pilot:
            await self._settle(pilot)
            await pilot.press("tab")
            await self._settle(pilot)
            self.assertTrue(app.query_one("#search_box", self.ab.Input).has_focus)
            await pilot.press("escape")
            await self._settle(pilot)
            self.assertFalse(app.query_one("#search_box", self.ab.Input).has_focus)

if __name__ == "__main__":
    unittest.main()
