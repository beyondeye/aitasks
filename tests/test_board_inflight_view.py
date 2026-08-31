"""Tests for the board In-Flight action view (t635_9)."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402


def _manager(ab):
    """Bare TaskManager built from the *fixture-bound* board module.

    `ab` is threaded in rather than imported here: under the harness the board
    is loaded under a synthetic module name, so a local `import aitask_board`
    would reach a different module object than the one under test.
    """
    TaskManager = ab.TaskManager

    mgr = TaskManager.__new__(TaskManager)
    mgr.task_datas = {}
    mgr.child_task_datas = {}
    mgr.archived_task_cache = {}
    mgr.columns = []
    mgr.column_order = []
    mgr.modified_files = set()
    mgr.lock_map = {}
    mgr.xdep_status_cache = {}
    mgr.gate_state_cache = {}
    mgr.gate_registry_cache = None
    mgr.gate_registry_error = ""
    # Local-dependency decision core (t1527), built lazily by dep_resolver().
    mgr._dep_resolver = None
    mgr.gate_digest_cache = ab._DIGEST_UNSET
    mgr.settings = {}
    return mgr


def _tree_task(ab, tasks_dir: Path, name: str, body: str, cleanup):
    """Write a task INTO the fixture tree, so on-disk resolution can find it.

    Registers its removal, because `FixtureBoardTestBase` builds one tree per
    class and a leaked task file would change the next test's starting state.
    """
    path = tasks_dir / name
    path.write_text(body, encoding="utf-8")
    cleanup(path.unlink, missing_ok=True)
    return ab.Task.from_text(path, body)


def _task(ab, tmp: Path, name: str, body: str):
    Task = ab.Task

    path = tmp / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return Task.from_text(path, body)


def _body(status: str, extra_fm: str = "", ledger: str = "") -> str:
    return f"""---
priority: high
effort: low
status: {status}
{extra_fm}---

Body.
{ledger}
"""


LEDGER_PENDING_HUMAN = """
## Gate Runs

> **⏸ gate:review_approved** run=2026-01-01T00:00:00Z status=pending type=human
"""

LEDGER_REVIEW_PASS = """
## Gate Runs

