"""Tests for brainstorm_dag.get_node_ancestors / is_safe_node_id (t1823_1)."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

from brainstorm.brainstorm_dag import (  # noqa: E402
    NODES_DIR,
    PROPOSALS_DIR,
    _node_module,
    create_node,
    get_node_ancestors,
    get_node_lineage,
    is_safe_node_id,
    read_node_safe,
)
from agentcrew.agentcrew_utils import write_yaml  # noqa: E402


class AncestorTestBase(unittest.TestCase):
    """A bare session dir (br_nodes/ + br_proposals/) inside a temp root."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="brainstorm_ancestors_"))
        self.session = self.tmpdir / "crews" / "crew-brainstorm-999"
        (self.session / NODES_DIR).mkdir(parents=True)
        (self.session / PROPOSALS_DIR).mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def node(self, node_id, parents, module_label=None):
        create_node(
            self.session, node_id, parents, node_id, {}, node_id,
            module_label=module_label,
        )

    def ids(self, node_id):
        return [a for a, _ in get_node_ancestors(self.session, node_id)]


class TestIsSafeNodeId(unittest.TestCase):

    def test_table(self):
        for value in (".", "..", "a/b", "a|b", "a,b", "a\nb", "", " ", "../x",
                      1, None, ["n1"], {"a": 1}):
            with self.subTest(value=value):
                self.assertFalse(is_safe_node_id(value))
        for value in ("n001_explorer", "n000_init", "a.b-c_d", "_umbrella"):
            with self.subTest(value=value):
                self.assertTrue(is_safe_node_id(value))


class TestGetNodeAncestors(AncestorTestBase):

    def test_multi_parent_synthesis_reports_both_branches(self):
        self.node("n000_root", [])
        self.node("n001_a", ["n000_root"])
        self.node("n002_a2", ["n001_a"])
        self.node("n003_b", ["n000_root"])
        self.node("n004_b2", ["n003_b"])
        self.node("n005_synth", ["n002_a2", "n004_b2"])

        self.assertEqual(
            get_node_ancestors(self.session, "n005_synth"),
            [("n002_a2", 1), ("n004_b2", 1), ("n001_a", 2), ("n003_b", 2),
             ("n000_root", 3)],
        )
        # Control: the first-parent lineage on the SAME fixture drops branch b.
        lineage = get_node_lineage(self.session, "n005_synth")
        self.assertNotIn("n004_b2", lineage)
        self.assertNotIn("n003_b", lineage)

    def test_crosses_module_boundaries(self):
        self.node("n000_root", [])
        self.node("n001_umb", ["n000_root"])
        self.node("n002_modroot", ["n001_umb"], module_label="mod")
        self.node("n003_modleaf", ["n002_modroot"], module_label="mod")

        self.assertEqual(
            self.ids("n003_modleaf"), ["n002_modroot", "n001_umb", "n000_root"]
        )
        self.assertEqual(_node_module(self.session, "n002_modroot"), "mod")
        self.assertEqual(_node_module(self.session, "n001_umb"), "_umbrella")
        # Control: the module-confined lineage stops at the subgraph root.
        self.assertEqual(
            get_node_lineage(self.session, "n003_modleaf", module="mod"),
            ["n002_modroot", "n003_modleaf"],
        )

    def test_diamond_reported_once_at_shortest_depth(self):
        self.node("n000_root", [])
        self.node("n001_long", ["n000_root"])
        self.node("n002_longer", ["n001_long"])
        self.node("n003_leaf", ["n002_longer", "n000_root"])

        result = get_node_ancestors(self.session, "n003_leaf")
        self.assertEqual([a for a, _ in result].count("n000_root"), 1)
        self.assertIn(("n000_root", 1), result)

    def test_cycle_terminates_and_start_node_excluded(self):
        write_yaml(str(self.session / NODES_DIR / "n001_x.yaml"),
                   {"node_id": "n001_x", "parents": ["n002_y"]})
        write_yaml(str(self.session / NODES_DIR / "n002_y.yaml"),
                   {"node_id": "n002_y", "parents": ["n001_x", "n002_y"]})

        self.assertEqual(get_node_ancestors(self.session, "n001_x"), [("n002_y", 1)])

    def test_missing_parent_yaml_is_reported_not_traversed(self):
        self.node("n001_leaf", ["n000_gone"])
        self.assertEqual(get_node_ancestors(self.session, "n001_leaf"), [("n000_gone", 1)])

    def test_malformed_parent_yaml_is_reported_not_traversed(self):
        self.node("n001_leaf", ["n000_broken"])
        (self.session / NODES_DIR / "n000_broken.yaml").write_text(
            "parents: [unclosed\n  : : bad", encoding="utf-8"
        )
        # Must not raise (a NameError here would mean yaml is not imported).
        self.assertEqual(get_node_ancestors(self.session, "n001_leaf"), [("n000_broken", 1)])
        self.assertIsNone(read_node_safe(self.session, "n000_broken"))

    def test_non_list_parents_and_unknown_start(self):
        write_yaml(str(self.session / NODES_DIR / "n001_odd.yaml"),
                   {"node_id": "n001_odd", "parents": "n000_root"})
        self.assertEqual(get_node_ancestors(self.session, "n001_odd"), [])
        self.assertEqual(get_node_ancestors(self.session, "n999_nope"), [])

    def test_unsafe_parent_is_never_read(self):
        # A valid YAML planted at the traversal target of "../outside/n9"
        # (relative to br_nodes/) whose parent is a canary. If the unsafe id
        # were ever read, "canary" would appear among the ancestors.
        outside = self.session / "outside"
        outside.mkdir()
        write_yaml(str(outside / "n9.yaml"), {"node_id": "n9", "parents": ["canary"]})
        self.node("canary", [])
        unsafe = "../outside/n9"
        self.assertTrue((self.session / NODES_DIR / f"{unsafe}.yaml").is_file())

        self.node("n001_leaf", [unsafe, "n000_ok"])
        self.node("n000_ok", [])

        result = get_node_ancestors(self.session, "n001_leaf")
        self.assertEqual(result, [(unsafe, 1), ("n000_ok", 1)])
        self.assertNotIn("canary", [a for a, _ in result])
        self.assertIsNone(read_node_safe(self.session, unsafe))

    def test_non_string_parents_reported_without_crash(self):
        write_yaml(str(self.session / NODES_DIR / "n001_leaf.yaml"),
                   {"node_id": "n001_leaf", "parents": [None, 7, ["x"], {"a": 1}]})
        result = get_node_ancestors(self.session, "n001_leaf")
        self.assertEqual(len(result), 4)
        self.assertTrue(all(depth == 1 for _, depth in result))


if __name__ == "__main__":
    unittest.main()
