"""Unit tests for section_viewer scroll-to-section correlation (t873_2).

Covers the pure helpers that map a parsed section to its rendered heading's
Textual ``header_id``: ``_first_heading``, ``_norm_title`` and
``correlate_sections_to_toc``. These are widget-free, so they run without a
Textual app (the actual scroll is validated manually — see the t873 aggregate
manual-verification sibling).
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from textual.app import App, ComposeResult  # noqa: E402
from textual.widgets import Markdown, Static  # noqa: E402

from section_viewer import (  # noqa: E402
    SectionAwareMarkdown,
    SectionMinimap,
    SectionViewerScreen,
    _first_heading,
    _norm_title,
    correlate_sections_to_toc,
    parse_sections,
)


def _section(name: str, body: str) -> str:
    return f"<!-- section: {name} -->\n{body}\n<!-- /section: {name} -->\n"


class FirstHeadingTests(unittest.TestCase):
    def test_simple_atx_heading(self):
        self.assertEqual(_first_heading("## Overview\nbody"), (2, "Overview"))

    def test_level_is_hash_count(self):
        self.assertEqual(_first_heading("#### Deep heading"), (4, "Deep heading"))

    def test_first_heading_wins(self):
        self.assertEqual(
            _first_heading("intro\n## First\ntext\n### Second"), (2, "First")
        )

    def test_skips_fenced_code_hash_lines(self):
        content = "```\n# not a heading\n```\n## Real Heading\n"
        self.assertEqual(_first_heading(content), (2, "Real Heading"))

    def test_skips_tilde_fence(self):
        content = "~~~\n# nope\n~~~\n### Actual\n"
        self.assertEqual(_first_heading(content), (3, "Actual"))

    def test_none_when_no_heading(self):
        self.assertIsNone(_first_heading("just prose\nno headings here"))

    def test_keeps_inline_markup_in_title(self):
        # _first_heading returns the raw title; normalization happens elsewhere.
        self.assertEqual(
            _first_heading("## Tooling — `scripts/gates.sh`"),
            (2, "Tooling — `scripts/gates.sh`"),
        )


class NormTitleTests(unittest.TestCase):
    def test_strips_backticks(self):
        self.assertEqual(_norm_title("Tooling — `scripts/gates.sh`"),
                         "tooling — scripts/gates.sh")

    def test_strips_emphasis(self):
        self.assertEqual(_norm_title("Profile *(inherited)* _x_"),
                         "profile (inherited) x")

    def test_collapses_whitespace_and_lowercases(self):
        self.assertEqual(_norm_title("  Data   Flow  "), "data flow")

    def test_plain_title_roundtrips(self):
        self.assertEqual(_norm_title("Overview"), "overview")


class CorrelateSectionsToTocTests(unittest.TestCase):
    def test_plain_titles_resolve(self):
        doc = _section("ov", "## Overview\ntext") + _section("comp", "## Components\nx")
        parsed = parse_sections(doc)
        toc = [(2, "Overview", "h-ov"), (2, "Components", "h-comp")]
        self.assertEqual(
            correlate_sections_to_toc(parsed.sections, toc),
            {"ov": "h-ov", "comp": "h-comp"},
        )

    def test_uses_first_heading_not_section_name(self):
        # Section name differs from heading; correlation must follow the heading.
        doc = _section(
            "component_profile_template_registry",
            "### Profile-template registry — `gates.yaml.j2`",
        )
        parsed = parse_sections(doc)
        toc = [(3, "Profile-template registry — gates.yaml.j2", "h-reg")]
        self.assertEqual(
            correlate_sections_to_toc(parsed.sections, toc),
            {"component_profile_template_registry": "h-reg"},
        )

    def test_inline_code_and_emphasis_heading_matches_deformatted_toc(self):
        # Textual de-formats inline markdown in TOC titles; the raw section
        # heading must still match.
        doc = _section("tool", "## Tooling — `scripts/gates.sh` *(new)*")
        parsed = parse_sections(doc)
        toc = [(2, "Tooling — scripts/gates.sh (new)", "h-tool")]
        self.assertEqual(
            correlate_sections_to_toc(parsed.sections, toc), {"tool": "h-tool"}
        )

    def test_duplicate_titles_resolve_by_position(self):
        # Two sections with the same heading must map to their own occurrence.
        doc = _section("a", "## Workflow\nfirst") + _section("b", "## Workflow\nsecond")
        parsed = parse_sections(doc)
        toc = [(2, "Workflow", "h-1"), (2, "Workflow", "h-2")]
        self.assertEqual(
            correlate_sections_to_toc(parsed.sections, toc),
            {"a": "h-1", "b": "h-2"},
        )

    def test_level_must_match(self):
        # A same-title TOC entry at a different level is not a match.
        doc = _section("a", "## Heading")
        parsed = parse_sections(doc)
        toc = [(3, "Heading", "h-deep")]
        self.assertEqual(correlate_sections_to_toc(parsed.sections, toc), {})

    def test_section_heading_absent_from_toc_is_omitted(self):
        doc = _section("x", "## Missing")
        parsed = parse_sections(doc)
        toc = [(2, "Other", "h-o")]
        self.assertEqual(correlate_sections_to_toc(parsed.sections, toc), {})

    def test_section_without_heading_is_skipped(self):
        doc = _section("nh", "just text, no heading") + _section("ov", "## Overview")
        parsed = parse_sections(doc)
        toc = [(2, "Overview", "h-ov")]
        self.assertEqual(
            correlate_sections_to_toc(parsed.sections, toc), {"ov": "h-ov"}
        )

    def test_intervening_subsection_headings_do_not_break_monotonic_walk(self):
        # Deeper headings between two parsed sections (swallowed-nesting case)
        # are stepped over by the monotonic pointer.
        doc = _section("comp", "## Components") + _section("conf", "## Conflicts")
        parsed = parse_sections(doc)
        toc = [
            (2, "Components", "h-comp"),
            (3, "Sub component", "h-sub"),  # swallowed nested heading
            (3, "Another sub", "h-sub2"),
            (2, "Conflicts", "h-conf"),
        ]
        self.assertEqual(
            correlate_sections_to_toc(parsed.sections, toc),
            {"comp": "h-comp", "conf": "h-conf"},
        )

    def test_empty_toc_yields_no_anchors(self):
        doc = _section("ov", "## Overview")
        parsed = parse_sections(doc)
        self.assertEqual(correlate_sections_to_toc(parsed.sections, []), {})

    def test_none_header_id_not_recorded_but_pointer_advances(self):
        # A matching entry with a falsy header_id is consumed (pointer advances)
        # but not recorded, so a later duplicate maps to its own real id.
        doc = _section("a", "## Workflow") + _section("b", "## Workflow")
        parsed = parse_sections(doc)
        toc = [(2, "Workflow", ""), (2, "Workflow", "h-2")]
        self.assertEqual(
            correlate_sections_to_toc(parsed.sections, toc), {"b": "h-2"}
        )


def _build_long_proposal() -> str:
    """A multi-section proposal long enough to scroll in a small viewport.

    Includes an inline-code heading (``tooling``) so the de-format path is
    exercised end-to-end, and enough filler per section that deep sections sit
    well below the fold.
    """
    sections = [
        ("overview", "## Overview"),
        ("design", "## Design"),
        ("tooling", "## Tooling — `scripts/run.sh`"),
        ("risks", "## Risks"),
        ("rollout", "## Rollout"),
        ("appendix", "## Appendix"),
    ]
    filler = "\n".join(f"- point {i} with some descriptive text" for i in range(12))
    parts = []
    for name, heading in sections:
        parts.append(
            f"<!-- section: {name} -->\n{heading}\n\n{filler}\n<!-- /section: {name} -->"
        )
    return "\n\n".join(parts) + "\n"


class _Host(App):
    def compose(self) -> ComposeResult:
        yield Static("host")


class AutoScrollPilotTests(unittest.TestCase):
    """End-to-end Pilot tests for SectionViewerScreen auto-scroll-on-open.

    Regression coverage for the bug where opening a proposal from a dimension
    row did not scroll to the linked section (the old poll-timer never fired)
    and, once firing, landed off-target before layout settled.
    """

    DOC = _build_long_proposal()

    def _run(self, coro):
        return asyncio.run(coro)

    def _heading_top_offset(self, content: SectionAwareMarkdown, name: str):
        header_id = content._section_anchors.get(name)
        if not header_id:
            return None
        md = content.query_one("#section_md", Markdown)
        widget = md.query_one(f"#{header_id}")
        return widget.region.y - content.region.y

    async def _open(self, pilot, app, section_filter):
        app.push_screen(SectionViewerScreen(self.DOC, title="P", section_filter=section_filter))
        await pilot.pause()
        # Let the TOC arrive and the convergent re-scroll settle.
        for _ in range(14):
            await pilot.pause()
        return app.screen.query_one("#sv_content", SectionAwareMarkdown)

    def test_autoscroll_lands_on_deep_section(self):
        async def runner():
            app = _Host()
            async with app.run_test(size=(80, 18)) as pilot:
                content = await self._open(pilot, app, ["rollout"])
                self.assertTrue(content.toc_ready)
                self.assertGreater(content.scroll_offset.y, 0)  # actually scrolled
                off = self._heading_top_offset(content, "rollout")
                self.assertIsNotNone(off)
                self.assertLessEqual(abs(off), 3)  # heading pinned near the top
                self.assertIsNone(content._active_scroll_section)  # converged + cleared
        self._run(runner())

    def test_autoscroll_inline_code_heading(self):
        async def runner():
            app = _Host()
            async with app.run_test(size=(80, 18)) as pilot:
                content = await self._open(pilot, app, ["tooling"])
                off = self._heading_top_offset(content, "tooling")
                self.assertIsNotNone(off)
                self.assertLessEqual(abs(off), 3)
        self._run(runner())

    def test_no_filter_does_not_autoscroll(self):
        async def runner():
            app = _Host()
            async with app.run_test(size=(80, 18)) as pilot:
                content = await self._open(pilot, app, None)
                self.assertEqual(content.scroll_offset.y, 0)
        self._run(runner())

    def test_minimap_selection_scrolls_to_section(self):
        async def runner():
            app = _Host()
            async with app.run_test(size=(80, 18)) as pilot:
                content = await self._open(pilot, app, None)
                minimap = app.screen.query_one("#sv_minimap", SectionMinimap)
                minimap.post_message(SectionMinimap.SectionSelected("appendix"))
                for _ in range(8):
                    await pilot.pause()
                off = self._heading_top_offset(content, "appendix")
                self.assertIsNotNone(off)
                self.assertLessEqual(abs(off), 3)
        self._run(runner())


if __name__ == "__main__":
    unittest.main()
