"""Module Decompose "From section markers" reloads the Browse view (t1995).

The from-sections branch of ``BrainstormApp._run_design_op`` is deterministic:
``apply_module_decompose_from_sections`` creates the module roots and moves their
subgraph HEADs in the worker, with no agent and therefore no apply poller to
reload the session afterwards. These tests boot a real ``BrainstormApp`` over a
temp session, drive the real worker, and assert every Browse surface the reload
rebuilds — the node list, the DAG and the module summary — shows the new roots.

The partial-failure case mirrors the prune branch's ``PrunePartialFailure``
reload: sections are validated inside the creation loop, so a module with no
matching section raises only after the earlier modules' roots are on disk.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agentcrew.agentcrew_utils as ac_mod  # noqa: E402
import brainstorm.brainstorm_session as bs_mod  # noqa: E402

from textual.widgets import Label  # noqa: E402

from brainstorm.brainstorm_app import BrainstormApp  # noqa: E402
from brainstorm.brainstorm_dag import (  # noqa: E402
    NODES_DIR,
    PROPOSALS_DIR,
    UMBRELLA_SUBGRAPH,
    list_nodes,
    read_node,
)
from brainstorm.brainstorm_dag_display import DAGDisplay  # noqa: E402
from brainstorm.widgets import NodeRow  # noqa: E402
from launch_modes import DEFAULT_LAUNCH_MODE  # noqa: E402

SECTIONED_PROPOSAL = (
    "<!-- section: parser [dimensions: component_parser] -->\n"
    "## Parser\nParser section.\n"
    "<!-- /section: parser -->\n\n"
    "<!-- section: cache [dimensions: component_cache] -->\n"
    "## Cache\nCache section.\n"
    "<!-- /section: cache -->\n"
)


class FromSectionsReloadTests(unittest.TestCase):

    TASK_NUM = "99995"

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_from_sections_")
        self._orig_dir = ac_mod.AGENTCREW_DIR
        ac_mod.AGENTCREW_DIR = str(Path(self.tmpdir) / "crews")
        bs_mod.AGENTCREW_DIR = ac_mod.AGENTCREW_DIR
        self.wt = bs_mod.crew_worktree(self.TASK_NUM)
        self.wt.mkdir(parents=True)
        bs_mod.init_session(
            self.TASK_NUM, "aitasks/fake.md", "tester@example.com",
            "Initial spec for the from-sections reload test session.",
        )
        (self.wt / PROPOSALS_DIR / "n000_init.md").write_text(
            SECTIONED_PROPOSAL, encoding="utf-8",
        )
        node = read_node(self.wt, "n000_init")
        node["component_parser"] = "Parser"
        node["component_cache"] = "Cache"
        (self.wt / NODES_DIR / "n000_init.yaml").write_text(
            yaml.safe_dump(node), encoding="utf-8",
        )

    def tearDown(self):
        ac_mod.AGENTCREW_DIR = self._orig_dir
        bs_mod.AGENTCREW_DIR = self._orig_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @staticmethod
    async def _settle(pilot, n=4):
        for _ in range(n):
            await pilot.pause()

    @staticmethod
    def _surfaces(app):
        """The three Browse surfaces ``_load_existing_session`` rebuilds."""
        rows = {r.node_id for r in app.query(NodeRow)}
        dag = list(app.query_one(DAGDisplay)._node_order)
        summary = str(app.query_one("#module_status_info", Label).render())
        return rows, dag, summary

    def _created_roots(self):
        return [n for n in list_nodes(self.wt) if n != "n000_init"]

    async def _run_from_sections(self, app, pilot, modules):
        """Drive the real design-op worker for a from-sections decompose."""
        app._wizard_op = "module_decompose"
        app._wizard_config = {
            "modules": modules,
            "from_sections": True,
            "link_to_task": False,
            "subgraph": UMBRELLA_SUBGRAPH,
            "review_before_apply": True,
            "instructions": "",
            "launch_mode": DEFAULT_LAUNCH_MODE,
        }
        app._wizard_subgraph = UMBRELLA_SUBGRAPH
        app._run_design_op()
        # Deliberately drives the real worker, so draining is the right tool;
        # the worker turns its own exceptions into a notify and never raises.
        await app.workers.wait_for_complete()
        await self._settle(pilot)

    async def _assert_stale_before(self, app, pilot):
        await self._settle(pilot)
        rows, dag, summary = self._surfaces(app)
        self.assertEqual(rows, {"n000_init"})
        self.assertEqual(dag, ["n000_init"])
        self.assertIn("no modules", summary)

    def test_success_shows_new_module_roots(self):
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._assert_stale_before(app, pilot)
                notes = MagicMock()
                app.notify = notes

                await self._run_from_sections(app, pilot, ["parser", "cache"])

                created = self._created_roots()
                self.assertEqual(
                    created,
                    [
                        "n001_module_decomposer_sections_parser",
                        "n002_module_decomposer_sections_cache",
                    ],
                )
                self.assertIn(
                    "Created module roots from sections",
                    notes.call_args.args[0],
                )
                rows, dag, summary = self._surfaces(app)
                for nid in created:
                    self.assertIn(nid, rows)
                    self.assertIn(nid, dag)
                self.assertNotIn("no modules", summary)
                self.assertIn("parser", summary)
                self.assertIn("cache", summary)

        asyncio.run(runner())

    def test_partial_failure_shows_roots_created_before_the_error(self):
        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._assert_stale_before(app, pilot)
                notes = MagicMock()
                app.notify = notes

                await self._run_from_sections(app, pilot, ["parser", "missing"])

                # parser's root landed before "missing" raised.
                created = self._created_roots()
                self.assertEqual(
                    created, ["n001_module_decomposer_sections_parser"],
                )
                self.assertIn(
                    "no section found for module 'missing'",
                    notes.call_args.args[0],
                )
                self.assertEqual(notes.call_args.kwargs.get("severity"), "error")
                rows, dag, summary = self._surfaces(app)
                self.assertIn(created[0], rows)
                self.assertIn(created[0], dag)
                self.assertNotIn("no modules", summary)
                self.assertIn("parser", summary)
                self.assertNotIn("missing", summary)

        asyncio.run(runner())


if __name__ == "__main__":
    unittest.main()
