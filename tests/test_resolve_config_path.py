"""Unit tests for config_utils.resolve_config_path (t1071_6).

resolve_config_path is the canonical seam for "a project_config.yaml value that
names a file on disk, with a fallback to the guide/template ait setup installed"
(learn_skill_authoring_guide for /aitask-learn-skill; the nested doc_update.guide
read by the docs_updated gate). These tests pin its contract: dotted-key walk,
PyYAML parser parity (quoted / commented values resolve cleanly — the cases a
hand-rolled grep would mangle), the readability check, and the seeded-default
fallback order.

Run: python3 tests/test_resolve_config_path.py
  or: bash tests/run_all_python_tests.sh
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".aitask-scripts", "lib"))
from config_utils import resolve_config_path


class ResolveConfigPathTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.meta = self.root / "aitasks" / "metadata"
        self.meta.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_config(self, text: str):
        (self.meta / "project_config.yaml").write_text(text, encoding="utf-8")

    def _touch(self, rel: str):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("guide\n", encoding="utf-8")
        return rel

    # -- flat key ---------------------------------------------------------
    def test_flat_key_configured_and_readable(self):
        rel = self._touch("custom/guide.md")
        self._write_config(f"learn_skill_authoring_guide: {rel}\n")
        self.assertEqual(
            resolve_config_path("learn_skill_authoring_guide", root=self.root), rel
        )

    def test_flat_key_double_quoted_value(self):
        # PyYAML strips the quotes — a grep '^key:' would keep them.
        rel = self._touch("q/guide.md")
        self._write_config(f'learn_skill_authoring_guide: "{rel}"\n')
        self.assertEqual(
            resolve_config_path("learn_skill_authoring_guide", root=self.root), rel
        )

    def test_flat_key_value_with_trailing_comment(self):
        rel = self._touch("c/guide.md")
        self._write_config(
            f"learn_skill_authoring_guide: {rel}   # project override\n"
        )
        self.assertEqual(
            resolve_config_path("learn_skill_authoring_guide", root=self.root), rel
        )

    # -- nested key (proves dotted-key support for the docs-gate migration)
    def test_nested_key_resolves(self):
        rel = self._touch("aitasks/metadata/doc_update_guide.md")
        self._write_config(f"doc_update:\n  guide: {rel}\n")
        self.assertEqual(
            resolve_config_path("doc_update.guide", root=self.root), rel
        )

    # -- fallback tiers ---------------------------------------------------
    def test_configured_missing_file_falls_to_default(self):
        default = self._touch("seeded/default.md")
        self._write_config("learn_skill_authoring_guide: does/not/exist.md\n")
        self.assertEqual(
            resolve_config_path(
                "learn_skill_authoring_guide", default, root=self.root
            ),
            default,
        )

    def test_unset_returns_default_when_present(self):
        default = self._touch("seeded/default.md")
        self._write_config("other: 1\n")
        self.assertEqual(
            resolve_config_path(
                "learn_skill_authoring_guide", default, root=self.root
            ),
            default,
        )

    def test_unset_and_default_absent_returns_none(self):
        self._write_config("other: 1\n")
        self.assertIsNone(
            resolve_config_path(
                "learn_skill_authoring_guide", "seeded/missing.md", root=self.root
            )
        )

    def test_no_config_file_returns_default_when_present(self):
        # No project_config.yaml at all -> load_yaml_config yields {}.
        default = self._touch("seeded/default.md")
        self.assertEqual(
            resolve_config_path("anything", default, root=self.root), default
        )

    def test_check_readable_false_skips_filesystem(self):
        self._write_config("learn_skill_authoring_guide: nowhere/on/disk.md\n")
        self.assertEqual(
            resolve_config_path(
                "learn_skill_authoring_guide",
                root=self.root,
                check_readable=False,
            ),
            "nowhere/on/disk.md",
        )

    def test_blank_value_treated_as_unset(self):
        default = self._touch("seeded/default.md")
        self._write_config("learn_skill_authoring_guide:   \n")
        self.assertEqual(
            resolve_config_path(
                "learn_skill_authoring_guide", default, root=self.root
            ),
            default,
        )


if __name__ == "__main__":
    unittest.main()
