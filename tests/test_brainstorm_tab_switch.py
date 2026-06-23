"""Tab-switch keybinding guard for the brainstorm TUI (t1060).

Boots a real ``BrainstormApp`` over a temp session and asserts that the
single-key tab switches (`b`/`g`/`d`/`s`/`r`) work **from any tab**, including
when focus is trapped on a focusable row inside a pane's content.

Regression context (t1060): the switches only fired while focus was on the tab
bar. Two independent defects caused this:

1. ``action_tab_*`` set ``TabbedContent.active`` but, with a focusable row in
   the old pane focused, Textual re-synced ``active`` back to that pane on the
   next refresh — silently reverting the switch. ``_select_tab`` now hands focus
   to the tab bar so the switch sticks.
2. ``BrainstormApp.on_key`` swallowed ``b`` on *every* tab (the task-brief
   shortcut), so the ``tab_browse`` binding never ran. The brief is now
   Browse-tab only; on other tabs ``b`` falls through to the switch.

The tests drive **real keypresses** via ``pilot.press`` (the actual entry
point) rather than setting ``.active`` directly, which would bypass both bugs.
The footer assertion reuses the ``active_bindings`` technique documented in
``test_brainstorm_binding_scope.py``.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agentcrew.agentcrew_utils as ac_mod  # noqa: E402
import brainstorm.brainstorm_session as bs_mod  # noqa: E402

from textual.widgets import TabbedContent, Tabs  # noqa: E402

from brainstorm.brainstorm_app import BrainstormApp  # noqa: E402


class TabSwitchTests(unittest.TestCase):

    TASK_NUM = "99401"

    # Browse-scoped footer actions that must NOT leak onto Session/Running.
    BROWSE_SCOPED_ACTIONS = {"open_node_detail", "node_action", "toggle_deferred"}

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_tab_switch_")
        self._orig_dir = ac_mod.AGENTCREW_DIR
        ac_mod.AGENTCREW_DIR = str(Path(self.tmpdir) / "crews")
        bs_mod.AGENTCREW_DIR = ac_mod.AGENTCREW_DIR
        wt = bs_mod.crew_worktree(self.TASK_NUM)
        wt.mkdir(parents=True)
        bs_mod.init_session(
            self.TASK_NUM, "aitasks/fake.md", "tester@example.com",
            "Initial spec for the tab-switch test session.",
        )

    def tearDown(self):
        ac_mod.AGENTCREW_DIR = self._orig_dir
        bs_mod.AGENTCREW_DIR = self._orig_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run(self, coro):
        return asyncio.run(coro)

    @staticmethod
    async def _settle(pilot, n=4):
        for _ in range(n):
            await pilot.pause()

    @staticmethod
    def _active(app):
        return app.query_one(TabbedContent).active

    @staticmethod
    def _focused_is_tab_bar(app):
        return isinstance(app.focused, Tabs)

    async def _enter_content_focus(self, app, pilot, tab_key, tab_id):
        """Switch to a tab via its key and land focus on a content row.

        Returns once focus is on a focusable widget *inside* the pane (not the
        tab bar) — the precondition that triggered the t1060 revert bug.
        """
        await pilot.press(tab_key)
        await self._settle(pilot)
        self.assertEqual(self._active(app), tab_id)
        if self._focused_is_tab_bar(app) or app.focused is None:
            # Arrow down off the tab bar into the pane content.
            await pilot.press("down")
            await self._settle(pilot)
        self.assertFalse(
            self._focused_is_tab_bar(app),
            f"expected focus inside {tab_id} content, got {type(app.focused).__name__}",
        )
        self.assertIsNotNone(app.focused)

    def test_switch_from_session_content(self):
        """From a focused OperationRow on Session, every tab key switches."""
        cases = [
            ("r", "tab_running"),
            ("b", "tab_browse"),   # proves the brief handler no longer swallows `b`
            ("g", "tab_browse"),
            ("d", "tab_browse"),
            ("s", "tab_session"),
        ]

        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot)
                for key, expected in cases:
                    # Re-trap focus inside Session content before each key.
                    await self._enter_content_focus(app, pilot, "s", "tab_session")
                    await pilot.press(key)
                    await self._settle(pilot)
                    self.assertEqual(
                        self._active(app), expected,
                        f"pressing {key!r} from Session content should activate "
                        f"{expected}, got {self._active(app)}",
                    )

        self._run(runner())

    def test_switch_from_running_content(self):
        """From a focused row on Running, `b` and `s` switch away."""
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot)
                # b: Running -> Browse (the brief-swallow regression).
                await self._enter_content_focus(app, pilot, "r", "tab_running")
                await pilot.press("b")
                await self._settle(pilot)
                self.assertEqual(self._active(app), "tab_browse")
                # s: Running -> Session.
                await self._enter_content_focus(app, pilot, "r", "tab_running")
                await pilot.press("s")
                await self._settle(pilot)
                self.assertEqual(self._active(app), "tab_session")

        self._run(runner())

    def test_browse_view_keys_keep_node_cursor_on_browse(self):
        """`d`/`g` from within Browse must not bounce focus to the tab bar.

        ``_select_tab`` only refocuses the tab bar when the tab actually
        changes, so toggling the Browse view keeps the in-pane focus.
        """
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot)
                # Move focus into Browse content.
                await pilot.press("down")
                await self._settle(pilot)
                if self._focused_is_tab_bar(app) or app.focused is None:
                    # No browse rows to focus in this fixture — nothing to assert.
                    return
                focused_before = app.focused
                # Press the view key that matches the CURRENT view, so the view
                # does not swap (graph<->list swaps the focused content widget,
                # which is expected and orthogonal to the tab-bar-bounce check).
                from brainstorm.brainstorm_app import DAGDisplay
                view_key = "g" if isinstance(focused_before, DAGDisplay) else "d"
                await pilot.press(view_key)
                await self._settle(pilot)
                self.assertEqual(self._active(app), "tab_browse")
                self.assertFalse(
                    self._focused_is_tab_bar(app),
                    f"`{view_key}` within Browse must not bounce focus to the tab bar",
                )
                self.assertIs(
                    app.focused, focused_before,
                    "a no-op Browse view key must preserve the in-pane focus",
                )

        self._run(runner())

    def test_footer_drops_browse_labels_off_browse(self):
        """Browse-scoped footer actions must not leak onto Session/Running."""
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot)
                for tab_key, tab_id in (("s", "tab_session"), ("r", "tab_running")):
                    await pilot.press(tab_key)
                    await self._settle(pilot)
                    self.assertEqual(self._active(app), tab_id)
                    actions = {
                        ab.binding.action
                        for ab in app.screen.active_bindings.values()
                    }
                    leaked = self.BROWSE_SCOPED_ACTIONS & actions
                    self.assertFalse(
                        leaked,
                        f"Browse-scoped actions leaked into the footer on "
                        f"{tab_id}: {leaked}",
                    )

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
