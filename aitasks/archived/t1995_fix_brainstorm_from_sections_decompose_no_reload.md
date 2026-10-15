---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [ait_brainstorm, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1983
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-14 22:22
updated_at: 2026-10-15 15:19
completed_at: 2026-10-15 15:19
---

## Origin

Spawned from t1983 during Step 8b review.

## Upstream defect

- `.aitask-scripts/brainstorm/brainstorm_app.py:5676` — Module Decompose's "From section markers" branch of `_run_design_op` creates the module root nodes (via `apply_module_decompose_from_sections`) and moves their subgraph HEADs, but never reloads the session (`_load_existing_session`). The new nodes probably stay invisible in the Browse graph/list until something else triggers a reload.

## Diagnostic context

This was found by code reading while implementing t1983 (the Prune Dimensions op); it was **not reproduced in a running TUI**. The evidence:
- The from-sections branch (around `brainstorm_app.py:5662-5680`, as of commit `ac442a25b`) only builds a notify message after `apply_module_decompose_from_sections(...)`.
- The agent-backed apply paths do reload: `_try_apply_module_agent_if_needed` calls `self._load_existing_session()` after a successful apply.
- The periodic `_refresh_runtime` (every 30s) only refreshes the status strip and the Running tab. It never rebuilds the DAG or node list.

t1983's own deterministic op, `prune_dimensions`, avoids the same gap: its `_run_design_op` branch calls `self.call_from_thread(self._load_existing_session)` after `run_prune_operation`, and also after a `PrunePartialFailure`.

## Suggested fix

1. Confirm the symptom live: run a from-sections decompose and check whether the new module roots appear without a manual reload.
2. If they don't, add `self.call_from_thread(self._load_existing_session)` after `apply_module_decompose_from_sections(...)` in the from-sections branch, mirroring the prune branch.
3. Consider a pilot or unit test asserting the reload is triggered.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T06:24:20Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-15T09:42:27Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-15T12:19:01Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:5ca9a2fb4bcb4afb

> **✅ gate:risk_evaluated** run=2026-10-15T12:19:01Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1995/risk_evaluated_2026-10-15T12:19:01Z-risk_evaluated-a1.log`
