---
priority: medium
effort: high
depends: [t423_2]
issue_type: feature
status: Implementing
labels: [brainstorming, tui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-20 12:40
updated_at: 2026-03-22 11:41
---

## Context
Implement the DAG visualization tab (Tab 2) rendering an ASCII art graph of proposal nodes. Must handle multi-parent merges (hybridizations) which a tree widget cannot represent. Uses a custom layout algorithm.

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — Replace DAG tab placeholder with DAGDisplay widget

## Reference Files for Patterns
- `.aitask-scripts/brainstorm/brainstorm_dag.py` — `list_nodes()`, `get_head()`, `get_children()`, `get_parents()`, `read_node()`
- `.aitask-scripts/diffviewer/diff_display.py` — Custom VerticalScroll widget with Rich Text rendering

## Implementation
1. Create `DAGDisplay(VerticalScroll)` custom widget
2. Implement layout algorithm:
   a. Topological sort of nodes
   b. Layer assignment (rank nodes by depth from roots)
   c. Crossing minimization (reorder nodes within layers)
   d. Coordinate assignment (x/y positions for each node)
3. Render nodes as boxes (+-borders) with node_id + short description
4. Render edges as pipe/dash/arrow characters between layers
5. Multi-parent merges: converging arrows from multiple sources into one node
6. HEAD node: distinct color/border
7. Focusable nodes: j/k navigation, highlight focused node
8. Enter → push NodeDetailModal; h → set_head()
9. Scrollable for graphs taller than terminal height

## Manual Verification
1. Linear chain renders as vertical stack with arrows
2. Hybrid node (n003 ← n001, n002) shows converging arrows
3. HEAD node visually distinct
4. j/k moves focus, Enter opens detail, h sets HEAD
