"""Behavioural pins for the markup *structure* fixes (t1486).

Three sites shipped markup whose brackets Textual read as tags:

===========================================  ==================================
site                                         symptom
===========================================  ==================================
``board/aitask_board.py`` GitLab indicators  ``MarkupError`` — hard crash on the
                                             compositor path, for any task whose
                                             ``issue:`` URL is a GitLab host
``monitor/monitor_app.py`` session bar       ``[AUTO]`` eaten as an unknown tag,
                                             so the badge is invisible exactly
                                             when auto-switch is on
``logview/logview_app.py`` header            ``[live]`` / ``[raw]`` eaten, so
                                             the state indicators never render
===========================================  ==================================

Why this file exists separately from ``test_textual_markup_colours.py``. That
module's Rule C statically catches the board case — a closing tag matching no
open tag. It **cannot** catch the other two: ``[AUTO]`` is a *syntactically
valid* unknown tag, indistinguishable at parse time from an intentional dynamic
style, so the parser never objects. The only evidence is the rendered text, and
producing it means running the real widget. That boundary is stated in the Rule
C docstring and pinned by its ``test_gap_the_literal_bracket_class``.

Every markup assertion below reads **rendered plain text**, never
``render().spans``. A span happily holds an unresolved tag, which is precisely
how this defect class hides (the same trap t1453 documents for the colour tier).

``LogViewStartupFocusTests`` guards a different defect, found while writing the
logview pins: the hidden ``#search-box`` Input took startup focus and swallowed
every binding key. It lives here because the two are entangled — without that
fix the header pins could only reach ``[raw]`` by focusing the log themselves,
which would have meant asserting past a real bug instead of through it.

Run: python3 tests/test_textual_markup_structure.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

# As in test_monitor_refresh_no_sync_tmux.py: scrub the ambient tmux env so
# MonitorApp.on_mount takes the deterministic not-inside-tmux path wherever the
# suite runs.
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from textual.content import Content  # noqa: E402
from textual.widgets import Input, RichLog  # noqa: E402

from aitask_board import _issue_indicator, _pr_indicator  # noqa: E402
from logview.logview_app import LogViewApp  # noqa: E402
from monitor.monitor_app import MonitorApp  # noqa: E402

GITLAB_ISSUE = "https://gitlab.com/acme/widgets/-/issues/7"
GITLAB_MR = "https://gitlab.com/acme/widgets/-/merge_requests/7"


def _rendered(widget) -> str:
    """The plain text a widget's markup actually produces."""
    return Content.from_markup(str(widget.content)).plain


