"""Tests for the docs-screenshot SVG export and cell finding (t2278_2).

`website/screenshots/svg_export.py` turns a captured tmux pane (text with SGR
escapes) into a Rich terminal SVG. No tmux is needed here: the captures are
canned strings shaped like `capture-pane -e -p -N` output.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_screenshots_svg_export.py -v
"""
import os
import re
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "website"))

from screenshots import session as sessions  # noqa: E402
from screenshots import svg_export as sx  # noqa: E402

ESC = "\x1b"
BG = f"{ESC}[48;2;18;52;86m"          # #123456
FG = f"{ESC}[38;2;255;85;85m"         # #ff5555
BOLD = f"{ESC}[1m"
RESET = f"{ESC}[0m"


def export(ansi, width=20, height=4, title="aitasks board", scene="scene_a"):
    return sx.ansi_to_svg(ansi, width, height, title=title, scene_id=scene)


def rects(svg, colour):
    return re.findall(rf'<rect fill="{colour}"[^>]*/>', svg)


class ExportTests(unittest.TestCase):
    def test_title_and_unique_id(self):
        svg = export("hello")
        self.assertIn("terminal-scene_a-", svg)
        self.assertIn("aitasks&#160;board", svg)
        self.assertIn("hello", sx.svg_plain_text(svg))

    def test_sgr_state_carries_across_lines(self):
        """tmux emits a colour once and lets it run over the following lines.

        The second row sets nothing, so a row-by-row decode would lose its
        background. This is the defect the first real capture showed.
        """
        ansi = f"{BG}first row{' ' * 11}\nsecond row{' ' * 10}\n{RESET}third"
        svg = export(ansi)
        ys = sorted({re.search(r' y="([0-9.]+)"', r).group(1) for r in rects(svg, "#123456")},
                    key=float)
        self.assertEqual(len(ys), 2, "the background must cover the first two rows")

    def test_control_row_by_row_decode_loses_the_carried_background(self):
        """Negative control: the naive decode really does drop the second row,
        so the test above can fail."""
        from rich.text import Text

        rows = [f"{BG}first row{' ' * 11}", f"second row{' ' * 10}"]
        naive = [Text.from_ansi(r) for r in rows]
        self.assertTrue(any(s.style and s.style.bgcolor for s in naive[0].spans))
        self.assertFalse(any(s.style and s.style.bgcolor for s in naive[1].spans))

    def test_colour_bold_box_drawing_and_wide_glyph_survive(self):
        ansi = f"{FG}┌──┐{RESET} {BOLD}bold{RESET}\n│👶│ café ↳"
        svg = export(ansi)
        text = sx.svg_plain_text(svg)
        for wanted in ("┌──┐", "bold", "👶", "café", "↳"):
            self.assertIn(wanted, text)
        self.assertIn("#ff5555", svg)
        self.assertIn("font-weight: bold", svg)

    def test_rows_are_padded_and_cropped_to_the_pane_height(self):
        self.assertEqual(export("a\nb\nc\nd\ne\nf", height=4).count("clipPath id"),
                         export("a", height=4).count("clipPath id"))
        self.assertNotIn(">f<", export("a\nb\nc\nd\ne\nf", height=4))

    def test_a_row_wider_than_the_pane_is_an_error(self):
        with self.assertRaises(sx.ExportError):
            export("x" * 21, width=20)

    def test_scene_id_is_validated(self):
        with self.assertRaises(sx.ExportError):
            export("x", scene="Bad Id")


class FindCellsTests(unittest.TestCase):
    """`find` reports terminal cells, so a wide glyph before the text counts
    as two columns, the measure the exporter uses."""

    def _find(self, rows, text):
        fake = types.SimpleNamespace(size=(40, len(rows)))
        with mock.patch.object(sessions, "screen_rows", return_value=rows):
            return sessions.find(fake, text)

    def test_plain_text_and_repeats(self):
        self.assertEqual(self._find(["ab ab", "", "  ab"], "ab"), [(0, 0), (3, 0), (2, 2)])

    def test_wide_glyph_shifts_the_column(self):
        self.assertEqual(self._find(["│👶 3 children"], "3 children"), [(4, 0)])

    def test_absent_text(self):
        self.assertEqual(self._find(["nothing here"], "missing"), [])


if __name__ == "__main__":
    unittest.main()
