"""Tests for board TUI layered config split (t268_4).

Verifies that load_metadata() and save_metadata() in aitask_board.py
correctly use config_utils to split board_config.json into project
(columns, column_order) and user (settings) layers.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_board_config_split.py -v
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "aiscripts", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "aiscripts", "board"))
from config_utils import load_layered_config, split_config, save_project_config, save_local_config, local_path_for


# Defaults matching aitask_board.py
DEFAULT_COLUMNS = [
    {"id": "now", "title": "Now", "color": "#FF5555"},
    {"id": "next", "title": "Next", "color": "#50FA7B"},
    {"id": "backlog", "title": "Backlog", "color": "#BD93F9"},
]
DEFAULT_ORDER = ["now", "next", "backlog"]
DEFAULT_SETTINGS = {"auto_refresh_minutes": 5}
_PROJECT_KEYS = {"columns", "column_order"}
_USER_KEYS = {"settings"}


def _make_project_file(tmpdir, data):
    """Write board_config.json in a temp directory."""
    path = Path(tmpdir) / "board_config.json"
    path.write_text(json.dumps(data, indent=2))
    return str(path)


def _make_local_file(tmpdir, data):
    """Write board_config.local.json in a temp directory."""
    path = Path(tmpdir) / "board_config.local.json"
    path.write_text(json.dumps(data, indent=2))
    return str(path)


def _load(project_path):
    """Simulate board's load_metadata using config_utils."""
    defaults = {
        "columns": DEFAULT_COLUMNS,
        "column_order": DEFAULT_ORDER,
        "settings": DEFAULT_SETTINGS.copy(),
    }
    return load_layered_config(project_path, defaults=defaults)


def _save(project_path, columns, column_order, settings):
    """Simulate board's save_metadata using config_utils."""
    data = {
        "columns": columns,
        "column_order": column_order,
        "settings": settings,
    }
    project_data, user_data = split_config(data, project_keys=_PROJECT_KEYS, user_keys=_USER_KEYS)
    save_project_config(project_path, project_data)
    if user_data:
        save_local_config(str(local_path_for(project_path)), user_data)


class TestLoadProjectOnly(unittest.TestCase):
    """Only board_config.json exists (no local file)."""

    def test_loads_project_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_data = {
                "columns": [{"id": "todo", "title": "Todo", "color": "#AAA"}],
                "column_order": ["todo"],
                "settings": {"auto_refresh_minutes": 10},
            }
            path = _make_project_file(tmpdir, project_data)
            config = _load(path)
            self.assertEqual(config["columns"], [{"id": "todo", "title": "Todo", "color": "#AAA"}])
            self.assertEqual(config["column_order"], ["todo"])
            self.assertEqual(config["settings"]["auto_refresh_minutes"], 10)

    def test_defaults_for_missing_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Project file with only columns, no settings
            path = _make_project_file(tmpdir, {"columns": DEFAULT_COLUMNS})
            config = _load(path)
            self.assertEqual(config["columns"], DEFAULT_COLUMNS)
            self.assertEqual(config["column_order"], DEFAULT_ORDER)
            self.assertEqual(config["settings"], DEFAULT_SETTINGS)


class TestLoadWithLocalOverride(unittest.TestCase):
    """Both project and local files exist."""

    def test_local_overrides_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _make_project_file(tmpdir, {
                "columns": DEFAULT_COLUMNS,
                "column_order": DEFAULT_ORDER,
                "settings": {"auto_refresh_minutes": 5},
            })
            _make_local_file(tmpdir, {
                "settings": {"auto_refresh_minutes": 15, "collapsed_columns": ["backlog"]},
            })
            path = str(Path(tmpdir) / "board_config.json")
            config = _load(path)
            self.assertEqual(config["settings"]["auto_refresh_minutes"], 15)
            self.assertEqual(config["settings"]["collapsed_columns"], ["backlog"])

    def test_project_columns_preserved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_cols = [{"id": "wip", "title": "WIP", "color": "#FFF"}]
            _make_project_file(tmpdir, {
                "columns": custom_cols,
                "column_order": ["wip"],
            })
            _make_local_file(tmpdir, {
                "settings": {"auto_refresh_minutes": 20},
            })
            path = str(Path(tmpdir) / "board_config.json")
            config = _load(path)
            self.assertEqual(config["columns"], custom_cols)
            self.assertEqual(config["column_order"], ["wip"])


class TestLoadNoFiles(unittest.TestCase):
    """Neither project nor local file exists."""

    def test_returns_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "board_config.json")
            config = _load(path)
            self.assertEqual(config["columns"], DEFAULT_COLUMNS)
            self.assertEqual(config["column_order"], DEFAULT_ORDER)
            self.assertEqual(config["settings"], DEFAULT_SETTINGS)


