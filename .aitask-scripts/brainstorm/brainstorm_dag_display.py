"""DAG visualization widget for the brainstorm TUI.

Renders an ASCII art graph of proposal nodes with box-drawing characters,
edge routing between layers, and keyboard navigation (j/k/Enter/h).
"""

from __future__ import annotations

import os
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Static

from rich.style import Style
from rich.text import Text

from brainstorm.brainstorm_dag import (
    get_head,
    list_nodes,
    read_node,
)

# ---------------------------------------------------------------------------
# Rendering constants
# ---------------------------------------------------------------------------

BOX_WIDTH = 28
COL_GAP = 4
COL_STRIDE = BOX_WIDTH + COL_GAP
EDGE_ROWS = 3
NODE_ROWS = 4  # top border, title, description, bottom border

# Styles
BORDER_STYLE = Style(color="#6272A4")
HEAD_BORDER_STYLE = Style(color="#50FA7B", bold=True)
FOCUSED_BG = Style(bgcolor="#44475A")
HEAD_TAG_STYLE = Style(color="#50FA7B", bold=True)
NODE_ID_STYLE = Style(bold=True)
DESC_STYLE = Style(color="#F8F8F2")
EDGE_STYLE = Style(color="#6272A4")


# ---------------------------------------------------------------------------
# Layout algorithm
# ---------------------------------------------------------------------------


def _build_graph(session_path: Path) -> tuple[list[str], dict, dict, dict]:
    """Build adjacency maps from session nodes.

    Returns (node_ids, parent_map, child_map, node_descs).
    """
    nodes = list_nodes(session_path)
    parent_map: dict[str, list[str]] = {}
    child_map: dict[str, list[str]] = {}
    node_descs: dict[str, str] = {}

    for nid in nodes:
        data = read_node(session_path, nid)
        parents = data.get("parents", [])
        # Only keep parents that actually exist as nodes
        parents = [p for p in parents if p in nodes]
        parent_map[nid] = parents
        node_descs[nid] = data.get("description", "")
        for p in parents:
            child_map.setdefault(p, []).append(nid)

    return nodes, parent_map, child_map, node_descs


def _assign_layers(
    nodes: list[str],
    parent_map: dict[str, list[str]],
    child_map: dict[str, list[str]],
) -> list[list[str]]:
    """Assign nodes to layers using topological ordering.

    Each node's layer = max(parent layers) + 1.
    Returns list of layers, each layer is a list of node IDs.
    """
    if not nodes:
        return []

    node_set = set(nodes)
    in_degree = {n: len(parent_map.get(n, [])) for n in nodes}
    layer_of: dict[str, int] = {}

    # Kahn's algorithm: start from roots (in_degree == 0)
    queue = deque(n for n in nodes if in_degree[n] == 0)

    # Fallback if no roots (cycle)
    if not queue:
        queue.append(nodes[0])

    for n in queue:
        layer_of[n] = 0

    processed = set()
    while queue:
        nid = queue.popleft()
        if nid in processed:
            continue
        processed.add(nid)

        for child in child_map.get(nid, []):
            if child not in node_set:
                continue
            # Layer = max of all parent layers + 1
            new_layer = layer_of[nid] + 1
            if child not in layer_of or layer_of[child] < new_layer:
                layer_of[child] = new_layer
            # Enqueue child only when ALL its parents are processed
            if all(p in processed for p in parent_map.get(child, [])):
                queue.append(child)

    # Nodes not reached go to layer 0
    for n in nodes:
        if n not in layer_of:
            layer_of[n] = 0

    max_layer = max(layer_of.values()) if layer_of else 0
    layers: list[list[str]] = [[] for _ in range(max_layer + 1)]
    for nid in nodes:  # preserve creation order within layers
        if nid in layer_of:
            layers[layer_of[nid]].append(nid)

    return layers


def _order_within_layers(
    layers: list[list[str]], parent_map: dict[str, list[str]]
) -> list[list[str]]:
    """Reorder nodes within each layer using barycenter heuristic."""
    if len(layers) <= 1:
        return layers

    for i in range(1, len(layers)):
        prev_positions = {nid: j for j, nid in enumerate(layers[i - 1])}

        def _bary(nid: str, pp: dict = prev_positions) -> float:
            parents = parent_map.get(nid, [])
            positions = [pp[p] for p in parents if p in pp]
            return sum(positions) / len(positions) if positions else 0.0

        layers[i].sort(key=_bary)

    return layers


# ---------------------------------------------------------------------------
# ASCII rendering
# ---------------------------------------------------------------------------


