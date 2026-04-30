"""Unit tests for brainstorm_schemas dimension helpers (t721)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

from brainstorm.brainstorm_schemas import (  # noqa: E402
    DIMENSION_PREFIXES,
    PREFIX_TO_LABEL,
    group_dimensions_by_prefix,
)


class GroupDimensionsTests(unittest.TestCase):
    def test_groups_in_prefix_order_and_strips_prefix(self):
        dims = {
            "tradeoff_cost": "low",
            "requirements_perf": "fast",
            "assumption_concurrency": "single",
            "component_storage": "sqlite",
            "requirements_security": "tls",
        }
        out = group_dimensions_by_prefix(dims)
        labels = [g[1] for g in out]
        self.assertEqual(
            labels, ["Requirements", "Assumptions", "Components", "Tradeoffs"]
        )
        # Each prefix shows up in canonical DIMENSION_PREFIXES order regardless
        # of dict insertion order.
        prefixes = [g[0] for g in out]
        self.assertEqual(prefixes, list(DIMENSION_PREFIXES))

        req_entries = out[0][2]
        self.assertEqual(
            sorted(req_entries),
            sorted([
                ("perf", "fast", "requirements_perf"),
                ("security", "tls", "requirements_security"),
            ]),
        )

    def test_single_entry_groups(self):
        out = group_dimensions_by_prefix({"requirements_x": "y"})
        self.assertEqual([g[0] for g in out], ["requirements_"])
        self.assertEqual(out[0][1], "Requirements")
        self.assertEqual(out[0][2], [("x", "y", "requirements_x")])

    def test_empty_input_returns_empty_list(self):
        self.assertEqual(group_dimensions_by_prefix({}), [])

    def test_unknown_prefix_dropped(self):
        # extract_dimensions guarantees only known prefixes, but be defensive.
        out = group_dimensions_by_prefix({"weird_x": 1, "requirements_a": 2})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0], "requirements_")
        self.assertEqual(out[0][2][0], ("a", 2, "requirements_a"))

    def test_prefix_to_label_covers_every_known_prefix(self):
        for prefix in DIMENSION_PREFIXES:
            self.assertIn(prefix, PREFIX_TO_LABEL)


if __name__ == "__main__":
    unittest.main()
