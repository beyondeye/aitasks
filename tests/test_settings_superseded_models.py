"""Settings TUI Agent Defaults: superseded model defaults (t1921).

t1910 records which code-agent model supersedes which and offers the newer model
from the CLI. The Settings TUI marks such values and lets the user switch them.
What is pinned here, and why each case exists:

* a superseded value gets a note naming the offered target; a custom value
  gets none — and the note stays readable at 80 columns, where a suffix on the
  one-row ConfigRow is clipped (negative control in the same test);
* a switch writes ONLY the focused row's layer: a project switch goes through
  the commit seam, a per-user switch commits nothing and leaves the project
  file's bytes alone (even when the project file is dirty);
* the switch acts on fresh disk state: an op changed elsewhere is not
  switched, and an unrelated edit made elsewhere survives;
* the switch writes exactly the target the user was shown — a table change
  while the dialog is open refuses instead of writing a different model;
* unreadable config at any point reports, writes nothing it should not, and
  never raises out of the action;
* a user binding already on `o` keeps the key; the switch stays reachable
  through Enter;
* a malformed table / registry only produces warnings; the CLI's keep memory
  is shown, never written.

Run: python3 tests/test_settings_superseded_models.py
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "settings"))

from textual.widgets import Static  # noqa: E402

from agent_model_picker import AgentModelPickerScreen  # noqa: E402
import keybinding_registry  # noqa: E402
from profile_editor import ConfigRow  # noqa: E402
from shortcuts_mixin import refresh_label_case  # noqa: E402
import settings_app  # noqa: E402
from settings_app import SettingsApp, SupersededSwitchScreen  # noqa: E402

META = Path("aitasks") / "metadata"
PROJECT = META / "codeagent_config.json"
LOCAL = META / "codeagent_config.local.json"
REGISTRY = META / "models_claudecode.json"
SIZE = (140, 60)


def _table(by: str = "opus5_5") -> dict:
    return {"version": 1, "agents": {"claudecode": {
        "opus5": {"by": by, "source": "test"}}}}


def _registry(*names: str) -> dict:
    return {"models": [{"name": n, "cli_id": n} for n in names]}


def _write_json(path: Path, data, *, indent=2) -> None:
    path.write_text(json.dumps(data, indent=indent) + "\n", encoding="utf-8")


def _defaults(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))["defaults"]


class _Fixture(unittest.TestCase):
    def setUp(self) -> None:
        keybinding_registry._reset_for_tests()
        refresh_label_case()
        self._prev_cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory(prefix="ait_superseded_")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / META).mkdir(parents=True)
        os.chdir(self.root)
        self.addCleanup(os.chdir, self._prev_cwd)
        self.addCleanup(keybinding_registry._reset_for_tests)
        self.addCleanup(refresh_label_case)

        (self.root / META / "userconfig.yaml").write_text(
            "email: tester@example.com\n", encoding="utf-8")
        self.table = self.root / "supersessions.json"
        _write_json(self.table, _table())
        _write_json(self.root / REGISTRY, _registry("opus5", "opus5_5", "custom1"))
        _write_json(self.root / PROJECT, {"defaults": {
            "pick": "claudecode/opus5", "explain": "claudecode/custom1"}})

        prev_table = settings_app.SUPERSESSION_TABLE
        settings_app.SUPERSESSION_TABLE = str(self.table)
        self.addCleanup(setattr, settings_app, "SUPERSESSION_TABLE", prev_table)

        # The seam ConfigManager._commit calls: record instead of running git.
        self.commits: list = []
        prev_commit = settings_app.commit_metadata

        def fake_commit(paths, allow_new=False):
            self.commits.append(list(paths))
            return SimpleNamespace(status="committed", subject="test commit",
                                   detail="", allow_new=allow_new)

        settings_app.commit_metadata = fake_commit
        self.addCleanup(setattr, settings_app, "commit_metadata", prev_commit)
        self.notes: list = []

    # --- helpers ---------------------------------------------------------
    def make_app(self) -> SettingsApp:
        app = SettingsApp()
        app._run_projects_group = lambda *a: (0, "", "")
        notes = self.notes
        app.notify = lambda message, **kw: notes.append(
            (str(message), kw.get("severity", "information")))
        return app

    def _run(self, coro):
        return asyncio.run(coro)

    @staticmethod
    def row(app, layer: str, key: str) -> ConfigRow:
        prefix = "agent_proj_" if layer == "project" else "agent_user_"
        rows = [r for r in app.query(ConfigRow)
                if (r.id or "").startswith(prefix) and r.row_key == key]
        assert rows, f"no {layer} row for {key}"
        return rows[-1]

    @staticmethod
    def note_after(app, row: ConfigRow) -> str:
        """Text of the superseded note mounted right after `row`, or ''."""
        siblings = list(row.parent.children)
        nxt = siblings[siblings.index(row) + 1]
        if isinstance(nxt, Static) and nxt.has_class("superseded-note"):
            return str(nxt.render())
        return ""

    @staticmethod
    def screen_lines(app) -> list[str]:
        return [s.text for s in app.screen._compositor.render_strips()]

    async def press_on(self, app, pilot, layer: str, key: str, keys: str) -> None:
        self.row(app, layer, key).focus()
        await pilot.pause()
        await pilot.press(keys)
        await pilot.pause()


class RenderTests(_Fixture):
    def test_superseded_value_is_marked_and_custom_value_is_not(self):
        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                note = self.note_after(app, self.row(app, "project", "pick"))
                self.assertIn("superseded by claudecode/opus5_5", note)
                self.assertIn("o/Enter: switch", note)
                self.assertEqual(
                    self.note_after(app, self.row(app, "project", "explain")), "")
                self.assertEqual(
                    self.note_after(app, self.row(app, "user", "pick")), "")
        self._run(runner())

    def test_target_stays_visible_at_80_columns(self):
        _write_json(self.root / PROJECT, {"defaults": {
            "brainstorm-module_decomposer": "claudecode/opus5"}})

        async def runner():
            app = self.make_app()
            async with app.run_test(size=(80, 60)) as pilot:
                await pilot.pause()
                row = self.row(app, "project", "brainstorm-module_decomposer")
                siblings = list(row.parent.children)
                note = siblings[siblings.index(row) + 1]
                # Negative control: the same marker appended to a one-row
                # ConfigRow value (the rejected design) is clipped.
                ctrl = ConfigRow(
                    "brainstorm-module_decomposer",
                    "claudecode/opus5  ⚠ superseded by claudecode/opus5_5",
                    config_layer="project", row_key="negctrl", id="negctrl")
                await row.parent.mount(ctrl, before=row)
                await pilot.pause()
                lines = self.screen_lines(app)
                ctrl_text = lines[ctrl.region.y]
                self.assertIn("brainstorm-module_decomposer", ctrl_text)
                self.assertNotIn("claudecode/opus5_5", ctrl_text)
                note_text = " ".join(
                    lines[y] for y in range(note.region.y,
                                            note.region.y + note.region.height))
                self.assertIn("superseded by claudecode/opus5_5", note_text)
        self._run(runner())

    def test_malformed_table_only_warns(self):
        self.table.write_text("{not json", encoding="utf-8")

        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                texts = [str(s.render()) for s in app.query(".superseded-note")]
                self.assertTrue(any("supersession table unreadable" in t for t in texts))
                self.assertFalse(any("superseded by" in t for t in texts))
                self.assertEqual(
                    self.note_after(app, self.row(app, "project", "pick")), "")
        self._run(runner())

    def test_malformed_registry_only_warns(self):
        # A standard provider registry: ConfigManager json-loads this one at
        # startup too, so the whole Settings app must survive it.
        (self.root / REGISTRY).write_text("{oops", encoding="utf-8")

        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                texts = [str(s.render()) for s in app.query(".superseded-note")]
                self.assertTrue(any("cannot read models_claudecode.json" in t
                                    for t in texts))
                self.assertFalse(any("superseded by" in t for t in texts))
                self.assertEqual(
                    self.note_after(app, self.row(app, "project", "pick")), "")
                self.assertNotIn("claudecode", app.config_mgr.models)
        self._run(runner())

    def test_wrong_shape_registry_only_warns(self):
        # Valid JSON, wrong structure: Settings' own readers iterate `models`
        # and call .get() on each entry, so neither may reach them.
        for body, warned in (({"models": None}, True),
                             ({"models": [1, "x", {"name": "opus5"}]}, False)):
            with self.subTest(body=body):
                _write_json(self.root / REGISTRY, body)
                self.notes.clear()

                async def runner():
                    app = self.make_app()
                    async with app.run_test(size=SIZE) as pilot:
                        await pilot.pause()
                        texts = [str(s.render())
                                 for s in app.query(".superseded-note")]
                        self.assertEqual(
                            any("cannot read models_claudecode.json" in t
                                for t in texts), warned)
                        self.assertEqual(
                            self.note_after(app, self.row(app, "project", "pick")), "")
                        await pilot.press("m")  # the Models tab reads it too
                        await pilot.pause()
                        self.assertTrue(app.is_running)
                self._run(runner())

    def test_switch_dialog_buttons_fit_at_80_columns(self):
        async def runner():
            app = self.make_app()
            async with app.run_test(size=(80, 40)) as pilot:
                await pilot.pause()
                await self.press_on(app, pilot, "project", "pick", "enter")
                self.assertIsInstance(app.screen, SupersededSwitchScreen)
                dialog = app.screen.query_one("#ss_dialog")
                lines = self.screen_lines(app)
                labels = {"btn_ss_switch": "Switch to claudecode/opus5_5",
                          "btn_ss_pick": "Choose another model",
                          "btn_ss_cancel": "Cancel"}
                for bid, label in labels.items():
                    btn = app.screen.query_one(f"#{bid}")
                    self.assertTrue(dialog.region.contains_region(btn.region),
                                    f"{bid} {btn.region} outside {dialog.region}")
                    shown = " ".join(lines[y] for y in range(
                        btn.region.y, btn.region.y + btn.region.height))
                    self.assertIn(label, shown)
        self._run(runner())


class SwitchTests(_Fixture):
    def test_project_switch_writes_and_commits_only_the_project_layer(self):
        # Non-canonical formatting: any rewrite of the local file would show.
        local_bytes = b'{"defaults":{"explain":"claudecode/custom1"}}'
        (self.root / LOCAL).write_bytes(local_bytes)

        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                await self.press_on(app, pilot, "project", "pick", "o")
                self.assertEqual(_defaults(self.root / PROJECT)["pick"],
                                 "claudecode/opus5_5")
                self.assertEqual((self.root / LOCAL).read_bytes(), local_bytes)
                self.assertEqual(self.commits, [[str(PROJECT)]])
                self.assertEqual(
                    self.note_after(app, self.row(app, "project", "pick")), "")
                self.assertIn(("Switched pick (project) to claudecode/opus5_5",
                               "information"), self.notes)
        self._run(runner())

    def test_local_switch_touches_only_the_local_file_and_commits_nothing(self):
        _write_json(self.root / LOCAL, {"defaults": {"pick": "claudecode/opus5"}})
        # A dirty project file a local switch must neither rewrite nor commit.
        project_bytes = b'{"defaults": {"pick": "claudecode/custom1", "x": 1}}'
        (self.root / PROJECT).write_bytes(project_bytes)

        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                self.assertIn("superseded by claudecode/opus5_5",
                              self.note_after(app, self.row(app, "user", "pick")))
                await self.press_on(app, pilot, "user", "pick", "o")
                self.assertEqual(_defaults(self.root / LOCAL)["pick"],
                                 "claudecode/opus5_5")
                self.assertEqual((self.root / PROJECT).read_bytes(), project_bytes)
                self.assertEqual(self.commits, [])
        self._run(runner())

    def test_value_changed_elsewhere_is_not_switched(self):
        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                _write_json(self.root / PROJECT, {"defaults": {
                    "pick": "claudecode/custom1", "explain": "claudecode/custom1"}})
                await self.press_on(app, pilot, "project", "pick", "o")
                self.assertEqual(_defaults(self.root / PROJECT)["pick"],
                                 "claudecode/custom1")
                self.assertEqual(self.commits, [])
                self.assertTrue(any(sev == "warning" for _m, sev in self.notes))
        self._run(runner())

    def test_unrelated_edit_made_elsewhere_survives_the_switch(self):
        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                _write_json(self.root / PROJECT, {"defaults": {
                    "pick": "claudecode/opus5", "explain": "claudecode/opus5_5",
                    "qa": "claudecode/custom1"}})
                await self.press_on(app, pilot, "project", "pick", "o")
                self.assertEqual(_defaults(self.root / PROJECT), {
                    "pick": "claudecode/opus5_5", "explain": "claudecode/opus5_5",
                    "qa": "claudecode/custom1"})
        self._run(runner())

    def test_unmarked_and_inheriting_rows_change_nothing(self):
        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                before = (self.root / PROJECT).read_bytes()
                await self.press_on(app, pilot, "project", "explain", "o")
                await self.press_on(app, pilot, "user", "pick", "o")
                self.assertEqual((self.root / PROJECT).read_bytes(), before)
                self.assertFalse((self.root / LOCAL).exists())
                self.assertEqual(self.commits, [])
        self._run(runner())

    def test_write_failure_is_reported_and_does_not_close_settings(self):
        prev = settings_app.save_project_config

        def deny(path, data):
            raise PermissionError(13, "Permission denied", str(path))

        settings_app.save_project_config = deny
        self.addCleanup(setattr, settings_app, "save_project_config", prev)

        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                await self.press_on(app, pilot, "project", "pick", "o")
                self.assertTrue(app.is_running)
                self.assertEqual(_defaults(self.root / PROJECT)["pick"],
                                 "claudecode/opus5")
                self.assertEqual(self.commits, [])
                errors = [m for m, sev in self.notes if sev == "error"]
                self.assertEqual(len(errors), 1, self.notes)
                self.assertIn("Could not write", errors[0])
                self.assertIn("now shows what is on disk", errors[0])
                self.assertFalse(any(m.startswith("Switched") for m, _ in self.notes))
        self._run(runner())

    def test_write_failure_with_failed_refresh_claims_no_disk_state(self):
        _write_json(self.root / LOCAL, {"defaults": {}})
        prev = settings_app.save_project_config
        local = self.root / LOCAL

        def deny_and_corrupt(path, data):
            local.write_text("{broken", encoding="utf-8")
            raise PermissionError(13, "Permission denied", str(path))

        settings_app.save_project_config = deny_and_corrupt
        self.addCleanup(setattr, settings_app, "save_project_config", prev)

        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                await self.press_on(app, pilot, "project", "pick", "o")
                self.assertTrue(app.is_running)
                errors = [m for m, sev in self.notes if sev == "error"]
                self.assertEqual(len(errors), 1, self.notes)
                self.assertIn("Could not write", errors[0])
                self.assertIn("could not refresh", errors[0])
                self.assertIn("last config it could read", errors[0])
                self.assertNotIn("now shows what is on disk", errors[0])
                self.assertEqual(app.config_mgr.codeagent_local, {"defaults": {}})
        self._run(runner())

    def test_o_is_inert_on_other_tabs(self):
        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                self.row(app, "project", "pick").focus()
                await pilot.press("b")
                await pilot.pause()
                self.assertEqual(app.query_one("TabbedContent").active, "tab_board")
                await pilot.press("o")
                await pilot.pause()
                self.assertEqual(_defaults(self.root / PROJECT)["pick"],
                                 "claudecode/opus5")
        self._run(runner())


class ConfirmedOfferTests(_Fixture):
    def test_dialog_switch_refuses_when_the_target_changed_while_open(self):
        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                await self.press_on(app, pilot, "project", "pick", "enter")
                self.assertIsInstance(app.screen, SupersededSwitchScreen)
                self.assertEqual(app.screen.target, "claudecode/opus5_5")
                _write_json(self.table, _table("opus5_6"))
                _write_json(self.root / REGISTRY,
                            _registry("opus5", "opus5_5", "opus5_6", "custom1"))
                await pilot.click("#btn_ss_switch")
                await pilot.pause()
                self.assertEqual(_defaults(self.root / PROJECT)["pick"],
                                 "claudecode/opus5")
                self.assertTrue(any("opus5_6" in m and sev == "warning"
                                    for m, sev in self.notes))
                self.assertIn("superseded by claudecode/opus5_6",
                              self.note_after(app, self.row(app, "project", "pick")))
        self._run(runner())

    def test_o_refuses_when_the_target_changed_since_display(self):
        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                _write_json(self.table, _table("opus5_6"))
                _write_json(self.root / REGISTRY,
                            _registry("opus5", "opus5_5", "opus5_6", "custom1"))
                await self.press_on(app, pilot, "project", "pick", "o")
                self.assertEqual(_defaults(self.root / PROJECT)["pick"],
                                 "claudecode/opus5")
                self.assertEqual(self.commits, [])
        self._run(runner())

    def test_dialog_switch_pick_and_escape(self):
        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                await self.press_on(app, pilot, "project", "pick", "enter")
                await pilot.press("escape")
                await pilot.pause()
                self.assertNotIsInstance(app.screen, SupersededSwitchScreen)
                self.assertEqual(_defaults(self.root / PROJECT)["pick"],
                                 "claudecode/opus5")
                await self.press_on(app, pilot, "project", "pick", "enter")
                await pilot.click("#btn_ss_pick")
                await pilot.pause()
                self.assertIsInstance(app.screen, AgentModelPickerScreen)
                await pilot.press("escape")
                await pilot.pause()
                await self.press_on(app, pilot, "project", "pick", "enter")
                await pilot.click("#btn_ss_switch")
                await pilot.pause()
                self.assertEqual(_defaults(self.root / PROJECT)["pick"],
                                 "claudecode/opus5_5")
        self._run(runner())

    def test_plain_enter_on_unmarked_row_opens_the_picker(self):
        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                await self.press_on(app, pilot, "project", "explain", "enter")
                self.assertIsInstance(app.screen, AgentModelPickerScreen)
        self._run(runner())


class UnreadableConfigTests(_Fixture):
    def _assert_reports_without_writing(self, corrupt: Path, row_layer: str):
        if row_layer == "local":
            _write_json(self.root / LOCAL, {"defaults": {"pick": "claudecode/opus5"}})

        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                (self.root / corrupt).write_text("{broken", encoding="utf-8")
                snapshot = {p: (self.root / p).read_bytes()
                            for p in (PROJECT, LOCAL) if (self.root / p).exists()}
                await self.press_on(app, pilot, row_layer, "pick", "o")
                for p, data in snapshot.items():
                    self.assertEqual((self.root / p).read_bytes(), data)
                self.assertEqual(self.commits, [])
                self.assertTrue(any("nothing switched" in m and sev == "error"
                                    for m, sev in self.notes), self.notes)
                self.assertTrue(app.is_running)
        self._run(runner())

    def test_opposite_layer_malformed_after_display(self):
        _write_json(self.root / LOCAL, {"defaults": {}})
        self._assert_reports_without_writing(LOCAL, "project")

    def test_own_layer_malformed_after_display(self):
        self._assert_reports_without_writing(PROJECT, "project")

    def _wrap_writer(self, app, corrupt: Path):
        original = app.config_mgr.switch_codeagent_default
        reloads = []
        original_reload = app.config_mgr.reload_codeagent

        def spy_reload():
            reloads.append(1)
            return original_reload()

        def wrapped(*args):
            (self.root / corrupt).write_text("{broken", encoding="utf-8")
            reloads.clear()
            return original(*args)

        app.config_mgr.switch_codeagent_default = wrapped
        app.config_mgr.reload_codeagent = spy_reload
        return reloads

    def test_own_layer_malformed_before_the_writer_reads(self):
        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                reloads = self._wrap_writer(app, PROJECT)
                await self.press_on(app, pilot, "project", "pick", "o")
                self.assertEqual((self.root / PROJECT).read_text(), "{broken")
                self.assertEqual(self.commits, [])
                self.assertEqual(reloads, [])
                self.assertTrue(any("nothing switched" in m and sev == "error"
                                    for m, sev in self.notes), self.notes)
                self.assertTrue(app.is_running)
        self._run(runner())

    def test_opposite_layer_malformed_before_the_final_refresh(self):
        _write_json(self.root / LOCAL, {"defaults": {}})

        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                self._wrap_writer(app, LOCAL)
                await self.press_on(app, pilot, "project", "pick", "o")
                before = (dict(app.config_mgr.codeagent_project),
                          dict(app.config_mgr.codeagent_local))
                self.assertEqual(_defaults(self.root / PROJECT)["pick"],
                                 "claudecode/opus5_5")
                refresh_notes = [m for m, sev in self.notes
                                 if "could not refresh" in m]
                self.assertEqual(len(refresh_notes), 1)
                self.assertTrue(refresh_notes[0].startswith("Switched pick"))
                self.assertIn("last config it could read", refresh_notes[0])
                self.assertIn("press r", refresh_notes[0])
                # The failed refresh left the in-memory layers untouched.
                self.assertEqual(before, (app.config_mgr.codeagent_project,
                                          app.config_mgr.codeagent_local))
                self.assertEqual(app.config_mgr.codeagent_project["defaults"]["pick"],
                                 "claudecode/opus5")
                self.assertTrue(app.is_running)
        self._run(runner())

    def test_failed_refresh_after_switch_refuses_the_next_save(self):
        """t1945: memory is behind the switched file, so a later save built on
        it would put the superseded model back. It is refused until `r`."""
        _write_json(self.root / LOCAL, {"defaults": {}})

        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                self._wrap_writer(app, LOCAL)
                await self.press_on(app, pilot, "project", "pick", "o")
                self.assertTrue(any(m.startswith("Switched pick") and
                                    "could not refresh" in m
                                    for m, _sev in self.notes), self.notes)
                self.assertTrue(app.config_mgr.needs_reload("codeagent"))
                switched = (self.root / PROJECT).read_bytes()
                commits = len(self.commits)
                self.notes.clear()

                app._editing_layer = "project"
                app._handle_agent_pick({"key": "explain", "value": "claudecode/opus5_5"})
                self.assertEqual((self.root / PROJECT).read_bytes(), switched)
                self.assertEqual((self.root / LOCAL).read_text(), "{broken")
                self.assertEqual(len(self.commits), commits)
                self.assertEqual([sev for _m, sev in self.notes], ["error"])
                self.assertIn("Not saved", self.notes[0][0])

                # Fixed and reloaded: the latch is released, and the save keeps
                # the switch it would otherwise have undone.
                _write_json(self.root / LOCAL, {"defaults": {}})
                await pilot.press("r")
                await pilot.pause()
                self.assertFalse(app.config_mgr.needs_reload("codeagent"))
                app._handle_agent_pick({"key": "explain", "value": "claudecode/opus5_5"})
                self.assertEqual(_defaults(self.root / PROJECT), {
                    "pick": "claudecode/opus5_5", "explain": "claudecode/opus5_5"})
                self.assertTrue(app.is_running)
        self._run(runner())

    def test_failed_refresh_after_unwritten_switch_latches_nothing(self):
        """`changed` wrote nothing, so memory is not behind any write of ours."""
        _write_json(self.root / LOCAL, {"defaults": {}})

        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()

                def changed(*_args):
                    (self.root / LOCAL).write_text("{broken", encoding="utf-8")
                    return "changed", "claudecode/custom1"

                app.config_mgr.switch_codeagent_default = changed
                await self.press_on(app, pilot, "project", "pick", "o")
                self.assertTrue(any("changed on disk" in m and "could not refresh" in m
                                    for m, _sev in self.notes), self.notes)
                self.assertFalse(app.config_mgr.needs_reload("codeagent"))
        self._run(runner())


class ShortcutClashTests(_Fixture):
    def test_existing_user_binding_keeps_the_key_and_enter_still_switches(self):
        (self.root / META / "userconfig.yaml").write_text(
            "email: tester@example.com\n"
            "shortcuts:\n  settings:\n    switch_tab_board: o\n",
            encoding="utf-8")
        keybinding_registry.refresh()

        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                note = self.note_after(app, self.row(app, "project", "pick"))
                self.assertIn("Enter: switch", note)
                self.assertNotIn("o/Enter", note)
                await self.press_on(app, pilot, "project", "pick", "o")
                self.assertEqual(app.query_one("TabbedContent").active, "tab_board")
                self.assertEqual(_defaults(self.root / PROJECT)["pick"],
                                 "claudecode/opus5")
                await pilot.press("a")
                await pilot.pause()
                await self.press_on(app, pilot, "project", "pick", "enter")
                await pilot.click("#btn_ss_switch")
                await pilot.pause()
                self.assertEqual(_defaults(self.root / PROJECT)["pick"],
                                 "claudecode/opus5_5")
        self._run(runner())


class KeptMemoryTests(_Fixture):
    def test_kept_offer_is_shown_dimmed_and_the_memory_is_never_written(self):
        subprocess.run(["git", "init", "-q", "."], cwd=self.root, check=True,
                       capture_output=True)
        kept_file = self.root / ".git" / "ait-codeagent-supersession-kept.json"
        kept_bytes = json.dumps(
            {"project": {"claudecode/opus5": "claudecode/opus5_5"}}).encode()
        kept_file.write_bytes(kept_bytes)

        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                note = self.note_after(app, self.row(app, "project", "pick"))
                self.assertIn("(kept", note)
                await self.press_on(app, pilot, "project", "pick", "o")
                self.assertEqual(_defaults(self.root / PROJECT)["pick"],
                                 "claudecode/opus5_5")
                self.assertEqual(kept_file.read_bytes(), kept_bytes)
        self._run(runner())

    def test_git_discovery_runs_once_and_the_memory_is_reread(self):
        subprocess.run(["git", "init", "-q", "."], cwd=self.root, check=True,
                       capture_output=True)
        calls = []
        original = settings_app.ms.git_common_dir

        def counting(root):
            calls.append(root)
            return original(root)

        settings_app.ms.git_common_dir = counting
        self.addCleanup(setattr, settings_app.ms, "git_common_dir", original)

        async def runner():
            app = self.make_app()
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                self.assertNotIn("(kept",
                                 self.note_after(app, self.row(app, "project", "pick")))
                (self.root / ".git" / "ait-codeagent-supersession-kept.json").write_text(
                    json.dumps({"project": {"claudecode/opus5": "claudecode/opus5_5"}}))
                app._populate_agent_tab()
                await pilot.pause()
                self.assertIn("(kept",
                              self.note_after(app, self.row(app, "project", "pick")))
                await self.press_on(app, pilot, "project", "pick", "o")
                self.assertEqual(_defaults(self.root / PROJECT)["pick"],
                                 "claudecode/opus5_5")
                self.assertEqual(len(calls), 1)
        self._run(runner())


if __name__ == "__main__":
    unittest.main()
