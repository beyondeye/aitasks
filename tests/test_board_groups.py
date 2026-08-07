"""Unit tests for lib/board_groups.py — the INV-R grouping derivation (t1243_8).

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_board_groups.py -v

The module is pure and duck-typed over ``.filename`` / ``.metadata``, so these
tests boot no Textual app and mount no widget.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".aitask-scripts", "lib"))
from board_groups import (  # noqa: E402
    build_column_units,
    column_sort_key,
    group_display_title,
    group_members,
    normalize_group_slug,
    task_group_slug,
)


class FakeTask:
    """Minimal stand-in: board_groups only ever reads these two attributes."""

    def __init__(self, filename, boardidx=None, boardgroup=None, **extra):
        self.filename = filename
        self.metadata = dict(extra)
        if boardidx is not None:
            self.metadata["boardidx"] = boardidx
        if boardgroup is not None:
            self.metadata["boardgroup"] = boardgroup

    def __repr__(self):
        return f"<{self.filename}>"


def slugs(units):
    return [slug for slug, _ in units]


def names(units):
    return [[t.filename for t in members] for _, members in units]


class NormalizeGroupSlugTests(unittest.TestCase):
    """The malformed-value boundary that keeps the derivation TOTAL.

    `boardgroup` is persisted YAML: a user can hand-edit it and it arrives from
    other checkouts, so the real loader can legally hand us None, a list, a
    dict, an int or a bool. `lib/task_yaml.py` deliberately leaves malformed
    input type-honest for the consumer, so this is where it stops.
    """

    def test_valid_slug_passes_through(self):
        self.assertEqual(normalize_group_slug("perf_work"), "perf_work")

    def test_whitespace_is_content_not_noise(self):
        """Stripping would silently coalesce distinct groups.

        A QUOTED `boardgroup: "perf_work "` survives the YAML loader with its
        space intact (only unquoted plain scalars are stripped by YAML itself).
        If this function stripped, that task would silently join `perf_work` —
        and the merge driver would read it as unchanged from an unspaced base
        and discard the edit. Both are the silent coalescing the design forbids.
        """
        self.assertEqual(normalize_group_slug("perf_work "), "perf_work ")
        self.assertEqual(normalize_group_slug(" perf_work"), " perf_work")
        self.assertNotEqual(normalize_group_slug("perf_work "),
                            normalize_group_slug("perf_work"))

    def test_none_is_ungrouped(self):
        self.assertEqual(normalize_group_slug(None), "")

    def test_empty_string_tombstone_is_ungrouped(self):
        self.assertEqual(normalize_group_slug(""), "")

    def test_whitespace_only_is_ungrouped(self):
        self.assertEqual(normalize_group_slug("   "), "")

    def test_empty_list_is_ungrouped_not_a_crash(self):
        """`boardgroup: []` is the specific regression case.

        It is non-empty AND unhashable, so using the raw value as a bucket key
        raises TypeError and takes the whole board down.
        """
        self.assertEqual(normalize_group_slug([]), "")

    def test_non_empty_list_is_ungrouped(self):
        self.assertEqual(normalize_group_slug(["a", "b"]), "")

    def test_dict_is_ungrouped(self):
        self.assertEqual(normalize_group_slug({"a": 1}), "")

    def test_int_is_ungrouped_not_coerced(self):
        """Coercing with str() would let 42 and "42" silently collide."""
        self.assertEqual(normalize_group_slug(42), "")

    def test_bool_is_ungrouped(self):
        self.assertEqual(normalize_group_slug(True), "")

    def test_whitespace_bearing_slug_forms_its_own_group(self):
        """The visible consequence: two units, not one silently merged unit."""
        tasks = [
            FakeTask("t1_a.md", boardidx=10, boardgroup="perf_work"),
            FakeTask("t2_b.md", boardidx=20, boardgroup="perf_work "),
            FakeTask("t3_c.md", boardidx=30, boardgroup="perf_work"),
        ]
        units = build_column_units(tasks)
        self.assertEqual(slugs(units), ["perf_work", "perf_work "])
        self.assertEqual(names(units), [["t1_a.md", "t3_c.md"], ["t2_b.md"]])

    def test_non_cli_shaped_string_is_kept(self):
        """A hand-edited value keeps working rather than being silently dropped.

        The CLI rejects this shape at the write site; this function's job is
        totality, not shape enforcement.
        """
        self.assertEqual(normalize_group_slug("Perf Work"), "Perf Work")


class MalformedValueDerivationTests(unittest.TestCase):
    """Every malformed value must yield a deterministic layout AND no exception."""

    MALFORMED = [[], {}, 42, True, None, "", "   "]

    def test_malformed_values_never_raise_and_render_ungrouped(self):
        for bad in self.MALFORMED:
            with self.subTest(value=repr(bad)):
                tasks = [
                    FakeTask("t1_a.md", boardidx=10, boardgroup=bad),
                    FakeTask("t2_b.md", boardidx=20, boardgroup="perf_work"),
                    FakeTask("t3_c.md", boardidx=30, boardgroup="perf_work"),
                ]
                units = build_column_units(tasks)
                # The malformed one is its own singleton; the real group holds 2.
                self.assertEqual(slugs(units), ["", "perf_work"])
                self.assertEqual(names(units), [["t1_a.md"], ["t2_b.md", "t3_c.md"]])

    def test_malformed_value_is_deterministic_across_calls(self):
        tasks = [FakeTask("t1_a.md", boardidx=10, boardgroup=[])]
        self.assertEqual(build_column_units(tasks), build_column_units(tasks))


class ColumnSortKeyTests(unittest.TestCase):

    def test_quoted_index_sorts_numerically(self):
        # normalize_board_idx's whole reason for existing: "10" must not sort
        # before "2" lexically, and a quoted/int mix must not raise.
        self.assertEqual(column_sort_key(FakeTask("a.md", boardidx="10"))[0], 10)

    def test_missing_index_is_zero(self):
        self.assertEqual(column_sort_key(FakeTask("a.md"))[0], 0)

    def test_non_numeric_index_is_zero(self):
        self.assertEqual(column_sort_key(FakeTask("a.md", boardidx="junk"))[0], 0)

    def test_filename_breaks_ties(self):
        self.assertEqual(column_sort_key(FakeTask("b.md", boardidx=5)),
                         (5, "b.md"))


class BuildColumnUnitsTests(unittest.TestCase):

    def test_empty_column(self):
        self.assertEqual(build_column_units([]), [])

    def test_all_ungrouped_are_singletons_in_index_order(self):
        tasks = [
            FakeTask("t2_b.md", boardidx=20),
            FakeTask("t1_a.md", boardidx=10),
            FakeTask("t3_c.md", boardidx=30),
        ]
        units = build_column_units(tasks)
        self.assertEqual(slugs(units), ["", "", ""])
        self.assertEqual(names(units), [["t1_a.md"], ["t2_b.md"], ["t3_c.md"]])

    def test_group_unit_takes_position_of_its_first_member(self):
        """Scattered indices: the group renders at its FIRST member's key."""
        tasks = [
            FakeTask("t1_a.md", boardidx=10, boardgroup="perf_work"),
            FakeTask("t2_b.md", boardidx=20),
            FakeTask("t3_c.md", boardidx=99, boardgroup="perf_work"),
        ]
        units = build_column_units(tasks)
        self.assertEqual(slugs(units), ["perf_work", ""])
        # Both members render together, at index 10's position — the task at 99
        # is pulled up into the block.
        self.assertEqual(names(units), [["t1_a.md", "t3_c.md"], ["t2_b.md"]])

    def test_interleaved_non_member_renders_outside_the_block(self):
        """The honest consequence of writing no indices.

        A non-member whose index falls BETWEEN two members renders outside the
        group, at its own key position — on-disk index order and rendered order
        legitimately differ.
        """
        tasks = [
            FakeTask("t1_a.md", boardidx=10, boardgroup="perf_work"),
            FakeTask("t2_mid.md", boardidx=20),
            FakeTask("t3_c.md", boardidx=30, boardgroup="perf_work"),
        ]
        units = build_column_units(tasks)
        self.assertEqual(slugs(units), ["perf_work", ""])
        self.assertEqual(names(units), [["t1_a.md", "t3_c.md"], ["t2_mid.md"]])

    def test_singleton_group_keeps_its_slug(self):
        """A one-member group is NOT downgraded to an ungrouped singleton.

        The caller renders it as a plain card, but the group must survive in the
        data so a member moving away never silently dissolves it.
        """
        tasks = [FakeTask("t1_a.md", boardidx=10, boardgroup="solo")]
        units = build_column_units(tasks)
        self.assertEqual(slugs(units), ["solo"])

    def test_two_groups_order_by_first_member(self):
        tasks = [
            FakeTask("t1_a.md", boardidx=30, boardgroup="beta"),
            FakeTask("t2_b.md", boardidx=10, boardgroup="alpha"),
            FakeTask("t3_c.md", boardidx=40, boardgroup="beta"),
            FakeTask("t4_d.md", boardidx=20, boardgroup="alpha"),
        ]
        units = build_column_units(tasks)
        self.assertEqual(slugs(units), ["alpha", "beta"])
        self.assertEqual(names(units), [["t2_b.md", "t4_d.md"],
                                        ["t1_a.md", "t3_c.md"]])

    def test_index_ties_break_by_filename(self):
        tasks = [
            FakeTask("t2_b.md", boardidx=10),
            FakeTask("t1_a.md", boardidx=10),
        ]
        self.assertEqual(names(build_column_units(tasks)),
                         [["t1_a.md"], ["t2_b.md"]])

    def test_input_order_does_not_affect_output(self):
        """INV-R: the result is a function of persisted state, not call order."""
        tasks = [
            FakeTask("t1_a.md", boardidx=10, boardgroup="g"),
            FakeTask("t2_b.md", boardidx=20),
            FakeTask("t3_c.md", boardidx=30, boardgroup="g"),
        ]
        forward = names(build_column_units(tasks))
        backward = names(build_column_units(list(reversed(tasks))))
        self.assertEqual(forward, backward)

    def test_tombstone_member_is_ungrouped(self):
        tasks = [
            FakeTask("t1_a.md", boardidx=10, boardgroup="perf_work"),
            FakeTask("t2_b.md", boardidx=20, boardgroup=""),
        ]
        units = build_column_units(tasks)
        self.assertEqual(slugs(units), ["perf_work", ""])


