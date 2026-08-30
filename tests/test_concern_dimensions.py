#!/usr/bin/env python3
"""Tests for the shadow concern impact-vector dimension vocabulary (t1636_1).

Covers `.aitask-scripts/monitor/concern_dimensions.py` — the single source of
truth every other t1636 child imports — and holds it in lockstep with the prose
definition in `.claude/skills/aitask-shadow/concern-format.md`.

Two guards here are structural rather than incidental, and both exist because
the naive version of each cannot fail:

* **The label-width guard** (:func:`check_label_widths`) is written as a
  ``raise``, not an ``assert``, because ``python -O`` strips assertions. These
  tests drive the real function over synthetic tables so the guard is proven to
  fire, rather than assumed to.
* **The doc/module drift guard** compares the doc's table **row by row** —
  ordered ``(dimension, label, rubric)`` tuples — not merely the set of
  dimension names. Name membership would be satisfied by the section's own
  prose, which names every dimension outside the table, so it would still pass
  with the table deleted; and it could never see a changed `label` (a
  load-bearing picker render token) or a drifted `rubric` at all. The negative
  controls below include exactly that case.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_concern_dimensions.py -v
"""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import NamedTuple

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(
    0, os.path.join(_TESTS_DIR, "..", ".aitask-scripts", "monitor")
)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from concern_dimensions import (  # noqa: E402
    CONCERN_DIMENSIONS,
    MAGNITUDES,
    MAX_LABEL_CELLS,
    OBLIGATION_DIMENSIONS,
    VALID_DIMENSIONS,
    check_label_widths,
    derive_priority,
    dimensions_pipe,
    label_for,
    normalize_magnitude,
    rubric_for,
    validate_dimension,
)

# The doc/code guard primitives are REUSED, not re-implemented: `extract_section`
# carries the "anchor matched N lines (expected exactly 1)" tripwire that stops a
# renamed heading from silently reducing a guard like this one to checking
# nothing, and `normalize` collapses whitespace so a re-wrapped table cell is not
# a false failure.
from test_shadow_disposition_surfaces import (  # noqa: E402
    extract_section,
    normalize,
)

REPO_ROOT = Path(_TESTS_DIR).parent
CONCERN_FORMAT = REPO_ROOT / ".claude/skills/aitask-shadow/concern-format.md"

#: Heading prefix of the spec section this module mirrors. Matched against the
#: start of the line, so the parenthetical suffix can be reworded freely.
SECTION_ANCHOR = "### Derived fields: the impact vector"

#: The settled vocabulary, pinned literally. Duplicating it here is deliberate:
#: a test that derived its expectation from the module could not detect a
#: rename, a reorder, or a relabelling at all.
EXPECTED_DIMENSIONS = [
    ("goal", "goal"),
    ("correctness", "corr"),
    ("robustness", "robus"),
    ("performance", "perf"),
    ("verification", "verif"),
    ("maintainability", "maint"),
    ("simplicity", "simpl"),
]


class ImpactEntryLike(NamedTuple):
    """Stands in for t1636_2's `ImpactEntry` — pins the index-access contract."""

    dimension: str
    magnitude: str


# --------------------------------------------------------------------------
# Doc-table parsing (shared by the drift guard and its negative controls)
# --------------------------------------------------------------------------


def _table_blocks(section: str) -> "list[list[str]]":
    """Split a section into contiguous runs of markdown table rows."""
    blocks: "list[list[str]]" = []
    current: "list[str]" = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            current.append(stripped)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def _cells(row: str) -> "list[str]":
    """Cells of a `| a | b | c |` row, outer pipes discarded."""
    return [cell.strip() for cell in row.split("|")[1:-1]]


