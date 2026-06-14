---
Task: t983_4_operations_dialog_cardinality.md
Parent Task: aitasks/t983_redesign_brainstorm_tui_ux_unified_browse_contextual_ops.md
Sibling Tasks: aitasks/t983/t983_*_*.md
Archived Sibling Plans: aiplans/archived/p983/p983_*_*.md
Worktree: aiwork/t983_4_operations_dialog_cardinality
Branch: aitask/t983_4_operations_dialog_cardinality
Base branch: main
---

# p983_4 — Operations dialog (cardinality-driven)

Child of t983. Unify the two op entry points (Actions-tab wizard op list + the
`A` `NodeActionSelectModal`) into ONE contextual **Operations** dialog. Lands
before the Node Hub (t983_5) so the Hub can open it.

## Goal
Extend `NodeActionSelectModal`
(`.aitask-scripts/brainstorm/brainstorm_app.py:2235`, today single-node ops only)
to "Operations" covering design + multi-node ops, greyed by selection cardinality
(t983_2 `NodeSelection`), preserving `_OPERATION_HELP` discoverability.

## Steps
1. Refactor `_node_action_op_states(node_id)` (:3939) → **pure**
   `op_states_for_selection(node_ctx, cardinality)`: single-node ops
   (explore/module_*/fast_track/delete) greyed-with-reason at cardinality > 1;
   compare/synthesize greyed at cardinality < 2.
2. Extend the modal op list to include design + multi-node ops; reuse the existing
   `OperationRow` disabled-with-reason rendering + `op_states` map.
3. Fold the old Actions-tab op list + descriptions into this dialog; ensure
   `_OPERATION_HELP` (:248) / `H` → `OperationHelpModal` (`action_op_help`, :4294)
   still resolves — repoint its `tabbed.active == "tab_actions"` gate (:4302/:3474)
   to the new host.
4. Wire the contextual selection through (wizard re-host/seeding is t983_6).

## Verification
- Pure unit: extend `tests/test_brainstorm_node_action_relevance.py` (already
  tests `_node_action_op_states`) with cardinality cases + reason strings.
- Pilot: `H` help resolves from the Operations dialog;
  `test_brainstorm_node_action_modal.py` updated + green.
- Manual: `A` on Browse opens Operations; ops grey by selection size.

## Step 9
Archive via `./.aitask-scripts/aitask_archive.sh 983_4`.
