"""Project Config values are stored as typed, not re-parsed as YAML (t1672).

`save_project_settings()` used to run every editor string through
`yaml.safe_load()`. Any command containing a colon-space therefore became a
**dict**::

    typed : sh -c "echo ADMISSION_REASON: no memory; exit 2"
    stored: {'sh -c "echo ADMISSION_REASON': 'no memory; exit 2"'}

which `safe_dump` wrote as a nested block. `aitask_resource_admission.sh` then
found no scalar, reported ``REASON:none_configured`` and exited 0 -- a silent
admit for a project that HAD configured a hook, inverting the feature's
fail-closed posture. And this key's own documented reason convention
(``ADMISSION_REASON: <text>``) makes a colon-space its normal case.

The rule that replaces it is asymmetric ON PURPOSE, and that asymmetry is what
these tests exist to hold in place:

* **flow form is ambiguous** with a shell command -- ``[ -f Makefile ]`` is a
  perfectly good ``verify_build`` and yet parses as ``['-f Makefile']`` -- so
  it counts as a list only when the text IS the canonical rendering of one;
* **block form is unambiguous** -- no shell command opens a line with ``- ``
  -- so a block edit is a list whatever its spelling: quoted items, trailing
  comments, re-indentation.

"Tidying" that into symmetry breaks real values in one direction or the other,
so both halves are pinned here, together with the two editor directions that
sit on either side of the save.

Like `tests/test_settings_learn_skill_guide.py`, this drives the REAL
user-facing path: it mounts the actual SettingsApp, sets ConfigRow values, and
calls the app's own `save_project_settings()`.

Run: python3 tests/test_settings_project_config_value_types.py
"""
from __future__ import annotations

import asyncio
import os
import subprocess
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
from settings_app import (  # noqa: E402
    PROJECT_CONFIG_SCHEMA,
    EditVerifyBuildScreen,
    SettingsApp,
    _format_yaml_block,
    _format_yaml_value,
    _list_if_canonical,
    _looks_like_block_list,
)

ADMISSION_KEY = "resource_admission_command"
BUILD_KEY = "verify_build"

# The command from the t1670 item-7 reproduction: a colon-space in the value,
# which is the NORMAL case for this key.
COLON_COMMAND = 'sh -c "echo ADMISSION_REASON: no memory; exit 2"'

_ADMISSION_HELPER = REPO_ROOT / ".aitask-scripts" / "aitask_resource_admission.sh"


class _Fixture(unittest.TestCase):
    def setUp(self) -> None:
        keybinding_registry._reset_for_tests()
        refresh_label_case()
        self._prev_cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "aitasks" / "metadata").mkdir(parents=True, exist_ok=True)
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

    def _find_row(self, app, key: str) -> ConfigRow:
        for row in app.query_one("#project_content").query(ConfigRow):
            if getattr(row, "row_key", None) == key:
                return row
        raise AssertionError(f"no ConfigRow for {key!r} in the Project Config tab")

    def _save_value(self, key: str, raw_value: str):
        """Set one row's raw_value, save through the app, return the reload."""
        result = {}

        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                self._find_row(app, key).raw_value = raw_value
                app.save_project_settings()
                await pilot.pause()
                result["data"] = load_yaml_config(self.cfg)

        self._run(runner())
        return result["data"].get(key)


class SchemaTypeTests(_Fixture):
    """Every project-config key declares a type, as TMUX_CONFIG_SCHEMA does."""

    def test_every_key_declares_a_type(self):
        for key, info in PROJECT_CONFIG_SCHEMA.items():
            self.assertIn(
                info.get("type"),
                ("string", "string_or_list", "mapping"),
                f"{key} declares no usable type",
            )

    def test_command_list_keys_are_string_or_list(self):
        for key in ("verify_build", "test_command", "lint_command"):
            self.assertEqual(PROJECT_CONFIG_SCHEMA[key]["type"], "string_or_list")

    def test_admission_hook_is_string_only(self):
        # It takes ONE command; the helper refuses every non-scalar shape.
        self.assertEqual(PROJECT_CONFIG_SCHEMA[ADMISSION_KEY]["type"], "string")


