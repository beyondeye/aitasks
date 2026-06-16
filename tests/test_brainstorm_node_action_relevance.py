"""Relevance-filter tests for the brainstorm Operations dialog (t925, t983_4).

Two layers:

- ``OpStatesForSelectionPureTests`` — the pure, headless
  ``op_states_for_selection(node_ctx, cardinality)`` decision (t983_4): the
  cardinality greying (single-node ops grey at N>1; compare/synthesize grey at
  N<2) plus the module-op preconditions, with NO Textual and NO session I/O.
  This is the testability centerpiece.
- ``NodeActionOpStatesTests`` — the thin I/O wrapper
  ``BrainstormApp._node_action_op_states`` over synthetic on-disk sessions with
  ``BrainstormApp.__init__`` bypassed (asserts the session reads map to the
  right ``node_ctx``); now called with an explicit ``cardinality``.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import yaml  # noqa: E402

from brainstorm.brainstorm_app import (  # noqa: E402
    BrainstormApp,
    op_states_for_selection,
)

_SINGLE = ("explore", "fast_track", "delete")
_MODULE = ("module_decompose", "module_merge", "module_sync")
_MULTI = ("compare", "synthesize")


class OpStatesForSelectionPureTests(unittest.TestCase):
    """Pure cardinality + precondition greying — no App, no I/O."""

    # A non-umbrella module node with an ancestor and a linked task: all module
    # preconditions satisfied, so at cardinality 1 only the multi-node ops grey.
    _FULL_CTX = {
        "is_umbrella": False,
        "has_ancestor": True,
        "has_linked_task": True,
    }

    def test_single_selection_enables_single_ops_greys_multi(self):
        states = op_states_for_selection(self._FULL_CTX, 1)
        for op in _SINGLE + _MODULE:
            self.assertFalse(states[op][0], f"{op} should be enabled at N=1")
        for op in _MULTI:
            self.assertTrue(states[op][0], f"{op} should grey at N=1")
            self.assertEqual(states[op][1], "mark 2+ nodes")

    def test_multi_selection_greys_single_ops_enables_multi(self):
        states = op_states_for_selection(self._FULL_CTX, 3)
        for op in _SINGLE + _MODULE:
            self.assertTrue(states[op][0], f"{op} should grey at N>1")
            self.assertEqual(states[op][1], "select a single node")
        for op in _MULTI:
            self.assertFalse(states[op][0], f"{op} should enable at N>1")

    def test_module_preconditions_apply_at_single_selection(self):
        # Empty ctx: not umbrella, no ancestor, no linked task.
        states = op_states_for_selection(
            {"is_umbrella": False, "has_ancestor": False,
             "has_linked_task": False},
            1,
        )
        self.assertFalse(states["module_decompose"][0])
        self.assertTrue(states["module_merge"][0])
        self.assertIn("no ancestor subgraph", states["module_merge"][1])
        self.assertTrue(states["module_sync"][0])
        self.assertIn("no linked task", states["module_sync"][1])

    def test_umbrella_root_greys_all_module_ops_at_single(self):
        states = op_states_for_selection(
            {"is_umbrella": True, "has_ancestor": False,
             "has_linked_task": False},
            1,
        )
        for op in _MODULE:
            self.assertTrue(states[op][0])
            self.assertIn("root design", states[op][1])

    def test_root_greys_delete_at_single_selection(self):
        states = op_states_for_selection(
            {"is_root": True, "is_umbrella": True, "has_ancestor": False,
             "has_linked_task": False},
            1,
        )
        self.assertTrue(states["delete"][0])
        self.assertIn("root design", states["delete"][1])

    def test_cardinality_reason_wins_over_precondition(self):
        # Umbrella (precondition would say "root design") but N>1 → the
        # cardinality reason takes precedence.
        states = op_states_for_selection(
            {"is_root": True, "is_umbrella": True, "has_ancestor": False,
             "has_linked_task": False},
            2,
        )
        for op in _MODULE + ("delete",):
            self.assertTrue(states[op][0])
            self.assertEqual(states[op][1], "select a single node")

    def test_cardinality_roundtrip_flips_states(self):
        # 1 -> 2 -> 1: single ops and multi ops swap enabled/disabled both ways.
        at1 = op_states_for_selection(self._FULL_CTX, 1)
        at2 = op_states_for_selection(self._FULL_CTX, 2)
        back = op_states_for_selection(self._FULL_CTX, 1)
        self.assertFalse(at1["explore"][0])
        self.assertTrue(at1["compare"][0])
        self.assertTrue(at2["explore"][0])
        self.assertFalse(at2["compare"][0])
        # Returning to a single selection restores the N=1 states exactly.
        self.assertEqual(back, at1)


class NodeActionOpStatesTests(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_relevance_")
        self.wt = Path(self.tmpdir)
        (self.wt / "br_nodes").mkdir()
        (self.wt / "br_proposals").mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _node(self, node_id, parents, module=None):
        data = {
            "node_id": node_id,
            "parents": parents,
            "description": node_id,
            "proposal_file": f"br_proposals/{node_id}.md",
        }
        if module:
            data["module_label"] = module
        (self.wt / "br_nodes" / f"{node_id}.yaml").write_text(
            yaml.safe_dump(data), encoding="utf-8"
        )

    def _graph_state(self, **fields):
        (self.wt / "br_graph_state.yaml").write_text(
            yaml.safe_dump(fields), encoding="utf-8"
        )

    def _app(self):
        app = BrainstormApp.__new__(BrainstormApp)
        app.session_path = self.wt
        return app

    def test_umbrella_node_disables_module_ops(self):
        self._node("n000_init", [])
        self._graph_state(current_heads={"_umbrella": "n000_init"})

        states = self._app()._node_action_op_states("n000_init", 1)

        self.assertTrue(states["module_decompose"][0])
        self.assertTrue(states["module_merge"][0])
        self.assertTrue(states["module_sync"][0])
        for op in ("module_decompose", "module_merge", "module_sync"):
            self.assertIn("root design", states[op][1])
        self.assertTrue(states["delete"][0])
        self.assertIn("root design", states["delete"][1])

    def test_module_node_with_task_and_ancestor_enables_all(self):
        self._node("n000_init", [])
        self._node("n010_p", ["n000_init"], module="parser")
        self._graph_state(
            current_heads={"_umbrella": "n000_init", "parser": "n010_p"},
            module_tasks={"parser": 123},
        )

        states = self._app()._node_action_op_states("n010_p", 1)

        self.assertFalse(states["module_decompose"][0])
        self.assertFalse(states["module_merge"][0])   # _umbrella is an ancestor
        self.assertFalse(states["module_sync"][0])    # linked task present

    def test_module_node_without_ancestor_disables_merge(self):
        # 'solo' module rooted at a parentless node -> no ancestor subgraph.
        self._node("n000_init", [])
        self._node("n020_s", [], module="solo")
        self._graph_state(
            current_heads={"_umbrella": "n000_init", "solo": "n020_s"},
            module_tasks={"solo": 55},
        )

        states = self._app()._node_action_op_states("n020_s", 1)

        self.assertTrue(states["module_merge"][0])
        self.assertIn("no ancestor subgraph", states["module_merge"][1])
        # sync still enabled (linked task present), decompose enabled.
        self.assertFalse(states["module_sync"][0])
        self.assertFalse(states["module_decompose"][0])

    def test_module_node_without_linked_task_disables_sync(self):
        self._node("n000_init", [])
        self._node("n010_p", ["n000_init"], module="parser")
        self._graph_state(
            current_heads={"_umbrella": "n000_init", "parser": "n010_p"},
            module_tasks={},
        )

        states = self._app()._node_action_op_states("n010_p", 1)

        self.assertTrue(states["module_sync"][0])
        self.assertIn("no linked task", states["module_sync"][1])


if __name__ == "__main__":
    unittest.main()
