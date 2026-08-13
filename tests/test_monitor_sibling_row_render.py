"""Render-level guard for the sibling picker's follow-up marker (t1468_5).

`_SiblingRow` and `NextSiblingDialog` are the monitor / minimonitor surfaces
where a user chooses the next task to work on, so "this candidate is an
auto-spawned follow-up" has to be visible there. Neither widget had any test
coverage before this file.

Asserts on the rich-markup string the widgets actually build, and pins the
three-way rule the shared boundary owns:

- a recognised kind  -> its glyph, carrying its severity-family colour;
- an absent kind     -> no marker at all (an ordinary task must not be
                        decorated — that would make the marker meaningless);
- an unrecognised kind -> the `·` fallback with no colour, because a bad value
                        that silently vanishes is indistinguishable from a task
                        that was never a follow-up.

It also pins the two-cell prefix width: the minimonitor variant renders at
~40 columns, so a marker that widened every row would push the title off.

This file deliberately does NOT prove the value reaches the widget from a task
file — that is `tests/test_task_info_cache_followup_kind.py`, which drives the
real cache. Constructing the widget directly here would pass just as happily
against a broken frontmatter lookup.

Run: python3 tests/test_monitor_sibling_row_render.py
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR / "lib"))

from textual.app import App  # noqa: E402

from followup_kinds import FOLLOWUP_KINDS, UNKNOWN_GLYPH  # noqa: E402
from monitor.monitor_shared import (  # noqa: E402
    NextSiblingDialog,
    _followup_prefix,
    _SiblingRow,
)

RISK_GLYPH, RISK_COLOUR, _ = FOLLOWUP_KINDS["risk_mitigation"]
DOCS_GLYPH, DOCS_COLOUR, _ = FOLLOWUP_KINDS["docs_gap"]


class FollowupPrefixTests(unittest.TestCase):
    def test_recognised_kind_renders_glyph_with_its_colour(self) -> None:
        prefix = _followup_prefix("risk_mitigation")
        self.assertIn(RISK_GLYPH, prefix)
        self.assertIn(RISK_COLOUR, prefix)

    def test_hex_colour_kind_renders_its_literal_hex(self) -> None:
        """`docs_gap`'s colour is a hex, not a name (t1468_3): Textual cannot
        parse `bright_black`, and an unparseable style falls back to the default
        foreground — i.e. no colour signal at all."""
        prefix = _followup_prefix("docs_gap")
        self.assertIn(DOCS_GLYPH, prefix)
        self.assertIn(DOCS_COLOUR, prefix)
        self.assertTrue(DOCS_COLOUR.startswith("#"))

    def test_absent_kind_renders_no_marker(self) -> None:
        for absent in ("", None, [], 0):
            with self.subTest(value=absent):
                self.assertEqual(_followup_prefix(absent), "  ")

    def test_unrecognised_kind_renders_the_fallback_without_colour(self) -> None:
        prefix = _followup_prefix("not_a_real_kind")
        self.assertIn(UNKNOWN_GLYPH, prefix)
        self.assertNotIn("[", prefix, "the fallback carries no colour tag")

    def test_prefix_is_always_two_cells(self) -> None:
        """Marked and unmarked rows must stay column-aligned, and the narrow
        (~40 col) minimonitor variant must lose no width to the marker."""
        for kind in ("", "risk_mitigation", "docs_gap", "not_a_real_kind"):
            with self.subTest(kind=kind):
                visible = _strip_markup(_followup_prefix(kind))
                self.assertEqual(len(visible), 2, repr(visible))


class SiblingRowRenderTests(unittest.TestCase):
    def test_row_shows_the_marker_before_the_task_id(self) -> None:
        rendered = _SiblingRow("42_3", "Do the thing", [],
                               "risk_mitigation").render()
        self.assertIn(RISK_GLYPH, rendered)
        self.assertLess(rendered.index(RISK_GLYPH), rendered.index("t42_3"))
        self.assertIn("Do the thing", rendered)

    def test_ordinary_row_is_undecorated(self) -> None:
        rendered = _SiblingRow("42_3", "Do the thing", [], "").render()
        for glyph, _colour, _label in FOLLOWUP_KINDS.values():
            self.assertNotIn(glyph, rendered)
        self.assertNotIn(UNKNOWN_GLYPH, rendered)

    def test_default_kind_keeps_the_pre_t1468_row_shape(self) -> None:
        """The parameter is optional, so a caller that has not been updated
        still renders an ordinary row rather than crashing."""
        self.assertEqual(_SiblingRow("42_3", "Do the thing", []).render(),
                         _SiblingRow("42_3", "Do the thing", [], "").render())

    def test_marker_and_blocked_by_coexist(self) -> None:
        rendered = _SiblingRow("42_3", "Do the thing", ["42_2"],
                               "upstream_defect").render()
        self.assertIn(FOLLOWUP_KINDS["upstream_defect"][0], rendered)
        self.assertIn("blocked by t42_2", rendered)


class _DialogHost(App):
    """Host that pushes the real dialog, so the assertion reads the composited
    screen rather than a widget's own render string — the latter cannot reveal
    that Rich ellipsised or wrapped the line on its way to the terminal."""

    def __init__(self, kind: str, narrow: bool) -> None:
        super().__init__()
        self._kind = kind
        self._narrow = narrow

    def on_mount(self) -> None:
        self.push_screen(NextSiblingDialog(
            "42_1", "Current title", "Implementing",
            "42_3", "Suggested title", "42",
            narrow=self._narrow, suggested_followup_kind=self._kind,
        ))


class NextSiblingDialogRenderTests(unittest.TestCase):
    """The `Suggested:` line is a second surface over the same value; if only
    the picker were marked, the two would disagree about the same task."""

    #: The minimonitor companion pane is ~40 columns; the marker must not push
    #: the suggested title out of the composited line there.
    NARROW_WIDTH = 40

    def _screen(self, kind: str, narrow: bool = False) -> list[str]:
        async def run():
            width = self.NARROW_WIDTH if narrow else 100
            host = _DialogHost(kind, narrow)
            async with host.run_test(size=(width, 24)):
                await host.workers.wait_for_complete()
                return [strip.text.rstrip()
                        for strip in host.screen._compositor.render_strips()]

        return asyncio.run(run())

    def _suggested_line(self, kind: str, narrow: bool = False) -> str:
        rows = [r for r in self._screen(kind, narrow) if "Suggested:" in r]
        self.assertEqual(len(rows), 1, rows)
        return rows[0]

    def test_suggested_line_shows_the_marker(self) -> None:
        line = self._suggested_line("risk_mitigation")
        self.assertIn(RISK_GLYPH, line)
        self.assertLess(line.index(RISK_GLYPH), line.index("t42_3"))

    def test_suggested_line_undecorated_when_absent(self) -> None:
        line = self._suggested_line("")
        for glyph, _colour, _label in FOLLOWUP_KINDS.values():
            self.assertNotIn(glyph, line)
        self.assertNotIn(UNKNOWN_GLYPH, line)

    def test_narrow_variant_keeps_marker_and_title(self) -> None:
        line = self._suggested_line("risk_mitigation", narrow=True)
        self.assertIn(RISK_GLYPH, line)
        self.assertIn("t42_3", line)
        self.assertNotIn("…", line, f"line was ellipsised: {line!r}")


def _strip_markup(text: str) -> str:
    """Drop rich `[...]` tags, leaving the cells that actually paint."""
    out, depth = [], 0
    for char in text:
        if char == "[":
            depth += 1
        elif char == "]":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(char)
    return "".join(out)


if __name__ == "__main__":
    unittest.main()
