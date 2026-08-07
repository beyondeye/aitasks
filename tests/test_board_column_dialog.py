"""Board ad-hoc column-management dialog (t1377_5).

`e` opens one dialog covering reorder / add / edit / delete / merge, and it is
the **first and only** consumer of `TaskManager.merge_columns` (t1377_4, which
landed the engine with zero call sites).

**The engine layer is NOT re-tested here.** `tests/test_board_column_manage.py`
already pins `merge_columns` headlessly across happy paths, refusals, both
metadata write boundaries, and the whole partial-failure matrix. This module
covers the *dialog* layer only:

* **The pre-phase characterization** (`CharacterizeColumnEditPathTests`) pins the
  behaviour of the existing column modals *before* `_apply_column_edit` is
  extracted out of `_handle_column_edit_result`. Nothing drove `ColumnEditScreen`
  or `DeleteColumnConfirmScreen` through a test before this task, and the header
  pencil button shares that code — so the extraction had no safety net.
* **The gate.** `e` is board-scoped, not card-scoped. It must be hidden in the
  three derived views and must stay available with *nothing focused*, which is
  what separates it from `w`'s column-scoped gate.
* **The reporting contract.** `MergeResult` distinguishes `refused` (nothing
  written) from `failed` (partial progress), and one of its sentinels means the
  merge *did* land. A dialog that branches on `complete` alone reports all three
  the same way — which is the specific failure the sentinel tests exist to catch.
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


def _fake_manager():
    """Manager double with the column-config API the dialog calls.

    `column_order` carries a stale `"ghost"` entry with no matching `columns`
    definition — the renderer and `load_columns()` both drop such an entry
    silently, so the dialog must not offer it either.
    """
    columns = [{"id": c["id"], "title": c["title"], "color": c["color"]}
               for c in bf.COLUMNS]
    unordered_tasks = []
    per_column = {"c0": ["t9000_parent.md"], "c1": ["t9001_alpha.md"]}

    def get_column_tasks(col_id):
        if col_id == "unordered":
            return list(unordered_tasks)
        return [SimpleNamespace(filename=n, board_col=col_id, board_idx=10)
                for n in per_column.get(col_id, [])]

    mgr = SimpleNamespace(
        columns=columns,
        column_order=[*bf.COLUMN_ORDER, "ghost"],
        get_column_conf=lambda col_id: next(
            (c for c in columns if c["id"] == col_id), None),
        get_column_tasks=get_column_tasks,
        is_column_collapsed=lambda col_id: False,
        add_column=MagicMock(),
        update_column=MagicMock(),
        delete_column=MagicMock(),
        merge_columns=MagicMock(),
        save_metadata=MagicMock(),
    )
    mgr._unordered_tasks = unordered_tasks
    return mgr


class _ColumnDialogBase(bf.FixtureBoardTestBase, unittest.TestCase):
    """Fixture tree + board module; a MagicMock app wired to the real methods."""

    #: Every `KanbanApp` method these tests exercise for real. Bound onto the
    #: mock app so the code under test is production code and everything it
    #: calls out to is a recorded double.
    #: `_apply_column_edit` MUST be here. Left to the auto-MagicMock it returns
    #: a truthy stub, so `_handle_column_edit_result`'s "changed?" branch always
    #: fires and the cancelled-edit case silently stops being testable.
    _REAL_METHODS = (
        "_apply_column_edit", "_handle_column_edit_result",
        "action_add_column", "action_edit_column", "action_delete_column",
        "open_column_edit", "_work_report_columns",
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.KanbanApp = cls.ab.KanbanApp

    def _mock_app(self, manager=None, *, base_filter="all", extra_methods=()):
        ab = self.ab
        app = MagicMock()
        app._modal_is_active.return_value = False
        app.base_filter = base_filter
        app.manager = manager if manager is not None else _fake_manager()
        app.push_screen = MagicMock()
        app.notify = MagicMock()
        app.refresh_board = MagicMock()
        for name in (*self._REAL_METHODS, *extra_methods):
            real = getattr(ab.KanbanApp, name, None)
            if real is None:
                continue
            setattr(app, name, (lambda _r=real: (
                lambda *a, **k: _r(app, *a, **k)))())
        return app

    def _pushed(self, app, index=0):
        """(screen, callback) of the `index`-th push_screen call."""
        args = app.push_screen.call_args_list[index].args
        return (args[0], args[1] if len(args) > 1 else None)

    def _notified(self, app):
        """[(message, severity)] for every notify call, severity defaulted."""
        return [(str(c.args[0]), c.kwargs.get("severity", "information"))
                for c in app.notify.call_args_list]

    def _run(self, coro_factory):
        asyncio.run(coro_factory())


# --------------------------------------------------------------------------
# Pre-phase (risk mitigation): characterize the existing column-edit path
# --------------------------------------------------------------------------


class CharacterizeColumnEditPathTests(_ColumnDialogBase):
    """Pin the CURRENT add / edit / delete behaviour before it is re-parented.

    `_apply_column_edit` is extracted out of `_handle_column_edit_result` so the
    new dialog can mutate without recomposing the board underneath itself. That
    handler is also the live path for the column-header pencil button
    (`open_column_edit`) and for three command-palette entries, and **nothing
    exercised it before this task** — so these tests are the baseline the
    extraction must not move.

    Mitigation `characterize_column_edit_path` (p1377_5 pre-phase).
    """

    def test_edit_result_updates_the_column_and_refreshes_once(self):
        app = self._mock_app()
        app._handle_column_edit_result(("edit", "c1", "Renamed", "red"))
        # The id is passed TWICE — update_column's rename branch is deliberately
        # unreachable from the UI (t1377_5 scope decision). If a later change
        # makes the two ids differ, every member task's `boardcol` gets rewritten
        # as a side effect of a title edit, and this assertion is the tripwire.
        app.manager.update_column.assert_called_once_with("c1", "c1", "Renamed", "red")
        app.manager.add_column.assert_not_called()
        app.refresh_board.assert_called_once()

    def test_add_result_adds_the_column_and_refreshes_once(self):
        app = self._mock_app()
        app._handle_column_edit_result(("add", "newcol", "New Col", "blue"))
        app.manager.add_column.assert_called_once_with("newcol", "New Col", "blue")
        app.manager.update_column.assert_not_called()
        app.refresh_board.assert_called_once()

    def test_a_cancelled_edit_changes_nothing(self):
        app = self._mock_app()
        app._handle_column_edit_result(None)
        app.manager.add_column.assert_not_called()
        app.manager.update_column.assert_not_called()
        app.refresh_board.assert_not_called()

    def test_header_pencil_button_opens_the_edit_dialog_for_that_column(self):
        app = self._mock_app()
        app.open_column_edit("c2")
        screen, callback = self._pushed(app)
        self.assertIsInstance(screen, self.ab.ColumnEditScreen)
        self.assertEqual(screen.mode, "edit")
        self.assertEqual(screen.col_id, "c2")
        # The callback must be the shared handler, so the pencil button and the
        # palette stay on one code path.
        callback(("edit", "c2", "T", "red"))
        app.manager.update_column.assert_called_once_with("c2", "c2", "T", "red")

    def test_add_column_action_opens_the_dialog_in_add_mode(self):
        app = self._mock_app()
        app.action_add_column()
        screen, _ = self._pushed(app)
        self.assertIsInstance(screen, self.ab.ColumnEditScreen)
        self.assertEqual(screen.mode, "add")
        self.assertIsNone(screen.col_id)

    def test_delete_action_confirms_with_the_real_task_count(self):
        app = self._mock_app()
        app.action_delete_column()
        picker, on_selected = self._pushed(app)
        self.assertIsInstance(picker, self.ab.ColumnSelectScreen)

        on_selected("c0")
        confirm, on_confirmed = self._pushed(app, 1)
        self.assertIsInstance(confirm, self.ab.DeleteColumnConfirmScreen)
        self.assertEqual(confirm.task_count, 1,
                         "the confirmation must name how many tasks drain to "
                         "Unsorted, not a placeholder")

        on_confirmed(True)
        app.manager.delete_column.assert_called_once_with("c0")
        app.refresh_board.assert_called_once()

    def test_declining_the_delete_confirmation_deletes_nothing(self):
        app = self._mock_app()
        app.action_delete_column()
        _, on_selected = self._pushed(app)
        on_selected("c0")
        _, on_confirmed = self._pushed(app, 1)
        on_confirmed(False)
        app.manager.delete_column.assert_not_called()
        app.refresh_board.assert_not_called()

    def test_edit_screen_in_edit_mode_preserves_the_column_id_verbatim(self):
        """`ColumnEditScreen.save()` never re-slugs an existing id.

        Driven through a real mounted screen rather than asserted on source:
        `save()` reads its Input, so a mounted widget is the only honest probe.
        """
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                col_id = app.manager.column_order[0]
                result = {}

                def capture(value):
                    result["dismissed"] = value

                app.push_screen(
                    ab.ColumnEditScreen(app.manager, col_id=col_id, mode="edit"),
                    capture)
                await pilot.pause()
                screen = app.screen
                screen.query_one("#col_title_input", ab.Input).value = "Totally New"
                screen.save()
                await pilot.pause()

            self.assertEqual(result["dismissed"][0], "edit")
            self.assertEqual(result["dismissed"][1], col_id,
                             "a title change must NOT re-slug the column id")
            self.assertEqual(result["dismissed"][2], "Totally New")

        self._run(go)


# --------------------------------------------------------------------------
# 1. The binding and its gate
# --------------------------------------------------------------------------


class ColumnManageBindingTests(_ColumnDialogBase):
    """`e` is declared once, footer-visible, and board-scoped."""

    def test_the_e_binding_is_declared_once(self):
        keys = [b.key for b in self.KanbanApp.BINDINGS if getattr(b, "key", None)]
        self.assertEqual(keys.count("e"), 1)
        binding = next(b for b in self.KanbanApp.BINDINGS
                       if getattr(b, "key", None) == "e")
        self.assertEqual(binding.action, "column_manage")

    def test_the_binding_is_footer_visible(self):
        binding = next(b for b in self.KanbanApp.BINDINGS
                       if getattr(b, "key", None) == "e")
        self.assertTrue(binding.show,
                        "t1418's multi-row footer removed the width excuse, and "
                        "tui_conventions now requires new bindings to be shown")
        self.assertTrue(binding.description.strip(),
                        "a shown key with no label renders as a bare glyph")

    def _check(self, base_filter):
        app = self._mock_app(base_filter=base_filter)
        return self.KanbanApp.check_action(app, "column_manage", None)

    def test_hidden_in_every_derived_view(self):
        for view in ("inflight", "bytopic", "bytrail"):
            with self.subTest(view=view):
                self.assertIs(
                    self._check(view), False,
                    "must be False (removed from active_bindings), not None "
                    "(which only greys it in the footer)")

    def test_available_in_the_kanban_views(self):
        for view in ("all", "locked", "free"):
            with self.subTest(view=view):
                self.assertIsNot(self._check(view), False)

    def test_available_with_nothing_focused(self):
        """The discriminating test against reusing `w`'s column-scoped gate.

        `work_report` additionally requires `_get_focused_col_id()`; copying that
        would make `e` dead on an empty or filter-emptied board — exactly when a
        user needs "Add Column".
        """
        app = self._mock_app()
        app._focused_card.return_value = None
        app._focused_placeholder.return_value = None
        app._get_focused_col_id.return_value = None
        self.assertIsNot(
            self.KanbanApp.check_action(app, "column_manage", None), False)

    def test_the_gate_issues_no_dom_query(self):
        """`check_action` runs once per binding on every `refresh_bindings()`.

        t1243_7 measured that path at 59.08 ms before it was made O(1); this gate
        must not put a query back on it.
        """
        app = self._mock_app()
        self.KanbanApp.check_action(app, "column_manage", None)
        self.assertEqual(app._focused_card.call_count, 0)
        self.assertEqual(app._get_focused_col_id.call_count, 0)


class PaletteBypassTests(_ColumnDialogBase):
    """The palette resolves `action_*` by NAME and never calls `check_action`.

    So hiding `e` in the derived views is only half the gate: without the same
    base-filter rejection inside the shared opener, Ctrl+P -> "Manage Columns"
    is an unguarded back door into the persistent-column editor from a view that
    renders derived lanes. Same lesson `action_move_to_column` records at its
    own re-check (t1243_7).
    """

    _DERIVED = ("inflight", "bytopic", "bytrail")

    def _app_in(self, view):
        return self._mock_app(base_filter=view,
                              extra_methods=("_open_column_manage",
                                             "action_column_manage",
                                             "action_merge_columns"))

    def test_the_palette_actions_are_declared_and_resolvable(self):
        declared = dict((d, a) for d, a, _ in
                        self.ab.KanbanCommandProvider._COMMANDS)
        self.assertEqual(declared.get("Manage Columns"), "action_column_manage")
        self.assertEqual(declared.get("Merge Columns"), "action_merge_columns")
        for attr in ("action_column_manage", "action_merge_columns"):
            self.assertTrue(hasattr(self.KanbanApp, attr))

    def test_manage_is_rejected_in_every_derived_view(self):
        for view in self._DERIVED:
            with self.subTest(view=view):
                app = self._app_in(view)
                app.action_column_manage()
                app.push_screen.assert_not_called()
                self.assertTrue(
                    self._notified(app),
                    "a palette command the user clicked must explain why it "
                    "did nothing, not silently no-op")
                self.assertEqual(self._notified(app)[0][1], "warning")

    def test_merge_is_rejected_in_every_derived_view(self):
        for view in self._DERIVED:
            with self.subTest(view=view):
                app = self._app_in(view)
                app.action_merge_columns()
                app.push_screen.assert_not_called()

    def test_both_actions_still_open_in_the_kanban_views(self):
        ab = self.ab
        for view in ("all", "locked", "free"):
            for action in ("action_column_manage", "action_merge_columns"):
                with self.subTest(view=view, action=action):
                    app = self._app_in(view)
                    getattr(app, action)()
                    screen, _ = self._pushed(app)
                    self.assertIsInstance(screen, ab.ColumnManageScreen)

    def test_merge_entry_point_starts_in_the_merge_flow(self):
        app = self._app_in("all")
        app.action_merge_columns()
        screen, _ = self._pushed(app)
        self.assertTrue(screen._start_in_merge)
        app2 = self._app_in("all")
        app2.action_column_manage()
        screen2, _ = self._pushed(app2)
        self.assertFalse(screen2._start_in_merge)


class ColumnManageFooterSurfaceTests(_ColumnDialogBase):
    """The rendered footer follows the gate, on a real running app."""

    @staticmethod
    def _footer_actions(app) -> set:
        return {active.binding.action
                for active in app.screen.active_bindings.values()}

    def test_footer_surface_follows_the_gate(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                self.assertIn("column_manage", self._footer_actions(app),
                              "column management needs no focused card")
                app._set_base_filter("bytopic")
                await pilot.pause()
                self.assertNotIn("column_manage", self._footer_actions(app))
                app._set_base_filter("all")
                await pilot.pause()
                self.assertIn("column_manage", self._footer_actions(app))

        self._run(go)


# --------------------------------------------------------------------------
# 2. The merge reporting contract
# --------------------------------------------------------------------------


class MergeReportingTests(_ColumnDialogBase):
    """`MergeResult` -> exactly one honest toast.

    `complete` is false for BOTH `refused` (nothing written) and `failed`
    (partial progress), and two sentinels change what the retry is. A handler
    that branches on `complete` alone reports all of them identically.
    """

    def _report(self, result, *, dest="Backlog", attempted=9):
        app = self._mock_app(extra_methods=("_report_merge",))
        app._report_merge(result, dest, attempted)
        return self._notified(app)

    def test_a_clean_merge_reports_success(self):
        ab = self.ab
        result = ab.MergeResult(merged=("a.md", "b.md"), sources_removed=("c1",))
        (msg, severity), = self._report(result, attempted=2)
        self.assertEqual(severity, "information")
        self.assertIn("Merged 2 tasks into Backlog", msg)

    def test_a_refusal_is_an_error_and_says_nothing_changed(self):
        ab = self.ab
        result = ab.MergeResult(refused=(("c9", "unknown_column"),))
        (msg, severity), = self._report(result)
        self.assertEqual(severity, "error",
                         "a refusal wrote NOTHING — it is not a partial merge")
        self.assertIn("nothing changed", msg)
        self.assertNotIn("Merged 0 of", msg,
                         "a refusal must not be worded as partial progress")

    def test_a_partial_merge_warns_with_both_counts(self):
        ab = self.ab
        result = ab.MergeResult(merged=tuple(f"t{i}.md" for i in range(7)),
                                failed=(("t7.md", "write_failed: disk full"),
                                        ("t8.md", "not_attempted")))
        (msg, severity), = self._report(result, attempted=9)
        self.assertEqual(severity, "warning",
                         "a bare success toast on a partial merge is the "
                         "specific failure this contract prevents")
        self.assertIn("7 of 9", msg)
        self.assertIn("re-run", msg)

    def test_metadata_sentinel_tells_the_user_to_re_run_the_merge(self):
        ab = self.ab
        result = ab.MergeResult(merged=("a.md",),
                                failed=((ab.MERGE_METADATA_KEY,
                                         "config_write_failed: disk full"),))
        (msg, severity), = self._report(result)
        self.assertEqual(severity, "warning")
        self.assertIn("re-run the merge", msg)

    def test_metadata_local_sentinel_does_NOT_offer_a_merge_retry(self):
        """The one case where re-running would refuse with `unknown_column`.

        Boundary B: the project write landed, so the columns are durably removed
        and only the user-local collapsed prune is pending. Telling the user to
        re-run the merge sends them into a guaranteed refusal.
        """
        ab = self.ab
        result = ab.MergeResult(merged=("a.md",),
                                sources_removed=("c1",),
                                failed=((ab.MERGE_METADATA_LOCAL_KEY,
                                         "local_cleanup_pending: disk full"),))
        (msg, severity), = self._report(result)
        self.assertEqual(severity, "warning")
        self.assertNotIn("re-run the merge", msg)
        self.assertIn("columns removed", msg)

    def test_unverifiable_sentinel_names_the_files_AND_the_recovery(self):
        ab = self.ab
        reason = "unreadable task file(s), cannot verify a column is empty: t9.md"
        result = ab.MergeResult(merged=("a.md",),
                                failed=((ab.MERGE_UNVERIFIABLE_KEY, reason),))
        (msg, severity), = self._report(result)
        self.assertEqual(severity, "warning")
        self.assertIn("t9.md", msg,
                      "the user cannot act without knowing which file to fix")
        # Naming the blocker without naming the remedy leaves the merge
        # interrupted with no stated way to finish it.
        self.assertIn("fix", msg.lower())
        self.assertIn("re-run", msg.lower())

    def test_every_incomplete_outcome_is_distinguishable(self):
        """Negative control for a `complete`-only branch.

        A handler that ignored the sentinels would emit one identical message
        for all four incomplete results, and this set would collapse to size 1.
        """
        ab = self.ab
        results = [
            ab.MergeResult(refused=(("c9", "unknown_column"),)),
            ab.MergeResult(merged=("a.md",), failed=(("b.md", "not_written"),)),
            ab.MergeResult(merged=("a.md",),
                           failed=((ab.MERGE_METADATA_KEY, "config_write_failed: x"),)),
            ab.MergeResult(merged=("a.md",), sources_removed=("c1",),
                           failed=((ab.MERGE_METADATA_LOCAL_KEY,
                                    "local_cleanup_pending: x"),)),
        ]
        messages = {self._report(r)[0][0] for r in results}
        self.assertEqual(len(messages), len(results),
                         "each failure class needs its own wording — the retry "
                         f"differs between them. Got: {messages}")


# --------------------------------------------------------------------------
# 3. The source list
# --------------------------------------------------------------------------


class MergeSourceColumnTests(_ColumnDialogBase):
    """`unordered` is offered as a source only while it holds tasks."""

    def _sources(self, manager):
        app = self._mock_app(manager, extra_methods=("_merge_source_columns",))
        return app._merge_source_columns()

    def test_empty_unordered_lane_is_not_offered(self):
        mgr = _fake_manager()
        self.assertEqual(mgr._unordered_tasks, [])
        ids = [cid for cid, _ in self._sources(mgr)]
        self.assertNotIn("unordered", ids,
                         "an empty inbox is not a meaningful merge source")

    def test_populated_unordered_lane_is_offered_first(self):
        mgr = _fake_manager()
        mgr._unordered_tasks.append(
            SimpleNamespace(filename="t9999_loose.md", board_col="unordered",
                            board_idx=0))
        ids = [cid for cid, _ in self._sources(mgr)]
        self.assertEqual(ids[0], "unordered")

    def test_a_stale_column_order_entry_is_never_offered(self):
        mgr = _fake_manager()
        self.assertIn("ghost", mgr.column_order)
        ids = [cid for cid, _ in self._sources(mgr)]
        self.assertNotIn("ghost", ids,
                         "an order entry with no columns definition does not "
                         "render on the board and must not be mergeable")


# --------------------------------------------------------------------------
# 4. End-to-end on the real app
# --------------------------------------------------------------------------


class _PristineConfigMixin(bf.PristineTreeMixin):
    """`PristineTreeMixin` plus the board config files.

    The shared mixin restores only `**/*.md`, so a class that mutates COLUMNS
    (add / delete / merge) leaks `board_config.json` into the next test. That
    leak is silently self-concealing here: with `c1` already dropped from the
    config, `merge_columns` refuses it as `unknown_column` and writes nothing,
    while a "source column was removed" assertion still passes — because it was
    removed by the *previous* test. Restore both halves so each test starts from
    the committed tree. (Harness gap, not a production bug — `snapshot()` in
    `board_fixture` already treats `board_config*.json` as part of the tree.)
    """

    @classmethod
    def _snapshot_pristine(cls):
        super()._snapshot_pristine()
        meta = (cls.tree / ".aitask-data" / "aitasks" / "metadata").resolve()
        cls._pristine_config = {p: p.read_bytes()
                                for p in sorted(meta.glob("board_config*.json"))}
        assert cls._pristine_config, "fixture tree produced no board config"

    def setUp(self):
        super().setUp()
        for path, data in self._pristine_config.items():
            if path.read_bytes() != data:
                path.write_bytes(data)


class ColumnManageDialogLiveTests(_PristineConfigMixin, _ColumnDialogBase):
    """Drive the real `KanbanApp` + real `TaskManager` on the fixture tree."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._snapshot_pristine()

    def _open(self, app):
        app.action_column_manage()

    def test_the_dialog_opens_and_lists_every_rendered_column(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await pilot.press("e")
                await pilot.pause()
                self.assertIsInstance(app.screen, ab.ColumnManageScreen)
                listed = [i.col_id for i in app.screen.query(ab.ColumnManageItem)]
                expected = [c for c in app.manager.column_order
                            if app.manager.get_column_conf(c)]
                self.assertEqual(listed, expected)

        self._run(go)

    def test_reorder_persists_and_survives_a_reload(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                original = list(app.manager.column_order)
                self._open(app)
                await pilot.pause()
                screen = app.screen
                screen._focus_col(original[1])
                await pilot.pause()
                screen.action_shift_up()
                await pilot.pause()
                self.assertTrue(screen._changed)

            swapped = [original[1], original[0], *original[2:]]
            self.assertEqual(list(ab.TaskManager().column_order), swapped,
                             "the new order must be on disk, not just in memory")

        self._run(go)

    def test_merge_moves_tasks_and_removes_the_source(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                source, dest = "c1", "c0"
                # Positive control on the same input: `merge_columns` refuses an
                # unconfigured source with `unknown_column` and writes nothing,
                # which would make the "source was removed" assertions below
                # pass vacuously. Prove the column is really there first.
                self.assertIsNotNone(app.manager.get_column_conf(source))
                self.assertIn(source, app.manager.column_order)
                moving = [t.filename
                          for t in app.manager.get_column_tasks(source)]
                self.assertTrue(moving, "fixture must have something to merge")
                dest_before = [t.filename
                               for t in app.manager.get_column_tasks(dest)]

                self._open(app)
                await pilot.pause()
                screen = app.screen
                screen._confirm_merge([source], dest)
                await pilot.pause()
                self.assertIsInstance(app.screen, ab.MergeColumnsConfirmScreen)
                app.screen.confirm()
                await pilot.pause()

            fresh = ab.TaskManager()
            self.assertNotIn(source, fresh.column_order)
            self.assertIsNone(fresh.get_column_conf(source))
            self.assertEqual(
                [t.filename for t in fresh.get_column_tasks(dest)],
                [*dest_before, *moving],
                "merged members land at the BOTTOM of the destination, in "
                "their original relative order")

        self._run(go)

    def test_cancelling_the_merge_confirmation_changes_nothing(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                before = list(app.manager.column_order)
                self._open(app)
                await pilot.pause()
                screen = app.screen
                screen._confirm_merge(["c1"], "c0")
                await pilot.pause()
                app.screen.cancel()
                await pilot.pause()
                self.assertFalse(screen._changed)

            self.assertEqual(list(ab.TaskManager().column_order), before)

        self._run(go)

    def test_add_through_the_dialog_creates_the_column(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                self._open(app)
                await pilot.pause()
                screen = app.screen
                screen._on_edit_result(("brandnew", "brandnew", "Brand New", "red"))
                await pilot.pause()
                # `_on_edit_result` routes through the app's shared mutation
                # helper, so this is the same code the palette and the header
                # pencil button run.
                screen._on_edit_result(("add", "brandnew", "Brand New", "red"))
                await pilot.pause()
                self.assertTrue(screen._changed)
                self.assertIn("brandnew",
                              [i.col_id for i in screen.query(ab.ColumnManageItem)])

            self.assertIsNotNone(ab.TaskManager().get_column_conf("brandnew"))

        self._run(go)

    def test_delete_through_the_dialog_drains_to_unsorted(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                self._open(app)
                await pilot.pause()
                screen = app.screen
                screen._focus_col("c1")
                await pilot.pause()
                screen.action_delete()
                await pilot.pause()
                self.assertIsInstance(app.screen, ab.DeleteColumnConfirmScreen)
                app.screen.confirm()
                await pilot.pause()

            fresh = ab.TaskManager()
            self.assertIsNone(fresh.get_column_conf("c1"))
            self.assertNotIn("c1", fresh.column_order)

        self._run(go)

    def test_the_synthetic_lane_is_named_not_shown_as_its_raw_id(self):
        """`get_column_conf("unordered")` is None — it is not in `columns`.

        A local raw-id fallback would confirm and report the merge as
        "unordered" while the picker the user just clicked said "Unsorted /
        Inbox". `KanbanApp._column_title` owns that mapping; the dialog must
        delegate rather than re-derive.
        """
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                self.assertIsNone(app.manager.get_column_conf("unordered"))
                self._open(app)
                await pilot.pause()
                screen = app.screen
                self.assertEqual(screen._title_of("unordered"),
                                 "Unsorted / Inbox")

                screen._confirm_merge(["c1"], "unordered")
                await pilot.pause()
                confirm = app.screen
                self.assertIsInstance(confirm, ab.MergeColumnsConfirmScreen)
                self.assertEqual(confirm.dest_title, "Unsorted / Inbox")
                rendered = "\n".join(
                    strip.text for strip
                    in app.screen._compositor.render_strips(app.screen.size))
                self.assertIn("Unsorted / Inbox", rendered)
                confirm.cancel()
                await pilot.pause()

        self._run(go)

    def test_the_button_row_fits_at_a_narrow_width(self):
        """Regression: a fifth button clipped off-dialog at 100 columns.

        `#detail_buttons` is `align: center middle` with no wrapping, so an
        over-wide row is silently cut rather than reflowed — the button stays
        visible in the DOM while being unreachable on screen. Found in a live
        tmux capture; asserted here against the composited frame so it cannot
        come back.
        """
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(100, 32)) as pilot:
                await pilot.pause()
                self._open(app)
                await pilot.pause()
                dialog = app.screen.query_one("#column_manage_dialog")
                row = app.screen.query_one("#detail_buttons")
                widths = sum(b.outer_size.width for b in row.query(ab.Button))
                self.assertLessEqual(
                    widths, dialog.size.width,
                    "the button row must fit inside the dialog; anything wider "
                    "is clipped and unclickable")

        self._run(go)

    def test_a_changed_dialog_refreshes_the_board_exactly_once_on_close(self):
        """The other half of the deferred-refresh contract.

        Deferring `refresh_board()` to close is only correct if it actually
        happens: without it the merged-away column keeps rendering with a stale
        task count until the next manual `r`. Found live — the dialog listed the
        new state while the board behind it still showed the removed column.
        """
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                self._open(app)
                await pilot.pause()
                screen = app.screen
                screen._confirm_merge(["c1"], "c0")
                await pilot.pause()
                app.screen.confirm()
                await pilot.pause()
                self.assertTrue(screen._changed)

                calls = []
                real = app.refresh_board
                app.refresh_board = lambda *a, **k: (calls.append(1), real(*a, **k))[1]
                await pilot.press("escape")
                await pilot.pause()
                self.assertEqual(len(calls), 1,
                                 "a dialog that changed columns must recompose "
                                 "the board exactly once, on close")

        self._run(go)

    def test_closing_an_untouched_dialog_does_not_refresh_the_board(self):
        """The whole point of `_apply_column_edit`: refresh once, on close."""
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                self._open(app)
                await pilot.pause()
                screen = app.screen
                self.assertFalse(screen._changed)
                calls = []
                app.refresh_board = lambda *a, **k: calls.append(1)
                await pilot.press("escape")
                await pilot.pause()
                self.assertEqual(calls, [],
                                 "a read-only visit must not recompose the board")

        self._run(go)


if __name__ == "__main__":
    unittest.main(verbosity=2)