class PostSyncFixtureTests(unittest.TestCase):
    """The two post-sync states must render deterministically with NO repair.

    `boardgroup` merges shared while `boardidx` stays per-checkout, so after a
    sync a remotely-added member keeps its own scattered index and a remotely
    removed member keeps its old position. If rendering were index-contiguity
    dependent these would need a reconciliation write on every board open; INV-R
    is what makes them need nothing.
    """

    def _base(self):
        return [
            FakeTask("t1_a.md", boardidx=1024, boardgroup="perf_work"),
            FakeTask("t2_b.md", boardidx=2048, boardgroup="perf_work"),
            FakeTask("t3_c.md", boardidx=3072),
        ]

    def test_remote_add_needs_no_reconciliation(self):
        """A member added remotely arrives with its OWN scattered index."""
        tasks = self._base()
        tasks[2].metadata["boardgroup"] = "perf_work"   # remote grouped it
        units = build_column_units(tasks)
        self.assertEqual(slugs(units), ["perf_work"])
        self.assertEqual(names(units), [["t1_a.md", "t2_b.md", "t3_c.md"]])
        # Stable across a reload of the identical persisted state.
        self.assertEqual(names(build_column_units(tasks)), names(units))

    def test_remote_remove_needs_no_reconciliation(self):
        """A member removed remotely arrives with the tombstone, not a move."""
        tasks = self._base()
        tasks[0].metadata["boardgroup"] = ""           # remote ungrouped it
        units = build_column_units(tasks)
        self.assertEqual(slugs(units), ["", "perf_work", ""])
        self.assertEqual(names(units),
                         [["t1_a.md"], ["t2_b.md"], ["t3_c.md"]])
        self.assertEqual(names(build_column_units(tasks)), names(units))

    def test_two_checkouts_with_identical_files_render_identically(self):
        pc1 = self._base()
        pc2 = self._base()
        self.assertEqual(names(build_column_units(pc1)),
                         names(build_column_units(pc2)))

    def test_grouping_writes_no_index(self):
        """Derivation must never mutate the tasks it reads."""
        tasks = self._base()
        before = [dict(t.metadata) for t in tasks]
        build_column_units(tasks)
        self.assertEqual([dict(t.metadata) for t in tasks], before)


class HelperTests(unittest.TestCase):

    def test_task_group_slug_reads_through_the_boundary(self):
        self.assertEqual(task_group_slug(FakeTask("a.md", boardgroup=[])), "")
        self.assertEqual(task_group_slug(FakeTask("a.md", boardgroup="g")), "g")

    def test_group_display_title_humanizes(self):
        self.assertEqual(group_display_title("perf_work"), "perf work")

    def test_group_display_title_tolerates_malformed(self):
        self.assertEqual(group_display_title(None), "")
        self.assertEqual(group_display_title([]), "")

    def test_group_members_returns_walk_order(self):
        tasks = [
            FakeTask("t3_c.md", boardidx=30, boardgroup="g"),
            FakeTask("t1_a.md", boardidx=10, boardgroup="g"),
            FakeTask("t2_b.md", boardidx=20),
        ]
        self.assertEqual([t.filename for t in group_members(tasks, "g")],
                         ["t1_a.md", "t3_c.md"])

    def test_group_members_of_empty_slug_is_empty(self):
        tasks = [FakeTask("t1_a.md", boardgroup="")]
        self.assertEqual(group_members(tasks, ""), [])


if __name__ == "__main__":
    unittest.main()