def _render_node_box(
    node_id: str,
    description: str,
    is_head: bool,
    is_focused: bool,
) -> list[Text]:
    """Render a single node box as BOX_WIDTH-wide Rich Text lines.

    Returns NODE_ROWS lines (top border, title, description, bottom border).
    """
    inner_w = BOX_WIDTH - 2  # inside the borders
    border_style = HEAD_BORDER_STYLE if is_head else BORDER_STYLE
    bg = FOCUSED_BG if is_focused else Style()

    # Title: node_id + optional HEAD tag
    head_tag = " HEAD" if is_head else ""
    title = f"{node_id}{head_tag}"
    if len(title) > inner_w:
        title = title[: inner_w - 1] + "\u2026"

    # Description: truncate to fit
    desc = description
    if len(desc) > inner_w - 1:
        desc = desc[: inner_w - 2] + "\u2026"

    lines: list[Text] = []

    # Row 0: top border +---...---+
    border_str = "+" + "-" * inner_w + "+"
    lines.append(Text(border_str, style=border_style + bg))

    # Row 1: title | n001  HEAD         |
    t = Text()
    t.append("|", style=border_style + bg)
    inner = Text()
    inner.append(node_id, style=NODE_ID_STYLE + bg)
    if is_head:
        inner.append(" HEAD", style=HEAD_TAG_STYLE + bg)
    pad = inner_w - len(inner.plain)
    if pad > 0:
        inner.append(" " * pad, style=bg)
    t.append_text(inner)
    t.append("|", style=border_style + bg)
    lines.append(t)

    # Row 2: description | Some description   |
    t2 = Text()
    t2.append("|", style=border_style + bg)
    t2.append(" " + desc.ljust(inner_w - 1), style=DESC_STYLE + bg)
    t2.append("|", style=border_style + bg)
    lines.append(t2)

    # Row 3: bottom border +---...---+
    lines.append(Text(border_str, style=border_style + bg))

    return lines


def _render_layer(
    layer: list[str],
    node_descs: dict[str, str],
    head: str | None,
    focused_id: str | None,
    total_width: int,
) -> list[Text]:
    """Render all node boxes in a layer as full-width lines."""
    # Build individual box lines
    boxes: list[list[Text]] = []
    for nid in layer:
        box = _render_node_box(
            node_id=nid,
            description=node_descs.get(nid, ""),
            is_head=(nid == head),
            is_focused=(nid == focused_id),
        )
        boxes.append(box)

    # Composite boxes into full-width lines
    result: list[Text] = []
    for row_idx in range(NODE_ROWS):
        line = Text()
        for col_idx, nid in enumerate(layer):
            x_pos = col_idx * COL_STRIDE
            # Pad from current position to box start
            gap = x_pos - len(line.plain)
            if gap > 0:
                line.append(" " * gap)
            line.append_text(boxes[col_idx][row_idx])
        # Pad to total_width
        remaining = total_width - len(line.plain)
        if remaining > 0:
            line.append(" " * remaining)
        result.append(line)

    return result


def _render_edges(
    layer_above: list[str],
    layer_below: list[str],
    parent_map: dict[str, list[str]],
    total_width: int,
) -> list[Text]:
    """Render edge rows connecting two adjacent layers.

    Returns EDGE_ROWS lines of Rich Text.
    """
    above_pos = {nid: i for i, nid in enumerate(layer_above)}
    below_pos = {nid: i for i, nid in enumerate(layer_below)}

    # Collect edges: (parent_col, child_col)
    edges: list[tuple[int, int]] = []
    for child in layer_below:
        for parent in parent_map.get(child, []):
            if parent in above_pos:
                edges.append((above_pos[parent], below_pos[child]))

    if not edges:
        return [Text(" " * total_width) for _ in range(EDGE_ROWS)]

    # Build character grid
    grid: list[list[str]] = [[" "] * total_width for _ in range(EDGE_ROWS)]

    def center_x(col: int) -> int:
        return col * COL_STRIDE + BOX_WIDTH // 2

    for p_col, c_col in edges:
        px = center_x(p_col)
        cx = center_x(c_col)

        if p_col == c_col:
            # Straight down
            for row in range(EDGE_ROWS):
                if 0 <= px < total_width:
                    grid[row][px] = "\u2502"  # │
        else:
            # Row 0: vertical down from parent
            if 0 <= px < total_width:
                grid[0][px] = "\u2502"  # │

            # Row 1: horizontal routing
            left_x = min(px, cx)
            right_x = max(px, cx)
            for x in range(left_x, right_x + 1):
                if 0 <= x < total_width:
                    if x == px and x == left_x:
                        grid[1][x] = "\u2514"  # └ (parent is left, going right)
                    elif x == px and x == right_x:
                        grid[1][x] = "\u2518"  # ┘ (parent is right, going left)
                    elif x == cx and x == left_x:
                        grid[1][x] = "\u250C"  # ┌ (child is left, coming from right)
                    elif x == cx and x == right_x:
                        grid[1][x] = "\u2510"  # ┐ (child is right, coming from left)
                    else:
                        if grid[1][x] == " ":
                            grid[1][x] = "\u2500"  # ─
                        elif grid[1][x] == "\u2502":
                            grid[1][x] = "\u253C"  # ┼ (crossing)

            # Row 2: vertical down to child
            if 0 <= cx < total_width:
                grid[2][cx] = "\u2502"  # │

    # Fix junctions where vertical lines pass through row 1
    for x in range(total_width):
        has_above = grid[0][x] == "\u2502"
        has_below = grid[2][x] == "\u2502"
        ch = grid[1][x]

        if has_above and has_below and ch == " ":
            grid[1][x] = "\u2502"  # │ straight through
        elif has_above and has_below and ch == "\u2500":
            grid[1][x] = "\u253C"  # ┼ crossing
        elif has_above and ch == "\u2500":
            grid[1][x] = "\u252C"  # ┬ (from above, continues horizontal)
        elif has_below and ch == "\u2500":
            grid[1][x] = "\u2534"  # ┴ (continues horizontal, exits below)

    # Convert grid to Rich Text
    return [Text("".join(row), style=EDGE_STYLE) for row in grid]


