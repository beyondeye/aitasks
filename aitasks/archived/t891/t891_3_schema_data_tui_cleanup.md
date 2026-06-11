---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: [t891_2]
issue_type: refactor
status: Done
labels: [ait_brainstorm, brainstom_modules, remove_support]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-01 10:52
updated_at: 2026-06-11 11:58
completed_at: 2026-06-11 11:58
---

# t891_3 — Schema/data + TUI cleanup: remove plan_file, br_plans, plan UI

> **⚠️ DEFERRED — gated on the t756 chain (auto-depends on t891_2).** Do NOT
> implement until t756 lands and t891_2 (ops/agents removal) is done. **Re-verify
> every code anchor below against the as-landed codebase** — anchors are a
> 2026-06-01 pre-modules snapshot and will drift; locate by symbol name.

## Context

Third removal child. With the `detail`/`patch` ops and detailer/patcher agents
gone (t891_2), remove the plan **data model** and the plan **TUI surfaces**: the
`plan_file` node field, the `br_plans/` store + `read_plan`/`PLANS_DIR`, the
node-detail Plan tab, plan key bindings, plan badges, and the now-dead patch
wizard gating. `ait brainstorm` is unshipped → remove outright, no migration for
existing `plan_file`-bearing sessions.

## Key files to modify (locate symbols by name; verify they still exist)

- `.aitask-scripts/brainstorm/brainstorm_schemas.py`
  - `NODE_OPTIONAL_FIELDS` — remove `"plan_file"`.
- `.aitask-scripts/brainstorm/brainstorm_dag.py`
  - Remove `read_plan` (reads `br_plans/<node>_plan.md`) and the `PLANS_DIR =
    "br_plans"` constant. Remove any `br_plans/` dir creation.
- `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `NodeDetailModal` — remove the "Plan" tab, its `read_plan(...)` call, and the
    plan minimap init.
  - Remove `_node_has_plan` and the patch-wizard step that gated on it (the patch
    op was removed in t891_2, so this gate is dead).
  - Remove the `l` / `V` plan key bindings and any plan-view actions/messages.
- `.aitask-scripts/brainstorm/brainstorm_dag_display.py`
  - Remove the plan-badge rendering (●/○), the `node_has_plan_map` / `has_plan`
    plumbing, the `Binding("l", "view_plan", ...)`, the `PlanRequested` message,
    and `action_view_plan`.
- Also: remove any `plan_file` entries from `_NODE_NON_DIMENSION_FIELDS` /
  field-stripping lists in `brainstorm_session.py` if not already removed by
  t891_2.

## Must preserve

- Node metadata + proposal model, dimensions, section markers (t873), and the
  surviving explore/compare/synthesize node-detail tabs and bindings.

## Implementation plan

1. Re-verify symbols against the as-landed code.
2. Drop `plan_file` from the schema, then `read_plan`/`PLANS_DIR`, then the TUI
   surfaces (modal tab, bindings, badges, wizard gating), then any residual
   field-stripping references.
3. grep for residual `plan_file` / `read_plan` / `PLANS_DIR` / `br_plans` /
   `has_plan` / `view_plan` and clean dead code + imports.

## Verification

- `grep -rn "plan_file\|read_plan\|PLANS_DIR\|br_plans\|node_has_plan\|view_plan\|PlanRequested" .aitask-scripts/brainstorm/`
  returns nothing live.
- The `.py` files parse; brainstorm tests (if any) pass.
- Launch `ait brainstorm` (manual): the node-detail modal has no Plan tab; no
  ●/○ plan badges in the DAG; `l`/`V` no longer bound to plan view; opening a
  node that previously had a plan does not error.
