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
* the suffixed add-new button still opens the New Profile dialog.

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

import keybinding_registry  # noqa: E402
from shortcuts_mixin import refresh_label_case  # noqa: E402
import settings_app  # noqa: E402
from settings_app import NewProfileScreen, SettingsApp  # noqa: E402

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

    def make_app(self) -> SettingsApp:
        app = SettingsApp()
        app._run_projects_group = lambda *a: (0, "", "")
        notes = self.notes
        app.notify = lambda message, **kw: notes.append(str(message))
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
