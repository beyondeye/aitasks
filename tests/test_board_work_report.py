"""Tests for the board `w` Work Report flow (t1162_4).

Covers the contextual footer visibility of the new `w` binding, the two
work-report modal screens (defaults, cancellation, ordering), the flow
orchestration in ``action_work_report`` (column intersection, full-column
behavior under search, empty-selection notifications), and the launch surface
(``_launch_work_report`` construction-spy incl. the direct-run "run" result
and the dry-run-resolution-failure fallback).

Harness notes: footer/Pilot tests run the real ``KanbanApp`` against the live
repo tree (the ``test_board_footer_visibility.py`` pattern); flow-closure and
launch tests use the ``MagicMock``-app construction-spy pattern from
``test_tui_switcher_agent_launch.py`` so no board state is mutated.
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))


def _fake_manager(unordered_tasks=()):
    """Manager stub: two configured columns + one stale column_order entry."""
    tasks = {
        "unordered": list(unordered_tasks),
        "now": [SimpleNamespace(filename="t5_alpha.md"),
                SimpleNamespace(filename="t3_beta.md")],
        "next": [SimpleNamespace(filename="t9_gamma.md")],
    }
    return SimpleNamespace(
        column_order=["now", "next", "ghost"],
        columns=[{"id": "now", "title": "Now"}, {"id": "next", "title": "Next"}],
        get_column_tasks=lambda col_id: tasks.get(col_id, []),
    )


class WorkReportTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._orig_cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        import aitask_board as ab  # noqa: E402

        cls.ab = ab

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._orig_cwd)

    def _mock_app(self, manager):
        ab = self.ab
        app = MagicMock()
        app._modal_is_active.return_value = False
        app._get_focused_col_id.return_value = "now"
        app.manager = manager
        app._work_report_columns = (
            lambda: ab.KanbanApp._work_report_columns(app))
        return app


class WorkReportColumnOptionsTests(WorkReportTestBase):
    """_work_report_columns builds the renderable configured intersection."""

    def test_stale_column_order_entry_is_not_offered(self):
        app = self._mock_app(_fake_manager())
        cols = self.ab.KanbanApp._work_report_columns(app)
        self.assertEqual(cols, [("now", "Now"), ("next", "Next")])

    def test_unordered_offered_first_only_when_it_has_tasks(self):
        with_tasks = self._mock_app(
            _fake_manager(unordered_tasks=[SimpleNamespace(filename="t7_u.md")]))
        cols = self.ab.KanbanApp._work_report_columns(with_tasks)
        self.assertEqual(cols[0], ("unordered", "Unsorted / Inbox"))

        without = self._mock_app(_fake_manager())
        cols = self.ab.KanbanApp._work_report_columns(without)
        self.assertNotIn("unordered", [c for c, _ in cols])


class WorkReportFlowTests(WorkReportTestBase):
    """action_work_report orchestration via its dismiss callbacks."""

    def _open_flow(self, app):
        self.ab.KanbanApp.action_work_report(app)
        self.assertEqual(app.push_screen.call_count, 1)
        screen, callback = app.push_screen.call_args.args
        self.assertIsInstance(screen, self.ab.WorkReportColumnSelectScreen)
        return screen, callback

    def test_column_screen_gets_intersection_and_focused_default(self):
        app = self._mock_app(_fake_manager())
        screen, _ = self._open_flow(app)
        self.assertEqual(screen.columns, [("now", "Now"), ("next", "Next")])
        self.assertEqual(screen.initial, "now")

    def test_task_screen_preserves_displayed_grouped_order(self):
        app = self._mock_app(_fake_manager())
        _, on_columns = self._open_flow(app)
        on_columns(["now", "next"])
        self.assertEqual(app.push_screen.call_count, 2)
        screen, _ = app.push_screen.call_args.args
        self.assertIsInstance(screen, self.ab.WorkReportTaskSelectScreen)
        self.assertEqual(screen.tasks, [
            ("now", "5", "[now] t5 alpha"),
            ("now", "3", "[now] t3 beta"),
            ("next", "9", "[next] t9 gamma"),
        ])

    def test_exact_launch_args_after_exclusion(self):
        app = self._mock_app(_fake_manager())
        _, on_columns = self._open_flow(app)
        on_columns(["now", "next"])
        _, on_tasks = app.push_screen.call_args.args
        on_tasks([("now", "5"), ("next", "9")])
        app._launch_work_report.assert_called_once_with("now,next", "5,9")

    def test_cancel_at_column_screen_stops_cleanly(self):
        app = self._mock_app(_fake_manager())
        _, on_columns = self._open_flow(app)
        on_columns(None)
        self.assertEqual(app.push_screen.call_count, 1)
        app._launch_work_report.assert_not_called()
        app.notify.assert_not_called()

    def test_cancel_at_task_screen_stops_cleanly(self):
        app = self._mock_app(_fake_manager())
        _, on_columns = self._open_flow(app)
        on_columns(["now"])
        _, on_tasks = app.push_screen.call_args.args
        on_tasks(None)
        app._launch_work_report.assert_not_called()
        app.notify.assert_not_called()

    def test_empty_column_selection_notifies_without_launch(self):
        app = self._mock_app(_fake_manager())
        _, on_columns = self._open_flow(app)
        on_columns([])
        self.assertEqual(app.push_screen.call_count, 1)
        app._launch_work_report.assert_not_called()
        app.notify.assert_called_once_with("No columns selected")

    def test_columns_without_tasks_notify_without_task_screen(self):
        app = self._mock_app(_fake_manager())
        _, on_columns = self._open_flow(app)
        on_columns(["unordered"])
        self.assertEqual(app.push_screen.call_count, 1)
        app._launch_work_report.assert_not_called()
        app.notify.assert_called_once_with("No tasks in the selected columns")

    def test_empty_task_selection_notifies_without_launch(self):
        app = self._mock_app(_fake_manager())
        _, on_columns = self._open_flow(app)
        on_columns(["now"])
        _, on_tasks = app.push_screen.call_args.args
        on_tasks([])
        app._launch_work_report.assert_not_called()
        app.notify.assert_called_once_with("No tasks selected")


class WorkReportLaunchTests(WorkReportTestBase):
    """_launch_work_report construction-spy: dialog args, run path, None path."""

    def test_dialog_carries_exact_command_and_args(self):
        ab = self.ab
        app = MagicMock()
        with patch.object(ab, "resolve_dry_run_command",
                          return_value="claude 'x'") as rdc, \
                patch.object(ab, "resolve_agent_string",
                             return_value="claudecode/sonnet4_6"):
            ab.KanbanApp._launch_work_report(app, "now,next", "5,9")
        rdc.assert_called_once_with(
            Path("."), "work-report",
            "--columns", "now,next", "--tasks", "5,9")
        screen, _ = app.push_screen.call_args.args
        self.assertIsInstance(screen, ab.AgentCommandScreen)
        self.assertEqual(
            screen.prompt_str,
            "/aitask-work-report --columns now,next --tasks 5,9")
        self.assertEqual(screen.full_command, "claude 'x'")
        self.assertEqual(screen.operation, "work-report")
        self.assertEqual(screen.operation_args,
                         ["--columns", "now,next", "--tasks", "5,9"])
        self.assertEqual(screen.skill_name, "work-report")
        self.assertEqual(screen.default_window_name, "agent-work-report")

    def test_run_result_dispatches_dialog_command_not_pick(self):
        """Run-in-terminal launches the dialog's CURRENT full_command.

        run_terminal stores user edits into screen.full_command and the
        agent/profile controls regenerate it — the direct-run path must
        dispatch that, never rebuild default wrapper args.
        """
        ab = self.ab
        app = MagicMock()
        with patch.object(ab, "resolve_dry_run_command",
                          return_value="claude 'x'"), \
                patch.object(ab, "resolve_agent_string", return_value=None):
            ab.KanbanApp._launch_work_report(app, "now", "5,3")
        screen, callback = app.push_screen.call_args.args
        # Simulate an in-dialog command edit / agent override having been
        # stored (run_terminal calls _store_command before dismissing "run").
        screen.full_command = "opencode run --model x '/aitask-work-report …'"
        callback("run")
        app.run_work_report.assert_called_once_with(
            "opencode run --model x '/aitask-work-report …'")
        app.run_aitask_pick.assert_not_called()

    def test_dry_run_failure_falls_back_to_direct_run(self):
        ab = self.ab
        import shlex
        app = MagicMock()
        with patch.object(ab, "resolve_dry_run_command",
                          return_value=None), \
                patch.object(ab, "resolve_agent_string",
                             return_value=None) as ras:
            ab.KanbanApp._launch_work_report(app, "now,next", "5,9")
        app.push_screen.assert_not_called()
        app.run_work_report.assert_called_once_with(shlex.join([
            str(ab.CODEAGENT_SCRIPT), "invoke", "work-report",
            "--columns", "now,next", "--tasks", "5,9",
        ]))
        app.notify.assert_called_once()
        ras.assert_not_called()

    def test_direct_run_worker_dispatches_command_string(self):
        """The worker shells out the given command verbatim (sh -c)."""
        ab = self.ab
        app = MagicMock()
        with patch.object(ab, "find_terminal", return_value="footerm"), \
                patch.object(ab, "spawn_in_terminal") as spawn:
            coro = ab.KanbanApp.run_work_report.__wrapped__(
                app, "claude --model y '/aitask-work-report --columns now'")
            asyncio.run(coro)
        spawn.assert_called_once_with("footerm", [
            "sh", "-c",
            "claude --model y '/aitask-work-report --columns now'",
        ])


class WorkReportModalTests(WorkReportTestBase):
    """Pilot tests for the two modal screens (real widgets, explicit data)."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_column_screen_defaults_and_escape(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                results = []
                app.push_screen(
                    ab.WorkReportColumnSelectScreen(
                        [("unordered", "Unsorted / Inbox"),
                         ("now", "Now"), ("next", "Next")], "now"),
                    results.append)
                await pilot.pause()
                from textual.widgets import SelectionList
                sl = app.screen.query_one(SelectionList)
                self.assertEqual(list(sl.selected), ["now"])
                await pilot.press("escape")
                await pilot.pause()
                self.assertEqual(results, [None])

        self._run(go())

    def test_column_screen_confirm_returns_presented_order(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                results = []
                app.push_screen(
                    ab.WorkReportColumnSelectScreen(
                        [("now", "Now"), ("next", "Next")], "next"),
                    results.append)
                await pilot.pause()
                from textual.widgets import SelectionList
                sl = app.screen.query_one(SelectionList)
                sl.select_all()
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(results, [["now", "next"]])

        self._run(go())

    def test_task_screen_all_checked_and_order_preserved(self):
        ab = self.ab
        triples = [
            ("now", "5", "[now] t5 alpha"),
            ("now", "3", "[now] t3 beta"),
            ("next", "9", "[next] t9 gamma"),
        ]

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                results = []
                app.push_screen(
                    ab.WorkReportTaskSelectScreen(triples), results.append)
                await pilot.pause()
                from textual.widgets import SelectionList
                sl = app.screen.query_one(SelectionList)
                self.assertEqual(set(sl.selected), {"5", "3", "9"})
                sl.deselect(sl.get_option_at_index(1))  # exclude t3
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(results, [[("now", "5"), ("next", "9")]])

        self._run(go())

    def test_task_screen_escape_cancels(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                results = []
                app.push_screen(
                    ab.WorkReportTaskSelectScreen(
                        [("now", "5", "[now] t5 alpha")]), results.append)
                await pilot.pause()
                await pilot.press("escape")
                await pilot.pause()
                self.assertEqual(results, [None])

        self._run(go())


class WorkReportFooterVisibilityTests(WorkReportTestBase):
    """`w` footer surface per view and focus state (live-tree Pilot)."""

    def _run(self, coro):
        return asyncio.run(coro)

    @staticmethod
    def _footer_actions(app) -> set[str]:
        return {
            active.binding.action
            for active in app.screen.active_bindings.values()
        }

    def test_hidden_in_derived_views_and_without_column(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                # No focused column at all.
                app._get_focused_col_id = lambda: None
                self.assertIs(app.check_action("work_report", None), False)
                self.assertNotIn("work_report", self._footer_actions(app))
                # Derived views hide it even with a column identified.
                app._get_focused_col_id = lambda: "now"
                for view in ("inflight", "bytopic"):
                    app.base_filter = view
                    self.assertIs(
                        app.check_action("work_report", None), False)
                    self.assertNotIn(
                        "work_report", self._footer_actions(app))

        self._run(go())

    def test_visible_with_focused_card(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                cards = list(app.query(ab.TaskCard))
                if not cards:
                    self.skipTest("live tree rendered no task cards")
                cards[0].focus()
                await pilot.pause()
                self.assertTrue(app.check_action("work_report", None))
                self.assertIn("work_report", self._footer_actions(app))

        self._run(go())

    def test_visible_with_focused_collapsed_placeholder(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                cols = list(app.query(ab.KanbanColumn))
                if not cols:
                    self.skipTest("live tree rendered no columns")
                # In-memory collapse only — never persist to the live config.
                app.manager.settings["collapsed_columns"] = [cols[0].col_id]
                app.refresh_board()
                await pilot.pause()
                placeholders = list(app.query(ab.CollapsedColumnPlaceholder))
                self.assertTrue(placeholders)
                placeholders[0].focus()
                await pilot.pause()
                self.assertTrue(app.check_action("work_report", None))
                self.assertIn("work_report", self._footer_actions(app))

        self._run(go())

    def test_visible_with_focused_empty_placeholder_under_search(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                app.search_filter = "zz_no_such_task_zz"
                app.apply_filter()
                await pilot.pause()
                shown = [p for p in app.query(ab.EmptyColumnPlaceholder)
                         if p.styles.display != "none"]
                if not shown:
                    self.skipTest("no empty-column placeholder surfaced")
                shown[0].focus()
                await pilot.pause()
                self.assertTrue(app.check_action("work_report", None))
                self.assertIn("work_report", self._footer_actions(app))

        self._run(go())


class WorkReportFullColumnUnderSearchTests(WorkReportTestBase):
    """The task screen lists the FULL column even when search hides cards."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_hidden_cards_still_listed(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                candidates = [
                    (col_id, app.manager.get_column_tasks(col_id))
                    for col_id, _ in app._work_report_columns()
                ]
                candidates = [(c, t) for c, t in candidates if t]
                if not candidates:
                    self.skipTest("live tree has no populated board column")
                col_id, col_tasks = candidates[0]

                app.search_filter = "zz_no_such_task_zz"
                app.apply_filter()
                await pilot.pause()
                visible = [c for c in app.query(ab.TaskCard)
                           if c.styles.display != "none"]
                self.assertEqual(visible, [])

                app._get_focused_col_id = lambda: col_id
                app.action_work_report()
                await pilot.pause()
                self.assertIsInstance(
                    app.screen, ab.WorkReportColumnSelectScreen)
                await pilot.press("enter")  # confirm default (focused col)
                await pilot.pause()
                self.assertIsInstance(
                    app.screen, ab.WorkReportTaskSelectScreen)
                from textual.widgets import SelectionList
                sl = app.screen.query_one(SelectionList)
                self.assertGreater(len(col_tasks), 0)
                self.assertEqual(sl.option_count, len(col_tasks))
                await pilot.press("escape")

        self._run(go())


if __name__ == "__main__":
    unittest.main()
