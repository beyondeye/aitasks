"""Terminal-width tier tests for the shared narrow-terminal breakpoint (t1251).

t1247 flagged that the repo was accumulating uncentralized narrow-terminal
breakpoints. t1251 hoisted the two codebrowser tier literals into
``.aitask-scripts/lib/tui_layout.py`` and left every *component minimum width*
(``CODE_MIN_WIDTH``, ``FILTER_SEARCH_MIN_WIDTH``, ``_SENTINEL_SAFE_COLS``, …)
with its own widget. See ``aidocs/framework/tui_conventions.md``, section
"Terminal-width tiers vs component minimum widths".

Two layers:

1. **Unit** — ``terminal_tier`` / ``is_narrow_terminal`` boundary conditions.
2. **Behavioral** — each migrated call site is driven through the real widget /
   app, then ``tui_layout``'s module global is monkeypatched and the *same*
   input must produce the other tier's result. That is what proves the site
   reads the shared value rather than a local literal: a re-inlined ``80``
   would ignore the patch and the assertion would fail.

The behavioral layer also closes a real coverage gap. Every case in
``tests/test_code_viewer_render.py`` runs at exactly ``size=(80, 24)``, so
``is_narrow_terminal(80)`` is False there — the narrow arm of
``_annotation_col_width`` had never been executed by a test, and
``CodeBrowserApp.on_resize`` had no coverage at all.

Run: python3 -m pytest tests/test_tui_narrow_breakpoint.py -v
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "codebrowser"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from textual.app import App, ComposeResult  # noqa: E402

import tui_layout  # noqa: E402
from tui_layout import (  # noqa: E402
    NARROW,
    NORMAL,
    WIDE,
    is_narrow_terminal,
    terminal_tier,
)
from code_viewer import CodeViewer  # noqa: E402
from codebrowser_app import CodeBrowserApp  # noqa: E402


class _ViewerHostApp(App):
    """Minimal host that mounts a single CodeViewer.

    Mirrors ``_HostApp`` in tests/test_code_viewer_render.py.
    """

    def compose(self) -> ComposeResult:
        yield CodeViewer(id="viewer")


class _TierPatch:
    """Context manager that shifts the shared tier boundaries.

    Patching ``tui_layout``'s module globals (rather than a consumer's copy) is
    the whole point: ``terminal_tier`` resolves them at call time, so one patch
    reaches every call site that genuinely goes through the shared seam.
    """

    def __init__(self, narrow: int, wide: int) -> None:
        self._narrow = narrow
        self._wide = wide

    def __enter__(self):
        self._orig_narrow = tui_layout.NARROW_TERMINAL_WIDTH
        self._orig_wide = tui_layout.WIDE_TERMINAL_WIDTH
        tui_layout.NARROW_TERMINAL_WIDTH = self._narrow
        tui_layout.WIDE_TERMINAL_WIDTH = self._wide
        return self

    def __exit__(self, *exc):
        tui_layout.NARROW_TERMINAL_WIDTH = self._orig_narrow
        tui_layout.WIDE_TERMINAL_WIDTH = self._orig_wide
        return False


class TerminalTierUnitTests(unittest.TestCase):
    """Layer 1 — the tier function's boundary conditions."""

    def test_tier_boundaries(self):
        # The boundaries are inclusive-at-the-top: >= WIDE is wide, >= NARROW is
        # normal, below NARROW is narrow.
        self.assertEqual(terminal_tier(0), NARROW)
        self.assertEqual(terminal_tier(79), NARROW)
        self.assertEqual(terminal_tier(80), NORMAL)
        self.assertEqual(terminal_tier(119), NORMAL)
        self.assertEqual(terminal_tier(120), WIDE)
        self.assertEqual(terminal_tier(500), WIDE)

    def test_boundaries_sit_on_the_named_constants(self):
        narrow = tui_layout.NARROW_TERMINAL_WIDTH
        wide = tui_layout.WIDE_TERMINAL_WIDTH
        self.assertEqual(terminal_tier(narrow - 1), NARROW)
        self.assertEqual(terminal_tier(narrow), NORMAL)
        self.assertEqual(terminal_tier(wide - 1), NORMAL)
        self.assertEqual(terminal_tier(wide), WIDE)

    def test_is_narrow_terminal_agrees_with_terminal_tier(self):
        for width in (0, 1, 40, 79, 80, 81, 119, 120, 200):
            self.assertEqual(
                is_narrow_terminal(width),
                terminal_tier(width) == NARROW,
                f"disagreement at width={width}",
            )

    def test_tier_functions_follow_the_shared_constant(self):
        # Sanity-check the patch mechanism the behavioral tests rely on.
        self.assertFalse(is_narrow_terminal(100))
        with _TierPatch(narrow=200, wide=300):
            self.assertTrue(is_narrow_terminal(100))
            self.assertEqual(terminal_tier(100), NARROW)
        self.assertFalse(is_narrow_terminal(100))


