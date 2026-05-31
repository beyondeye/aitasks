"""Tests for the global ``shortcut_label_case`` setting (t848_10).

Covers the config-aware layer in ``shortcuts_mixin``:
  - ``_resolve_uppercase_key``: default/``upper``/garbage -> uppercase (True);
    ``preserve`` -> case-preserving (False); missing file -> default; malformed
    userconfig degrades fail-soft to the default.
  - cache + ``refresh_label_case`` invalidation.
  - ``render_label_cfg`` (literal-key callsite) honors the setting.
  - ``get_label`` (registry-resolved callsite) honors the setting end-to-end.

Run: python3 tests/test_shortcut_label_case.py
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from textual.binding import Binding  # noqa: E402

import keybinding_registry  # noqa: E402
import shortcuts_mixin  # noqa: E402
from shortcuts_mixin import (  # noqa: E402
    _resolve_uppercase_key,
    get_label,
    refresh_label_case,
    render_label_cfg,
)


class _Fixture(unittest.TestCase):
    """chdir into a temp workspace; reset registry + label-case cache state."""

    def setUp(self) -> None:
        keybinding_registry._reset_for_tests()
        refresh_label_case()
        self._prev_cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        self._meta = Path(self._tmp.name) / "aitasks" / "metadata"
        self._meta.mkdir(parents=True, exist_ok=True)
        os.chdir(self._tmp.name)

    def tearDown(self) -> None:
        os.chdir(self._prev_cwd)
        self._tmp.cleanup()
        keybinding_registry._reset_for_tests()
        refresh_label_case()

    def _write_userconfig(self, body: str) -> None:
        (self._meta / "userconfig.yaml").write_text(body, encoding="utf-8")
        refresh_label_case()


class ResolveUppercaseKeyTests(_Fixture):
    def test_missing_file_defaults_to_uppercase(self):
        # No userconfig.yaml written.
        self.assertTrue(_resolve_uppercase_key())

    def test_explicit_upper_is_uppercase(self):
        self._write_userconfig("shortcut_label_case: upper\n")
        self.assertTrue(_resolve_uppercase_key())

    def test_preserve_flips_to_false(self):
        self._write_userconfig("shortcut_label_case: preserve\n")
        self.assertFalse(_resolve_uppercase_key())

    def test_preserve_is_case_and_whitespace_insensitive(self):
        self._write_userconfig('shortcut_label_case: "  PRESERVE  "\n')
        self.assertFalse(_resolve_uppercase_key())

    def test_garbage_value_defaults_to_uppercase(self):
        self._write_userconfig("shortcut_label_case: banana\n")
        self.assertTrue(_resolve_uppercase_key())

    def test_unrelated_keys_only_defaults_to_uppercase(self):
        self._write_userconfig("email: me@example.com\n")
        self.assertTrue(_resolve_uppercase_key())

    def test_malformed_yaml_degrades_to_uppercase(self):
        # Unbalanced bracket -> yaml.YAMLError, must not propagate.
        self._write_userconfig("shortcut_label_case: [unclosed\n")
        self.assertTrue(_resolve_uppercase_key())


class CacheTests(_Fixture):
    def test_value_is_cached_until_refresh(self):
        self._write_userconfig("shortcut_label_case: preserve\n")
        self.assertFalse(_resolve_uppercase_key())
        # Change the file WITHOUT refreshing: cached value persists.
        (self._meta / "userconfig.yaml").write_text(
            "shortcut_label_case: upper\n", encoding="utf-8"
        )
        self.assertFalse(_resolve_uppercase_key())
        # After refresh the new value is read.
        refresh_label_case()
        self.assertTrue(_resolve_uppercase_key())


class RenderLabelCfgTests(_Fixture):
    def test_default_uppercases_matched_char(self):
        # No setting -> default uppercase.
        self.assertEqual(
            render_label_cfg("Export shortcuts", "x"), "E(X)port shortcuts"
        )

    def test_preserve_keeps_matched_char_case(self):
        self._write_userconfig("shortcut_label_case: preserve\n")
        self.assertEqual(
            render_label_cfg("Export shortcuts", "x"), "E(x)port shortcuts"
        )

    def test_preserve_leaves_no_match_prefix_uppercase(self):
        # 'd' is not in "Reset scope" -> prefix form, unaffected by preserve.
        self._write_userconfig("shortcut_label_case: preserve\n")
        self.assertEqual(
            render_label_cfg("Reset scope", "d"), "(D) Reset scope"
        )


class GetLabelTests(_Fixture):
    def _register(self) -> None:
        keybinding_registry.register_app_bindings(
            "test", [Binding("x", "do_export", "Export")]
        )

    def test_default_uppercases(self):
        self._register()
        self.assertEqual(
            get_label("test", "do_export", "Export shortcuts"),
            "E(X)port shortcuts",
        )

    def test_preserve_honored_end_to_end(self):
        self._register()
        self._write_userconfig("shortcut_label_case: preserve\n")
        self.assertEqual(
            get_label("test", "do_export", "Export shortcuts"),
            "E(x)port shortcuts",
        )


if __name__ == "__main__":
    unittest.main()
