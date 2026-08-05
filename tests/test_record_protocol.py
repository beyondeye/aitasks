"""Unit pins for lib/record_protocol.py — the `|`-delimited safety policy (t1433).

The module was extracted from three private copies (`work_report_gather`,
`trail_gather`, `board_columns`). Its consumers' own suites pin the *protocol*
end-to-end; this file pins the *policy* directly, so a change in the shared rule
is attributable here rather than surfacing as a puzzling CLI diff.

Two properties are load bearing and easy to break silently:

* the **last-field / middle-field asymmetry** — `|` must survive the last field
  (consumers split with a fixed maxsplit, and titles/paths legitimately contain
  one) and must not survive a middle one;
* the **zero-import** property — `board_columns` imports this module and is
  itself imported by `board/aitask_board.py` at module scope, so any import
  added here lands on the board's startup path. Asserted structurally via `ast`,
  because nothing else in the tree would notice.

Run: ~/.aitask/venv/bin/python -m pytest tests/test_record_protocol.py -q
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / ".aitask-scripts" / "lib" / "record_protocol.py"
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import record_protocol as rp  # noqa: E402


class RecordBreakingTests(unittest.TestCase):
    """The classifier, asserted at its weakest surface: one character at a time."""

    def test_each_reserved_character_is_detected_on_its_own(self):
        """A string containing all three would pass even if two checks were lost.

        So each is asserted separately — that is what makes this discriminate.
        """
        for ch in ("|", "\r", "\n"):
            with self.subTest(char=repr(ch)):
                self.assertTrue(rp.has_record_breaking(f"ba{ch}d"))

    def test_the_reserved_set_is_exactly_these_three(self):
        self.assertEqual(rp.RECORD_BREAKING, ("|", "\r", "\n"))

    def test_a_clean_value_is_not_flagged(self):
        """Positive control: the predicate is not simply always true."""
        self.assertFalse(rp.has_record_breaking("perfectly fine / title"))
        self.assertFalse(rp.has_record_breaking(""))


class LastFieldTests(unittest.TestCase):
    """`|` SURVIVES here. That asymmetry is the point of the name."""

    def test_pipe_survives(self):
        self.assertEqual(rp.sanitize_last_field("Col|One"), "Col|One")
        self.assertEqual(rp.sanitize_last_field("a|b|c"), "a|b|c")

    def test_each_newline_form_collapses_to_exactly_one_space(self):
        """CRLF is ONE line break, so it must not become two spaces (t1433)."""
        for raw, expected in (("a\r\nb", "a b"), ("a\rb", "a b"), ("a\nb", "a b")):
            with self.subTest(raw=repr(raw)):
                self.assertEqual(rp.sanitize_last_field(raw), expected)

    def test_result_can_never_break_a_record_except_by_pipe(self):
        out = rp.sanitize_last_field("t\r\nitle\rwith\nbreaks|and|pipes")
        self.assertNotIn("\r", out)
        self.assertNotIn("\n", out)
        self.assertIn("|", out)


class MiddleFieldTests(unittest.TestCase):
    """`|` does NOT survive here — a middle field is delimited on both sides."""

    def test_pipe_is_stripped(self):
        self.assertEqual(rp.sanitize_middle_field("Col|One"), "ColOne")

    def test_newlines_are_handled_as_in_the_last_field(self):
        self.assertEqual(rp.sanitize_middle_field("a\r\nb"), "a b")

    def test_result_carries_no_reserved_character_at_all(self):
        out = rp.sanitize_middle_field("#FF|00\r00\n")
        for ch in rp.RECORD_BREAKING:
            with self.subTest(char=repr(ch)):
                self.assertNotIn(ch, out)

    def test_agrees_with_last_field_whenever_there_is_no_pipe(self):
        """The two differ ONLY on `|`. Anything else is an accidental drift."""
        for raw in ("plain", "a\r\nb", "a\rb", "a\nb", "", "  spaced  "):
            with self.subTest(raw=repr(raw)):
                self.assertEqual(rp.sanitize_middle_field(raw),
                                 rp.sanitize_last_field(raw))


class EnumFieldTests(unittest.TestCase):
    """`unknown` (no value) and `invalid` (untransportable value) stay distinct."""

    def test_absent_values_read_as_unknown(self):
        for raw in (None, ""):
            with self.subTest(raw=repr(raw)):
                self.assertEqual(rp.enum_field(raw), rp.UNKNOWN_ENUM)

    def test_record_breaking_values_read_as_invalid(self):
        for ch in rp.RECORD_BREAKING:
            with self.subTest(char=repr(ch)):
                self.assertEqual(rp.enum_field(f"Sta{ch}tus"), rp.INVALID_ENUM)

    def test_unknown_and_invalid_are_different_strings(self):
        """Collapsing them would erase "had no value" vs "had an unusable one"."""
        self.assertNotEqual(rp.UNKNOWN_ENUM, rp.INVALID_ENUM)
        self.assertEqual((rp.UNKNOWN_ENUM, rp.INVALID_ENUM), ("unknown", "invalid"))

    def test_a_clean_value_passes_through_unchanged(self):
        self.assertEqual(rp.enum_field("Ready"), "Ready")

    def test_a_clean_non_string_is_stringified(self):
        self.assertEqual(rp.enum_field(42), "42")
        self.assertEqual(rp.enum_field(True), "True")

    def test_zero_is_a_value_not_an_absence(self):
        """`0 == ""` is False in Python, but `not 0` is True — so an
        emptiness test written as truthiness would report `unknown` here."""
        self.assertEqual(rp.enum_field(0), "0")


class DependencyFreeTests(unittest.TestCase):
    """The constraint the task states, enforced structurally rather than by trust.

    `board_columns` imports this module and `board/aitask_board.py` imports
    `board_columns` at module scope, so an import added here silently becomes a
    board startup cost. Parsing the source is what makes that visible: importing
    the module and inspecting its namespace would not distinguish a plain
    `import json` from a name it defines itself.
    """

    def _tree(self) -> ast.Module:
        return ast.parse(MODULE_PATH.read_text(encoding="utf-8"))

    def test_the_module_imports_nothing_at_all(self):
        imports = [
            node for node in ast.walk(self._tree())
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        rendered = [ast.dump(node) for node in imports]
        self.assertEqual(
            imports, [],
            "lib/record_protocol.py must import nothing — not even stdlib — "
            "because it sits on the board's module-scope startup path via "
            f"board_columns. Found: {rendered}")

    def test_the_parse_actually_sees_the_real_module(self):
        """Negative control for the assertion above.

        An empty import list also results from parsing the wrong file or an
        empty one, so pin that the tree really contains this module's functions.
        """
        names = {node.name for node in ast.walk(self._tree())
                 if isinstance(node, ast.FunctionDef)}
        self.assertEqual(
            names,
            {"has_record_breaking", "sanitize_last_field",
             "sanitize_middle_field", "enum_field"})

    def test_no_all_is_declared(self):
        """This is an internal shared implementation detail, not a public API.

        An `__all__` would advertise a stability commitment the module does not
        make (see its docstring); `lib/board_ordering.py` is the precedent.
        """
        self.assertFalse(hasattr(rp, "__all__"))


if __name__ == "__main__":
    unittest.main()
