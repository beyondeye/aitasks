"""Relevance-filter tests for the brainstorm node-action picker (t925).

Unit-tests ``BrainstormApp._node_action_op_states`` — the map of
``{op_key: (disabled, reason)}`` the picker uses to grey out ops that do not
apply to the focused node. Runs over synthetic (dummy-data) sessions on disk
with ``BrainstormApp.__init__`` bypassed (the pattern established by
``test_brainstorm_node_action_modal.py``); no Textual runtime is needed.
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

from brainstorm.brainstorm_app import BrainstormApp  # noqa: E402


class NodeActionOpStatesTests(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_relevance_")
        self.wt = Path(self.tmpdir)
        (self.wt / "br_nodes").mkdir()
        (self.wt / "br_proposals").mkdir()
        (self.wt / "br_plans").mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _node(self, node_id, parents, module=None, plan_file=None):
        data = {
            "node_id": node_id,
            "parents": parents,
            "description": node_id,
            "proposal_file": f"br_proposals/{node_id}.md",
        }
        if module:
            data["module_label"] = module
        if plan_file:
            data["plan_file"] = plan_file
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
        self._node("n000_init", [], plan_file="br_plans/n000_init_plan.md")
        (self.wt / "br_plans" / "n000_init_plan.md").write_text("# p", "utf-8")
        self._graph_state(current_heads={"_umbrella": "n000_init"})

        states = self._app()._node_action_op_states("n000_init")

        self.assertTrue(states["module_decompose"][0])
        self.assertTrue(states["module_merge"][0])
        self.assertTrue(states["module_sync"][0])
        for op in ("module_decompose", "module_merge", "module_sync"):
            self.assertIn("root design", states[op][1])

    def test_module_node_with_task_and_ancestor_enables_all(self):
        self._node("n000_init", [])
        self._node("n010_p", ["n000_init"], module="parser")
        self._graph_state(
            current_heads={"_umbrella": "n000_init", "parser": "n010_p"},
            module_tasks={"parser": 123},
        )

        states = self._app()._node_action_op_states("n010_p")

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

        states = self._app()._node_action_op_states("n020_s")

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

        states = self._app()._node_action_op_states("n010_p")

        self.assertTrue(states["module_sync"][0])
        self.assertIn("no linked task", states["module_sync"][1])


if __name__ == "__main__":
    unittest.main()
