"""board_trail_view.py — the pure trail view extracted from aitask_board.py (t1794_3).

Four contracts, checkable only against the sources or the loaded board:

* **Single home.** Each of the 25 moved names is defined in
  `board_trail_view.py` exactly once and nowhere in `aitask_board.py`, which
  imports every one of them back. Checked on the SOURCE, name by name, private
  names included: re-export identity alone cannot see a stale copy left ABOVE
  the import — the import rebinds the name, identity stays true, and the dead
  duplicate survives.
* **Re-export identity.** `ab.TrailColumn` IS `ab.board_trail_view.TrailColumn`
  — the runtime half of the same claim, on the fixture-loaded board.
* **Trail CSS is single-sourced (parent contract C7).** `TRAIL_CSS` is part of
  `KanbanApp.CSS`, each rule exactly once, and its drift colour does not depend
  on where the host App puts its own `.task-info` rule.
* **The trail modals carry their own CSS.** All three lay out in an App that
  has none of the board's CSS (tui_conventions.md "Modals pushed by multiple
  Apps") — the stand-alone trails app is such an App — and the select modal's
  rules stay scoped to it.

Reaches `board_trail_view` only as `self.ab.board_trail_view` (the harness's
binding) or by reading its source — never by a canonical import (see
`MIGRATED_MODULES` in test_board_fixture_harness.py). The headless run of the
trail model lives in test_board_bytrail_view.py (`HeadlessTrailModelTests`).

Run: bash tests/run_all_python_tests.sh
  or: ~/.aitask/venv/bin/python -m pytest tests/test_board_trail_view.py -q
"""

from __future__ import annotations

import ast
import asyncio
import re
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402

BOARD_DIR = REPO_ROOT / ".aitask-scripts" / "board"
BOARD_SRC = BOARD_DIR / "aitask_board.py"
VIEW_SRC = BOARD_DIR / "board_trail_view.py"

#: Every name t1794_3 moved out of aitask_board.py — the one list the checks
#: below read. A name added to board_trail_view.py must be added here, or
#: `test_the_view_defines_exactly_the_moved_names` fails.
MOVED_NAMES = (
    "TRAIL_WATCH_INTERVAL", "TRAIL_WATCH_MAX_TICKS", "TRAIL_GATHER_SCRIPT",
    "TRAIL_CLASSIFICATION_GLYPHS", "_TRAIL_GHOST_LABELS",
    "TrailEntryView", "TrailWaveLane",
    "load_local_project_name", "trail_ref_to_local_id", "canonical_trail_ref",
    "build_trail_lanes", "trail_drift_by_ref", "trail_summary_text",
    "run_trail_drift",
    "_GhostTaskStub", "_trail_badge_text", "_trail_drift_text",
    "TrailTaskCard", "TrailGhostCard", "TrailColumn",
    "_trail_stored_freshness", "TrailSelectItem", "TrailSelectScreen",
    "TrailDetailScreen", "TrailSummaryScreen",
)
#: Defined by the view and new with the move, so never in the board.
VIEW_ONLY_NAMES = ("TRAIL_CSS",)


# --- single home (source level) ---------------------------------------------


# The checkers are shared with test_board_task_manager.py (t1794_4); their
# negative controls stay below, in SingleHomeTests.
from board_single_home import (  # noqa: E402
    _imported_from, _name_targets, _single_home_findings, _top_level_bindings,
)


