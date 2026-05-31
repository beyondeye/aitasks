"""Tests for shortcuts export/import integration in config_utils (t848_5).

Covers:
  - export_all_configs(include_shortcuts=True) adds ONLY the `shortcuts:`
    subtree as a top-level bundle member (never the raw userconfig.yaml — no
    email leak), and bumps file_count.
  - export with no `shortcuts:` present adds no `shortcuts` bundle key.
  - import_all_configs deep-merges the shortcuts member into userconfig.yaml,
    preserving email/last_used_labels and other scopes.
  - import respects the selection: "shortcuts" excluded from selected_files
    leaves userconfig untouched.

Run: bash tests/run_all_python_tests.sh
  or: python3 tests/test_config_utils_shortcuts.py
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".aitask-scripts", "lib"))
from config_utils import (  # noqa: E402
    export_all_configs,
    import_all_configs,
    load_yaml_config,
    save_yaml_config,
)


class _Fixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.meta = Path(self._tmp.name) / "metadata"
        self.meta.mkdir(parents=True)
        self.bundle_path = Path(self._tmp.name) / "exp.aitcfg.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_userconfig(self, data: dict) -> None:
        save_yaml_config(self.meta / "userconfig.yaml", data)


class ExportShortcutsTests(_Fixture):
    def test_shortcuts_only_bundle_excludes_files_and_email(self):
        self._write_userconfig({
            "email": "me@example.com",
            "last_used_labels": ["x"],
            "shortcuts": {"board": {"pick": "o"}, "monitor": {"refresh": "g"}},
        })
        bundle = export_all_configs(
            self.bundle_path, self.meta, patterns=[], include_shortcuts=True,
        )
        self.assertEqual(bundle["files"], {})
        self.assertEqual(
            bundle["shortcuts"],
            {"board": {"pick": "o"}, "monitor": {"refresh": "g"}},
        )
        self.assertEqual(bundle["_export_meta"]["file_count"], 1)
        # Email must never appear anywhere in the serialized bundle.
        self.assertNotIn("me@example.com", json.dumps(bundle))

    def test_include_shortcuts_false_omits_member(self):
        self._write_userconfig({"email": "me@example.com",
                                "shortcuts": {"board": {"pick": "o"}}})
        bundle = export_all_configs(
            self.bundle_path, self.meta, patterns=[], include_shortcuts=False,
        )
        self.assertNotIn("shortcuts", bundle)

    def test_no_shortcuts_present_adds_no_member(self):
        self._write_userconfig({"email": "me@example.com"})
        bundle = export_all_configs(
            self.bundle_path, self.meta, patterns=[], include_shortcuts=True,
        )
        self.assertNotIn("shortcuts", bundle)
        self.assertEqual(bundle["_export_meta"]["file_count"], 0)


class ImportShortcutsTests(_Fixture):
    def _make_bundle(self, shortcuts: dict) -> Path:
        bundle = {
            "_export_meta": {"version": 1, "exported_at": "x", "file_count": 1},
            "files": {},
            "shortcuts": shortcuts,
        }
        self.bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
        return self.bundle_path

    def test_deep_merge_preserves_local_email_and_labels(self):
        self._write_userconfig({
            "email": "LOCAL@keep.me",
            "last_used_labels": ["y"],
            "shortcuts": {"board": {"close": "q"}},
        })
        self._make_bundle({"board": {"pick": "o"}, "monitor": {"refresh": "g"}})
        written = import_all_configs(
            self.bundle_path, self.meta, overwrite=True,
            selected_files=["shortcuts"],
        )
        self.assertIn("shortcuts", written)
        merged = load_yaml_config(self.meta / "userconfig.yaml")
        self.assertEqual(merged["email"], "LOCAL@keep.me")
        self.assertEqual(merged["last_used_labels"], ["y"])
        # board scope merged (close kept, pick added); monitor scope added.
        self.assertEqual(merged["shortcuts"]["board"], {"close": "q", "pick": "o"})
        self.assertEqual(merged["shortcuts"]["monitor"], {"refresh": "g"})

    def test_merge_when_no_selection_given(self):
        self._write_userconfig({"email": "a@b.c"})
        self._make_bundle({"board": {"pick": "o"}})
        written = import_all_configs(
            self.bundle_path, self.meta, overwrite=True, selected_files=None,
        )
        self.assertIn("shortcuts", written)
        merged = load_yaml_config(self.meta / "userconfig.yaml")
        self.assertEqual(merged["shortcuts"]["board"]["pick"], "o")
        self.assertEqual(merged["email"], "a@b.c")

    def test_shortcuts_excluded_from_selection_is_not_merged(self):
        self._write_userconfig({"email": "a@b.c"})
        self._make_bundle({"board": {"pick": "o"}})
        written = import_all_configs(
            self.bundle_path, self.meta, overwrite=True,
            selected_files=["board_config.json"],  # shortcuts not selected
        )
        self.assertNotIn("shortcuts", written)
        merged = load_yaml_config(self.meta / "userconfig.yaml")
        self.assertNotIn("shortcuts", merged)


if __name__ == "__main__":
    unittest.main()
