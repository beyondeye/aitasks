"""The headless board-column seam: lib/board_columns.py (t1377_1).

Mirrors `tests/test_board_manager_moves.py` — fixture tree, no Textual Pilot,
byte-identical tree snapshots to prove a refusal wrote nothing. Note the fixture
vocabulary is `c0`…`c4`, not `now`/`next`/`backlog`.

Four groups of assertions, and it is worth saying why each exists:

* **arithmetic** — the append index must be computed the way the board computes
  it, including the mover's own exclusion and the empty-column base of `STEP`;
* **board parity** — a phantom stub or unparseable file carrying the destination
  column is invisible on the board, so it must not inflate the index either;
* **refusals** — the id reaches a `glob`, so `*`, `../x` and a duplicate match
  are each their own named refusal, and every one of them writes nothing;
* **boundaries** — `task_dir` containment and the vanished-file guard, both of
  which protect a *mutation* boundary and both of which carry the control that
  proves the check is live rather than vacuous.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(REPO_ROOT / "tests" / "lib"),
           str(REPO_ROOT / ".aitask-scripts" / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import board_fixture as bf  # noqa: E402
import board_columns as bc  # noqa: E402
import board_ordering as BO  # noqa: E402
from task_yaml import parse_frontmatter, serialize_frontmatter  # noqa: E402

STEP = BO.STEP

TOPOLOGY = (
    bf.FixtureTask(task_id="9000", col="c0", idx=10, slug="parent"),
    bf.FixtureTask(task_id="9001", col="c1", idx=10, slug="alpha"),
    bf.FixtureTask(task_id="9002", col="c1", idx=20, slug="beta"),
    bf.FixtureTask(task_id="9003", col="c2", idx=10, slug="gamma"),
    bf.FixtureTask(task_id="9000_1", col="c0", idx=20, slug="childone"),
    bf.FixtureTask(filename="t_unparseable.md", col="c0", idx=99),
)


class _SeamCase(unittest.TestCase):
    def setUp(self):
        self.root_dir = Path(tempfile.mkdtemp(prefix="ait-bc-seam-"))
        self.addCleanup(shutil.rmtree, self.root_dir, ignore_errors=True)
        self.tree = bf.build_fixture_tree(self.root_dir, self.topology())
        self.before = bf.snapshot(self.tree)

    def topology(self):
        return TOPOLOGY

    def assert_untouched(self):
        self.assertEqual(
            bf.diff_snapshots(self.before, bf.snapshot(self.tree)),
            {"changed": set(), "added": set(), "removed": set()},
            "a refused operation must leave the tree byte-identical")

    def idx_of(self, filename):
        path = self.tree / "aitasks" / filename
        return parse_frontmatter(path.read_text(encoding="utf-8"))[0]["boardidx"]

    def meta_of(self, filename):
        path = self.tree / "aitasks" / filename
        return parse_frontmatter(path.read_text(encoding="utf-8"))[0]


# --- Index arithmetic --------------------------------------------------------

class AppendArithmeticTests(_SeamCase):
    def test_move_lands_past_the_destination_maximum(self):
        out = bc.move_task_to_column(self.tree, "9000", "c1")
        self.assertTrue(out.ok, out.refused)
        self.assertEqual(out.board_idx, 20 + STEP)
        self.assertEqual(self.idx_of("t9000_parent.md"), 20 + STEP)
        self.assertEqual(self.meta_of("t9000_parent.md")["boardcol"], "c1")

    def test_sequential_moves_get_distinct_ascending_indices(self):
        seen = []
        for task_id in ("9000", "9001", "9003"):
            out = bc.move_task_to_column(self.tree, task_id, "c4")
            self.assertTrue(out.ok, out.refused)
            seen.append(out.board_idx)
        self.assertEqual(seen, sorted(set(seen)), f"not distinct/ascending: {seen}")

    def test_empty_destination_starts_at_step_not_zero(self):
        out = bc.move_task_to_column(self.tree, "9000", "c4")
        self.assertEqual(out.board_idx, STEP)

    def test_the_mover_is_excluded_from_its_own_append(self):
        """A card already holding the column max must still actually move.

        Counting the mover would yield `self + STEP`, which looks like movement
        but leaves the card exactly where it was relative to the column.
        """
        # t9002 holds c1's maximum (20); moving it within c1 must not see itself.
        out = bc.move_task_to_column(self.tree, "9002", "c1")
        self.assertTrue(out.ok, out.refused)
        self.assertEqual(out.board_idx, 10 + STEP,
                         "expected max-of-OTHERS (10) + STEP, not self (20) + STEP")


class UnorderedMembershipTests(_SeamCase):
    def topology(self):
        return TOPOLOGY + (
            # No `boardcol` at all — the board renders this in `unordered`.
            bf.FixtureTask(task_id="9010", col="", idx=44, slug="loose"),
        )

    def test_a_task_without_boardcol_counts_as_unordered(self):
        path = self.tree / "aitasks" / "t9010_loose.md"
        meta, body, order = parse_frontmatter(path.read_text(encoding="utf-8"))
        del meta["boardcol"]
        path.write_text(serialize_frontmatter(meta, body, order), encoding="utf-8")

        self.assertIn(44, bc.column_indices(self.tree, bc.UNORDERED_ID))
        self.assertEqual(bc.task_column(self.tree, "9010").col_id, bc.UNORDERED_ID)

    def test_unordered_is_a_legal_move_target(self):
        out = bc.move_task_to_column(self.tree, "9000", bc.UNORDERED_ID)
        self.assertTrue(out.ok, out.refused)
        self.assertEqual(self.meta_of("t9000_parent.md")["boardcol"],
                         bc.UNORDERED_ID)


# --- Board parity ------------------------------------------------------------

class BoardParityTests(_SeamCase):
    """Files the board does not render must not affect the arithmetic."""

    def _plant(self, name, text):
        (self.tree / "aitasks" / name).write_text(text, encoding="utf-8")

    def test_phantom_stub_does_not_inflate_the_append_index(self):
        # Only board keys => TaskManager._is_phantom_stub drops it, so the board
        # never draws it. A huge boardidx here must be invisible to us too.
        self._plant("t9500_phantom.md",
                    "---\nboardcol: c2\nboardidx: 99999\n---\n\nbody\n")
        out = bc.move_task_to_column(self.tree, "9000", "c2")
        self.assertEqual(out.board_idx, 10 + STEP,
                         "phantom stub must not be counted")

    def test_unparseable_file_does_not_inflate_the_append_index(self):
        """Note this is a *different* enforcement point from the phantom-stub
        filter: the frontmatter never parses, so `_parse_task` bails before
        eligibility is consulted. It therefore needs its own discriminating
        control (below) — disabling `_eligible` would not move this assertion.
        """
        self._plant("t9501_broken.md",
                    "---\n: : not: valid: yaml\nboardidx: 99999\n---\nbody\n")
        out = bc.move_task_to_column(self.tree, "9000", "c2")
        self.assertEqual(out.board_idx, 10 + STEP,
                         "unparseable file must not be counted")

    def test_the_same_card_made_parseable_IS_counted(self):
        """Discriminating control for the test above.

        Same column, same huge index — only validity differs. If the outcome is
        identical either way, the parse guard is not what produced it.
        """
        self._plant("t9502_valid.md",
                    "---\nissue_type: chore\nboardcol: c2\nboardidx: 99999\n"
                    "---\n\nbody\n")
        out = bc.move_task_to_column(self.tree, "9000", "c2")
        self.assertEqual(out.board_idx, 99999 + STEP,
                         "a parseable, non-stub card MUST be counted")

    def test_a_real_card_in_the_destination_IS_counted(self):
        """Positive control: the parity filter is not simply dropping everything."""
        out = bc.move_task_to_column(self.tree, "9000", "c2")
        self.assertEqual(out.board_idx, 10 + STEP)
        self.assertGreater(out.board_idx, 10)


# --- Refusals ----------------------------------------------------------------

class TaskIdRefusalTests(_SeamCase):
    MALFORMED = ("*", "1*", "../etc", "t42", "42.5", "", "9000 ", "0x10")

    def test_malformed_ids_are_refused_without_touching_the_tree(self):
        for bad in self.MALFORMED:
            with self.subTest(task_id=bad):
                out = bc.move_task_to_column(self.tree, bad, "c1")
                self.assertEqual(out.refused, ((bad, "malformed_task_id"),))
                self.assert_untouched()

    def test_a_glob_metacharacter_is_never_expanded(self):
        """Positive control for the regex gate.

        Without it, `--task '*'` would glob `t*_*.md` and hit a real task. The
        assertion above only proves a refusal; this proves the refusal is what
        stands between the input and a real file.
        """
        self.assertTrue(list((self.tree / "aitasks").glob("t*_*.md")),
                        "fixture must contain files a bare glob could match")
        out = bc.move_task_to_column(self.tree, "*", "c1")
        self.assertEqual(out.refused, (("*", "malformed_task_id"),))
        self.assert_untouched()

    def test_child_id_is_refused_as_not_a_parent_task(self):
        out = bc.move_task_to_column(self.tree, "9000_1", "c1")
        self.assertEqual(out.refused, (("9000_1", "not_a_parent_task"),))
        self.assert_untouched()

    def test_missing_task_is_refused_as_not_found(self):
        out = bc.move_task_to_column(self.tree, "99999", "c1")
        self.assertEqual(out.refused, (("99999", "not_found"),))
        self.assert_untouched()

    def test_unknown_column_is_refused_before_resolving_the_task(self):
        out = bc.move_task_to_column(self.tree, "9000", "no_such_column")
        self.assertEqual(out.refused, (("9000", "unknown_column"),))
        self.assert_untouched()

    def test_ambiguous_id_is_refused_and_writes_nothing(self):
        tasks = self.tree / "aitasks"
        src = (tasks / "t9000_parent.md").read_text(encoding="utf-8")
        for suffix in ("a", "b"):
            (tasks / f"t9100_{suffix}.md").write_text(src, encoding="utf-8")
        before = bf.snapshot(self.tree)

        out = bc.move_task_to_column(self.tree, "9100", "c1")
        self.assertEqual(out.refused, (("9100", "ambiguous_task_id"),))
        self.assertEqual(bf.diff_snapshots(before, bf.snapshot(self.tree)),
                         {"changed": set(), "added": set(), "removed": set()})

    def test_task_column_uses_the_same_rule_as_move(self):
        """One resolution rule: the two verbs cannot disagree about an id."""
        for bad, reason in (("*", "malformed_task_id"),
                            ("9000_1", "not_a_parent_task"),
                            ("99999", "not_found")):
            with self.subTest(task_id=bad):
                self.assertEqual(bc.task_column(self.tree, bad).refused,
                                 ((bad, reason),))


# --- Layout write discipline -------------------------------------------------

class LayoutWriteTests(_SeamCase):
    def topology(self):
        return TOPOLOGY + (
            bf.FixtureTask(task_id="9020", col="c0", idx=5, slug="stamped",
                           extra={"updated_at": "2020-01-01 00:00"}),
        )

    def test_move_does_not_stamp_updated_at(self):
        before = self.meta_of("t9020_stamped.md")["updated_at"]
        out = bc.move_task_to_column(self.tree, "9020", "c1")
        self.assertTrue(out.ok, out.refused)
        self.assertEqual(self.meta_of("t9020_stamped.md")["updated_at"], before,
                         "boardcol/boardidx are BOARD_LAYOUT_KEYS: a layout "
                         "write must not bump updated_at")

    def test_updated_at_assertion_discriminates(self):
        """Negative control for the assertion above.

        `BOARD_KEYS == BOARD_LAYOUT_KEYS` today, so there is no non-layout board
        key to write as a contrast. Instead prove the *check* is live: stamp the
        field by hand and confirm the same read reports the change. If this
        fails, the assertion above is vacuous.
        """
        before = self.meta_of("t9020_stamped.md")["updated_at"]
        path = self.tree / "aitasks" / "t9020_stamped.md"
        meta, body, order = parse_frontmatter(path.read_text(encoding="utf-8"))
        meta["updated_at"] = "2031-12-31 23:59"
        path.write_text(serialize_frontmatter(meta, body, order), encoding="utf-8")
        self.assertNotEqual(self.meta_of("t9020_stamped.md")["updated_at"], before)

    def test_only_board_fields_change(self):
        path = self.tree / "aitasks" / "t9020_stamped.md"
        before_meta, before_body, _ = parse_frontmatter(
            path.read_text(encoding="utf-8"))
        bc.move_task_to_column(self.tree, "9020", "c1")
        after_meta, after_body, _ = parse_frontmatter(
            path.read_text(encoding="utf-8"))

        self.assertEqual(before_body, after_body, "body must be untouched")
        self.assertEqual(set(before_meta), set(after_meta), "no key invented")
        changed = {k for k in before_meta if before_meta[k] != after_meta[k]}
        self.assertEqual(changed, {"boardcol", "boardidx"})


# --- task_dir containment ----------------------------------------------------

def _build_custom_layout(root: Path, task_dir_name: str) -> Path:
    """Minimal tree under an arbitrary task-directory name."""
    tree = root / "tree"
    meta = tree / task_dir_name / "metadata"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "board_config.json").write_text(
        json.dumps({"columns": bf.COLUMNS, "column_order": bf.COLUMN_ORDER},
                   indent=2) + "\n", encoding="utf-8")
    (tree / task_dir_name / "t7001_solo.md").write_text(
        bf.FixtureTask(task_id="7001", col="c0", idx=7, slug="solo").text(),
        encoding="utf-8")
    return tree


class TaskDirContainmentTests(unittest.TestCase):
    def setUp(self):
        self.root_dir = Path(tempfile.mkdtemp(prefix="ait-bc-td-"))
        self.addCleanup(shutil.rmtree, self.root_dir, ignore_errors=True)
        self.tree = bf.build_fixture_tree(self.root_dir, TOPOLOGY)

    def test_pathlib_really_discards_the_root_for_an_absolute_operand(self):
        """The motivation, asserted rather than asserted-about.

        This is why an absolute `task_dir` must be rejected outright: joining it
        does not produce a path *under* the root, it produces the absolute path
        itself, and every later containment intuition is wrong.
        """
        self.assertEqual(Path("/proj") / "/etc", Path("/etc"))

    def test_unsafe_values_are_refused(self):
        for bad in ("/etc", "/", "../sibling", "a/../../b", "", "   "):
            with self.subTest(task_dir=bad):
                with self.assertRaises(bc.UnsafeTaskDirError):
                    bc.tasks_dir(self.tree, bad)

    def test_unsafe_task_dir_surfaces_as_a_refusal_not_an_exception(self):
        out = bc.move_task_to_column(self.tree, "9000", "c1", task_dir="/etc")
        self.assertEqual(out.refused, (("9000", "unsafe_task_dir"),))
        query = bc.task_column(self.tree, "9000", task_dir="../x")
        self.assertEqual(query.refused, (("9000", "unsafe_task_dir"),))

    def test_branch_mode_symlink_layout_passes(self):
        """Production layout control — `aitasks` is a symlink to .aitask-data.

        A containment check that rejected this would be wrong, not strict: the
        symlink target still resolves beneath the root.
        """
        self.assertTrue((self.tree / "aitasks").is_symlink(),
                        "fixture should be in branch mode")
        self.assertTrue(bc.tasks_dir(self.tree, "aitasks").is_dir())
        self.assertTrue(bc.load_columns(self.tree)[0])

    def test_missing_layout_is_refused_not_degraded_to_defaults(self):
        empty = self.root_dir / "empty"
        empty.mkdir()
        with self.assertRaises(bc.UnsupportedLayoutError):
            bc.load_columns(empty)
        out = bc.move_task_to_column(empty, "9000", "c1")
        self.assertEqual(out.refused, (("9000", "unsupported_layout"),))

    def test_missing_layout_would_otherwise_report_stock_defaults(self):
        """Why the layout check exists: the underlying reader fails soft."""
        ghost = self.root_dir / "empty2" / "aitasks" / "metadata"
        ids, _ = bc.load_columns_at(ghost / "board_config.json")
        self.assertEqual(ids, bc.DEFAULT_ORDER,
                         "a missing config silently yields the stock board")

    def test_custom_task_dir_is_read_and_written(self):
        root = Path(tempfile.mkdtemp(prefix="ait-bc-custom-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        tree = _build_custom_layout(root, "mytasks")

        self.assertEqual(bc.load_columns(tree, task_dir="mytasks")[0],
                         bf.COLUMN_ORDER)
        out = bc.move_task_to_column(tree, "7001", "c2", task_dir="mytasks")
        self.assertTrue(out.ok, out.refused)
        moved = (tree / "mytasks" / "t7001_solo.md").read_text(encoding="utf-8")
        self.assertIn("boardcol: c2", moved)
        # And the default layout is genuinely absent, so this was not a fluke.
        self.assertFalse((tree / "aitasks").exists())


class RootScopingTests(unittest.TestCase):
    def test_a_move_writes_only_inside_its_own_root(self):
        root_a = Path(tempfile.mkdtemp(prefix="ait-bc-a-"))
        root_b = Path(tempfile.mkdtemp(prefix="ait-bc-b-"))
        self.addCleanup(shutil.rmtree, root_a, ignore_errors=True)
        self.addCleanup(shutil.rmtree, root_b, ignore_errors=True)
        tree_a = bf.build_fixture_tree(root_a, TOPOLOGY)
        tree_b = bf.build_fixture_tree(root_b, TOPOLOGY)
        before_b = bf.snapshot(tree_b)

        self.assertTrue(bc.move_task_to_column(tree_a, "9000", "c1").ok)
        self.assertEqual(bf.diff_snapshots(before_b, bf.snapshot(tree_b)),
                         {"changed": set(), "added": set(), "removed": set()},
                         "the other project must be untouched")


# --- The vanished-file guard -------------------------------------------------

class VanishedFileTests(_SeamCase):
    """The guard, and the honest statement of what it does not cover."""

    def _target(self):
        return self.tree / "aitasks" / "t9000_parent.md"

    def test_guard_refuses_when_the_file_disappears_before_the_rename(self):
        """Delete strictly between the parse-time stat and `_assert_same_file`.

        `_atomic_prepare` runs in exactly that window, so wrapping it is what
        actually exercises the guard. (Wrapping `_atomic_commit` would place the
        deletion *after* the check — see the next test.)
        """
        target = self._target()
        real_prepare = bc._atomic_prepare

        def prepare_then_delete(path, render):
            tmp = real_prepare(path, render)
            target.unlink()
            return tmp

        with mock.patch.object(bc, "_atomic_prepare", prepare_then_delete):
            out = bc.move_task_to_column(self.tree, "9000", "c1")

        self.assertEqual(out.refused, (("9000", "vanished"),))
        self.assertFalse(target.exists(), "a deleted task must NOT be recreated")
        leftovers = [p.name for p in (self.tree / "aitasks").glob(".*.tmp")]
        self.assertEqual(leftovers, [], "the staged temp must be discarded")

    def test_documented_residual_race_still_recreates(self):
        """Characterization of the limit the docstring claims — and the negative
        control for the test above.

        Deleting *after* `_assert_same_file` leaves an unconditional
        `os.replace`, which recreates the file. Pinning this proves the guard
        test above is not vacuous: patching the wrong seam gives the opposite
        outcome, so a guard that never ran could not produce that result.
        """
        target = self._target()
        real_commit = bc._atomic_commit

        def delete_then_commit(tmp, path):
            target.unlink()
            return real_commit(tmp, path)

        with mock.patch.object(bc, "_atomic_commit", delete_then_commit):
            out = bc.move_task_to_column(self.tree, "9000", "c1")

        self.assertTrue(out.ok, out.refused)
        self.assertTrue(target.exists(),
                        "known limit: a deletion inside the rename window is "
                        "not detectable by a pre-commit check")


# --- Colour handling ---------------------------------------------------------

class ColourTests(_SeamCase):
    def _set_colour(self, colour):
        path = self.tree / "aitasks" / "metadata" / "board_config.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        config["columns"][0]["color"] = colour
        path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    def test_colour_is_exposed_on_the_record(self):
        rec = bc.column_records(self.tree)[0]
        self.assertEqual(rec.id, "c0")
        self.assertEqual(rec.color, bf.COLUMNS[0]["color"])

    def test_record_breaking_colour_is_stripped_at_the_emit_site(self):
        """Sanitize where the delimited encoding is produced.

        On read it is undecidable: once a stray `|` is in the stream nothing can
        tell it from a separator. Colour is cosmetic, so it degrades rather than
        failing the run — a bad *id* stays fatal.
        """
        self._set_colour("#FF|00\r00")
        rendered = bc.sanitize_middle_field(bc.column_records(self.tree)[0].color)
        self.assertNotIn("|", rendered)
        self.assertNotIn("\r", rendered)

    def test_a_title_keeps_its_pipe_because_it_is_the_last_field(self):
        """The asymmetry is the whole reason title is emitted last.

        Stripping `|` from the title too would silently corrupt a legitimate
        title and make the field ordering pointless.

        Reached through `bc.` rather than by importing `record_protocol`
        directly: that also proves `board_columns` really does import the shared
        helpers rather than keeping a private copy.

        **CRLF flip (t1433).** This assertion used to expect `"a  b"` — two
        spaces. `board_columns._line_safe` replaced CR and LF independently,
        while the gatherers' `_free_text` replaced `"\\r\\n"` first and produced
        one space. Both were safe; neither was canonical. t1433 unified the
        shared last-field sanitizer on the collapsing policy (a CRLF is one line
        break, so it becomes one space), which makes this the **single intended
        behaviour change** of that task. Everything else about the protocol —
        including `|` survival below — is byte-identical.
        """
        self.assertEqual(bc.sanitize_last_field("Col|One"), "Col|One")
        self.assertEqual(bc.sanitize_middle_field("Col|One"), "ColOne")
        self.assertEqual(bc.sanitize_last_field("a\r\nb"), "a b",
                         "CR/LF still go — they would break the line protocol")

    def test_a_non_string_colour_degrades_to_none(self):
        self._set_colour(12345)
        self.assertIsNone(bc.column_records(self.tree)[0].color)


# --- Reader contract ---------------------------------------------------------

class ReaderContractTests(_SeamCase):
    def test_titles_include_unordered_but_ids_do_not(self):
        ids, titles = bc.load_columns(self.tree)
        self.assertNotIn(bc.UNORDERED_ID, ids)
        self.assertEqual(titles[bc.UNORDERED_ID], bc.UNORDERED_TITLE)

    def test_column_order_entry_without_definition_is_dropped(self):
        path = self.tree / "aitasks" / "metadata" / "board_config.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        config["column_order"] = config["column_order"] + ["ghost"]
        path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        self.assertNotIn("ghost", bc.load_columns(self.tree)[0])

    def test_deliberately_empty_board_stays_empty(self):
        path = self.tree / "aitasks" / "metadata" / "board_config.json"
        path.write_text(json.dumps({"columns": [], "column_order": []}) + "\n",
                        encoding="utf-8")
        self.assertEqual(bc.load_columns(self.tree)[0], [],
                         "`.get(k, default)` not `or default` — an empty board "
                         "must not be replaced by the stock one")

    def test_record_breaking_column_id_raises(self):
        path = self.tree / "aitasks" / "metadata" / "board_config.json"
        path.write_text(json.dumps(
            {"columns": [{"id": "ba|d", "title": "Bad"}],
             "column_order": ["ba|d"]}) + "\n", encoding="utf-8")
        with self.assertRaises(bc.ColumnIdError):
            bc.load_columns(self.tree)

    def test_reader_never_creates_the_config_file(self):
        path = self.tree / "aitasks" / "metadata" / "board_config.json"
        path.unlink()
        bc.load_columns(self.tree)
        self.assertFalse(path.exists(),
                         "unlike TaskManager.load_metadata, this reader must "
                         "not write the config it failed to find")

    def test_include_unordered_prepends_the_synthetic_row(self):
        records = bc.column_records(self.tree, include_unordered=True)
        self.assertEqual(records[0].id, bc.UNORDERED_ID)
        self.assertEqual(records[0].title, bc.UNORDERED_TITLE)


# --- De-dup and headless guards ----------------------------------------------

BOARD_SRC = REPO_ROOT / ".aitask-scripts" / "board" / "aitask_board.py"
GATHER_SRC = REPO_ROOT / ".aitask-scripts" / "lib" / "work_report_gather.py"
SEAM_SRC = REPO_ROOT / ".aitask-scripts" / "lib" / "board_columns.py"
SETTINGS_SRC = REPO_ROOT / ".aitask-scripts" / "settings" / "settings_app.py"
STATS_CONFIG_SRC = REPO_ROOT / ".aitask-scripts" / "stats" / "stats_config.py"


class SeamGuardTests(unittest.TestCase):
    """Keep the behaviour tests green AND assert the definitions moved.

    Mirrors `test_board_manager_moves.SeamGuardTests`, the precedent from the
    `board_ordering` extraction.
    """

    def test_the_seam_is_headless(self):
        src = SEAM_SRC.read_text(encoding="utf-8")
        for forbidden in ("import textual", "from textual", "import aitask_board"):
            self.assertNotIn(forbidden, src,
                             f"{forbidden} would defeat the whole point")

    def test_board_imports_the_vocabulary_instead_of_defining_it(self):
        src = BOARD_SRC.read_text(encoding="utf-8")
        self.assertIn("from board_columns import", src)
        self.assertNotIn("DEFAULT_COLUMNS = [", src,
                         "DEFAULT_COLUMNS must live in lib/board_columns.py")
        self.assertNotIn("DEFAULT_ORDER = [", src,
                         "DEFAULT_ORDER must live in lib/board_columns.py")
        self.assertNotIn('metadata.get("boardcol", "unordered")', src,
                         "the bare literal must be the shared UNORDERED_ID")

    def test_gatherer_imports_the_vocabulary_instead_of_defining_it(self):
        src = GATHER_SRC.read_text(encoding="utf-8")
        self.assertIn("from board_columns import", src)
        self.assertNotIn("DEFAULT_COLUMNS = [", src)
        self.assertNotIn('UNORDERED_ID = "unordered"', src)

    def test_no_stale_sync_comment_survives(self):
        """The comment declaring the manual-sync obligation must be gone."""
        self.assertNotIn("kept in sync with aitask_board.py",
                         GATHER_SRC.read_text(encoding="utf-8"))

    def test_board_imports_the_palette_and_slug_instead_of_defining_them(self):
        """t1377_3: the board delegates rather than carrying a second copy."""
        src = BOARD_SRC.read_text(encoding="utf-8")
        self.assertNotIn("PALETTE_COLORS = [", src,
                         "PALETTE_COLORS must live in lib/board_columns.py")
        self.assertNotIn("slug = slug.strip('_')", src,
                         "the slug body must live in lib/board_columns.py")
        self.assertIn("return generate_col_id(name, existing_ids)", src,
                      "_generate_col_id must delegate to the shared one")

    def test_board_and_settings_import_the_layer_key_sets(self):
        """t1377_3: `_PROJECT_KEYS` / `_USER_KEYS` had two byte-identical copies."""
        board = BOARD_SRC.read_text(encoding="utf-8")
        settings = SETTINGS_SRC.read_text(encoding="utf-8")
        self.assertNotIn('_PROJECT_KEYS = {"columns"', board)
        self.assertNotIn('_USER_KEYS = {"settings"}', board)
        self.assertNotIn('_BOARD_PROJECT_KEYS = {"columns"', settings)
        self.assertNotIn('_BOARD_USER_KEYS = {"settings"}', settings)
        self.assertIn("from board_columns import PROJECT_KEYS", board)
        self.assertIn("from board_columns import PROJECT_KEYS", settings)

    def test_stats_config_user_keys_is_a_name_collision_not_a_duplicate(self):
        """The negative control for the de-dup's *scope*.

        `stats/stats_config.py` also defines `_USER_KEYS`, and a sweep that
        matched on the name alone would "unify" it. It is a different key set for
        a different config file — this pins that it is left alone, and that the
        two are not interchangeable.
        """
        # `stats_config` does `from lib.config_utils import …`, so it needs the
        # scripts ROOT on the path, not the stats directory.
        scripts_root = str(REPO_ROOT / ".aitask-scripts")
        if scripts_root not in sys.path:
            sys.path.insert(0, scripts_root)
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "stats_config_probe", STATS_CONFIG_SRC)
        stats_config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stats_config)

        self.assertEqual(stats_config._USER_KEYS,
                         ("active", "days", "week_start", "custom"))
        self.assertNotEqual(set(stats_config._USER_KEYS), bc.USER_KEYS)
        self.assertNotIn("from board_columns import",
                         STATS_CONFIG_SRC.read_text(encoding="utf-8"))


class DedupDriftTests(_SeamCase):
    """The de-dup is real, not two implementations that agree today.

    The ambient reader is redirected with an **absolute** `TASK_DIR` rather than
    a `chdir`: `config_utils.task_dir()` returns the env value verbatim, so an
    absolute one points `metadata_dir()` straight at the fixture. That keeps the
    process cwd untouched, which matters under `-n` parallelism where a chdir is
    process-global (and is what `test_board_fixture_harness.LiveTreeSweepTests`
    forbids for exactly that reason).
    """

    def _ambient_load_columns(self):
        import work_report_gather as wrg

        with mock.patch.dict(os.environ,
                             {"TASK_DIR": str(self.tree / "aitasks")}):
            return wrg.load_columns()

    def test_gatherer_and_seam_agree_on_the_same_tree(self):
        self.assertEqual(self._ambient_load_columns(), bc.load_columns(self.tree))

    def test_they_agree_after_the_config_is_edited(self):
        """Agreement must survive a change, not just the shipped fixture."""
        path = self.tree / "aitasks" / "metadata" / "board_config.json"
        path.write_text(json.dumps(
            {"columns": [{"id": "solo", "title": "Solo|Bar"}],
             "column_order": ["solo", "ghost"]}) + "\n", encoding="utf-8")

        ambient = self._ambient_load_columns()
        self.assertEqual(ambient, bc.load_columns(self.tree))
        self.assertEqual(ambient[0], ["solo"],
                         "the undefined 'ghost' entry must be dropped by both")


# --- Column creation (t1377_3) ----------------------------------------------


class SlugTests(unittest.TestCase):
    """First tests for the slug generator — it had none before t1377_3."""

    def test_non_ascii_is_stripped_and_the_rest_slugged(self):
        self.assertEqual(bc.generate_col_id("My Spikes 🚀", []), "my_spikes")
        self.assertEqual(bc.generate_col_id("  Now ⚡  ", []), "now")

    def test_empty_and_all_stripped_titles_fall_back(self):
        for title in ("", "   ", "🙂", "!!!"):
            self.assertEqual(bc.generate_col_id(title, []), "column")

    def test_collisions_are_uniquified_in_order(self):
        existing = []
        for expected in ("dup", "dup_2", "dup_3"):
            got = bc.generate_col_id("Dup", existing)
            self.assertEqual(got, expected)
            existing.append(got)

    def test_length_is_capped_at_twenty_before_the_suffix(self):
        """Preserved verbatim from the board, quirk included: the uniquifying
        suffix is appended AFTER truncation, so a collided id may exceed 20."""
        long_title = "a" * 40
        self.assertEqual(bc.generate_col_id(long_title, []), "a" * 20)
        self.assertEqual(bc.generate_col_id(long_title, ["a" * 20]),
                         "a" * 20 + "_2")

    def test_output_can_never_break_a_delimited_record(self):
        """The load-bearing property, asserted with the REAL predicate.

        `record_protocol.has_record_breaking` is what the report protocol
        actually enforces; a hand-rolled regex here could drift from it.
        """
        from record_protocol import has_record_breaking

        for title in ("a|b", "a\rb", "a\nb", "pipe | cr \r lf \n 🚀",
                      "|||", "\r\n"):
            for existing in ([], ["a_b"], ["column"]):
                self.assertFalse(has_record_breaking(
                    bc.generate_col_id(title, existing)))


class PaletteTests(unittest.TestCase):
    def test_first_unused_palette_entry_is_chosen(self):
        self.assertEqual(bc.next_palette_color([]), "#FF5555")
        self.assertEqual(bc.next_palette_color(["#FF5555"]), "#FFB86C")
        self.assertEqual(bc.next_palette_color(["#FF5555", "#FFB86C"]),
                         "#F1FA8C")

    def test_non_palette_colours_do_not_suppress_a_palette_entry(self):
        self.assertEqual(bc.next_palette_color(["gray", "#123456", None]),
                         "#FF5555")

    def test_all_used_falls_back_by_count(self):
        used = [hexv for hexv, _label in bc.PALETTE_COLORS]
        self.assertEqual(bc.next_palette_color(used),
                         bc.PALETTE_COLORS[len(used) % 8][0])


class ColorPolicyTests(_SeamCase):
    """Writers refuse, readers degrade — both stances pinned here."""

    REFUSED = ("not a color", "#GG0000", "#FF55", "red] [/", "Red",
               "a|b", "a\rb", "a\nb", "[bold]", "#", "rgb(1,2,3)")
    ACCEPTED = ("#FF5555", "#abc", "#ABC", "gray", "bright_blue", "red")

    def test_malformed_colours_are_refused_and_write_nothing(self):
        for color in self.REFUSED:
            with self.subTest(color=color):
                out = bc.create_column(self.tree, "Title", color)
                self.assertFalse(out.ok, f"{color!r} should be refused")
                self.assertEqual(out.refused, (("Title", "invalid_color"),))
                self.assert_untouched()

    def test_accepted_colours_include_the_seams_own_stock_value(self):
        """`gray` is `UNORDERED_COLOR` and rich CANNOT parse it.

        This row is what fails if the validator is ever "improved" into
        `rich.Color.parse` — it would start refusing a value this module ships.
        """
        self.assertIn("gray", self.ACCEPTED)
        for color in self.ACCEPTED:
            with self.subTest(color=color):
                out = bc.create_column(self.tree, f"T {color}", color)
                self.assertTrue(out.ok, out.refused)
                self.assertEqual(out.color, color)

    def test_colour_is_stored_verbatim_case_preserved(self):
        out = bc.create_column(self.tree, "Cased", "#AbCdEf")
        self.assertEqual(self._entry(out.col_id)["color"], "#AbCdEf")

    def test_omitted_colour_auto_assigns_from_the_palette(self):
        out = bc.create_column(self.tree, "Auto")
        self.assertIn(out.color, [h for h, _l in bc.PALETTE_COLORS])

    def test_empty_colour_means_explicitly_colourless(self):
        """`None` (omitted) and `""` (explicit) are different requests."""
        out = bc.create_column(self.tree, "Plain", "")
        self.assertTrue(out.ok, out.refused)
        self.assertIsNone(out.color)
        self.assertNotIn("color", self._entry(out.col_id))

    def test_reader_still_degrades_a_hand_written_bad_colour(self):
        """The asymmetry, in one test so neither stance can absorb the other."""
        path = self.tree / "aitasks" / "metadata" / "board_config.json"
        path.write_text(json.dumps(
            {"columns": [{"id": "c9", "title": "Nine", "color": "not a color"}],
             "column_order": ["c9"]}) + "\n", encoding="utf-8")

        records = bc.column_records(self.tree)
        self.assertEqual(records[0].color, "not a color")   # reader tolerates
        self.assertFalse(bc.create_column(self.tree, "X", "not a color").ok)

    def test_negative_control_bypassing_the_guard_lets_a_pipe_be_mangled(self):
        """Why refusal, not storage: the corruption is undecidable on read.

        With the validator bypassed a `|` colour reaches disk, and `list-columns`
        then silently strips it — the reader cannot tell that from a colour that
        never had one.
        """
        with mock.patch.object(bc, "_validate_color", lambda c: c):
            out = bc.create_column(self.tree, "Sneak", "re|d")
        self.assertTrue(out.ok, out.refused)
        self.assertEqual(self._entry(out.col_id)["color"], "re|d")

        emitted = [line for line in self._cli_list_columns()
                   if line.startswith(f"COLUMN:{out.col_id}|")]
        self.assertEqual(len(emitted), 1)
        _cid, color, _title = emitted[0][len("COLUMN:"):].split("|", 2)
        self.assertEqual(color, "red")      # the `|` vanished, silently

    def _entry(self, col_id):
        path = self.tree / "aitasks" / "metadata" / "board_config.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        return next(c for c in raw["columns"] if c["id"] == col_id)

    def _cli_list_columns(self):
        out = []
        path = self.tree / "aitasks" / "metadata" / "board_config.json"
        for rec in bc.column_records_at(path):
            from record_protocol import sanitize_last_field, sanitize_middle_field
            out.append(f"COLUMN:{rec.id}|{sanitize_middle_field(rec.color or '')}"
                       f"|{sanitize_last_field(rec.title)}")
        return out


class CreateRefusalTests(_SeamCase):
    def test_blank_titles_are_refused(self):
        for title in ("", "   ", "\t", None):
            with self.subTest(title=title):
                out = bc.create_column(self.tree, title)
                self.assertFalse(out.ok)
                self.assertEqual(out.refused[0][1], "empty_title")
                self.assert_untouched()

    def test_unsafe_task_dir_is_refused(self):
        for task_dir in ("/etc", "../sibling", "a/../../b", ""):
            with self.subTest(task_dir=task_dir):
                out = bc.create_column(self.tree, "T", task_dir=task_dir)
                self.assertFalse(out.ok)
                self.assertEqual(out.refused[0][1], "unsafe_task_dir")
                self.assert_untouched()

    def test_missing_layout_is_refused(self):
        empty = self.root_dir / "empty"
        empty.mkdir()
        out = bc.create_column(empty, "T")
        self.assertFalse(out.ok)
        self.assertEqual(out.refused[0][1], "unsupported_layout")


class CreateSemanticsTests(_SeamCase):
    def test_new_column_lands_last_in_both_lists(self):
        before_ids, _titles = bc.load_columns(self.tree)
        out = bc.create_column(self.tree, "Spikes")
        self.assertTrue(out.ok, out.refused)
        after_ids, titles = bc.load_columns(self.tree)
        self.assertEqual(after_ids, before_ids + [out.col_id])
        self.assertEqual(titles[out.col_id], "Spikes")

    def test_existing_columns_keep_their_order_and_colours(self):
        before = bc.column_records(self.tree)
        bc.create_column(self.tree, "Spikes")
        after = bc.column_records(self.tree)
        self.assertEqual([(r.id, r.title, r.color) for r in after[:len(before)]],
                         [(r.id, r.title, r.color) for r in before])

    def test_title_keeps_its_pipe(self):
        out = bc.create_column(self.tree, "a|b")
        _ids, titles = bc.load_columns(self.tree)
        self.assertEqual(titles[out.col_id], "a|b")

    def test_missing_config_file_yields_the_stock_board_plus_the_new_column(self):
        """Board parity with `load_metadata`, pinned because it is surprising."""
        (self.tree / "aitasks" / "metadata" / "board_config.json").unlink()
        (self.tree / "aitasks" / "metadata" / "board_config.local.json").unlink()
        out = bc.create_column(self.tree, "Spikes")
        ids, _titles = bc.load_columns(self.tree)
        self.assertEqual(ids, bc.DEFAULT_ORDER + [out.col_id])


class LayeredWriteTests(_SeamCase):
    """The project/local split — three failure modes, all invisible to a
    happy-path creation test."""

    def setUp(self):
        super().setUp()
        self.config = self.tree / "aitasks" / "metadata" / "board_config.json"
        self.local = self.tree / "aitasks" / "metadata" / "board_config.local.json"
        raw = json.loads(self.config.read_text(encoding="utf-8"))
        raw["unrelated_project_key"] = {"keep": "me"}
        self.config.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
        local = json.loads(self.local.read_text(encoding="utf-8"))
        local["settings"]["collapsed_columns"] = ["c1"]
        local["settings"]["auto_refresh_minutes"] = 7
        # A top-level user key that is in NEITHER key set. `split_config` routes
        # an unclassified key to the PROJECT dict, so this is what discriminates
        # "wrote the project layer" from "wrote the merged dict": the former
        # leaves it here, the latter both drops it here and leaks it there.
        # It is also what makes the mirror control observable at all — a
        # `settings`-only round trip re-serializes byte-identically, so a bytes
        # comparison alone could not tell a rewrite from a no-op.
        local["local_only_marker"] = {"user": "private"}
        self.local.write_text(json.dumps(local, indent=2) + "\n", encoding="utf-8")
        self.local_before = self.local.read_bytes()

    def project(self):
        return json.loads(self.config.read_text(encoding="utf-8"))

    def test_round_trip_keeps_each_layer_where_it_belongs(self):
        out = bc.create_column(self.tree, "Spikes")
        self.assertTrue(out.ok, out.refused)
        project = self.project()

        # (a) the new column is in the project layer
        self.assertIn(out.col_id, [c["id"] for c in project["columns"]])
        # (b) an unrelated project key survives verbatim
        self.assertEqual(project["unrelated_project_key"], {"keep": "me"})
        # (c) NO user-layer key leaked into the tracked file — not `settings`,
        #     and not an unclassified one either
        self.assertNotIn("settings", project)
        self.assertNotIn("local_only_marker", project)
        # (d) the local file is byte-identical
        self.assertEqual(self.local.read_bytes(), self.local_before)

    def test_negative_control_merged_write_leaks_settings(self):
        """Mutation 1: skip `split_config` and write the merged dict.

        Names the exact corruption — `settings` in the tracked file — rather
        than asserting that "something" differs.
        """
        real_save = bc.save_project_config

        def leaky(path, _data):
            merged = bc.load_layered_config(
                str(path), defaults={"columns": bc.DEFAULT_COLUMNS,
                                     "column_order": bc.DEFAULT_ORDER})
            real_save(path, merged)

        with mock.patch.object(bc, "save_project_config", leaky):
            bc.create_column(self.tree, "Spikes")

        project = self.project()
        self.assertIn("settings", project)
        self.assertIn("collapsed_columns", project["settings"])
        # An unclassified local key rides along too — the leak is not limited to
        # `settings`, which is why the real writer never touches the merged dict.
        self.assertIn("local_only_marker", project)
        # …and the local file is still untouched, which is what makes this a
        # one-mutation control rather than two overlapping ones.
        self.assertEqual(self.local.read_bytes(), self.local_before)

    def test_negative_control_save_metadata_mirror_rewrites_the_local_file(self):
        """Mutation 2: also write the user layer, as `save_metadata` does.

        A distinct failure from the leak above — this one leaves the project
        file correct and damages the user's own file instead, which is why one
        control cannot stand in for both.

        Note what makes it *observable*: a `settings`-only round trip
        re-serializes to identical bytes, so comparing bytes would have shown no
        difference and the control would have "passed" while proving nothing.
        The unclassified `local_only_marker` is the discriminator — a mirroring
        write drops it, because `split_config` does not route it to the user
        layer.
        """
        from config_utils import local_path_for, save_local_config

        real_save = bc.save_project_config

        def mirroring(path, data):
            real_save(path, data)
            merged = bc.load_layered_config(str(path))
            _p, user = bc.split_config(merged, project_keys=bc.PROJECT_KEYS,
                                       user_keys=bc.USER_KEYS)
            save_local_config(str(local_path_for(str(path))), user)

        with mock.patch.object(bc, "save_project_config", mirroring):
            bc.create_column(self.tree, "Spikes")

        self.assertNotEqual(self.local.read_bytes(), self.local_before)
        local_now = json.loads(self.local.read_text(encoding="utf-8"))
        self.assertNotIn("local_only_marker", local_now,
                         "the mirror silently drops an unclassified user key")
        self.assertNotIn("settings", self.project())   # project stayed clean

    def test_the_controls_start_from_a_clean_baseline(self):
        """Assert the pre-state too, so a control that 'fails' because the
        fixture was already dirty is distinguishable from a live guard."""
        self.assertNotIn("settings", self.project())
        self.assertEqual(self.local.read_bytes(), self.local_before)


if __name__ == "__main__":
    unittest.main()
