---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: high
depends: [t983_3]
issue_type: refactor
status: Done
labels: [brainstorming, tui, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-14 11:39
updated_at: 2026-06-16 11:20
completed_at: 2026-06-16 11:20
---

## Context
Child of t983. Unifies the two ways to run node ops (the Actions-tab wizard op
list AND the `A` `NodeActionSelectModal`) into ONE contextual **Operations**
dialog driven by selection cardinality (t983_2 `NodeSelection`). Today
`NodeActionSelectModal` (`.aitask-scripts/brainstorm/brainstorm_app.py:2235`)
offers single-node ops only (explore, fast_track, module_decompose/merge/sync,
delete); it does NOT include the multi-node ops compare/synthesize. This child
extends it and makes the enable/disable logic pure.

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — extend `NodeActionSelectModal`
  (→ "Operations") with design ops + multi-node ops; refactor
  `_node_action_op_states` (:3939) into a **pure** function taking selection
  cardinality; fold in the Actions-tab op list with descriptions; repoint the
  `H`→`OperationHelpModal` gate.
- `tests/test_brainstorm_node_action_relevance.py` — extend for cardinality.
- `tests/test_brainstorm_node_action_modal.py` — update.

## Reference Files for Patterns
- `op_states: dict[str, tuple[bool,str]]` (disabled+reason) pattern already in
  `NodeActionSelectModal` (:2235) + `_node_action_op_states` (:3939).
- `_OPERATION_HELP` (:248), `_OP_LABELS`, `OperationHelpModal`, `action_op_help`
  (:4294) — the discoverability text that MUST be preserved.

## Implementation Plan
1. Refactor `_node_action_op_states(node_id)` → pure
   `op_states_for_selection(node_ctx, cardinality)`: single-node ops
   (explore/module_*/fast_track/delete) greyed-with-reason when cardinality > 1;
   multi-node ops (compare/synthesize) greyed when cardinality < 2.
2. Extend the modal's op list to include all design + multi-node ops; reuse the
   existing OperationRow disabled-with-reason rendering.
3. Fold the Actions-tab op list + its descriptions into this dialog; ensure
   `_OPERATION_HELP` / `H` help still resolves from the new host (repoint the
   `tabbed.active == "tab_actions"` gate at :4302 / :3474).
4. Choosing an op will (in t983_6) launch the seeded wizard — for now wire the
   selection through; do not yet re-host the wizard.

## Verification
- Pure unit: `tests/test_brainstorm_node_action_relevance.py` — cardinality cases
  (N>1 greys single-node ops; N<2 greys compare/synthesize; reasons correct).
- Pilot: `H` help resolves for an op from the Operations dialog;
  `test_brainstorm_node_action_modal.py` updated + green.
- Manual: `A` on Browse opens Operations; ops grey by selection size.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-16T08:01:02Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-16T08:01:03Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-16T08:19:49Z status=pass attempt=1 type=human
