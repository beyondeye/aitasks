---
priority: high
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-17 10:11
updated_at: 2026-05-17 11:12
---

## Context

Part of t748 (parent: `aitasks/t748_browsable_node_graph.md`, plan: `aiplans/p748_browsable_node_graph.md`). This child adds 2D arrow-key navigation to the brainstorm Graph tab's `DAGDisplay` widget.

Currently the DAG is navigable only via `j` / `k` (flat top-to-bottom-left-to-right order). Users want true 2D nav matching the visual layout: `up`/`down` between layers, `left`/`right` within a layer. Arrow bindings must be `show=True` so the Textual footer surfaces them while the Graph tab is focused (the user has explicitly asked for this — arrow keys default to `show=False` in many Textual apps).

## Key Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_dag_display.py` (only file touched by this child)

## Reference Files for Patterns

- Existing `DAGDisplay.BINDINGS` at `brainstorm_dag_display.py:407-412` (shows the `show=True` convention already used for `j`/`k`/`Enter`/`h`/`o`).
- Existing `action_next_node` / `action_prev_node` at lines 537-547 (the flat `_focused_idx` walk that arrow nav extends).
- `_layers: list[list[str]]` populated in `load_dag` (line 472) — the 2D structure to derive `(layer_idx, col_idx)` from.
- `_node_order` flat list (line 475-477) — keep in sync so `j`/`k` continues to work.

## Implementation Plan

1. Add four new `Binding` entries to `DAGDisplay.BINDINGS` with `show=True`:
   - `Binding("up", "prev_layer", "↑ Layer", show=True)`
   - `Binding("down", "next_layer", "↓ Layer", show=True)`
   - `Binding("left", "prev_col", "← Col", show=True)`
   - `Binding("right", "next_col", "→ Col", show=True)`
2. Derive current `(layer_idx, col_idx)` from `_focused_idx` and `_layers` at action time (no need to store both — compute on demand).
3. `action_prev_layer` / `action_next_layer`: clamp at first/last layer; snap to the column in the target layer whose horizontal CENTER is closest to the current column's center. Use existing layout constants (`COL_STRIDE`, `BOX_WIDTH`) for center calculation.
4. `action_prev_col` / `action_next_col`: move within current layer; clamp at edges (no wrap).
5. All four actions update `_focused_idx` (recomputed from the new `(layer_idx, col_idx)` via the flat `_node_order`) and call `self._render_dag()`.
6. `j` / `k` continue unchanged.
7. Confirm `TuiSwitcherMixin`'s `j` priority binding does not intercept `j` while DAGDisplay is focused. If a conflict surfaces, document it as a known issue in the plan file's Final Implementation Notes (Step 8).

## Verification Steps

1. Launch `ait brainstorm` on a session with a multi-layer DAG.
2. Tab to the (G)raph tab; observe footer shows `↑ Layer`, `↓ Layer`, `← Col`, `→ Col` along with existing `j`/`k`/`Enter`/`h`/`o`.
3. Press `left`/`right` — focus moves within the current layer, clamps at edges.
4. Press `up`/`down` — focus moves to the column whose center is closest to the current one in the adjacent layer.
5. Press `j`/`k` — flat walk still works, including across layer boundaries.
6. Switch to another tab and back — focus is preserved.

## Notes for Sibling Tasks

- Add a `DAGDisplay.FocusChanged(node_id)` message post in all four new actions if t748_2 is being implemented in the same session (t748_2 owns the message class declaration — coordinate at sibling-implementation time).
- Keep `_focused_idx` as the canonical "where am I" state — don't introduce a separate `_layer_idx` attribute. Derive on the fly to avoid drift.
