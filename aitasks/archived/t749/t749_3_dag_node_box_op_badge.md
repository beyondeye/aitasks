---
priority: high
effort: low
depends: [t749_2]
issue_type: enhancement
status: Done
labels: [ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-05 10:41
updated_at: 2026-05-06 12:20
completed_at: 2026-05-06 12:20
---

## Context

Add a colored `[<operation>]` badge row inside each DAG node box in
`brainstorm_dag_display.py`. This is the most visible, at-a-glance
provenance signal asked for by the user — when scanning the DAG, a
glance tells you whether a node came from `[explore]`, `[hybridize]`,
`[detail]`, etc.

Depends on t749_1 (br_groups.yaml population) so the operation lookup
works for non-legacy sessions.

## Key Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_dag_display.py` — bump
  `NODE_ROWS` from 4 to 5 and render a third inner row (badge)
  between title and description in `_render_node_box`. Build a
  `node_id -> operation` map in `_build_graph` by joining
  `created_by_group` (per node) with `br_groups.yaml`.

## Reference Files for Patterns

- `brainstorm_dag_display.py:162-217` — current `_render_node_box`
  with its inner_w/border_str logic. Mirror the existing per-row
  Text-with-style construction style.
- `brainstorm_dag_display.py:55-75` — `_build_graph` already reads
  per-node yaml; piggy-back the operation lookup there.
- The existing `HEAD_BORDER_STYLE`, `BORDER_STYLE`, `HEAD_TAG_STYLE`
  constants at lines 41-47 — add op-type colors in the same style.

## Implementation Plan

1. Constants at the top of `brainstorm_dag_display.py`:
   ```python
   NODE_ROWS = 5  # was 4
   OP_BADGE_STYLES = {
       "explore":   Style(color="#8BE9FD"),  # cyan
       "compare":   Style(color="#F1FA8C"),  # yellow
       "hybridize": Style(color="#FF79C6"),  # magenta
       "detail":    Style(color="#BD93F9"),  # purple
       "patch":     Style(color="#FF5555"),  # red
       "bootstrap": Style(color="#6272A4"),  # dim
   }
   UNKNOWN_OP_STYLE = Style(color="#6272A4", italic=True)
   ```

2. Modify `_build_graph(session_path)` to also return a
   `node_op_map: dict[str, str]` — read `br_groups.yaml` once and join:
   ```python
   from .brainstorm_session import GROUPS_FILE
   from agentcrew.agentcrew_utils import read_yaml
   groups_path = session_path / GROUPS_FILE
   groups = {}
   if groups_path.is_file():
       gdata = read_yaml(str(groups_path)) or {}
       groups = gdata.get("groups", {}) or {}
   node_op_map = {}
   for nid in nodes:
       data = read_node(session_path, nid)
       group_name = data.get("created_by_group", "")
       op = (groups.get(group_name) or {}).get("operation", "?")
       node_op_map[nid] = op
   ```
   Update the return tuple to `(nodes, parent_map, child_map,
   node_descs, node_op_map)`. Update the single caller
   (`DAGDisplay.load_dag`).

3. Modify `_render_node_box(...)` signature to accept `operation: str`.
   Insert a new badge row between title (row 1) and description (now
   row 3):
   ```python
   # Row 2: operation badge | [explore]                  |
   t_b = Text()
   t_b.append("|", style=border_style + bg)
   badge_inner = Text()
   if operation and operation != "?":
       badge_text = f"[{operation}]"
       badge_style = OP_BADGE_STYLES.get(operation, UNKNOWN_OP_STYLE)
       badge_inner.append(" " + badge_text, style=badge_style + bg)
   else:
       badge_inner.append("", style=bg)
   pad = inner_w - len(badge_inner.plain)
   if pad > 0:
       badge_inner.append(" " * pad, style=bg)
   t_b.append_text(badge_inner)
   t_b.append("|", style=border_style + bg)
   lines.append(t_b)
   ```
   Renumber the description row (now row 3) and bottom border (now
   row 4).

4. Modify `_render_layer(...)` to pass `node_op_map[nid]` to
   `_render_node_box`. Threading: `_render_layer` receives the new
   map from `DAGDisplay._render_dag`.

5. Make sure all existing call sites that compute layer height now
   account for `NODE_ROWS = 5` (search for any literal `4` referencing
   row counts in the file).

## Verification Steps

1. Add `tests/test_brainstorm_dag_op_badge.sh` (bash test) that:
   - Creates a tmp session via `init_session(...)`.
   - Records an explore operation via `record_operation(...)`.
   - Manually creates a node with `created_by_group="explore_001"`.
   - Calls `_build_graph(...)` and asserts the returned
     `node_op_map[<nid>] == "explore"`.
   - Renders `_render_node_box(node_id, desc, is_head=False,
     is_focused=False, operation="explore")` and asserts the result
     contains `[explore]` in row 2 with the cyan color attribute.

2. Manually launch the brainstorm TUI on a session with multiple ops;
   visually confirm each non-root node shows a colored op badge row.
   Confirm legacy session (with empty br_groups.yaml) renders boxes
   without breakage (badge row blank, no `[?]`).

## Notes for Sibling Tasks

- The op-badge color map (`OP_BADGE_STYLES`) becomes shared semantic
  data. Sibling t749_4 (dashboard pane) and t749_5
  (OperationDetailScreen header) should reuse it; **import the
  constant**, do not redefine it.
- Empty op (legacy session) renders as a blank badge row, not `[?]`.
  Don't draw attention to missing data — just leave the row white-
  space.
- Layer height = `NODE_ROWS * len(layers) + EDGE_ROWS * (len(layers) -
  1)`. Bumping `NODE_ROWS` to 5 increases overall DAG height by 1 row
  per layer — fine, the view scrolls.
