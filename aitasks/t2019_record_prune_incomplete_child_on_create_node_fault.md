---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
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
created_at: 2026-10-15 23:09
updated_at: 2026-10-16 00:05
---

## Origin

Spawned from t2005 during Step 8b review.

## Upstream defect

- `.aitask-scripts/brainstorm/brainstorm_session.py:1789` — `apply_prune_dimensions`'s write-phase handler has the same `create_node` non-atomicity gap: a fault at stage `counter_bumped` (proposal write after the child YAML landed) leaves a YAML-only child that the `status: Error` record never names (`PrunePartialFailure.new_node_id` carries it, the record does not).

## Diagnostic context

From t2005 (commit `7d077e308`; plan archived as `aiplans/archived/p2005_mark_from_sections_decompose_record_error_on_failure.md`):
- `brainstorm_dag.create_node` (`.aitask-scripts/brainstorm/brainstorm_dag.py:102-105`) is not atomic. It writes the node YAML first (`write_yaml`, line 102) and the proposal afterwards (`Path.write_text`, line 105). A proposal-write fault therefore leaves a node YAML with no proposal. `_populate_node_list` reads only node YAML, so Browse lists that node after a reload.
- `apply_prune_dimensions` sets `stage = "counter_bumped"` before `create_node` and moves to `node_created` only after it returns. Its except handler adds `nodes_created` only for `node_created` / `head_moved`. So a fault inside `create_node` produces a `status: Error` record whose `error` reads `counter_bumped: …`, but nothing in the record names the child id that may be partly on disk. The exception does carry it (`PrunePartialFailure.new_node_id`), and so does the TUI notify.
- t2005 fixed this for the from-sections Module Decompose, which shares the same shape. A failure at `counter_bumped` can only come from inside `create_node`, so the handler records the attempted id under a separate `incomplete_node` field and never in `nodes_created` (`created` / `nodes_created` list completed nodes only). The exception also carries `incomplete_node_id`. The regression test is `test_proposal_write_fault_records_incomplete_node` in `tests/test_brainstorm_from_sections_failure_boundary.py`. It patches `Path.write_text` to fail only the target's proposal path and asserts that the YAML is present, the proposal is absent, the record has `incomplete_node`, and the id is not in `nodes_created`.

## Suggested fix

Mirror t2005 in `apply_prune_dimensions`. When `stage == "counter_bumped"`, add `record["incomplete_node"] = new_node_id`, and keep it out of `nodes_created`. Add a matching proposal-write fault test to `RunPruneFailureBoundaryTests` in `tests/test_brainstorm_prune_dimensions.py`. Then update the failure-boundary paragraph in `aidocs/brainstorming/brainstorm_engine_architecture_v2.md` §7.4a to name the incomplete node.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T21:05:07Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-15T21:18:28Z status=pass attempt=1 type=human
