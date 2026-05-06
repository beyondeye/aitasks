"""Tests for the DAG node-box op badge (t749_3).

Covers _build_graph's node_op_map join against br_groups.yaml, and
_render_node_box's badge row rendering.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

from brainstorm.brainstorm_dag_display import (  # noqa: E402
    BOX_WIDTH,
    NODE_ROWS,
    OP_BADGE_STYLES,
    UNKNOWN_OP_STYLE,
    _build_graph,
    _render_node_box,
)


def _seed_session(wt: Path) -> None:
    """Set up the minimal directory layout _build_graph expects."""
    (wt / "br_nodes").mkdir(parents=True, exist_ok=True)
    (wt / "br_proposals").mkdir(parents=True, exist_ok=True)
    (wt / "br_plans").mkdir(parents=True, exist_ok=True)


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


class TestBuildGraphOpMap(unittest.TestCase):
    def test_joins_node_to_operation_via_groups(self):
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
            _, _, _, _, op_map = _build_graph(wt)
            self.assertEqual(op_map.get("n001_x"), "explore")

    def test_legacy_session_empty_groups_yields_empty_op(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt)
            _write_groups(wt, {})
            _write_node(wt, "n001_x", parents=[], group="some_legacy_group")
            _, _, _, _, op_map = _build_graph(wt)
            self.assertEqual(op_map.get("n001_x"), "")

    def test_missing_groups_file_yields_empty_op(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt)
            _write_node(wt, "n001_x", parents=[], group="explore_001")
            _, _, _, _, op_map = _build_graph(wt)
            self.assertEqual(op_map.get("n001_x"), "")

    def test_missing_created_by_group_yields_empty_op(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_session(wt)
            _write_groups(wt, {
                "explore_001": {"operation": "explore", "agents": ["a"]},
            })
            # node yaml missing created_by_group
            data = {
                "node_id": "n001_x",
                "parents": [],
                "description": "no group",
                "proposal_file": "br_proposals/n001_x.md",
                "created_at": "2026-05-05 12:00",
            }
            (wt / "br_nodes" / "n001_x.yaml").write_text(
                yaml.safe_dump(data), encoding="utf-8"
            )
            _, _, _, _, op_map = _build_graph(wt)
            self.assertEqual(op_map.get("n001_x"), "")


class TestRenderNodeBox(unittest.TestCase):
    def test_node_rows_constant_is_five(self):
        self.assertEqual(NODE_ROWS, 5)

    def test_renders_five_rows(self):
        rows = _render_node_box("n001_x", "desc", False, False, "explore")
        self.assertEqual(len(rows), 5)

    def test_badge_row_contains_operation_text(self):
        rows = _render_node_box("n001_x", "desc", False, False, "explore")
        # Row 0: top border. Row 1: title. Row 2: badge. Row 3: desc. Row 4: bot.
        badge_plain = rows[2].plain
        self.assertIn("[explore]", badge_plain)

    def test_each_row_is_box_width(self):
        rows = _render_node_box("n001_x", "desc", False, False, "explore")
        for i, row in enumerate(rows):
            self.assertEqual(
                len(row.plain), BOX_WIDTH,
                f"row {i} width {len(row.plain)} != {BOX_WIDTH}: {row.plain!r}",
            )

    def test_empty_operation_renders_blank_badge(self):
        rows = _render_node_box("n001_x", "desc", False, False, "")
        # Badge row should be all spaces between the | borders.
        badge_plain = rows[2].plain
        self.assertEqual(badge_plain[0], "|")
        self.assertEqual(badge_plain[-1], "|")
        self.assertEqual(badge_plain[1:-1].strip(), "")

    def test_unknown_operation_uses_unknown_style(self):
        rows = _render_node_box("n001_x", "desc", False, False, "weird")
        self.assertIn("[weird]", rows[2].plain)
        # The first non-border span should carry the UNKNOWN_OP_STYLE color.
        # Rich Text uses spans; we check that *some* span has italic=True.
        spans = rows[2].spans
        italic_spans = [s for s in spans if s.style and getattr(s.style, "italic", False)]
        self.assertTrue(italic_spans, "expected an italic span for unknown op")

    def test_known_operation_uses_palette_color(self):
        for op in OP_BADGE_STYLES:
            with self.subTest(op=op):
                rows = _render_node_box("n001_x", "desc", False, False, op)
                self.assertIn(f"[{op}]", rows[2].plain)

    def test_op_badge_styles_keys_match_group_operations(self):
        # Sanity: the badge color map covers every op listed in
        # GROUP_OPERATIONS plus bootstrap (the t749_1 init group).
        from brainstorm.brainstorm_schemas import GROUP_OPERATIONS  # noqa: E402
        for op in GROUP_OPERATIONS:
            self.assertIn(op, OP_BADGE_STYLES, f"missing color for {op}")
        self.assertIn("bootstrap", OP_BADGE_STYLES)


if __name__ == "__main__":
    unittest.main()
