---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: documentation
status: Implementing
labels: [ait_brainstorm, brainstom_modules]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-11 10:07
updated_at: 2026-06-11 13:10
---

## Origin

Spawned from t891_1 during Step 8b review.

## Upstream defect

`aidocs/brainstorming/module_decomposition_design.md` is stale relative to the
as-landed codebase:

- **L9 header** still reads `Status: design only — no implementation has landed`,
  even though t756 (which implemented `decompose`/`sync`/`merge`) is **Done and
  archived**.
- **§4.3 sync (L338)** still describes sync producing an "updated `plan_file`
  mirroring the aitask's final plan", and the **syncer template note (~L514-518)**
  outputs "+ plan reflecting as-implemented state". The node `plan_file` field is
  being removed by **t891_3** (proposal-only), so sync should produce an updated
  **proposal** node, not a plan_file.

## Diagnostic context

t891_1 made `ait brainstorm` proposal-only in the docs (new
`brainstorm_engine_architecture_v2.md`, archived v1). Its scope (confirmed with
the user) was "scoped + entailed consistency" on `module_decomposition_design.md`
— it added a t891 proposal-only note and removed `detail`/`patch` from the
op-lists/lifecycle/worked-example/templates, but deliberately did NOT rewrite the
"design only" status line or the sync `plan_file` semantics, because those are a
**t756-as-built reconciliation** on a different axis from the plan-layer
retirement.

## Suggested fix

Refresh `module_decomposition_design.md` to post-t756 / post-t891 reality:
update the status header to reflect that decompose/sync/merge have landed (per
documentation conventions — describe current state, no version-history prose),
and align §4.3 sync + the syncer template so sync's output is an updated
proposal node (drop the node `plan_file` framing once t891_3 lands). Best
sequenced after t891_3 so the sync/proposal wording matches the implemented
schema. Cross-check against `brainstorm_engine_architecture_v2.md`.