def dimension_rows(doc_text: str) -> "list[tuple[str, str, str]]":
    """The doc's dimension table as ordered ``(dimension, label, rubric)`` tuples.

    Raises ``ValueError`` for every structural problem — a heading anchor that
    does not match exactly one line, an empty section, a section carrying no
    table or more than one, a malformed separator row, or a row without exactly
    three cells. Each of those is a way this guard could otherwise pass while
    reading the wrong text.
    """
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", encoding="utf-8", delete=False
    ) as handle:
        handle.write(doc_text)
        tmp = Path(handle.name)
    try:
        # Reuses the house tripwire; surfaced as ValueError so callers (and the
        # negative controls) have one exception type for "the doc is wrong".
        try:
            section = extract_section(tmp, SECTION_ANCHOR)
        except AssertionError as exc:
            raise ValueError(f"section anchor {SECTION_ANCHOR!r}: {exc}") from exc
    finally:
        tmp.unlink()

    if not section.strip():
        raise ValueError(
            f"section {SECTION_ANCHOR!r} is empty — the anchor matched a heading "
            f"with no body, so nothing is really being checked."
        )

    blocks = _table_blocks(section)
    if len(blocks) != 1:
        raise ValueError(
            f"section {SECTION_ANCHOR!r} contains {len(blocks)} markdown tables "
            f"(expected exactly 1). With none, the guard has nothing to compare; "
            f"with two, it cannot tell which one mirrors CONCERN_DIMENSIONS."
        )

    block = blocks[0]
    if len(block) < 3:
        raise ValueError(
            f"the dimension table has {len(block)} lines — expected a header, a "
            f"separator, and at least one dimension row."
        )
    if not re.fullmatch(r"\|[\s:|-]+\|", block[1]):
        raise ValueError(f"expected a table separator row, got {block[1]!r}")

    rows = []
    for row in block[2:]:
        cells = _cells(row)
        if len(cells) != 3:
            raise ValueError(
                f"dimension row {row!r} has {len(cells)} cells, expected 3 "
                f"(| dimension | label | rubric |)"
            )
        dimension, label, rubric = cells
        rows.append(
            (
                dimension.strip("`"),
                label.strip("`"),
                normalize(rubric).strip(),
            )
        )
    return rows


def expected_rows() -> "list[tuple[str, str, str]]":
    """`CONCERN_DIMENSIONS` in the row shape the doc table must carry."""
    return [
        (name, label, normalize(rubric).strip())
        for name, (label, rubric) in CONCERN_DIMENSIONS.items()
    ]


def check_doc_matches_module(doc_text: str) -> None:
    """Raise ``ValueError`` unless the doc's table equals the module exactly."""
    actual = dimension_rows(doc_text)
    expected = expected_rows()
    if actual != expected:
        raise ValueError(
            f"concern-format.md's dimension table has drifted from "
            f"CONCERN_DIMENSIONS.\n  doc:    {actual}\n  module: {expected}"
        )


class TestVocabularyContent(unittest.TestCase):
    """The settled vocabulary: names, order, labels, derived sets."""

    def test_names_and_labels_in_canonical_order(self):
        actual = [(name, label) for name, (label, _) in CONCERN_DIMENSIONS.items()]
        self.assertEqual(actual, EXPECTED_DIMENSIONS)

    def test_every_dimension_has_a_nonempty_rubric(self):
        for name, (_label, rubric) in CONCERN_DIMENSIONS.items():
            with self.subTest(dimension=name):
                self.assertTrue(rubric.strip(), f"{name} has no rubric")

    def test_valid_dimensions_is_derived_not_a_second_copy(self):
        self.assertEqual(VALID_DIMENSIONS, frozenset(CONCERN_DIMENSIONS))

    def test_obligation_core_is_a_subset_of_the_vocabulary(self):
        self.assertEqual(OBLIGATION_DIMENSIONS, frozenset({"goal", "correctness"}))
        self.assertLessEqual(OBLIGATION_DIMENSIONS, VALID_DIMENSIONS)

    def test_magnitudes_are_ordered_strongest_first(self):
        # derive_priority walks this tuple in order, so the order IS the ranking.
        self.assertEqual(MAGNITUDES, ("high", "medium", "low"))

    def test_dimensions_pipe_is_a_sorted_alternation(self):
        pipe = dimensions_pipe()
        self.assertEqual(pipe.split("|"), sorted(VALID_DIMENSIONS))
        # Usable verbatim inside a regex alternation group.
        self.assertRegex("robustness", f"^(?:{pipe})$")

    def test_accessors_are_total(self):
        self.assertEqual(label_for("robustness"), "robus")
        self.assertEqual(rubric_for("simplicity"), CONCERN_DIMENSIONS["simplicity"][1])
        # An unknown or absent name yields "" rather than raising.
        self.assertEqual(label_for("frobnication"), "")
        self.assertEqual(rubric_for(None), "")
        self.assertTrue(validate_dimension("goal"))
        self.assertFalse(validate_dimension("frobnication"))