> **✅ gate:review_approved** run=2026-01-01T00:00:00Z status=pass attempt=1 type=human
"""


class InFlightModelTests(bf.FixtureBoardTestBase, unittest.TestCase):
    def test_implementing_without_ledger_is_included(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _manager(self.ab)
            task = _task(self.ab, Path(td), "t1_plain.md", _body("Implementing"))
            mgr.task_datas[task.filename] = task

            items = mgr.get_inflight_items()
            self.assertEqual([i.task_id for i in items], ["t1"])
            self.assertEqual(items[0].group, "agent")
            self.assertIn("No gate information yet", items[0].next_action)
            # No-ledger cards omit the duplicate gate-summary line.
            self.assertEqual(items[0].gate_summary, "")

    def test_ready_with_ledger_is_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _manager(self.ab)
            task = _task(
                self.ab,
                Path(td),
                "t2_ready.md",
                _body("Ready", "gates: [review_approved]\n", LEDGER_REVIEW_PASS),
            )
            mgr.task_datas[task.filename] = task

            self.assertEqual(mgr.get_inflight_items(), [])

    def test_pending_human_gate_needs_action(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _manager(self.ab)
            task = _task(
                self.ab,
                Path(td),
                "t3_review.md",
                _body("Implementing", "gates: [review_approved]\n", LEDGER_PENDING_HUMAN),
            )
            mgr.task_datas[task.filename] = task

            item = mgr.get_inflight_items()[0]
            self.assertEqual(item.group, "human")
            self.assertEqual(item.human_gates, ["review_approved"])

    def test_gate_satisfied_dependency_does_not_block(self):
        """t635_3 through the shared core: an active upstream whose required
        gates all pass releases its dependents before archival.

        Written into the FIXTURE TREE, not a detached tempdir: since t1527 the
        board resolves a dep id against `TASKS_DIR` on disk rather than against
        the in-memory `task_datas` map, so a task that exists only in that map is
        (correctly) UNRESOLVED. Production never has one — every entry in
        `task_datas` was loaded from that tree — and a fixture that stages one
        would be asserting against a state the board cannot reach.
        """
        upstream = _tree_task(
            self.ab, self.tasks_dir, "t10_upstream.md",
            _body("Implementing", "gates: [review_approved]\n", LEDGER_REVIEW_PASS),
            self.addCleanup,
        )
        dependent = _tree_task(
            self.ab, self.tasks_dir, "t11_dependent.md",
            _body("Ready", "depends: [10]\n"), self.addCleanup,
        )
        mgr = _manager(self.ab)
        mgr.task_datas[upstream.filename] = upstream
        mgr.task_datas[dependent.filename] = dependent

        self.assertEqual(mgr.unresolved_local_deps(dependent), [])

        # Negative control: without the passing gate the same upstream DOES
        # block, so the assertion above is not vacuously satisfied by the
        # dependent simply having no deps.
        ungated = _tree_task(
            self.ab, self.tasks_dir, "t10_upstream.md",
            _body("Implementing"), self.addCleanup,
        )
        mgr2 = _manager(self.ab)
        mgr2.task_datas[ungated.filename] = ungated
        mgr2.task_datas[dependent.filename] = dependent
        self.assertEqual(mgr2.unresolved_local_deps(dependent), ["t10"])

    def test_gate_parse_failure_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = _manager(self.ab)
            task = _task(self.ab, Path(td), "t12_missing.md", _body("Implementing"))
            task.filepath = Path(td) / "does_not_exist.md"
            mgr.task_datas[task.filename] = task

            item = mgr.get_inflight_items()[0]
            self.assertEqual(item.group, "agent")
            self.assertIn("unavailable", item.next_action)
            self.assertTrue(item.state_error)


class InFlightPilotTests(bf.FixtureBoardTestBase, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.InFlightColumn = cls.ab.InFlightColumn
        cls.KanbanApp = cls.ab.KanbanApp
        cls.KanbanColumn = cls.ab.KanbanColumn

    def _run(self, coro):
        return asyncio.run(coro)

    def test_fixture_facts(self):
        """Precondition (t1354_2 Step 2a): the tree must carry an in-flight
        task, or the In-Flight view assertions below would pass against an
        empty view."""
        mgr = self.ab.TaskManager()
        mgr.load_tasks()
        implementing = [
            f for f, t in list(mgr.task_datas.items()) + list(mgr.child_task_datas.items())
            if t.metadata.get("status") == "Implementing"
        ]
        self.assertTrue(
            implementing,
            "fixture must contain at least one Implementing task for the "
            "In-Flight view")

    def test_i_switches_to_inflight_columns_and_a_returns(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await pilot.press("i")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(app.base_filter, "inflight")
                self.assertTrue(list(app.query(self.InFlightColumn)))
                self.assertFalse(list(app.query(self.KanbanColumn)))

                await pilot.press("a")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(app.base_filter, "all")
                self.assertTrue(list(app.query(self.KanbanColumn)))
        self._run(go())

    def test_existing_agent_window_guard_reuses_window(self):
        # Targets are bound to `self.ab` (the fixture-loaded module), NOT the
        # string "aitask_board". Under the harness the board is imported under a
        # synthetic module name, so a string target would patch the *canonical*
        # module — a different object from the one under test — and this test
        # would silently shell out to the real tmux helpers (t1354_2 Step 2b).
        app = self.KanbanApp()
        with patch.object(self.ab, "_current_tmux_session", return_value="aitasks"), \
                patch.object(self.ab, "find_window_by_name",
                             return_value=("aitasks", "2")), \
                patch.object(self.ab.subprocess, "Popen") as popen:
            self.assertTrue(app._focus_existing_agent_window("42"))
            popen.assert_called_once()


class InFlightCardRenderTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """Render-level checks: mount a real InFlightTaskCard and read what the
    Labels actually display (post-markup), exercising compose() + Label rather
    than a helper string in isolation."""

    def _render_card(self, body: str):
        """Build an InFlightItem from `body`, mount its card, and return
        {ops, action} -> rendered plain text."""
        InFlightTaskCard = self.ab.InFlightTaskCard
        from textual.app import App
        from textual.widgets import Label

        async def go():
            with tempfile.TemporaryDirectory() as td:
                mgr = _manager(self.ab)
                task = _task(self.ab, Path(td), "t1_card.md", body)
                mgr.task_datas[task.filename] = task
                item = mgr.get_inflight_items()[0]

                class CardApp(App):
                    def compose(self):
                        yield InFlightTaskCard(item, mgr, column_id="inflight-agent")

                app = CardApp()
                async with app.run_test(size=(90, 24)) as pilot:
                    await pilot.pause()
                    card = app.query_one(InFlightTaskCard)
                    ops = card.query_one(".inflight-ops", Label)
                    action = card.query_one(".inflight-action", Label)
                    return {
                        "ops": ops.render().plain,
                        "action": action.render().plain,
                    }

        return asyncio.run(go())

    def test_inflight_card_renders_literal_ops_and_friendly_copy(self):
        rendered = self._render_card(_body("Implementing"))
        # Bug 1: literal shortcut hint survives markup parsing (negative control:
        # on the old code this renders empty).
        self.assertIn("[p pick]", rendered["ops"])
        self.assertNotIn("[g resume]", rendered["ops"])
        # Bug 2: friendly, non-technical copy; no "ledger" jargon.
        self.assertIn("No gate information yet", rendered["action"])
        self.assertNotIn("ledger", rendered["action"].lower())

    def test_inflight_card_renders_all_ops_for_pending_human(self):
        rendered = self._render_card(
            _body("Implementing", "gates: [review_approved]\n", LEDGER_PENDING_HUMAN)
        )
        for hint in ("[p pick]", "[g resume]", "[s sign-off]", "[f fail]"):
            self.assertIn(hint, rendered["ops"])


# --- t1642: the actor axis keys off the ENFORCED active set -------------------


def _run(gate: str, status: str, **fields) -> str:
    """One `## Gate Runs` marker line, matching the production writer's shape."""
    icon = {"pass": "✅", "fail": "❌", "error": "❌", "skip": "⏭",
            "pending": "⏸"}.get(status, "⏸")
    extra = "".join(f" {k}={v}" for k, v in fields.items())
    return (f"> **{icon} gate:{gate}** run=2026-01-01T00:00:00Z "
            f"status={status} attempt=1{extra}\n")


