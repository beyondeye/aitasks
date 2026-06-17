"""Full-app integration tests for the brainstorm node-action picker (t819).

Boots a real `BrainstormApp` over a temp session and drives it with the
Textual pilot: focus a node on the Graph / Dashboard tab, press `A`, pick an
operation, and assert the contextual Actions wizard (ActionsWizardScreen) opens
seeded (t983_11: the wizard is a pushed modal now, not an in-tab surface).

This is the regression guard for the t819 review bug: picking an operation
appeared to do nothing (non-deterministically "fixed" after several retries).
Unit tests over the modal and the callback could not catch it — only a booted
app exercises the screen-stack / focus interaction.
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

from textual.widgets import TabbedContent  # noqa: E402

from brainstorm.brainstorm_app import (  # noqa: E402
    ActionsWizardScreen,
    BrainstormApp,
    NodeActionSelectModal,
    NodeRow,
)
from brainstorm.brainstorm_dag_display import DAGDisplay  # noqa: E402


class NodeActionIntegrationTests(unittest.TestCase):

    TASK_NUM = "99001"

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_node_action_int_")
        self._orig_dir = ac_mod.AGENTCREW_DIR
        ac_mod.AGENTCREW_DIR = str(Path(self.tmpdir) / "crews")
        bs_mod.AGENTCREW_DIR = ac_mod.AGENTCREW_DIR
        wt = bs_mod.crew_worktree(self.TASK_NUM)
        wt.mkdir(parents=True)
        bs_mod.init_session(
            self.TASK_NUM, "aitasks/fake.md", "tester@example.com",
            "Initial spec for the integration test session.",
        )

    def tearDown(self):
        ac_mod.AGENTCREW_DIR = self._orig_dir
        bs_mod.AGENTCREW_DIR = self._orig_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run(self, coro):
        return asyncio.run(coro)

    @staticmethod
    async def _settle(pilot, n=8):
        for _ in range(n):
            await pilot.pause()

    async def _focus_graph_node(self, app, pilot):
        await pilot.press("g")
        await pilot.pause()
        app.set_focus(app.query_one(DAGDisplay))
        await self._settle(pilot, 3)

    async def _focus_dashboard_node(self, app, pilot):
        await pilot.press("d")
        await pilot.pause()
        rows = list(app.query(NodeRow))
        self.assertTrue(rows, "expected at least one NodeRow on the Dashboard")
        app.set_focus(rows[0])
        await self._settle(pilot, 3)

    def test_graph_tab_pick_enters_actions_wizard(self):
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot, 3)
                tabbed = app.query_one(TabbedContent)
                await self._focus_graph_node(app, pilot)

                await pilot.press("A")
                await self._settle(pilot, 3)
                self.assertIsInstance(app.screen, NodeActionSelectModal)

                await pilot.press("enter")  # first enabled op == explore
                await self._settle(pilot, 10)

                # t983_11: picking an op pushes the contextual wizard modal,
                # seeded from the focused node (no Actions tab anymore).
                self.assertIsInstance(app.screen, ActionsWizardScreen)
                self.assertEqual(app.screen._wizard_op, "explore")
                self.assertEqual(
                    app.screen._wizard_config.get("_selected_node"), "n000_init"
                )

        self._run(runner())

    def test_dashboard_tab_pick_enters_actions_wizard(self):
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot, 3)
                tabbed = app.query_one(TabbedContent)
                await self._focus_dashboard_node(app, pilot)

                await pilot.press("A")
                await self._settle(pilot, 3)
                self.assertIsInstance(app.screen, NodeActionSelectModal)

                await pilot.press("enter")
                await self._settle(pilot, 10)

                self.assertIsInstance(app.screen, ActionsWizardScreen)
                self.assertEqual(app.screen._wizard_op, "explore")

        self._run(runner())

    def test_graph_tab_works_on_every_attempt(self):
        # The bug manifested as "works only after several retries". Verify
        # the very first attempt and each subsequent one succeeds.
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot, 3)
                tabbed = app.query_one(TabbedContent)
                for attempt in range(1, 4):
                    await self._focus_graph_node(app, pilot)
                    await pilot.press("A")
                    await self._settle(pilot, 3)
                    self.assertIsInstance(
                        app.screen, NodeActionSelectModal,
                        f"attempt {attempt}: modal did not open",
                    )
                    await pilot.press("enter")
                    await self._settle(pilot, 10)
                    self.assertIsInstance(
                        app.screen, ActionsWizardScreen,
                        f"attempt {attempt}: wizard modal not opened",
                    )
                    # Close the wizard before the next attempt (the modal
                    # consumes keys, so `g`/focus wouldn't reach Browse).
                    app.screen.dismiss(None)
                    await self._settle(pilot, 5)

        self._run(runner())

    def test_cancel_keeps_origin_tab(self):
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot, 3)
                tabbed = app.query_one(TabbedContent)
                await self._focus_graph_node(app, pilot)

                await pilot.press("A")
                await self._settle(pilot, 3)
                self.assertIsInstance(app.screen, NodeActionSelectModal)

                await pilot.press("escape")  # cancel the picker
                await self._settle(pilot, 8)

                self.assertNotIsInstance(app.screen, NodeActionSelectModal)
                self.assertEqual(tabbed.active, "tab_browse")

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
