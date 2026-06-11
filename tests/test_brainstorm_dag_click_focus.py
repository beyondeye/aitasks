"""Pilot tests for click-to-focus on DAGDisplay (t793).

Mounts a host App with a DAGDisplay over a synthesized 3-node brainstorm
session and exercises _handle_click directly with content-relative
coordinates derived from the module's geometry constants.
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

from brainstorm.brainstorm_dag_display import (  # noqa: E402
    BOX_WIDTH,
    COL_STRIDE,
    DAGDisplay,
    EDGE_ROWS,
    NODE_ROWS,
)


def _seed_session(wt: Path) -> None:
    (wt / "br_nodes").mkdir(parents=True, exist_ok=True)
    (wt / "br_proposals").mkdir(parents=True, exist_ok=True)
    (wt / "br_graph_state.yaml").write_text(
        yaml.safe_dump({
            "current_head": None,
            "history": [],
            "next_node_id": 1,
        }),
        encoding="utf-8",
    )
    (wt / "br_groups.yaml").write_text(
        yaml.safe_dump({"groups": {}}), encoding="utf-8"
    )


def _write_node(wt: Path, node_id: str, parents: list[str]) -> None:
    data = {
        "node_id": node_id,
        "parents": parents,
        "description": f"desc for {node_id}",
        "proposal_file": f"br_proposals/{node_id}.md",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "created_by_group": "",
    }
    (wt / "br_nodes" / f"{node_id}.yaml").write_text(
        yaml.safe_dump(data), encoding="utf-8"
    )


class _HostApp(App):
    """Host that mounts a DAGDisplay and records FocusChanged events."""

    def __init__(self, session_path: Path) -> None:
        super().__init__()
        self._session_path = session_path
        self.focus_changes: list[str] = []

    def compose(self) -> ComposeResult:
        yield DAGDisplay(id="dag")

    def on_mount(self) -> None:
        dag = self.query_one(DAGDisplay)
        dag.load_dag(self._session_path)
        self.set_focus(dag)

    @on(DAGDisplay.FocusChanged)
    def _record_focus(self, event: DAGDisplay.FocusChanged) -> None:
        self.focus_changes.append(event.node_id)


def _seed_three_nodes(wt: Path) -> None:
    """Build a 2-layer graph: n001 (root), n002 + n003 (children)."""
    _seed_session(wt)
    _write_node(wt, "n001", parents=[])
    _write_node(wt, "n002", parents=["n001"])
    _write_node(wt, "n003", parents=["n001"])


class TestDAGClickFocus(unittest.TestCase):

    def _run(self, coro):
        return asyncio.run(coro)

    def test_click_on_second_layer_node_focuses_it(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                wt = Path(td)
                _seed_three_nodes(wt)

                app = _HostApp(wt)
                async with app.run_test(size=(140, 48)) as pilot:
                    await pilot.pause()
                    await pilot.pause()
                    dag = app.query_one(DAGDisplay)

                    # Initial focus is on n001 (first node).
                    self.assertEqual(
                        dag._node_order[dag._focused_idx], "n001"
                    )

                    # The layout: layer 0 = [n001], layer 1 = [n002, n003].
                    self.assertEqual(dag._layers[0], ["n001"])
                    self.assertEqual(set(dag._layers[1]), {"n002", "n003"})

                    # Click the center of the right-hand box in layer 1.
                    target_col = 1
                    target_id = dag._layers[1][target_col]
                    top = dag._node_line_map[target_id]
                    x = target_col * COL_STRIDE + BOX_WIDTH // 2
                    y = top + NODE_ROWS // 2

                    app.focus_changes.clear()
                    dag._handle_click(x, y)
                    await pilot.pause()

                    self.assertEqual(
                        dag._node_order[dag._focused_idx], target_id
                    )
                    self.assertEqual(app.focus_changes, [target_id])

        self._run(runner())

    def test_click_on_already_focused_node_does_not_repost(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                wt = Path(td)
                _seed_three_nodes(wt)

                app = _HostApp(wt)
                async with app.run_test(size=(140, 48)) as pilot:
                    await pilot.pause()
                    await pilot.pause()
                    dag = app.query_one(DAGDisplay)

                    focused_id = dag._node_order[dag._focused_idx]
                    top = dag._node_line_map[focused_id]
                    # Find which column the focused node is in.
                    for layer in dag._layers:
                        if focused_id in layer:
                            col_idx = layer.index(focused_id)
                            break
                    x = col_idx * COL_STRIDE + BOX_WIDTH // 2
                    y = top + NODE_ROWS // 2

                    app.focus_changes.clear()
                    dag._handle_click(x, y)
                    await pilot.pause()

                    self.assertEqual(
                        dag._node_order[dag._focused_idx], focused_id
                    )
                    self.assertEqual(app.focus_changes, [])

        self._run(runner())

    def test_click_in_column_gap_is_noop(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                wt = Path(td)
                _seed_three_nodes(wt)

                app = _HostApp(wt)
                async with app.run_test(size=(140, 48)) as pilot:
                    await pilot.pause()
                    await pilot.pause()
                    dag = app.query_one(DAGDisplay)

                    initial_idx = dag._focused_idx
                    # Top of layer 1 row, x just past first box (in the
                    # COL_GAP between box 0 and box 1).
                    layer1_top = dag._node_line_map[dag._layers[1][0]]
                    x = BOX_WIDTH + 1  # inside the gap
                    y = layer1_top + NODE_ROWS // 2

                    app.focus_changes.clear()
                    dag._handle_click(x, y)
                    await pilot.pause()

                    self.assertEqual(dag._focused_idx, initial_idx)
                    self.assertEqual(app.focus_changes, [])

        self._run(runner())

    def test_click_in_edge_row_between_layers_is_noop(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                wt = Path(td)
                _seed_three_nodes(wt)

                app = _HostApp(wt)
                async with app.run_test(size=(140, 48)) as pilot:
                    await pilot.pause()
                    await pilot.pause()
                    dag = app.query_one(DAGDisplay)

                    initial_idx = dag._focused_idx
                    # Edge rows live between layer 0's last line and
                    # layer 1's first line.
                    n001_top = dag._node_line_map["n001"]
                    layer1_top = dag._node_line_map[dag._layers[1][0]]
                    # Sanity: there are EDGE_ROWS lines between them.
                    self.assertEqual(
                        layer1_top - (n001_top + NODE_ROWS), EDGE_ROWS
                    )
                    edge_y = n001_top + NODE_ROWS + EDGE_ROWS // 2
                    x = BOX_WIDTH // 2  # center of column 0

                    app.focus_changes.clear()
                    dag._handle_click(x, edge_y)
                    await pilot.pause()

                    self.assertEqual(dag._focused_idx, initial_idx)
                    self.assertEqual(app.focus_changes, [])

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
