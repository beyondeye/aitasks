"""End-to-end for the board settings dialog: `O` -> Save -> disk + notification.

The gap this closes (t1480). `TaskManager.auto_refresh_minutes` used to carry a
setter with **zero callers** — the dialog result is applied through
`self.manager.settings.update(result)` instead, because `SettingsScreen`
dismisses with several keys at once (`auto_refresh_minutes` AND
`sync_on_refresh`) and only one of them has a property. t1480 deleted the
setter. Deleting a write path is only safe if the *surviving* one is proven, and
nothing drove this dialog before: `tests/test_board_persistence_seam.py` pins
`save_settings()` at the manager layer, which says nothing about whether the
dialog ever reaches it.

So this module drives the REAL `KanbanApp` through the real modal — keypress to
persisted bytes to user-visible notification — rather than leaving that as a
manual smoke test against the user's own `board_config.local.json`. The fixture
tree is a temp directory, so no user state is touched.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_board_settings_dialog.py -v
"""

from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402


class BoardSettingsDialogTests(bf.FixtureBoardTestBase, bf.PristineTreeMixin,
                               unittest.TestCase):
    """`PristineTreeMixin` matters here: these tests persist settings, and a
    leaked `board_config.local.json` would make the next one boot with the
    previous test's value and assert vacuously."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.KanbanApp = cls.ab.KanbanApp
        cls.CycleField = cls.ab.CycleField
        cls.SettingsScreen = cls.ab.SettingsScreen
        cls._snapshot_pristine()

    def _run(self, coro):
        return asyncio.run(coro)

    @property
    def local_path(self) -> Path:
        return self.tasks_dir / "metadata" / "board_config.local.json"

    def persisted(self) -> dict:
        return json.loads(self.local_path.read_text(encoding="utf-8"))["settings"]

    def _capture_notifications(self, app):
        """Record `notify` calls, calling THROUGH — a stub would suppress the
        real notification and leave the assertion proving nothing."""
        seen: list[str] = []
        original = app.notify

        def spy(message, **kwargs):
            seen.append(str(message))
            return original(message, **kwargs)

        app.notify = spy
        return seen

    async def _settle(self, pilot, times=3):
        for _ in range(times):
            await pilot.pause()

    async def _open_settings(self, app, pilot):
        await self._settle(pilot)
        await pilot.press("O")
        await self._settle(pilot)
        self.assertIsInstance(app.screen, self.SettingsScreen,
                              "`O` must open the settings modal")
        return app.screen

    def test_fixture_facts(self):
        """Preconditions: the fixture starts at 0 minutes, and the dialog reads
        that starting value through the (surviving) getter."""

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                screen = await self._open_settings(app, pilot)
                field = screen.query_one("#cf_auto_refresh", self.CycleField)
                self.assertEqual(app.manager.auto_refresh_minutes, 0)
                self.assertEqual(field.current_value, "0",
                                 "the dialog seeds itself from the getter")
                self.assertEqual(self.persisted().get("auto_refresh_minutes"), 0)

        self._run(go())

    def test_saving_the_dialog_persists_and_notifies(self):
        """The whole surviving write path, end to end.

        Asserts all three effects, because each can fail on its own: the
        in-memory settings dict, the bytes on disk (`save_settings` ->
        `_write_user_layer`), and the user-visible notification.
        """

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                notes = self._capture_notifications(app)
                screen = await self._open_settings(app, pilot)
                field = screen.query_one("#cf_auto_refresh", self.CycleField)
                field.cycle_next()                       # "0" -> "1"
                await self._settle(pilot)
                self.assertEqual(field.current_value, "1", "control: the field moved")

                await pilot.click("#btn_settings_save")
                await self._settle(pilot)

                self.assertNotIsInstance(app.screen, self.SettingsScreen,
                                         "Save dismisses the modal")
                self.assertEqual(app.manager.auto_refresh_minutes, 1)
                self.assertEqual(self.persisted()["auto_refresh_minutes"], 1)
                self.assertIn("Auto-refresh: 1min", notes)

        self._run(go())

    def test_the_other_dialog_key_rides_along(self):
        """`sync_on_refresh` has no property — it is exactly the key a per-key
        setter could not have carried, which is why `settings.update()` is the
        write path and the setter was deleted rather than wired up."""

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                screen = await self._open_settings(app, pilot)
                sync = screen.query_one("#cf_sync_on_refresh", self.CycleField)
                self.assertEqual(sync.current_value, "no", "control: starts off")
                sync.cycle_next()                        # "no" -> "yes"
                await self._settle(pilot)

                await pilot.click("#btn_settings_save")
                await self._settle(pilot)

                self.assertIs(self.persisted()["sync_on_refresh"], True)
                self.assertEqual(self.persisted()["auto_refresh_minutes"], 0,
                                 "…and the untouched key kept its value")

        self._run(go())

    def test_cancel_writes_nothing(self):
        """Without this, the tests above could pass on a board that persists on
        every dismissal rather than on Save."""

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                before = self.local_path.read_bytes()
                screen = await self._open_settings(app, pilot)
                screen.query_one("#cf_auto_refresh", self.CycleField).cycle_next()
                await self._settle(pilot)

                await pilot.press("escape")
                await self._settle(pilot)

                self.assertNotIsInstance(app.screen, self.SettingsScreen)
                self.assertEqual(self.local_path.read_bytes(), before)
                self.assertEqual(app.manager.auto_refresh_minutes, 0)

        self._run(go())


if __name__ == "__main__":
    unittest.main()
