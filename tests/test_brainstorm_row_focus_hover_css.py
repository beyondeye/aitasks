"""Regression coverage for brainstorm row focus+hover styling (t1038)."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

from brainstorm.styles import APP_CSS  # noqa: E402
from brainstorm.widgets import DimensionRow  # noqa: E402


def _selector_body(css: str, selector: str) -> str:
    match = re.search(rf"{re.escape(selector)}\s*\{{(?P<body>[^}}]+)\}}", css)
    if not match:
        raise AssertionError(f"missing CSS selector: {selector}")
    return match.group("body")


class BrainstormRowFocusHoverCssTests(unittest.TestCase):
    def assert_focus_hover_accent(self, css: str, selector: str) -> None:
        body = _selector_body(css, f"{selector}:focus:hover")
        self.assertIn("background: $accent-lighten-1;", body)
        self.assertIn("color: $text;", body)

    def test_app_css_focus_hover_rows_stay_in_accent_family(self):
        for selector in (
            "GroupRow",
            "AgentStatusRow",
            "ProcessRow",
            "OperationRow",
            "NodeRow",
        ):
            with self.subTest(selector=selector):
                self.assert_focus_hover_accent(APP_CSS, selector)

    def test_dimension_row_focus_hover_stays_in_accent_family(self):
        self.assert_focus_hover_accent(DimensionRow.DEFAULT_CSS, "DimensionRow")


if __name__ == "__main__":
    unittest.main()
