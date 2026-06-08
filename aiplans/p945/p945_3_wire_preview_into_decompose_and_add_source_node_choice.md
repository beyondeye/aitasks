---
Task: t945_3_wire_preview_into_decompose_and_add_source_node_choice.md
Parent Task: aitasks/t945_show_proposal_viewer_side_by_side_to_explore_and_decompose.md
Sibling Tasks: aitasks/t945/t945_1_reusable_proposal_preview_pane.md, aitasks/t945/t945_2_wire_preview_into_explore_wizard.md
Archived Sibling Plans: aiplans/archived/p945/p945_*_*.md
Worktree: aiwork/t945_3_wire_preview_into_decompose_and_add_source_node_choice
Branch: aitask/t945_3_wire_preview_into_decompose_and_add_source_node_choice
Base branch: main
---

# t945_3 — Wire preview into module-decompose + add source-node choice

## Context

Third child of t945. Two deliverables for the **module-decompose** wizard:

1. **Source-node choice (new requirement from the user):** today
   module-decompose auto-uses the subgraph HEAD (`get_head`) with no node
   choice, unlike explore. Let the user pick the source node within the chosen
   subgraph, defaulting to HEAD.
2. **Preview wiring:** show the chosen source node's proposal side-by-side with
   the Decomposition Plan input, using the component from t945_1.

Depends on t945_1 and t945_2 (read their archived plans
`aiplans/archived/p945/p945_1_*.md` and `p945_2_*.md` — t945_2 establishes the
explore wiring pattern this child mirrors).

## Existing pieces to reuse
- `_mount_config_with_preview` + `ProposalPreviewPane` (from t945_1).
- Explore's node-select flow (the UX to mirror): `node_select` step
  (`_WIZARD_STEPS` line 1754), `_NODE_SELECT_OPS` (line 157), how
  `_selected_node` is set/consumed in `_wizard_config`.
- `get_head` (`brainstorm/brainstorm_dag.py:135`), `read_proposal`
  (`brainstorm/brainstorm_dag.py:514`), node-listing helpers (`list_nodes`).
- Current decompose config: `_config_module_decompose`
  (`brainstorm_app.py:6962`); collectors at `brainstorm_app.py:7201`.

## Blast-radius analysis (decide approach early)
`module_decompose` is in `_SUBGRAPH_SELECT_OPS` but **not** `_NODE_SELECT_OPS`
(`brainstorm_app.py:157`). The `section_select` step is gated on
`op in _NODE_SELECT_OPS and node_has_sections` (`_WIZARD_STEPS`, line 1755).

> Naively adding `module_decompose` to `_NODE_SELECT_OPS` would also activate
> `section_select` for decompose — an unwanted side effect.

Before changing anything, `grep` every use of `_NODE_SELECT_OPS` to map the
blast radius. Preferred approaches (pick one in implementation):
- (a) Add a dedicated node-select wizard step gated on
  `op == "module_decompose"` (new predicate), independent of `_NODE_SELECT_OPS`; OR
- (b) Add `module_decompose` to `_NODE_SELECT_OPS` **and** tighten the
  `section_select` predicate to exclude `module_decompose`.
Approach (a) is lower-risk (no change to existing node-select ops). Default to
HEAD as the pre-selected node.

## Implementation steps
1. **Source-node selection:** per the chosen approach, present a node-select
   step for module-decompose scoped to the selected subgraph, pre-selecting
   `get_head(session, module=subgraph)`. Store the choice in `_wizard_config`
   (e.g. `_selected_node`, consistent with explore). Ensure `subgraph_select`
   still runs first.
2. **Collector:** in `_actions_collect_config` module_decompose branch
   (`brainstorm_app.py:7201`), replace
   `config["source_node"] = get_head(self.session_path, module=self._wizard_subgraph)`
   (line 7203) with the user-chosen node, falling back to `get_head` when none
   chosen. Keep the empty-HEAD warning.
3. **Preview wiring:** refactor `_config_module_decompose`
   (`brainstorm_app.py:6962`) to build its existing widgets — the
   `rs_decompose_mode` `RadioSet`, the `.ta_module_decompose_modules` and
   `.ta_module_decompose_plan` `TextArea`s, the `.chk_link_to_task` /
   `.chk_review_before_apply` checkboxes, and the Next button — inside a
   `left_builder`, and pass `read_proposal(session, <chosen node>)` to the
   right pane via `_mount_config_with_preview`. The class-based collectors are
   robust to the new wrapper.

## Verification
- Launch `ait brainstorm`; run module-decompose → subgraph select → new
  source-node select (defaults to HEAD) → config. Confirm: the chosen node's
  proposal shows on the right with a working minimap; the decompose runs
  against the chosen node; and `section_select` does NOT appear for decompose.
- Re-run explore (t945_2 flow) to confirm the node-select / op-set changes did
  not regress it.
- Run touched brainstorm app tests under `tests/`.

## Reference to parent workflow
On completion follow task-workflow Step 8 (review) → Step 9 (archival). When
all three children are done, parent t945 archives.
