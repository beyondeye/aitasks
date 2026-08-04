"""Bulk move-to-column command on the board (t1243_7).

`m` moves the marked task(s) — or the focused card — to a destination column in
exactly K writes, input order preserved. It consumes two APIs built for it and
previously unused by production code: `TaskManager.move_tasks_to_column`
(t1243_3, batch + all-or-nothing) and `MarkedSelection` (t1243_6, `space`
marking).

**The model layer is NOT re-tested here.** `tests/test_board_manager_moves.py`
already pins `move_tasks_to_column` for K writes, input order, append
semantics, duplicates, empty input, unknown names, child ids and mixed
refusals. This module covers the *command* layer only:

* **Palette parity.** `KanbanCommandProvider` used to repeat its command list
  verbatim in `discover()` and `search()`; the de-dup onto `_COMMANDS` is the
  precondition for adding two commands to it, and the parity guard is the
  regression that de-dup prevents.
* **The review gate.** Marks deliberately survive a filter pass (t1243_6), so a
  marked card can be hidden. `m` must show the set before acting on it, and
  must **fail closed** rather than silently dropping a mark that no longer
  resolves — dropping it would move a subset of what the user selected.
* **The destination set.** Three filters, each matching an existing board
  contract (transient `unordered`, collapsed columns, the targets' own column).
  Each is asserted with its negative half; a one-directional assertion would
  pass for a list that never filters anything.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402

PARENT = "t9000_parent.md"      # c0, has two children
ALPHA = "t9001_alpha.md"        # c1
BETA = "t9002_beta.md"          # c2
GAMMA = "t9003_gamma.md"        # c3
DELTA = "t9004_delta.md"        # c4
CHILD = "t9000_1_childone.md"   # child of t9000
NUMBERLESS = "t_unparseable.md"  # c0, no parseable task number


def _task(filename, col, idx):
    return SimpleNamespace(filename=filename, board_col=col, board_idx=idx)


def _fake_manager(*, collapsed=(), unordered=(), tasks=None):
    """Manager stub: five configured columns + one stale `column_order` entry.

    The stale `"ghost"` entry has no conf and must never be offered — the same
    trap `_work_report_columns` guards against.
    """
    parents = tasks if tasks is not None else {
        PARENT: _task(PARENT, "c0", 10),
        ALPHA: _task(ALPHA, "c1", 10),
        BETA: _task(BETA, "c2", 10),
        GAMMA: _task(GAMMA, "c3", 10),
        DELTA: _task(DELTA, "c4", 10),
    }
    children = {CHILD: _task(CHILD, "c0", 20)}
    unordered_tasks = list(unordered)

    def get_column_tasks(col_id):
        if col_id == "unordered":
            return unordered_tasks
        return sorted((t for t in parents.values() if t.board_col == col_id),
                      key=lambda t: (t.board_idx, t.filename))

    columns = [{"id": c["id"], "title": c["title"], "color": c["color"]}
               for c in bf.COLUMNS]
    return SimpleNamespace(
        task_datas=parents,
        child_task_datas=children,
        columns=columns,
        column_order=[*bf.COLUMN_ORDER, "ghost"],
        get_column_conf=lambda col_id: next(
            (c for c in columns if c["id"] == col_id), None),
        get_column_tasks=get_column_tasks,
        is_column_collapsed=lambda col_id: col_id in set(collapsed),
        move_tasks_to_column=MagicMock(),
    )


class _MoveTestBase(bf.FixtureBoardTestBase, unittest.TestCase):
    """Fixture tree + board module; a MagicMock app wired to the real methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.KanbanApp = cls.ab.KanbanApp

    def _mock_app(self, manager=None, *, marked=(), focused=None,
                  focused_col=None, base_filter="all"):
        """MagicMock app with the real move methods bound to it.

        Same construction-spy shape as `test_board_work_report.py`: the methods
        under test are the production ones, everything they call out to is a
        recorded double, and no board state is mutated.
        """
        ab = self.ab
        app = MagicMock()
        app._modal_is_active.return_value = False
        app.base_filter = base_filter
        app.manager = manager if manager is not None else _fake_manager()
        app.marked = ab.MarkedSelection(marked)
        app._focused_card.return_value = focused
        # Mirror production: `_get_focused_col_id` returns the focused card's
        # own column, falling back to a focused placeholder. A mock that always
        # returned None would make the gate look stricter than it is.
        if focused_col is None and focused is not None:
            focused_col = focused.column_id
        app._get_focused_col_id.return_value = focused_col
        # A placeholder holds focus only when no card does. Left as a bare
        # MagicMock this returns a truthy stub and the "nothing in focus" gate
        # silently stops being testable.
        app._focused_placeholder.return_value = (
            SimpleNamespace(column_id=focused_col)
            if focused is None and focused_col is not None else None)
        app.push_screen = MagicMock()
        app.notify = MagicMock()
        for name in ("_move_destination_columns", "_column_title", "_board_order",
                     "_reject_stale", "_review_then", "_apply_move_to_column",
                     "action_move_to_column", "action_clear_marks"):
            real = getattr(ab.KanbanApp, name)
            setattr(app, name, (lambda _r=real: (
                lambda *a, **k: _r(app, *a, **k)))())
        return app

    @staticmethod
    def _card(filename, *, is_child=False, col="c0"):
        return SimpleNamespace(is_child=is_child, column_id=col,
                               task_data=SimpleNamespace(filename=filename))

    def _pushed(self, app, index=0):
        """(screen, callback) of the `index`-th push_screen call."""
        return app.push_screen.call_args_list[index].args

    def _notified(self, app) -> str:
        return " | ".join(str(c.args[0]) for c in app.notify.call_args_list)


