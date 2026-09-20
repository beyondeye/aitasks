"""board_column_dialogs.py — the column-management dialogs extracted from
aitask_board.py (t1794_8).

Three contracts the move must keep:

* **Single home (source level).** Each moved name is defined exactly once, in
  board_column_dialogs.py, and nowhere in aitask_board.py. This is checked on
  the SOURCE, not on the loaded modules: re-export identity cannot see a stale
  copy left ABOVE the board's import (the import rebinds the name, identity
  stays true, the dead duplicate survives). The shared helper's own negative
  controls live in test_board_trail_view.SingleHomeTests.
* **Re-export identity.** `aitask_board.py` imports every moved name back, so
  `ab.ColumnManageScreen` IS `ab.board_column_dialogs.ColumnManageScreen`. The
  board's own push sites and every existing test reach them that way.
* **The board_columns import is now a PURE re-export (t1794_8).** Every in-file
  consumer of PALETTE_COLORS / generate_col_id / UNORDERED_* moved out with the
  dialogs, so nothing in aitask_board.py reads them any more — but
  test_board_columns_seam.py pins the import text and
  test_board_column_manage.py reads `B.UNORDERED_ID`. This pins the import so a
  later "remove unused import" cleanup fails here instead of there.

Reaches the module only as `self.ab.board_column_dialogs` — the fixture-loaded
board's own binding — or by reading its source; never by a canonical import
(see `MIGRATED_MODULES` in test_board_fixture_harness.py). The headless-import
pin lives in test_board_package_contract.py beside the other subprocess checks.

Run: bash tests/run_all_python_tests.sh
  or: ~/.aitask/venv/bin/python -m pytest tests/test_board_column_dialogs.py -q
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402

from board_single_home import (  # noqa: E402
    _imported_from, _single_home_findings, _top_level_bindings,
)

BOARD_DIR = REPO_ROOT / ".aitask-scripts" / "board"
BOARD_SRC = BOARD_DIR / "aitask_board.py"
DIALOGS_SRC = BOARD_DIR / "board_column_dialogs.py"

#: Every name t1794_8 moved out of aitask_board.py — the board's re-export list.
#: Nine, not the six the parent file map names: ColumnManageScreen pushes
#: ColumnEditScreen, DeleteColumnConfirmScreen and MergeColumnsConfirmScreen, so
#: leaving those behind would need an `import aitask_board` back (C1 forbids it)
#: and would strand ColorSwatch from ColumnEditScreen, its only consumer.
MOVED_NAMES = (
    "ColorSwatch", "ColumnEditScreen", "ColumnManageItem", "ColumnManageScreen",
    "ColumnMultiSelectScreen", "ColumnSelectItem", "ColumnSelectScreen",
    "DeleteColumnConfirmScreen", "MergeColumnsConfirmScreen",
)

#: The column vocabulary the moved classes took with them. The board keeps
#: importing these for its consumers even though it no longer reads them.
REEXPORTED_VOCABULARY = frozenset({
    "PALETTE_COLORS", "UNORDERED_COLOR", "UNORDERED_ID", "UNORDERED_TITLE",
    "generate_col_id",
})


def _non_identical(board, module, names) -> list[str]:
    """Names `board` does not bind to the very object `module` defines.

    A name missing from either side is reported too, so an empty result cannot
    come from comparing two absences.
    """
    absent = object()
    return [n for n in names
            if getattr(board, n, absent) is not getattr(module, n, None)]


class SingleHomeTests(unittest.TestCase):
    """Each moved definition lives in board_column_dialogs.py and only there."""

    @classmethod
    def setUpClass(cls):
        cls.board_src = BOARD_SRC.read_text(encoding="utf-8")
        cls.dialogs_src = DIALOGS_SRC.read_text(encoding="utf-8")

    def test_every_moved_name_has_exactly_one_home(self):
        board = _top_level_bindings(self.board_src)
        dialogs = _top_level_bindings(self.dialogs_src)
        for name in MOVED_NAMES:
            with self.subTest(name=name):
                self.assertEqual(
                    len(dialogs.get(name, [])), 1,
                    f"{name} must be defined exactly once in "
                    f"board_column_dialogs.py (found {dialogs.get(name)})")
                self.assertNotIn(
                    name, board,
                    f"{name} is still defined in aitask_board.py:"
                    f"{board.get(name)} — a stale copy beside the re-export")
        self.assertEqual(
            _single_home_findings(self.board_src, self.dialogs_src, MOVED_NAMES,
                                  view_label="board_column_dialogs.py"),
            [])

    def test_the_module_defines_exactly_the_moved_names(self):
        """Completeness both ways: nothing moved without being listed, and
        nothing listed that the module does not define."""
        defined = {n for n, lines in
                   _top_level_bindings(self.dialogs_src).items()
                   if not n.startswith("_") and n[0].isupper()}
        self.assertEqual(defined, set(MOVED_NAMES))

    def test_the_module_never_imports_the_board(self):
        """C1, checked on the source as well as by the subprocess probe in
        test_board_package_contract.py.

        An AST check, not a substring one: the module docstring names
        ``aitask_board.py`` in prose (it says what was extracted from where),
        and that must stay legal.
        """
        tree = ast.parse(self.dialogs_src)
        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders += [a.name for a in node.names
                              if a.name == "aitask_board"]
            elif isinstance(node, ast.ImportFrom) and node.module == "aitask_board":
                offenders.append(node.module)
        self.assertEqual(offenders, [],
                         "board_column_dialogs.py must never import "
                         "aitask_board (C1)")


class ReexportedVocabularyTests(unittest.TestCase):
    """The board's `from board_columns import` survived losing its last user."""

    @classmethod
    def setUpClass(cls):
        cls.board_src = BOARD_SRC.read_text(encoding="utf-8")
        cls.dialogs_src = DIALOGS_SRC.read_text(encoding="utf-8")

    def test_the_board_still_imports_the_vocabulary(self):
        self.assertEqual(
            REEXPORTED_VOCABULARY - _imported_from(self.board_src,
                                                   "board_columns"),
            set(),
            "aitask_board.py must keep re-exporting these: "
            "test_board_columns_seam.py pins the import text and "
            "test_board_column_manage.py reads B.UNORDERED_ID, even though "
            "t1794_8 moved every in-file consumer to board_column_dialogs.py")

    def test_the_dialogs_are_the_real_consumer(self):
        """Anti-vacuity: the names are pinned on the board because they moved,
        so the new module must actually import and use them."""
        self.assertEqual(
            REEXPORTED_VOCABULARY - _imported_from(self.dialogs_src,
                                                   "board_columns"),
            set())


class ReexportIdentityTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """`ab.<name>` is `ab.board_column_dialogs.<name>` for every moved name."""

    def test_every_moved_name_is_the_dialogs_module_object(self):
        self.assertEqual(len(set(MOVED_NAMES)), 9)
        self.assertEqual(
            _non_identical(self.ab, self.ab.board_column_dialogs, MOVED_NAMES),
            [],
            "aitask_board.py must re-export these from board_column_dialogs, "
            "not define (or keep) its own copy")

    def test_the_identity_check_can_fail(self):
        """Negative control: a stand-in board holding a copy, or missing the
        name, is reported."""
        module = self.ab.board_column_dialogs
        copy = type("ColumnManageScreen", (), {})
        stand_in = type("Board", (), {"ColumnManageScreen": copy})
        self.assertEqual(
            _non_identical(stand_in, module,
                           ("ColumnManageScreen", "ColorSwatch")),
            ["ColumnManageScreen", "ColorSwatch"])

    def test_the_module_owns_them_the_board_does_not(self):
        for name in MOVED_NAMES:
            with self.subTest(name=name):
                obj = getattr(self.ab.board_column_dialogs, name)
                self.assertEqual(obj.__module__, "board_column_dialogs")


class HostReachTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """The dialogs need no injection: every board helper they call is a
    `KanbanApp` method reached through `self.app` at call time (t1794_8)."""

    HOST_METHODS = ("_column_title", "_apply_column_edit",
                    "_merge_source_columns", "_report_merge")

    def test_the_board_app_still_provides_the_host_surface(self):
        for name in self.HOST_METHODS:
            with self.subTest(name=name):
                self.assertTrue(callable(getattr(self.ab.KanbanApp, name)))

    def test_the_dialogs_reach_them_only_through_self_app(self):
        src = DIALOGS_SRC.read_text(encoding="utf-8")
        for name in self.HOST_METHODS:
            with self.subTest(name=name):
                self.assertIn(f"self.app.{name}", src)


if __name__ == "__main__":
    unittest.main()
