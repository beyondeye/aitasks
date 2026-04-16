"""Unit tests for brainstorm_sections: section parser, validation, and helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

from brainstorm.brainstorm_sections import (
    ContentSection,
    ParsedContent,
    format_section_footer,
    format_section_header,
    get_section_by_name,
    get_sections_for_dimension,
    parse_sections,
    section_names,
    validate_sections,
)

# ---------------------------------------------------------------------------
# Shared test content
# ---------------------------------------------------------------------------

MULTI_SECTION_TEXT = """\
# My Plan

Some preamble text here.

<!-- section: database_layer [dimensions: component_database, assumption_scale] -->
Set up PostgreSQL with read replicas.
Add connection pooling.
<!-- /section: database_layer -->

<!-- section: auth [dimensions: component_auth] -->
Use JWT tokens for authentication.
<!-- /section: auth -->

<!-- section: prerequisites -->
Install dependencies first.
<!-- /section: prerequisites -->

Epilogue content after all sections."""

NO_SECTION_TEXT = """\
# Just a plain document

No section markers at all.
Some more text."""

EMPTY_SECTION_TEXT = """\
Before.
<!-- section: empty_one -->
<!-- /section: empty_one -->
After."""


class TestParseSections(unittest.TestCase):
    """Tests for the core parse_sections() function."""

    def test_multi_section_with_dimensions(self):
        parsed = parse_sections(MULTI_SECTION_TEXT)

        self.assertEqual(len(parsed.sections), 3)

        db = parsed.sections[0]
        self.assertEqual(db.name, "database_layer")
        self.assertEqual(db.dimensions, ["component_database", "assumption_scale"])
        self.assertIn("PostgreSQL", db.content)
        self.assertIn("connection pooling", db.content)
        self.assertEqual(db.start_line, 5)
        self.assertEqual(db.end_line, 8)

        auth = parsed.sections[1]
        self.assertEqual(auth.name, "auth")
        self.assertEqual(auth.dimensions, ["component_auth"])
        self.assertEqual(auth.start_line, 10)
        self.assertEqual(auth.end_line, 12)

        prereq = parsed.sections[2]
        self.assertEqual(prereq.name, "prerequisites")
        self.assertEqual(prereq.dimensions, [])
        self.assertEqual(prereq.start_line, 14)
        self.assertEqual(prereq.end_line, 16)

    def test_no_sections(self):
        parsed = parse_sections(NO_SECTION_TEXT)

        self.assertEqual(parsed.sections, [])
        self.assertIn("Just a plain document", parsed.preamble)
        self.assertIn("Some more text", parsed.preamble)
        self.assertEqual(parsed.epilogue, "")

    def test_empty_section_content(self):
        parsed = parse_sections(EMPTY_SECTION_TEXT)

        self.assertEqual(len(parsed.sections), 1)
        self.assertEqual(parsed.sections[0].name, "empty_one")
        self.assertEqual(parsed.sections[0].content, "")

    def test_preamble_and_epilogue(self):
        parsed = parse_sections(MULTI_SECTION_TEXT)

        self.assertIn("preamble text", parsed.preamble)
        self.assertIn("Epilogue content", parsed.epilogue)

    def test_content_between_sections(self):
        text = (
            "Preamble\n"
            "<!-- section: a -->\nA content\n<!-- /section: a -->\n"
            "Between sections\n"
            "<!-- section: b -->\nB content\n<!-- /section: b -->\n"
            "After"
        )
        parsed = parse_sections(text)

        self.assertEqual(len(parsed.sections), 2)
        self.assertEqual(parsed.preamble, "Preamble")
        self.assertIn("Between sections", parsed.epilogue)
        self.assertIn("After", parsed.epilogue)

    def test_raw_preserved(self):
        parsed = parse_sections(MULTI_SECTION_TEXT)
        self.assertEqual(parsed.raw, MULTI_SECTION_TEXT)


class TestValidateSections(unittest.TestCase):
    """Tests for validate_sections()."""

    def test_valid_sections_no_errors(self):
        parsed = parse_sections(MULTI_SECTION_TEXT)
        errors = validate_sections(parsed)
        self.assertEqual(errors, [])

    def test_duplicate_section_names(self):
        text = (
            "<!-- section: dup -->\nA\n<!-- /section: dup -->\n"
            "<!-- section: dup -->\nB\n<!-- /section: dup -->"
        )
        parsed = parse_sections(text)
        errors = validate_sections(parsed)
        self.assertTrue(any("Duplicate" in e and "dup" in e for e in errors))

    def test_unclosed_section(self):
        text = "<!-- section: open_no_close -->\nSome content\n"
        parsed = parse_sections(text)
        errors = validate_sections(parsed)
        self.assertTrue(any("Unclosed" in e and "open_no_close" in e for e in errors))

    def test_invalid_dimension_prefix(self):
        text = (
            "<!-- section: bad_dims [dimensions: invalid_prefix_foo] -->\n"
            "Content\n"
            "<!-- /section: bad_dims -->"
        )
        parsed = parse_sections(text)
        errors = validate_sections(parsed)
        self.assertTrue(any("Invalid dimension" in e for e in errors))


class TestQueryHelpers(unittest.TestCase):
    """Tests for get_section_by_name, get_sections_for_dimension, section_names."""

    def setUp(self):
        self.parsed = parse_sections(MULTI_SECTION_TEXT)

    def test_get_section_by_name_found(self):
        sec = get_section_by_name(self.parsed, "auth")
        self.assertIsNotNone(sec)
        self.assertEqual(sec.name, "auth")

    def test_get_section_by_name_not_found(self):
        sec = get_section_by_name(self.parsed, "nonexistent")
        self.assertIsNone(sec)

    def test_get_sections_for_dimension(self):
        secs = get_sections_for_dimension(self.parsed, "component_database")
        self.assertEqual(len(secs), 1)
        self.assertEqual(secs[0].name, "database_layer")

    def test_get_sections_for_dimension_shared(self):
        text = (
            "<!-- section: a [dimensions: component_shared] -->\nA\n<!-- /section: a -->\n"
            "<!-- section: b [dimensions: component_shared] -->\nB\n<!-- /section: b -->"
        )
        parsed = parse_sections(text)
        secs = get_sections_for_dimension(parsed, "component_shared")
        self.assertEqual(len(secs), 2)
        self.assertEqual([s.name for s in secs], ["a", "b"])

    def test_section_names(self):
        names = section_names(self.parsed)
        self.assertEqual(names, ["database_layer", "auth", "prerequisites"])


class TestGenerationHelpers(unittest.TestCase):
    """Tests for format_section_header, format_section_footer, and round-trip."""

    def test_format_header_with_dimensions(self):
        header = format_section_header("db", ["component_database", "assumption_scale"])
        self.assertEqual(header, "<!-- section: db [dimensions: component_database, assumption_scale] -->")

    def test_format_header_no_dimensions(self):
        header = format_section_header("prereqs")
        self.assertEqual(header, "<!-- section: prereqs -->")

    def test_format_header_empty_dimensions(self):
        header = format_section_header("prereqs", [])
        self.assertEqual(header, "<!-- section: prereqs -->")

    def test_format_footer(self):
        footer = format_section_footer("db")
        self.assertEqual(footer, "<!-- /section: db -->")

    def test_round_trip(self):
        name = "round_trip_test"
        dims = ["component_api", "assumption_load"]
        content = "Line one.\nLine two."

        header = format_section_header(name, dims)
        footer = format_section_footer(name)
        doc = f"{header}\n{content}\n{footer}"

        parsed = parse_sections(doc)
        self.assertEqual(len(parsed.sections), 1)

        sec = parsed.sections[0]
        self.assertEqual(sec.name, name)
        self.assertEqual(sec.dimensions, dims)
        self.assertEqual(sec.content, content)


if __name__ == "__main__":
    unittest.main()
