"""Tests for the brainstorm cascade node-delete UI (t925).

Covers three pieces:

- ``DeleteNodeModal`` — the confirmation dialog (Pilot-driven on a minimal host
  App): full closure list rendered, linked-aitask warning, Delete blocked when
  running-agent casualties are present, and the double-confirm dismiss(True).
- ``BrainstormApp._delete_agent_casualties`` — the running-agent guard, over a
  synthetic worktree with ``_status.yaml`` + ``<agent>_input.md`` fixtures.
- ``BrainstormApp._on_delete_node_result`` — the confirm callback runs the
  cascade, clears focus, and notifies.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import yaml  # noqa: E402

from textual.app import App, ComposeResult  # noqa: E402
from textual.widgets import Button, Label  # noqa: E402

from brainstorm.brainstorm_app import (  # noqa: E402
    BrainstormApp,
    DeleteNodeModal,
    NodeSelection,
)


# --------------------------------------------------------------------------
# DeleteNodeModal — Pilot tests
# --------------------------------------------------------------------------

class _DeleteModalHost(App):
    def __init__(self, node_id, closure, linked_modules, casualties) -> None:
        super().__init__()
        self._args = (node_id, closure, linked_modules, casualties)
        self.result = "UNSET"

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(DeleteNodeModal(*self._args), self._record)

    def _record(self, result) -> None:
        self.result = result


class DeleteNodeModalTests(unittest.TestCase):

    def _run(self, coro):
        return asyncio.run(coro)

    def test_lists_full_closure_and_warns_on_linked_task(self):
        async def runner():
            closure = ["n001_b", "n002_c", "n003_d"]
            app = _DeleteModalHost(
                "n001_b", closure, [("parser", 123)], []
            )
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                rows = app.screen.query("#delete_node_closure Label")
                self.assertEqual(len(list(rows)), len(closure))
                text = " ".join(
                    str(lbl.render()) for lbl in app.screen.query(Label)
                )
                self.assertIn("linked aitask t123", text)
                self.assertIn("left untouched", text)

        self._run(runner())

    def test_delete_blocked_when_agent_casualties_present(self):
        async def runner():
            app = _DeleteModalHost(
                "n001_b", ["n001_b"], [], [("n001_b", "explorer_001", "Running")]
            )
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                btn = app.screen.query_one("#btn_delete_node", Button)
                self.assertTrue(btn.disabled)
                text = " ".join(
                    str(lbl.render()) for lbl in app.screen.query(Label)
                )
                self.assertIn("Blocked", text)

        self._run(runner())

    def test_double_confirm_dismisses_true(self):
        async def runner():
            app = _DeleteModalHost("n001_b", ["n001_b"], [], [])
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                await pilot.click("#btn_delete_node")  # first: "are you sure?"
                await pilot.pause()
                self.assertEqual(app.result, "UNSET")
                await pilot.click("#btn_delete_node")  # second: confirm
                await pilot.pause()
                self.assertTrue(app.result)

        self._run(runner())

    def test_escape_cancels_with_false(self):
        async def runner():
            app = _DeleteModalHost("n001_b", ["n001_b"], [], [])
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.pause()
                await pilot.press("escape")
                await pilot.pause()
                self.assertFalse(app.result)

        self._run(runner())


# --------------------------------------------------------------------------
# _delete_agent_casualties + _on_delete_node_result — unit tests
# --------------------------------------------------------------------------

class DeleteGuardAndCallbackTests(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_node_delete_")
        self.wt = Path(self.tmpdir)
        for d in ("br_nodes", "br_proposals"):
            (self.wt / d).mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _node(self, node_id, parents):
        data = {
            "node_id": node_id,
            "parents": parents,
            "description": node_id,
            "proposal_file": f"br_proposals/{node_id}.md",
        }
        (self.wt / "br_nodes" / f"{node_id}.yaml").write_text(
            yaml.safe_dump(data), encoding="utf-8"
        )
        (self.wt / "br_proposals" / f"{node_id}.md").write_text("# p", "utf-8")

    def _agent(self, name, status, target_node=None):
        (self.wt / f"{name}_status.yaml").write_text(
            yaml.safe_dump({"agent_name": name, "status": status}),
            encoding="utf-8",
        )
        if target_node is not None:
            (self.wt / f"{name}_input.md").write_text(
                f"- Metadata: {self.wt}/br_nodes/{target_node}.yaml\n",
                encoding="utf-8",
            )

    def _app(self):
        app = BrainstormApp.__new__(BrainstormApp)
        app.session_path = self.wt
        # __init__ is bypassed here; the Browse selection model (t983_3) is
        # touched by the delete-cascade purge, so provide it explicitly.
        app._selection = NodeSelection()
        return app

    def test_running_agent_on_affected_node_is_a_casualty(self):
        self._agent("explorer_001", "Running", target_node="n001_b")
        casualties = self._app()._delete_agent_casualties({"n001_b", "n002_c"})
        self.assertEqual(casualties, [("n001_b", "explorer_001", "Running")])

    def test_unrecoverable_agent_does_not_block(self):
        # No input file -> node cannot be recovered (multi-node op) -> ignored.
        self._agent("synthesizer_001", "Running", target_node=None)
        casualties = self._app()._delete_agent_casualties({"n001_b"})
        self.assertEqual(casualties, [])

    def test_completed_agent_is_not_a_casualty(self):
        self._agent("explorer_001", "Completed", target_node="n001_b")
        casualties = self._app()._delete_agent_casualties({"n001_b"})
        self.assertEqual(casualties, [])

    def test_agent_on_unaffected_node_is_not_a_casualty(self):
        self._agent("explorer_001", "Running", target_node="n999_other")
        casualties = self._app()._delete_agent_casualties({"n001_b"})
        self.assertEqual(casualties, [])

    def test_on_delete_node_result_cascades_clears_focus_notifies(self):
        self._node("n000_a", [])
        self._node("n001_b", ["n000_a"])
        self._node("n002_c", ["n001_b"])
        (self.wt / "br_graph_state.yaml").write_text(
            yaml.safe_dump({"current_heads": {"_umbrella": "n002_c"}}),
            encoding="utf-8",
        )
        app = self._app()
        app._selection.set_primary("n002_c")
        app.notices = []
        app.refreshed = False
        app.notify = lambda msg, **kw: app.notices.append(msg)
        app._load_existing_session = lambda: setattr(app, "refreshed", True)

        app._on_delete_node_result("n001_b", True)

        self.assertFalse((self.wt / "br_nodes" / "n001_b.yaml").is_file())
        self.assertFalse((self.wt / "br_nodes" / "n002_c.yaml").is_file())
        self.assertTrue((self.wt / "br_nodes" / "n000_a.yaml").is_file())
        # Consolidated cursor: the deleted cursor node is cleared purely via
        # NodeSelection.remove in the delete-cascade loop (t1003).
        self.assertIsNone(app._selection.primary)
        self.assertTrue(app.refreshed)
        self.assertTrue(any("Deleted 2 node" in m for m in app.notices))

    def test_on_delete_node_result_noop_when_not_confirmed(self):
        self._node("n001_b", [])
        app = self._app()
        app.notices = []
        app.notify = lambda msg, **kw: app.notices.append(msg)
        app._on_delete_node_result("n001_b", False)
        self.assertTrue((self.wt / "br_nodes" / "n001_b.yaml").is_file())

    def test_on_delete_node_result_blocks_when_agent_appears(self):
        self._node("n000_init", [])
        self._node("n001_b", ["n000_init"])
        (self.wt / "br_graph_state.yaml").write_text(
            yaml.safe_dump({"current_heads": {"_umbrella": "n001_b"}}),
            encoding="utf-8",
        )
        self._agent("explorer_001", "Running", target_node="n001_b")
        app = self._app()
        app.notices = []
        app.notify = lambda msg, **kw: app.notices.append(msg)
        app._on_delete_node_result("n001_b", True)
        # Guard re-check blocks the delete; node survives.
        self.assertTrue((self.wt / "br_nodes" / "n001_b.yaml").is_file())
        self.assertTrue(any("blocked" in m.lower() for m in app.notices))

    def test_on_delete_node_result_refuses_root(self):
        self._node("n000_init", [])
        self._node("n001_b", ["n000_init"])
        (self.wt / "br_graph_state.yaml").write_text(
            yaml.safe_dump({"current_heads": {"_umbrella": "n001_b"}}),
            encoding="utf-8",
        )
        app = self._app()
        app.notices = []
        app.refreshed = False
        app.notify = lambda msg, **kw: app.notices.append(msg)
        app._load_existing_session = lambda: setattr(app, "refreshed", True)

        app._on_delete_node_result("n000_init", True)

        self.assertTrue((self.wt / "br_nodes" / "n000_init.yaml").is_file())
        self.assertTrue((self.wt / "br_nodes" / "n001_b.yaml").is_file())
        self.assertFalse(app.refreshed)
        self.assertTrue(any("root design" in m for m in app.notices))


if __name__ == "__main__":
    unittest.main()
