"""Footer binding-scope guard for the brainstorm retry-apply actions (t1018_1).

Boots a real ``BrainstormApp`` over a temp session and asserts that the three
``retry_*_apply`` actions are gated to the (R)unning tab via ``check_action`` —
i.e. they are active there and hidden/inactive (``None``) on every other tab.

Before t1018_1 these actions fell through ``check_action``'s default
``return True``, so ``ctrl+r`` leaked a visible footer label on every tab and
all three stayed live everywhere. There was no test for that leak — this file
is the regression guard. The action methods themselves are untouched (t1018_2
re-homes the explorer/synthesizer retries onto the Running-tab GroupRow).
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

from brainstorm.brainstorm_app import BrainstormApp  # noqa: E402


RETRY_ACTIONS = (
    "retry_initializer_apply",
    "retry_explorer_apply",
    "retry_synthesizer_apply",
)


class RetryActionScopeTests(unittest.TestCase):

    TASK_NUM = "99201"

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_binding_scope_")
        self._orig_dir = ac_mod.AGENTCREW_DIR
        ac_mod.AGENTCREW_DIR = str(Path(self.tmpdir) / "crews")
        bs_mod.AGENTCREW_DIR = ac_mod.AGENTCREW_DIR
        wt = bs_mod.crew_worktree(self.TASK_NUM)
        wt.mkdir(parents=True)
        bs_mod.init_session(
            self.TASK_NUM, "aitasks/fake.md", "tester@example.com",
            "Initial spec for the binding-scope test session.",
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

    async def _activate_tab(self, app, pilot, tab_id):
        # Drive check_action's input (the active tab id) directly rather than
        # through the tab-switch keybinding, whose routing depends on the
        # currently-focused widget. check_action reads ``TabbedContent.active``,
        # so this exercises the real gating logic in isolation.
        app.query_one(TabbedContent).active = tab_id
        await self._settle(pilot)
        self.assertEqual(app.query_one(TabbedContent).active, tab_id)

    def test_retry_actions_active_only_on_running_tab(self):
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot)

                # (R)unning tab — the owning surface: active + footer-visible.
                await self._activate_tab(app, pilot, "tab_running")
                for action in RETRY_ACTIONS:
                    self.assertTrue(
                        app.check_action(action, None),
                        f"{action} should be active on the Running tab",
                    )

                # (B)rowse tab — hidden + inactive (check_action returns None).
                await self._activate_tab(app, pilot, "tab_browse")
                for action in RETRY_ACTIONS:
                    self.assertIsNone(
                        app.check_action(action, None),
                        f"{action} should be hidden/inactive on the Browse tab",
                    )

                # (S)ession tab — likewise hidden + inactive.
                await self._activate_tab(app, pilot, "tab_session")
                for action in RETRY_ACTIONS:
                    self.assertIsNone(
                        app.check_action(action, None),
                        f"{action} should be hidden/inactive on the Session tab",
                    )

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