class SingleHomeTests(unittest.TestCase):
    """Each moved definition lives in board_trail_view.py and only there."""

    @classmethod
    def setUpClass(cls):
        cls.board_src = BOARD_SRC.read_text(encoding="utf-8")
        cls.view_src = VIEW_SRC.read_text(encoding="utf-8")

    def test_every_moved_name_has_exactly_one_home(self):
        board = _top_level_bindings(self.board_src)
        view = _top_level_bindings(self.view_src)
        for name in MOVED_NAMES:
            with self.subTest(name=name):
                self.assertEqual(len(view.get(name, [])), 1,
                                 f"{name} must be defined exactly once in "
                                 f"board_trail_view.py (found {view.get(name)})")
                self.assertNotIn(
                    name, board,
                    f"{name} is still defined in aitask_board.py:{board.get(name)}"
                    " — a stale copy beside the re-export")
        self.assertEqual(
            _single_home_findings(self.board_src, self.view_src, MOVED_NAMES), [])

    def test_the_view_defines_exactly_the_moved_names(self):
        """Completeness both ways: nothing moved without being listed, and
        nothing listed that the view does not define."""
        self.assertEqual(set(_top_level_bindings(self.view_src)),
                         set(MOVED_NAMES) | set(VIEW_ONLY_NAMES))

    def test_the_board_imports_every_name_back(self):
        """The re-export list cannot silently shrink: tests and KanbanApp read
        these names off the board."""
        missing = ((set(MOVED_NAMES) | set(VIEW_ONLY_NAMES))
                   - _imported_from(self.board_src, "board_trail_view"))
        self.assertEqual(missing, set())

    # -- negative controls, through the same checker -------------------------

    IMPORT = "from board_trail_view import _trail_badge_text, run_trail_drift\n"
    COPY = "def _trail_badge_text(entry):\n    return ''\n"
    VIEW = ("def _trail_badge_text(entry):\n    return 'x'\n\n\n"
            "def run_trail_drift(handle):\n    return 'CURRENT', []\n")
    NAMES = ("_trail_badge_text", "run_trail_drift")

    def test_a_board_that_only_imports_is_clean(self):
        self.assertEqual(
            _single_home_findings(self.IMPORT, self.VIEW, self.NAMES), [])

    def test_a_copy_above_the_import_is_flagged(self):
        """The shape re-export identity cannot see: the import rebinds it."""
        self.assertEqual(
            _single_home_findings(self.COPY + self.IMPORT, self.VIEW, self.NAMES),
            ["_trail_badge_text: still defined in aitask_board.py:1"])

    def test_a_copy_below_the_import_is_flagged(self):
        self.assertEqual(
            _single_home_findings(self.IMPORT + self.COPY, self.VIEW, self.NAMES),
            ["_trail_badge_text: still defined in aitask_board.py:2"])

    def test_a_copy_in_a_module_level_block_is_flagged(self):
        board = ("try:\n    def _trail_badge_text(entry):\n        return ''\n"
                 "except ImportError:\n    pass\n" + self.IMPORT)
        self.assertEqual(
            _single_home_findings(board, self.VIEW, self.NAMES),
            ["_trail_badge_text: still defined in aitask_board.py:2"])

    def test_a_leftover_constant_is_flagged(self):
        board = "_TRAIL_GHOST_LABELS = {'missing': 'missing'}\n"
        view = "_TRAIL_GHOST_LABELS = {'missing': 'missing'}\n"
        self.assertEqual(
            _single_home_findings(board, view, ("_TRAIL_GHOST_LABELS",)),
            ["_TRAIL_GHOST_LABELS: still defined in aitask_board.py:1"])

    def test_a_name_missing_from_the_view_is_flagged(self):
        view = "def _trail_badge_text(entry):\n    return 'x'\n"
        self.assertEqual(
            _single_home_findings(self.IMPORT, view, self.NAMES),
            ["run_trail_drift: not defined in board_trail_view.py"])

    def test_a_duplicate_in_the_view_is_flagged(self):
        view = self.VIEW + "\n\n" + self.COPY
        self.assertEqual(
            _single_home_findings(self.IMPORT, view, self.NAMES),
            ["_trail_badge_text: defined 2x in board_trail_view.py (lines [1, 9])"])

    def test_a_method_of_the_same_name_is_not_module_scope(self):
        """A method named like a moved function is not a copy of it."""
        board = self.IMPORT + "class K:\n    def _trail_badge_text(self):\n        pass\n"
        self.assertEqual(
            _single_home_findings(board, self.VIEW, self.NAMES), [])


# --- re-export identity (runtime) -------------------------------------------


def _non_identical(board, view, names) -> list[str]:
    """Names `board` does not bind to the very object `view` defines. A name
    missing from either side is reported too, so an empty result cannot come
    from comparing two absences."""
    absent = object()
    return [n for n in names
            if getattr(board, n, absent) is not getattr(view, n, None)]


class ReexportIdentityTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """`ab.<name>` is `ab.board_trail_view.<name>` for every moved name."""

    def test_every_moved_name_is_the_view_object(self):
        self.assertEqual(
            _non_identical(self.ab, self.ab.board_trail_view,
                           MOVED_NAMES + VIEW_ONLY_NAMES), [],
            "aitask_board.py must re-export these from board_trail_view, not "
            "define (or keep) its own copy")

    def test_the_classes_belong_to_the_view_module(self):
        for name in ("TrailEntryView", "TrailWaveLane", "_GhostTaskStub",
                     "TrailTaskCard", "TrailGhostCard", "TrailColumn",
                     "TrailSelectItem", "TrailSelectScreen", "TrailDetailScreen",
                     "TrailSummaryScreen"):
            with self.subTest(name=name):
                self.assertEqual(getattr(self.ab, name).__module__,
                                 "board_trail_view")
        self.assertTrue(issubclass(self.ab.TrailTaskCard,
                                   self.ab.board_widgets.TaskCard))

    def test_a_stale_copy_or_a_missing_name_is_reported(self):
        view = self.ab.board_trail_view
        board = types.SimpleNamespace(**{n: getattr(view, n) for n in MOVED_NAMES})
        self.assertEqual(_non_identical(board, view, MOVED_NAMES), [],
                         "control: a faithful re-export must pass")
        board.TrailColumn = type("TrailColumn", (view.TrailColumn,), {})
        del board.run_trail_drift
        self.assertEqual(sorted(_non_identical(board, view, MOVED_NAMES)),
                         ["TrailColumn", "run_trail_drift"])


# --- trail CSS (C7) ---------------------------------------------------------


def _rule_lines(css: str) -> list[str]:
    """The non-comment, non-blank lines of a CSS literal, stripped."""
    no_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [ln.strip() for ln in no_comments.splitlines() if ln.strip()]


def _run_bare_app(css: str, compose, probe):
    """Boot an App carrying ONLY `css` (none of the board's) and return
    `probe(app)` once it has laid out."""
    from textual.app import App

    host = type("BareHost", (App,), {"CSS": css, "compose": compose})

    async def go():
        app = host()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            return await probe(app, pilot)

    return asyncio.run(go())


def _drift_colour(css: str) -> str:
    from textual.widgets import Label

    def compose(self):
        yield Label("drift", id="probe", classes="task-info trail-drift")

    async def probe(app, pilot):
        return app.query_one("#probe").styles.color.hex.upper()

    return _run_bare_app(css, compose, probe)


class TrailCssTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """`TRAIL_CSS` is single-sourced into the board and host-order independent."""

    DRIFT = "#FFB86C"
    LATER_HOST_RULE = "\n.task-info { color: #FF0000; }\n"

    def test_trail_css_is_part_of_the_board_css(self):
        self.assertIn(self.ab.TRAIL_CSS, self.ab.KanbanApp.CSS)

    def test_each_trail_rule_appears_exactly_once_in_the_board(self):
        rules = _rule_lines(self.ab.TRAIL_CSS)
        # Anti-vacuity: the two rules the view owns.
        self.assertTrue(any(r.startswith(".task-info.trail-drift {") for r in rules),
                        rules)
        self.assertTrue(any(r.startswith("#trail_summary {") for r in rules), rules)
        for rule in rules:
            with self.subTest(rule=rule):
                self.assertEqual(self.ab.KanbanApp.CSS.count(rule), 1)

    def test_the_order_dependent_selector_is_gone(self):
        """The pre-move single-class `.trail-drift` rule must not survive
        beside the two-class one."""
        self.assertIsNone(re.search(r"(^|[\s}])\.trail-drift\s*\{",
                                    self.ab.KanbanApp.CSS))

    def test_the_drift_colour_survives_a_later_host_rule(self):
        self.assertEqual(
            _drift_colour(self.ab.TRAIL_CSS + self.LATER_HOST_RULE), self.DRIFT)

    def test_the_pre_move_selector_was_order_dependent(self):
        """Negative control: with the old single-class rule, a host that puts
        its `.task-info` rule later silently wins — so the order dependence was
        real and the selector is what removes it."""
        legacy = ".trail-drift { color: #FFB86C; }" + self.LATER_HOST_RULE
        self.assertEqual(_drift_colour(legacy), "#FF0000")


