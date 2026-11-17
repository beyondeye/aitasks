"""Tests for the multi-pane window stitcher (t2278_4).

`website/screenshots/stitch.py` puts each pane's capture at its place in the
window and draws the borders between panes as tmux does. No tmux is needed
here: the fixtures under `tests/fixtures/screenshots_stitch/` hold real pane
captures AND what a real tmux client drew for the same window (its rows and
which border cells it coloured), recorded by the oracle in
`tests/test_screenshots_session_live.py` (`tmux_render`). So the expected
borders come from tmux, not from the rule under test; the live module checks
the same rule against a live client.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_screenshots_stitch.py -v
"""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "website"))

from rich.console import Console  # noqa: E402

from screenshots import stitch  # noqa: E402
from screenshots import svg_export as sx  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "screenshots_stitch"
LAYOUTS = sorted(FIXTURES.glob("*_active*.json"))
GLYPHS = set("│─┼├┤┬┴┌┐└┘")


def load(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    panes = [stitch.Pane(p["left"], p["top"], p["width"], p["height"], p["active"], p["ansi"])
             for p in data["panes"]]
    return data["size"], panes, data["tmux"]


def green(row, x):
    style = row.get_style_at_offset(Console(), x)
    return style.color is not None and (style.color.name == "green" or style.color.number == 2)


def pane(left, top, width, height, ansi="", active=False):
    return stitch.Pane(left, top, width, height, active, ansi)


class AgainstTmuxTests(unittest.TestCase):
    """Two-pane (the minimonitor scene) and three-pane (the sitrep window)
    layouts, with each pane active in turn."""

    def test_fixtures_cover_both_layouts_and_every_active_pane(self):
        names = {p.stem for p in LAYOUTS}
        self.assertEqual(names, {"two_pane_active0", "two_pane_active1",
                                 "sitrep_active0", "sitrep_active1", "sitrep_active2"})

    def test_text_and_border_glyphs_are_what_tmux_drew(self):
        for path in LAYOUTS:
            with self.subTest(path.stem):
                (width, height), panes, tmux = load(path)
                rows = stitch.stitch(width, height, panes, stitch.REQUIRED_OPTIONS)
                self.assertEqual(len(rows), height)
                self.assertEqual(stitch.plain_rows(rows), tmux["rows"])

    def test_green_borders_are_the_ones_tmux_coloured(self):
        for path in LAYOUTS:
            with self.subTest(path.stem):
                (width, height), panes, tmux = load(path)
                rows = stitch.stitch(width, height, panes)
                ours = {(x, y) for y, row in enumerate(rows) for x in range(len(row.plain))
                        if row.plain[x] in GLYPHS and green(row, x)}
                expected = {tuple(cell) for cell in tmux["green_borders"]}
                self.assertTrue(expected)                 # non-vacuous
                self.assertEqual(ours, expected)

    def test_border_cells_agree_with_the_stitched_rows(self):
        (width, height), panes, _ = load(FIXTURES / "sitrep_active0.json")
        rows = stitch.plain_rows(stitch.stitch(width, height, panes))
        for (x, y), (glyph, _active) in stitch.border_cells(width, height, panes).items():
            self.assertEqual(rows[y][x] if x < len(rows[y]) else " ", glyph, (x, y))
        # The T-junctions of the sitrep layout: ├ / ┤ where the horizontal
        # border meets the full-height one.
        self.assertIn("┤", "".join(rows))


class DecodingTests(unittest.TestCase):
    def test_sgr_state_carries_within_a_pane_but_never_into_its_neighbour(self):
        left = pane(0, 0, 4, 2, "\x1b[44mAAAA\nAAAA", active=True)   # never reset
        right = pane(5, 0, 4, 2, "BBBB\nBBBB")
        rows = stitch.stitch(9, 2, [left, right])
        console = Console()
        # Row 1 of the left pane still has the blue background ...
        self.assertIsNotNone(rows[1].get_style_at_offset(console, 0).bgcolor)
        # ... and the right pane's row 1 does not.
        self.assertIsNone(rows[1].get_style_at_offset(console, 6).bgcolor)
        self.assertEqual(stitch.plain_rows(rows), ["AAAA│BBBB", "AAAA│BBBB"])

    def test_a_short_pane_row_is_padded_so_the_next_pane_starts_at_its_column(self):
        rows = stitch.stitch(9, 1, [pane(0, 0, 4, 1, "A"), pane(5, 0, 4, 1, "B")])
        self.assertEqual(stitch.plain_rows(rows), ["A   │B"])

    def test_wide_glyphs_count_as_two_cells(self):
        rows = stitch.stitch(9, 1, [pane(0, 0, 4, 1, "日本"), pane(5, 0, 4, 1, "B")])
        self.assertEqual(stitch.plain_rows(rows), ["日本│B"])


class RefusalTests(unittest.TestCase):
    def test_a_row_wider_than_its_pane_is_a_capture_error(self):
        with self.assertRaisesRegex(stitch.StitchError, "row 0 is 5 cells wide, the pane is 4"):
            stitch.stitch(9, 1, [pane(0, 0, 4, 1, "AAAAA"), pane(5, 0, 4, 1, "B")])

    def test_overlapping_panes_raise(self):
        with self.assertRaisesRegex(stitch.StitchError, "overlap"):
            stitch.stitch(9, 1, [pane(0, 0, 5, 1), pane(4, 0, 5, 1)])

    def test_a_pane_outside_the_window_raises(self):
        with self.assertRaisesRegex(stitch.StitchError, "outside"):
            stitch.stitch(9, 1, [pane(0, 0, 4, 1), pane(5, 0, 5, 1)])

    def test_no_pane_raises(self):
        with self.assertRaises(stitch.StitchError):
            stitch.stitch(9, 1, [])

    def test_border_options_other_than_the_pinned_ones_are_refused(self):
        for name in stitch.REQUIRED_OPTIONS:
            with self.subTest(name):
                options = dict(stitch.REQUIRED_OPTIONS, **{name: "something-else"})
                with self.assertRaisesRegex(stitch.StitchError, name):
                    stitch.stitch(9, 1, [pane(0, 0, 9, 1)], options)
        # tmux's own default: half-coloured borders in a two-pane window.
        with self.assertRaisesRegex(stitch.StitchError, "pane-border-indicators"):
            stitch.stitch(9, 1, [pane(0, 0, 9, 1)],
                          dict(stitch.REQUIRED_OPTIONS, **{"pane-border-indicators": "colour"}))


class ExportTests(unittest.TestCase):
    def test_a_stitched_window_exports_and_reads_back(self):
        (width, height), panes, tmux = load(FIXTURES / "two_pane_active0.json")
        svg = sx.rows_to_svg(stitch.stitch(width, height, panes), width, height,
                             title="aitasks minimonitor", scene_id="two_pane")
        text = sx.svg_plain_text(svg).splitlines()
        self.assertEqual(text[0], "aitasks minimonitor")
        self.assertEqual([row.rstrip() for row in text[1:]], tmux["rows"][:len(text) - 1])

    def test_ansi_to_svg_output_is_unchanged_by_the_split_into_rows_to_svg(self):
        """``ansi_to_svg`` became decode + ``rows_to_svg``; the reference file
        was exported by the code before that change, from this input."""
        ansi = ("\x1b[1;38;5;208mt12\x1b[0m add checkout ╭──╮ 日本\n\x1b[44mblue bg\n"
                "still blue\x1b[0m\n🏷️ tag")
        svg = sx.ansi_to_svg(ansi, 30, 5, title="aitasks board", scene_id="fixture")
        reference = (FIXTURES / "ansi_to_svg_reference.svg").read_text(encoding="utf-8")
        self.assertEqual(svg, reference)


if __name__ == "__main__":
    unittest.main()
