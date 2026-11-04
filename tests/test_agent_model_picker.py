"""Tests for the agent model picker's ranked lists (t2194).

The two top lists rank by recorded usage in the date-correct recent window
(current + previous calendar month as of a pinned "today"):
  - top_all_ops — summed across every recorded op;
  - top_usage   — this op only (batch-review reads the `review` counters).

Run: python3 -m pytest tests/test_agent_model_picker.py -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_model_picker  # noqa: E402
from agent_model_picker import (  # noqa: E402
    AgentModelPickerScreen,
    FuzzySelect,
    _format_op_stats,
)

TODAY = date(2026, 11, 4)  # month 2026-11, previous month 2026-10


def _u(period: str, runs: int) -> dict:
    return {"period": period, "runs": runs}


ALL_MODELS = {
    "claudecode": {
        "models": [
            {   # opus4_8's real shape on 2026-11-04: big but months-old buckets.
                "name": "stale",
                "usagestats": {"pick": {
                    "all_time": {"runs": 303},
                    "month": _u("2026-07", 47),
                    "prev_month": _u("2026-06", 220),
                    "week": _u("2026-W30", 27),
                }},
            },
            {   # used a little across three ops: 2 + 3 + 2 = 7 recent.
                "name": "spread",
                "usagestats": {
                    "pick": {"all_time": {"runs": 2}, "month": _u("2026-11", 2)},
                    "explore": {"all_time": {"runs": 3}, "month": _u("2026-11", 3)},
                    # month slot not rolled over yet: last month's data.
                    "wrap": {"all_time": {"runs": 2}, "month": _u("2026-10", 2)},
                },
            },
            {   # used heavily in one op: 6 recent.
                "name": "heavy",
                "usagestats": {"pick": {
                    "all_time": {"runs": 9}, "month": _u("2026-11", 6),
                    "prev_month": _u("2026-09", 3),
                }},
            },
            {   # last month's data still in the `month` slot: 5 recent.
                "name": "unrolled",
                "usagestats": {"pick": {
                    "all_time": {"runs": 9}, "month": _u("2026-10", 5),
                    "prev_month": _u("2026-09", 4),
                }},
            },
            {   # recorded by aitask-review under `review`.
                "name": "reviewer",
                "usagestats": {"review": {
                    "all_time": {"runs": 4}, "month": _u("2026-11", 4),
                }},
            },
            {
                "name": "tiny",
                "usagestats": {"explore": {
                    "all_time": {"runs": 1}, "month": _u("2026-11", 1),
                }},
            },
            {
                "name": "gone",
                "status": "unavailable",
                "usagestats": {"pick": {
                    "all_time": {"runs": 50}, "month": _u("2026-11", 50),
                }},
            },
        ]
    },
    "codex": {
        "models": [
            {
                "name": "gpt",
                "usagestats": {"explore": {
                    "all_time": {"runs": 1}, "month": _u("2026-11", 1),
                }},
            },
        ]
    },
}


def _screen(op: str) -> AgentModelPickerScreen:
    return AgentModelPickerScreen(op, all_models=ALL_MODELS, today=TODAY)


def _values(options: list[dict]) -> list[str]:
    return [o["value"] for o in options]


class ModesTests(unittest.TestCase):
    def test_mode_order(self):
        self.assertEqual(
            [k for k, _ in AgentModelPickerScreen._MODES],
            ["top_all_ops", "top_usage", "all", "codex", "opencode", "claudecode"],
        )
        labels = dict(AgentModelPickerScreen._MODES)
        self.assertEqual(labels["top_all_ops"], "Top used models (recent, all ops)")
        self.assertEqual(labels["top_usage"], "Top by usage (recent, this op)")


class TopAllOpsTests(unittest.TestCase):
    def test_ranks_by_recent_usage_summed_across_ops(self):
        options = _screen("pick")._build_options_top_all_ops()
        # spread (7 over three ops) outranks heavy (6 in one op); the stale
        # model's 267 months-old runs and the unavailable model never appear;
        # capped at 5 with ties broken by agent then name (tiny before codex/gpt).
        self.assertEqual(_values(options), [
            "claudecode/spread", "claudecode/heavy", "claudecode/unrolled",
            "claudecode/reviewer", "claudecode/tiny",
        ])
        details = {o["value"]: o["description"] for o in options}
        self.assertEqual(details["claudecode/spread"], "7 runs recent, all ops · 2 this op")
        self.assertEqual(details["claudecode/heavy"], "6 runs recent, all ops · 6 this op")
        self.assertEqual(details["claudecode/unrolled"], "5 runs recent, all ops · 5 this op")
        self.assertEqual(details["claudecode/reviewer"], "4 runs recent, all ops")

    def test_populated_for_ops_that_record_no_usage_of_their_own(self):
        for op in ("raw", "shadow", "discuss"):
            options = _screen(op)._build_options_top_all_ops()
            self.assertEqual(options[0]["value"], "claudecode/spread", op)
            self.assertEqual(options[0]["description"], "7 runs recent, all ops", op)

    def test_empty_when_nothing_is_recent(self):
        screen = AgentModelPickerScreen(
            "pick", all_models={"claudecode": {"models": [ALL_MODELS["claudecode"]["models"][0]]}},
            today=TODAY,
        )
        self.assertEqual(screen._build_options_top_all_ops(), [
            {"value": "", "display": "(no recent usage)", "description": ""},
        ])


class TopUsageThisOpTests(unittest.TestCase):
    def test_ranks_this_op_only(self):
        options = _screen("pick")._build_options_top_usage()
        # The order flips against the all-ops list: heavy (6) over spread (2).
        self.assertEqual(_values(options), [
            "claudecode/heavy", "claudecode/unrolled", "claudecode/spread",
        ])
        details = {o["value"]: o["description"] for o in options}
        self.assertEqual(details["claudecode/heavy"], "6 runs recent · 9 all-time")
        self.assertEqual(details["claudecode/unrolled"], "5 runs recent · 9 all-time")
        self.assertEqual(details["claudecode/spread"], "2 runs recent")

    def test_op_without_recorded_usage_shows_short_placeholder(self):
        self.assertEqual(_screen("raw")._build_options_top_usage(), [
            {"value": "", "display": "(no recent usage for this op)", "description": ""},
        ])

    def test_batch_review_reads_the_review_counters(self):
        options = _screen("batch-review")._build_options_top_usage()
        self.assertEqual(_values(options), ["claudecode/reviewer"])
        # all-time (4) == recent (4), so no "· N all-time" suffix.
        self.assertEqual(options[0]["description"], "4 runs recent")
        all_ops = {o["value"]: o["description"]
                   for o in _screen("batch-review")._build_options_top_all_ops()}
        self.assertEqual(all_ops["claudecode/reviewer"], "4 runs recent, all ops · 4 this op")


class SelectionTests(unittest.TestCase):
    def _select(self, screen: AgentModelPickerScreen, mode_idx: int, value: str):
        captured: list = []
        screen.dismiss = captured.append  # type: ignore[method-assign]
        screen._mode_idx = mode_idx
        screen.on_fuzzy_select_selected(FuzzySelect.Selected(value))
        return captured

    def test_top_lists_dismiss_with_the_operation_key(self):
        for idx in (0, 1):
            got = self._select(_screen("batch-review"), idx, "claudecode/reviewer")
            self.assertEqual(got, [{"key": "batch-review", "value": "claudecode/reviewer"}])

    def test_per_agent_list_prefixes_the_agent(self):
        got = self._select(_screen("pick"), 5, "heavy")  # claudecode mode
        self.assertEqual(got, [{"key": "pick", "value": "claudecode/heavy"}])

    def test_placeholder_row_selects_nothing(self):
        self.assertEqual(self._select(_screen("raw"), 1, ""), [])


class PerAgentListTests(unittest.TestCase):
    def test_batch_review_shows_the_review_scores(self):
        models = {"models": [
            {"name": "plain", "verified": {"pick": 90}},
            {"name": "reviewer", "verifiedstats": {"review": {
                "all_time": {"runs": 2, "score_sum": 180},
                "month": {"period": "2026-11", "runs": 1, "score_sum": 100},
                "prev_month": {"period": "2026-10", "runs": 1, "score_sum": 80},
            }}},
        ]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "models_claudecode.json"
            path.write_text(json.dumps(models), encoding="utf-8")
            with mock.patch.dict(agent_model_picker.MODEL_FILES, {"claudecode": path}):
                options = _screen("batch-review")._build_options_for_agent("claudecode")
        self.assertEqual(_values(options), ["reviewer", "plain"])
        self.assertEqual(options[0]["description"], "[90 (2 runs, 1 this mo, 1 prev mo)]")
        self.assertEqual(options[1]["description"], "")


class FormatOpStatsTests(unittest.TestCase):
    def test_stale_month_is_not_this_month(self):
        buckets = {
            "all_time": {"runs": 9, "score_sum": 864},
            "month": {"period": "2026-07", "runs": 4, "score_sum": 400},
            "prev_month": {"period": "2026-06", "runs": 5, "score_sum": 464},
        }
        self.assertEqual(_format_op_stats(buckets, compact=True, today=TODAY), "96 (9 runs)")

    def test_unrolled_month_slot_shows_as_previous_month(self):
        buckets = {
            "all_time": {"runs": 9, "score_sum": 864},
            "month": {"period": "2026-10", "runs": 3, "score_sum": 300},
        }
        self.assertEqual(_format_op_stats(buckets, compact=True, today=TODAY),
                         "96 (9 runs, 3 prev mo)")
        self.assertEqual(_format_op_stats(buckets, compact=False, today=TODAY),
                         "96 (9 runs, 3 last month)")

    def test_current_month(self):
        buckets = {
            "all_time": {"runs": 9, "score_sum": 864},
            "month": {"period": "2026-11", "runs": 2, "score_sum": 200},
            "prev_month": {"period": "2026-10", "runs": 1, "score_sum": 100},
        }
        self.assertEqual(_format_op_stats(buckets, compact=False, today=TODAY),
                         "96 (9 runs, 2 this month, 1 last month)")


if __name__ == "__main__":
    unittest.main()
