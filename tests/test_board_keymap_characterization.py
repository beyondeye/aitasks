"""Characterization of the board key map, check_action matrix and trail widgets (t1794_1).

Pins — before any code moves out of aitask_board.py (t1794) — the key surface
the split must preserve:

  (a) GOLDEN_BINDINGS: `KanbanApp.BINDINGS` as declared, one
      `(key, action, description, show, priority)` row per binding, in order.
      Order is behaviour: a repeated key (`r`, `s`, `x`) dispatches to the first
      binding `check_action` admits, and the footer lists keys in
      first-declaration order. The class attribute holds the defaults;
      `ShortcutsMixin.__init__` applies user overrides per instance.
  (b) GOLDEN_CHECK_ACTION: `check_action(action, None)` for every bound action,
      in each `base_filter` view × {no focus, focused parent card}. Stored as
      the hidden (`False`) and greyed (`None`) sets; every other bound action
      must answer exactly `True`.
  (c) the widget contract the By-Trail view queries: `HeaderTitle`,
      `#board_container`, `#trail_summary` > `#trail_summary_body`, and the
      `LoadingOverlay` modal.

**t1794 children 5 and 6 keep this file green UNCHANGED** — that is the proof
that splicing the shared trail bindings and the `T` policy seam changed nothing
in the board. Any OTHER task that adds a binding or a `check_action` gate
updates the golden deliberately and names the change in its own plan. Never
regenerate it to turn a red run green: a golden rebuilt from the code it checks
proves nothing. A failure prints a readable diff to decide from.

Generated once from the fixture-loaded board (`DEFAULT_TOPOLOGY`, 200×48, no
trail selected, clean tree) and hand-reviewed against `check_action`
(aitask_board.py `KanbanApp.check_action`).

Run: bash tests/run_all_python_tests.sh
  or: ~/.aitask/venv/bin/python -m pytest tests/test_board_keymap_characterization.py -q
"""

from __future__ import annotations

