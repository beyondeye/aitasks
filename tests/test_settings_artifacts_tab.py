"""Tests for the Settings TUI Artifacts tab (t1231_2).

The tab edits the `artifacts:` block of project_config.yaml. Every rule about
what that block may contain lives in lib/artifact_registry.py, which the tab
reaches through one subprocess seam (`SettingsApp._run_artifact_registry`).
Most tests wrap the REAL seam in a recorder, so the registry's actual verdicts
are exercised; a few replace it with canned answers to pin exact argv.

Pinned here:
  - the backend selector is fed by `adapters` (offers gitbranch on a project
    with no artifacts: block — fails if `list` is used);
  - selecting gitbranch saves both default_backend and backends.gitbranch;
  - an invalid / reserved branch, a gitbranch default with no branch, a `dir`
    default with a missing or relative path, and a malformed nested section
    each produce ZERO writes (file byte-identical);
  - clearing drops emptied sections while unknown keys survive;
  - `k` switches to the tab;
  - values read from the YAML are text, never markup or argv-unsafe: a
    backend named "[/bold]" renders and is refused, a branch with a NUL byte is
    refused without crashing.

Run: python3 tests/test_settings_artifacts_tab.py
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

from textual.content import Content  # noqa: E402
from textual.widgets import Input, Label, TabbedContent  # noqa: E402

import keybinding_registry  # noqa: E402
from config_utils import load_yaml_config  # noqa: E402
from shortcuts_mixin import refresh_label_case  # noqa: E402
from settings_app import (  # noqa: E402
    ARTIFACTS_CONFIG_SCHEMA,
    EditArtifactBranchScreen,
    SettingsApp,
)

_CFG_REL = Path("aitasks") / "metadata" / "project_config.yaml"


def _recorder(app: SettingsApp, calls: list, canned: dict | None = None):
    """Wrap the real registry seam: record (config, args, config_existed) for
    every call, answer from `canned` (keyed by subcommand) when given, else run
    the real registry. Installed as an INSTANCE attribute."""
    real = SettingsApp._run_artifact_registry.__get__(app)

    def seam(*args, config=None):
        calls.append((config, args, config is None or os.path.exists(config)))
        if canned and args[0] in canned:
            return canned[args[0]]
        return real(*args, config=config)
    return seam


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
        self.cfg = self.root / _CFG_REL
        os.chdir(self.root)

    def tearDown(self) -> None:
        os.chdir(self._prev_cwd)
        self._tmp.cleanup()
        keybinding_registry._reset_for_tests()
        refresh_label_case()

    def write_cfg(self, text: str) -> bytes:
        self.cfg.write_text(text, encoding="utf-8")
        return self.cfg.read_bytes()

    def run_app(self, body, canned: dict | None = None,
                fetch_exclusion: tuple[int, str, str] | None = None):
        """Boot the app with a recording seam and a notify/save spy, then run
        `body(app, pilot, calls, notes, saves)`.

        The fetch-exclusion seam (t2099) is always stubbed — a save must never
        launch the real CLI from a test — and records its calls in
        `app._fx_calls`; `fetch_exclusion` is its canned (rc, out, err)."""
        async def runner():
            app = SettingsApp()
            calls: list = []
            notes: list = []
            saves: list = []
            app._run_artifact_registry = _recorder(app, calls, canned)
            fx_calls: list = []
            fx_result = fetch_exclusion or (0, "FETCH_EXCLUSION:UNCHANGED\n", "")

            def fx_seam():
                fx_calls.append(True)
                return fx_result
            app._run_fetch_exclusion = fx_seam
            app._fx_calls = fx_calls
            real_notify = app.notify

            def notify(message, **kw):
                # Pass through, so a toast whose text breaks markup still
                # crashes the app (and so this test) as it would for a user.
                notes.append((str(message), kw.get("severity", "information")))
                return real_notify(message, **kw)
            app.notify = notify
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                real_save = app.config_mgr.save_project_settings

                def spy(data):
                    saves.append(data)
                    return real_save(data)
                app.config_mgr.save_project_settings = spy
                await body(app, pilot, calls, notes, saves)
        asyncio.run(runner())

    @staticmethod
    async def select_backend(app, pilot, name: str) -> None:
        field, _row = app._artifacts_widgets()
        for _ in range(len(field.options)):
            if field.current_value == name:
                break
            field.cycle_next()
        await pilot.pause()
        assert field.current_value == name, field.options

    @staticmethod
    def set_branch(app, value: str) -> None:
        _field, row = app._artifacts_widgets()
        row.raw_value = value

    def errors(self, notes) -> list[str]:
        return [m for m, sev in notes if sev == "error"]


class SchemaTests(unittest.TestCase):
    def test_keys_have_summary_and_detail(self):
        self.assertEqual(set(ARTIFACTS_CONFIG_SCHEMA),
                         {"default_backend", "backends.gitbranch.branch"})
        for key, info in ARTIFACTS_CONFIG_SCHEMA.items():
            self.assertTrue(info.get("summary", "").strip(), key)
            self.assertTrue(info.get("detail", "").strip(), key)


class SelectorTests(_Fixture):
    def test_bootstrap_offers_gitbranch_without_artifacts_block(self):
        self.write_cfg("verify_build: make\n")

        async def body(app, pilot, calls, notes, saves):
            field, row = app._artifacts_widgets()
            self.assertIn("gitbranch", field.options)
            self.assertEqual(field.current_value, "local")
            self.assertEqual(row.raw_value, "")
            self.assertIn((None, ("adapters",), True), calls)
            self.assertNotIn("list", [c[1][0] for c in calls])
        self.run_app(body)

    def test_k_switches_to_artifacts_tab(self):
        self.write_cfg("verify_build: make\n")

        async def body(app, pilot, calls, notes, saves):
            await pilot.press("k")
            await pilot.pause()
            self.assertEqual(app.query_one(TabbedContent).active, "tab_artifacts")
        self.run_app(body)

    def test_adapters_failure_falls_back_and_reports(self):
        self.write_cfg("artifacts:\n  default_backend: gitbranch\n")

        async def body(app, pilot, calls, notes, saves):
            field, _row = app._artifacts_widgets()
            # The configured value is kept visible, never silently rewritten.
            self.assertEqual(field.current_value, "gitbranch")
            self.assertIn("local", field.options)
            self.assertTrue(any("Could not list artifact backends" in m
                                for m in self.errors(notes)))
        self.run_app(body, canned={"adapters": (1, "", "boom")})


class SaveTests(_Fixture):
    def test_selecting_gitbranch_writes_default_and_backend(self):
        self.write_cfg("verify_build: make\n")

        async def body(app, pilot, calls, notes, saves):
            await self.select_backend(app, pilot, "gitbranch")
            _field, row = app._artifacts_widgets()
            self.assertEqual(row.raw_value, "aitask-artifacts")  # prefilled
            app.save_artifacts_settings()
            await pilot.pause()
            self.assertEqual(len(saves), 1, notes)
            data = load_yaml_config(str(self.cfg))
            self.assertEqual(data["verify_build"], "make")
            self.assertEqual(data["artifacts"], {
                "default_backend": "gitbranch",
                "backends": {"gitbranch": {"branch": "aitask-artifacts"}},
            })
            # The candidate was checked by the registry against a temp copy,
            # in this order, and the temp copy is gone afterwards.
            checks = [(c[1], c[2]) for c in calls if c[0] is not None]
            self.assertEqual([a for a, _ in checks],
                             [("default-backend",), ("backend-env", "gitbranch")])
            self.assertTrue(all(existed for _, existed in checks))
            for c in calls:
                if c[0] is not None:
                    self.assertFalse(os.path.exists(c[0]))
        self.run_app(body)
        # The real registry accepts what was written.
        rc, out, _err = SettingsApp._run_artifact_registry(
            object(), "default-backend", config=str(self.cfg))
        self.assertEqual((rc, out.strip()), (0, "gitbranch"))

    def test_invalid_or_reserved_branch_zero_writes(self):
        for bad in ("bad name", "main", "a..b"):
            with self.subTest(branch=bad):
                before = self.write_cfg(
                    "artifacts:\n  backends:\n    gitbranch:\n"
                    "      branch: aitask-artifacts\n")

                async def body(app, pilot, calls, notes, saves, bad=bad):
                    self.set_branch(app, bad)
                    app.save_artifacts_settings()
                    await pilot.pause()
                    self.assertEqual(saves, [])
                    self.assertIn((None, ("validate-ref", bad), True), calls)
                    self.assertTrue(any(m.startswith("Not saved")
                                        for m in self.errors(notes)), notes)
                self.run_app(body)
                self.assertEqual(self.cfg.read_bytes(), before)

    def test_gitbranch_default_without_branch_refused(self):
        before = self.write_cfg(
            "artifacts:\n  default_backend: gitbranch\n  backends:\n"
            "    gitbranch:\n      branch: aitask-artifacts\n")

        async def body(app, pilot, calls, notes, saves):
            self.set_branch(app, "")
            app.save_artifacts_settings()
            await pilot.pause()
            self.assertEqual(saves, [])
            self.assertTrue(any("needs a branch" in m for m in self.errors(notes)))
        self.run_app(body)
        self.assertEqual(self.cfg.read_bytes(), before)

    def test_dir_default_validated_through_backend_env(self):
        cases = {
            "unregistered": "verify_build: make\n",
            "empty entry": "artifacts:\n  backends:\n    dir: {}\n",
            "relative path": ("artifacts:\n  backends:\n    dir:\n"
                              "      path: relative/store\n"),
        }
        for label, text in cases.items():
            with self.subTest(case=label):
                before = self.write_cfg(text)

                async def body(app, pilot, calls, notes, saves):
                    await self.select_backend(app, pilot, "dir")
                    app.save_artifacts_settings()
                    await pilot.pause()
                    self.assertEqual(saves, [])
                    errs = self.errors(notes)
                    self.assertTrue(any(m.startswith("Not saved") for m in errs),
                                    notes)
                    # The message names the real file, not the temp copy.
                    self.assertFalse(any("ait_artifacts_" in m for m in errs))
                self.run_app(body)
                self.assertEqual(self.cfg.read_bytes(), before)

        self.write_cfg("artifacts:\n  backends:\n    dir:\n"
                       "      path: /abs/store\n")

        async def body_ok(app, pilot, calls, notes, saves):
            await self.select_backend(app, pilot, "dir")
            app.save_artifacts_settings()
            await pilot.pause()
            self.assertEqual(len(saves), 1, notes)
            self.assertIn(("backend-env", "dir"),
                          [c[1] for c in calls if c[0] is not None])
        self.run_app(body_ok)
        data = load_yaml_config(str(self.cfg))
        self.assertEqual(data["artifacts"], {
            "backends": {"dir": {"path": "/abs/store"}},
            "default_backend": "dir",
        })

    def test_malformed_nested_sections_refused(self):
        cases = {
            "artifacts": "artifacts: oops\n",
            "artifacts.backends": "artifacts:\n  backends: oops\n",
            "artifacts.backends.gitbranch":
                "artifacts:\n  backends:\n    gitbranch: oops\n",
        }
        for path, text in cases.items():
            with self.subTest(path=path):
                before = self.write_cfg(text)

                async def body(app, pilot, calls, notes, saves, path=path):
                    hints = [str(lbl.render()) for lbl in
                             app.query_one("#artifacts_content").query(Label)]
                    self.assertTrue(any(f"{path} is a str" in h for h in hints),
                                    hints)
                    calls.clear()
                    self.set_branch(app, "aitask-artifacts")
                    app.save_artifacts_settings()
                    await pilot.pause()
                    self.assertEqual(saves, [])
                    self.assertEqual(calls, [])  # refused before any registry call
                    self.assertTrue(any(f"{path} is a str" in m
                                        for m in self.errors(notes)), notes)
                self.run_app(body)
                self.assertEqual(self.cfg.read_bytes(), before)

    def test_clear_drops_emptied_sections(self):
        self.write_cfg(
            "verify_build: make\nartifacts:\n  default_backend: gitbranch\n"
            "  backends:\n    gitbranch:\n      branch: aitask-artifacts\n")

        async def body(app, pilot, calls, notes, saves):
            await self.select_backend(app, pilot, "local")
            self.set_branch(app, "")
            app.save_artifacts_settings()
            await pilot.pause()
            self.assertEqual(len(saves), 1, notes)
        self.run_app(body)
        data = load_yaml_config(str(self.cfg))
        self.assertNotIn("artifacts", data)
        self.assertEqual(data["verify_build"], "make")

    def test_unknown_siblings_preserved(self):
        probes = ("extra_probe", "dir", "extra")
        for key in probes:  # tripwire: the probes really are unknown keys
            self.assertFalse(any(key in k.split(".")
                                 for k in ARTIFACTS_CONFIG_SCHEMA), key)
        self.write_cfg(
            "artifacts:\n  extra_probe: 1\n  backends:\n"
            "    dir:\n      path: /abs/store\n"
            "    gitbranch:\n      branch: old-branch\n      extra: keep-me\n")

        async def body(app, pilot, calls, notes, saves):
            self.set_branch(app, "new-branch")
            app.save_artifacts_settings()
            await pilot.pause()
            self.assertEqual(len(saves), 1, notes)
        self.run_app(body)
        data = load_yaml_config(str(self.cfg))
        self.assertEqual(data["artifacts"], {
            "extra_probe": 1,
            "backends": {
                "dir": {"path": "/abs/store"},
                "gitbranch": {"branch": "new-branch", "extra": "keep-me"},
            },
        })

    def test_clear_branch_keeps_unknown_key_in_entry(self):
        self.write_cfg(
            "artifacts:\n  default_backend: gitbranch\n  backends:\n"
            "    gitbranch:\n      branch: aitask-artifacts\n"
            "      extra: keep-me\n")

        async def body(app, pilot, calls, notes, saves):
            await self.select_backend(app, pilot, "local")
            self.set_branch(app, "")
            app.save_artifacts_settings()
            await pilot.pause()
            self.assertEqual(len(saves), 1, notes)
            # (The fixture is not a git repo, so a commit notice is expected.)
            self.assertFalse(any(m.startswith("Not saved")
                                 for m in self.errors(notes)), notes)
        self.run_app(body)
        data = load_yaml_config(str(self.cfg))
        self.assertEqual(data["artifacts"],
                         {"backends": {"gitbranch": {"extra": "keep-me"}}})

    def test_branch_change_warns_with_migrate_command(self):
        self.write_cfg("artifacts:\n  backends:\n    gitbranch:\n"
                       "      branch: old-branch\n")

        async def body(app, pilot, calls, notes, saves):
            self.set_branch(app, "new-branch")
            app.save_artifacts_settings()
            await pilot.pause()
            warnings = [m for m, sev in notes if sev == "warning"]
            self.assertTrue(any(
                "ait artifact gitbranch-migrate --from old-branch --to new-branch"
                in m for m in warnings), notes)
        self.run_app(body)


class FetchExclusionTests(_Fixture):
    """t2099: saving a gitbranch branch re-applies the routine-fetch exclusion."""

    def test_save_with_branch_applies_exclusion(self):
        self.write_cfg("artifacts:\n  backends:\n    gitbranch:\n"
                       "      branch: old-branch\n")

        async def body(app, pilot, calls, notes, saves):
            self.set_branch(app, "new-branch")
            app.save_artifacts_settings()
            await pilot.pause()
            self.assertEqual(len(saves), 1, notes)
            self.assertEqual(len(app._fx_calls), 1)
        self.run_app(body)

    def test_changed_exclusion_is_reported(self):
        self.write_cfg("artifacts:\n  backends:\n    gitbranch:\n"
                       "      branch: old-branch\n")

        async def body(app, pilot, calls, notes, saves):
            self.set_branch(app, "new-branch")
            app.save_artifacts_settings()
            await pilot.pause()
            self.assertTrue(any("Routine fetches now skip" in m for m, _ in notes), notes)
        self.run_app(body, fetch_exclusion=(
            0, "EXCLUDED:origin:new-branch\nFETCH_EXCLUSION:CHANGED\n", ""))

    def test_failed_exclusion_warns_and_keeps_the_save(self):
        self.write_cfg("artifacts:\n  backends:\n    gitbranch:\n"
                       "      branch: old-branch\n")

        async def body(app, pilot, calls, notes, saves):
            self.set_branch(app, "new-branch")
            app.save_artifacts_settings()
            await pilot.pause()
            self.assertEqual(len(saves), 1, notes)
            warnings = [m for m, sev in notes if sev == "warning"]
            self.assertTrue(any(
                "not updated" in m and "[x] lock busy" in m
                and "ait artifact fetch-exclusion apply" in m
                for m in warnings), notes)
            # Advisory only: the exclusion never turns into an error toast.
            self.assertFalse(any("exclusion" in m for m in self.errors(notes)), notes)
        # The stderr carries markup-like text: it must render literally.
        self.run_app(body, fetch_exclusion=(1, "FETCH_EXCLUSION:BUSY\n", "[x] lock busy\n"))

    def test_save_without_gitbranch_skips_exclusion(self):
        self.write_cfg("verify_build: make\n")

        async def body(app, pilot, calls, notes, saves):
            app.save_artifacts_settings()
            await pilot.pause()
            self.assertEqual(app._fx_calls, [])
        self.run_app(body)

    def test_real_seam_targets_the_artifact_cli(self):
        from settings_app import ARTIFACT_CLI
        self.assertEqual(ARTIFACT_CLI.name, "aitask_artifact.sh")
        self.assertTrue(os.access(ARTIFACT_CLI, os.X_OK), ARTIFACT_CLI)


class HostileValueTests(_Fixture):
    def test_markup_like_default_backend_renders_and_is_refused(self):
        before = self.write_cfg('artifacts:\n  default_backend: "[/bold]"\n')

        async def body(app, pilot, calls, notes, saves):
            await pilot.press("k")
            await pilot.pause()
            field, _row = app._artifacts_widgets()
            self.assertEqual(field.current_value, "[/bold]")  # raw, not escaped
            self.assertIn("[/bold]", str(field.render()).replace("\\", ""))
            await pilot.click(f"#btn_artifacts_save_{app._artifacts_tab_rc}")
            await pilot.pause()
            self.assertEqual(saves, [])
            self.assertTrue(any("[/bold]" in m for m in self.errors(notes)),
                            notes)
        self.run_app(body)
        self.assertEqual(self.cfg.read_bytes(), before)

    def test_refusal_toast_shows_rejected_value_literally(self):
        # A well-formed tag: unescaped, the toast would render a bold "x" and
        # hide the value the user has to go and fix.
        self.write_cfg('artifacts:\n  default_backend: "[b]x[/b]"\n')

        async def body(app, pilot, calls, notes, saves):
            app.save_artifacts_settings()
            await pilot.pause()
            self.assertEqual(saves, [])
            # What the toast shows: the message as Textual's markup parser
            # renders it.
            shown = [Content.from_markup(m).plain for m in self.errors(notes)]
            self.assertTrue(any("[b]x[/b]" in t for t in shown), shown)
        self.run_app(body)

    def test_nul_in_yaml_branch_refused_without_crash(self):
        before = self.write_cfg('artifacts:\n  backends:\n    gitbranch:\n'
                                '      branch: "bad\\0branch"\n')

        async def body(app, pilot, calls, notes, saves):
            await pilot.press("k")
            await pilot.pause()
            _field, row = app._artifacts_widgets()
            self.assertEqual(row.raw_value, "bad\0branch")
            await pilot.click(f"#btn_artifacts_save_{app._artifacts_tab_rc}")
            await pilot.pause()
            self.assertEqual(saves, [])
            self.assertIn((None, ("validate-ref", "bad\0branch"), True), calls)
            self.assertTrue(any("cannot run the artifact registry" in m
                                for m in self.errors(notes)), notes)
        self.run_app(body)
        self.assertEqual(self.cfg.read_bytes(), before)


class EditModalTests(_Fixture):
    def test_rejected_branch_keeps_modal_open(self):
        self.write_cfg("verify_build: make\n")

        async def body(app, pilot, calls, notes, saves):
            await pilot.press("k")
            await pilot.pause()
            _field, row = app._artifacts_widgets()
            row.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            self.assertIsInstance(app.screen, EditArtifactBranchScreen)
            app.screen.query_one("#edit_branch_input", Input).value = "main"
            await pilot.press("enter")
            await pilot.pause()
            self.assertIsInstance(app.screen, EditArtifactBranchScreen)
            err = str(app.screen.query_one("#edit_branch_error", Label).render())
            self.assertIn("reserved", err)
            self.assertIn((None, ("validate-ref", "main"), True), calls)
            self.assertEqual(row.raw_value, "")

            app.screen.query_one("#edit_branch_input", Input).value = "my-store"
            await pilot.press("enter")
            await pilot.pause()
            self.assertNotIsInstance(app.screen, EditArtifactBranchScreen)
            self.assertEqual(row.raw_value, "my-store")
            self.assertEqual(saves, [])  # the pane only; nothing until Save
        self.run_app(body)


if __name__ == "__main__":
    unittest.main()