# --------------------------------------------------------------------------
# 0. Preconditions
# --------------------------------------------------------------------------


class FixtureFactsTests(_MoveTestBase):
    """Fail loudly if the fixture is reshaped, rather than going vacuous."""

    def test_fixture_topology_is_what_these_tests_assume(self):
        mgr = _fake_manager()
        self.assertEqual([t.filename for t in mgr.get_column_tasks("c0")], [PARENT])
        self.assertIn(CHILD, mgr.child_task_datas)
        self.assertNotIn(CHILD, mgr.task_datas,
                         "task_datas must hold PARENTS only — the structural "
                         "exclusion of child rows depends on it")
        self.assertIsNone(mgr.get_column_conf("ghost"),
                          "the stale column_order entry must have no conf")

    def test_real_tree_carries_the_files_the_write_tests_move(self):
        base = self.tasks_dir
        for name in (PARENT, ALPHA, BETA, NUMBERLESS):
            self.assertTrue((base / name).exists(), f"fixture lost {name}")


# --------------------------------------------------------------------------
# 1. Command-palette parity — the regression the de-dup prevents
# --------------------------------------------------------------------------


class CommandPaletteParityTests(_MoveTestBase):
    """`discover()` and `search()` must expose the SAME command set."""

    def _provider(self):
        screen = MagicMock()
        return self.ab.KanbanCommandProvider(screen)

    @staticmethod
    def _drain(agen):
        async def go():
            return [hit async for hit in agen]
        return asyncio.run(go())

    def _discovered(self, provider) -> set:
        return {h.display for h in self._drain(provider.discover())}

    def _searchable(self, provider, displays) -> set:
        """Every display reachable by searching for its own text."""
        found = set()
        for display in displays:
            for hit in self._drain(provider.search(display)):
                text = getattr(hit.match_display, "plain", hit.match_display)
                found.add(str(text))
        return found

    def test_both_surfaces_expose_the_declared_command_set(self):
        provider = self._provider()
        declared = {d for d, _, _ in self.ab.KanbanCommandProvider._COMMANDS}
        self.assertEqual(self._discovered(provider), declared)
        self.assertEqual(self._searchable(provider, declared), declared)

    def test_a_sentinel_reaches_BOTH_surfaces(self):
        """Discriminating control: a re-hardcoded `search()` fails here.

        Patching `_COMMANDS` proves both coroutines actually derive from it. If
        `search()` were reverted to its own literal list, the sentinel would
        appear in `discover()` only and this fails — which the equality test
        above cannot detect, since a hardcoded list can happen to agree.
        """
        ab = self.ab
        sentinel = ("Zz Sentinel Command", "action_sentinel_probe", "probe")
        original = ab.KanbanCommandProvider._COMMANDS
        ab.KanbanCommandProvider._COMMANDS = original + (sentinel,)
        try:
            provider = self._provider()
            self.assertIn(sentinel[0], self._discovered(provider))
            self.assertIn(sentinel[0], self._searchable(provider, [sentinel[0]]))
        finally:
            ab.KanbanCommandProvider._COMMANDS = original

    def test_every_command_action_resolves_on_the_real_app_class(self):
        """`getattr(app, attr)` resolves by NAME, so a typo would only surface
        when the palette is opened. Pin it against the real class."""
        for display, attr, _ in self.ab.KanbanCommandProvider._COMMANDS:
            self.assertTrue(hasattr(self.KanbanApp, attr),
                            f"{display!r} -> KanbanApp.{attr} does not exist")

    def test_the_new_commands_are_declared(self):
        declared = {d for d, _, _ in self.ab.KanbanCommandProvider._COMMANDS}
        self.assertIn("Move Tasks to Column", declared)
        self.assertIn("Clear Selection", declared)


