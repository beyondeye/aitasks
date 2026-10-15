"""Tests for the compact elapsed counter on the agent status badge (t1996).

``format_pane_status`` renders ``PROMPT <t>`` / ``DONE <t>`` / ``IDLE <t>`` on
every monitor and minimonitor card. Before t1996 ``<t>`` was raw seconds with no
upper bound (``IDLE 18734s``), so the badge grew without limit and wrapped the
first line of a minimonitor card. ``format_elapsed_compact`` caps it at four
characters by switching units as it grows, always rounding down:

    0 – 999 s                 -> ``<n>s``   (``0s`` … ``999s``)
    whole minutes <= 240      -> ``<n>m``   (``16m`` … ``240m``)
    beyond that               -> ``<n>h``   (``4h`` … ``999h``, capped)

Colour is asserted through the ``STATE_STYLE_*`` constants, never as a literal —
the values are ratified in ``test_markup_colour_contract.py`` (t1453).

Run: python3 tests/test_monitor_elapsed_badge.py
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

from monitor.monitor_core import (  # noqa: E402
    PaneCategory, PaneSnapshot, TmuxPaneInfo,
)
from monitor.monitor_shared import (  # noqa: E402
    STATE_STYLE_DONE, STATE_STYLE_IDLE, STATE_STYLE_PROMPT,
    format_elapsed_compact, format_pane_status,
)

_COMPACT = re.compile(r"^\d+[smh]$")


def _snapshot(idle_seconds: float, *, awaiting=False, idle=True) -> PaneSnapshot:
    pane = TmuxPaneInfo(
        window_index="1", window_name="agent-pick-42", pane_index="0",
        pane_id="%1", pane_pid=1001, current_command="bash",
        width=80, height=24, category=PaneCategory.AGENT, session_name="demo",
    )
    return PaneSnapshot(
        pane=pane, content="x", timestamp=0.0,
        idle_seconds=idle_seconds, is_idle=idle,
        awaiting_input=awaiting,
        awaiting_input_kind="claude_proceed" if awaiting else "",
    )


class FormatElapsedCompactTests(unittest.TestCase):
    """The pure helper, at every unit boundary."""

    def test_boundaries(self):
        cases = [
            (0, "0s"),
            (-5, "0s"),
            (-0.5, "0s"),
            (999.9, "999s"),
            (1000, "16m"),
            (240 * 60 + 59, "240m"),
            (241 * 60, "4h"),
            (999 * 3600 + 3599, "999h"),
            (1500 * 3600, "999h"),
        ]
        for seconds, expected in cases:
            with self.subTest(seconds=seconds):
                self.assertEqual(format_elapsed_compact(seconds), expected)

    def test_rounds_down_within_each_unit(self):
        self.assertEqual(format_elapsed_compact(59.99), "59s")
        self.assertEqual(format_elapsed_compact(1079), "17m")   # 17m59s
        self.assertEqual(format_elapsed_compact(5 * 3600 - 1), "4h")

    def test_never_longer_than_four_characters(self):
        thresholds = (999, 1000, 240 * 60, 241 * 60, 999 * 3600, 1000 * 3600)
        values = {s + d for s in thresholds for d in range(-120, 121)}
        values.update(round(1.3 ** k) for k in range(0, 62))   # up to ~1e7 s
        values.update({0.0, 0.4, 999.999, 1e9})
        for seconds in sorted(values):
            out = format_elapsed_compact(seconds)
            with self.subTest(seconds=seconds, out=out):
                self.assertLessEqual(len(out), 4)
                self.assertRegex(out, _COMPACT)


class FormatPaneStatusCompactTests(unittest.TestCase):
    """The badge picks the compact form up in all three timed states."""

    def test_prompt_past_the_seconds_range(self):
        s = _snapshot(5000.0, awaiting=True)
        self.assertEqual(
            format_pane_status(s), f"[{STATE_STYLE_PROMPT}]PROMPT 83m[/]"
        )

    def test_done_past_the_minutes_range(self):
        s = _snapshot(241 * 60.0)
        self.assertEqual(
            format_pane_status(s, True), f"[{STATE_STYLE_DONE}]DONE 4h[/]"
        )

    def test_idle_at_the_seconds_ceiling(self):
        s = _snapshot(999.0)
        self.assertEqual(
            format_pane_status(s), f"[{STATE_STYLE_IDLE}]IDLE 999s[/]"
        )

    def test_large_value_is_no_longer_printed_in_seconds(self):
        """Negative control: the unbounded pre-t1996 form must be gone."""
        out = format_pane_status(_snapshot(18734.0))
        self.assertNotIn("18734", out)
        self.assertEqual(out, f"[{STATE_STYLE_IDLE}]IDLE 5h[/]")

    def test_badge_text_is_bounded(self):
        """The longest badge is ``PROMPT`` plus a four-character counter."""
        for seconds in (999.0, 240 * 60.0, 1e9):
            s = _snapshot(seconds, awaiting=True)
            plain = re.sub(r"\[[^\]]*\]", "", format_pane_status(s))
            with self.subTest(seconds=seconds, plain=plain):
                self.assertLessEqual(len(plain), len("PROMPT 999s"))


if __name__ == "__main__":
    unittest.main()
