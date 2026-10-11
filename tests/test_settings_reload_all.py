"""Settings TUI `r` (reload all configs) must not crash (t1930).

`_reload_all_configs` repopulates every tab back to back. Each populate calls
`remove_children()`, which is deferred, and then mounts the new widgets right
away, so any fixed id mounted directly into a tab container collides with the
not-yet-removed copy and Textual raises `DuplicateIds`. The Profiles tab's
empty-state "Create New Profile" button had a fixed id and crashed the app on
`r` whenever the project had no execution profiles.

What is pinned here:

* `r` (twice) with no profiles keeps the app running, every tab repopulates,
  and exactly one add-new button survives once removals settle;
* the same with a profile (that path already used suffixed ids — pinned so it
  stays that way);
* the suffixed add-new button still opens the New Profile dialog;
* `r` with a malformed config (JSON or YAML) keeps the app running, names the
  unreadable file in an error, and keeps the config already loaded — all or
  nothing, so a valid file read before the broken one is not applied either —
  and a later `r` after the fix reloads normally (t1938);
* the error names the layer that actually failed — a broken per-user
  `*.local.json` is never reported as its project file — because `load_all`
  reads each JSON layer exactly once and merges what it read, with the same
  defaults <- project <- local precedence as `load_layered_config`.

Run: python3 tests/test_settings_reload_all.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "settings"))

from textual.widgets import Button  # noqa: E402

import config_utils  # noqa: E402
import keybinding_registry  # noqa: E402
from shortcuts_mixin import refresh_label_case  # noqa: E402
import settings_app  # noqa: E402
from settings_app import ConfigManager, NewProfileScreen, SettingsApp  # noqa: E402

META = Path("aitasks") / "metadata"
SIZE = (140, 60)
TAB_CONTAINERS = (
    "#agent_content", "#board_content", "#project_content",
    "#project_groups_content", "#tmux_content", "#models_content",
    "#profiles_content", "#shortcuts_content",
)


class _Fixture(unittest.TestCase):
    with_profile = False

    def setUp(self) -> None:
        keybinding_registry._reset_for_tests()
        refresh_label_case()
        self._prev_cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory(prefix="ait_reload_all_")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / META).mkdir(parents=True)
        os.chdir(self.root)
        self.addCleanup(os.chdir, self._prev_cwd)
        self.addCleanup(keybinding_registry._reset_for_tests)
        self.addCleanup(refresh_label_case)

        (self.root / META / "userconfig.yaml").write_text(
            "email: tester@example.com\n", encoding="utf-8")
        (self.root / META / "codeagent_config.json").write_text(
            json.dumps({"defaults": {}}) + "\n", encoding="utf-8")
        if self.with_profile:
            (self.root / META / "profiles").mkdir()
            (self.root / META / "profiles" / "fast.yaml").write_text(
                "name: fast\n", encoding="utf-8")

        prev_commit = settings_app.commit_metadata
        settings_app.commit_metadata = lambda paths, allow_new=False: SimpleNamespace(
            status="nochange", subject="", detail="", allow_new=allow_new)
        self.addCleanup(setattr, settings_app, "commit_metadata", prev_commit)
        self.notes: list = []
        self.errors: list = []

    def make_app(self) -> SettingsApp:
        app = SettingsApp()
        app._run_projects_group = lambda *a: (0, "", "")
        notes, errors = self.notes, self.errors

        def notify(message, **kw):
            notes.append(str(message))
            if kw.get("severity") == "error":
                errors.append(str(message))
        app.notify = notify
        return app

    def run_async(self, coro):
        return asyncio.run(coro)

    def assert_tabs_repopulated(self, app: SettingsApp) -> None:
        for sel in TAB_CONTAINERS:
            self.assertTrue(list(app.query_one(sel).children),
                            f"{sel} is empty after reload")

    def add_new_buttons(self, app: SettingsApp) -> list:
        return [b for b in app.query_one("#profiles_content").query(Button)
                if (b.id or "").startswith("btn_profile_add_new")]


class ReloadWithoutProfilesTest(_Fixture):
    with_profile = False

    def test_reload_keeps_running_and_repopulates(self) -> None:
        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                rc_before = app._repop_counter
                self.assertEqual(len(self.add_new_buttons(app)), 1)
                for _ in range(2):
                    await pilot.press("r")
                    await pilot.pause()
                await pilot.pause()
                self.assertTrue(app.is_running)
                self.assertGreater(app._repop_counter, rc_before)
                self.assert_tabs_repopulated(app)
                self.assertEqual(len(self.add_new_buttons(app)), 1)
                self.assertEqual(
                    self.notes.count("Configs reloaded from disk"), 2)
        self.run_async(body())

    def test_add_new_button_opens_dialog_after_reload(self) -> None:
        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                await pilot.press("r")
                await pilot.pause()
                (button,) = self.add_new_buttons(app)
                button.press()
                await pilot.pause()
                self.assertIsInstance(app.screen, NewProfileScreen)
        self.run_async(body())


class ReloadWithProfileTest(_Fixture):
    with_profile = True

    def test_reload_keeps_running_and_repopulates(self) -> None:
        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                for _ in range(2):
                    await pilot.press("r")
                    await pilot.pause()
                await pilot.pause()
                self.assertTrue(app.is_running)
                self.assert_tabs_repopulated(app)
                content = app.query_one("#profiles_content")
                hboxes = [w for w in content.children
                          if (w.id or "").startswith("profiles_buttons_")]
                self.assertEqual(len(hboxes), 1)
                self.assertEqual(self.add_new_buttons(app), [])
        self.run_async(body())



class ReloadMalformedConfigTest(_Fixture):
    with_profile = False

    def write(self, name: str, text: str) -> None:
        (self.root / META / name).write_text(text, encoding="utf-8")

    def assert_rejected(self, app: SettingsApp, filename: str) -> None:
        self.assertTrue(app.is_running)
        self.assertEqual(len(self.errors), 1, self.errors)
        self.assertIn(filename, self.errors[0])
        self.assertIn("press r", self.errors[0])
        self.assertNotIn("Configs reloaded from disk", self.notes)
        self.assert_tabs_repopulated(app)

    def test_malformed_codeagent_keeps_running(self) -> None:
        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                before = dict(app.config_mgr.codeagent)
                self.write("codeagent_config.json", "{not json")
                await pilot.press("r")
                await pilot.pause()
                self.assert_rejected(app, "codeagent_config.json")
                self.assertEqual(app.config_mgr.codeagent, before)
        self.run_async(body())

    def test_failure_is_all_or_nothing(self) -> None:
        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                before = (dict(app.config_mgr.codeagent),
                          dict(app.config_mgr.codeagent_project))
                # Valid and read first, but must not land: the board file
                # read after it is broken.
                self.write("codeagent_config.json",
                           json.dumps({"defaults": {"pick": "x/y"}}))
                self.write("board_config.json", "{not json")
                await pilot.press("r")
                await pilot.pause()
                self.assert_rejected(app, "board_config.json")
                self.assertEqual(before, (app.config_mgr.codeagent,
                                          app.config_mgr.codeagent_project))
        self.run_async(body())

    def test_malformed_project_yaml(self) -> None:
        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                self.write("project_config.yaml", "key: [unclosed\n")
                await pilot.press("r")
                await pilot.pause()
                self.assert_rejected(app, "project_config.yaml")
        self.run_async(body())

    def test_reload_recovers_after_fix(self) -> None:
        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                self.write("codeagent_config.json", "{not json")
                await pilot.press("r")
                await pilot.pause()
                self.assertEqual(len(self.errors), 1)
                self.write("codeagent_config.json",
                           json.dumps({"defaults": {"pick": "x/y"}}))
                await pilot.press("r")
                await pilot.pause()
                self.assertTrue(app.is_running)
                self.assertEqual(len(self.errors), 1)
                self.assertIn("Configs reloaded from disk", self.notes)
                self.assertEqual(
                    app.config_mgr.codeagent["defaults"]["pick"], "x/y")
        self.run_async(body())


    def _assert_local_named(self, project_name: str) -> None:
        local_name = project_name.replace(".json", ".local.json")

        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                self.write(local_name, "{not json")
                await pilot.press("r")
                await pilot.pause()
                self.assert_rejected(app, local_name)
                self.assertNotIn(project_name, self.errors[0])
        self.run_async(body())

    def test_malformed_codeagent_local_layer_is_named(self) -> None:
        self._assert_local_named("codeagent_config.json")

    def test_malformed_board_local_layer_is_named(self) -> None:
        self._assert_local_named("board_config.json")

    def test_non_object_layer_is_rejected(self) -> None:
        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                self.write("codeagent_config.local.json", "[]")
                await pilot.press("r")
                await pilot.pause()
                self.assert_rejected(app, "codeagent_config.local.json")
                self.assertIn("JSON object", self.errors[0])
        self.run_async(body())


class LoadAllLayersTest(_Fixture):
    """`ConfigManager.load_all` without the TUI."""

    def write(self, name: str, data) -> None:
        (self.root / META / name).write_text(json.dumps(data), encoding="utf-8")

    def test_each_json_layer_read_once(self) -> None:
        self.write("codeagent_config.local.json", {"defaults": {}})
        self.write("board_config.json", {"columns": []})
        self.write("board_config.local.json", {"columns": []})
        mgr = ConfigManager()
        reads: list = []

        def counting(load):
            def wrapper(path):
                reads.append(Path(path).name)
                return load(path)
            return wrapper
        # Both modules' bindings: a regression back to load_layered_config
        # would re-read through config_utils' own global.
        for mod in (settings_app, config_utils):
            prev = mod._load_json
            mod._load_json = counting(prev)
            self.addCleanup(setattr, mod, "_load_json", prev)
        mgr.load_all()
        layers = [n for n in reads if n.startswith(("codeagent_config", "board_config"))]
        self.assertEqual(sorted(layers), sorted([
            "codeagent_config.json", "codeagent_config.local.json",
            "board_config.json", "board_config.local.json"]))

    def test_merge_matches_load_layered_config(self) -> None:
        self.write("codeagent_config.json", {
            "defaults": {"pick": "a/1", "explore": "a/2"}, "extra": [1, 2]})
        self.write("codeagent_config.local.json", {
            "defaults": {"pick": "b/1"}, "extra": [3]})
        self.write("board_config.json", {
            "columns": [{"id": "now"}], "settings": {"x": 1}})
        self.write("board_config.local.json", {"settings": {"auto_refresh_minutes": 5}})
        mgr = ConfigManager()
        self.assertEqual(mgr.codeagent, config_utils.load_layered_config(
            str(settings_app.CODEAGENT_CONFIG), defaults={"defaults": {}}))
        self.assertEqual(mgr.codeagent["defaults"],
                         {"pick": "b/1", "explore": "a/2"})
        self.assertEqual(mgr.codeagent["extra"], [3])
        self.assertEqual(mgr.board, config_utils.load_layered_config(
            str(settings_app.BOARD_CONFIG), defaults={
                "columns": [], "column_order": [],
                "settings": {"auto_refresh_minutes": 0}}))
        self.assertEqual(mgr.board["settings"],
                         {"auto_refresh_minutes": 5, "x": 1})
        self.assertEqual(mgr.board["column_order"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