# --------------------------------------------------------------------------
# 2. The two-stage chain
# --------------------------------------------------------------------------


class MoveChainTests(_MoveTestBase):
    """Which screen is pushed, with which arguments, per focus/mark state."""

    def test_focused_card_without_marks_skips_the_review(self):
        app = self._mock_app(focused=self._card(PARENT))
        app.action_move_to_column()
        self.assertEqual(app.push_screen.call_count, 1,
                         "one unambiguous visible target needs no review")
        screen, _ = self._pushed(app)
        self.assertIsInstance(screen, self.ab.ColumnSelectScreen)

    def test_marks_force_the_review_even_with_a_card_focused(self):
        app = self._mock_app(marked={BETA, ALPHA}, focused=self._card(PARENT))
        app.action_move_to_column()
        screen, callback = self._pushed(app)
        self.assertIsInstance(screen, self.ab.MoveTaskSelectScreen)
        self.assertEqual([r[0] for r in screen.rows], [ALPHA, BETA],
                         "marked set in BOARD order (c1 before c2), not the "
                         "filename order MarkedSelection.effective() returns")
        callback([ALPHA, BETA])
        second, _ = self._pushed(app, 1)
        self.assertIsInstance(second, self.ab.ColumnSelectScreen)

    def test_column_focus_reviews_the_whole_column_from_task_datas(self):
        app = self._mock_app(focused=None, focused_col="c0")
        app.action_move_to_column()
        screen, _ = self._pushed(app)
        self.assertIsInstance(screen, self.ab.MoveTaskSelectScreen)
        self.assertEqual([r[0] for r in screen.rows], [PARENT])

    def test_column_focus_with_marks_reviews_the_marks_not_the_column(self):
        app = self._mock_app(marked={GAMMA}, focused=None, focused_col="c0")
        app.action_move_to_column()
        screen, _ = self._pushed(app)
        self.assertEqual([r[0] for r in screen.rows], [GAMMA])

    def test_focused_child_without_marks_refuses_with_a_reason(self):
        app = self._mock_app(focused=self._card(CHILD, is_child=True))
        app.action_move_to_column()
        app.push_screen.assert_not_called()
        self.assertIn("move with their parent", self._notified(app))

    def test_focused_child_with_marks_acts_on_the_marks(self):
        """The one place the gate diverges from plain movement."""
        app = self._mock_app(marked={ALPHA},
                             focused=self._card(CHILD, is_child=True))
        app.action_move_to_column()
        screen, _ = self._pushed(app)
        self.assertEqual([r[0] for r in screen.rows], [ALPHA])

    def test_empty_column_focus_notifies_and_pushes_nothing(self):
        app = self._mock_app(focused=None, focused_col="unordered")
        app.action_move_to_column()
        app.push_screen.assert_not_called()
        self.assertIn("No tasks in Unsorted / Inbox", self._notified(app))

    def test_nothing_focused_and_nothing_marked_is_a_silent_no_op(self):
        app = self._mock_app(focused=None, focused_col=None)
        app.action_move_to_column()
        app.push_screen.assert_not_called()
        app.notify.assert_not_called()

    def test_review_row_labels_carry_column_and_task_number(self):
        app = self._mock_app(marked={ALPHA})
        app.action_move_to_column()
        screen, _ = self._pushed(app)
        self.assertEqual(screen.rows[0][1], "[Col 1] t9001 alpha")

    def test_confirmed_subset_is_what_reaches_the_destination_stage(self):
        app = self._mock_app(marked={ALPHA, BETA, GAMMA})
        app.action_move_to_column()
        _, callback = self._pushed(app)
        callback([ALPHA, GAMMA])                       # BETA excluded
        _, on_col = self._pushed(app, 1)
        on_col("c4")
        app.manager.move_tasks_to_column.assert_called_once_with(
            [ALPHA, GAMMA], "c4")


# --------------------------------------------------------------------------
# 3. Ordering
# --------------------------------------------------------------------------