import asyncio
import difflib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(REPO_ROOT / "tests" / "lib"),
           str(REPO_ROOT / ".aitask-scripts"),
           str(REPO_ROOT / ".aitask-scripts" / "board"),
           str(REPO_ROOT / ".aitask-scripts" / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import board_fixture as bf  # noqa: E402

FILTERS = ("all", "locked", "free", "inflight", "bytopic", "bytrail")
FOCUS_STATES = ("none", "parent_card")
#: DEFAULT_TOPOLOGY's parent with two children, so `toggle_children` is live on it.
FOCUS_CARD = "t9000_parent.md"

UPDATE_RULE = (
    "t1794 children 5 and 6 must keep this golden UNCHANGED. Any other task "
    "that adds a binding or a check_action gate updates the golden "
    "deliberately and names the change in its own plan — never regenerate it "
    "to turn a red run green.")

GOLDEN_BINDINGS = [
    ("j", "tui_switcher", "TUI switcher", False, False),
    ("?", "open_shortcuts_editor", "Keys", True, False),
    ("q", "quit", "Quit", True, False),
    ("tab", "focus_search", "Search", False, True),
    ("escape", "focus_board", "Board", False, True),
    ("up", "nav_up", "Up", False, True),
    ("down", "nav_down", "Down", False, True),
    ("left", "nav_left", "Left", False, True),
    ("right", "nav_right", "Right", False, True),
    ("shift+right", "move_task_right", "Task >", True, False),
    ("shift+left", "move_task_left", "< Task", True, False),
    ("shift+up", "move_task_up", "Task Up", True, False),
    ("shift+down", "move_task_down", "Task Down", True, False),
    ("ctrl+up", "move_task_top", "Task Top", True, False),
    ("ctrl+down", "move_task_bottom", "Task Btm", True, False),
    ("enter", "view_details", "View/Edit", True, False),
    ("o", "sort_topic", "Sort Order", True, False),
    ("r", "refresh_board", "Refresh", True, False),
    ("r", "trail_refresh_local", "Refresh", True, False),
    ("R", "trail_refresh_agent", "Agent Refresh", True, False),
    ("d", "trail_refresh_drift", "Freshness", True, False),
    ("s", "sync_remote", "Sync", True, False),
    ("s", "trail_select", "Select Trail", True, False),
    ("S", "trail_sync", "Sync", True, False),
    ("v", "trail_summary_expand", "Summary", True, False),
    ("c", "commit_selected", "Commit", True, False),
    ("C", "commit_all", "Commit All", True, False),
    ("n", "create_task", "New Task", True, False),
    ("p", "pick_task", "Pick", True, False),
    ("w", "work_report", "Work Report", True, False),
    ("b", "brainstorm_task", "Brainstorm", True, False),
    ("T", "trail_task", "Trail", True, False),
    ("#", "open_cross_repo", "Cross-repo", True, False),
    ("x", "toggle_children", "Toggle Children", True, False),
    ("x", "toggle_group", "Toggle Group", True, False),
    ("space", "toggle_mark", "Mark", True, False),
    ("m", "move_to_column", "Move to Col", True, False),
    ("M", "trail_move_wave", "Move Wave", True, False),
    ("ctrl+right", "move_col_right", "Move Col >", True, False),
    ("ctrl+left", "move_col_left", "< Move Col", True, False),
    ("X", "toggle_column_collapsed", "Collapse Col", True, False),
    ("e", "column_manage", "Columns", True, False),
    ("O", "open_settings", "Options", True, False),
    ("a", "view_all", "All", False, False),
    ("l", "view_locked", "Locked", False, False),
    ("f", "view_free", "Free", False, False),
    ("i", "view_inflight", "In-Flight", False, False),
    ("y", "view_bytopic", "By-Topic", False, False),
    ("z", "view_bytrail", "By-Trail", False, False),
    ("g", "view_git", "Git", False, False),
    ("t", "view_type", "Type", False, False),
]

GOLDEN_CHECK_ACTION = {
    "all/none": {
        "hidden": (
            "brainstorm_task", "commit_all", "commit_selected", "move_to_column",
            "open_cross_repo", "pick_task", "sort_topic", "toggle_children",
            "toggle_group", "trail_move_wave", "trail_refresh_agent",
            "trail_refresh_drift", "trail_refresh_local", "trail_select",
            "trail_summary_expand", "trail_sync", "trail_task", "work_report",
        ),
        "greyed": (),
    },
    "locked/none": {
        "hidden": (
            "brainstorm_task", "commit_all", "commit_selected", "move_to_column",
            "open_cross_repo", "pick_task", "sort_topic", "toggle_children",
            "toggle_group", "trail_move_wave", "trail_refresh_agent",
            "trail_refresh_drift", "trail_refresh_local", "trail_select",
            "trail_summary_expand", "trail_sync", "trail_task", "work_report",
        ),
        "greyed": (),
    },
    "free/none": {
        "hidden": (
            "brainstorm_task", "commit_all", "commit_selected", "move_to_column",
            "open_cross_repo", "pick_task", "sort_topic", "toggle_children",
            "toggle_group", "trail_move_wave", "trail_refresh_agent",
            "trail_refresh_drift", "trail_refresh_local", "trail_select",
            "trail_summary_expand", "trail_sync", "trail_task", "work_report",
        ),
        "greyed": (),
    },
    "inflight/none": {
        "hidden": (
            "brainstorm_task", "column_manage", "commit_all", "commit_selected",
            "move_col_left", "move_col_right", "move_task_bottom", "move_task_down",
            "move_task_left", "move_task_right", "move_task_top", "move_task_up",
            "move_to_column", "open_cross_repo", "pick_task", "sort_topic",
            "toggle_children", "toggle_column_collapsed", "toggle_group", "toggle_mark",
            "trail_move_wave", "trail_refresh_agent", "trail_refresh_drift",
            "trail_refresh_local", "trail_select", "trail_summary_expand", "trail_sync",
            "trail_task", "work_report",
        ),
        "greyed": (),
    },
    "bytopic/none": {
        "hidden": (
            "brainstorm_task", "column_manage", "commit_all", "commit_selected",
            "move_col_left", "move_col_right", "move_task_bottom", "move_task_down",
            "move_task_left", "move_task_right", "move_task_top", "move_task_up",
            "move_to_column", "open_cross_repo", "pick_task", "toggle_children",
            "toggle_column_collapsed", "toggle_group", "toggle_mark", "trail_move_wave",
            "trail_refresh_agent", "trail_refresh_drift", "trail_refresh_local",
            "trail_select", "trail_summary_expand", "trail_sync", "trail_task",
            "work_report",
        ),
        "greyed": (),
    },
    "bytrail/none": {
        "hidden": (
            "brainstorm_task", "column_manage", "commit_all", "commit_selected",
            "move_col_left", "move_col_right", "move_task_bottom", "move_task_down",
            "move_task_left", "move_task_right", "move_task_top", "move_task_up",
            "move_to_column", "open_cross_repo", "pick_task", "refresh_board",
            "sort_topic", "sync_remote", "toggle_children", "toggle_column_collapsed",
            "toggle_group", "toggle_mark", "trail_move_wave", "trail_refresh_agent",
            "trail_refresh_drift", "trail_refresh_local", "trail_summary_expand",
            "trail_task", "work_report",
        ),
        "greyed": (),
    },
    "all/parent_card": {
        "hidden": (
            "commit_all", "commit_selected", "open_cross_repo", "sort_topic",
            "toggle_group", "trail_move_wave", "trail_refresh_agent",
            "trail_refresh_drift", "trail_refresh_local", "trail_select",
            "trail_summary_expand", "trail_sync",
        ),
        "greyed": (),
    },
    "locked/parent_card": {
        "hidden": (
            "commit_all", "commit_selected", "open_cross_repo", "sort_topic",
            "toggle_group", "trail_move_wave", "trail_refresh_agent",
            "trail_refresh_drift", "trail_refresh_local", "trail_select",
            "trail_summary_expand", "trail_sync",
        ),
        "greyed": (),
    },
    "free/parent_card": {
        "hidden": (
            "commit_all", "commit_selected", "open_cross_repo", "sort_topic",
            "toggle_group", "trail_move_wave", "trail_refresh_agent",
            "trail_refresh_drift", "trail_refresh_local", "trail_select",
            "trail_summary_expand", "trail_sync",
        ),
        "greyed": (),
    },
    "inflight/parent_card": {
        "hidden": (
            "column_manage", "commit_all", "commit_selected", "move_col_left",
            "move_col_right", "move_task_bottom", "move_task_down", "move_task_left",
            "move_task_right", "move_task_top", "move_task_up", "move_to_column",
            "open_cross_repo", "sort_topic", "toggle_children",
            "toggle_column_collapsed", "toggle_group", "toggle_mark", "trail_move_wave",
            "trail_refresh_agent", "trail_refresh_drift", "trail_refresh_local",
            "trail_select", "trail_summary_expand", "trail_sync", "trail_task",
            "work_report",
        ),
        "greyed": (),
    },
    "bytopic/parent_card": {
        "hidden": (
            "column_manage", "commit_all", "commit_selected", "move_col_left",
            "move_col_right", "move_task_bottom", "move_task_down", "move_task_left",
            "move_task_right", "move_task_top", "move_task_up", "move_to_column",
            "open_cross_repo", "toggle_children", "toggle_column_collapsed",
            "toggle_group", "toggle_mark", "trail_move_wave", "trail_refresh_agent",
            "trail_refresh_drift", "trail_refresh_local", "trail_select",
            "trail_summary_expand", "trail_sync", "work_report",
        ),
        "greyed": (),
    },
    "bytrail/parent_card": {
        "hidden": (
            "column_manage", "commit_all", "commit_selected", "move_col_left",
            "move_col_right", "move_task_bottom", "move_task_down", "move_task_left",
            "move_task_right", "move_task_top", "move_task_up", "open_cross_repo",
            "refresh_board", "sort_topic", "sync_remote", "toggle_children",
            "toggle_column_collapsed", "toggle_group", "toggle_mark",
            "trail_refresh_agent", "trail_refresh_drift", "trail_refresh_local",
            "trail_summary_expand", "trail_task", "work_report",
        ),
        "greyed": (),
    },
}


def _binding_rows(bindings) -> list[tuple]:
    return [(b.key, b.action, b.description, b.show, b.priority) for b in bindings]


def _diff_bindings(expected, observed) -> list[str]:
    """Readable, order-aware diff of two binding tables."""
    lines: list[str] = []
    matcher = difflib.SequenceMatcher(a=expected, b=observed, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        old, new = expected[i1:i2], observed[j1:j2]
        if tag == "replace" and len(old) == len(new):
            lines += [f"~ changed row #{i1 + k}: {o!r} -> {n!r}"
                      for k, (o, n) in enumerate(zip(old, new))]
            continue
        lines += [f"- removed row #{i1 + k}: {o!r}" for k, o in enumerate(old)]
        lines += [f"+ added row #{j1 + k}: {n!r}" for k, n in enumerate(new)]
    return lines


def _cell(state: dict, action: str) -> str:
    if action in state["hidden"]:
        return "hidden"
    if action in state["greyed"]:
        return "greyed"
    return "shown"


def _diff_matrix(expected, observed) -> list[str]:
    """`<filter>/<focus> <action>: <old> -> <new>` for every changed cell."""
    lines: list[str] = []
    for key in sorted(set(expected) | set(observed)):
        if key not in observed:
            lines.append(f"- missing state {key}")
            continue
        if key not in expected:
            lines.append(f"+ unexpected state {key}")
            continue
        exp, obs = expected[key], observed[key]
        touched = set(exp["hidden"]) | set(exp["greyed"]) | set(obs["hidden"]) | set(obs["greyed"])
        for action in sorted(touched):
            old, new = _cell(exp, action), _cell(obs, action)
            if old != new:
                lines.append(f"{key} {action}: {old} -> {new}")
    return lines


def _message(diff: list[str]) -> str:
    return "\n".join(diff) + "\n\n" + UPDATE_RULE


class KeymapCharacterizationTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """The board's key surface, observed on the fixture-loaded module."""

    def test_bindings_table_is_unchanged(self):
        diff = _diff_bindings(GOLDEN_BINDINGS, _binding_rows(self.ab.KanbanApp.BINDINGS))
        self.assertFalse(diff, _message(diff))

    def test_check_action_matrix_is_unchanged(self):
        ab = self.ab
        observed: dict[str, dict] = {}

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(200, 48)) as pilot:
                await pilot.pause()
                self.assertEqual(len(app.screen_stack), 1, "precondition: no modal")
                self.assertIsNone(app.active_trail_handle, "precondition: no trail")
                actions = list(dict.fromkeys(b.action for b in ab.KanbanApp.BINDINGS))
                cards = [c for c in app.query(ab.TaskCard)
                         if c.task_data.filename == FOCUS_CARD]
                self.assertEqual(len(cards), 1, f"precondition: one {FOCUS_CARD} card")
                for focus in FOCUS_STATES:
                    if focus == "none":
                        app.set_focus(None)
                    else:
                        cards[0].focus()
                    await pilot.pause()
                    expected_focus = None if focus == "none" else cards[0]
                    self.assertIs(app.focused, expected_focus, f"precondition: {focus}")
                    for flt in FILTERS:
                        # Set directly: `_set_base_filter` would push the trail
                        # selector and start workers, changing the answers.
                        app.base_filter = flt
                        answers = {a: app.check_action(a, None) for a in actions}
                        odd = {a: v for a, v in answers.items()
                               if v is not True and v is not False and v is not None}
                        self.assertEqual(odd, {}, "check_action must answer True/False/None")
                        observed[f"{flt}/{focus}"] = {
                            "hidden": tuple(sorted(a for a, v in answers.items() if v is False)),
                            "greyed": tuple(sorted(a for a, v in answers.items() if v is None)),
                        }
                    app.base_filter = "all"
                self.assertNoLiveWorkers(app)

        asyncio.run(go())
        diff = _diff_matrix(GOLDEN_CHECK_ACTION, observed)
        self.assertFalse(diff, _message(diff))

    def test_trail_view_widget_contract(self):
        from textual.css.query import NoMatches
        from textual.screen import ModalScreen

        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(200, 48)) as pilot:
                await pilot.pause()
                app.query_one("HeaderTitle")
                app.query_one("#board_container")
                app.query_one("#trail_summary").query_one("#trail_summary_body")
                with self.assertRaises(NoMatches):  # the queries discriminate
                    app.query_one("#t1794_no_such_widget")
                self.assertNoLiveWorkers(app)

        asyncio.run(go())
        self.assertTrue(issubclass(ab.LoadingOverlay, ModalScreen))

    def test_real_table_minus_one_row_is_reported(self):
        """Negative control on the REAL observed table, not only on the golden."""
        observed = _binding_rows(self.ab.KanbanApp.BINDINGS)
        index = next(i for i, row in enumerate(observed) if row[1] == "trail_select")
        del observed[index]
        diff = _diff_bindings(GOLDEN_BINDINGS, observed)
        self.assertTrue(any(line.startswith(f"- removed row #{index}:")
                            and "'trail_select'" in line for line in diff), diff)


