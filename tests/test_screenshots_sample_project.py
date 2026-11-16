"""Tests for the docs-screenshot sample project (t2278_2).

`website/screenshots/sample_project.py` builds the only data a docs screenshot
may show. These tests build into a temporary directory and never touch the
real `aitasks/` tree.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_screenshots_sample_project.py -v
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "website"))

from screenshots import sample_project as sp  # noqa: E402


class BaseDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory(prefix="ait_shots_test_")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = sp.build(Path(tmp.name) / "lumen", "base")

    def _git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True,
                              text=True, check=True).stdout

    def test_is_a_standalone_ait_project(self):
        self.assertTrue(os.access(self.root / "ait", os.X_OK))
        self.assertTrue((self.root / ".aitask-scripts").is_symlink())
        self.assertTrue((self.root / ".aitask-scripts" / "aitask_ls.sh").is_file())

    def test_is_a_clean_git_repository_with_one_commit(self):
        self.assertEqual(self._git("rev-list", "--count", "HEAD").strip(), "1")
        self.assertEqual(self._git("status", "--porcelain").strip(), "")
        self.assertIn(sp.PERSON_EMAIL, self._git("log", "-1", "--format=%ae"))

    def test_parent_with_children_and_every_column(self):
        tasks = self.root / "aitasks"
        children = sorted(p.name for p in (tasks / "t12").glob("t12_*.md"))
        self.assertEqual(len(children), 3)
        parent = (tasks / "t12_add_checkout_page.md").read_text()
        self.assertIn("children_to_implement: [t12_1, t12_2, t12_3]", parent)
        columns = {line.split(": ")[1] for p in tasks.rglob("t*.md")
                   for line in p.read_text().splitlines() if line.startswith("boardcol: ")}
        self.assertEqual(columns, {c["id"] for c in sp.BASE_COLUMNS})

    def test_only_invented_names_reach_the_data(self):
        """The doc guide forbids the real repo names in an on-screen example."""
        config = (self.root / "aitasks" / "metadata" / "project_config.yaml").read_text()
        self.assertEqual(config, "project:\n  name: lumen\n")
        for path in (self.root / "aitasks").rglob("t*.md"):
            text = path.read_text()
            self.assertNotIn("aitasks", text, path.name)
            self.assertNotIn("9000", path.name)

    def test_dates_are_fixed(self):
        for path in (self.root / "aitasks").rglob("t*.md"):
            self.assertIn(f"created_at: {sp.FIXED_STAMP}", path.read_text(), path.name)

    def test_no_timer_can_repaint_the_board(self):
        local = (self.root / "aitasks" / "metadata" / "board_config.local.json").read_text()
        self.assertIn('"auto_refresh_minutes": 0', local)


class BuildContractTests(unittest.TestCase):
    def test_unknown_dataset_is_an_error_naming_the_known_ones(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(sp.DatasetError) as ctx:
                sp.build(Path(tmp) / "x", "no_such_dataset")
            self.assertIn("base", str(ctx.exception))
            self.assertFalse((Path(tmp) / "x").exists())

    def test_an_existing_root_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(sp.DatasetError):
                sp.build(Path(tmp), "base")
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_builders_do_not_import_tui_code(self):
        """A dataset is data. An adapter that imports a TUI would be the design
        this tool replaced."""
        source = Path(sp.__file__).read_text()
        for forbidden in ("textual", "aitask_board", "tui_switcher", "brainstorm_app",
                          "from tests", "import tests"):
            self.assertNotIn(forbidden, source, forbidden)


if __name__ == "__main__":
    unittest.main()