class MoveOrderingTests(_MoveTestBase):
    """`_board_order` must reproduce the RENDERED sequence."""

    def _order(self, manager, names):
        app = self._mock_app(manager)
        return app._board_order(names)

    def test_sorts_by_column_then_index_then_filename(self):
        mgr = _fake_manager(tasks={
            "t1_a.md": _task("t1_a.md", "c2", 10),
            "t2_b.md": _task("t2_b.md", "c0", 30),
            "t3_c.md": _task("t3_c.md", "c0", 20),
        })
        self.assertEqual(self._order(mgr, ["t1_a.md", "t2_b.md", "t3_c.md"]),
                         ["t3_c.md", "t2_b.md", "t1_a.md"])

    def test_unordered_sorts_before_every_configured_column(self):
        mgr = _fake_manager(tasks={
            "t1_a.md": _task("t1_a.md", "c0", 10),
            "t2_b.md": _task("t2_b.md", "unordered", 10),
        })
        self.assertEqual(self._order(mgr, ["t1_a.md", "t2_b.md"]),
                         ["t2_b.md", "t1_a.md"])

    def test_quoted_board_idx_sorts_numerically(self):
        """`normalize_board_idx` — a hand-quoted "5" must not sort as a string."""
        mgr = _fake_manager(tasks={
            "t1_a.md": _task("t1_a.md", "c0", "5"),
            "t2_b.md": _task("t2_b.md", "c0", 40),
        })
        self.assertEqual(self._order(mgr, ["t2_b.md", "t1_a.md"]),
                         ["t1_a.md", "t2_b.md"])

    def test_a_target_in_a_COLLAPSED_column_sorts_where_it_renders(self):
        """Discriminating control for the full-column ranking.

        Ranking off `_move_destination_columns()` (which drops collapsed
        columns) would push this target to the end. Every other ordering
        assertion in this class would still pass.
        """
        mgr = _fake_manager(collapsed=("c0",), tasks={
            "t1_a.md": _task("t1_a.md", "c0", 10),
            "t2_b.md": _task("t2_b.md", "c4", 10),
        })
        self.assertEqual(self._order(mgr, ["t2_b.md", "t1_a.md"]),
                         ["t1_a.md", "t2_b.md"])

    def test_a_target_in_the_REDUNDANT_column_sorts_where_it_renders(self):
        """Second control: the destination list also drops the shared column."""
        mgr = _fake_manager(tasks={
            "t1_a.md": _task("t1_a.md", "c0", 10),
            "t2_b.md": _task("t2_b.md", "c0", 20),
        })
        self.assertEqual(self._order(mgr, ["t2_b.md", "t1_a.md"]),
                         ["t1_a.md", "t2_b.md"])

    def test_unresolvable_name_sorts_last_without_raising(self):
        mgr = _fake_manager()
        self.assertEqual(self._order(mgr, ["gone.md", ALPHA]),
                         [ALPHA, "gone.md"])


# --------------------------------------------------------------------------
# 4. Destination set — one test per filter, each with its negative half
# --------------------------------------------------------------------------


class MoveDestinationTests(_MoveTestBase):
    """`_move_destination_columns` applies three filters, all load-bearing."""

    def _dests(self, manager, filenames=()):
        app = self._mock_app(manager)
        return [c["id"] for c in app._move_destination_columns(filenames)]

    def test_unordered_is_offered_first_only_when_it_has_tasks(self):
        with_tasks = _fake_manager(unordered=[_task("t7_u.md", "unordered", 10)])
        self.assertEqual(self._dests(with_tasks)[0], "unordered")
        self.assertNotIn("unordered", self._dests(_fake_manager()))

    def test_unordered_is_omitted_when_collapsed(self):
        mgr = _fake_manager(collapsed=("unordered",),
                            unordered=[_task("t7_u.md", "unordered", 10)])
        self.assertNotIn("unordered", self._dests(mgr))

    def test_a_collapsed_column_is_omitted_and_an_expanded_one_is_offered(self):
        self.assertNotIn("c2", self._dests(_fake_manager(collapsed=("c2",))))
        self.assertIn("c2", self._dests(_fake_manager()))

    def test_destinations_match_where_lateral_movement_can_LAND(self):
        """Parity with `_move_task_lateral`, which steps OVER collapsed columns.

        Reproduces that helper's own column list, then applies its skip rule —
        the set `shift+left/right` can land on must equal the set `m` offers.
        """
        for collapsed in ((), ("c2",), ("c0", "c4")):
            mgr = _fake_manager(collapsed=collapsed,
                                unordered=[_task("t7_u.md", "unordered", 10)])
            lateral = ["unordered", *mgr.column_order]
            landable = {c for c in lateral
                        if not mgr.is_column_collapsed(c)
                        and (c == "unordered" or mgr.get_column_conf(c))}
            self.assertEqual(set(self._dests(mgr)), landable,
                             f"parity broke with collapsed={collapsed}")

    def test_the_shared_column_is_omitted_when_ALL_targets_sit_in_it(self):
        mgr = _fake_manager()
        self.assertNotIn("c1", self._dests(mgr, [ALPHA]))

    def test_the_shared_column_is_KEPT_when_targets_span_two_columns(self):
        """Consolidation is a real move — only a pure no-op is filtered out."""
        mgr = _fake_manager()
        dests = self._dests(mgr, [ALPHA, BETA])
        self.assertIn("c1", dests)
        self.assertIn("c2", dests)

    def test_a_stale_column_order_entry_is_not_offered(self):
        self.assertNotIn("ghost", self._dests(_fake_manager()))

    def test_all_columns_collapsed_notifies_and_pushes_no_picker(self):
        mgr = _fake_manager(collapsed=bf.COLUMN_ORDER)
        app = self._mock_app(mgr, focused=self._card(PARENT))
        app.action_move_to_column()
        app.push_screen.assert_not_called()
        self.assertIn("Nowhere to move to", self._notified(app))