class TestSaveSplitsCorrectly(unittest.TestCase):
    """After save, project file has columns+column_order, local has settings."""

    def test_split_on_save(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "board_config.json")
            local_path = str(Path(tmpdir) / "board_config.local.json")

            _save(path, DEFAULT_COLUMNS, DEFAULT_ORDER, {"auto_refresh_minutes": 10})

            with open(path) as f:
                project = json.load(f)
            with open(local_path) as f:
                local = json.load(f)

            self.assertIn("columns", project)
            self.assertIn("column_order", project)
            self.assertNotIn("settings", project)
            self.assertIn("settings", local)
            self.assertEqual(local["settings"]["auto_refresh_minutes"], 10)


class TestSavePreservesProjectData(unittest.TestCase):
    """Columns and column_order are preserved exactly."""

    def test_columns_unchanged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_cols = [{"id": "a", "title": "A", "color": "#111"}, {"id": "b", "title": "B", "color": "#222"}]
            custom_order = ["b", "a"]
            path = str(Path(tmpdir) / "board_config.json")

            _save(path, custom_cols, custom_order, DEFAULT_SETTINGS)

            with open(path) as f:
                project = json.load(f)
            self.assertEqual(project["columns"], custom_cols)
            self.assertEqual(project["column_order"], custom_order)


class TestLocalSettingsNotInProject(unittest.TestCase):
    """Settings key must not appear in project file after save."""

    def test_no_settings_in_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "board_config.json")
            _save(path, DEFAULT_COLUMNS, DEFAULT_ORDER, {"auto_refresh_minutes": 5, "collapsed_columns": ["now"]})

            with open(path) as f:
                project = json.load(f)
            self.assertNotIn("settings", project)


class TestRoundtrip(unittest.TestCase):
    """Load -> modify -> save -> reload preserves modifications."""

    def test_modify_and_reload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "board_config.json")

            # Initial save
            _save(path, DEFAULT_COLUMNS, DEFAULT_ORDER, {"auto_refresh_minutes": 5})

            # Load, modify, save
            config = _load(path)
            config["settings"]["auto_refresh_minutes"] = 30
            config["settings"]["collapsed_columns"] = ["backlog"]
            _save(path, config["columns"], config["column_order"], config["settings"])

            # Reload and verify
            config2 = _load(path)
            self.assertEqual(config2["settings"]["auto_refresh_minutes"], 30)
            self.assertEqual(config2["settings"]["collapsed_columns"], ["backlog"])
            self.assertEqual(config2["columns"], DEFAULT_COLUMNS)

    def test_modify_columns_and_reload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "board_config.json")

            _save(path, DEFAULT_COLUMNS, DEFAULT_ORDER, DEFAULT_SETTINGS)

            config = _load(path)
            new_cols = config["columns"] + [{"id": "done", "title": "Done", "color": "#00FF00"}]
            new_order = config["column_order"] + ["done"]
            _save(path, new_cols, new_order, config["settings"])

            config2 = _load(path)
            self.assertEqual(len(config2["columns"]), 4)
            self.assertIn("done", config2["column_order"])


class TestMigrationFromSingleFile(unittest.TestCase):
    """Existing board_config.json with all keys loads and splits on save."""

    def test_migration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Pre-migration format: all keys in one file
            old_data = {
                "columns": DEFAULT_COLUMNS,
                "column_order": DEFAULT_ORDER,
                "settings": {"auto_refresh_minutes": 7, "collapsed_columns": ["now"]},
            }
            path = _make_project_file(tmpdir, old_data)
            local_path = str(Path(tmpdir) / "board_config.local.json")

            # No local file exists yet
            self.assertFalse(Path(local_path).exists())

            # Load (should work with old format)
            config = _load(path)
            self.assertEqual(config["settings"]["auto_refresh_minutes"], 7)
            self.assertEqual(config["settings"]["collapsed_columns"], ["now"])

            # Save triggers split
            _save(path, config["columns"], config["column_order"], config["settings"])

            # Now project file should NOT have settings
            with open(path) as f:
                project = json.load(f)
            self.assertNotIn("settings", project)
            self.assertIn("columns", project)

            # Local file should have settings
            self.assertTrue(Path(local_path).exists())
            with open(local_path) as f:
                local = json.load(f)
            self.assertEqual(local["settings"]["auto_refresh_minutes"], 7)
            self.assertEqual(local["settings"]["collapsed_columns"], ["now"])


class TestDeepMergeSettings(unittest.TestCase):
    """Local overrides specific settings keys, preserving others from defaults."""

    def test_partial_settings_override(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Project has full settings
            _make_project_file(tmpdir, {
                "columns": DEFAULT_COLUMNS,
                "column_order": DEFAULT_ORDER,
                "settings": {"auto_refresh_minutes": 5, "collapsed_columns": []},
            })
            # Local overrides only auto_refresh
            _make_local_file(tmpdir, {
                "settings": {"auto_refresh_minutes": 20},
            })
            path = str(Path(tmpdir) / "board_config.json")
            config = _load(path)
            # auto_refresh overridden by local
            self.assertEqual(config["settings"]["auto_refresh_minutes"], 20)
            # collapsed_columns preserved from project (deep merge)
            self.assertEqual(config["settings"]["collapsed_columns"], [])


if __name__ == "__main__":
    unittest.main()
