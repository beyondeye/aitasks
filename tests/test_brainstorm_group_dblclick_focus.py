"""Running-tab GroupRow double-click toggle + focus-preservation (t1018_3).

Covers two coupled behaviors added in t1018_3:

* Double-click a GroupRow -> expand/collapse the operation group (mirrors the
  Enter toggle) via ``GroupRow.ToggleRequested`` -> ``_toggle_group``;
  single-click only focuses.
* The focused GroupRow keeps focus across a Running-tab status refresh
  (``_refresh_status_tab`` rebuilds the whole row list every poll).

Synthetic ``Click`` events here cannot exercise real terminal->tmux mouse
delivery — that live check is owned by the t1018_4 manual-verification sibling.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agentcrew.agentcrew_utils as ac_mod  # noqa: E402
import brainstorm.brainstorm_session as bs_mod  # noqa: E402

from textual.widgets import TabbedContent  # noqa: E402

from brainstorm.brainstorm_app import (  # noqa: E402
    BrainstormApp,
    GroupRow,
)
from brainstorm.brainstorm_session import GROUPS_FILE  # noqa: E402


class _ClickEvent:
    """Minimal stand-in for textual.events.Click — on_click only reads .chain."""

    def __init__(self, chain: int) -> None:
        self.chain = chain


class GroupDblClickFocusTests(unittest.TestCase):

    TASK_NUM = "99303"

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_group_dblclick_")
        self._orig_dir = ac_mod.AGENTCREW_DIR
        ac_mod.AGENTCREW_DIR = str(Path(self.tmpdir) / "crews")
        bs_mod.AGENTCREW_DIR = ac_mod.AGENTCREW_DIR
        wt = bs_mod.crew_worktree(self.TASK_NUM)
        wt.mkdir(parents=True)
        bs_mod.init_session(
            self.TASK_NUM, "aitasks/fake.md", "tester@example.com",
            "Initial spec for the dblclick/focus test session.",
        )
        ac_mod.write_yaml(
            str(wt / GROUPS_FILE),
            {
                "groups": {
                    "explore_900": {
                        "operation": "explore",
                        "agents": ["explorer_900a"],
                        "status": "Waiting",
                        "created_at": "2026-01-01 00:00",
                    },
                    "synthesize_900": {
                        "operation": "synthesize",
                        "agents": ["synthesizer_900"],
                        "status": "Waiting",
                        "created_at": "2026-01-02 00:00",
                    },
                }
            },
        )
        ac_mod.write_yaml(
            str(wt / "explorer_900a_status.yaml"),
            {"agent_name": "explorer_900a", "status": "Waiting"},
        )
        ac_mod.write_yaml(
            str(wt / "synthesizer_900_status.yaml"),
            {"agent_name": "synthesizer_900", "status": "Waiting"},
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

    async def _running_groups(self, app, pilot):
        app.query_one(TabbedContent).active = "tab_running"
        await self._settle(pilot)
        app._refresh_status_tab()
        await self._settle(pilot)
        return {r.group_name: r for r in app.query(GroupRow)}

    def test_double_click_toggles_expand(self):
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot)
                rows = await self._running_groups(app, pilot)
                row = rows["explore_900"]
                self.assertNotIn("explore_900", app._expanded_groups)

                # Double-click -> ToggleRequested -> _toggle_group expands it.
                row.on_click(_ClickEvent(chain=2))
                await self._settle(pilot)
                self.assertIn("explore_900", app._expanded_groups)

                # Double-click again collapses (re-query: refresh remounted rows).
                row2 = {
                    r.group_name: r for r in app.query(GroupRow)
                }["explore_900"]
                row2.on_click(_ClickEvent(chain=2))
                await self._settle(pilot)
                self.assertNotIn("explore_900", app._expanded_groups)

        self._run(runner())

    def test_single_click_only_focuses(self):
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot)
                rows = await self._running_groups(app, pilot)
                row = rows["synthesize_900"]
                self.assertNotIn("synthesize_900", app._expanded_groups)

                row.on_click(_ClickEvent(chain=1))
                await self._settle(pilot)

                # Single-click focuses but does NOT toggle expansion.
                self.assertTrue(row.has_focus)
                self.assertNotIn("synthesize_900", app._expanded_groups)

        self._run(runner())

    def test_enter_still_toggles_via_shared_helper(self):
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot)
                rows = await self._running_groups(app, pilot)
                row = rows["explore_900"]
                row.focus()
                await self._settle(pilot)

                # Regression: extracting _toggle_group must keep Enter working.
                await pilot.press("enter")
                await self._settle(pilot)
                self.assertIn("explore_900", app._expanded_groups)

        self._run(runner())

    def test_focus_preserved_across_refresh(self):
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot)
                rows = await self._running_groups(app, pilot)
                row = rows["synthesize_900"]
                row.focus()
                await self._settle(pilot)
                self.assertTrue(row.has_focus)

                # A status refresh remounts every GroupRow; focus must survive.
                app._refresh_status_tab()
                await self._settle(pilot)

                refocused = {r.group_name: r for r in app.query(GroupRow)}
                self.assertTrue(refocused["synthesize_900"].has_focus)
                # The row is a fresh instance — the rebuild really happened.
                self.assertIsNot(refocused["synthesize_900"], row)

        self._run(runner())

    def test_vanished_focused_group_degrades_gracefully(self):
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot)
                rows = await self._running_groups(app, pilot)
                row = rows["explore_900"]
                row.focus()
                await self._settle(pilot)

                # Remove the focused group from disk, then refresh.
                wt = bs_mod.crew_worktree(self.TASK_NUM)
                with (wt / GROUPS_FILE).open() as f:
                    gdata = yaml.safe_load(f)
                gdata["groups"].pop("explore_900")
                ac_mod.write_yaml(str(wt / GROUPS_FILE), gdata)

                # Must not raise even though the focused group is gone.
                app._refresh_status_tab()
                await self._settle(pilot)

                names = {r.group_name for r in app.query(GroupRow)}
                self.assertNotIn("explore_900", names)
                self.assertIn("synthesize_900", names)

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
