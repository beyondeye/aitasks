"""Tests for model_stats_windows — the date-correct usagestats / verifiedstats
windows shared by the model picker, the settings TUI and stats_data (t2194).

Run: python3 -m pytest tests/test_model_stats_windows.py -v
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from model_stats_windows import (  # noqa: E402
    Periods,
    current_periods,
    recent_aggregate,
    resolve_windows,
    stats_key_for_operation,
)

TODAY = date(2026, 11, 4)  # ISO 2026-W45; previous month 2026-10


def _b(period: str, runs: int, score_sum: int = 0) -> dict:
    return {"period": period, "runs": runs, "score_sum": score_sum}


def _gnu_date() -> bool:
    if shutil.which("date") is None:
        return False
    return subprocess.run(
        ["date", "--version"], capture_output=True, check=False,
    ).returncode == 0


class CurrentPeriodsTests(unittest.TestCase):
    def test_mid_year(self):
        self.assertEqual(
            current_periods(TODAY), Periods("2026-11", "2026-10", "2026-W45"),
        )

    def test_january_previous_month_is_last_december(self):
        self.assertEqual(current_periods(date(2026, 1, 15)).prev_month, "2025-12")

    def test_iso_week_year_differs_from_calendar_year(self):
        # 2027-01-01 is a Friday in ISO week 53 of ISO year 2026.
        p = current_periods(date(2027, 1, 1))
        self.assertEqual(p.month, "2027-01")
        self.assertEqual(p.week, "2026-W53")

    @unittest.skipUnless(_gnu_date(), "GNU date not available")
    def test_week_matches_the_writers_date_format(self):
        """The writers stamp `date +%G-W%V`; the reader must produce the same."""
        for d in (TODAY, date(2026, 1, 15), date(2027, 1, 1), date(2026, 12, 28)):
            out = subprocess.run(
                ["date", "-d", d.isoformat(), "+%G-W%V"],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
            self.assertEqual(current_periods(d).week, out, d)


class ResolveWindowsTests(unittest.TestCase):
    def test_current_month_and_week_count(self):
        w = resolve_windows({
            "month": _b("2026-11", 3, 300),
            "prev_month": _b("2026-10", 5, 400),
            "week": _b("2026-W45", 2, 200),
        }, TODAY)
        self.assertEqual((w["month"]["runs"], w["month"]["score_sum"]), (3, 300))
        self.assertEqual((w["prev_month"]["runs"], w["prev_month"]["score_sum"]), (5, 400))
        self.assertEqual((w["week"]["runs"], w["week"]["score_sum"]), (2, 200))
        self.assertEqual((w["recent"]["runs"], w["recent"]["score_sum"]), (8, 700))

    def test_unrolled_month_slot_from_last_month_counts_as_prev_month(self):
        w = resolve_windows({
            "month": _b("2026-10", 6, 600),
            "prev_month": _b("2026-09", 9, 900),
            "week": _b("2026-W44", 1, 100),
        }, TODAY)
        self.assertEqual(w["month"]["runs"], 0)
        self.assertEqual(w["prev_month"]["runs"], 6)
        self.assertEqual(w["week"]["runs"], 0)
        self.assertEqual(w["recent"]["runs"], 6)

    def test_stale_buckets_months_old_count_nowhere(self):
        """opus4_8's real shape on 2026-11-04: 2026-07 / 2026-06 buckets."""
        w = resolve_windows({
            "all_time": {"runs": 303},
            "month": _b("2026-07", 47),
            "prev_month": _b("2026-06", 220),
            "week": _b("2026-W30", 27),
        }, TODAY)
        for win in ("month", "prev_month", "week", "recent"):
            self.assertEqual(w[win]["runs"], 0, win)

    def test_missing_or_empty_period_is_not_recent(self):
        for bucket in ({"runs": 4}, _b("", 4), {"period": None, "runs": 4}):
            w = resolve_windows({"month": bucket, "prev_month": bucket, "week": bucket}, TODAY)
            self.assertEqual(w["recent"]["runs"], 0, bucket)
            self.assertEqual(w["week"]["runs"], 0, bucket)

    def test_non_dict_and_old_flat_format_contribute_nothing(self):
        for buckets in (None, [], "x", {"runs": 5, "score_sum": 400},
                        {"month": "2026-11", "week": 3}):
            w = resolve_windows(buckets, TODAY)
            self.assertEqual(w["recent"], {"runs": 0, "score_sum": 0}, buckets)

    def test_non_int_counts_are_ignored(self):
        w = resolve_windows({"month": {"period": "2026-11", "runs": True},
                             "prev_month": {"period": "2026-10", "runs": "3"}}, TODAY)
        self.assertEqual(w["recent"]["runs"], 0)

    def test_both_slots_claiming_previous_month_count_once(self):
        w = resolve_windows({
            "month": _b("2026-10", 4, 400),
            "prev_month": _b("2026-10", 7, 700),
        }, TODAY)
        self.assertEqual(w["prev_month"]["runs"], 7)  # the prev_month slot wins
        self.assertEqual(w["recent"]["runs"], 7)

    def test_resolved_windows_carry_current_periods_and_are_idempotent(self):
        once = resolve_windows({
            "month": _b("2026-10", 6, 600),
            "week": _b("2026-W45", 2, 200),
        }, TODAY)
        self.assertEqual(once["month"]["period"], "2026-11")
        self.assertEqual(once["prev_month"]["period"], "2026-10")
        self.assertEqual(once["week"]["period"], "2026-W45")
        self.assertEqual(resolve_windows(once, TODAY), once)

    def test_today_defaults_to_the_wall_clock(self):
        p = current_periods()
        w = resolve_windows({"month": _b(p.month, 2), "week": _b(p.week, 1)})
        self.assertEqual(w["month"]["runs"], 2)
        self.assertEqual(w["week"]["runs"], 1)


class RecentAggregateTests(unittest.TestCase):
    def test_sums_current_and_previous_month(self):
        self.assertEqual(
            recent_aggregate({"month": _b("2026-11", 16, 1600),
                              "prev_month": _b("2026-10", 276, 27600)}, TODAY),
            (292, 29200),
        )

    def test_stale_is_zero(self):
        self.assertEqual(
            recent_aggregate({"month": _b("2026-09", 158),
                              "prev_month": _b("2026-08", 198)}, TODAY),
            (0, 0),
        )


class StatsKeyTests(unittest.TestCase):
    def test_batch_review_reads_the_review_counters(self):
        self.assertEqual(stats_key_for_operation("batch-review"), "review")

    def test_every_other_operation_is_identity(self):
        for op in ("pick", "explain", "qa", "raw", "shadow", "brainstorm-explorer", "review"):
            self.assertEqual(stats_key_for_operation(op), op)


if __name__ == "__main__":
    unittest.main()
