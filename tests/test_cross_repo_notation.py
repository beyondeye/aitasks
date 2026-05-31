"""Unit tests for lib/cross_repo_notation.py."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = REPO_ROOT / ".aitask-scripts" / "lib"
sys.path.insert(0, str(LIB_DIR))

from cross_repo_notation import parse  # noqa: E402


class TestParse(unittest.TestCase):
    def test_basic_and_t_prefix(self):
        self.assertEqual(
            parse("see aitasks#42 and aitasks_mobile#t16_2"),
            [("aitasks", "42"), ("aitasks_mobile", "16_2")],
        )

    def test_no_refs(self):
        self.assertEqual(parse("no refs here"), [])

    def test_malformed_trailing_hash(self):
        self.assertEqual(parse("malformed#"), [])

    def test_empty_and_falsy(self):
        self.assertEqual(parse(""), [])
        self.assertEqual(parse(None), [])

    def test_child_id_form(self):
        self.assertEqual(parse("repo#835_3"), [("repo", "835_3")])

    def test_t_prefix_stripped(self):
        # The leading 't' is tolerated but stripped to the canonical form.
        self.assertEqual(parse("repo#t99"), [("repo", "99")])

    def test_dash_and_underscore_in_project(self):
        self.assertEqual(
            parse("my-proj_2#7"),
            [("my-proj_2", "7")],
        )

    def test_multiple_in_prose(self):
        text = "blocked by aitasks_mobile#1, aitasks_mobile#2_3; also foo#10."
        self.assertEqual(
            parse(text),
            [("aitasks_mobile", "1"), ("aitasks_mobile", "2_3"), ("foo", "10")],
        )

    def test_uppercase_leading_char_partial_match(self):
        # Canonical project keys are lowercase ([a-z0-9_-]); an uppercase
        # leading char is dropped and only the lowercase tail is captured.
        # Harmless in practice (an unresolvable name yields an error popup).
        self.assertEqual(parse("Repo#5"), [("epo", "5")])


if __name__ == "__main__":
    unittest.main()
