"""Tests for the Settings TUI Shortcuts tab (t848_5).

Covers:
  - The tab populates from keybinding_registry.iter_all_bindings AFTER the
    global sweep, so cross-TUI scopes (board, monitor, brainstorm, ...) appear
    even though only SettingsApp is instantiated.
  - `s` switches to the Shortcuts tab.
  - A row edit (override saved) is reflected on repaint (Current + Origin).
  - Reset-scope clears that scope's overrides.
  - Lint pushes a results screen when there is drift, notifies when clean.
  - "Export shortcuts" produces a bundle whose top-level `shortcuts` member is
    only the subtree (no email); "Import shortcuts" deep-merges preserving the
    local email.
  - The general ExportScreen carries a "Shortcuts" category (export/import of
    shortcuts is the general e/i flow, not dedicated tab buttons); ImportScreen
    surfaces a `shortcuts` entry when the bundle carries one.

Run: python3 tests/test_settings_shortcuts_tab.py
"""

from __future__ import annotations

import asyncio
import glob
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "settings"))

import yaml  # noqa: E402
from textual.widgets import DataTable, Input  # noqa: E402

import keybinding_registry  # noqa: E402
import shortcut_persist  # noqa: E402
from settings_app import (  # noqa: E402
    ExportScreen,
    ImportScreen,
    LintResultsScreen,
    SettingsApp,
)


def _read_userconfig() -> dict:
    p = Path("aitasks/metadata/userconfig.yaml")
    if not p.is_file():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


class _Fixture(unittest.TestCase):
    """chdir into a temp workspace with userconfig.yaml; reset registry state."""

    def setUp(self) -> None:
        keybinding_registry._reset_for_tests()
        self._prev_cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "aitasks" / "metadata").mkdir(parents=True, exist_ok=True)
        (self.root / "aitasks" / "metadata" / "userconfig.yaml").write_text(
            "# Local user configuration (gitignored, not shared)\n"
            "email: tester@example.com\n",
            encoding="utf-8",
        )
        os.chdir(self.root)

    def tearDown(self) -> None:
        os.chdir(self._prev_cwd)
        self._tmp.cleanup()
        keybinding_registry._reset_for_tests()

    def _run(self, coro):
        return asyncio.run(coro)

    def _table_scopes(self, table: DataTable) -> set[str]:
        return {str(table.get_row(rk)[0]) for rk in table.rows}

    def _row_for(self, table: DataTable, scope: str, action_id: str):
        for rk in table.rows:
            row = table.get_row(rk)
            if str(row[0]) == scope and str(row[1]) == action_id:
                return row
        return None


class PopulateTests(_Fixture):
    def test_tab_populated_with_cross_tui_scopes(self):
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                table = app.query_one("#shortcuts_table", DataTable)
                scopes = self._table_scopes(table)
                for need in ("board", "monitor", "brainstorm", "settings",
                             "shared", "shared.tui_switcher"):
                    self.assertIn(need, scopes)
                self.assertGreater(table.row_count, 20)
        self._run(runner())

    def test_s_switches_to_shortcuts_tab(self):
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                await pilot.press("s")
                await pilot.pause()
                self.assertEqual(app.query_one("TabbedContent").active, "tab_shortcuts")
        self._run(runner())

    def test_buttons_render_shortcut_key_in_label(self):
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                labels = {
                    bid: str(app.query_one(f"#{bid}").label)
                    for bid in ("btn_sc_reset", "btn_sc_lint")
                }
                self.assertEqual(labels["btn_sc_lint"], "(L)int coherence")
                self.assertEqual(labels["btn_sc_reset"], "(D) Reset scope")
                # The sc_* bindings stay out of the footer (show=False). Export
                # /import of shortcuts is the general e/i action, not tab buttons.
                sc = {b.action: b.show for b in SettingsApp.BINDINGS
                      if b.action in ("sc_reset", "sc_lint")}
                self.assertEqual(set(sc), {"sc_reset", "sc_lint"})
                self.assertTrue(all(show is False for show in sc.values()))
        self._run(runner())

    def test_row_edit_reflected_on_repaint(self):
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                table = app.query_one("#shortcuts_table", DataTable)
                # Pick a real (scope, action) row to override.
                rk = next(iter(table.rows))
                scope, action_id = (str(c) for c in table.get_row(rk)[:2])
                shortcut_persist.save_override(scope, action_id, "ctrl+y")
                app._populate_shortcuts_tab()
                table = app.query_one("#shortcuts_table", DataTable)
                row = self._row_for(table, scope, action_id)
                self.assertIsNotNone(row)
                self.assertEqual(str(row[2]), "ctrl+y")  # Current
                self.assertEqual(str(row[5]), "user")     # Origin
        self._run(runner())


