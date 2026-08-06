"""Manager-level contract for column merge + rename migration (t1377_4).

`TaskManager.merge_columns` is headless-first: t1377_5 builds the dialog, so
nothing in the UI calls it yet and these tests are its only exercise. That makes
the failure-path coverage load-bearing rather than decorative.

Three traps drive the shape of this file:

1. **The `Task`-object trap.** `move_tasks_to_column` resolves names through
   `task_datas`, a dict keyed by FILENAME. Passing the `Task` objects
   `get_column_tasks` returns makes every lookup miss and refuses the batch
   silently, writing nothing. So the happy-path tests assert the RE-READ on-disk
   `boardcol`, never just the returned object — a `merge_columns` that swallowed
   the inner `MoveResult` and reported its own success would pass an
   object-only assertion.

2. **In-memory/disk divergence on a failed write.** `reload_and_save_board_fields`
   re-applies the already-mutated values after its own reload, so a raising save
   leaves `task.board_col` at the destination while disk still says the source.
   `get_column_tasks` filters on that in-memory value, so a same-manager retry
   would skip the task, find the source empty, and remove the column — orphaning
   it. Hence recovery is tested on the SAME manager as the failure, not only on a
   fresh one: a fresh instance reloads from disk and masks the bug entirely.

3. **The two metadata write boundaries need opposite handling.** `save_metadata`
   writes PROJECT keys (`columns`/`column_order`) and USER keys (`settings`,
   holding `collapsed_columns`) to two separate files, project first. Rolling
   back after the project write already landed would make a later
   `save_metadata()` resurrect the merged-away columns, because `self.columns` is
   written wholesale.

Harness mirrors `tests/test_board_manager_moves.py`: no Pilot, no app, no git —
`TaskManager.__init__` reads the module globals at call time, so patching the
module attributes redirects it.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m unittest tests.test_board_column_manage -v
"""

from __future__ import annotations

import json
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
import aitask_board as B  # noqa: E402

#: Three populated columns so an N->1 merge has two distinct sources whose
#: relative order must survive, plus a task with no boardcol feeding the
#: synthetic `unordered` lane.
TOPOLOGY = (
    FixtureTask(task_id="9001", col="c0", idx=10, slug="alpha"),
    FixtureTask(task_id="9002", col="c0", idx=20, slug="beta"),
    FixtureTask(task_id="9003", col="c1", idx=10, slug="gamma"),
    FixtureTask(task_id="9004", col="c1", idx=20, slug="delta"),
    FixtureTask(task_id="9005", col="c2", idx=10, slug="epsilon"),
)

ALPHA = "t9001_alpha.md"
BETA = "t9002_beta.md"
GAMMA = "t9003_gamma.md"
DELTA = "t9004_delta.md"
EPSILON = "t9005_epsilon.md"


