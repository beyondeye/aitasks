"""The log viewer's `/` box must DRAW its text, not merely receive it (t2014).

The shipped CSS gave the stock `Input` `height: 1`. Its 2-row `tall` border
filled that entirely, leaving a 0-row content area: keys still reached
`Input.value`, so a test reading `box.value` passed while the user saw an empty
two-line strip — no placeholder, no typed term. Same defect t2003 fixed in
frozenagent, whose CSS was copied from here; this pins it the same way, through
the rendered screen.

Run: python3 tests/test_logview_search_box.py
"""

from __future__ import annotations

import html
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

from textual.widgets import Input, RichLog  # noqa: E402

from logview.logview_app import LogViewApp  # noqa: E402


def _screen_text(app) -> str:
    """Everything currently drawn, as plain text (SVG tags stripped)."""
    svg = app.export_screenshot()
    return html.unescape(re.sub(r"<[^>]+>", "", svg)).replace("\xa0", " ")


class SearchBoxTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.log_path = Path(self._tmp.name) / "agent.log"
        self.log_path.write_text("alpha\nbravo\ncharlie\n", encoding="utf-8")

    async def test_slash_opens_a_box_whose_placeholder_and_text_are_drawn(self):
        # tail=False: no poll thread, the content is static.
        app = LogViewApp(self.log_path, tail=False)
        async with app.run_test(size=(100, 24)) as pilot:
            await pilot.press("slash")
            await pilot.pause()
            box = app.query_one("#search-box", Input)
            self.assertIs(app.focused, box)
            self.assertGreaterEqual(box.content_region.height, 1)
            self.assertIn("Search (Enter to confirm", _screen_text(app))

            # A term the log does not contain, so only the box can draw it.
            for ch in "qzx":
                await pilot.press(ch)
            await pilot.pause()
            self.assertIn("qzx", _screen_text(app))

            header = app.query_one("#header-info")
            log = app.query_one("#log", RichLog)
            self.assertGreaterEqual(box.region.y, header.region.bottom)
            self.assertGreaterEqual(log.region.y, box.region.bottom)
            self.assertGreaterEqual(log.region.height, 1)

            # The compact box still submits: Enter closes it and hands focus
            # back to the log.
            box.value = ""
            for ch in "charlie":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            self.assertFalse(box.has_class("visible"))
            self.assertIs(app.focused, log)
            self.assertEqual(app._search_term, "charlie")


if __name__ == "__main__":
    unittest.main(verbosity=2)