class GoldenDiffControlTests(unittest.TestCase):
    """The diff helpers discriminate, and the failure message names the rule."""

    def test_identical_tables_have_no_diff(self):
        self.assertEqual(_diff_bindings(GOLDEN_BINDINGS, list(GOLDEN_BINDINGS)), [])
        self.assertEqual(_diff_matrix(GOLDEN_CHECK_ACTION, dict(GOLDEN_CHECK_ACTION)), [])

    def test_changed_row_is_reported(self):
        observed = list(GOLDEN_BINDINGS)
        index = next(i for i, row in enumerate(observed) if row[1] == "trail_move_wave")
        observed[index] = ("W",) + observed[index][1:]
        self.assertEqual(
            _diff_bindings(GOLDEN_BINDINGS, observed),
            [f"~ changed row #{index}: {GOLDEN_BINDINGS[index]!r} -> {observed[index]!r}"])

    def test_reordered_duplicate_key_pair_is_reported(self):
        """Swapping the `r` pair changes which one dispatches — not a no-op."""
        observed = list(GOLDEN_BINDINGS)
        i = next(i for i, row in enumerate(observed) if row[1] == "refresh_board")
        observed[i], observed[i + 1] = observed[i + 1], observed[i]
        self.assertTrue(_diff_bindings(GOLDEN_BINDINGS, observed))

    def test_flipped_cell_is_reported_by_state_and_action(self):
        observed = {k: dict(v) for k, v in GOLDEN_CHECK_ACTION.items()}
        state = observed["bytrail/parent_card"]
        state["hidden"] = tuple(a for a in state["hidden"] if a != "trail_task")
        diff = _diff_matrix(GOLDEN_CHECK_ACTION, observed)
        self.assertEqual(diff, ["bytrail/parent_card trail_task: hidden -> shown"])
        message = _message(diff)
        self.assertIn("bytrail/parent_card trail_task", message)
        self.assertIn("children 5 and 6", message)

    def test_missing_state_is_reported(self):
        observed = dict(GOLDEN_CHECK_ACTION)
        del observed["inflight/none"]
        self.assertEqual(_diff_matrix(GOLDEN_CHECK_ACTION, observed),
                         ["- missing state inflight/none"])

    def test_golden_covers_every_view_and_focus_state(self):
        self.assertEqual(set(GOLDEN_CHECK_ACTION),
                         {f"{f}/{s}" for f in FILTERS for s in FOCUS_STATES})


if __name__ == "__main__":
    unittest.main()