class TestLabelWidthGuard(unittest.TestCase):
    """The packing guard must be able to fail — see check_label_widths.__doc__.

    The bound is stated in terminal cells but measured with ``len()``, so the
    guard pins ASCII as well as width; a non-ASCII label would make ``len()``
    the wrong instrument. Every control below drives the real function.
    """

    def test_the_shipped_table_satisfies_the_bound(self):
        # Positive control: import already ran this, but pin it explicitly so the
        # negative controls below are known to be testing a live predicate.
        check_label_widths(CONCERN_DIMENSIONS)
        for name, (label, _) in CONCERN_DIMENSIONS.items():
            with self.subTest(dimension=name):
                self.assertLessEqual(len(label), MAX_LABEL_CELLS)

    def test_rejects_a_label_one_cell_over_the_bound(self):
        with self.assertRaises(ValueError) as ctx:
            check_label_widths({"widened": ("robust", "six characters")})
        self.assertIn("robust", str(ctx.exception))

    def test_rejects_a_non_ascii_label(self):
        # Within the numeric bound, but len() no longer counts cells reliably.
        with self.assertRaises(ValueError) as ctx:
            check_label_widths({"unicode": ("robü", "four chars, not four cells")})
        self.assertIn("ASCII", str(ctx.exception))

    def test_rejects_an_empty_label(self):
        # Passes `len(label) <= 5` yet renders as a bare arrow.
        with self.assertRaises(ValueError):
            check_label_widths({"blank": ("", "no label at all")})


class TestNormalizeMagnitude(unittest.TestCase):
    def test_recognised_tokens_canonicalise(self):
        self.assertEqual(normalize_magnitude("HIGH"), "high")
        self.assertEqual(normalize_magnitude(" Low "), "low")
        self.assertEqual(normalize_magnitude("medium"), "medium")

    def test_unknown_and_absent_become_unspecified_never_low(self):
        for raw in ("extreme", "", "   ", None, 123, ["high"]):
            with self.subTest(raw=raw):
                self.assertEqual(normalize_magnitude(raw), "")


class TestDerivePriority(unittest.TestCase):
    """Parent decision 2: the single canonical vector -> marker-priority mapping."""

    def test_single_entry_uses_its_magnitude(self):
        self.assertEqual(derive_priority([("robustness", "high")]), "high")

    def test_takes_the_max_not_the_first(self):
        self.assertEqual(
            derive_priority([("simplicity", "low"), ("goal", "medium")]), "medium"
        )
        self.assertEqual(
            derive_priority([("goal", "medium"), ("correctness", "high")]), "high"
        )

    def test_absent_empty_and_all_unspecified_all_yield_low(self):
        self.assertEqual(derive_priority(None), "low")
        self.assertEqual(derive_priority(()), "low")
        self.assertEqual(derive_priority([("goal", "")]), "low")
        self.assertEqual(
            derive_priority([("goal", "extreme"), ("performance", None)]), "low"
        )

    def test_an_unknown_magnitude_does_not_mask_a_known_one(self):
        self.assertEqual(
            derive_priority([("goal", "extreme"), ("robustness", "medium")]), "medium"
        )

    def test_namedtuple_entries_resolve_identically_to_tuples(self):
        # Pins the index-access contract t1636_2's `ImpactEntry` relies on.
        entries = [
            ImpactEntryLike("simplicity", "low"),
            ImpactEntryLike("goal", "high"),
        ]
        self.assertEqual(derive_priority(entries), "high")
        self.assertEqual(
            derive_priority(entries),
            derive_priority([("simplicity", "low"), ("goal", "high")]),
        )


class TestDocModuleDrift(unittest.TestCase):
    """concern-format.md's table and CONCERN_DIMENSIONS are one vocabulary."""

    def setUp(self):
        self.doc_text = CONCERN_FORMAT.read_text(encoding="utf-8")

    def test_doc_table_matches_the_module_row_for_row(self):
        # assertEqual (not the predicate) so a real drift prints a readable diff.
        self.assertEqual(dimension_rows(self.doc_text), expected_rows())

    def test_predicate_accepts_the_real_doc(self):
        # Positive control: without it every negative control below could be
        # passing for the wrong reason.
        check_doc_matches_module(self.doc_text)

    def test_doc_section_names_the_module_as_the_source_of_truth(self):
        section = extract_section(CONCERN_FORMAT, SECTION_ANCHOR)
        self.assertIn("concern_dimensions.py", section)