def _ledger(*runs: str) -> str:
    return "\n## Gate Runs\n\n" + "".join(runs)


class InFlightActiveSetTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """The In-Flight view's two decision helpers, over the cases t1603_2 found
    them wrong on (t1642).

    Fixtures are real task files parsed by the production gate parser and carry a
    VALID `active_gates` tuple, so "active" vs "filtered" vs "absent from both"
    are genuinely distinct here rather than collapsing onto raw `gates:`. The
    class fixture stages `metadata/gates.yaml`, so `plan_approved` /
    `review_approved` are `type: human` and `tests_pass` / `lint` are
    `type: machine` — without it every one of these would measure the degraded
    no-registry branch.
    """

    def _item(self, name: str, fm: str, ledger: str):
        """`(InFlightItem, TaskGateState)` for one fixture task."""
        mgr = _manager(self.ab)
        path = self.tasks_dir / name
        body = _body("Implementing", fm, ledger)
        path.write_text(body, encoding="utf-8")
        self.addCleanup(path.unlink, missing_ok=True)
        task = self.ab.Task.from_text(path, body)
        mgr.task_datas[task.filename] = task
        items = mgr.get_inflight_items()
        self.assertEqual(len(items), 1, "fixture must yield exactly one item")
        return items[0], mgr.gate_state_for(task).state

    # --- Defect 1: `skip` is terminal-satisfied, not pending ------------------

    def test_skipped_human_gate_is_not_pending(self):
        """`SATISFIED_STATUSES` is {pass, skip}, so a SKIPPED `review_approved`
        is absent from `archive_pending` and the task is legitimately ALL_PASS.
        The shipped `status != "pass"` test reported it pending, which put a
        `[s sign-off]` op on a gate nothing is owed for."""
        item, state = self._item(
            "t1300_skipped.md",
            bf.active_tuple_fm(["plan_approved", "review_approved"],
                               ["plan_approved", "review_approved"], []),
            _ledger(_run("plan_approved", "pass", type="human"),
                    _run("review_approved", "skip", type="human")))
        self.assertEqual(state.archive_decision, "ALL_PASS")
        self.assertEqual(item.human_gates, [])
        self.assertEqual(item.next_action, "all gates pass — archive/re-enter")

    def test_skipped_human_gate_does_not_own_the_actor_column(self):
        """DISCRIMINATING CASE. The ALL_PASS rung sits ahead of the human-gate
        rung, so the fixture above cannot show the actor column moving. Here a
        pending MACHINE gate keeps the task off ALL_PASS: the work is owed by an
        agent, and only the skipped human gate was filing it under `human`."""
        item, state = self._item(
            "t1301_skip_plus_machine.md",
            bf.active_tuple_fm(
                ["plan_approved", "review_approved", "tests_pass"],
                ["plan_approved", "review_approved", "tests_pass"], []),
            _ledger(_run("plan_approved", "pass", type="human"),
                    _run("review_approved", "skip", type="human"),
                    _run("tests_pass", "pending", type="machine")))
        self.assertEqual(state.archive_pending, ["tests_pass"])
        self.assertEqual(item.human_gates, [])
        self.assertEqual(item.group, "agent")
        self.assertEqual(item.next_action, "plan approved — resume implementation")

    def test_pending_human_gate_still_owns_the_actor_column(self):
        """NEGATIVE CONTROL for the row above: the identical fixture with the
        human gate `pending` instead of `skip` must still be the human's. Without
        it, the assertions above would also pass against a `_human_pending_gates`
        that always answered `[]`."""
        item, _ = self._item(
            "t1302_pending_plus_machine.md",
            bf.active_tuple_fm(
                ["plan_approved", "review_approved", "tests_pass"],
                ["plan_approved", "review_approved", "tests_pass"], []),
            _ledger(_run("plan_approved", "pass", type="human"),
                    _run("review_approved", "pending", type="human"),
                    _run("tests_pass", "pending", type="machine")))
        self.assertEqual(item.human_gates, ["review_approved"])
        self.assertEqual(item.group, "human")
        self.assertEqual(item.next_action, "pending human gate")

    # --- Defect 2: a failure only counts for an ACTIVE gate -------------------

    def test_historical_failure_of_inactive_gate_does_not_classify(self):
        """A gate deleted from `gates:` outright is in NEITHER `active_gates` nor
        `active_gates_filtered`, so the shipped `_has_failed_gate` — which
        subtracts only `filtered_gates` from all of `state.current` — still
        classified on its historical `fail` and reported "failed gate" for a task
        whose only outstanding item is a human review."""
        item, state = self._item(
            "t1303_ghost_fail.md",
            bf.active_tuple_fm(["plan_approved", "review_approved"],
                               ["plan_approved", "review_approved"], []),
            _ledger(_run("plan_approved", "pass", type="human"),
                    _run("review_approved", "pending", type="human"),
                    _run("tests_pass", "fail", type="machine")))
        # Precondition: the failed gate really is outside BOTH lists.
        self.assertIn("tests_pass", state.current)
        self.assertNotIn("tests_pass", state.active_gates)
        self.assertNotIn("tests_pass", state.filtered_gates)
        self.assertEqual(item.next_action, "pending human gate")
        self.assertEqual(item.human_gates, ["review_approved"])

    def test_profile_filtered_failure_still_does_not_classify(self):
        """The other route into "not active" — a gate the profile filtered out.
        This one IS in `filtered_gates`, so the shipped helper already handled
        it; asserted so the rewrite does not regress it while fixing the sibling
        above."""
        item, state = self._item(
            "t1304_filtered_fail.md",
            bf.active_tuple_fm(["plan_approved", "review_approved", "lint"],
                               ["plan_approved", "review_approved"], ["lint"]),
            _ledger(_run("plan_approved", "pass", type="human"),
                    _run("review_approved", "pending", type="human"),
                    _run("lint", "fail", type="machine")))
        self.assertEqual(state.filtered_gates, ["lint"])
        self.assertEqual(item.next_action, "pending human gate")

    def test_active_gate_failure_still_classifies(self):
        """POSITIVE CONTROL for the two rows above: an ACTIVE gate's failure must
        still reach the `failed` rung. Without this they would both pass against
        a `_has_failed_gate` that always returned False."""
        item, _ = self._item(
            "t1305_real_fail.md",
            bf.active_tuple_fm(["plan_approved", "tests_pass"],
                               ["plan_approved", "tests_pass"], []),
            _ledger(_run("plan_approved", "pass", type="human"),
                    _run("tests_pass", "fail", type="machine")))
        self.assertEqual(item.group, "human")
        self.assertEqual(item.next_action, "failed gate — inspect/sign off or fail")


if __name__ == "__main__":
    unittest.main()
