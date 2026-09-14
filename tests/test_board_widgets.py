"""board_widgets.py — the widget layer extracted from aitask_board.py (t1794_2).

Two contracts the move must keep, both checkable only against the loaded board:

* **Re-export identity.** `aitask_board.py` imports every moved name back from
  `board_widgets`, so `ab.TaskCard` IS `ab.board_widgets.TaskCard` — the same
  object, not a copy. A definition left behind (or re-added) in the board would
  shadow the import: the board's subclasses and its `query(TaskCard)` calls
  would bind the stale class while the trail modules bind the extracted one.
* **Host surface.** `TaskCard` and the column-header buttons reach back into the
  App through `self.app`. `board_widgets.CardHost` / `ColumnHeaderHost` document
  that surface; this file asserts `KanbanApp` provides it, so the Protocols stay
  a checked claim that a second host (the stand-alone trails app) is held to.

Reaches `board_widgets` only as `self.ab.board_widgets` — the fixture-loaded
board's own binding — never by a canonical import (see `MIGRATED_MODULES` in
test_board_fixture_harness.py). The headless-import pin lives in
test_board_package_contract.py beside the other subprocess checks.

Run: bash tests/run_all_python_tests.sh
  or: ~/.aitask/venv/bin/python -m pytest tests/test_board_widgets.py -q
"""

from __future__ import annotations

import inspect
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402

#: Every name t1794_2 moved out of aitask_board.py — the board's re-export list.
MOVED_NAMES = (
    "CollapseToggleButton", "ColumnEditButton", "ColumnHeader", "LoadingOverlay",
    "MarkedSelection", "PickerItem", "TaskCard",
    "_followup_colour_hex", "_followup_glyph_text", "_followup_marker",
    "_issue_indicator", "_plan_approved_marker", "_pr_indicator",
    "_status_badge_text",
)


def _non_identical(board, widgets, names) -> list[str]:
    """Names `board` does not bind to the very object `widgets` defines.

    A name missing from either side is reported too, so an empty result cannot
    come from comparing two absences.
    """
    absent = object()
    return [n for n in names
            if getattr(board, n, absent) is not getattr(widgets, n, None)]


def _protocol_members(protocol) -> set[str]:
    """Declared attributes plus public methods of a `typing.Protocol` body."""
    members = set(inspect.get_annotations(protocol))
    members |= {name for name, value in vars(protocol).items()
                if callable(value) and not name.startswith("_")}
    return members


def _missing_members(protocol, host) -> list[str]:
    return sorted(m for m in _protocol_members(protocol) if not hasattr(host, m))


class ReexportIdentityTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """`ab.<name>` is `ab.board_widgets.<name>` for every moved name."""

    def test_every_moved_name_is_the_widgets_object(self):
        self.assertEqual(
            _non_identical(self.ab, self.ab.board_widgets, MOVED_NAMES), [],
            "aitask_board.py must re-export these from board_widgets, not "
            "define (or keep) its own copy")

    def test_the_board_subclasses_the_extracted_card(self):
        self.assertEqual(self.ab.TaskCard.__module__, "board_widgets")
        self.assertTrue(issubclass(self.ab.InFlightTaskCard,
                                   self.ab.board_widgets.TaskCard))
        self.assertTrue(issubclass(self.ab.GateChoiceItem,
                                   self.ab.board_widgets.PickerItem))

    def test_a_stale_copy_or_a_missing_name_is_reported(self):
        widgets = self.ab.board_widgets
        board = types.SimpleNamespace(
            **{n: getattr(widgets, n) for n in MOVED_NAMES})
        self.assertEqual(_non_identical(board, widgets, MOVED_NAMES), [],
                         "control: a faithful re-export must pass")
        board.TaskCard = type("TaskCard", (widgets.TaskCard,), {})
        del board.PickerItem
        self.assertEqual(_non_identical(board, widgets, MOVED_NAMES),
                         ["PickerItem", "TaskCard"])


class HostProtocolTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """`KanbanApp` provides everything the extracted widgets read off `self.app`."""

    def test_the_protocols_name_the_widgets_app_reads(self):
        """Anti-vacuity: an empty Protocol would make every host conform."""
        bw = self.ab.board_widgets
        self.assertEqual(_protocol_members(bw.CardHost),
                         {"marked", "expanded_tasks", "check_action",
                          "action_toggle_children", "action_view_details"})
        self.assertEqual(_protocol_members(bw.ColumnHeaderHost),
                         {"toggle_column_collapse", "open_column_edit"})

    def test_kanban_app_is_a_card_host(self):
        """On an instance: `marked` and `expanded_tasks` are set in `__init__`."""
        app = self.ab.KanbanApp()
        self.assertEqual(
            _missing_members(self.ab.board_widgets.CardHost, app), [])

    def test_kanban_app_is_a_column_header_host(self):
        self.assertEqual(
            _missing_members(self.ab.board_widgets.ColumnHeaderHost,
                             self.ab.KanbanApp), [])

    def test_a_host_missing_a_member_is_reported(self):
        bw = self.ab.board_widgets
        host = types.SimpleNamespace(
            marked=bw.MarkedSelection(),
            check_action=lambda action, parameters: True,
            action_toggle_children=lambda: None,
            action_view_details=lambda: None)
        self.assertEqual(_missing_members(bw.CardHost, host), ["expanded_tasks"])


if __name__ == "__main__":
    unittest.main()