class NavigationTests(_Fixture):
    def test_arrow_nav_between_tab_title_search_and_table(self):
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                await pilot.press("s")           # switch to Shortcuts tab
                await pilot.pause()
                table = app.query_one("#shortcuts_table", DataTable)
                search = app.query_one("#shortcuts_search", Input)
                self.assertIs(app.focused, table)        # table focused on entry
                await pilot.press("up")                  # row 0 -> search box
                self.assertIs(app.focused, search)
                await pilot.press("up")                  # search box -> tab title
                self.assertIn("Tabs", type(app.focused).__name__)
                await pilot.press("down")                # tab title -> search box
                self.assertIs(app.focused, search)
                await pilot.press("down")                # search box -> table row 0
                self.assertIs(app.focused, table)
                self.assertEqual(table.cursor_row, 0)
                await pilot.press("down")                # row 0 -> row 1 (in-table)
                self.assertEqual(table.cursor_row, 1)
        self._run(runner())

    def test_search_box_filters_table(self):
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                table = app.query_one("#shortcuts_table", DataTable)
                full_count = table.row_count
                # Pick a real action_id to filter for, then type it.
                rk = next(iter(table.rows))
                action_id = str(table.get_row(rk)[1])
                search = app.query_one("#shortcuts_search", Input)
                # Setting .value posts Input.Changed, driving the live filter.
                search.value = action_id
                await pilot.pause()
                table = app.query_one("#shortcuts_table", DataTable)
                self.assertLessEqual(table.row_count, full_count)
                self.assertGreaterEqual(table.row_count, 1)
                # The targeted action survives the filter.
                actions = {str(table.get_row(r)[1]) for r in table.rows}
                self.assertIn(action_id, actions)
                # Clearing restores the full list.
                search.value = ""
                await pilot.pause()
                table = app.query_one("#shortcuts_table", DataTable)
                self.assertEqual(table.row_count, full_count)
        self._run(runner())

    def test_check_action_gates_shortcut_bindings_to_tab(self):
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                await pilot.press("s")
                await pilot.pause()
                self.assertTrue(app.check_action("sc_lint", None))
                await pilot.press("a")           # switch to Agent Defaults tab
                await pilot.pause()
                self.assertIsNone(app.check_action("sc_lint", None))
        self._run(runner())

    def test_l_key_triggers_lint_on_tab(self):
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                await pilot.press("s")
                await pilot.pause()
                keybinding_registry._DEFAULTS[("board", "quit")] = ("q", "Quit")
                keybinding_registry._DEFAULTS[("monitor", "quit")] = ("x", "Quit")
                await pilot.press("l")
                await pilot.pause()
                self.assertIsInstance(app.screen, LintResultsScreen)
        self._run(runner())

    def test_d_key_opens_reset_confirm_on_tab(self):
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                await pilot.press("s")
                await pilot.pause()
                await pilot.press("d")           # selected row's scope
                await pilot.pause()
                from settings_app import ResetShortcutsConfirmScreen
                self.assertIsInstance(app.screen, ResetShortcutsConfirmScreen)
        self._run(runner())