class CodeViewerAnnotationWidthTests(unittest.TestCase):
    """Layer 2a — CodeViewer._annotation_col_width reads the shared tier."""

    def _gutter_width_at(self, width: int) -> int:
        async def runner():
            app = _ViewerHostApp()
            async with app.run_test(size=(width, 24)) as pilot:
                await pilot.pause()
                viewer = app.query_one(CodeViewer)
                return viewer._annotation_col_width()

        return asyncio.run(runner())

    def test_wide_terminal_uses_the_full_gutter(self):
        self.assertEqual(
            self._gutter_width_at(100), CodeViewer.ANNOTATION_COL_WIDTH
        )

    def test_narrow_terminal_uses_the_narrow_gutter(self):
        # Never exercised before t1251: test_code_viewer_render.py runs
        # everything at exactly 80 columns, which is NOT narrow.
        self.assertEqual(
            self._gutter_width_at(70), CodeViewer.ANNOTATION_COL_WIDTH_NARROW
        )

    def test_gutter_follows_the_shared_breakpoint(self):
        """A re-inlined `app_width < 80` would ignore this patch and fail."""
        with _TierPatch(narrow=200, wide=300):
            observed = self._gutter_width_at(100)
        self.assertEqual(observed, CodeViewer.ANNOTATION_COL_WIDTH_NARROW)
        # Explicit discrimination: 100 columns is the *wide* result unpatched,
        # so an assertion that merely accepted the default would pass here.
        self.assertNotEqual(observed, CodeViewer.ANNOTATION_COL_WIDTH)


class CodeBrowserSidebarWidthTests(unittest.TestCase):
    """Layer 2b — CodeBrowserApp.on_resize reads the shared tier."""

    def _sidebar_width_at(self, width: int) -> int:
        async def runner():
            app = CodeBrowserApp()
            async with app.run_test(size=(width, 40)) as pilot:
                await pilot.pause()
                sidebar = app.query_one("#left_sidebar")
                return int(sidebar.styles.width.value)

        return asyncio.run(runner())

    def test_each_tier_gets_its_own_sidebar_width(self):
        by_tier = CodeBrowserApp.SIDEBAR_WIDTH_BY_TIER
        self.assertEqual(self._sidebar_width_at(130), by_tier[WIDE])
        self.assertEqual(self._sidebar_width_at(100), by_tier[NORMAL])
        self.assertEqual(self._sidebar_width_at(70), by_tier[NARROW])

    def test_per_tier_widths_are_distinct(self):
        # A mapping that collapsed two tiers would make the test above pass
        # while the layout silently stopped adapting.
        widths = list(CodeBrowserApp.SIDEBAR_WIDTH_BY_TIER.values())
        self.assertEqual(len(widths), len(set(widths)))

    def test_sidebar_follows_the_shared_breakpoint(self):
        """A re-inlined `width >= 80` would ignore this patch and fail."""
        by_tier = CodeBrowserApp.SIDEBAR_WIDTH_BY_TIER
        with _TierPatch(narrow=200, wide=300):
            observed = self._sidebar_width_at(100)
        self.assertEqual(observed, by_tier[NARROW])
        self.assertNotEqual(observed, by_tier[NORMAL])


class SharedSeamTests(unittest.TestCase):
    """Both migrated sites resolve against the same module global."""

    def test_one_patch_moves_both_call_sites(self):
        async def viewer_gutter():
            app = _ViewerHostApp()
            async with app.run_test(size=(100, 24)) as pilot:
                await pilot.pause()
                return app.query_one(CodeViewer)._annotation_col_width()

        async def browser_sidebar():
            app = CodeBrowserApp()
            async with app.run_test(size=(100, 40)) as pilot:
                await pilot.pause()
                return int(app.query_one("#left_sidebar").styles.width.value)

        # Unpatched, 100 columns is NORMAL for both.
        self.assertEqual(asyncio.run(viewer_gutter()), CodeViewer.ANNOTATION_COL_WIDTH)
        self.assertEqual(
            asyncio.run(browser_sidebar()),
            CodeBrowserApp.SIDEBAR_WIDTH_BY_TIER[NORMAL],
        )

        # A single edit to the shared module moves both — which is the property
        # centralization was for.
        with _TierPatch(narrow=200, wide=300):
            self.assertEqual(
                asyncio.run(viewer_gutter()),
                CodeViewer.ANNOTATION_COL_WIDTH_NARROW,
            )
            self.assertEqual(
                asyncio.run(browser_sidebar()),
                CodeBrowserApp.SIDEBAR_WIDTH_BY_TIER[NARROW],
            )

    def test_component_minimums_are_not_the_tier_constant(self):
        """CODE_MIN_WIDTH == 80 is a coincidence, not a derivation (t1251).

        If someone "cleans up" by pointing CODE_MIN_WIDTH at the tier constant,
        a UX retune of the narrow breakpoint would silently resize the code
        pane. Pin the two as independent values.
        """
        with _TierPatch(narrow=200, wide=300):
            self.assertEqual(CodeBrowserApp.CODE_MIN_WIDTH, 80)
            self.assertNotEqual(
                CodeBrowserApp.CODE_MIN_WIDTH, tui_layout.NARROW_TERMINAL_WIDTH
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
