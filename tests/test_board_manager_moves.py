"""Manager-level contract for the gap-indexing move API (t1243_3).

`tests/test_board_ordering.py` pins the arithmetic and
`tests/test_board_movement.py` drives the three keyboard actions through a real
Pilot. Neither reaches `TaskManager.move_tasks_to_column`, and that gap matters:
**an implementation that writes each resolved task as it goes and only then
discovers an invalid one would pass every other test in this task** while
leaving the batch half-applied — silently breaking the all-or-nothing hand-off
t1243_7 is built on.

So every refusal case here asserts THREE things, not one:

  1. what `MoveResult.refused` reports,
  2. a write-spy count of zero,
  3. a byte-identical tree via `snapshot` / `diff_snapshots`.

(3) is the one a partial-write implementation fails; (1) alone would pass.

Child ids are exercised against a REAL child file (`build_fixture_tree` writes
`t9000/t9000_1_*.md`), not a fabricated string, so "the manager refuses a child"
is proved against the path `TaskManager.load_child_tasks` actually globs rather
than against a name that happens to be absent.

Why no subprocess (unlike tests/test_board_movement.py)
-------------------------------------------------------
Nothing here constructs `KanbanApp`. `TaskManager.__init__` reads the module
globals `TASKS_DIR` / `METADATA_FILE` **at call time**, so patching the module
*attribute* redirects it with no app, no Pilot and no git — the same patch-mode
seam `tests/test_board_persistence_seam.py` documents. `mock.patch.object`
restores both even on failure; the suite shares one interpreter and
`test_board_movement.IsolationNegativeControlTests` asserts
`aitask_board.TASKS_DIR == Path("aitasks")`.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m unittest tests.test_board_manager_moves -v
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
_TESTS = Path(__file__).resolve().parent
for _p in (str(_TESTS),
           str(REPO_ROOT / "tests" / "lib"),
           str(REPO_ROOT / ".aitask-scripts" / "board"),
           str(REPO_ROOT / ".aitask-scripts" / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from board_fixture import (  # noqa: E402
    FixtureTask, build_fixture_tree, diff_snapshots, snapshot,
)
import board_ordering as BO  # noqa: E402
import aitask_board as B  # noqa: E402

STEP = BO.STEP

#: Five parents over three columns plus two real children under t9000. `c1` is
#: deliberately left at legacy 10/20 spacing so the append-only batch runs
#: against a dense column.
TOPOLOGY = (
    FixtureTask(task_id="9001", col="c0", idx=10, slug="alpha"),
    FixtureTask(task_id="9002", col="c0", idx=20, slug="beta"),
    FixtureTask(task_id="9003", col="c0", idx=30, slug="gamma"),
    FixtureTask(task_id="9004", col="c1", idx=10, slug="delta"),
    FixtureTask(task_id="9005", col="c1", idx=20, slug="epsilon"),
    FixtureTask(task_id="9000", col="c2", idx=10, slug="parent"),
    FixtureTask(task_id="9000_1", col="c2", idx=20, slug="childone"),
    FixtureTask(task_id="9000_2", col="c2", idx=30, slug="childtwo"),
)

ALPHA = "t9001_alpha.md"
BETA = "t9002_beta.md"
GAMMA = "t9003_gamma.md"
DELTA = "t9004_delta.md"
EPSILON = "t9005_epsilon.md"
CHILD = "t9000_1_childone.md"
UNKNOWN = "t9999_nope.md"


class _ManagerBase(unittest.TestCase):
    def setUp(self):
        root = Path(tempfile.mkdtemp(prefix="aitask-mgr-move-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        self.tree = build_fixture_tree(root, TOPOLOGY)
        tasks_dir = self.tree / "aitasks"
        for attr, value in (
                ("TASKS_DIR", tasks_dir),
                ("METADATA_FILE", tasks_dir / "metadata" / "board_config.json")):
            patcher = mock.patch.object(B, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.manager = B.TaskManager()
        self.writes: list[str] = []
        self.respaces: list[str] = []
        self._spy_writes()
        self._spy_respace()
        self.before = snapshot(self.tree)

    def _spy_writes(self):
        original = B.Task.reload_and_save_board_fields

        def wrapper(self_, fields):
            self.writes.append(self_.filename)
            return original(self_, fields)

        p = mock.patch.object(B.Task, "reload_and_save_board_fields", wrapper)
        p.start()
        self.addCleanup(p.stop)

    def _spy_respace(self):
        original = B.TaskManager.respace_column

        def wrapper(self_, col_id, stride=BO.STEP):
            self.respaces.append(col_id)
            return original(self_, col_id, stride)

        p = mock.patch.object(B.TaskManager, "respace_column", wrapper)
        p.start()
        self.addCleanup(p.stop)

    # --- assertions -------------------------------------------------------

    def assert_untouched(self):
        """Nothing was written AND nothing on disk changed.

        The byte check is the load-bearing half: a partial-write implementation
        produces the right `refused` report and still fails here.
        """
        self.assertEqual(self.writes, [], "a refused move must write nothing")
        self.assertEqual(diff_snapshots(self.before, snapshot(self.tree)),
                         {"changed": set(), "added": set(), "removed": set()},
                         "a refused move must leave the tree byte-identical")

    def idx(self, filename: str) -> int:
        return B.normalize_board_idx(self.manager.task_datas[filename].board_idx)

    def col_order(self, col_id: str) -> list[str]:
        return [t.filename for t in self.manager.get_column_tasks(col_id)]


class MoveTasksToColumnHappyPathTests(_ManagerBase):
    def test_k_tasks_land_in_input_order_with_k_writes(self):
        result = self.manager.move_tasks_to_column([ALPHA, BETA, GAMMA], "c1")

        self.assertTrue(result.ok)
        self.assertEqual(result.moved, (ALPHA, BETA, GAMMA))
        self.assertEqual(result.refused, ())
        self.assertFalse(result.compacted)
        self.assertEqual(self.writes, [ALPHA, BETA, GAMMA])
        self.assertEqual([self.idx(n) for n in (ALPHA, BETA, GAMMA)],
                         [20 + STEP, 20 + 2 * STEP, 20 + 3 * STEP])
        self.assertEqual(self.col_order("c1"),
                         [DELTA, EPSILON, ALPHA, BETA, GAMMA])
        self.assertEqual(self.col_order("c0"), [])

    def test_destination_order_follows_input_not_source_order(self):
        """Order is part of the contract: t1243_7 presents a selection and the
        destination sequence must match what the user saw."""
        self.manager.move_tasks_to_column([GAMMA, ALPHA, BETA], "c1")
        self.assertEqual(self.col_order("c1"),
                         [DELTA, EPSILON, GAMMA, ALPHA, BETA])

    def test_source_column_is_never_rewritten(self):
        self.manager.move_tasks_to_column([ALPHA], "c1")
        changed = diff_snapshots(self.before, snapshot(self.tree))["changed"]
        self.assertEqual(changed, {f"aitasks/{ALPHA}"})
        self.assertEqual(self.idx(BETA), 20)
        self.assertEqual(self.idx(GAMMA), 30)

    def test_append_only_batch_never_compacts(self):
        """`move_tasks_to_column` places past the destination maximum — an
        unbounded region — so no interval can be exhausted and compaction is
        unreachable by construction. Asserted, not left unstated."""
        names = [ALPHA, BETA, GAMMA, DELTA, EPSILON]
        result = self.manager.move_tasks_to_column(names, "c2")

        self.assertTrue(result.ok)
        self.assertFalse(result.compacted)
        self.assertEqual(self.respaces, [], "the batch path must never respace")
        self.assertEqual(len(self.writes), 5)
        # c2's maximum is 10, not 30: `get_column_tasks` scans `task_datas`
        # (parents), so t9000's children at 20/30 contribute no index.
        self.assertEqual([self.idx(n) for n in names],
                         [10 + i * STEP for i in range(1, 6)])

    def test_move_into_an_empty_column_starts_at_step(self):
        self.manager.move_tasks_to_column([ALPHA, BETA, GAMMA], "c1")
        result = self.manager.move_tasks_to_column([ALPHA], "c0")
        self.assertTrue(result.ok)
        self.assertEqual(self.idx(ALPHA), STEP)

    def test_empty_list_is_a_successful_no_op(self):
        """Distinct from a refusal — t1243_7 shows different messages for
        "nothing selected" and "these ids were rejected"."""
        result = self.manager.move_tasks_to_column([], "c1")
        self.assertTrue(result.ok)
        self.assertEqual(result.moved, ())
        self.assertEqual(result.refused, ())
        self.assert_untouched()

    def test_duplicate_names_resolve_once(self):
        result = self.manager.move_tasks_to_column([ALPHA, ALPHA], "c1")
        self.assertTrue(result.ok)
        self.assertEqual(result.moved, (ALPHA,))
        self.assertEqual(self.writes, [ALPHA],
                         "a repeated name must not write twice")
        self.assertEqual(self.idx(ALPHA), 20 + STEP,
                         "a repeated name must not consume two indices")


class MoveTasksToColumnRefusalTests(_ManagerBase):
    def test_unknown_name_is_refused(self):
        result = self.manager.move_tasks_to_column([UNKNOWN], "c1")
        self.assertFalse(result.ok)
        self.assertEqual(result.refused, ((UNKNOWN, "not_a_parent_task"),))
        self.assertEqual(result.moved, ())
        self.assert_untouched()

    def test_child_id_is_refused(self):
        """`task_datas` holds parents only; movement is a parent-level operation
        and a child must fail closed rather than be skipped silently."""
        self.assertIn(CHILD, self.manager.child_task_datas,
                      "fixture must contain a real child file")
        result = self.manager.move_tasks_to_column([CHILD], "c1")
        self.assertFalse(result.ok)
        self.assertEqual(result.refused, ((CHILD, "not_a_parent_task"),))
        self.assert_untouched()

    def test_mixed_valid_and_child_writes_nothing(self):
        """THE all-or-nothing case. A loop that wrote as it went would land the
        two valid tasks and still return the right `refused` report."""
        result = self.manager.move_tasks_to_column([ALPHA, BETA, CHILD], "c1")
        self.assertFalse(result.ok)
        self.assertEqual(result.refused, ((CHILD, "not_a_parent_task"),))
        self.assertEqual(result.moved, ())
        self.assert_untouched()
        self.assertEqual(self.idx(ALPHA), 10)
        self.assertEqual(self.idx(BETA), 20)

    def test_mixed_valid_unknown_and_child_names_both_offenders(self):
        result = self.manager.move_tasks_to_column([ALPHA, UNKNOWN, CHILD], "c1")
        self.assertFalse(result.ok)
        self.assertEqual(result.refused,
                         ((UNKNOWN, "not_a_parent_task"),
                          (CHILD, "not_a_parent_task")),
                         "every offender is reported, in input order")
        self.assert_untouched()

    def test_offending_item_last_still_writes_nothing(self):
        """Ordering guard: resolution must complete before the first write, so a
        bad id in the FINAL position is as fatal as one in the first."""
        result = self.manager.move_tasks_to_column([ALPHA, BETA, GAMMA, UNKNOWN], "c1")
        self.assertFalse(result.ok)
        self.assert_untouched()


class MoveTaskToColumnTests(_ManagerBase):
    def test_single_move_writes_one_file(self):
        result = self.manager.move_task_to_column(GAMMA, "c1")
        self.assertTrue(result.ok)
        self.assertEqual(result.moved, (GAMMA,))
        self.assertEqual(self.writes, [GAMMA])
        self.assertEqual(self.idx(GAMMA), 20 + STEP)

    def test_unknown_is_refused(self):
        result = self.manager.move_task_to_column(UNKNOWN, "c1")
        self.assertEqual(result.refused, ((UNKNOWN, "not_a_parent_task"),))
        self.assert_untouched()

    def test_child_is_refused(self):
        result = self.manager.move_task_to_column(CHILD, "c1")
        self.assertEqual(result.refused, ((CHILD, "not_a_parent_task"),))
        self.assert_untouched()


class MoveTaskToEdgeTests(_ManagerBase):
    def test_to_top_prepends_below_the_minimum(self):
        result = self.manager.move_task_to_edge(GAMMA, "c0", to_top=True)
        self.assertTrue(result.ok)
        self.assertEqual(self.writes, [GAMMA])
        self.assertEqual(self.idx(GAMMA), 10 - STEP)
        self.assertEqual(self.col_order("c0"), [GAMMA, ALPHA, BETA])

    def test_to_bottom_appends_past_the_maximum(self):
        result = self.manager.move_task_to_edge(ALPHA, "c0", to_top=False)
        self.assertTrue(result.ok)
        self.assertEqual(self.idx(ALPHA), 30 + STEP)
        self.assertEqual(self.col_order("c0"), [BETA, GAMMA, ALPHA])

    def test_the_mover_is_excluded_from_its_own_extremum(self):
        """A card already holding the minimum must still move strictly above it.
        Counting the mover would return `self - STEP` twice over and, worse,
        `to_bottom` on the current maximum would be a visible no-op."""
        result = self.manager.move_task_to_edge(ALPHA, "c0", to_top=False)
        self.assertTrue(result.ok)
        self.assertEqual(self.idx(ALPHA), 30 + STEP)
        self.assertNotEqual(self.idx(ALPHA), 10 + STEP)

    def test_edge_moves_never_compact(self):
        self.manager.move_task_to_edge(GAMMA, "c0", to_top=True)
        self.manager.move_task_to_edge(ALPHA, "c0", to_top=False)
        self.assertEqual(self.respaces, [])

    def test_child_is_refused(self):
        result = self.manager.move_task_to_edge(CHILD, "c2", to_top=True)
        self.assertEqual(result.refused, ((CHILD, "not_a_parent_task"),))
        self.assert_untouched()


class RepositionTaskTests(_ManagerBase):
    def test_between_two_neighbours_is_one_write(self):
        result = self.manager.reposition_task(
            GAMMA,
            self.manager.task_datas[ALPHA],
            self.manager.task_datas[BETA])
        self.assertTrue(result.ok)
        self.assertFalse(result.compacted)
        self.assertEqual(self.writes, [GAMMA])
        self.assertEqual(self.idx(GAMMA), 15)
        self.assertEqual(self.col_order("c0"), [ALPHA, GAMMA, BETA])

    def test_before_none_prepends(self):
        result = self.manager.reposition_task(
            GAMMA, None, self.manager.task_datas[ALPHA])
        self.assertTrue(result.ok)
        self.assertEqual(self.idx(GAMMA), 10 - STEP)
        self.assertEqual(self.col_order("c0"), [GAMMA, ALPHA, BETA])

    def test_after_none_appends(self):
        result = self.manager.reposition_task(
            ALPHA, self.manager.task_datas[GAMMA], None)
        self.assertTrue(result.ok)
        self.assertEqual(self.idx(ALPHA), 30 + STEP)
        self.assertEqual(self.col_order("c0"), [BETA, GAMMA, ALPHA])

    def test_tied_neighbours_compact_once_then_place(self):
        """A tie is the densest possible interval, so it is the shortest path to
        the compaction branch. Ties are reachable in production: `delete_column`
        assigns `board_idx = 0` to every evicted task."""
        for name in (ALPHA, BETA, GAMMA):
            self.manager.task_datas[name].board_idx = 10
            self.manager.task_datas[name].reload_and_save_board_fields(("boardidx",))
        self.writes.clear()

        result = self.manager.reposition_task(
            GAMMA,
            self.manager.task_datas[ALPHA],
            self.manager.task_datas[BETA])

        self.assertTrue(result.ok)
        self.assertTrue(result.compacted)
        self.assertEqual(self.respaces, ["c0"], "exactly one compaction")
        self.assertEqual(self.writes, [ALPHA, BETA, GAMMA, GAMMA],
                         "respace writes all three, then the placement writes one")
        self.assertEqual([self.idx(n) for n in (ALPHA, GAMMA, BETA)],
                         [STEP, STEP + STEP // 2, 2 * STEP])
        self.assertEqual(self.col_order("c0"), [ALPHA, GAMMA, BETA])

    def test_exhausted_gap_compacts_once_then_places(self):
        self.manager.task_datas[BETA].board_idx = 11
        self.manager.task_datas[BETA].reload_and_save_board_fields(("boardidx",))
        self.writes.clear()

        result = self.manager.reposition_task(
            GAMMA,
            self.manager.task_datas[ALPHA],
            self.manager.task_datas[BETA])

        self.assertTrue(result.compacted)
        self.assertEqual(self.respaces, ["c0"])
        self.assertEqual(self.col_order("c0"), [ALPHA, GAMMA, BETA])

    def test_compaction_is_confined_to_one_column(self):
        for name in (ALPHA, BETA, GAMMA):
            self.manager.task_datas[name].board_idx = 10
            self.manager.task_datas[name].reload_and_save_board_fields(("boardidx",))
        base = snapshot(self.tree)

        self.manager.reposition_task(GAMMA,
                                     self.manager.task_datas[ALPHA],
                                     self.manager.task_datas[BETA])

        changed = diff_snapshots(base, snapshot(self.tree))["changed"]
        self.assertTrue(all(p.split("/")[-1] in {ALPHA, BETA, GAMMA} for p in changed),
                        f"compaction escaped column c0: {changed}")

    def test_equal_index_move_is_no_longer_a_no_op(self):
        """The bug `reposition_task` replaces: exchanging two equal indices left
        both files byte-identical, so the card visibly did not move."""
        self.manager.task_datas[ALPHA].board_idx = 10
        self.manager.task_datas[BETA].board_idx = 10
        for name in (ALPHA, BETA):
            self.manager.task_datas[name].reload_and_save_board_fields(("boardidx",))
        self.assertEqual(self.col_order("c0"), [ALPHA, BETA, GAMMA])

        # Move BETA above ALPHA: it is at position 1, so there is no neighbour
        # above the destination slot.
        result = self.manager.reposition_task(
            BETA, None, self.manager.task_datas[ALPHA])

        self.assertTrue(result.ok)
        self.assertEqual(self.col_order("c0"), [BETA, ALPHA, GAMMA],
                         "the card must actually move")

    def test_child_is_refused(self):
        result = self.manager.reposition_task(CHILD, None, None)
        self.assertEqual(result.refused, ((CHILD, "not_a_parent_task"),))
        self.assert_untouched()


class RespaceColumnTests(_ManagerBase):
    def test_renumbers_to_the_stride(self):
        self.manager.respace_column("c0")
        self.assertEqual([self.idx(n) for n in (ALPHA, BETA, GAMMA)],
                         [STEP, 2 * STEP, 3 * STEP])
        self.assertEqual(self.writes, [ALPHA, BETA, GAMMA])

    def test_explicit_stride(self):
        self.manager.respace_column("c0", stride=10)
        self.assertEqual([self.idx(n) for n in (ALPHA, BETA, GAMMA)], [10, 20, 30])

    def test_writes_only_where_the_value_differs(self):
        """Already-canonical entries must not be rewritten — the guard the old
        `normalize_indices` had, preserved through the rename."""
        self.manager.respace_column("c0", stride=10)
        self.assertEqual(self.writes, [], "10/20/30 is already 10-spaced")

    def test_preserves_rendered_order(self):
        self.manager.task_datas[GAMMA].board_idx = 5
        self.manager.task_datas[GAMMA].reload_and_save_board_fields(("boardidx",))
        order_before = self.col_order("c0")
        self.manager.respace_column("c0")
        self.assertEqual(self.col_order("c0"), order_before)

    def test_does_not_touch_other_columns(self):
        base = snapshot(self.tree)
        self.manager.respace_column("c0")
        changed = diff_snapshots(base, snapshot(self.tree))["changed"]
        self.assertEqual(changed, {f"aitasks/{n}" for n in (ALPHA, BETA, GAMMA)})


class QuotedBoardIdxTests(_ManagerBase):
    """The raw-value `TypeError` the old `max()` / `±10` arithmetic raised.

    Every index read now goes through `normalize_board_idx`, so a hand-quoted
    `boardidx: "20"` sitting next to ints sorts and computes correctly instead of
    crashing the board.
    """

    def _quote(self, filename: str, value: str):
        task = self.manager.task_datas[filename]
        task.metadata["boardidx"] = value
        task.reload_and_save_board_fields(("boardidx",))
        self.writes.clear()

    def test_append_over_a_quoted_index(self):
        self._quote(EPSILON, "20")
        result = self.manager.move_task_to_column(GAMMA, "c1")
        self.assertTrue(result.ok)
        self.assertEqual(self.idx(GAMMA), 20 + STEP)

    def test_edge_move_over_a_quoted_index(self):
        self._quote(BETA, "20")
        result = self.manager.move_task_to_edge(ALPHA, "c0", to_top=False)
        self.assertTrue(result.ok)
        self.assertEqual(self.idx(ALPHA), 30 + STEP)

    def test_reposition_over_quoted_neighbours(self):
        self._quote(ALPHA, "10")
        self._quote(BETA, "20")
        result = self.manager.reposition_task(
            GAMMA,
            self.manager.task_datas[ALPHA],
            self.manager.task_datas[BETA])
        self.assertTrue(result.ok)
        self.assertEqual(self.idx(GAMMA), 15)

    def test_respace_over_a_quoted_index(self):
        self._quote(BETA, "20")
        self.manager.respace_column("c0", stride=10)
        self.assertEqual(self.writes, [],
                         "a quoted '20' equals 20 — it must not be rewritten")


class RetryAssertionTests(_ManagerBase):
    """The in-code assertion guarding the post-respace retry.

    It is unreachable by construction (`stride_for` makes every post-respace gap
    wide enough), so the only way to show it is not vacuous is to break the
    guarantee deliberately and watch it fire. A test asserting only the happy
    path would pass even if the branch raised on every compaction.
    """

    def test_retry_assertion_fires_when_the_stride_guarantee_is_broken(self):
        for name in (ALPHA, BETA, GAMMA):
            self.manager.task_datas[name].board_idx = 10
            self.manager.task_datas[name].reload_and_save_board_fields(("boardidx",))

        with mock.patch.object(BO, "respace_indices",
                               lambda n, stride=BO.STEP: list(range(1, n + 1))):
            with self.assertRaises(AssertionError) as ctx:
                self.manager.reposition_task(
                    GAMMA,
                    self.manager.task_datas[ALPHA],
                    self.manager.task_datas[BETA])
        self.assertIn("retry after respace", str(ctx.exception))

    def test_the_same_move_succeeds_without_the_mutation(self):
        """Negative control for the control: proves the AssertionError above came
        from the broken stride and not from the scenario itself."""
        for name in (ALPHA, BETA, GAMMA):
            self.manager.task_datas[name].board_idx = 10
            self.manager.task_datas[name].reload_and_save_board_fields(("boardidx",))
        result = self.manager.reposition_task(
            GAMMA,
            self.manager.task_datas[ALPHA],
            self.manager.task_datas[BETA])
        self.assertTrue(result.ok)
        self.assertTrue(result.compacted)


class SeamGuardTests(unittest.TestCase):
    """The arithmetic must stay in the pure module.

    Mirrors `tests/test_trail_gather.BoardSeamGuardTests`, the precedent from the
    `topic_semantics` extraction: keep the behaviour tests green AND assert the
    definitions did not stay behind in the board.
    """

    def test_board_imports_board_ordering(self):
        src = (REPO_ROOT / ".aitask-scripts" / "board" / "aitask_board.py"
               ).read_text(encoding="utf-8")
        self.assertIn("import board_ordering", src)
        for symbol in ("def index_between(", "def indices_between(",
                       "def index_for_append(", "def index_for_prepend(",
                       "def respace_indices(", "def stride_for("):
            self.assertNotIn(symbol, src,
                             f"{symbol} must live in lib/board_ordering.py")

    def test_board_ordering_is_headless(self):
        src = (REPO_ROOT / ".aitask-scripts" / "lib" / "board_ordering.py"
               ).read_text(encoding="utf-8")
        for forbidden in ("import textual", "from textual", "import aitask_board"):
            self.assertNotIn(forbidden, src)

    def test_the_retired_methods_are_gone(self):
        """`move_task_col` / `swap_tasks` / `normalize_indices` are removed, not
        aliased — a dead alias is an unread duplicate."""
        for name in ("move_task_col", "swap_tasks", "normalize_indices"):
            self.assertFalse(hasattr(B.TaskManager, name),
                             f"TaskManager.{name} should have been removed")


if __name__ == "__main__":
    unittest.main()
