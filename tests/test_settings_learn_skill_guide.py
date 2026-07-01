"""Tests for the Settings TUI Project Config control for
`learn_skill_authoring_guide` (t1071_6).

This asserts the REAL user-facing save path — not a config_utils proxy: it
mounts the actual SettingsApp, edits the `learn_skill_authoring_guide` row in
the Project Config tab, and drives the app's own `save_project_settings()` (the
DOM-row-collection + persist path). So a raw/display-value or row-wiring bug
would fail here.

  - the setting renders as a ConfigRow in the Project Config tab (schema-driven);
  - setting its value and saving persists `learn_skill_authoring_guide: <path>`
    to aitasks/metadata/project_config.yaml;
  - blanking it and saving REMOVES the key (the "unset -> default" contract);
  - the key is registered in PROJECT_CONFIG_SCHEMA with summary/detail.

Run: python3 tests/test_settings_learn_skill_guide.py
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

import keybinding_registry  # noqa: E402
from shortcuts_mixin import refresh_label_case  # noqa: E402
from config_utils import load_yaml_config  # noqa: E402
from profile_editor import ConfigRow  # noqa: E402
from settings_app import PROJECT_CONFIG_SCHEMA, SettingsApp  # noqa: E402

KEY = "learn_skill_authoring_guide"


class _Fixture(unittest.TestCase):
    def setUp(self) -> None:
        keybinding_registry._reset_for_tests()
        refresh_label_case()
        self._prev_cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "aitasks" / "metadata").mkdir(parents=True, exist_ok=True)
        # A minimal, valid starting config (key absent).
        self.cfg = self.root / "aitasks" / "metadata" / "project_config.yaml"
        self.cfg.write_text("codeagent_coauthor_domain: example.io\n", encoding="utf-8")
        os.chdir(self.root)

    def tearDown(self) -> None:
        os.chdir(self._prev_cwd)
        self._tmp.cleanup()
        keybinding_registry._reset_for_tests()
        refresh_label_case()

    def _run(self, coro):
        return asyncio.run(coro)

    def _find_row(self, app) -> ConfigRow:
        for row in app.query_one("#project_content").query(ConfigRow):
            if getattr(row, "row_key", None) == KEY:
                return row
        raise AssertionError(f"no ConfigRow for {KEY!r} in the Project Config tab")


class SchemaTests(_Fixture):
    def test_key_registered_with_summary_and_detail(self):
        self.assertIn(KEY, PROJECT_CONFIG_SCHEMA)
        info = PROJECT_CONFIG_SCHEMA[KEY]
        self.assertTrue(info.get("summary"))
        self.assertTrue(info.get("detail"))


class SavePathTests(_Fixture):
    def test_row_renders_saves_and_clears(self):
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()

                # 1. The setting renders as an editable row.
                row = self._find_row(app)

                # 2. Set a value and save via the app's real save path.
                row.raw_value = "custom/house_guide.md"
                app.save_project_settings()
                await pilot.pause()
                data = load_yaml_config(self.cfg)
                self.assertEqual(data.get(KEY), "custom/house_guide.md")

                # 3. Blank it and save -> the key is removed (unset contract).
                row = self._find_row(app)  # re-query: save re-populated the tab
                row.raw_value = ""
                app.save_project_settings()
                await pilot.pause()
                data = load_yaml_config(self.cfg)
                self.assertNotIn(KEY, data)

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