class ResetTests(_Fixture):
    def test_handle_reset_scope_clears_overrides(self):
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                shortcut_persist.save_override("board", "pick", "z")
                self.assertEqual(
                    _read_userconfig()["shortcuts"]["board"]["pick"], "z")
                app._handle_reset_scope(True, "board")
                await pilot.pause()
                self.assertNotIn(
                    "board", _read_userconfig().get("shortcuts", {}))
        self._run(runner())

    def test_handle_reset_scope_declined_keeps_overrides(self):
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                shortcut_persist.save_override("board", "pick", "z")
                app._handle_reset_scope(False, "board")
                await pilot.pause()
                self.assertEqual(
                    _read_userconfig()["shortcuts"]["board"]["pick"], "z")
        self._run(runner())


class LintTests(_Fixture):
    def test_lint_pushes_results_screen_on_drift(self):
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                # Force a coherence conflict for a shared action across scopes.
                keybinding_registry._DEFAULTS[("board", "quit")] = ("q", "Quit")
                keybinding_registry._DEFAULTS[("monitor", "quit")] = ("x", "Quit")
                app._lint_shortcuts()
                await pilot.pause()
                self.assertIsInstance(app.screen, LintResultsScreen)
        self._run(runner())


class ExportImportTests(_Fixture):
    def test_export_shortcuts_only_bundle_no_email(self):
        async def runner():
            (self.root / "aitasks" / "metadata" / "userconfig.yaml").write_text(
                "email: tester@example.com\n"
                "shortcuts:\n  board:\n    pick: o\n",
                encoding="utf-8",
            )
            keybinding_registry.refresh_all()
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                app._handle_export(
                    {"directory": str(self.root), "patterns": ["__shortcuts__"]})
                await pilot.pause()
                bundles = glob.glob(str(self.root / "*.aitcfg.json"))
                self.assertTrue(bundles)
                data = json.loads(Path(bundles[0]).read_text(encoding="utf-8"))
                self.assertEqual(data["files"], {})
                self.assertEqual(data["shortcuts"], {"board": {"pick": "o"}})
                self.assertNotIn("tester@example.com", json.dumps(data))
        self._run(runner())

    def test_import_shortcuts_merges_preserving_email(self):
        async def runner():
            bundle = {
                "_export_meta": {"version": 1, "exported_at": "x", "file_count": 1},
                "files": {},
                "shortcuts": {"board": {"pick": "o"}},
            }
            bpath = self.root / "in.aitcfg.json"
            bpath.write_text(json.dumps(bundle), encoding="utf-8")
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                # import_all_configs writes userconfig.yaml synchronously before
                # the (fire-and-forget) tab repaints, so assert the file directly
                # without waiting on the screen to fully quiesce.
                app._handle_import({
                    "path": str(bpath), "overwrite": True,
                    "selected_files": ["shortcuts"],
                })
                uc = _read_userconfig()
                self.assertEqual(uc["email"], "tester@example.com")
                self.assertEqual(uc["shortcuts"]["board"]["pick"], "o")
        self._run(runner())

    def test_general_export_screen_has_shortcuts_category(self):
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                screen = ExportScreen()
                app.push_screen(screen)
                await pilot.pause()
                from settings_app import CycleField
                # The general Export screen carries a "Shortcuts" category
                # (default yes) — no dedicated tab export button needed.
                sc = screen.query_one("#cf_exp_shortcuts", CycleField)
                self.assertEqual(sc.current_value, "yes")
        self._run(runner())

    def test_import_screen_surfaces_shortcuts_entry(self):
        async def runner():
            bundle = {
                "_export_meta": {"version": 1, "exported_at": "x", "file_count": 1},
                "files": {},
                "shortcuts": {"board": {"pick": "o"}},
            }
            bpath = self.root / "in.aitcfg.json"
            bpath.write_text(json.dumps(bundle), encoding="utf-8")
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                screen = ImportScreen()
                app.push_screen(screen)
                await pilot.pause()
                screen.query_one("#import_path").value = str(bpath)
                screen.do_next()
                await pilot.pause()
                from settings_app import CycleField
                cf = screen.query_one("#cf_imp_shortcuts", CycleField)
                self.assertEqual(cf.current_value, "yes")
        self._run(runner())


if __name__ == "__main__":
    unittest.main()
