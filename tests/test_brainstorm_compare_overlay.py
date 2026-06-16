"""Tests for the Compare matrix overlay (t983_7).

t983_7 (child of the t983 brainstorm-TUI IA redesign) re-homes the former
Compare-*tab* dimension matrix as a ``CompareMatrixModal`` overlay opened from
the Browse marked set, the Node Hub (``c`` / Compare button), or the graph
``x``/Enter picker, and deletes the Compare tab + ``CompareNodeSelectModal``.

Coverage:
- ``NextCheckboxIndexTests`` (retained): ``_next_checkbox_index`` survives the
  modal deletion — it is still used by ``FuzzyCheckList``.
- ``CompareMatrixRowsTests``: the pure, App-free ``compare_matrix_rows`` build
  logic (same/diff cells, similarity row, empty-dims guard, column order).
- ``CompareTriggerTests``: the 2-4 cardinality guard and the Node-Hub contract
  (focal node unioned with the marked set, so it always participates).
- ``CompareMatrixModalPilotTests``: the overlay renders the table and ``D``
  stacks a ``DiffViewerScreen`` over the modal, returning to the matrix on pop.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import yaml  # noqa: E402

from textual.app import App, ComposeResult  # noqa: E402
from textual.widgets import DataTable, Label  # noqa: E402

from brainstorm.brainstorm_app import (  # noqa: E402
    NODE_HUB_COMPARE,
    BrainstormApp,
    CompareMatrixModal,
    NodeHubResult,
    NodeSelection,
    _next_checkbox_index,
    compare_matrix_rows,
)
from diffviewer.diff_viewer_screen import DiffViewerScreen  # noqa: E402


# ---------------------------------------------------------------------------
# Retained: shared helper still used by FuzzyCheckList (Finding 2)
# ---------------------------------------------------------------------------


class NextCheckboxIndexTests(unittest.TestCase):
    def test_no_checkboxes_returns_none(self):
        self.assertIsNone(_next_checkbox_index(None, 0, 1))
        self.assertIsNone(_next_checkbox_index(None, 0, -1))
        self.assertIsNone(_next_checkbox_index(0, 0, 1))

    def test_no_focus_down_focuses_first(self):
        self.assertEqual(_next_checkbox_index(None, 5, 1), 0)

    def test_no_focus_up_focuses_last(self):
        self.assertEqual(_next_checkbox_index(None, 5, -1), 4)

    def test_down_increments(self):
        self.assertEqual(_next_checkbox_index(0, 5, 1), 1)
        self.assertEqual(_next_checkbox_index(2, 5, 1), 3)

    def test_up_decrements(self):
        self.assertEqual(_next_checkbox_index(4, 5, -1), 3)
        self.assertEqual(_next_checkbox_index(1, 5, -1), 0)

    def test_down_at_bottom_stays(self):
        self.assertIsNone(_next_checkbox_index(4, 5, 1))

    def test_up_at_top_stays(self):
        self.assertIsNone(_next_checkbox_index(0, 5, -1))

    def test_single_checkbox_no_movement(self):
        self.assertIsNone(_next_checkbox_index(0, 1, 1))
        self.assertIsNone(_next_checkbox_index(0, 1, -1))


# ---------------------------------------------------------------------------
# Pure matrix-build logic (no App, no I/O)
# ---------------------------------------------------------------------------


def _plain(cells) -> list:
    """The plain text of each cell (str or rich Text)."""
    return [getattr(c, "plain", c) for c in cells]


class CompareMatrixRowsTests(unittest.TestCase):
    def test_empty_dims_returns_none(self):
        self.assertIsNone(compare_matrix_rows({"a": {}, "b": {}}, ["a", "b"]))

    def test_two_node_same_and_diff_rows(self):
        dims = {
            "n1": {"tradeoff_cost": "low", "tradeoff_speed": "fast"},
            "n2": {"tradeoff_cost": "high", "tradeoff_speed": "fast"},
        }
        rows = compare_matrix_rows(dims, ["n1", "n2"])
        self.assertIsNotNone(rows)
        # 2 dimension rows + 1 similarity summary row.
        self.assertEqual(len(rows), 3)
        by_key = {rk: cells for rk, cells in rows}
        # Differing values are both shown.
        self.assertEqual(_plain(by_key["tradeoff_cost"]),
                         ["tradeoff_cost", "low", "high"])
        # Equal values collapse to a "← same" marker for n == 2.
        self.assertEqual(_plain(by_key["tradeoff_speed"]),
                         ["tradeoff_speed", "fast", "← same"])
        # The last row is the average-similarity summary.
        self.assertEqual(rows[-1][0], "sim_score")
        self.assertEqual(_plain(rows[-1][1])[0], "— Avg Similarity —")

    def test_each_row_has_one_cell_per_node_plus_dimension(self):
        dims = {n: {"component_x": v}
                for n, v in (("n1", "a"), ("n2", "b"), ("n3", "c"))}
        rows = compare_matrix_rows(dims, ["n1", "n2", "n3"])
        # 1 dimension row + 1 similarity row.
        self.assertEqual(len(rows), 2)
        for _rk, cells in rows:
            # Dimension column + one cell per node id.
            self.assertEqual(len(cells), 1 + 3)

    def test_column_order_follows_node_ids(self):
        dims = {
            "n1": {"tradeoff_cost": "low"},
            "n2": {"tradeoff_cost": "high"},
        }
        rows_fwd = compare_matrix_rows(dims, ["n1", "n2"])
        rows_rev = compare_matrix_rows(dims, ["n2", "n1"])
        self.assertEqual(_plain(dict(rows_fwd)["tradeoff_cost"]),
                         ["tradeoff_cost", "low", "high"])
        self.assertEqual(_plain(dict(rows_rev)["tradeoff_cost"]),
                         ["tradeoff_cost", "high", "low"])


# ---------------------------------------------------------------------------
# Trigger / guard logic (bare app — __init__ bypassed, push/notify stubbed)
# ---------------------------------------------------------------------------


def _bare_app(session_path=None, marked=None):
    app = BrainstormApp.__new__(BrainstormApp)
    app.session_path = session_path
    sel = NodeSelection()
    for m in marked or []:
        sel.mark(m)
    app._selection = sel
    app.pushed = []
    app.notices = []
    app.push_screen = lambda screen, *a, **k: app.pushed.append(screen)
    app.notify = lambda msg, **kw: app.notices.append((msg, kw))
    return app


class CompareTriggerTests(unittest.TestCase):
    def test_too_few_nodes_notifies_no_push(self):
        app = _bare_app("/tmp/x")
        app._open_compare_matrix(["n1"])
        self.assertEqual(app.pushed, [])
        self.assertTrue(app.notices)

    def test_too_many_nodes_notifies_no_push(self):
        app = _bare_app("/tmp/x")
        app._open_compare_matrix(["n1", "n2", "n3", "n4", "n5"])
        self.assertEqual(app.pushed, [])
        self.assertTrue(app.notices)

    def test_valid_set_pushes_modal(self):
        app = _bare_app("/tmp/x")
        app._open_compare_matrix(["n1", "n2"])
        self.assertEqual(len(app.pushed), 1)
        self.assertIsInstance(app.pushed[0], CompareMatrixModal)
        self.assertEqual(app.pushed[0].node_ids, ["n1", "n2"])

    def test_hub_compare_unions_focal_node_with_marks(self):
        # The Hub's focal node (n1) is unioned with the marked peers (n2, n3),
        # so the node you were viewing always participates — review concern 1.
        app = _bare_app("/tmp/x", marked=["n2", "n3"])
        app._on_node_hub_result(NodeHubResult(NODE_HUB_COMPARE, "n1"))
        self.assertEqual(len(app.pushed), 1)
        self.assertEqual(app.pushed[0].node_ids, ["n1", "n2", "n3"])

    def test_hub_compare_dedups_focal_node_already_marked(self):
        app = _bare_app("/tmp/x", marked=["n1", "n2"])
        app._on_node_hub_result(NodeHubResult(NODE_HUB_COMPARE, "n1"))
        self.assertEqual(app.pushed[0].node_ids, ["n1", "n2"])

    def test_hub_compare_lone_node_notifies(self):
        app = _bare_app("/tmp/x")  # nothing marked → only the focal node
        app._on_node_hub_result(NodeHubResult(NODE_HUB_COMPARE, "n1"))
        self.assertEqual(app.pushed, [])
        self.assertTrue(app.notices)


# ---------------------------------------------------------------------------
# Pilot: overlay renders + D stacks the diff over the modal
# ---------------------------------------------------------------------------


def _make_session(td: str, nodes: dict) -> Path:
    """Write a minimal session with the given ``{node_id: dims}`` mapping; each
    node gets a proposal file (needed for the ``D`` diff path)."""
    session = Path(td)
    (session / "br_nodes").mkdir(parents=True, exist_ok=True)
    (session / "br_proposals").mkdir(parents=True, exist_ok=True)
    for nid, dims in nodes.items():
        data = {"description": f"node {nid}", "parents": [], **dims}
        (session / "br_nodes" / f"{nid}.yaml").write_text(
            yaml.safe_dump(data), encoding="utf-8"
        )
        (session / "br_proposals" / f"{nid}.md").write_text(
            f"# Proposal {nid}\n", encoding="utf-8"
        )
    return session


class _HostCompareApp(App):
    """Bare host that pushes a CompareMatrixModal on mount (borrowing the app
    CSS so the dialog renders)."""

    CSS = BrainstormApp.CSS
    task_num = "0"

    def __init__(self, session_path: Path, node_ids: list[str]) -> None:
        super().__init__()
        self._session_path = session_path
        self._node_ids = node_ids

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(CompareMatrixModal(self._session_path, self._node_ids))


class CompareMatrixModalPilotTests(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def test_overlay_renders_matrix_table(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                session = _make_session(td, {
                    "n1": {"tradeoff_cost": "low"},
                    "n2": {"tradeoff_cost": "high"},
                })
                app = _HostCompareApp(session, ["n1", "n2"])
                cm = app.run_test(size=(140, 48))
                pilot = await cm.__aenter__()
                await pilot.pause()
                await pilot.pause()
                try:
                    screen = app.screen
                    self.assertIsInstance(screen, CompareMatrixModal)
                    table = screen.query_one("#compare_table", DataTable)
                    # Dimension column + 2 node columns.
                    self.assertEqual(len(table.columns), 3)
                    # 1 dimension row + similarity summary.
                    self.assertEqual(table.row_count, 2)
                finally:
                    await cm.__aexit__(None, None, None)

        self._run(runner())

    def test_diff_stacks_over_modal_and_returns(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                session = _make_session(td, {
                    "n1": {"tradeoff_cost": "low"},
                    "n2": {"tradeoff_cost": "high"},
                })
                app = _HostCompareApp(session, ["n1", "n2"])
                cm = app.run_test(size=(140, 48))
                pilot = await cm.__aenter__()
                await pilot.pause()
                await pilot.pause()
                try:
                    await pilot.press("D")
                    await pilot.pause()
                    # The diff screen is stacked OVER the still-mounted matrix.
                    self.assertIsInstance(app.screen, DiffViewerScreen)
                    await app.pop_screen()
                    await pilot.pause()
                    # Popping the diff returns to the matrix (not the base host).
                    self.assertIsInstance(app.screen, CompareMatrixModal)
                finally:
                    await cm.__aexit__(None, None, None)

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
