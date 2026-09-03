"""diffviewer's MRU history lives in the USER layer, not a tracked file (t1677).

`diffviewer_history.json` was git-tracked and rewritten on every `select_plan`,
so pure browsing made a tracked file dirty. It accumulated 13 commits, every one
of them swept in under an unrelated task's message, and a dirty copy blocks
task-data sync until someone clears it.

Committing it would be the wrong fix -- it is per-user MRU state, like
`board_config.local.json` and `stats_config.local.json`. So it moved to the
`*.local.json` layer, which the data branch already gitignores.

The migration constraint pinned below: **nothing deletes a user's existing
tracked file.** An upgraded repo still reads it once (so the history is not
silently forgotten), but never writes it again -- so it goes clean and stays
clean, without this change touching anyone's data.

Run: python3 tests/test_diffviewer_history_local.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "diffviewer"))

import plan_browser  # noqa: E402


class _History:
    """The two methods under test, unbound from the Textual widget.

    `PlanBrowser` is a `VerticalScroll`, so constructing one needs an app. The
    persistence pair touches no widget state beyond `self._history`, so binding
    them to a plain object exercises the real functions rather than a copy.
    """

    def __init__(self):
        self._history: list[str] = []

    _load_history = plan_browser.PlanBrowser._load_history
    _save_history = plan_browser.PlanBrowser._save_history


class HistoryLayer(unittest.TestCase):

    def setUp(self) -> None:
        self._prev_cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory(prefix="ait_diffviewer_hist_")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "aitasks" / "metadata").mkdir(parents=True)
        os.chdir(self.root)
        self.addCleanup(os.chdir, self._prev_cwd)

        self.user = self.root / plan_browser.HISTORY_FILE
        self.legacy = self.root / plan_browser.LEGACY_HISTORY_FILE

    def test_the_paths_are_the_user_layer_and_the_legacy_tracked_one(self):
        # `*.local.json` is what the data branch's .gitignore already covers, so
        # the move needs no new ignore rule.
        self.assertTrue(plan_browser.HISTORY_FILE.endswith(".local.json"))
        self.assertEqual(
            plan_browser.LEGACY_HISTORY_FILE,
            os.path.join("aitasks", "metadata", "diffviewer_history.json"))

    def test_a_save_writes_the_user_layer_only(self):
        h = _History()
        h._history = ["aiplans/p1.md", "aiplans/p2.md"]
        h._save_history()

        self.assertTrue(self.user.is_file())
        self.assertFalse(self.legacy.exists(),
                         "the tracked path must never be written")
        self.assertEqual(json.loads(self.user.read_text())["recent"],
                         ["aiplans/p1.md", "aiplans/p2.md"])

    def test_a_save_never_rewrites_an_existing_legacy_file(self):
        """The migration guarantee: a user's tracked file goes clean and stays clean."""
        self.legacy.write_text(json.dumps({"recent": ["aiplans/old.md"]}),
                               encoding="utf-8")
        before = self.legacy.read_bytes()

        h = _History()
        h._history = ["aiplans/new.md"]
        h._save_history()

        self.assertEqual(self.legacy.read_bytes(), before)
        self.assertEqual(json.loads(self.user.read_text())["recent"],
                         ["aiplans/new.md"])

    def test_load_falls_back_to_the_legacy_file_when_no_user_file_exists(self):
        self.legacy.write_text(json.dumps({"recent": ["aiplans/old.md"]}),
                               encoding="utf-8")
        h = _History()
        h._load_history()
        self.assertEqual(h._history, ["aiplans/old.md"])

    def test_the_user_layer_wins_once_it_exists(self):
        self.legacy.write_text(json.dumps({"recent": ["aiplans/old.md"]}),
                               encoding="utf-8")
        self.user.write_text(json.dumps({"recent": ["aiplans/mine.md"]}),
                             encoding="utf-8")
        h = _History()
        h._load_history()
        self.assertEqual(h._history, ["aiplans/mine.md"])

    def test_no_file_at_all_is_an_empty_history(self):
        h = _History()
        h._load_history()
        self.assertEqual(h._history, [])

    def test_a_corrupt_user_file_falls_through_rather_than_raising(self):
        self.user.write_text("{not json", encoding="utf-8")
        self.legacy.write_text(json.dumps({"recent": ["aiplans/old.md"]}),
                               encoding="utf-8")
        h = _History()
        h._load_history()
        self.assertEqual(h._history, ["aiplans/old.md"])

    def test_the_write_is_atomic(self):
        """No reader can observe a truncated file (lib/atomic_write.py)."""
        self.user.write_text(json.dumps({"recent": ["aiplans/keep.md"]}),
                             encoding="utf-8")
        h = _History()
        h._history = ["x" * 4096]
        h._save_history()
        # A temp-and-rename leaves no dot-prefixed staging file behind.
        strays = [p.name for p in (self.root / "aitasks" / "metadata").iterdir()
                  if p.name.startswith(".")]
        self.assertEqual(strays, [])

    def test_history_is_capped(self):
        h = _History()
        h._history = [f"aiplans/p{i}.md" for i in range(50)]
        h._save_history()
        self.assertEqual(len(json.loads(self.user.read_text())["recent"]),
                         plan_browser.MAX_HISTORY)


if __name__ == "__main__":
    unittest.main(verbosity=2)