# --- modal DEFAULT_CSS ------------------------------------------------------


def _modal_layout(screen_factory, dialog_id: str, then=None):
    """Push the modal in a bare App and report how its dialog actually laid
    out: rendered width and x offset on the screen, plus the screen's
    alignment. Measured on the region rather than read off the style — Textual
    stores `width: 60%` in a width-relative unit, so the rule's text is not the
    claim; the laid-out size is. `then()` may build a second screen to push
    after popping the first; its `#dep_picker_dialog` width is reported too."""
    from textual.containers import Container

    def compose(self):
        return iter(())

    async def probe(app, pilot):
        app.push_screen(screen_factory())
        await pilot.pause()
        await pilot.pause()
        dialog = app.screen.query_one(dialog_id, Container)
        out = {"screen": app.screen.size.width,
               "width": dialog.region.width,
               "x": dialog.region.x,
               "align": (app.screen.styles.align_horizontal,
                         app.screen.styles.align_vertical)}
        if then is not None:
            app.pop_screen()
            await pilot.pause()
            app.push_screen(then())
            await pilot.pause()
            await pilot.pause()
            other = app.screen.query_one("#dep_picker_dialog", Container)
            out["other_width"] = other.region.width
        return out

    return _run_bare_app("", compose, probe)


class ModalDefaultCssTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """The trail modals lay out without the board's CSS."""

    def _select_screen(self):
        view = self.ab.board_trail_view
        info = view.TrailInfo(
            handle="art:trail-a", owner_id="9000", owner_archived=False,
            owner_folded=False, name="Trail A",
            doc={"title": "Trail A", "scope": {"kind": "repo"},
                 "generation": {"generated_at": "2026-08-01"},
                 "freshness": {"state": "current"}})
        return view.TrailSelectScreen([info], {})

    @staticmethod
    def _plain_picker_screen():
        """A modal reusing the `#dep_picker_dialog` id with no CSS of its own."""
        from textual.containers import Container
        from textual.screen import ModalScreen
        from textual.widgets import Label

        class PlainPicker(ModalScreen):
            def compose(self):
                with Container(id="dep_picker_dialog"):
                    yield Label("plain")

        return PlainPicker()

    def assertCenteredAt(self, out, fraction):
        """The dialog is `fraction` of the screen wide and centred on it."""
        width = int(out["screen"] * fraction)
        self.assertEqual(out["width"], width, out)
        self.assertEqual(out["x"], (out["screen"] - width) // 2, out)
        self.assertEqual(out["align"], ("center", "middle"), out)

    def test_the_select_modal_lays_out_without_the_board(self):
        self.assertCenteredAt(
            _modal_layout(self._select_screen, "#dep_picker_dialog"), 0.6)

    def test_the_select_modal_rules_stay_scoped_to_it(self):
        """Negative control, and the scoping claim: the bare App supplies no
        `#dep_picker_dialog` rule of its own — another modal reusing the id in
        the same App does not get the width, even after the select modal ran.
        (The board's 19 other `#dep_picker_dialog` modals rely on
        `KanbanApp.CSS`, not on this screen.)"""
        out = _modal_layout(self._select_screen, "#dep_picker_dialog",
                            then=self._plain_picker_screen)
        self.assertCenteredAt(out, 0.6)
        self.assertNotEqual(out["other_width"], out["width"], out)

    def test_the_detail_modal_lays_out_without_the_board(self):
        view = self.ab.board_trail_view
        self.assertCenteredAt(_modal_layout(
            lambda: view.TrailDetailScreen({"title": "T", "waves": []}, []),
            "#trail_detail_dialog"), 0.8)

    def test_the_summary_modal_lays_out_without_the_board(self):
        view = self.ab.board_trail_view
        self.assertCenteredAt(_modal_layout(
            lambda: view.TrailSummaryScreen("summary", "T"),
            "#trail_summary_dialog"), 0.8)


if __name__ == "__main__":
    unittest.main()