# --------------------------------------------------------------------------
# 5. Cancellation — None and [] are different things
# --------------------------------------------------------------------------


class MoveCancellationTests(_MoveTestBase):
    """Neither cancellation path may write, and they must not be conflated."""

    def test_escape_at_the_review_is_silent_and_writes_nothing(self):
        app = self._mock_app(marked={ALPHA})
        app.action_move_to_column()
        _, callback = self._pushed(app)
        callback(None)
        self.assertEqual(app.push_screen.call_count, 1)
        app.notify.assert_not_called()
        app.manager.move_tasks_to_column.assert_not_called()

    def test_confirming_with_nothing_checked_notifies_and_writes_nothing(self):
        app = self._mock_app(marked={ALPHA})
        app.action_move_to_column()
        _, callback = self._pushed(app)
        callback([])
        self.assertEqual(app.push_screen.call_count, 1)
        self.assertIn("No tasks selected", self._notified(app))
        app.manager.move_tasks_to_column.assert_not_called()

    def test_the_two_cancellations_produce_different_output(self):
        esc = self._mock_app(marked={ALPHA})
        esc.action_move_to_column()
        self._pushed(esc)[1](None)

        empty = self._mock_app(marked={ALPHA})
        empty.action_move_to_column()
        self._pushed(empty)[1]([])

        self.assertNotEqual(self._notified(esc), self._notified(empty))

    def test_escape_at_the_column_picker_writes_nothing(self):
        app = self._mock_app(focused=self._card(PARENT))
        app.action_move_to_column()
        _, on_col = self._pushed(app)
        on_col(None)
        app.manager.move_tasks_to_column.assert_not_called()

    def test_marks_survive_a_cancelled_flow(self):
        app = self._mock_app(marked={ALPHA, BETA})
        app.action_move_to_column()
        self._pushed(app)[1](None)
        self.assertEqual(app.marked.marked, {ALPHA, BETA})


# --------------------------------------------------------------------------
# 6. Stale selection — fail closed, never a partial application
# --------------------------------------------------------------------------


class MoveStaleSelectionTests(_MoveTestBase):
    """A mark that no longer resolves stops the whole operation."""

    def _stale_app(self, **kw):
        mgr = _fake_manager()
        return self._mock_app(mgr, marked={ALPHA, "t9999_gone.md"}, **kw)

    def test_a_stale_mark_stops_before_the_picker(self):
        app = self._stale_app()
        app.action_move_to_column()
        app.push_screen.assert_not_called()

    def test_the_stale_name_is_reported(self):
        app = self._stale_app()
        app.action_move_to_column()
        self.assertIn("t9999_gone.md", self._notified(app))
        self.assertIn("stale", self._notified(app).lower())

    def test_the_VALID_member_is_not_moved(self):
        """The partial application this guard exists to prevent."""
        app = self._stale_app()
        app.action_move_to_column()
        app.manager.move_tasks_to_column.assert_not_called()

    def test_marks_are_RETAINED_so_a_refresh_can_prune_them(self):
        app = self._stale_app()
        app.action_move_to_column()
        self.assertEqual(app.marked.marked, {ALPHA, "t9999_gone.md"},
                         "clearing here would destroy a selection the user may "
                         "still want after `r`")

    def test_the_focused_card_path_is_guarded_too(self):
        mgr = _fake_manager()
        app = self._mock_app(mgr, focused=self._card("t9999_gone.md"))
        app.action_move_to_column()
        app.push_screen.assert_not_called()
        self.assertIn("t9999_gone.md", self._notified(app))

    def test_a_child_filename_gets_the_CHILD_message_not_the_stale_one(self):
        app = self._mock_app(_fake_manager(), marked={CHILD})
        app.action_move_to_column()
        app.push_screen.assert_not_called()
        message = self._notified(app)
        self.assertIn("move with their parent", message)
        self.assertNotIn("stale", message.lower())

    def test_a_fully_resolvable_selection_passes_the_guard(self):
        """Control: the guard must not block the normal path."""
        app = self._mock_app(_fake_manager(), marked={ALPHA, BETA})
        self.assertFalse(app._reject_stale([ALPHA, BETA]))
        app.notify.assert_not_called()


# --------------------------------------------------------------------------
# 7. Post-review refusal (TOCTOU) — the branch's only reachable trigger
# --------------------------------------------------------------------------


