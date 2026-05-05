---
Task: t749_3_dag_node_box_op_badge.md
Parent Task: aitasks/t749_report_operation_that_generated_nod.md
Sibling Tasks: aitasks/t749/t749_1_*.md, aitasks/t749/t749_2_*.md, aitasks/t749/t749_4_*.md, aitasks/t749/t749_5_*.md, aitasks/t749/t749_6_*.md, aitasks/t749/t749_7_*.md
Archived Sibling Plans: aiplans/archived/p749/p749_*_*.md
Worktree: (current branch — no separate worktree)
Branch: main
Base branch: main
---

# Plan: DAG node-box operation badge (t749_3)

## Context

Add a colored `[<operation>]` row inside each DAG node box. Provides
an at-a-glance "what produced this node" cue without opening any
modal.

Bumps `NODE_ROWS` from 4 to 5. Layer height grows by 1 row.

## Implementation Steps

### Step 1 — Constants

In `brainstorm_dag_display.py`, change `NODE_ROWS = 4` to `NODE_ROWS = 5`
and add the op-color map (Dracula palette to match existing
`HEAD_BORDER_STYLE`):

```python
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

### Step 2 — Update `_build_graph`

Currently returns `(nodes, parent_map, child_map, node_descs)`. Extend
to `(nodes, parent_map, child_map, node_descs, node_op_map)` by:

1. Reading `br_groups.yaml` once at the top.
2. For each node, joining `created_by_group` against the groups dict
   to derive the operation type.
3. Defaulting to `"?"` when the group entry is missing (legacy
   sessions).

### Step 3 — Update `_render_node_box`

Add an `operation: str` parameter and insert a new badge row between
title (now row 1) and description (now row 3). See the task
description for the per-row Text construction snippet.

### Step 4 — Thread the op map

`DAGDisplay._render_dag` calls `_render_layer(layer, node_descs, head,
focused_id, total_width)` — extend the signature to also pass
`node_op_map`. `_render_layer` passes `node_op_map[nid]` to
`_render_node_box`.

### Step 5 — Test

`tests/test_brainstorm_dag_op_badge.sh`:

- `init_session(...)`, `record_operation(..., "explore")`, manually
  drop a node yaml with `created_by_group="explore_001"`.
- Call `_build_graph` and assert `node_op_map[<nid>] == "explore"`.
- Render `_render_node_box(...)` and assert the rendered text has
  `[explore]` on row 2 and 5 rows total.

## Files Modified

- `.aitask-scripts/brainstorm/brainstorm_dag_display.py` — ~30 LOC
- `tests/test_brainstorm_dag_op_badge.sh` — NEW

## Verification

1. `bash tests/test_brainstorm_dag_op_badge.sh` passes.
2. Manually run brainstorm with multiple ops; visually verify the
   badge row.
3. Verify legacy session (empty br_groups.yaml) still renders
   correctly with a blank badge row (no `[?]` shown).

## Step 9 (Post-Implementation)

Standard archival flow.

## Verification

(Aggregated under the parent task's manual-verification sibling.)
