"""Round-trip tests for the Settings TUI's `default_profiles` handling (t1219).

The reader (`aitask_skill_resolve_profile.sh`) accepts ANY key under
`default_profiles:`, while the Settings TUI only renders rows for
`VALID_PROFILE_SKILLS`. `save_project_settings()` used to rebuild the whole
block from those rows, so a key the schema did not know about was silently
discarded on the next save. These tests pin the preservation contract without
regressing the two existing ones (blanking a row clears its key; an empty map
removes the block entirely).

Like `tests/test_settings_learn_skill_guide.py`, this drives the REAL
user-facing path: it mounts the actual SettingsApp, edits Project Config tab
rows, and calls the app's own `save_project_settings()`.

Run: python3 tests/test_settings_default_profiles_unknown_keys.py
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
from textual.widgets import Label  # noqa: E402
from settings_app import VALID_PROFILE_SKILLS, SettingsApp  # noqa: E402

UNKNOWN = "someskill_not_in_schema"
KNOWN = "pick"


class _Fixture(unittest.TestCase):
    # A known key plus a key the schema does not recognize.
    CONFIG = (
        "codeagent_coauthor_domain: example.io\n"
        "default_profiles:\n"
        f"  {KNOWN}: fast\n"
        f"  {UNKNOWN}: fast\n"
    )

    def setUp(self) -> None:
        keybinding_registry._reset_for_tests()
        refresh_label_case()
        self._prev_cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "aitasks" / "metadata").mkdir(parents=True, exist_ok=True)
        self.cfg = self.root / "aitasks" / "metadata" / "project_config.yaml"
        self.cfg.write_text(self.CONFIG, encoding="utf-8")
        os.chdir(self.root)

    def tearDown(self) -> None:
        os.chdir(self._prev_cwd)
        self._tmp.cleanup()
        keybinding_registry._reset_for_tests()
        refresh_label_case()

    def _run(self, coro):
        return asyncio.run(coro)

    def _dp_rows(self, app) -> dict[str, ConfigRow]:
        """Map row_key -> ConfigRow for every rendered default_profiles row."""
        rows = {}
        for row in app.query_one("#project_content").query(ConfigRow):
            if row.id and row.id.startswith("project_dp_"):
                rows[row.row_key] = row
        return rows

    def _reload(self) -> dict:
        return load_yaml_config(self.cfg).get("default_profiles") or {}


class NegativeControlTests(_Fixture):
    def test_probe_key_really_is_unknown(self):
        # Guards the whole file: if someone adds this key to the allow-list,
        # every test below would pass for the wrong reason.
        self.assertNotIn(UNKNOWN, VALID_PROFILE_SKILLS)
        self.assertIn(KNOWN, VALID_PROFILE_SKILLS)


class SavePathTests(_Fixture):
    def test_unknown_key_survives_save(self):
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                # The unknown key has no rendered row (that is the trap)...
                self.assertNotIn(UNKNOWN, self._dp_rows(app))
                # ...but an untouched save must not drop it.
                app.save_project_settings()
                await pilot.pause()
                dp = self._reload()
                self.assertEqual(dp.get(UNKNOWN), "fast")
                self.assertEqual(dp.get(KNOWN), "fast")

        self._run(runner())

    def test_editing_a_known_row_preserves_unknown(self):
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                self._dp_rows(app)[KNOWN].raw_value = "default"
                app.save_project_settings()
                await pilot.pause()
                dp = self._reload()
                self.assertEqual(dp.get(KNOWN), "default")
                self.assertEqual(dp.get(UNKNOWN), "fast")

        self._run(runner())

    def test_clearing_a_known_row_still_removes_it(self):
        # Pre-seeding the map must not turn a blanked row into a no-op.
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                self._dp_rows(app)[KNOWN].raw_value = ""
                app.save_project_settings()
                await pilot.pause()
                dp = self._reload()
                self.assertNotIn(KNOWN, dp)
                self.assertEqual(dp.get(UNKNOWN), "fast")
                # The block itself survives — the unknown key still lives there.
                self.assertIn("default_profiles", load_yaml_config(self.cfg))

        self._run(runner())


class BlockRemovalTests(_Fixture):
    # No unknown key here: clearing every rendered row must empty the map.
    CONFIG = (
        "codeagent_coauthor_domain: example.io\n"
        "default_profiles:\n"
        f"  {KNOWN}: fast\n"
    )

    def test_all_keys_cleared_removes_the_block(self):
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                for row in self._dp_rows(app).values():
                    row.raw_value = ""
                app.save_project_settings()
                await pilot.pause()
                self.assertNotIn("default_profiles", load_yaml_config(self.cfg))

        self._run(runner())


class VisibilityTests(_Fixture):
    def test_unknown_key_is_visible_in_the_tab(self):
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                # render() -> Content; str() is the markup-stripped plain text.
                hints = [
                    str(lbl.render())
                    for lbl in app.query_one("#project_content").query(Label)
                ]
                self.assertTrue(
                    any(UNKNOWN in h for h in hints),
                    f"no Label surfaces the unrecognized key {UNKNOWN!r}",
                )

        self._run(runner())

    def test_no_hint_when_every_key_is_known(self):
        # Negative control for the hint: it must not appear unconditionally.
        self.cfg.write_text(
            "default_profiles:\n"
            f"  {KNOWN}: fast\n",
            encoding="utf-8",
        )

        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                # render() -> Content; str() is the markup-stripped plain text.
                hints = [
                    str(lbl.render())
                    for lbl in app.query_one("#project_content").query(Label)
                ]
                self.assertFalse(
                    any("unrecognized skill" in h for h in hints),
                    "the unrecognized-key hint rendered with no unknown keys",
                )

        self._run(runner())


class NonStringKeyTests(_Fixture):
    """YAML mapping keys are not necessarily strings: an unquoted `42:` parses
    to int, `true:` to bool. Such a key is valid YAML the profile resolver
    still reads, so the tab must render (and the save must preserve) it rather
    than raising while sorting/joining a mixed-type key set."""

    # Mixed int + str unknown keys — the case that breaks a naive sorted().
    CONFIG = (
        "default_profiles:\n"
        f"  {KNOWN}: fast\n"
        "  42: fast\n"
        f"  {UNKNOWN}: fast\n"
    )

    def test_mixed_type_keys_render_and_survive_save(self):
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                hints = [
                    str(lbl.render())
                    for lbl in app.query_one("#project_content").query(Label)
                ]
                self.assertTrue(
                    any("42" in h and UNKNOWN in h for h in hints),
                    "the hint must list both the numeric and the string key",
                )
                app.save_project_settings()
                await pilot.pause()
                dp = self._reload()
                # The key keeps its original YAML type — display normalization
                # must not rewrite the saved mapping.
                self.assertEqual(dp.get(42), "fast")
                self.assertEqual(dp.get(UNKNOWN), "fast")
                self.assertEqual(dp.get(KNOWN), "fast")

        self._run(runner())


class LoneNonStringKeyTests(_Fixture):
    """A single non-string unknown key sorts fine but still cannot be joined."""

    CONFIG = (
        "default_profiles:\n"
        f"  {KNOWN}: fast\n"
        "  42: fast\n"
    )

    def test_lone_numeric_key_renders_and_survives_save(self):
        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                hints = [
                    str(lbl.render())
                    for lbl in app.query_one("#project_content").query(Label)
                ]
                self.assertTrue(
                    any("unrecognized skill" in h and "42" in h for h in hints),
                    "the numeric key must be surfaced in the hint",
                )
                app.save_project_settings()
                await pilot.pause()
                self.assertEqual(self._reload().get(42), "fast")

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
