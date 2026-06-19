"""Tests for the Settings TUI Project Groups tab (t1025_3).

The editor is a thin front-end over the bash CLI `ait projects group …` (the
single registry-writer authority — t1025_1 D5): it never writes projects.yaml
directly and introduces no Python writer. These tests stub the one subprocess
seam (`_run_projects_group`) so they assert, deterministically:

  - the tab mounts and lists registered repos under their group (grouped +
    the synthetic "(ungrouped)" bucket), parsed from `group list` output;
  - `g` switches to the Project Groups tab;
  - an INVALID slug is rejected in the modal BEFORE any subprocess fires
    (no `set` reaches the CLI — proving no-write-on-invalid), and a VALID
    assign issues exactly `group set <repo> <slug>`;
  - clear / rename / sync issue exactly their CLI verbs.

Run: python3 tests/test_settings_project_groups_tab.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "settings"))

from textual.widgets import DataTable, Input  # noqa: E402

from agent_model_picker import FuzzySelect  # noqa: E402
import keybinding_registry  # noqa: E402
from shortcuts_mixin import refresh_label_case  # noqa: E402
from settings_app import (  # noqa: E402
    AssignGroupScreen,
    RenameGroupScreen,
    SettingsApp,
)

# A representative `ait projects group list` rendering: one real group with a
# member, plus the synthetic ungrouped bucket (with a STALE member).
_LIST_OUTPUT = "team_a:\n  alpha\n(ungrouped):\n  beta\n  delta [STALE]\n"


def _make_stub(calls: list, list_output: str = _LIST_OUTPUT):
    """Return a drop-in for SettingsApp._run_projects_group that records every
    call and returns canned output (rc 0). Assigned as an INSTANCE attribute, so
    it is invoked as a plain function (no implicit self)."""
    def stub(*args):
        calls.append(tuple(args))
        if args and args[0] == "list":
            return (0, list_output, "")
        return (0, "", "")
    return stub


class _Fixture(unittest.TestCase):
    def setUp(self) -> None:
        keybinding_registry._reset_for_tests()
        refresh_label_case()
        self._prev_cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "aitasks" / "metadata").mkdir(parents=True, exist_ok=True)
        (self.root / "aitasks" / "metadata" / "userconfig.yaml").write_text(
            "email: tester@example.com\n", encoding="utf-8",
        )
        os.chdir(self.root)

    def tearDown(self) -> None:
        os.chdir(self._prev_cwd)
        self._tmp.cleanup()
        keybinding_registry._reset_for_tests()
        refresh_label_case()

    def _run(self, coro):
        return asyncio.run(coro)

    def _rows_by_repo(self, table: DataTable) -> dict:
        return {
            str(table.get_row_at(i)[0]): str(table.get_row_at(i)[1])
            for i in range(table.row_count)
        }


class PopulateTests(_Fixture):
    def test_tab_lists_repos_under_their_group(self):
        async def runner():
            calls: list = []
            app = SettingsApp()
            app._run_projects_group = _make_stub(calls)
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                table = app.query_one("#project_groups_table", DataTable)
                rows = self._rows_by_repo(table)
                self.assertEqual(rows.get("alpha"), "team_a")
                self.assertEqual(rows.get("beta"), "(ungrouped)")
                self.assertEqual(rows.get("delta"), "(ungrouped)")
                # The STALE suffix is parsed into the Status column.
                statuses = {
                    str(table.get_row_at(i)[0]): str(table.get_row_at(i)[2])
                    for i in range(table.row_count)
                }
                self.assertEqual(statuses.get("delta"), "STALE")
                self.assertIn(("list",), calls)
        self._run(runner())

    def test_g_switches_to_project_groups_tab(self):
        async def runner():
            app = SettingsApp()
            app._run_projects_group = _make_stub([])
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                await pilot.press("g")
                await pilot.pause()
                self.assertEqual(
                    app.query_one("TabbedContent").active, "tab_project_groups")
        self._run(runner())


class MutationDispatchTests(_Fixture):
    def test_invalid_new_slug_rejected_before_any_subprocess(self):
        async def runner():
            calls: list = []
            app = SettingsApp()
            app._run_projects_group = _make_stub(calls)
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                await pilot.press("g")
                await pilot.pause()
                # Cursor row 0 == alpha (team_a). Open the assign modal.
                app._pg_assign()
                await pilot.pause()
                self.assertIsInstance(app.screen, AssignGroupScreen)
                finp = app.screen.query_one("#assign_group_select_input", Input)
                fuzzy = app.screen.query_one("#assign_group_select", FuzzySelect)

                # INVALID new slug: no existing match → create path → validated
                # → the modal refuses to dismiss; no `set` fires.
                finp.value = "Bad Slug"
                await pilot.pause()
                fuzzy.accept()
                await pilot.pause()
                self.assertIsInstance(app.screen, AssignGroupScreen)
                self.assertFalse(
                    any(c and c[0] == "set" for c in calls),
                    "an invalid slug must not reach the CLI",
                )

                # VALID new slug: dismisses, callback issues exactly `set`.
                finp.value = "team_b"
                await pilot.pause()
                fuzzy.accept()
                await pilot.pause()
                self.assertNotIsInstance(app.screen, AssignGroupScreen)
                self.assertIn(("set", "alpha", "team_b"), calls)
        self._run(runner())

    def test_typing_new_group_and_pressing_enter_creates_it(self):
        """End-to-end keyboard path (the reported gap): focus opens on the
        combobox filter, type a new slug, press Enter → the group is created and
        assigned without touching the mouse."""
        async def runner():
            calls: list = []
            app = SettingsApp()
            app._run_projects_group = _make_stub(calls)
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                await pilot.press("g")
                await pilot.pause()
                app._pg_assign()  # cursor 0 == alpha
                await pilot.pause()
                # Focus lands on the combobox filter input; type + Enter.
                for ch in "newgrp":
                    await pilot.press(ch)
                await pilot.press("enter")
                await pilot.pause()
                self.assertIn(("set", "alpha", "newgrp"), calls)
        self._run(runner())

    def test_assign_lists_existing_groups_and_picking_one_sets_it(self):
        async def runner():
            from agent_model_picker import FuzzySelect
            calls: list = []
            app = SettingsApp()
            app._run_projects_group = _make_stub(calls)
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                await pilot.press("g")
                await pilot.pause()
                table = app.query_one("#project_groups_table", DataTable)
                table.move_cursor(row=1)  # beta (ungrouped)
                app._pg_assign()
                await pilot.pause()
                self.assertIsInstance(app.screen, AssignGroupScreen)
                # The existing real group is offered for selection.
                picker = app.screen.query_one("#assign_group_select", FuzzySelect)
                self.assertIn("team_a", [o["value"] for o in picker.all_options])
                # Picking it assigns beta to team_a — no typing/validation needed.
                app.screen.on_fuzzy_select_selected(FuzzySelect.Selected("team_a"))
                await pilot.pause()
                self.assertIn(("set", "beta", "team_a"), calls)
        self._run(runner())

    def test_enter_on_row_opens_assign_dialog(self):
        async def runner():
            app = SettingsApp()
            app._run_projects_group = _make_stub([])
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                await pilot.press("g")
                await pilot.pause()
                table = app.query_one("#project_groups_table", DataTable)
                table.focus()
                await pilot.pause()
                await pilot.press("enter")  # primary action on the selected row
                await pilot.pause()
                self.assertIsInstance(app.screen, AssignGroupScreen)
        self._run(runner())

    def test_clear_issues_unset_for_grouped_row(self):
        async def runner():
            calls: list = []
            app = SettingsApp()
            app._run_projects_group = _make_stub(calls)
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                await pilot.press("g")
                await pilot.pause()
                # Row 0 == alpha (grouped) → unset fires.
                app._pg_clear()
                await pilot.pause()
                self.assertIn(("unset", "alpha"), calls)
        self._run(runner())

    def test_clear_noops_for_ungrouped_row(self):
        async def runner():
            calls: list = []
            app = SettingsApp()
            app._run_projects_group = _make_stub(calls)
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                await pilot.press("g")
                await pilot.pause()
                table = app.query_one("#project_groups_table", DataTable)
                # Move the cursor to beta (ungrouped) and clear → no unset.
                table.move_cursor(row=1)
                app._pg_clear()
                await pilot.pause()
                self.assertFalse(any(c and c[0] == "unset" for c in calls))
        self._run(runner())

    def test_rename_issues_rename_verb(self):
        async def runner():
            calls: list = []
            app = SettingsApp()
            app._run_projects_group = _make_stub(calls)
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                await pilot.press("g")
                await pilot.pause()
                app._pg_rename()
                await pilot.pause()
                self.assertIsInstance(app.screen, RenameGroupScreen)
                app.screen.query_one("#rename_group_input", Input).value = "team_z"
                app.screen._do_rename()
                await pilot.pause()
                self.assertIn(("rename", "team_a", "team_z"), calls)
        self._run(runner())

    def test_rename_rejects_invalid_new_slug(self):
        async def runner():
            calls: list = []
            app = SettingsApp()
            app._run_projects_group = _make_stub(calls)
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                await pilot.press("g")
                await pilot.pause()
                app._pg_rename()
                await pilot.pause()
                app.screen.query_one("#rename_group_input", Input).value = "Bad Slug"
                app.screen._do_rename()
                await pilot.pause()
                self.assertIsInstance(app.screen, RenameGroupScreen)
                self.assertFalse(any(c and c[0] == "rename" for c in calls))
        self._run(runner())

    def test_sync_issues_sync_verb(self):
        async def runner():
            calls: list = []
            app = SettingsApp()
            app._run_projects_group = _make_stub(calls)
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                await pilot.press("g")
                await pilot.pause()
                app._pg_sync()
                await pilot.pause()
                self.assertIn(("sync",), calls)
        self._run(runner())


class ContextualShortcutTests(_Fixture):
    """The tab's action buttons have keyboard shortcuts that fire ONLY while
    the Project Groups tab is active (and are inert under a modal)."""

    _PG_ACTIONS = ("pg_assign", "pg_clear", "pg_rename", "pg_sync", "pg_refresh")

    def test_actions_gated_to_the_project_groups_tab(self):
        async def runner():
            app = SettingsApp()
            app._run_projects_group = _make_stub([])
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                await pilot.press("g")
                await pilot.pause()
                for act in self._PG_ACTIONS:
                    self.assertTrue(
                        app.check_action(act, None),
                        f"{act} should be active on the Project Groups tab")
                await pilot.press("a")  # switch to Agent Defaults
                await pilot.pause()
                for act in self._PG_ACTIONS:
                    self.assertIsNone(
                        app.check_action(act, None),
                        f"{act} must be inert off the Project Groups tab")
        self._run(runner())

    def test_actions_inert_while_modal_active(self):
        async def runner():
            app = SettingsApp()
            app._run_projects_group = _make_stub([])
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                await pilot.press("g")
                await pilot.pause()
                app._pg_assign()  # opens AssignGroupScreen
                await pilot.pause()
                self.assertIsInstance(app.screen, AssignGroupScreen)
                for act in self._PG_ACTIONS:
                    self.assertIsNone(app.check_action(act, None))
        self._run(runner())

    def test_sync_key_fires_on_tab(self):
        async def runner():
            calls: list = []
            app = SettingsApp()
            app._run_projects_group = _make_stub(calls)
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                await pilot.press("g")
                await pilot.pause()
                calls.clear()
                await pilot.press("y")  # Sync
                await pilot.pause()
                self.assertIn(("sync",), calls)
        self._run(runner())

    def test_refresh_key_repopulates_on_tab(self):
        async def runner():
            calls: list = []
            app = SettingsApp()
            app._run_projects_group = _make_stub(calls)
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                await pilot.press("g")
                await pilot.pause()
                calls.clear()
                await pilot.press("f")  # Refresh → re-runs `list`
                await pilot.pause()
                self.assertIn(("list",), calls)
        self._run(runner())

    def test_button_labels_carry_their_shortcut_key(self):
        async def runner():
            from shortcuts_mixin import render_label_cfg
            app = SettingsApp()
            app._run_projects_group = _make_stub([])
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                expected = {
                    "btn_pg_assign": render_label_cfg("Assign / change", "h"),
                    "btn_pg_clear": render_label_cfg("Clear group", "u"),
                    "btn_pg_rename": render_label_cfg("Rename group", "n"),
                    "btn_pg_sync": render_label_cfg("Sync from configs", "y"),
                    "btn_pg_refresh": render_label_cfg("Refresh", "f"),
                }
                for bid, label in expected.items():
                    self.assertEqual(str(app.query_one(f"#{bid}").label), label)
        self._run(runner())


if __name__ == "__main__":
    unittest.main()