class TheReportedDefectTests(_Fixture):
    """t1670 item 7: the row saves back to project_config.yaml losslessly."""

    def test_colon_bearing_command_stays_a_string(self):
        stored = self._save_value(ADMISSION_KEY, COLON_COMMAND)
        self.assertIsInstance(stored, str, "the command was re-parsed as YAML")
        self.assertEqual(stored, COLON_COMMAND)

    def test_the_saved_hook_actually_runs(self):
        """Independent ground truth: drive the REAL helper over the saved file.

        A string-equality check alone would pass even if the value were stored
        in some shape the shell reader cannot see. What the defect actually
        cost was a silent admit, so assert on the verdict.
        """
        self._save_value(ADMISSION_KEY, COLON_COMMAND)
        proc = subprocess.run(
            [str(_ADMISSION_HELPER)],
            cwd=self.root, capture_output=True, text=True,
        )
        self.assertIn("REASON:refused", proc.stdout)
        self.assertIn("DETAIL:no memory", proc.stdout)
        self.assertEqual(proc.returncode, 1, "the hook ran and refused")
        self.assertNotIn("none_configured", proc.stdout)

    def test_colon_in_any_string_typed_key(self):
        stored = self._save_value("learn_skill_authoring_guide", "guides/a: b.md")
        self.assertEqual(stored, "guides/a: b.md")


class ListFormNegativeControlTests(_Fixture):
    """verify_build's list form must survive -- and nothing else may join it.

    The bracket-leading rows are what discriminate the canonicality rule from
    a naive ``startswith("[")`` or ``isinstance(parsed, list)`` rule. Without
    them a regression here is invisible.
    """

    def test_canonical_flow_list_is_stored_as_a_list(self):
        self.assertEqual(self._save_value(BUILD_KEY, "[a, b]"), ["a", "b"])

    def test_unicode_flow_list_is_stored_as_a_list(self):
        self.assertEqual(
            self._save_value(BUILD_KEY, "[café, naïve]"), ["café", "naïve"]
        )

    def test_genuine_one_item_list_still_works(self):
        self.assertEqual(self._save_value(BUILD_KEY, "[-f Makefile]"), ["-f Makefile"])

    def test_bracket_leading_commands_stay_exact_strings(self):
        for command in (
            "[ -f Makefile ] && make",        # ScannerError
            "[ -d build ] || mkdir build",    # ScannerError
            '[[ -n "$CI" ]] && pytest',       # ScannerError
            "[ -f Makefile ]",                # parses as a list, but not canonical
        ):
            with self.subTest(command=command):
                stored = self._save_value(BUILD_KEY, command)
                self.assertIsInstance(stored, str)
                self.assertEqual(stored, command)

    def test_colon_and_quoting_in_a_string_or_list_key(self):
        for command in ('make build: release', '"$HOME/with space/run"'):
            with self.subTest(command=command):
                self.assertEqual(self._save_value(BUILD_KEY, command), command)

    def test_mistyped_flow_list_saves_as_a_string_without_aborting(self):
        """The removed notify-guard: a bad row no longer aborts the whole tab.

        The old code raised on the parse failure and returned from the save,
        discarding every other row's edit with it.
        """
        result = {}

        async def runner():
            app = SettingsApp()
            async with app.run_test(size=(140, 45)) as pilot:
                await pilot.pause()
                self._find_row(app, BUILD_KEY).raw_value = "[a, b"
                self._find_row(app, "test_command").raw_value = "pytest -q"
                app.save_project_settings()
                await pilot.pause()
                result["data"] = load_yaml_config(self.cfg)

        self._run(runner())
        self.assertEqual(result["data"].get(BUILD_KEY), "[a, b")
        # The other row in the SAME save survived.
        self.assertEqual(result["data"].get("test_command"), "pytest -q")


class OpenAndSaveCycleTests(_Fixture):
    """A stored value opened in the editor and saved unchanged must not move.

    Two of the defects live only here: `_to_block_yaml` expanded any
    parse-as-list into block form (so `[ -f Makefile ]` became a list purely by
    being looked at), and `_to_compact_yaml` returned the YAML-DECODED scalar
    (so a quoted path lost its quotes). Neither is visible to a test that only
    exercises the save path.
    """

    CASES = [
        # (stored value, expected type after a no-op open+save)
        ("[ -f Makefile ]", str),
        ("[ -f Makefile ] && make", str),
        ('"$HOME/with space/run"', str),
        ("'pytest -k \"a b\"'", str),
        ("make build", str),
        ("[a, b]", list),
        ("[café, naïve]", list),
        ("[-f Makefile]", list),
    ]

    def _cycle(self, stored: str) -> str:
        """One editor open + save, as raw_value text."""
        return EditVerifyBuildScreen._to_compact_yaml(
            EditVerifyBuildScreen._to_block_yaml(stored)
        )

    def test_no_op_cycle_is_lossless_and_idempotent(self):
        for stored, expected_type in self.CASES:
            with self.subTest(stored=stored):
                once = self._cycle(stored)
                self.assertEqual(
                    once, stored, "an unedited open+save changed the value"
                )
                # A half-canonical form cannot hide behind a single pass.
                self.assertEqual(self._cycle(once), stored)
                saved = self._save_value(BUILD_KEY, once)
                self.assertIsInstance(saved, expected_type)
                if expected_type is str:
                    self.assertEqual(saved, stored)
                else:
                    self.assertEqual(_format_yaml_value(saved), stored)