class MoveRefusalTests(_MoveTestBase):
    """A task removed WHILE the user sits in the modals is refused wholesale.

    `_reject_stale` screens the selection before the dialogs open, so this is
    the one window left: the confirmed filename list is captured in a closure,
    and the auto-refresh timer (or another session) can drop a task from
    `task_datas` before the column callback fires. Driven deterministically by
    mutating the manager between the two callbacks — no timer, no sleep.
    """

    def test_a_task_removed_between_the_callbacks_refuses_everything(self):
        mgr = _fake_manager()
        mgr.move_tasks_to_column = lambda names, col: self.ab.MoveResult(
            refused=tuple((n, "not_a_parent_task") for n in names
                          if n not in mgr.task_datas))
        app = self._mock_app(mgr, marked={ALPHA, BETA})
        app.action_move_to_column()
        _, on_tasks = self._pushed(app)
        on_tasks([ALPHA, BETA])

        del mgr.task_datas[BETA]                    # the TOCTOU window

        _, on_col = self._pushed(app, 1)
        on_col("c4")
        message = self._notified(app)
        self.assertIn("refused", message.lower())
        self.assertIn(BETA, message)
        app.refresh_columns.assert_not_called()

    def test_a_refusal_leaves_the_marks_alone(self):
        mgr = _fake_manager()
        mgr.move_tasks_to_column = lambda names, col: self.ab.MoveResult(
            refused=((BETA, "not_a_parent_task"),))
        app = self._mock_app(mgr, marked={ALPHA, BETA})
        app.action_move_to_column()
        self._pushed(app)[1]([ALPHA, BETA])
        del mgr.task_datas[BETA]
        self._pushed(app, 1)[1]("c4")
        self.assertEqual(app.marked.marked, {ALPHA, BETA})

    def test_a_successful_move_clears_the_marks_and_refreshes(self):
        """Control: the refusal branch must not swallow the success path.

        The stub **mutates `board_col`**, exactly as the real API does. Without
        that the source-column snapshot could be taken after the move and this
        test would still pass — a negative control proved it did.
        """
        mgr = _fake_manager()

        def _move(names, col):
            for n in names:
                mgr.task_datas[n].board_col = col
            return self.ab.MoveResult(moved=tuple(names))

        mgr.move_tasks_to_column = _move
        app = self._mock_app(mgr, marked={ALPHA, BETA})
        app.action_move_to_column()
        self._pushed(app)[1]([ALPHA, BETA])
        self._pushed(app, 1)[1]("c4")
        self.assertEqual(app.marked.marked, set())
        app.refresh_columns.assert_called_once()
        cols, _ = app.refresh_columns.call_args.args[0], None
        self.assertEqual(cols, {"c1", "c2", "c4"},
                         "source columns are snapshot BEFORE the move mutates "
                         "board_col, plus the destination")
        self.assertIn("Moved 2 task(s) to Col 4", self._notified(app))


# --------------------------------------------------------------------------
# 8. Footer / binding gating
# --------------------------------------------------------------------------


