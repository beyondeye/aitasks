"""Operation/group-level restart on the Running tab (t1018_2).

Two layers:

* ``DeleteGroupModelTests`` — pure-unit coverage of the
  ``brainstorm_session.delete_group`` model helper (group entry removed +
  agent artifacts deleted, rich return value, missing-group no-op).
* ``GroupRecoveryActionTests`` — boots a real ``BrainstormApp`` over a temp
  session with failed/completed operation groups and drives the GroupRow
  ``n`` (re-run fresh) / ``i`` (retry-apply) actions, asserting the wizard
  seed, the apply call, gating, focus hints, and that the undeliverable
  ``ctrl+shift+x``/``ctrl+shift+y`` chords are gone.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agentcrew.agentcrew_utils as ac_mod  # noqa: E402
import brainstorm.brainstorm_session as bs_mod  # noqa: E402

from textual.widgets import TabbedContent  # noqa: E402

from brainstorm.brainstorm_app import (  # noqa: E402
    BrainstormApp,
    ActionsWizardScreen,
    CleanupAgentModal,
    GroupRow,
)
from brainstorm.brainstorm_session import (  # noqa: E402
    GROUPS_FILE,
    delete_group,
)


# --------------------------------------------------------------------------
# Pure-unit: the delete_group model helper
# --------------------------------------------------------------------------


class DeleteGroupModelTests(unittest.TestCase):
    def _seed(self, wt: Path) -> None:
        ac_mod.write_yaml(
            str(wt / GROUPS_FILE),
            {
                "groups": {
                    "explore_001": {
                        "operation": "explore",
                        "agents": ["explorer_001a", "explorer_001b"],
                        "status": "Waiting",
                    },
                    "synthesize_001": {
                        "operation": "synthesize",
                        "agents": ["synthesizer_001"],
                        "status": "Completed",
                    },
                }
            },
        )
        for agent in ("explorer_001a", "explorer_001b"):
            for suffix in ("_status.yaml", "_alive.yaml", "_output.md", "_log.txt"):
                (wt / f"{agent}{suffix}").write_text("x", encoding="utf-8")

    def test_removes_entry_and_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            self._seed(wt)
            with patch(
                "brainstorm.brainstorm_session.crew_worktree", return_value=wt
            ):
                removed = delete_group("42", "explore_001")

            # Rich return: names of agents whose artifacts were removed.
            self.assertEqual(sorted(removed), ["explorer_001a", "explorer_001b"])
            # Group entry gone; the sibling group is untouched.
            with (wt / GROUPS_FILE).open() as f:
                groups = (yaml.safe_load(f) or {}).get("groups", {})
            self.assertNotIn("explore_001", groups)
            self.assertIn("synthesize_001", groups)
            # All artifact files removed.
            for agent in ("explorer_001a", "explorer_001b"):
                for suffix in (
                    "_status.yaml", "_alive.yaml", "_output.md", "_log.txt"
                ):
                    self.assertFalse((wt / f"{agent}{suffix}").exists())

    def test_missing_group_is_noop(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            self._seed(wt)
            with patch(
                "brainstorm.brainstorm_session.crew_worktree", return_value=wt
            ):
                removed = delete_group("42", "does_not_exist")
            self.assertEqual(removed, [])
            # The real groups survive a no-op.
            with (wt / GROUPS_FILE).open() as f:
                groups = (yaml.safe_load(f) or {}).get("groups", {})
            self.assertIn("explore_001", groups)
            self.assertIn("synthesize_001", groups)


# --------------------------------------------------------------------------
# App-level: GroupRow n/i recovery actions
# --------------------------------------------------------------------------


class GroupRecoveryActionTests(unittest.TestCase):

    TASK_NUM = "99202"

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_group_recovery_")
        self._orig_dir = ac_mod.AGENTCREW_DIR
        ac_mod.AGENTCREW_DIR = str(Path(self.tmpdir) / "crews")
        bs_mod.AGENTCREW_DIR = ac_mod.AGENTCREW_DIR
        wt = bs_mod.crew_worktree(self.TASK_NUM)
        wt.mkdir(parents=True)
        bs_mod.init_session(
            self.TASK_NUM, "aitasks/fake.md", "tester@example.com",
            "Initial spec for the group-recovery test session.",
        )
        # A failed explore group, a completed synthesize group, and a completed
        # compare group (retry-apply unsupported for compare).
        ac_mod.write_yaml(
            str(wt / GROUPS_FILE),
            {
                "groups": {
                    "explore_900": {
                        "operation": "explore",
                        "agents": ["explorer_900a"],
                        "status": "Waiting",
                        "head_at_creation": "n000_init",
                    },
                    "synthesize_900": {
                        "operation": "synthesize",
                        "agents": ["synthesizer_900"],
                        "status": "Waiting",
                        "head_at_creation": "n000_init",
                    },
                    "compare_900": {
                        "operation": "compare",
                        "agents": ["comparator_900"],
                        "status": "Waiting",
                        "head_at_creation": "n000_init",
                    },
                }
            },
        )
        ac_mod.write_yaml(
            str(wt / "explorer_900a_status.yaml"),
            {"agent_name": "explorer_900a", "status": "Error"},
        )
        ac_mod.write_yaml(
            str(wt / "synthesizer_900_status.yaml"),
            {"agent_name": "synthesizer_900", "status": "Completed"},
        )
        ac_mod.write_yaml(
            str(wt / "comparator_900_status.yaml"),
            {"agent_name": "comparator_900", "status": "Completed"},
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

    def test_recovery_flags_and_focus_hints(self):
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot)
                rows = await self._running_groups(app, pilot)

                self.assertIn("explore_900", rows)
                failed = rows["explore_900"]
                self.assertTrue(failed.has_failed_agent)
                self.assertFalse(failed.has_completed_agent)

                synth = rows["synthesize_900"]
                self.assertFalse(synth.has_failed_agent)
                self.assertTrue(synth.has_completed_agent)

                # Focus hints render only on focus, per eligibility.
                failed.focus()
                await self._settle(pilot)
                self.assertIn("n: re-run fresh", failed.render())
                self.assertNotIn("i: retry-apply", failed.render())

                synth.focus()
                await self._settle(pilot)
                self.assertIn("i: retry-apply", synth.render())
                self.assertNotIn("n: re-run fresh", synth.render())

        self._run(runner())

    def test_n_reruns_via_preseeded_wizard(self):
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot)
                rows = await self._running_groups(app, pilot)
                failed = rows["explore_900"]
                failed.focus()
                await self._settle(pilot)

                # Capture the wizard push without mounting it / launching.
                pushed = []
                app.push_screen = MagicMock(
                    side_effect=lambda screen, *a, **k: pushed.append(screen)
                )
                exec_spy = MagicMock()
                app._execute_design_op = exec_spy

                await pilot.press("n")
                await self._settle(pilot)

                self.assertEqual(len(pushed), 1)
                wizard = pushed[0]
                self.assertIsInstance(wizard, ActionsWizardScreen)
                # Seeded with the group's operation + head node.
                self.assertEqual(wizard._seed_op, "explore")
                self.assertEqual(wizard._seed_node, "n000_init")
                # No live launch until the wizard returns a config.
                exec_spy.assert_not_called()

        self._run(runner())

    def test_n_warns_when_no_failed_agent(self):
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot)
                rows = await self._running_groups(app, pilot)
                synth = rows["synthesize_900"]  # completed, not failed
                synth.focus()
                await self._settle(pilot)

                app.push_screen = MagicMock()
                notify_spy = MagicMock()
                app.notify = notify_spy

                await pilot.press("n")
                await self._settle(pilot)

                app.push_screen.assert_not_called()
                self.assertTrue(notify_spy.called)

        self._run(runner())

    def test_i_reapplies_completed_synthesizer(self):
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot)
                rows = await self._running_groups(app, pilot)
                synth = rows["synthesize_900"]
                synth.focus()
                await self._settle(pilot)

                apply_spy = MagicMock()
                app._try_apply_synthesizer_if_needed = apply_spy

                await pilot.press("i")
                await self._settle(pilot)

                apply_spy.assert_called_once_with("synthesizer_900", force=True)

        self._run(runner())

    def test_i_unsupported_for_compare(self):
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot)
                rows = await self._running_groups(app, pilot)
                cmp_row = rows["compare_900"]
                cmp_row.focus()
                await self._settle(pilot)

                notify_spy = MagicMock()
                app.notify = notify_spy

                # Directly exercise the action (compare has no apply helper).
                app._retry_group_apply(cmp_row)
                await self._settle(pilot)

                self.assertTrue(notify_spy.called)

        self._run(runner())

    def test_cleanup_group_confirm_pushes_modal(self):
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot)
                pushed = []
                app.push_screen = MagicMock(
                    side_effect=lambda screen, *a, **k: pushed.append(screen)
                )
                app._confirm_cleanup_group("explore_900")
                self.assertEqual(len(pushed), 1)
                self.assertIsInstance(pushed[0], CleanupAgentModal)

        self._run(runner())


class NoChordBindingTests(unittest.TestCase):
    """Structural guard: the undeliverable retry-apply chords are gone."""

    def test_no_ctrl_shift_chords_in_bindings(self):
        keys = {
            b.key for b in BrainstormApp.BINDINGS
            if hasattr(b, "key")
        }
        self.assertNotIn("ctrl+shift+x", keys)
        self.assertNotIn("ctrl+shift+y", keys)

    def test_no_chord_anywhere_in_source(self):
        src = (
            REPO_ROOT
            / ".aitask-scripts" / "brainstorm" / "brainstorm_app.py"
        ).read_text(encoding="utf-8")
        # No Binding(...) declaration for the removed chords (comments are fine).
        self.assertNotIn('Binding("ctrl+shift+x"', src)
        self.assertNotIn('Binding("ctrl+shift+y"', src)


if __name__ == "__main__":
    unittest.main()