# ---------------------------------------------------------------------------
# DAGDisplay widget
# ---------------------------------------------------------------------------


class DAGDisplay(VerticalScroll):
    """ASCII art DAG visualization with keyboard-navigable nodes."""

    can_focus = True

    BINDINGS = [
        Binding("j", "next_node", "Next node", show=False),
        Binding("k", "prev_node", "Previous node", show=False),
    ]

    class NodeSelected(Message):
        """Emitted when Enter is pressed on a focused node."""

        def __init__(self, node_id: str) -> None:
            super().__init__()
            self.node_id = node_id

    class HeadChanged(Message):
        """Emitted when h is pressed to change HEAD."""

        def __init__(self, node_id: str) -> None:
            super().__init__()
            self.node_id = node_id

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._session_path: Path | None = None
        self._node_order: list[str] = []
        self._focused_idx: int = 0
        self._layers: list[list[str]] = []
        self._parent_map: dict[str, list[str]] = {}
        self._child_map: dict[str, list[str]] = {}
        self._node_descs: dict[str, str] = {}
        self._head: str | None = None
        self._node_line_map: dict[str, int] = {}

    def compose(self):
        yield Static("No DAG loaded", id="dag_display")

    def load_dag(self, session_path: Path) -> None:
        """Build layout from session data and render."""
        self._session_path = session_path

        nodes, parent_map, child_map, node_descs = _build_graph(session_path)
        self._parent_map = parent_map
        self._child_map = child_map
        self._node_descs = node_descs
        self._head = get_head(session_path)

        if not nodes:
            self.query_one("#dag_display", Static).update("No nodes in session")
            self._node_order = []
            return

        layers = _assign_layers(nodes, parent_map, child_map)
        layers = _order_within_layers(layers, parent_map)
        self._layers = layers

        # Flatten for navigation (top-to-bottom, left-to-right)
        self._node_order = []
        for layer in layers:
            self._node_order.extend(layer)

        # Clamp focus
        if self._focused_idx >= len(self._node_order):
            self._focused_idx = len(self._node_order) - 1
        if self._focused_idx < 0:
            self._focused_idx = 0

        self._render_dag()

    def _render_dag(self) -> None:
        """Build full DAG rendering and update display."""
        if not self._layers:
            return

        focused_id = (
            self._node_order[self._focused_idx]
            if self._node_order
            else None
        )

        max_cols = max(len(layer) for layer in self._layers)
        total_width = max(max_cols * COL_STRIDE - COL_GAP, BOX_WIDTH)

        all_lines: list[Text] = []
        self._node_line_map = {}

        for layer_idx, layer in enumerate(self._layers):
            # Record line positions for scroll-to-focus
            for nid in layer:
                self._node_line_map[nid] = len(all_lines)

            layer_lines = _render_layer(
                layer, self._node_descs, self._head, focused_id, total_width,
            )
            all_lines.extend(layer_lines)

            # Edge rows to next layer
            if layer_idx < len(self._layers) - 1:
                edge_lines = _render_edges(
                    layer, self._layers[layer_idx + 1],
                    self._parent_map, total_width,
                )
                all_lines.extend(edge_lines)

        # Join all lines
        result = Text()
        for i, line in enumerate(all_lines):
            if i > 0:
                result.append("\n")
            result.append_text(line)

        self.query_one("#dag_display", Static).update(result)

        # Scroll to focused node
        if focused_id and focused_id in self._node_line_map:
            target_y = self._node_line_map[focused_id]
            self.scroll_to(0, target_y, animate=False)

    def on_key(self, event) -> None:
        """Handle Enter and h keys."""
        if not self._node_order:
            return

        focused_id = self._node_order[self._focused_idx]

        if event.key == "enter":
            self.post_message(self.NodeSelected(focused_id))
            event.prevent_default()
            event.stop()
        elif event.key == "h":
            self.post_message(self.HeadChanged(focused_id))
            event.prevent_default()
            event.stop()

    def action_next_node(self) -> None:
        """Move focus to next node (j key)."""
        if self._focused_idx < len(self._node_order) - 1:
            self._focused_idx += 1
            self._render_dag()

    def action_prev_node(self) -> None:
        """Move focus to previous node (k key)."""
        if self._focused_idx > 0:
            self._focused_idx -= 1
            self._render_dag()