class MoveGatingTests(_MoveTestBase):
    """`check_action("move_to_column", …)` — False hides, None only greys."""

    def _check(self, **kw):
        app = self._mock_app(**kw)
        return self.KanbanApp.check_action(app, "move_to_column", None)

    def test_hidden_in_every_derived_view(self):
        for view in ("inflight", "bytopic", "bytrail"):
            with self.subTest(view=view):
                self.assertIs(
                    self._check(base_filter=view, focused=self._card(PARENT)),
                    False, "must be False (hidden), not None (greyed)")

    def test_visible_with_a_parent_card_focused(self):
        self.assertIs(self._check(focused=self._card(PARENT)), True)

    def test_visible_with_a_column_placeholder_focused(self):
        self.assertIs(self._check(focused=None, focused_col="c0"), True)

    def test_hidden_with_nothing_in_focus_and_nothing_marked(self):
        self.assertIs(self._check(focused=None, focused_col=None), False)

    def test_hidden_on_a_focused_child_with_no_marks(self):
        self.assertIs(
            self._check(focused=self._card(CHILD, is_child=True),
                        focused_col="c0"),
            False)

    def test_VISIBLE_on_a_focused_child_when_something_is_marked(self):
        """The deliberate divergence from the plain movement gate."""
        self.assertIs(
            self._check(marked={ALPHA},
                        focused=self._card(CHILD, is_child=True),
                        focused_col="c0"),
            True)

    def test_marks_beat_an_empty_focus(self):
        self.assertIs(
            self._check(marked={ALPHA}, focused=None, focused_col=None), True)

    def test_footer_surface_follows_the_gate(self):
        """Live binding surface, not just the predicate (t1243_6's idiom)."""
        ab = self.ab

        def footer(app):
            return {a.binding.action for a in app.screen.active_bindings.values()}

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                # Nothing holds focus at boot, so the gate hides `m` — assert
                # that first, or the "shown" half below could pass for a gate
                # that never hides anything.
                self.assertNotIn("move_to_column", footer(app))

                card = next(c for c in app.query(ab.TaskCard) if not c.is_child)
                card.focus()
                await pilot.pause()
                self.assertIn("move_to_column", footer(app))

                app._set_base_filter("bytopic")
                await pilot.pause()
                self.assertNotIn("move_to_column", footer(app))

        asyncio.run(go())

    def test_the_gate_issues_AT_MOST_ONE_dom_query(self):
        """`check_action` runs once per binding on every `refresh_bindings()`
        — i.e. on every focus change during a move — and `_focused_card()` is a
        whole-board `query("TaskCard:focus")`. The first draft called
        `_get_focused_col_id()` (which queries) *and* `_focused_card()`,
        doubling the cost of the hottest gate on the board and regressing
        `test_board_movement`'s attribution benchmark. One query, no more.
        """
        app = self._mock_app(focused=self._card(PARENT))
        self.KanbanApp.check_action(app, "move_to_column", None)
        self.assertLessEqual(app._focused_card.call_count, 1)
        self.assertEqual(app._get_focused_col_id.call_count, 0,
                         "_get_focused_col_id calls _focused_card internally — "
                         "using it here reintroduces the double query")

    def test_a_marked_set_short_circuits_before_any_dom_query(self):
        """The cheap path: with marks, focus is irrelevant, so don't look."""
        app = self._mock_app(marked={ALPHA}, focused=self._card(PARENT))
        self.assertIs(self.KanbanApp.check_action(app, "move_to_column", None),
                      True)
        self.assertEqual(app._focused_card.call_count, 0)

    def test_the_m_binding_is_declared_once(self):
        keys = [b.key for b in self.KanbanApp.BINDINGS if getattr(b, "key", None)]
        self.assertEqual(keys.count("m"), 1)
        binding = next(b for b in self.KanbanApp.BINDINGS
                       if getattr(b, "key", None) == "m")
        self.assertEqual(binding.action, "move_to_column")


# --------------------------------------------------------------------------
# 9. Action guards — the palette bypasses check_action entirely
# --------------------------------------------------------------------------


class FocusedCardCostTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """`_focused_card()` is an attribute read, not a whole-board query.

    Lives here because t1243_7 is what surfaced it: adding the 28th call per
    footer sweep tipped `test_board_movement`'s attribution benchmark over its
    cross-run threshold. `check_action` runs once per binding on every
    `refresh_bindings()`, and ~10 of its gates call this helper — measured at
    27 whole-board walks and 59 ms per sweep before the change, 0 and 0.05 ms
    after.
    """

    def test_it_agrees_with_screen_focused_in_both_directions(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                card = next(c for c in app.query(ab.TaskCard) if not c.is_child)
                card.focus()
                await pilot.pause()
                self.assertIs(app._focused_card(), card)

                # Negative half: a non-TaskCard with focus must yield None, or
                # the isinstance narrowing is not doing its job.
                app.query_one("#search_box").focus()
                await pilot.pause()
                self.assertIsNone(app._focused_card())

        asyncio.run(go())

    def test_a_footer_sweep_issues_ZERO_whole_board_focus_queries(self):
        ab = self.ab
        seen = []

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                card = next(c for c in app.query(ab.TaskCard) if not c.is_child)
                card.focus()
                await pilot.pause()

                real = ab.KanbanApp.query

                def counting(self, selector=None):
                    if selector == "TaskCard:focus":
                        seen.append(selector)
                    return (real(self, selector) if selector is not None
                            else real(self))

                ab.KanbanApp.query = counting
                try:
                    for binding in app.BINDINGS:
                        if getattr(binding, "action", None):
                            app.check_action(binding.action, None)
                finally:
                    ab.KanbanApp.query = real

        asyncio.run(go())
        self.assertEqual(seen, [],
                         f"{len(seen)} whole-board 'TaskCard:focus' queries in "
                         "one footer sweep — _focused_card must stay O(1)")


class MoveActionGuardTests(_MoveTestBase):
    """A binding gate is not an action guard."""

    def test_the_view_gate_is_re_checked_inside_the_action(self):
        for view in ("inflight", "bytopic", "bytrail"):
            with self.subTest(view=view):
                app = self._mock_app(base_filter=view,
                                     focused=self._card(PARENT))
                app.action_move_to_column()
                app.push_screen.assert_not_called()

    def test_an_active_modal_blocks_the_action(self):
        app = self._mock_app(focused=self._card(PARENT))
        app._modal_is_active.return_value = True
        app.action_move_to_column()
        app.push_screen.assert_not_called()

    def test_clear_marks_empties_the_set_and_repaints_only_those_cards(self):
        app = self._mock_app(marked={ALPHA, BETA})
        cards = [self._card(ALPHA), self._card(GAMMA)]
        app.query = MagicMock(return_value=cards)
        app.action_clear_marks()
        self.assertEqual(app.marked.marked, set())
        repainted = [c.args[0] for c in app._repaint_card_mark.call_args_list]
        self.assertEqual(repainted, [cards[0]],
                         "only previously-marked cards need a repaint")

    def test_clear_marks_on_an_empty_selection_says_so(self):
        app = self._mock_app()
        app.query = MagicMock(return_value=[])
        app.action_clear_marks()
        self.assertIn("Nothing marked", self._notified(app))
        app._repaint_card_mark.assert_not_called()

    def test_clear_marks_is_blocked_by_a_modal(self):
        app = self._mock_app(marked={ALPHA})
        app._modal_is_active.return_value = True
        app.action_clear_marks()
        self.assertEqual(app.marked.marked, {ALPHA})


# --------------------------------------------------------------------------
# 10. Real writes — exactly K files, in the presented order
# --------------------------------------------------------------------------


class MoveWriteTests(bf.FixtureBoardTestBase, bf.PristineTreeMixin,
                     unittest.TestCase):
    """The only class that touches the tree. K writes, exact changed-path set."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._snapshot_pristine()

    def _drive(self, marks, destination, *, keep=None):
        """Boot, mark, run the chain to completion; return the changed paths."""
        ab = self.ab
        tree = self.tree
        result = {}

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                pushed = []
                app.push_screen = lambda screen, cb=None: pushed.append((screen, cb))
                for name in marks:
                    app.marked.toggle(name)

                before = bf.snapshot(tree)
                app.action_move_to_column()
                review, on_tasks = pushed[0]
                result["rows"] = [r[0] for r in review.rows]
                on_tasks(keep if keep is not None else result["rows"])
                _, on_col = pushed[1]
                on_col(destination)
                await pilot.pause()
                await pilot.pause()
                result["diff"] = bf.diff_snapshots(before, bf.snapshot(tree))
                result["marked"] = set(app.marked.marked)
                result["cols"] = {
                    n: app.manager.task_datas[n].board_col
                    for n in app.manager.task_datas}
                result["order"] = [t.filename
                                   for t in app.manager.get_column_tasks(destination)]

        asyncio.run(go())
        return result

    def test_K_marks_write_exactly_K_files_and_nothing_else(self):
        out = self._drive([ALPHA, BETA], "c4")
        self.assertEqual(out["diff"]["changed"],
                         {f"aitasks/{ALPHA}", f"aitasks/{BETA}"})
        self.assertEqual(out["diff"]["added"], set())
        self.assertEqual(out["diff"]["removed"], set())

    def test_the_destination_sequence_matches_the_presented_sequence(self):
        out = self._drive([BETA, ALPHA], "c4")
        self.assertEqual(out["rows"], [ALPHA, BETA],
                         "presented in board order (c1 then c2)")
        self.assertEqual(out["order"][-2:], [ALPHA, BETA],
                         "and they land in that same order")

    def test_an_excluded_row_is_not_moved_and_not_written(self):
        out = self._drive([ALPHA, BETA], "c4", keep=[ALPHA])
        self.assertEqual(out["diff"]["changed"], {f"aitasks/{ALPHA}"})
        self.assertEqual(out["cols"][BETA], "c2")

    def test_marks_are_cleared_after_a_successful_move(self):
        out = self._drive([ALPHA, BETA], "c4")
        self.assertEqual(out["marked"], set())

    def test_consolidation_into_a_column_a_target_already_occupies(self):
        """Targets spanning c1 and c2 moved into c2 — the one path where a
        target's own column is a legal destination."""
        out = self._drive([ALPHA, BETA], "c2")
        self.assertEqual(out["diff"]["changed"],
                         {f"aitasks/{ALPHA}", f"aitasks/{BETA}"})
        self.assertEqual(out["order"][-2:], [ALPHA, BETA])
        self.assertEqual(out["cols"][ALPHA], "c2")

    def test_the_numberless_file_is_listed_by_filename(self):
        """`_parse_filename` returns no number for it; the label falls back."""
        out = self._drive([NUMBERLESS], "c4")
        self.assertEqual(out["cols"][NUMBERLESS], "c4")
        self.assertEqual(out["diff"]["changed"], {f"aitasks/{NUMBERLESS}"})


if __name__ == "__main__":
    unittest.main()
