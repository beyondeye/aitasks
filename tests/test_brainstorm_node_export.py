"""Tests for NodeDetailModal export helpers + ExportNodeDetailModal smoke (t753).

Covers the pure logic introduced for the brainstorm dashboard's `Shift+E`
export shortcut: tab-scoped binding visibility, directory validation, and
the actual file-writing helper. The interactive modal flow itself is verified
manually per the plan's verification section.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from brainstorm.brainstorm_app import (  # noqa: E402
    ExportNodeDetailModal,
    _export_filename,
    _open_node_detail_visible,
    _validate_export_dir,
    _write_node_exports,
)


class OpenNodeDetailVisibleTests(unittest.TestCase):
    def test_visible_only_on_dashboard_with_noderow(self):
        self.assertTrue(_open_node_detail_visible("tab_dashboard", True))

    def test_hidden_when_focus_is_not_noderow(self):
        self.assertFalse(_open_node_detail_visible("tab_dashboard", False))

    def test_hidden_on_other_tabs_regardless_of_focus(self):
        for tab in ("tab_proposal", "tab_plan", "tab_compare", "tab_status", ""):
            self.assertFalse(_open_node_detail_visible(tab, True))
            self.assertFalse(_open_node_detail_visible(tab, False))


class ExportFilenameTests(unittest.TestCase):
    def test_proposal_filename(self):
        self.assertEqual(
            _export_filename("753", "init_001", "proposal"),
            "brainstorm_t753_init_001_proposal.md",
        )

    def test_plan_filename(self):
        self.assertEqual(
            _export_filename("753", "init_001", "plan"),
            "brainstorm_t753_init_001_plan.md",
        )

    def test_alphanumeric_task_num(self):
        self.assertEqual(
            _export_filename("42_3", "op1_002", "plan"),
            "brainstorm_t42_3_op1_002_plan.md",
        )


class ValidateExportDirTests(unittest.TestCase):
    def test_empty_string_rejected(self):
        path, err = _validate_export_dir("")
        self.assertIsNone(path)
        self.assertEqual(err, "Output directory is required")

    def test_whitespace_rejected(self):
        path, err = _validate_export_dir("   ")
        self.assertIsNone(path)
        self.assertEqual(err, "Output directory is required")

    def test_existing_dir_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            path, err = _validate_export_dir(td)
            self.assertIsNone(err)
            self.assertEqual(path, Path(td))
            self.assertTrue(path.is_dir())

    def test_missing_dir_is_created(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "nested" / "deeper"
            self.assertFalse(target.exists())
            path, err = _validate_export_dir(str(target))
            self.assertIsNone(err)
            self.assertEqual(path, target)
            self.assertTrue(target.is_dir())

    def test_path_to_file_rejected(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as tf:
            path, err = _validate_export_dir(tf.name)
            self.assertIsNone(path)
            self.assertIsNotNone(err)
            # mkdir(parents=True, exist_ok=True) raises FileExistsError for a
            # non-directory existing path, surfaced as "Cannot create directory"
            # — either error message is acceptable rejection.
            self.assertTrue(
                "Not a directory" in err or "Cannot create directory" in err,
                f"Unexpected error: {err!r}",
            )

    def test_tilde_expanded(self):
        path, err = _validate_export_dir("~")
        self.assertIsNone(err)
        self.assertEqual(path, Path.home())


class WriteNodeExportsTests(unittest.TestCase):
    def test_both_flags_write_both_files(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            written = _write_node_exports(
                target,
                task_num="753",
                node_id="init_001",
                proposal_text="proposal body",
                plan_text="plan body",
                do_proposal=True,
                do_plan=True,
            )
            prop = target / "brainstorm_t753_init_001_proposal.md"
            plan = target / "brainstorm_t753_init_001_plan.md"
            self.assertEqual(written, [str(prop), str(plan)])
            self.assertEqual(prop.read_text(encoding="utf-8"), "proposal body")
            self.assertEqual(plan.read_text(encoding="utf-8"), "plan body")

    def test_only_proposal_flag(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            written = _write_node_exports(
                target, "753", "n", "p", "pl", True, False
            )
            self.assertEqual(len(written), 1)
            self.assertTrue(written[0].endswith("_proposal.md"))
            self.assertFalse((target / "brainstorm_t753_n_plan.md").exists())

    def test_only_plan_flag(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            written = _write_node_exports(
                target, "753", "n", "p", "pl", False, True
            )
            self.assertEqual(len(written), 1)
            self.assertTrue(written[0].endswith("_plan.md"))
            self.assertFalse((target / "brainstorm_t753_n_proposal.md").exists())

    def test_no_flags_no_files(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            written = _write_node_exports(
                target, "753", "n", "p", "pl", False, False
            )
            self.assertEqual(written, [])
            self.assertEqual(list(target.iterdir()), [])

    def test_unicode_and_newlines_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            text = "# Heading\n\nLine with é and 日本語\n\n- item\n"
            written = _write_node_exports(
                target, "1", "n", text, "", True, False
            )
            self.assertEqual(Path(written[0]).read_text(encoding="utf-8"), text)


class ExportNodeDetailModalSmokeTests(unittest.TestCase):
    def test_empty_plan_coerces_default_plan_to_false(self):
        modal = ExportNodeDetailModal(
            node_id="init_001",
            task_num="753",
            proposal_text="proposal",
            plan_text="",
            default_proposal=True,
            default_plan=True,
            default_dir="/tmp/x",
        )
        self.assertTrue(modal._default_proposal)
        self.assertFalse(modal._default_plan)

    def test_empty_proposal_coerces_default_proposal_to_false(self):
        modal = ExportNodeDetailModal(
            "n", "753", "", "plan", True, True, "/tmp/x"
        )
        self.assertFalse(modal._default_proposal)
        self.assertTrue(modal._default_plan)

    def test_both_non_empty_keeps_flags(self):
        modal = ExportNodeDetailModal(
            "n", "753", "p", "pl", True, True, "/tmp/x"
        )
        self.assertTrue(modal._default_proposal)
        self.assertTrue(modal._default_plan)

    def test_round_trip_attrs(self):
        modal = ExportNodeDetailModal(
            node_id="init_001",
            task_num="753",
            proposal_text="proposal body",
            plan_text="plan body",
            default_proposal=False,
            default_plan=False,
            default_dir="/some/dir",
        )
        self.assertEqual(modal.node_id, "init_001")
        self.assertEqual(modal.task_num, "753")
        self.assertEqual(modal._proposal_text, "proposal body")
        self.assertEqual(modal._plan_text, "plan body")
        self.assertEqual(modal._default_dir, "/some/dir")


if __name__ == "__main__":
    unittest.main()