class BoardIndicatorMarkupTests(unittest.TestCase):
    """``_issue_indicator`` / ``_pr_indicator`` must produce parseable markup.

    The GitLab branches shipped ``[#e24329]GL[/e24329]`` — the closing tag drops
    the ``#``, so it names a tag that was never opened and Textual raises. Every
    branch is exercised, not just the broken one: the fix changes the closing
    tag, and a fix that broke a sibling branch would otherwise go unnoticed.
    """

    def _assert_renders(self, markup: str, expected: str) -> None:
        try:
            content = Content.from_markup(markup)
        except Exception as exc:  # pragma: no cover - the failure being pinned
            self.fail(f"{markup!r} does not parse: {type(exc).__name__}: {exc}")
        self.assertEqual(expected, content.plain)

    def test_every_issue_indicator_branch_parses(self):
        cases = {
            "https://github.com/acme/widgets/issues/7": "GH",
            GITLAB_ISSUE: "GL",
            "https://bitbucket.org/acme/widgets/issues/7": "BB",
            "https://example.invalid/tracker/7": "Issue",
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self._assert_renders(_issue_indicator(url), expected)

    def test_every_pr_indicator_branch_parses(self):
        cases = {
            "https://github.com/acme/widgets/pull/7": "PR:GH",
            GITLAB_MR: "MR:GL",
            "https://bitbucket.org/acme/widgets/pull-requests/7": "PR:BB",
            "https://example.invalid/pr/7": "PR",
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self._assert_renders(_pr_indicator(url), expected)

    def test_the_gitlab_indicators_keep_their_brand_colour(self):
        """The fix must not silently drop the style along with the bad tag."""
        for markup in (_issue_indicator(GITLAB_ISSUE), _pr_indicator(GITLAB_MR)):
            with self.subTest(markup=markup):
                spans = Content.from_markup(markup).spans
                self.assertEqual(
                    ["#e24329"], [str(span.style) for span in spans]
                )


class MonitorAutoBadgeTests(unittest.TestCase):
    """The session bar's ``[AUTO]`` badge must survive markup parsing.

    Driven through the real app rather than the literal: the badge is built
    inline in ``_rebuild_session_bar``, so a replica string would prove nothing
    about the call site. Harness shape follows
    ``test_monitor_refresh_no_sync_tmux.py``.
    """

    def test_the_auto_badge_is_visible_when_auto_switch_is_on(self):
        async def runner():
            app = MonitorApp(session="demo", project_root=REPO_ROOT)
            async with app.run_test(size=(120, 30)) as pilot:
                bar = app.query_one("#session-bar")
                self.assertNotIn(
                    "[AUTO]", _rendered(bar), "badge shown while auto-switch is off"
                )

                app.action_toggle_auto_switch()
                await pilot.pause()

                self.assertIn("[AUTO]", _rendered(bar))

        asyncio.run(runner())


class LogViewHeaderTests(unittest.TestCase):
    """The log viewer's header indicators must survive markup parsing.

    **The fixture must hold bytes.** ``action_toggle_raw`` does not update
    ``#header-info`` itself — it flips ``raw_mode``, rewinds ``_last_pos`` and
    delegates to ``_read_and_append``, which refreshes the header only on its
    last line and returns early when there is nothing to read. Over an empty
    file the header is therefore never rebuilt and ``[raw]`` could not appear
    even with the markup correct, so the test would pass or fail for reasons
    unrelated to the fix.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.log_path = Path(self._tmp.name) / "agent.log"
        self.log_path.write_text("hello from the agent\n", encoding="utf-8")
        self.addCleanup(self._tmp.cleanup)

    def test_live_raw_and_paused_indicators_render(self):
        async def runner():
            app = LogViewApp(self.log_path, tail=True)
            async with app.run_test(size=(120, 24)) as pilot:
                header = app.query_one("#header-info")
                self.assertIn("[live]", _rendered(header))
                # Escaped for the same reason, and it only survived unescaped
                # by accident before the fix.
                self.assertIn("[size:", _rendered(header))

                # No manual focus: the keys must work as a user would find
                # them. See LogViewStartupFocusTests for why that is not free.
                await pilot.press("r")
                await pilot.pause()
                self.assertTrue(app.raw_mode, "the r binding did not fire")
                self.assertIn("[raw]", _rendered(header))
                self.assertIn("[live]", _rendered(header))

                await pilot.press("p")
                await pilot.pause()
                self.assertTrue(app.paused, "the p binding did not fire")
                self.assertIn("[paused]", _rendered(header))

        asyncio.run(runner())

    def test_the_static_indicator_renders(self):
        """`tail` is constructor-only, so `[static]` needs its own app."""

        async def runner():
            app = LogViewApp(self.log_path, tail=False)
            async with app.run_test(size=(120, 24)):
                self.assertIn("[static]", _rendered(app.query_one("#header-info")))

        asyncio.run(runner())


class LogViewStartupFocusTests(unittest.TestCase):
    """Keys must reach their bindings from a cold start.

    Found while writing the header pins above, and a defect in its own right:
    Textual auto-focuses the first focusable widget, which here is the
    ``display: none`` ``#search-box`` Input. It then swallowed every letter, so
    ``q``/``p``/``r``/``g``/``G``/``/``/``n`` typed into an invisible field and
    the viewer looked frozen until the user happened to click the log.

    Kept separate from the markup pins because it is a separate failure — but
    kept here because they are entangled in practice: without the fix, the
    header tests can only reach ``[raw]`` by focusing the log themselves, and a
    test that arranges its own preconditions past a real bug is not measuring
    the user's path.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.log_path = Path(self._tmp.name) / "agent.log"
        self.log_path.write_text("hello from the agent\n", encoding="utf-8")
        self.addCleanup(self._tmp.cleanup)

    def test_the_log_holds_focus_on_startup(self):
        async def runner():
            app = LogViewApp(self.log_path, tail=True)
            async with app.run_test(size=(120, 24)):
                self.assertIsInstance(app.focused, RichLog)

        asyncio.run(runner())

    def test_the_log_holds_focus_even_when_the_file_is_missing(self):
        """`on_mount` returns early on a missing file — focus must precede it."""

        async def runner():
            app = LogViewApp(self.log_path.parent / "absent.log", tail=True)
            async with app.run_test(size=(120, 24)):
                self.assertIsInstance(app.focused, RichLog)

        asyncio.run(runner())

    def test_a_bare_letter_key_reaches_its_binding(self):
        """The user-visible symptom, asserted end to end."""

        async def runner():
            app = LogViewApp(self.log_path, tail=True)
            async with app.run_test(size=(120, 24)) as pilot:
                await pilot.press("p")
                await pilot.pause()
                self.assertTrue(app.paused, "the p binding never fired")
                self.assertEqual(
                    "", app.query_one("#search-box", Input).value,
                    "the keystroke was typed into the hidden search field",
                )

        asyncio.run(runner())


if __name__ == "__main__":
    unittest.main(verbosity=2)