class _ManagerBase(unittest.TestCase):
    FIXTURE_SETTINGS: dict | None = None
    FIXTURE_TOPOLOGY = TOPOLOGY

    def setUp(self):
        root = Path(tempfile.mkdtemp(prefix="aitask-colmerge-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        self.tree = build_fixture_tree(root, self.FIXTURE_TOPOLOGY,
                                       settings=self.FIXTURE_SETTINGS)
        self.tasks_dir = self.tree / "aitasks"
        self.metadata_file = self.tasks_dir / "metadata" / "board_config.json"
        for attr, value in (("TASKS_DIR", self.tasks_dir),
                            ("METADATA_FILE", self.metadata_file)):
            patcher = mock.patch.object(B, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.manager = B.TaskManager()
        self.events: list[tuple[str, str]] = []
        #: Fault-injection state, mutated in place so a test can arm and disarm
        #: the fault WITHOUT stopping any patch. `mock.patch.stopall()` would
        #: also drop the TASKS_DIR / METADATA_FILE patches above and silently
        #: re-point the manager at the real repository.
        self.fault = {"fail_on": None, "n": 0, "hook": None}
        self._spy_writes()
        self.before = snapshot(self.tree)

    def arm(self, fail_on: int, hook=None):
        """Fail the Nth board-field write from now on (counter resets)."""
        self.fault.update({"fail_on": fail_on, "n": 0, "hook": hook})

    def disarm(self):
        self.fault.update({"fail_on": None, "n": 0, "hook": None})

    def _spy_writes(self):
        """Record every board-field write; optionally raise on the armed Nth.

        This is both the write spy and the fault-injection seam — the same patch
        point the production write path uses.
        """
        original = B.Task.reload_and_save_board_fields

        def wrapper(self_, fields):
            self.fault["n"] += 1
            if self.fault["fail_on"] == self.fault["n"]:
                if self.fault["hook"] is not None:
                    self.fault["hook"](self_)
                raise OSError(28, "No space left on device")
            self.events.append(("write", self_.filename))
            return original(self_, fields)

        p = mock.patch.object(B.Task, "reload_and_save_board_fields", wrapper)
        p.start()
        self.addCleanup(p.stop)

    # --- helpers ----------------------------------------------------------

    def disk_col(self, filename: str) -> str:
        """Re-read a task's boardcol FROM DISK, bypassing the in-memory copy."""
        text = (self.tasks_dir / filename).read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("boardcol:"):
                return line.split(":", 1)[1].strip()
        return B.UNORDERED_ID

    def disk_idx(self, filename: str) -> int:
        text = (self.tasks_dir / filename).read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("boardidx:"):
                return int(line.split(":", 1)[1].strip())
        return 0

    def project_cols(self) -> list[str]:
        data = json.loads(self.metadata_file.read_text(encoding="utf-8"))
        return [c["id"] for c in data.get("columns", [])]

    def project_order(self) -> list[str]:
        data = json.loads(self.metadata_file.read_text(encoding="utf-8"))
        return list(data.get("column_order", []))

    def fresh_manager(self):
        """A brand-new TaskManager over the same tree (reloads from disk)."""
        return B.TaskManager()

    def col_order(self, col_id: str) -> list[str]:
        return [t.filename for t in self.manager.get_column_tasks(col_id)]

    def assert_untouched(self):
        self.assertEqual(
            diff_snapshots(self.before, snapshot(self.tree)),
            {"changed": set(), "added": set(), "removed": set()},
            "a refused merge must leave the tree byte-identical "
            "(this covers board_config*.json, so it also proves no save_metadata)")


# =====================================================================
# Pre-phase (risk mitigations) — characterize what merge sits beside.
# =====================================================================

class DeleteColumnDrainCharacterizationTests(_ManagerBase):
    """[characterize_delete_column_drain] Pin delete_column's CURRENT drain.

    `merge_columns` is a second drain path alongside `delete_column`, with
    deliberately different index arithmetic: merge appends fresh gap indices,
    delete flattens every task to 0. t1243_11 §4 intends to replace this flat
    tie with contiguous order-preserving indices. When it does, THIS test is
    expected to fail — that is the point. It converts a silent behavioural shift
    into a named failing expectation.
    """

    FIXTURE_SETTINGS = {"collapsed_columns": ["c0"]}

    def test_delete_column_flattens_indices_to_zero(self):
        self.manager.delete_column("c0")

        for name in (ALPHA, BETA):
            self.assertEqual(self.disk_col(name), B.UNORDERED_ID)
            # The mass-tie t1243_11 §4 replaces. If this assertion fails, check
            # whether that task landed and reuse its re-index helper here.
            self.assertEqual(self.disk_idx(name), 0)

    def test_delete_column_removes_config_and_collapsed_entry(self):
        self.manager.delete_column("c0")
        self.assertNotIn("c0", self.project_cols())
        self.assertNotIn("c0", self.project_order())
        self.assertNotIn("c0", self.manager.collapsed_columns)


class WriteBeforeConfigOrderingTests(_ManagerBase):
    """[pin_write_before_config_ordering] Task writes precede config removal.

    "Ordering is the safety property": a crash between the two must leave the
    source column present holding unmoved members, never tasks pointing at a
    column that no longer exists. Asserting the rule directly means a future
    refactor that hoists config removal earlier fails loudly instead of silently
    orphaning tasks into a lane that renders nowhere.
    """

    def _spy_config(self):
        original = B.TaskManager.save_metadata

        def wrapper(self_):
            self.events.append(("config", ",".join(self_.column_order)))
            return original(self_)

        p = mock.patch.object(B.TaskManager, "save_metadata", wrapper)
        p.start()
        self.addCleanup(p.stop)

    def test_every_member_write_precedes_the_config_removal(self):
        self._spy_config()
        result = self.manager.merge_columns(["c0", "c1"], "c2")
        self.assertTrue(result.complete, result)

        kinds = [kind for kind, _ in self.events]
        self.assertIn("config", kinds, "merge must persist the column removal")
        first_config = kinds.index("config")
        self.assertEqual(
            kinds[:first_config], ["write"] * first_config,
            "every task write must precede the first config write")
        self.assertEqual(len([k for k in kinds if k == "write"]), 4)

    def test_config_write_sees_sources_already_removed(self):
        self._spy_config()
        self.manager.merge_columns(["c0"], "c2")
        config_events = [payload for kind, payload in self.events
                         if kind == "config"]
        self.assertTrue(config_events)
        self.assertNotIn("c0", config_events[-1].split(","))


# =====================================================================
# merge_columns — happy paths
# =====================================================================

class MergeHappyPathTests(_ManagerBase):
    def test_n_to_1_merge_lands_on_disk_in_column_order(self):
        result = self.manager.merge_columns(["c1", "c0"], "c2")

        self.assertTrue(result.complete, result)
        self.assertEqual(set(result.sources_removed), {"c0", "c1"})

        # Re-read from disk: the object-only assertion would pass even if the
        # inner MoveResult had been swallowed.
        for name in (ALPHA, BETA, GAMMA, DELTA):
            self.assertEqual(self.disk_col(name), "c2", name)

        # Sources are processed in column_order order regardless of caller order,
        # and relative order within each source survives.
        self.assertEqual(self.col_order("c2"),
                         [EPSILON, ALPHA, BETA, GAMMA, DELTA])

        indices = [self.disk_idx(n) for n in (ALPHA, BETA, GAMMA, DELTA)]
        self.assertEqual(indices, sorted(indices), "indices must ascend")
        self.assertEqual(len(set(indices)), 4, "indices must be distinct")

        self.assertEqual(self.project_cols(), ["c2", "c3", "c4"])
        self.assertEqual(self.project_order(), ["c2", "c3", "c4"])

    def test_merge_never_respaces(self):
        with mock.patch.object(B.TaskManager, "respace_column") as respace:
            self.manager.merge_columns(["c0"], "c2")
        respace.assert_not_called()


class UnorderedLaneTests(_ManagerBase):
    def setUp(self):
        super().setUp()
        # Put a task in the synthetic lane by clearing its boardcol on disk.
        self.manager.move_tasks_to_column([EPSILON], B.UNORDERED_ID)
        self.manager = self.fresh_manager()

    def test_unordered_as_source_skips_config_removal(self):
        result = self.manager.merge_columns([B.UNORDERED_ID], "c0")

        self.assertTrue(result.complete, result)
        self.assertEqual(self.disk_col(EPSILON), "c0")
        # No ValueError from column_order.remove(), and nothing to remove.
        self.assertEqual(result.sources_removed, (B.UNORDERED_ID,))
        self.assertNotIn(B.UNORDERED_ID, self.project_order())
        self.assertEqual(self.project_cols(), ["c0", "c1", "c2", "c3", "c4"])

    def test_unordered_as_destination_removes_nothing_extra(self):
        result = self.manager.merge_columns(["c0"], B.UNORDERED_ID)

        self.assertTrue(result.complete, result)
        for name in (ALPHA, BETA):
            self.assertEqual(self.disk_col(name), B.UNORDERED_ID)
        self.assertEqual(self.project_cols(), ["c1", "c2", "c3", "c4"])

    def test_mixed_sources_order_unordered_last(self):
        result = self.manager.merge_columns([B.UNORDERED_ID, "c1", "c0"], "c3")

        self.assertTrue(result.complete, result)
        # Configured columns in column_order order, then the synthetic lane.
        self.assertEqual(self.col_order("c3"),
                         [ALPHA, BETA, GAMMA, DELTA, EPSILON])


class CollapsedStateTests(_ManagerBase):
    FIXTURE_SETTINGS = {"collapsed_columns": ["c0", "c2"]}

    def test_collapsed_source_pruned_destination_kept(self):
        result = self.manager.merge_columns(["c0"], "c2")

        self.assertTrue(result.complete, result)
        self.assertNotIn("c0", self.manager.collapsed_columns)
        self.assertIn("c2", self.manager.collapsed_columns)
        self.assertTrue(self.fresh_manager().is_column_collapsed("c2"))


# =====================================================================
# merge_columns — refusals (nothing written, config included)
# =====================================================================

class MergeRefusalTests(_ManagerBase):
    def test_unknown_source_is_refused_and_writes_nothing(self):
        result = self.manager.merge_columns(["c0", "nope"], "c2")

        self.assertFalse(result.complete)
        self.assertIn(("nope", "unknown_column"), result.refused)
        self.assertEqual(result.merged, ())
        self.assertEqual(result.sources_removed, ())
        self.assert_untouched()

    def test_destination_in_sources_is_refused(self):
        result = self.manager.merge_columns(["c0", "c2"], "c2")
        self.assertIn(("c2", "source_is_destination"), result.refused)
        self.assert_untouched()

    def test_empty_sources_is_refused(self):
        result = self.manager.merge_columns([], "c2")
        self.assertEqual(result.refused, (("", "no_source_columns"),))
        self.assert_untouched()

    def test_duplicate_source_is_refused_once(self):
        result = self.manager.merge_columns(["c0", "c0"], "c2")
        self.assertEqual(
            [r for r in result.refused if r[1] == "duplicate_source"],
            [("c0", "duplicate_source")])
        self.assert_untouched()

    def test_unknown_destination_is_refused(self):
        result = self.manager.merge_columns(["c0"], "nope")
        self.assertIn(("nope", "unknown_destination"), result.refused)
        self.assert_untouched()


# =====================================================================
# t1377_3 interaction: the reconciler must not resurrect a merged source
# =====================================================================

class ReconcileSurvivalTests(_ManagerBase):
    def test_merged_source_stays_gone_for_a_fresh_manager(self):
        self.manager.merge_columns(["c0"], "c2")

        # save_metadata runs _reconcile_external_columns, which re-reads the
        # on-disk columns. A source we deleted is in _known_col_ids, so the
        # "known, absent from self.columns -> deletion sticks" row must hold.
        fresh = self.fresh_manager()
        self.assertNotIn("c0", [c["id"] for c in fresh.columns])
        self.assertNotIn("c0", fresh.column_order)

    def test_a_later_save_does_not_resurrect_the_source(self):
        self.manager.merge_columns(["c0"], "c2")
        self.manager.toggle_column_collapsed("c3")
        self.assertNotIn("c0", self.project_cols())


# =====================================================================
# Partial recovery — the divergence trap
# =====================================================================

class PartialMergeRecoveryTests(_ManagerBase):
    """Fault-inject the Nth board-field write and prove convergence.

    The fixture's c0 holds two members, so failing on the 2nd write leaves one
    moved and one not.
    """

    def test_partial_state_is_safe_and_self_describing(self):
        self.arm(fail_on=2)

        result = self.manager.merge_columns(["c0"], "c2")

        self.assertFalse(result.complete)
        self.assertEqual(self.disk_col(ALPHA), "c2", "first member moved")
        self.assertEqual(self.disk_col(BETA), "c0", "second member did not")

        # The source is still present, holding its unmoved member.
        self.assertIn("c0", self.project_cols())
        self.assertIn("c0", self.project_order())
        self.assertEqual(result.sources_removed, ())

        # The I/O casualty is named; nothing else is blamed for it.
        reasons = dict(result.failed)
        self.assertIn(BETA, reasons)
        self.assertTrue(reasons[BETA].startswith("write_failed:"), reasons)

        # THE divergence assertion: in-memory must have been reconciled back to
        # disk, or a same-manager retry would not see BETA in c0 at all.
        self.assertEqual(self.manager.task_datas[BETA].board_col, "c0")
        self.assertIn(BETA, self.col_order("c0"))

    def test_same_manager_retry_converges(self):
        self.arm(fail_on=2)
        self.manager.merge_columns(["c0"], "c2")

        # Clear the injection, keep the SAME manager — this is the path the
        # stale in-memory mutation would break.
        self.disarm()
        result = self.manager.merge_columns(["c0"], "c2")

        self.assertTrue(result.complete, result)
        self.assertEqual(self.disk_col(BETA), "c2")
        self.assertEqual(result.sources_removed, ("c0",))
        self.assertNotIn("c0", self.project_cols())

    def test_fresh_manager_retry_converges(self):
        self.arm(fail_on=2)
        self.manager.merge_columns(["c0"], "c2")

        self.disarm()
        result = self.fresh_manager().merge_columns(["c0"], "c2")

        self.assertTrue(result.complete, result)
        self.assertEqual(self.disk_col(BETA), "c2")
        self.assertNotIn("c0", self.project_cols())

    def test_vanished_file_is_reported_not_counted_as_merged(self):
        self.arm(fail_on=2,
                 hook=lambda task: (self.tasks_dir / task.filename).unlink())

        result = self.manager.merge_columns(["c0"], "c2")

        self.assertFalse(result.complete)
        self.assertIn((BETA, "file_missing"), result.failed)
        self.assertNotIn(BETA, result.merged)
        self.assertEqual(result.sources_removed, ())


class SilentSkipTests(_ManagerBase):
    """A member can fail to land with NO exception at all.

    `reload_and_save_board_fields` returns early when its reload fails — a
    deleted file, but also a permission or decode error on a file that still
    exists — and `move_tasks_to_column` reports that task in `moved` anyway. If
    `merge_columns` trusted the nominal return it would drain the source and,
    in the still-exists case, strand a task on a column that no longer exists.
    """

    def _delete_before_write(self, victim):
        """Delete `victim`'s file just before its write, raising nothing."""
        original = B.Task.reload_and_save_board_fields

        def wrapper(self_, fields):
            if self_.filename == victim:
                # missing_ok: the hook stays installed across a retry, and the
                # file is already gone by then.
                (self.tasks_dir / victim).unlink(missing_ok=True)
            return original(self_, fields)

        p = mock.patch.object(B.Task, "reload_and_save_board_fields", wrapper)
        p.start()
        self.addCleanup(p.stop)

    def test_deleted_member_is_not_reported_merged_without_an_oserror(self):
        self._delete_before_write(BETA)

        result = self.manager.merge_columns(["c0"], "c2")

        # The whole point: no OSError was raised anywhere.
        self.assertFalse(result.complete, "a vanished member is not a success")
        self.assertNotIn(BETA, result.merged)
        self.assertIn((BETA, "file_missing"), result.failed)
        self.assertIn(ALPHA, result.merged)

    def test_source_is_retained_when_a_member_silently_skipped(self):
        self._delete_before_write(BETA)
        result = self.manager.merge_columns(["c0"], "c2")

        self.assertEqual(result.sources_removed, ())
        self.assertIn("c0", self.project_cols())
        self.assertIn("c0", self.project_order())

    def test_unreadable_member_does_not_get_orphaned(self):
        """The harmful variant: the file EXISTS and still says the source.

        Draining here would remove c0 while BETA's frontmatter still reads
        `boardcol: c0`, leaving it rendered by no column at all.
        """
        original = B.Task.reload_and_save_board_fields

        def wrapper(self_, fields):
            if self_.filename == BETA:
                # Present but unreadable -> Task.load() returns False, no raise.
                self_.filepath.write_bytes(b"\xff\xfe not valid utf-8")
                return original(self_, fields)
            return original(self_, fields)

        p = mock.patch.object(B.Task, "reload_and_save_board_fields", wrapper)
        p.start()
        self.addCleanup(p.stop)

        result = self.manager.merge_columns(["c0"], "c2")

        self.assertFalse(result.complete)
        self.assertNotIn(BETA, result.merged)
        self.assertEqual(result.sources_removed, ())
        self.assertIn("c0", self.project_cols())
        self.assertTrue((self.tasks_dir / BETA).exists())

    def _corrupt_before_write(self, victim):
        """Make `victim` present-but-unreadable just before its write."""
        original = B.Task.reload_and_save_board_fields

        def wrapper(self_, fields):
            if self_.filename == victim and self_.filepath.exists():
                self_.filepath.write_bytes(b"\xff\xfe not valid utf-8")
            return original(self_, fields)

        p = mock.patch.object(B.Task, "reload_and_save_board_fields", wrapper)
        p.start()
        self.addCleanup(p.stop)
        return p

    def test_same_manager_retry_does_not_drain_an_unverifiable_source(self):
        """The retry is where the orphan happens without tracking.

        The failed `Task.load()` wiped BETA's metadata, so `get_column_tasks`
        no longer lists it in c0 — the source looks empty and a naive retry
        removes it while BETA's file still reads `boardcol: c0`.
        """
        self._corrupt_before_write(BETA)
        self.manager.merge_columns(["c0"], "c2")

        result = self.manager.merge_columns(["c0"], "c2")

        self.assertFalse(result.complete, result)
        self.assertEqual(result.sources_removed, ())
        self.assertIn("c0", self.project_cols())
        self.assertIn(B.MERGE_UNVERIFIABLE_KEY, dict(result.failed))
        self.assertTrue((self.tasks_dir / BETA).exists())

    def test_fresh_manager_retry_does_not_drain_an_unverifiable_source(self):
        """A fresh manager has no memory of the failure — it must re-derive it.

        `load_tasks` drops an unreadable file as a phantom stub, so without
        tracking it at load time the fresh manager sees an empty c0 and removes
        it.
        """
        self._corrupt_before_write(BETA)
        self.manager.merge_columns(["c0"], "c2")

        fresh = self.fresh_manager()
        self.assertIn(BETA, fresh.unreadable_files)

        result = fresh.merge_columns(["c0"], "c2")
        self.assertEqual(result.sources_removed, ())
        self.assertIn("c0", self.project_cols())

    def _repair(self, name, col):
        (self.tasks_dir / name).write_text(
            "---\npriority: medium\nissue_type: feature\n"
            f"status: Ready\nboardcol: {col}\nboardidx: 20\n---\n\nrepaired\n",
            encoding="utf-8")

    def test_same_manager_converges_after_the_file_is_repaired(self):
        """The block must lift WITHOUT reconstructing the manager.

        `unreadable_files` is otherwise cleared only by `load_tasks`, so the
        stale entry would keep this manager refusing forever. A fresh manager
        re-runs `load_tasks` and hides that entirely — which is why the
        fresh-manager recovery test below is not sufficient on its own.
        """
        patcher = self._corrupt_before_write(BETA)
        self.manager.merge_columns(["c0"], "c2")
        self.assertIn(BETA, self.manager.unreadable_files)
        patcher.stop()

        self._repair(BETA, "c0")

        # Same manager object, no reload.
        result = self.manager.merge_columns(["c0"], "c2")

        self.assertTrue(result.complete, result)
        self.assertNotIn(BETA, self.manager.unreadable_files)
        self.assertIn(BETA, result.merged, "the repaired task must actually move")
        self.assertEqual(self.disk_col(BETA), "c2")
        self.assertEqual(result.sources_removed, ("c0",))
        self.assertNotIn("c0", self.project_cols())

    def test_converges_once_the_file_becomes_readable_again(self):
        """The block is until-readable, not permanent."""
        patcher = self._corrupt_before_write(BETA)
        self.manager.merge_columns(["c0"], "c2")
        patcher.stop()
        self.addCleanup(lambda: None)

        # Restore a readable file still claiming the source column.
        (self.tasks_dir / BETA).write_text(
            "---\npriority: medium\nissue_type: feature\n"
            "status: Ready\nboardcol: c0\nboardidx: 20\n---\n\nBeta\n",
            encoding="utf-8")

        result = self.fresh_manager().merge_columns(["c0"], "c2")

        self.assertTrue(result.complete, result)
        self.assertEqual(result.sources_removed, ("c0",))
        self.assertEqual(self.disk_col(BETA), "c2")
        self.assertNotIn("c0", self.project_cols())

    def test_retry_after_a_deleted_member_converges(self):
        self._delete_before_write(BETA)
        self.manager.merge_columns(["c0"], "c2")

        # The vanished task drops out of the source (its wiped metadata no
        # longer claims c0), so the retry sees only real members and completes.
        result = self.manager.merge_columns(["c0"], "c2")
        self.assertTrue(result.complete, result)
        self.assertEqual(result.sources_removed, ("c0",))
        self.assertNotIn("c0", self.project_cols())


class AttemptBoundaryTests(_ManagerBase):
    """The casualty is fixed by SOURCE ORDER, not by list position.

    Needs a THREE-member source: with two, the failing member is the last one
    and no following member exists to be misattributed, so the two-member cases
    above pass vacuously on this path.
    """

    FIXTURE_TOPOLOGY = (
        FixtureTask(task_id="9001", col="c0", idx=10, slug="alpha"),
        FixtureTask(task_id="9002", col="c0", idx=20, slug="beta"),
        FixtureTask(task_id="9006", col="c0", idx=30, slug="zeta"),
        FixtureTask(task_id="9005", col="c2", idx=10, slug="epsilon"),
    )
    ZETA = "t9006_zeta.md"

    def test_following_member_is_not_attempted_not_blamed(self):
        self.arm(fail_on=2)
        result = self.manager.merge_columns(["c0"], "c2")

        reasons = dict(result.failed)
        self.assertTrue(reasons[BETA].startswith("write_failed:"), reasons)
        self.assertEqual(reasons[self.ZETA], "not_attempted", reasons)

    def test_vanished_casualty_does_not_shift_blame_to_the_next_member(self):
        # The regression: BETA both fails AND disappears. Filtering it out
        # before deriving the boundary promotes ZETA to position 0, so ZETA —
        # never attempted — gets reported as the I/O casualty.
        self.arm(fail_on=2,
                 hook=lambda task: (self.tasks_dir / task.filename).unlink())
        result = self.manager.merge_columns(["c0"], "c2")

        reasons = dict(result.failed)
        self.assertEqual(reasons[BETA], "file_missing", reasons)
        self.assertEqual(reasons[self.ZETA], "not_attempted", reasons)
        self.assertNotIn("write_failed", reasons[self.ZETA])


# =====================================================================
# Metadata write boundaries — opposite handling
# =====================================================================

class MetadataFailureTests(_ManagerBase):
    FIXTURE_SETTINGS = {"collapsed_columns": ["c0"]}

    def test_boundary_a_project_write_rolls_back_and_merge_retry_converges(self):
        with mock.patch.object(B, "save_project_config",
                               side_effect=OSError(28, "No space")):
            result = self.manager.merge_columns(["c0"], "c2")

        self.assertFalse(result.complete)
        self.assertIn(B.MERGE_METADATA_KEY, dict(result.failed))
        self.assertEqual(result.sources_removed, ())

        # Task moves persisted; config did not. In-memory rolled back to match.
        self.assertEqual(self.disk_col(ALPHA), "c2")
        self.assertIn("c0", [c["id"] for c in self.manager.columns])
        self.assertIn("c0", self.project_cols())

        # Retry IS merge_columns here, on the same manager and on a fresh one.
        self.assertTrue(self.manager.merge_columns(["c0"], "c2").complete)
        self.assertNotIn("c0", self.project_cols())

    def test_boundary_b_local_write_keeps_removal_and_reports_asymmetrically(self):
        with mock.patch.object(B, "save_local_config",
                               side_effect=OSError(28, "No space")):
            result = self.manager.merge_columns(["c0"], "c2")

        self.assertFalse(result.complete)
        self.assertIn(B.MERGE_METADATA_LOCAL_KEY, dict(result.failed))
        # The merge DID land: report it as such.
        self.assertEqual(result.sources_removed, ("c0",))

        # Project half is durable...
        self.assertNotIn("c0", self.project_cols())
        # ...and in-memory was NOT rolled back to contradict it.
        self.assertNotIn("c0", [c["id"] for c in self.manager.columns])
        self.assertNotIn("c0", self.manager.column_order)

    def test_boundary_b_retry_is_save_metadata_not_merge(self):
        with mock.patch.object(B, "save_local_config",
                               side_effect=OSError(28, "No space")):
            self.manager.merge_columns(["c0"], "c2")

        # A fresh manager cannot retry the MERGE: the columns are already gone,
        # so the sources are correctly unknown. This replaces the impossible
        # "fresh manager re-runs the merge" assertion.
        fresh = self.fresh_manager()
        retry = fresh.merge_columns(["c0"], "c2")
        self.assertIn(("c0", "unknown_column"), retry.refused)

        # The real retry is the metadata save.
        self.manager.save_metadata()
        self.assertNotIn("c0", self.fresh_manager().collapsed_columns)

    def test_boundary_b_later_save_does_not_resurrect_the_source(self):
        with mock.patch.object(B, "save_local_config",
                               side_effect=OSError(28, "No space")):
            self.manager.merge_columns(["c0"], "c2")

        # The regression a blanket rollback would cause: save_metadata writes
        # self.columns wholesale, so restored sources would reappear on disk.
        self.manager.toggle_column_collapsed("c3")
        self.assertNotIn("c0", self.project_cols())


# =====================================================================
# §4b load-time orphan prune + §4 rename migration
# =====================================================================

class OrphanCollapsedPruneTests(_ManagerBase):
    FIXTURE_SETTINGS = {"collapsed_columns": ["c0", "ghost"]}

    def test_orphan_entry_is_pruned_at_load(self):
        self.assertNotIn("ghost", self.manager.collapsed_columns)
        self.assertIn("c0", self.manager.collapsed_columns)

    def test_prune_is_persisted_on_the_next_save(self):
        self.manager.save_metadata()
        self.assertNotIn("ghost", self.fresh_manager().collapsed_columns)


class OrphanPruneWhitelistTests(_ManagerBase):
    """Negative control for the §4b trap.

    `unordered` is collapsible but is deliberately absent from `columns`, so an
    unguarded "prune ids not in columns" would silently drop a legitimate
    collapse of the synthetic lane.
    """

    FIXTURE_SETTINGS = {"collapsed_columns": [B.UNORDERED_ID]}

    def test_unordered_survives_the_prune(self):
        self.assertIn(B.UNORDERED_ID, self.manager.collapsed_columns)
        self.assertTrue(self.manager.is_column_collapsed(B.UNORDERED_ID))
        self.manager.save_metadata()
        self.assertTrue(self.fresh_manager().is_column_collapsed(B.UNORDERED_ID))


class RenameMigratesCollapsedTests(_ManagerBase):
    FIXTURE_SETTINGS = {"collapsed_columns": ["c0"]}

    def test_rename_migrates_the_collapsed_entry(self):
        self.manager.update_column("c0", "c0new", "Renamed", "#FF5555")

        self.assertIn("c0new", self.manager.collapsed_columns)
        self.assertNotIn("c0", self.manager.collapsed_columns)
        # Survives a reload — and is not then eaten by the §4b prune, which is
        # the interaction a naive migration would get wrong.
        self.assertTrue(self.fresh_manager().is_column_collapsed("c0new"))

    def test_rename_still_moves_members_and_order(self):
        self.manager.update_column("c0", "c0new", "Renamed", "#FF5555")
        self.assertEqual(self.disk_col(ALPHA), "c0new")
        self.assertIn("c0new", self.project_order())


if __name__ == "__main__":
    unittest.main()