class TestDocDriftNegativeControls(unittest.TestCase):
    """Each control mutates the real doc and proves the guard rejects it.

    Every case drives `check_doc_matches_module`, the same predicate the guard
    above uses — never a re-implementation.
    """

    def setUp(self):
        self.doc_text = CONCERN_FORMAT.read_text(encoding="utf-8")

    def _mutate(self, old: str, new: str) -> str:
        self.assertIn(old, self.doc_text, f"fixture anchor {old!r} not in the doc")
        return self.doc_text.replace(old, new, 1)

    def test_rejects_an_altered_label(self):
        mutated = self._mutate("| `correctness` | `corr` |", "| `correctness` | `crct` |")
        with self.assertRaises(ValueError):
            check_doc_matches_module(mutated)

    def test_rejects_an_altered_rubric(self):
        mutated = self._mutate(
            "right behavior on reachable inputs",
            "right behavior on every input",
        )
        with self.assertRaises(ValueError):
            check_doc_matches_module(mutated)

    def test_rejects_a_missing_dimension_row(self):
        row = [
            line
            for line in self.doc_text.splitlines()
            if line.strip().startswith("| `performance` |")
        ]
        self.assertEqual(len(row), 1, "expected exactly one performance table row")
        mutated = self.doc_text.replace(row[0] + "\n", "", 1)
        with self.assertRaises(ValueError):
            check_doc_matches_module(mutated)

    def test_rejects_an_extra_dimension_row(self):
        mutated = self._mutate(
            "| `simplicity` | `simpl` |",
            "| `frobnication` | `frob` | invented dimension |\n| `simplicity` | `simpl` |",
        )
        with self.assertRaises(ValueError):
            check_doc_matches_module(mutated)

    def test_rejects_reordered_rows(self):
        lines = self.doc_text.splitlines()
        idx = [
            i
            for i, line in enumerate(lines)
            if line.strip().startswith("| `goal` |")
            or line.strip().startswith("| `correctness` |")
        ]
        self.assertEqual(len(idx), 2, "expected the goal and correctness rows")
        lines[idx[0]], lines[idx[1]] = lines[idx[1]], lines[idx[0]]
        with self.assertRaises(ValueError):
            check_doc_matches_module("\n".join(lines))

    def test_rejects_a_deleted_table_even_though_the_prose_names_every_dimension(self):
        """The control that distinguishes this guard from a membership check.

        With the table removed, the section's surrounding prose still names all
        seven dimensions (the grammar example, the obligation core, the
        per-task-obligation note), so a name-membership guard would pass here.
        """
        lines = [
            line
            for line in self.doc_text.splitlines()
            if not line.strip().startswith("|")
        ]
        stripped = "\n".join(lines)
        section = extract_section_from_text(stripped, SECTION_ANCHOR)
        for dimension in VALID_DIMENSIONS:
            self.assertIn(
                dimension,
                section,
                f"fixture is not discriminating: {dimension!r} must still appear "
                f"in the section's prose for this control to mean anything",
            )
        with self.assertRaises(ValueError):
            check_doc_matches_module(stripped)

    def test_rejects_a_renamed_section_heading(self):
        mutated = self._mutate(SECTION_ANCHOR, "### Derived fields: the impact profile")
        with self.assertRaises(ValueError) as ctx:
            check_doc_matches_module(mutated)
        self.assertIn("anchor", str(ctx.exception))

    def test_rejects_a_second_table_in_the_section(self):
        mutated = self._mutate(
            "**Grammar.** Each of the three sentences",
            "| extra | table |\n|---|---|\n| a | b |\n\n**Grammar.** Each of the three sentences",
        )
        with self.assertRaises(ValueError) as ctx:
            check_doc_matches_module(mutated)
        self.assertIn("2 markdown tables", str(ctx.exception))


def extract_section_from_text(doc_text: str, anchor: str) -> str:
    """`extract_section` over in-memory text (used by the fixture self-check)."""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", encoding="utf-8", delete=False
    ) as handle:
        handle.write(doc_text)
        tmp = Path(handle.name)
    try:
        return extract_section(tmp, anchor)
    finally:
        tmp.unlink()


if __name__ == "__main__":
    unittest.main()
