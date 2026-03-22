---
Task: t423_3_dag_visualization_ascii_art_graph.md
Parent Task: aitasks/t423_design_and_finalize_brainstorm_tui.md
Sibling Tasks: aitasks/t423/t423_4_*.md through t423_11_*.md
Archived Sibling Plans: aiplans/archived/p423/p423_1_*.md, aiplans/archived/p423/p423_2_*.md
Worktree: (none - working on current branch)
Branch: (current)
Base branch: main
---

## Context

Implement the DAG visualization tab (Tab 2) rendering an ASCII art graph of proposal nodes. Must handle multi-parent merges (hybridizations) which a tree widget cannot represent. Uses a custom layout algorithm.

## Architecture

**New file: `.aitask-scripts/brainstorm/brainstorm_dag_display.py`** — Contains `DAGDisplay(VerticalScroll)` widget plus all layout/rendering logic. Follows the `diffviewer/diff_display.py` pattern (VerticalScroll subclass + Rich Text rendering into a Static widget).

**Modify: `.aitask-scripts/brainstorm/brainstorm_app.py`** — Import DAGDisplay, replace DAG tab placeholder, wire up navigation/actions.

## Implementation

### Step 1: Create `brainstorm_dag_display.py` — Layout Algorithm

Simplified Sugiyama approach:
- `_build_graph(session_path)` → build parent_map, child_map, node_descs from `list_nodes` + `read_node`
- **Layer assignment:** BFS from roots. Each node's layer = max(parent layers) + 1.
- **Ordering within layers:** Barycenter heuristic — sort by average parent column position.

### Step 2: ASCII Renderer

Render as Rich `Text` lines:
- **Node boxes** (4 lines): `+--borders--+` with node_id + `[HEAD]` tag + truncated description
  - BOX_WIDTH=28, COL_STRIDE=32
  - HEAD: green border color
  - Focused: accent background highlight
- **Edge rows** (3 lines between layers): grid-based routing
  - Same column: `│` straight down
  - Different columns: `└───┐` / `┌───┘` routing with `┬`/`┴` junctions
  - Multi-parent merge: converging lines with `┬` junction

### Step 3: DAGDisplay Widget

`DAGDisplay(VerticalScroll)` with:
- `compose()`: yields `Static("", id="dag_display")`
- `load_dag(session_path)`: builds layout + renders
- `_render()`: builds Rich Text, updates Static
- j/k bindings → `action_next_node`/`action_prev_node` → re-render + scroll
- Enter/h in `on_key()` → post `NodeSelected`/`HeadChanged` messages
- `_node_order: list[str]` for flat navigation order
- `_focused_idx: int` for current focus

### Step 4: Integrate into `brainstorm_app.py`

- Add import: `from brainstorm.brainstorm_dag_display import DAGDisplay`
- Add import: `from brainstorm.brainstorm_dag import set_head`
- Replace DAG tab placeholder (lines 301-308) with `yield DAGDisplay(id="dag_content")`
- Remove `#dag_placeholder` from CSS
- Add `DAGDisplay { height: 1fr; padding: 1 2; }` CSS
- Add `on_dag_display_node_selected()` → push NodeDetailModal
- Add `on_dag_display_head_changed()` → set_head + refresh DAG + dashboard
- Add `self.query_one(DAGDisplay).load_dag(self.session_path)` in `_load_existing_session()`

### Reference Files
- `.aitask-scripts/brainstorm/brainstorm_dag.py` — `list_nodes()`, `get_head()`, `get_children()`, `get_parents()`, `read_node()`, `set_head()`
- `.aitask-scripts/diffviewer/diff_display.py` — VerticalScroll + Rich Text rendering pattern
- `.aitask-scripts/brainstorm/brainstorm_app.py` — NodeRow, NodeDetailModal, TabbedContent integration

### Manual Verification
1. Linear chain renders as vertical stack with `│` arrows
2. Hybrid node (n003 ← n001, n002) shows converging arrows
3. HEAD node visually distinct (green, `[HEAD]` tag)
4. j/k moves focus, Enter opens detail, h sets HEAD
5. Scrolling follows focused node for tall graphs

## Post-Implementation

Follow Step 9 of the task workflow (testing, verification, commit).
