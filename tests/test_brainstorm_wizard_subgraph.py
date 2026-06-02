"""Tests for the wizard subgraph node-filter helper (t756_2).

``_nodes_for_subgraph`` keeps only the nodes whose ``module_label`` matches the
selected subgraph (unlabeled/legacy nodes resolve to ``_umbrella``). Pure over a
node list — verified without a running Textual App.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from brainstorm.brainstorm_app import _nodes_for_subgraph  # noqa: E402
from brainstorm.brainstorm_dag import (  # noqa: E402
    NODES_DIR,
    PROPOSALS_DIR,
    UMBRELLA_SUBGRAPH,
    create_node,
    list_nodes,
)


class NodesForSubgraphTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.wt = Path(self._td.name)
        (self.wt / NODES_DIR).mkdir(parents=True, exist_ok=True)
        (self.wt / PROPOSALS_DIR).mkdir(parents=True, exist_ok=True)
        # Two unlabeled (_umbrella) nodes, two parser nodes, one cache node.
        create_node(self.wt, "n000_init", [], "init", {}, "# init", "")
        create_node(self.wt, "n001_u", ["n000_init"], "u", {}, "# u", "")
        create_node(
            self.wt, "n010_p", ["n000_init"], "p", {}, "# p", "",
            module_label="parser",
        )
        create_node(
            self.wt, "n011_p", ["n010_p"], "p2", {}, "# p2", "",
            module_label="parser",
        )
        create_node(
            self.wt, "n014_c", ["n000_init"], "c", {}, "# c", "",
            module_label="cache",
        )

    def tearDown(self):
        self._td.cleanup()

    def test_filters_to_named_subgraph(self):
        nodes = list_nodes(self.wt)
        self.assertEqual(
            _nodes_for_subgraph(self.wt, nodes, "parser"), ["n010_p", "n011_p"]
        )
        self.assertEqual(_nodes_for_subgraph(self.wt, nodes, "cache"), ["n014_c"])

    def test_umbrella_keeps_unlabeled_nodes(self):
        nodes = list_nodes(self.wt)
        self.assertEqual(
            _nodes_for_subgraph(self.wt, nodes, UMBRELLA_SUBGRAPH),
            ["n000_init", "n001_u"],
        )

    def test_order_preserved(self):
        nodes = ["n014_c", "n010_p", "n011_p"]
        self.assertEqual(
            _nodes_for_subgraph(self.wt, nodes, "parser"), ["n010_p", "n011_p"]
        )


if __name__ == "__main__":
    unittest.main()
