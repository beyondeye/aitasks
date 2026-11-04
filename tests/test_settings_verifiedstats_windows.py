"""Settings TUI verified-stats readers (t2194).

- `_aggregate_verifiedstats` resolves each provider's buckets against "today"
  before summing them, so a stale or not-yet-rolled-over bucket never counts as
  this month (the old first-seen-period grouping dropped a provider instead).
- The Agent Defaults labels look `batch-review` up under `review`, the name
  aitask-review records with, and `review` is then not listed again among the
  "skills without defaults".

Run: python3 -m pytest tests/test_settings_verifiedstats_windows.py -v
"""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "settings"))

from agent_model_picker import _format_op_stats  # noqa: E402
from settings_app import SettingsApp, _aggregate_verifiedstats  # noqa: E402

TODAY = date(2026, 11, 4)


def _v(period: str, runs: int, score_sum: int) -> dict:
    return {"period": period, "runs": runs, "score_sum": score_sum}


AGG_MODELS = {
    "codex": {"models": [{
        "name": "gpt5_3codex", "cli_id": "gpt-5.3-codex",
        "verifiedstats": {
            "pick": {   # months old
                "all_time": {"runs": 3, "score_sum": 240},
                "month": _v("2026-07", 2, 160),
                "week": _v("2026-W30", 1, 80),
            },
            "explore": {   # last month, not rolled over yet
                "all_time": {"runs": 2, "score_sum": 200},
                "month": _v("2026-10", 2, 200),
            },
        },
    }]},
    "opencode": {"models": [{
        "name": "openai_gpt_5_3_codex", "cli_id": "openai/gpt-5.3-codex",
        "verifiedstats": {
            "pick": {
                "all_time": {"runs": 2, "score_sum": 200},
                "month": _v("2026-11", 1, 100),
                "prev_month": _v("2026-10", 1, 100),
                "week": _v("2026-W45", 1, 100),
            },
            "explore": {
                "all_time": {"runs": 1, "score_sum": 100},
                "month": _v("2026-11", 1, 100),
            },
        },
    }]},
}


class AggregateVerifiedstatsTests(unittest.TestCase):
    def test_stale_provider_buckets_are_not_this_month(self):
        agg = _aggregate_verifiedstats(AGG_MODELS, "gpt-5.3-codex", today=TODAY)["pick"]
        self.assertEqual(agg["all_time"], {"runs": 5, "score_sum": 440})
        self.assertEqual(agg["month"], {"period": "2026-11", "runs": 1, "score_sum": 100})
        self.assertEqual(agg["prev_month"], {"period": "2026-10", "runs": 1, "score_sum": 100})
        self.assertEqual(agg["week"], {"period": "2026-W45", "runs": 1, "score_sum": 100})

    def test_providers_in_different_months_both_count(self):
        agg = _aggregate_verifiedstats(AGG_MODELS, "gpt-5.3-codex", today=TODAY)["explore"]
        self.assertEqual(agg["month"]["runs"], 1)       # opencode, 2026-11
        self.assertEqual(agg["prev_month"]["runs"], 2)  # codex, unrolled 2026-10
        self.assertEqual(_format_op_stats(agg, compact=True, today=TODAY),
                         "100 (3 runs, 1 this mo, 2 prev mo)")


def _fake_self(models: dict, project_defaults: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(config_mgr=SimpleNamespace(
        models=models,
        codeagent_project={"defaults": project_defaults or {}},
        codeagent_local={"defaults": {}},
    ))


# Months-old buckets: no window counts them, whatever the wall-clock date.
REVIEW_MODELS = {
    "claudecode": {"models": [
        {"name": "rev", "cli_id": "claude-x", "verifiedstats": {
            "review": {"all_time": {"runs": 2, "score_sum": 180},
                       "month": _v("2020-01", 2, 180)},
            "fold": {"all_time": {"runs": 1, "score_sum": 60},
                     "month": _v("2020-01", 1, 60)},
        }},
        {"name": "flat", "cli_id": "claude-y", "verified": {"review": 70}},
    ]},
    "opencode": {"models": [
        {"name": "rev_oc", "cli_id": "anthropic/claude-x", "verifiedstats": {
            "review": {"all_time": {"runs": 1, "score_sum": 100}},
        }},
    ]},
}


class BatchReviewKeyTests(unittest.TestCase):
    def test_verified_label_reads_review_counters(self):
        fake = _fake_self(REVIEW_MODELS)
        self.assertEqual(
            SettingsApp._get_verified_label(fake, "batch-review", "claudecode/rev"),
            " [dim][90 (2 runs)][/dim]",
        )
        self.assertEqual(
            SettingsApp._get_verified_label(fake, "batch-review", "claudecode/flat"),
            " [dim][score: 70][/dim]",
        )
        self.assertEqual(SettingsApp._get_verified_label(fake, "pick", "claudecode/rev"), "")

    def test_all_providers_label_reads_review_counters(self):
        fake = _fake_self(REVIEW_MODELS)
        self.assertEqual(
            SettingsApp._get_all_providers_label(fake, "batch-review", "claudecode/rev"),
            " [dim]all providers: 93 (3 runs)[/dim]",
        )

    def test_review_is_not_listed_as_a_skill_without_defaults(self):
        fake = _fake_self(REVIEW_MODELS, project_defaults={"batch-review": "claudecode/rev"})
        stats = SettingsApp._collect_non_default_skill_stats(fake)
        self.assertEqual(sorted(stats), ["fold"])


if __name__ == "__main__":
    unittest.main()