class EditedBlockListTests(_Fixture):
    """A block-form edit is a list whatever its spelling.

    Gating block text on canonicality -- the obvious symmetric move, and wrong
    -- turns every ordinary hand edit into a scalar string, silently replacing
    a command list with a broken command.
    """

    def test_block_edits_persist_as_lists(self):
        cases = [
            ("- make build", ["make build"]),
            ('- "make build"', ["make build"]),                 # quoted item
            ("- make build  # release", ["make build"]),        # trailing comment
            ("- a\n-   b", ["a", "b"]),                         # re-indented
            ("- café", ["café"]),
            ('- pytest -k "a b"', ['pytest -k "a b"']),
            ("# note\n- make build", ["make build"]),           # leading comment
        ]
        for edited, expected in cases:
            with self.subTest(edited=edited):
                raw = EditVerifyBuildScreen._to_compact_yaml(edited)
                self.assertEqual(self._save_value(BUILD_KEY, raw), expected)

    def test_the_discriminating_negative(self):
        """The pair that IS the rule -- kept in one test so it cannot drift.

        A non-block edit that merely parses as a list stays a string, while the
        same text in block form is a list.
        """
        raw = EditVerifyBuildScreen._to_compact_yaml("[ -f Makefile ]")
        self.assertEqual(self._save_value(BUILD_KEY, raw), "[ -f Makefile ]")

        raw = EditVerifyBuildScreen._to_compact_yaml("- -f Makefile")
        self.assertEqual(self._save_value(BUILD_KEY, raw), ["-f Makefile"])


class SeamTests(_Fixture):
    """The predicate and the two renderers, asserted directly.

    A future third dumper, or a re-added scalar branch, fails here rather than
    silently in a user's config.
    """

    def test_block_yaml_does_not_expand_a_command(self):
        self.assertEqual(
            EditVerifyBuildScreen._to_block_yaml("[ -f Makefile ]"),
            "[ -f Makefile ]",
        )
        self.assertEqual(
            EditVerifyBuildScreen._to_block_yaml("[a, b]"), "- a\n- b"
        )

    def test_compact_yaml_keeps_shell_quoting(self):
        for text in ('"$HOME/with space/run"', "'pytest -k \"a b\"'", '"quoted"'):
            with self.subTest(text=text):
                self.assertEqual(EditVerifyBuildScreen._to_compact_yaml(text), text)

    def test_the_two_dumpers_agree_on_unicode(self):
        value = ["café", "naïve"]
        block = EditVerifyBuildScreen._to_block_yaml(_format_yaml_value(value))
        self.assertIn("café", block)
        self.assertNotIn("\\x", block)
        self.assertEqual(
            EditVerifyBuildScreen._to_compact_yaml(block), _format_yaml_value(value)
        )

    def test_list_if_canonical_discriminating_pair(self):
        self.assertIsNone(_list_if_canonical("[ -f Makefile ]", _format_yaml_value))
        self.assertEqual(
            _list_if_canonical("[-f Makefile]", _format_yaml_value), ["-f Makefile"]
        )
        # The block renderer is a renderer, not a gate -- but the predicate
        # works with either, so pin that it does.
        self.assertEqual(
            _list_if_canonical("- a\n- b", _format_yaml_block), ["a", "b"]
        )

    def test_looks_like_block_list(self):
        for text in ("- a", "-", "# c\n- a", "\n\n- a"):
            with self.subTest(text=text):
                self.assertTrue(_looks_like_block_list(text))
        for text in (
            "[ -f Makefile ]",
            "make build",
            "",
            # Decided by the FIRST content line, not by any line: a multi-line
            # scalar whose continuation opens with `- ` is not a block list.
            "make build \\\n  - foo",
        ):
            with self.subTest(text=text):
                self.assertFalse(_looks_like_block_list(text))


class WhitespaceContractTests(_Fixture):
    """"Verbatim" is scoped to interior content -- the edges are trimmed.

    `save_project_settings` trims each row before storing. That is deliberate
    and pre-existing; it is asserted here so the narrowed claim is executable
    rather than prose. If a later change decides to preserve the edges, this
    test is the thing that must be updated on purpose.
    """

    def test_surrounding_whitespace_is_trimmed(self):
        stored = self._save_value(ADMISSION_KEY, f"  {COLON_COMMAND}  ")
        self.assertEqual(stored, COLON_COMMAND)

    def test_interior_whitespace_is_untouched(self):
        command = 'sh -c  "echo  a: b"'
        self.assertEqual(self._save_value(ADMISSION_KEY, command), command)


if __name__ == "__main__":
    unittest.main()
