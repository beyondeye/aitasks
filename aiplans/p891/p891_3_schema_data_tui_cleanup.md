---
Task: t891_3_schema_data_tui_cleanup.md
Parent Task: aitasks/t891_brainstorm_proposal_only_retire_plans.md
Sibling Tasks: aitasks/t891/t891_1_decision_docs_v2_architecture.md, aitasks/t891/t891_2_ops_agents_removal.md, aitasks/t891/t891_4_finalize_proposal_export.md
Worktree: (decide at pick time)
Branch: aitask/t891_3_schema_data_tui_cleanup
Base branch: main
---

# Plan — t891_3: remove plan_file / br_plans data + plan TUI surfaces

> **⚠️ DEFERRED — gated on the t756 chain (after t891_2). Re-verify anchors
> against as-landed code (2026-06-01 snapshot; locate by symbol name).** No
> migration — `ait brainstorm` is unshipped; remove `plan_file` nodes/`br_plans/`
> outright.

## Code anchors (2026-06-01 snapshot — verify by name)

`.aitask-scripts/brainstorm/brainstorm_schemas.py`
- `NODE_OPTIONAL_FIELDS` (~L17) — remove `"plan_file"`.

`.aitask-scripts/brainstorm/brainstorm_dag.py`
- `PLANS_DIR = "br_plans"` (~L24), `read_plan` (~L212) — remove; remove any
  `br_plans/` mkdir.

`.aitask-scripts/brainstorm/brainstorm_app.py`
- `NodeDetailModal` (~L691): Plan tab (~L726), `read_plan(...)` call (~L784),
  plan minimap (~L788-795) — remove.
- `_node_has_plan` (~L5913) and the patch-wizard gate `if self._wizard_op ==
  "patch" and not self._node_has_plan(node)` (~L5617) — remove (patch op gone).
- `l`/`V` plan key bindings + plan-view actions/messages — remove.

`.aitask-scripts/brainstorm/brainstorm_dag_display.py`
- `node_has_plan_map`(~L95)/`has_plan`(~L213) plumbing, badge rendering ●/○
  (~L254-257, build sites ~L303-307/~L607), `Binding("l","view_plan",...)`
  (~L459), `PlanRequested`(~L500), `action_view_plan`(~L826) — remove. Also
  `_node_has_plan_map` instance state (~L531) and its `_build_graph` read (~L544).

`.aitask-scripts/brainstorm/brainstorm_session.py`
- Remove `"plan_file"` from `_NODE_NON_DIMENSION_FIELDS` (~L511) if not already
  removed by t891_2.

## Preserve
Node metadata + proposal model, dimensions, section markers (t873), and the
surviving node-detail tabs/bindings.

## Steps
1. Verify symbols against as-landed code.
2. Drop `plan_file` schema field → `read_plan`/`PLANS_DIR` → TUI surfaces (modal
   tab, bindings, badges, wizard gate) → residual field-stripping refs.
3. grep `plan_file|read_plan|PLANS_DIR|br_plans|node_has_plan|view_plan|
   PlanRequested`; clean dead code + imports.

## Verification
- The grep above returns nothing live.
- `.py` files parse; brainstorm tests pass.
- Manual `ait brainstorm`: no Plan tab in node-detail modal; no ●/○ plan badges;
  `l`/`V` unbound from plan view; opening a previously-planned node does not error.
