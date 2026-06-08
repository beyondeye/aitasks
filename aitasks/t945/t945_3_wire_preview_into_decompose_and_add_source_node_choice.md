---
priority: medium
effort: medium
depends: [t945_2]
issue_type: feature
status: Ready
labels: [ait_brainstorm, brainstorm_explore]
created_at: 2026-06-08 09:31
updated_at: 2026-06-08 09:31
---

## Context

Part of t945. Two deliverables for the **module-decompose** wizard:
1. **Source-node choice (new requirement raised by the user):** today
   module-decompose auto-uses the subgraph HEAD (`get_head`) and gives no node
   choice, unlike explore. Let the user pick the source node within the chosen
   subgraph, defaulting to HEAD.
2. **Preview wiring:** show the chosen source node's proposal side-by-side with
   the Decomposition Plan input, using the component from t945_1.

Depends on t945_1 and t945_2 (sibling auto-dependency).

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py`
  - Wizard step machinery (`_WIZARD_STEPS`, line 1744; op sets line 157):
    add module-decompose source-node selection **without** triggering the
    `section_select` step.
  - `_config_module_decompose` (line 6962): refactor to use
    `_mount_config_with_preview`; right pane shows
    `read_proposal(session, <chosen source node>)`.
  - `_actions_collect_config` module_decompose branch (line 7201): change
    `config["source_node"] = get_head(...)` (line 7203) to the user-chosen
    node (still defaulting to HEAD when unchanged).

## Blast-radius note (decide approach in implementation)
`module_decompose` is in `_SUBGRAPH_SELECT_OPS` but NOT `_NODE_SELECT_OPS`
(`brainstorm_app.py:157`). The `section_select` step is gated on
`op in _NODE_SELECT_OPS and node_has_sections` (line 1755). **Naively adding
`module_decompose` to `_NODE_SELECT_OPS` would also activate `section_select`**
— an unwanted side effect for decompose. Preferred approach: add a dedicated
node-select step (or a new predicate) gated on `op == "module_decompose"`, OR
make the `section_select` predicate explicitly exclude module_decompose. Keep
HEAD as the default selection. Confirm `_NODE_SELECT_OPS` is not consumed
elsewhere in a way that would regress (grep usages before changing the set).

## Reference Files for Patterns
- Explore's node-select flow (the UX to mirror): `node_select` step
  (`_WIZARD_STEPS` line 1754), `_NODE_SELECT_OPS` (line 157), and how
  `_selected_node` is set/consumed in `_wizard_config`.
- `_mount_config_with_preview` + `ProposalPreviewPane` (t945_1).
- `get_head` (`brainstorm/brainstorm_dag.py:135`), `read_proposal`
  (`brainstorm/brainstorm_dag.py:514`), `list_nodes` / subgraph node listing.
- Current decompose config: `_config_module_decompose`
  (`brainstorm_app.py:6962`); collectors at line 7201 (class-based queries
  `.ta_module_decompose_modules` / `.ta_module_decompose_plan`, robust to a
  wrapper).

## Implementation Plan
1. **Source-node selection:** add the node-select step for module_decompose
   (default HEAD) per the blast-radius approach above; store the choice in
   `_wizard_config`. Verify `subgraph_select` still runs first and the new
   node list is scoped to that subgraph.
2. **Collector:** replace `get_head(...)` at line 7203 with the chosen node
   (fall back to `get_head` if none chosen). Keep the empty-HEAD warning.
3. **Preview wiring:** refactor `_config_module_decompose` to build its
   existing widgets (RadioSet `rs_decompose_mode`, the two module/plan
   TextAreas, the two checkboxes, Next) via the `left_builder`, and pass
   `read_proposal(session, <chosen node>)` to the right pane.

## Verification Steps
- Launch `ait brainstorm`; run module-decompose → subgraph select → new
  source-node select (defaults to HEAD) → config. Confirm the chosen node's
  proposal shows on the right with a working minimap; the decompose runs
  against the chosen node; and `section_select` does NOT appear for decompose.
- Re-run explore to confirm the node-select changes did not regress it.
