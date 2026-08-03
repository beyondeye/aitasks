"""Render-filter scoping, the data-level filter primitives, and the targeted
dirty-marker update (t1243_4).

Three properties are pinned here, each with the negative control that proves the
assertion discriminates:

1. **The filter decision is computable from `Task` DATA, with no widget mounted.**
   t1243_10 evaluates collapsed-group members that mount no card at all, so
   `task_matches_filter` must never require a widget and the search corpus must
   live on the `Task`. The memo that makes that cheap has an invalidation
   contract; every site it claims to cover gets its own case, because a memo
   whose invalidation is tested "as a group" hides which site actually works.

2. **A scoped pass touches only the columns it names.** `apply_filter(cols=...)`
   must not re-decide, and must not flip, anything outside `cols`. The seeded
   sentinel is what makes that observable: a card pre-set to the *wrong* display
   in an untouched column stays wrong after a scoped pass and is corrected by an
   unscoped one.

3. **No movement path spawns a subprocess, and the dirty marker still lands.**
   Covered for all THREE action families (lateral / vertical / extreme), not just
   the lateral one — a `refresh_git_status()` left behind in any single family
   would otherwise pass. Every case first proves the move actually happened: an
   early-returned action writes nothing and spawns nothing, so "no subprocess"
   would pass vacuously (the same trap as the benchmark harness's zero-write
   validity invariant in tests/test_board_movement.py).

Run: bash tests/run_all_python_tests.sh
  or: python3 -m unittest tests.test_board_render_scoping -v
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402


# Promoted into the shared fixture module (t1243_5) so the DOM-transplant tests
# reuse it rather than forking a copy. Aliased here so this module's classes are
# unchanged.
_PristineTreeMixin = bf.PristineTreeMixin


class _RecordingStyles:
    """Minimal `styles` stand-in that counts assignments to `display`."""

    def __init__(self, display="block"):
        self._display = display
        self.writes = 0

    @property
    def display(self):
        return self._display

    @display.setter
    def display(self, value):
        self._display = value
        self.writes += 1


class _FakeUnit:
    """A filter unit that is deliberately NOT a TaskCard.

    `set_unit_display` must stay widget-kind-agnostic for t1243_10's collapsed
    group header, so the no-op guard is exercised through an object the board has
    never seen.
    """

    def __init__(self, display="block", column_id="c0"):
        self.styles = _RecordingStyles(display)
        self.column_id = column_id
        self.parent = None


class FilterPrimitivesTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """`task_matches_filter`, `Task.search_haystack`, `set_unit_display` — no app."""

    FIXTURE_TASKS = bf.DEFAULT_TOPOLOGY

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Task = cls.ab.Task

    def _task(self, name="t9000_parent.md"):
        return self.Task(self.tasks_dir / name)

    def test_fixture_facts(self):
        """The tasks these assertions select on really exist and carry metadata."""
        task = self._task()
        self.assertTrue(task.metadata,
                        "fixture task must carry frontmatter — a task whose keys are "
                        "a subset of BOARD_KEYS is dropped as a phantom stub and "
                        "every case below would pass vacuously")
        self.assertIn("priority", task.metadata)
        self.assertEqual(task.board_col, "c0")

    # --- the data-level predicate (the t1243_10 prerequisite) ----------------

    def test_predicate_decides_from_task_data_with_no_widget_mounted(self):
        """The whole point: no KanbanApp, no Pilot, no mounted card."""
        task = self._task()
        self.assertTrue(self.ab.task_matches_filter(task, None, ""))
        self.assertTrue(self.ab.task_matches_filter(task, None, "t9000"))
        self.assertFalse(self.ab.task_matches_filter(task, None, "zzz-no-such-text"))

    def test_predicate_honours_the_visible_set(self):
        task = self._task()
        self.assertTrue(self.ab.task_matches_filter(task, {task.filename}, ""))
        self.assertFalse(self.ab.task_matches_filter(task, set(), ""))
        self.assertFalse(self.ab.task_matches_filter(task, {"other.md"}, ""))

    def test_predicate_searches_metadata_not_only_the_filename(self):
        """The corpus is filename + the whole metadata dict — unchanged semantics."""
        task = self._task()
        self.assertTrue(self.ab.task_matches_filter(task, None, "priority"))

    # --- memo lifecycle: one case per claimed invalidation site --------------

    def test_haystack_is_memoized(self):
        task = self._task()
        self.assertIs(task.search_haystack, task.search_haystack,
                      "second read must return the memoized object, not a rebuild")

    def test_board_idx_setter_invalidates(self):
        task = self._task()
        before = task.search_haystack
        task.board_idx = 987654
        self.assertNotEqual(before, task.search_haystack)
        self.assertIn("987654", task.search_haystack)

    def test_board_col_setter_invalidates(self):
        task = self._task()
        before = task.search_haystack
        task.board_col = "c4"
        self.assertNotEqual(before, task.search_haystack)
        self.assertIn("c4", task.search_haystack)

    def test_load_invalidates(self):
        """`reload_task` calls `load()` on the SAME object — the memo must not survive."""
        task = self._task()
        task.metadata["boardidx"] = 424242
        task._invalidate_search_haystack()
        self.assertIn("424242", task.search_haystack)
        task.load()
        self.assertNotIn("424242", task.search_haystack,
                         "load() replaced metadata; the memo must have been dropped")

    def test_save_invalidates(self):
        task = self._task()
        original = task.filepath.read_bytes()
        self.addCleanup(task.filepath.write_bytes, original)
        _ = task.search_haystack
        task.metadata["labels"] = ["memo-probe"]
        task.save()
        self.assertIn("memo-probe", task.search_haystack,
                      "save() is the tail of every persisted metadata mutation, so it "
                      "must drop the memo")

    def test_from_text_instance_can_read_the_haystack(self):
        """`from_text` bypasses __init__ via `cls.__new__`.

        Without seeding the memo slot there, this raises AttributeError on every
        archived task the board resolves.
        """
        raw = (self.tasks_dir / "t9000_parent.md").read_text(encoding="utf-8")
        task = self.Task.from_text(Path("aitasks/archived/t9000_parent.md"), raw,
                                   archived=True)
        self.assertIn("t9000_parent.md", task.search_haystack)

    # --- the no-op display guard --------------------------------------------

    def test_set_unit_display_skips_a_no_op_assignment(self):
        unit = _FakeUnit(display="block")
        self.ab.set_unit_display(unit, True)
        self.assertEqual(unit.styles.writes, 0,
                         "assigning styles.display schedules a Textual refresh; an "
                         "unchanged value must not be reassigned")

    def test_set_unit_display_writes_when_the_value_changes(self):
        """The discriminating control for the case above."""
        unit = _FakeUnit(display="block")
        self.ab.set_unit_display(unit, False)
        self.assertEqual(unit.styles.writes, 1)
        self.assertEqual(unit.styles.display, "none")


class ScopedFilterTests(bf.FixtureBoardTestBase, _PristineTreeMixin, unittest.TestCase):
    """`apply_filter(cols=...)` restricts the pass to the columns it names."""

    FIXTURE_TASKS = bf.DEFAULT_TOPOLOGY

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.KanbanApp = cls.ab.KanbanApp
        cls.TaskCard = cls.ab.TaskCard
        cls.EmptyColumnPlaceholder = cls.ab.EmptyColumnPlaceholder
        cls._snapshot_pristine()

    def _run(self, coro):
        return asyncio.run(coro)

    def test_fixture_facts(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                cards = list(app.query(self.TaskCard))
                self.assertGreater(len(cards), 0, "fixture must mount cards")
                cols = {c.column_id for c in cards}
                self.assertGreaterEqual(
                    len(cols), 3,
                    "the scoping assertions need cards in at least three columns, "
                    "so an untouched column is available as a sentinel")
        self._run(go())

    def test_filter_units_yields_exactly_the_named_columns(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                scoped = list(app._filter_units({"c0", "c1"}))
                expected = app._get_column_cards("c0") + app._get_column_cards("c1")
                self.assertEqual(sorted(id(c) for c in scoped),
                                 sorted(id(c) for c in expected))
                # Discriminating control: the unscoped pass must be strictly wider.
                every = list(app._filter_units(None))
                self.assertEqual(sorted(id(c) for c in every),
                                 sorted(id(c) for c in app.query(self.TaskCard)))
                self.assertGreater(len(every), len(scoped),
                                   "if scoped and unscoped yield the same set the "
                                   "scoping assertion proves nothing")
        self._run(go())

    def test_filter_units_ignores_an_unmounted_column(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                self.assertEqual(list(app._filter_units({"no-such-column"})), [])
        self._run(go())

    def _untouched_sentinel(self, app, exclude):
        """A card in a column none of `exclude` names, pre-set to the wrong display."""
        for card in app.query(self.TaskCard):
            if card.column_id not in exclude:
                card.styles.display = "none"
                return card
        raise AssertionError("fixture has no column outside the moved pair")

    def test_scoped_pass_leaves_an_untouched_column_alone(self):
        """Seeded sentinel: a scoped pass must not correct a display it did not decide."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                sentinel = self._untouched_sentinel(app, {"c0", "c1"})
                app.apply_filter({"c0", "c1"})
                await pilot.pause()
                self.assertEqual(
                    sentinel.styles.display, "none",
                    f"scoped pass flipped {sentinel.task_data.filename} in untouched "
                    f"column {sentinel.column_id} — the scope is not being honoured")

                # Negative control: the unscoped pass MUST correct it. Without this
                # the case above would also pass if apply_filter did nothing at all.
                app.apply_filter()
                await pilot.pause()
                self.assertEqual(sentinel.styles.display, "block")
        self._run(go())

    def test_lateral_move_scopes_the_deferred_pass_to_the_touched_columns(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                card = next(c for c in app.query(self.TaskCard)
                            if not c.is_child and c.column_id == "c0")
                card.focus()
                await pilot.pause()

                seen = []
                real = app.apply_filter

                def spy(cols=None):
                    seen.append(cols)
                    return real(cols)

                app.apply_filter = spy
                sentinel = self._untouched_sentinel(app, {"c0", "c1"})
                await pilot.press("shift+right")
                await pilot.pause()
                await pilot.pause()

                self.assertTrue(seen, "the move must still run a filter pass")
                self.assertEqual(
                    seen[-1], {"c0", "c1"},
                    f"lateral move passed {seen[-1]!r}; it must scope to exactly the "
                    f"source and destination columns")
                self.assertEqual(
                    sentinel.styles.display, "none",
                    "the move's filter pass reached a column it did not touch")
        self._run(go())

    def test_scoped_pass_does_not_flip_an_untouched_placeholder(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                others = [p for p in app.query(self.EmptyColumnPlaceholder)
                          if p.column_id not in ("c0", "c1")]
                self.assertTrue(others, "fixture must mount placeholders outside c0/c1")
                probe = others[0]
                probe.styles.display = "block"

                app.apply_filter({"c0", "c1"})
                await pilot.pause()
                self.assertEqual(
                    probe.styles.display, "block",
                    f"scoped pass flipped the placeholder of untouched column "
                    f"{probe.column_id}; cols_with_visible says nothing about it")
        self._run(go())

    def test_search_still_hides_non_matching_cards(self):
        """The memoized corpus must keep whole-board search behaviour intact."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                app.search_filter = "t9003"
                app.apply_filter()
                await pilot.pause()
                shown = {c.task_data.filename for c in app.query(self.TaskCard)
                         if c.styles.display != "none"}
                self.assertTrue(shown, "the matching card must stay visible")
                self.assertTrue(all("t9003" in name for name in shown),
                                f"non-matching cards leaked past the search: {shown}")
        self._run(go())


class MovementSideEffectTests(bf.FixtureBoardTestBase, _PristineTreeMixin,
                              unittest.TestCase):
    """No movement family spawns a subprocess, and each still marks what it wrote."""

    #: 15 parents round-robin over five columns = 3 per column, so a mid-column
    #: card can move up, down, to either extreme, and laterally in both
    #: directions. A topology where a move early-returns makes "no subprocess"
    #: vacuously true.
    FIXTURE_TASKS = bf.wide_topology(15)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.KanbanApp = cls.ab.KanbanApp
        cls.TaskCard = cls.ab.TaskCard
        cls._snapshot_pristine()

    def _run(self, coro):
        return asyncio.run(coro)

    def _spy_writes(self):
        """Record which files `reload_and_save_board_fields` actually persisted."""
        written = []
        original = self.ab.Task.reload_and_save_board_fields

        def wrapper(task, fields):
            written.append(task.filename)
            return original(task, fields)

        patcher = mock.patch.object(self.ab.Task, "reload_and_save_board_fields",
                                    wrapper)
        patcher.start()
        self.addCleanup(patcher.stop)
        return written

    def test_fixture_facts(self):
        """Every column holds enough parents for every move to be performable."""
        manager = self.ab.TaskManager()
        for col in ("c0", "c1"):
            self.assertGreaterEqual(
                len(manager.get_column_tasks(col)), 3,
                f"column {col} needs >=3 parents or the extreme/vertical moves "
                f"early-return and their assertions become vacuous")

    def _drive_move(self, key, focus_filename):
        """Press `key` with `focus_filename` focused; return (written, spawns, marks)."""
        written = self._spy_writes()
        spawns: list[list[str]] = []
        real_run = subprocess.run

        def spy(argv, **kwargs):
            try:
                spawns.append([str(a) for a in argv])
            except TypeError:                       # shell=True string form
                spawns.append([str(argv)])
            return real_run(argv, **kwargs)

        state = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                card = next(c for c in app.query(self.TaskCard)
                            if not c.is_child
                            and c.task_data.filename == focus_filename)
                card.focus()
                await pilot.pause()
                before = set(app.manager.modified_files)
                del spawns[:]                       # discard boot-phase spawns
                del written[:]
                with mock.patch("subprocess.run", side_effect=spy):
                    await pilot.press(key)
                    await pilot.pause()
                    await pilot.pause()
                state["marks"] = set(app.manager.modified_files) - before
                state["manager"] = app.manager

        self._run(go())
        return written, spawns, state

    def _assert_move_is_silent_and_marked(self, key, focus_filename):
        written, spawns, state = self._drive_move(key, focus_filename)

        # 1. The move actually happened. Without this the two assertions below
        #    pass for a rejected action that did nothing at all.
        self.assertGreater(
            len(written), 0,
            f"{key} on {focus_filename} wrote nothing — the action early-returned, "
            f"so 'no subprocess' would be vacuously true")

        # 2. No subprocess. A refresh_git_status() left in this family shows up here.
        self.assertEqual(
            spawns, [],
            f"{key} spawned {spawns}; movement must not shell out per keypress")

        # 3. The dirty marker still landed, for exactly what was written.
        manager = state["manager"]
        expected = set()
        for name in written:
            task = (manager.task_datas.get(name)
                    or manager.child_task_datas.get(name))
            self.assertIsNotNone(task, f"written file {name} not resolvable")
            expected.add(str(task.filepath))
        self.assertEqual(
            state["marks"], expected,
            f"{key}: dirty marker set {state['marks']} does not match the files "
            f"actually written {expected}")

    def test_lateral_right_is_silent_and_marks(self):
        self._assert_move_is_silent_and_marked("shift+right", "t9005_wide5.md")

    def test_lateral_left_is_silent_and_marks(self):
        self._assert_move_is_silent_and_marked("shift+left", "t9006_wide6.md")

    def test_vertical_up_is_silent_and_marks(self):
        self._assert_move_is_silent_and_marked("shift+up", "t9005_wide5.md")

    def test_vertical_down_is_silent_and_marks(self):
        self._assert_move_is_silent_and_marked("shift+down", "t9005_wide5.md")

    def test_extreme_top_is_silent_and_marks(self):
        self._assert_move_is_silent_and_marked("ctrl+up", "t9005_wide5.md")

    def test_extreme_bottom_is_silent_and_marks(self):
        self._assert_move_is_silent_and_marked("ctrl+down", "t9005_wide5.md")

    def test_moved_card_renders_the_dirty_marker(self):
        """Render-level: the marker reaches the SCREEN, not just `modified_files`.

        `TaskCard.compose` reads `is_modified` when the card is built, and a lateral
        move recomposes both columns — so this is what proves the targeted marking is
        equivalent to the scan it replaced from the user's point of view.
        """
        rendered = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                card = next(c for c in app.query(self.TaskCard)
                            if not c.is_child
                            and c.task_data.filename == "t9005_wide5.md")
                card.focus()
                await pilot.pause()
                await pilot.press("shift+right")
                await pilot.pause()
                await pilot.pause()

                for c in app.query(self.TaskCard):
                    if c.is_child:
                        continue
                    labels = c.query(".task-number")
                    if labels:
                        rendered[c.task_data.filename] = labels.first().render().plain

        self._run(go())
        self.assertIn("t9005_wide5.md", rendered, "the moved card must still be mounted")
        self.assertEqual(
            rendered["t9005_wide5.md"], "t9005 *",
            "the moved card must render the modified marker — without the targeted "
            "`_mark_written` update it would render bare until the next full scan")

        # Discriminating control: an untouched card must NOT be marked, so the
        # assertion above is not just observing a board where everything is dirty.
        untouched = {name: text for name, text in rendered.items()
                     if name != "t9005_wide5.md"}
        self.assertTrue(untouched, "need at least one untouched card as a control")
        self.assertFalse(
            [name for name, text in untouched.items() if text.endswith("*")],
            f"cards that were never written rendered as modified: {untouched}")

    def test_refresh_still_spawns_git_status(self):
        """Negative control: the spy DOES see spawns, so an empty set means something.

        `r` still runs the full scan — the removal above is scoped to movement.
        """
        _, spawns, _ = self._drive_move("r", "t9005_wide5.md")
        names = {Path(argv[0]).name for argv in spawns}
        self.assertIn("git", names,
                      f"refresh must still run the full git scan; saw {spawns}")


class TargetedMarkingTests(bf.FixtureBoardTestBase, _PristineTreeMixin,
                           unittest.TestCase):
    """`_mark_written` agrees with a real `git status` and with the filesystem.

    `refresh_git_status()` CLEARS and repopulates `modified_files` on the manager it
    is called on, so scanning the manager under test would overwrite the value being
    checked and compare the scan with itself. The observed set is therefore captured
    first, and the expectation comes from a separate manager plus a byte differ —
    three sources, none derived from another.
    """

    FIXTURE_TASKS = bf.wide_topology(15)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._snapshot_pristine()

    def _independent_scan(self) -> set:
        """A real `git status` from a manager that has never been mutated here."""
        scanner = self.ab.TaskManager()
        scanner.refresh_git_status()
        return set(scanner.modified_files)

    def _assert_marking_agrees(self, manager, before_snapshot, label):
        observed = set(manager.modified_files)          # capture BEFORE any scan
        scanned = self._independent_scan()
        changed = bf.diff_snapshots(before_snapshot, bf.snapshot(self.tree))["changed"]

        self.assertTrue(changed, f"{label}: nothing was written to disk")
        self.assertEqual(observed, scanned,
                         f"{label}: targeted marking {observed} disagrees with a real "
                         f"git status {scanned}")
        self.assertEqual(observed, set(changed),
                         f"{label}: targeted marking {observed} disagrees with the "
                         f"filesystem delta {set(changed)}")

    def test_fixture_facts(self):
        manager = self.ab.TaskManager()
        self.assertEqual(self._independent_scan(), set(),
                         "the fixture tree must start committed-clean, or every "
                         "marking comparison starts from pre-existing dirt")
        self.assertGreaterEqual(len(manager.get_column_tasks("c0")), 3)

    def test_move_to_column_marks_what_it_wrote(self):
        manager = self.ab.TaskManager()
        before = bf.snapshot(self.tree)
        manager.move_task_to_column("t9005_wide5.md", "c2")
        self._assert_marking_agrees(manager, before, "move_task_to_column")

    def test_move_to_edge_marks_what_it_wrote(self):
        manager = self.ab.TaskManager()
        before = bf.snapshot(self.tree)
        manager.move_task_to_edge("t9005_wide5.md", "c0", to_top=True)
        self._assert_marking_agrees(manager, before, "move_task_to_edge")

    def test_reposition_marks_what_it_wrote(self):
        manager = self.ab.TaskManager()
        tasks = manager.get_column_tasks("c0")
        before = bf.snapshot(self.tree)
        manager.reposition_task(tasks[2].filename, tasks[0], tasks[1])
        self._assert_marking_agrees(manager, before, "reposition_task")

    def test_compaction_marks_every_respaced_file(self):
        """The case a caller-side update keyed on `MoveResult.moved` would miss.

        A respace rewrites N files that `moved` never names; marking at the write
        site is what keeps the marker exact through a compaction.
        """
        manager = self.ab.TaskManager()
        tasks = manager.get_column_tasks("c0")
        # Exhaust the interval so `index_between` fails and `reposition_task`
        # respaces the whole column.
        for offset, task in enumerate(tasks):
            task.board_idx = 10 + offset
            task.reload_and_save_board_fields(("boardidx",))
        manager.modified_files.clear()

        before = bf.snapshot(self.tree)
        tasks = manager.get_column_tasks("c0")
        result = manager.reposition_task(tasks[2].filename, tasks[0], tasks[1])
        self.assertTrue(result.compacted,
                        "the seeded gap did not force a compaction — this case would "
                        "then be an ordinary reposition and prove nothing")
        self._assert_marking_agrees(manager, before, "reposition_task (compacted)")
        self.assertGreater(
            len(manager.modified_files), 1,
            "a compaction rewrites more than the moved file; marking only "
            "`MoveResult.moved` would under-report exactly here")


if __name__ == "__main__":
    unittest.main()
