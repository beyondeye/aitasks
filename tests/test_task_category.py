#!/usr/bin/env python3
"""Tests for lib/task_category.py -- the unified category axis (t1544_2).

Style follows tests/test_followup_backfill_classify.py: plain unittest, in-memory
string fixtures, no tempdirs. Exposes only ``unittest.TestCase`` methods -- a
module-level ``def test_x(arg)`` is read by pytest as a fixture request and
shows up as a collection-count mismatch in tests/test_collection_parity.py
(which is skipped entirely when pytest is absent, so it cannot be relied on to
catch the shape locally).

Fixtures go through ``stats_data.split_frontmatter`` rather than task_yaml on
purpose: that flat scanner is the production path this axis is fed from, and
pairing them here is what tests the real seam.
"""

import importlib.util
import os
import sys
import unittest
from collections import Counter
from pathlib import Path

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, ".aitask-scripts", "lib"))

import stats_data  # noqa: E402
import task_category  # noqa: E402


def resolve_raw(raw, filename="t999_example.md", tally=None):
    """Split a verbatim task file the way collection does, resolve its category.

    Takes the raw text so a caller can control the EXACT byte after the closing
    ``---``. The convenience wrapper below inserts a blank line there, which
    silently defeats any test trying to pin the first body line.
    """
    metadata, parsed_body = stats_data.split_frontmatter(raw)
    return task_category.resolve_category(metadata, parsed_body, filename, tally)


def resolve(frontmatter_lines, body, filename="t999_example.md", tally=None):
    """Build a conventional task file (blank line after the terminator)."""
    raw = "---\n" + "\n".join(frontmatter_lines) + "\n---\n\n" + body
    return resolve_raw(raw, filename, tally)


def _load_stats_module():
    script = Path(__file__).resolve().parents[1] / ".aitask-scripts" / "aitask_stats.py"
    spec = importlib.util.spec_from_file_location("aitask_stats_py_tc", script)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestPrecedence(unittest.TestCase):
    def test_declared_kind_beats_a_classifiable_body(self):
        """An explicit followup_kind wins over a body that would classify differently."""
        self.assertEqual(
            resolve(["issue_type: bug", "followup_kind: carry_over"],
                    "## Upstream defect\n\nprose\n"),
            "kind:carry_over",
        )

    def test_body_prose_rule_resolves_via_classify(self):
        """No followup_kind field: the retro-classifier supplies the kind."""
        self.assertEqual(
            resolve(["issue_type: bug"], "## Upstream defect\n\nprose\n"),
            "kind:upstream_defect",
        )

    def test_plain_task_is_genuine_new_work(self):
        """classify() returns kind=None for residue -> the issue-type fallback."""
        self.assertEqual(
            resolve(["issue_type: feature"], "## Goal\n\nAdd a thing.\n"),
            "type:feature",
        )

    def test_missing_issue_type_is_type_unknown(self):
        self.assertEqual(resolve(["priority: high"], "## Goal\n\nprose\n"), "type:unknown")


class TestNamespacing(unittest.TestCase):
    """The prefix is what disambiguates the two vocabularies -- not precedence."""

    def test_issue_type_manual_verification_is_a_kind(self):
        self.assertEqual(
            resolve(["issue_type: manual_verification"], "## Checklist\n\nitems\n"),
            "kind:manual_verification",
        )

    def test_followup_kind_manual_verification_is_the_same_key(self):
        self.assertEqual(
            resolve(["issue_type: bug", "followup_kind: manual_verification"],
                    "## Goal\n\nprose\n"),
            "kind:manual_verification",
        )

    def test_user_defined_issue_type_does_not_collide_with_a_kind_name(self):
        """task_types.txt is user-extensible; `review_finding` is also a kind name.

        Without the namespace this would silently merge two categories. Note the
        labels must NOT contain `review`, or classify's review_finding rule
        fires and the task legitimately becomes a kind.
        """
        self.assertEqual(
            resolve(["issue_type: review_finding", "labels: [reporting]"],
                    "## Goal\n\nprose\n"),
            "type:review_finding",
        )


