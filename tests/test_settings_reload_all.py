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
  defaults <- project <- local precedence as `load_layered_config`;
* a well-formed layer with a mistyped key a reader depends on (code-agent
  `defaults` an object; board `columns` an array of objects, `settings` an
  object) is rejected the same way, naming its layer — before t1945
  `{"defaults": null}` was swapped in and `_populate_agent_tab` crashed the
  app — while keys no reader depends on (`column_order`) still load (t1945);
* every save/revert handler re-reads only its own config family, so an
  unrelated malformed file never blocks it, and a failure in its own family is
  reported instead of escaping the button handler; a save whose re-read fails
  says the write landed, leaves every loaded representation untouched (payloads
  are deep copies), and latches the family: further saves are refused before
  touching disk until a successful re-read, so none can be built on memory that
  is behind the earlier write. An import whose reload fails latches every
  family (t1945).

Run: python3 tests/test_settings_reload_all.py
"""
from __future__ import annotations

import asyncio
import copy
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

from profile_editor import CycleField  # noqa: E402

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

    def test_mistyped_defaults_keeps_loaded_state(self) -> None:
        self.write("codeagent_config.json", json.dumps({"defaults": {"pick": "a/1"}}))

        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                before = (copy.deepcopy(app.config_mgr.codeagent),
                          copy.deepcopy(app.config_mgr.codeagent_project))
                self.write("codeagent_config.json", json.dumps({"defaults": None}))
                await pilot.press("r")
                await pilot.pause()
                self.assert_rejected(app, "codeagent_config.json")
                self.assertIn("'defaults'", self.errors[0])
                self.assertIn("null", self.errors[0])
                self.assertEqual(before, (app.config_mgr.codeagent,
                                          app.config_mgr.codeagent_project))
        self.run_async(body())

    def test_mistyped_local_defaults_is_named(self) -> None:
        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                self.write("codeagent_config.local.json", json.dumps({"defaults": []}))
                await pilot.press("r")
                await pilot.pause()
                self.assert_rejected(app, "codeagent_config.local.json")
                self.assertNotIn("codeagent_config.json", self.errors[0])
        self.run_async(body())

    def test_mistyped_board_settings_keeps_running(self) -> None:
        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                before = copy.deepcopy(app.config_mgr.board)
                self.write("board_config.json", json.dumps({"settings": None}))
                await pilot.press("r")
                await pilot.pause()
                self.assert_rejected(app, "board_config.json")
                self.assertEqual(app.config_mgr.board, before)
        self.run_async(body())


class SaveRevertRefreshTest(_Fixture):
    """Save/revert handlers re-read their own family; failures are reported."""

    with_profile = True

    def write(self, name: str, data) -> None:
        text = data if isinstance(data, str) else json.dumps(data)
        (self.root / META / name).write_text(text, encoding="utf-8")

    def read(self, name: str):
        path = self.root / META / name
        return path.read_bytes() if path.exists() else None

    def failing(self, app, method: str, name: str) -> None:
        """Make the manager's `method` re-read raise, as if `name` were bad."""
        def boom():
            raise settings_app.ConfigReadError(META / name, "simulated failure")
        setattr(app.config_mgr, method, boom)

    def codeagent_state(self, app):
        mgr = app.config_mgr
        return copy.deepcopy((mgr.codeagent, mgr.codeagent_project,
                              mgr.codeagent_local))

    def board_state(self, app):
        mgr = app.config_mgr
        return copy.deepcopy((mgr.board, mgr.board_project, mgr.board_local))

    def assert_one_error(self, *fragments: str) -> None:
        self.assertEqual(len(self.errors), 1, self.errors)
        for fragment in fragments:
            self.assertIn(fragment, self.errors[0])

    def test_board_revert_ignores_unrelated_bad_config(self) -> None:
        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                before = self.codeagent_state(app)
                self.write("codeagent_config.json", {"defaults": None})
                app._revert_board_settings()
                await pilot.pause()
                self.assertTrue(app.is_running)
                self.assertEqual(self.errors, [])
                self.assertIn("Board settings reverted", self.notes)
                self.assertEqual(self.codeagent_state(app), before)
        self.run_async(body())

    def test_board_revert_reports_own_bad_config(self) -> None:
        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                before = self.board_state(app)
                self.write("board_config.json", {"columns": {}})
                app._revert_board_settings()
                await pilot.pause()
                self.assertTrue(app.is_running)
                self.assert_one_error("Cannot revert", "board_config.json")
                self.assertNotIn("Board settings reverted", self.notes)
                self.assertEqual(self.board_state(app), before)
        self.run_async(body())

    def test_project_revert_ignores_unrelated_bad_config(self) -> None:
        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                self.write("board_config.json", {"settings": []})
                app._revert_project_settings()
                await pilot.pause()
                self.assertTrue(app.is_running)
                self.assertEqual(self.errors, [])
                self.assertIn("Project config reverted", self.notes)
        self.run_async(body())

    def test_board_save_refresh_failure(self) -> None:
        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                field = next(cf for cf in app.query_one("#board_content").query(CycleField)
                             if cf.field_key == "auto_refresh_minutes")
                field.current_index = field.options.index("5")
                before = self.board_state(app)
                self.failing(app, "reload_board", "board_config.local.json")
                app.save_board_settings()
                await pilot.pause()
                # (a) the write landed
                local = json.loads(self.read("board_config.local.json"))
                self.assertEqual(local["settings"]["auto_refresh_minutes"], 5)
                # (b) the notification says so, and nothing claims plain success
                self.assert_one_error("Board settings saved, but re-reading",
                                      "board_config.local.json")
                self.assertNotIn("Board settings saved", self.notes)
                # (c) every loaded representation is untouched
                self.assertEqual(self.board_state(app), before)
                self.assertTrue(app.config_mgr.needs_reload("board"))
                # A second save is refused before touching disk.
                written = self.read("board_config.local.json")
                field.current_index = field.options.index("10")
                app.save_board_settings()
                self.assertEqual(self.read("board_config.local.json"), written)
                self.assertEqual(len(self.errors), 2)
                self.assertIn("Not saved", self.errors[1])
                # A successful revert re-reads the family and releases it.
                del app.config_mgr.reload_board
                app._revert_board_settings()
                await pilot.pause()
                self.assertFalse(app.config_mgr.needs_reload("board"))
                self.assertEqual(
                    app.config_mgr.board["settings"]["auto_refresh_minutes"], 5)
        self.run_async(body())

    def test_clear_override_refresh_failure(self) -> None:
        self.write("codeagent_config.json", {"defaults": {"pick": "p/1"}})
        self.write("codeagent_config.local.json", {"defaults": {"pick": "a/1"}})

        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                before = self.codeagent_state(app)
                self.failing(app, "reload_codeagent", "codeagent_config.local.json")
                app._clear_user_override("pick")
                await pilot.pause()
                # (a) the local override is gone from disk (emptied → removed)
                self.assertIsNone(self.read("codeagent_config.local.json"))
                # (b)
                self.assert_one_error("Cleared user override for pick, but re-reading")
                self.assertNotIn("Cleared user override for pick", self.notes)
                # (c) all three representations agree with the pre-save state
                self.assertEqual(self.codeagent_state(app), before)
                self.assertEqual(app.config_mgr.codeagent_local,
                                 {"defaults": {"pick": "a/1"}})
                # The second clear is refused — not "no override" — and writes nothing.
                project = self.read("codeagent_config.json")
                app._clear_user_override("pick")
                self.assertEqual(len(self.errors), 2)
                self.assertIn("Not saved", self.errors[1])
                self.assertFalse(any("No user override" in n for n in self.notes))
                self.assertEqual(self.read("codeagent_config.json"), project)
                self.assertIsNone(self.read("codeagent_config.local.json"))
        self.run_async(body())

    def test_agent_pick_refresh_failure_then_second_save(self) -> None:
        self.write("codeagent_config.json", {"defaults": {"pick": "a/1"}})

        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                before = self.codeagent_state(app)
                self.failing(app, "reload_codeagent", "codeagent_config.local.json")
                app._editing_layer = "user"
                app._handle_agent_pick({"key": "pick", "value": "b/2"})
                await pilot.pause()
                local_path = "codeagent_config.local.json"
                self.assertEqual(json.loads(self.read(local_path)),
                                 {"defaults": {"pick": "b/2"}})          # (a)
                self.assert_one_error("Saved pick = b/2 (user), but re-reading")  # (b)
                self.assertEqual(self.codeagent_state(app), before)       # (c)

                # The lost-write regression: memory still says pick=a/1 (no
                # local layer), so a save built on it would drop pick=b/2.
                after_first = (self.read("codeagent_config.json"), self.read(local_path))
                app._handle_agent_pick({"key": "explore", "value": "c/3"})
                self.assertEqual(len(self.errors), 2)
                self.assertIn("Not saved", self.errors[1])
                self.assertEqual((self.read("codeagent_config.json"),
                                  self.read(local_path)), after_first)

                # Reload succeeds → latch released → the next save keeps b/2.
                del app.config_mgr.reload_codeagent
                await pilot.press("r")
                await pilot.pause()
                self.assertFalse(app.config_mgr.needs_reload("codeagent"))
                app._handle_agent_pick({"key": "explore", "value": "c/3"})
                self.assertEqual(json.loads(self.read(local_path)),
                                 {"defaults": {"pick": "b/2", "explore": "c/3"}})
                self.assertEqual(len(self.errors), 2)
        self.run_async(body())

    def test_project_layer_pick_refresh_failure_keeps_state(self) -> None:
        # The project branch also drops the op's local override: that local
        # `defaults` must be a detached copy too.
        self.write("codeagent_config.json", {"defaults": {"pick": "p/1"}})
        self.write("codeagent_config.local.json",
                   {"defaults": {"pick": "a/1", "explore": "e/1"}})

        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                before = self.codeagent_state(app)
                self.failing(app, "reload_codeagent", "codeagent_config.json")
                app._editing_layer = "project"
                app._handle_agent_pick({"key": "pick", "value": "b/2"})
                await pilot.pause()
                self.assertEqual(json.loads(self.read("codeagent_config.json")),
                                 {"defaults": {"pick": "b/2"}})
                self.assertEqual(json.loads(self.read("codeagent_config.local.json")),
                                 {"defaults": {"explore": "e/1"}})
                self.assert_one_error("Saved pick = b/2 (project), but re-reading")
                self.assertEqual(self.codeagent_state(app), before)
        self.run_async(body())

    def test_project_save_refresh_failure_latches(self) -> None:
        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                self.failing(app, "reload_project_config", "project_config.yaml")
                app.save_project_settings()
                await pilot.pause()
                self.assert_one_error("Project config saved, but re-reading",
                                      "project_config.yaml")
                self.assertTrue(app.config_mgr.needs_reload("project"))
                written = self.read("project_config.yaml")
                # Tmux writes the same file: same family, refused before writing.
                app.save_tmux_settings()
                self.assertEqual(self.read("project_config.yaml"), written)
                self.assertEqual(len(self.errors), 2)
                self.assertIn("Not saved", self.errors[1])
                # Other families are not latched.
                self.assertFalse(app.config_mgr.needs_reload("board"))
        self.run_async(body())

    def _import_latches_everything(self, import_fn) -> None:
        prev = settings_app.import_all_configs
        settings_app.import_all_configs = import_fn
        self.addCleanup(setattr, settings_app, "import_all_configs", prev)

        async def body():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                app._commit_imported = lambda *a: None
                app._handle_import({"path": "bundle"})
                await pilot.pause()
                self.assertTrue(app.is_running)
                self.assertTrue(any("Cannot reload configs" in e for e in self.errors),
                                self.errors)
                for family in ("codeagent", "board", "project", "profiles"):
                    self.assertTrue(app.config_mgr.needs_reload(family), family)
                files = {n: self.read(n) for n in (
                    "codeagent_config.json", "board_config.local.json",
                    "profiles/fast.yaml")}
                errors = len(self.errors)
                app._editing_layer = "project"
                app._handle_agent_pick({"key": "pick", "value": "x/1"})
                app.save_board_settings()
                app._save_profile("fast.yaml")
                self.assertEqual(len(self.errors), errors + 3)
                self.assertTrue(all("Not saved" in e for e in self.errors[errors:]))
                self.assertEqual(files, {n: self.read(n) for n in files})

                self.write("codeagent_config.json", {"defaults": {}})
                await pilot.press("r")
                await pilot.pause()
                for family in ("codeagent", "board", "project", "profiles"):
                    self.assertFalse(app.config_mgr.needs_reload(family), family)
                app._handle_agent_pick({"key": "pick", "value": "x/1"})
                self.assertEqual(json.loads(self.read("codeagent_config.json")),
                                 {"defaults": {"pick": "x/1"}})
        self.run_async(body())

    def test_import_reload_failure_latches_all_families(self) -> None:
        def fake_import(path, meta, **kw):
            self.write("codeagent_config.json", {"defaults": None})
            return ["codeagent_config.json"]
        self._import_latches_everything(fake_import)

    def test_partial_import_reload_failure_latches_all_families(self) -> None:
        def fake_import(path, meta, **kw):
            self.write("codeagent_config.json", {"defaults": None})
            raise config_utils.ConfigImportPartialError(
                ["codeagent_config.json"], OSError("disk full"))
        self._import_latches_everything(fake_import)


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

    def state(self, mgr):
        return copy.deepcopy((mgr.codeagent, mgr.codeagent_project, mgr.codeagent_local,
                              mgr.board, mgr.board_project, mgr.board_local))

    def test_mistyped_layer_rejected_and_state_kept(self) -> None:
        rows = [
            ("codeagent_config.json", {"defaults": None}, "'defaults' must be a JSON object, got null"),
            ("codeagent_config.json", {"defaults": "x"}, "got string"),
            ("codeagent_config.local.json", {"defaults": [1]}, "got array"),
            ("board_config.json", {"columns": {}}, "'columns' must be a JSON array"),
            ("board_config.json", {"columns": ["now"]}, "'columns[0]' must be a JSON object"),
            ("board_config.local.json", {"settings": []}, "'settings' must be a JSON object"),
        ]
        mgr = ConfigManager()
        for name, payload, fragment in rows:
            with self.subTest(file=name, payload=payload):
                before = self.state(mgr)
                path = self.root / META / name
                previous = path.read_bytes() if path.exists() else None
                self.write(name, payload)
                with self.assertRaises(settings_app.ConfigReadError) as cm:
                    mgr.load_all()
                self.assertEqual(cm.exception.path.name, name)
                self.assertIn(fragment, str(cm.exception))
                self.assertEqual(self.state(mgr), before)
                if previous is None:
                    path.unlink()
                else:
                    path.write_bytes(previous)

    def test_family_reloads_validate_and_keep_state(self) -> None:
        mgr = ConfigManager()
        cases = [
            ("codeagent_config.json", {"defaults": None}, mgr.reload_codeagent),
            ("codeagent_config.json", [], mgr.reload_codeagent),
            ("board_config.json", {"settings": None}, mgr.reload_board),
        ]
        for name, payload, reload in cases:
            with self.subTest(file=name, payload=payload):
                before = self.state(mgr)
                self.write(name, payload)
                with self.assertRaises(settings_app.ConfigReadError) as cm:
                    reload()
                self.assertEqual(cm.exception.path.name, name)
                self.assertEqual(self.state(mgr), before)
                (self.root / META / name).unlink()

    def test_unvalidated_keys_still_load(self) -> None:
        self.write("board_config.json", {"column_order": "x", "columns": [{"id": "now"}]})
        self.write("codeagent_config.json", {"defaults": {"pick": 5}})
        mgr = ConfigManager()
        self.assertEqual(mgr.board["column_order"], "x")
        self.assertEqual(mgr.codeagent["defaults"], {"pick": 5})

    def test_writer_backstop_refuses_latched_family(self) -> None:
        mgr = ConfigManager()
        board = self.root / META / "board_config.json"

        def boom():
            raise settings_app.ConfigReadError(board, "simulated failure")
        mgr.reload_board = boom
        with self.assertRaises(settings_app.ConfigReadError):
            mgr.refresh_after_write("board")
        del mgr.reload_board
        self.assertTrue(mgr.needs_reload("board"))
        self.assertFalse(board.exists())
        with self.assertRaises(settings_app.ConfigStaleError):
            mgr.save_board({"columns": [], "settings": {}})
        self.assertFalse(board.exists())
        # The latch is per family.
        mgr.save_codeagent({"defaults": {"pick": "a/1"}}, {})
        # A successful re-read releases it.
        mgr.reload_board()
        self.assertFalse(mgr.needs_reload("board"))
        mgr.save_board({"columns": [], "settings": {}})
        self.assertTrue(board.exists())

    def test_plain_writes_never_latch(self) -> None:
        mgr = ConfigManager()
        for _ in range(2):
            mgr.save_codeagent({"defaults": {"pick": "a/1"}}, {})
            mgr.save_board({"columns": [], "settings": {}})
            mgr.save_project_settings({"verify_build": "make"})
        self.assertFalse(any(mgr.needs_reload(f) for f in settings_app._FAMILIES))


if __name__ == "__main__":
    unittest.main(verbosity=2)
