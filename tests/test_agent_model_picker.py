"""Tests for agent model picker ranking behavior.

Run: python3 -m pytest tests/test_agent_model_picker.py -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from agent_model_picker import AgentModelPickerScreen  # noqa: E402


class TopVerifiedRecentRankingTests(unittest.TestCase):
    def test_recent_verified_models_rank_above_no_recent_fallback_scores(self):
        all_models = {
            "claudecode": {
                "models": [
                    {
                        "name": "old_high",
                        "verified": {"pick": 100},
                        "verifiedstats": {
                            "pick": {
                                "all_time": {"runs": 10, "score_sum": 1000},
                                "month": {"runs": 0, "score_sum": 0},
                                "prev_month": {"runs": 0, "score_sum": 0},
                            }
                        },
                    },
                    {
                        "name": "recent_lower",
                        "verified": {"pick": 80},
                        "verifiedstats": {
                            "pick": {
                                "all_time": {"runs": 2, "score_sum": 160},
                                "month": {"runs": 2, "score_sum": 160},
                                "prev_month": {"runs": 0, "score_sum": 0},
                            }
                        },
                    },
                ]
            }
        }

        options = AgentModelPickerScreen(
            "pick",
            all_models=all_models,
        )._build_options_top()

        values = [opt["value"] for opt in options]
        self.assertEqual(
            values,
            ["claudecode/recent_lower", "claudecode/old_high"],
        )
        self.assertEqual(options[0]["description"], "80 (2 runs recent)")
        self.assertEqual(
            options[1]["description"],
            "score: 100 (no recent data)",
        )


if __name__ == "__main__":
    unittest.main()
