"""Pilot tests for the 'o' keybinding on DAGDisplay (t749_6).

Mounts a host App with a DAGDisplay over a synthesized brainstorm session,
focuses a node, simulates 'o', and asserts an OperationOpened message
is posted with the right group_name. Also covers the "no group recorded"
path where no message is posted.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import yaml  # noqa: E402

from textual import on  # noqa: E402
from textual.app import App, ComposeResult  # noqa: E402

from brainstorm.brainstorm_dag_display import DAGDisplay  # noqa: E402


def _seed_session(wt: Path) -> None:
    (wt / "br_nodes").mkdir(parents=True, exist_ok=True)
    (wt / "br_proposals").mkdir(parents=True, exist_ok=True)
    (wt / "br_plans").mkdir(parents=True, exist_ok=True)
    (wt / "br_graph_state.yaml").write_text(
        yaml.safe_dump({
            "current_head": None,
            "history": [],
            "next_node_id": 1,
        }),
        encoding="utf-8",
    )


def _write_node(wt: Path, node_id: str, parents: list[str], group: str) -> None:
    data = {
        "node_id": node_id,
        "parents": parents,
        "description": f"desc for {node_id}",
        "proposal_file": f"br_proposals/{node_id}.md",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "created_by_group": group,
    }
    (wt / "br_nodes" / f"{node_id}.yaml").write_text(
        yaml.safe_dump(data), encoding="utf-8"
    )


def _write_groups(wt: Path, groups: dict) -> None:
    (wt / "br_groups.yaml").write_text(
        yaml.safe_dump({"groups": groups}), encoding="utf-8"
    )


class _HostApp(App):
    """Host that mounts a DAGDisplay and records OperationOpened events."""

    def __init__(self, session_path: Path) -> None:
        super().__init__()
        self._session_path = session_path
        self.opened_groups: list[str] = []

    def compose(self) -> ComposeResult:
        yield DAGDisplay(id="dag")

    def on_mount(self) -> None:
        dag = self.query_one(DAGDisplay)
        dag.load_dag(self._session_path)
        self.set_focus(dag)

    @on(DAGDisplay.OperationOpened)
    def _record_op_opened(self, event: DAGDisplay.OperationOpened) -> None:
        self.opened_groups.append(event.group_name)


class TestDAGOpKeybinding(unittest.TestCase):

    def _run(self, coro):
        return asyncio.run(coro)

    def test_o_posts_operation_opened_for_node_with_group(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                wt = Path(td)
                _seed_session(wt)
                _write_groups(wt, {
                    "explore_001": {
                        "operation": "explore",
                        "agents": ["explorer_a"],
                        "status": "Completed",
                        "head_at_creation": "n000_init",
                        "nodes_created": ["n001_x"],
                    },
                })
                _write_node(wt, "n001_x", parents=[], group="explore_001")

                app = _HostApp(wt)
                async with app.run_test(size=(140, 48)) as pilot:
                    await pilot.pause()
                    await pilot.pause()
                    await pilot.press("o")
                    await pilot.pause()
                    self.assertEqual(app.opened_groups, ["explore_001"])

        self._run(runner())

    def test_o_on_node_without_group_posts_nothing(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                wt = Path(td)
                _seed_session(wt)
                _write_groups(wt, {})
                _write_node(wt, "n001_x", parents=[], group="")

                app = _HostApp(wt)
                async with app.run_test(size=(140, 48)) as pilot:
                    await pilot.pause()
                    await pilot.pause()
                    await pilot.press("o")
                    await pilot.pause()
                    self.assertEqual(app.opened_groups, [])

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