class TestUnquoteAndClamp(unittest.TestCase):
    def test_quoted_value_still_resolves(self):
        """The flat scanner keeps quotes verbatim; _unquote runs before the clamp."""
        self.assertEqual(
            resolve(['followup_kind: "carry_over"', "issue_type: bug"],
                    "## Goal\n\nprose\n"),
            "kind:carry_over",
        )

    def test_trailing_whitespace_value_still_resolves(self):
        self.assertEqual(
            resolve(["followup_kind: risk_mitigation   ", "issue_type: bug"],
                    "## Goal\n\nprose\n"),
            "kind:risk_mitigation",
        )

    def test_bogus_value_falls_through_and_is_tallied(self):
        """A present-but-unrecognised kind must be counted, not silently absorbed."""
        tally = Counter()
        self.assertEqual(
            resolve(["followup_kind: not_a_real_kind", "issue_type: bug"],
                    "## Goal\n\nprose\n", tally=tally),
            "type:bug",
        )
        self.assertEqual(tally["invalid_followup_kind"], 1)

    def test_absent_kind_is_not_tallied(self):
        """`unknown` (absent) is the common case and must not trip the tripwire."""
        tally = Counter()
        resolve(["issue_type: bug"], "## Goal\n\nprose\n", tally=tally)
        self.assertEqual(tally["invalid_followup_kind"], 0)

    def test_tally_is_optional(self):
        self.assertEqual(
            resolve(["followup_kind: not_a_real_kind", "issue_type: bug"],
                    "## Goal\n\nprose\n"),
            "type:bug",
        )


class TestBodyBoundaryIsClassifierVisible(unittest.TestCase):
    """Pin the split_frontmatter/classify seam from BOTH defect directions.

    Metadata assertions cannot see the body boundary, and neither case below is
    sufficient alone -- see each test's docstring.
    """

    def test_first_body_line_is_not_dropped(self):
        """Catches an off-by-one that slices one line too far (lines[i+2:]).

        The trigger heading is the FIRST body line, so dropping it changes the
        answer from a kind to a type.
        """
        raw = "---\nissue_type: bug\n---\n## Upstream defect\n\nprose\n"
        self.assertEqual(resolve_raw(raw), "kind:upstream_defect")

    def test_frontmatter_does_not_leak_into_the_body(self):
        """Catches the body being the whole document instead of the tail.

        RE_RISK_MITIGATION is unanchored, so it fires anywhere in the text it is
        given -- which is exactly what makes leaked frontmatter detectable. The
        first case above cannot catch this: RE_UPSTREAM_HEADING is re.MULTILINE
        and still matches when the body is prefixed with other text.

        Verified by injecting `return result, content`: this test fails and the
        first one does not. (A `lines[i:]` slice is NOT a leak of frontmatter --
        it only prepends the terminator line, since the frontmatter sits before
        index i.)

        The other rule inputs are kept inert on purpose: issue_type is not
        manual_verification, labels contain neither `review` nor `qa`, and the
        filename does not contain `docs_gaps_since_` -- otherwise this would
        pass for the wrong reason.
        """
        self.assertEqual(
            resolve(['note: Risk-mitigation ("before") for t123',
                     "issue_type: bug",
                     "labels: [reporting]"],
                    "## Goal\n\nplain prose with no provenance marker\n"),
            "type:bug",
        )


class TestDisplayDispatch(unittest.TestCase):
    def test_kind_side_uses_the_vocabulary_labels_uncased(self):
        """label_for is the source of truth and is NOT uniformly lowercase."""
        self.assertEqual(task_category.category_display_name("kind:qa_test_gap"), "QA test gap")
        self.assertEqual(
            task_category.category_display_name("kind:risk_mitigation"), "risk mitigation"
        )
        self.assertEqual(task_category.category_display_name("kind:carry_over"), "carry-over")

    def test_type_side_uses_the_issue_type_map(self):
        self.assertEqual(task_category.category_display_name("type:bug"), "Bug Fixes")
        self.assertEqual(task_category.category_display_name("type:feature"), "Features")

    def test_unrecognised_kind_falls_back_to_the_bare_key(self):
        """label_for returns "" for an unknown kind; never render an empty cell."""
        self.assertEqual(task_category.category_display_name("kind:not_a_kind"), "not_a_kind")

    def test_is_followup_category(self):
        self.assertTrue(task_category.is_followup_category("kind:risk_mitigation"))
        self.assertFalse(task_category.is_followup_category("type:bug"))


class TestGetTypeDisplayNameByteIdentity(unittest.TestCase):
    """The delegation must not change one character of existing ait stats output."""

    @classmethod
    def setUpClass(cls):
        cls.stats = _load_stats_module()

    def test_unmapped_types_still_use_capitalize(self):
        """The map has no entry for either; both render via raw.capitalize().

        Delegating to category_display_name instead of type_display_name would
        turn the first into `manual verification`.
        """
        self.assertEqual(
            self.stats.get_type_display_name("manual_verification"), "Manual_verification"
        )
        self.assertEqual(self.stats.get_type_display_name("enhancement"), "Enhancement")

    def test_mapped_types_are_unchanged(self):
        for raw, expected in (
            ("feature", "Features"),
            ("bug", "Bug Fixes"),
            ("refactor", "Refactors"),
            ("documentation", "Documentation"),
            ("performance", "Performance"),
            ("style", "Style Changes"),
            ("test", "Tests"),
            ("chore", "Chores"),
            ("parent", "Parent Tasks"),
            ("child", "Child Tasks"),
        ):
            self.assertEqual(self.stats.get_type_display_name(raw), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
