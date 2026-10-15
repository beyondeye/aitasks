---
priority: medium
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
created_at: 2026-10-15 15:18
updated_at: 2026-10-15 22:51
---

## Origin

Spawned from t1995 during Step 8b review.

## Upstream defect

- `.aitask-scripts/brainstorm/brainstorm_session.py:1355-1408`: `apply_module_decompose_from_sections` never marks its operation record `Error` when it raises mid-loop. The group record that `record_operation(...)` writes in `_run_design_op` stays `status: Waiting` with `agents: []`, even though some module roots, their HEAD moves and `nodes_created` entries may already be on disk. By contrast, `apply_prune_dimensions` writes `status: Error` plus the stage reached (`brainstorm_session.py:1620`), and `run_prune_operation` keeps that record.

## Diagnostic context

From t1995 (commit `e77775958`; plan archived as `aiplans/archived/p1995_fix_brainstorm_from_sections_decompose_no_reload.md`):
- In `BrainstormApp._run_design_op` (`brainstorm_app.py`), the "From section markers" Module Decompose branch calls `record_operation(...)` with `agents=[]`, which writes `status: Waiting`. It then calls `apply_module_decompose_from_sections(task_num, group_name)`.
- `apply_module_decompose_from_sections` validates each module's section *inside* its creation loop. For each module it calls `create_node`, `set_head(module=...)` and `update_operation(nodes_created=...)`, and creates the linked task if one is configured. It writes `update_operation(status="Completed")` only after the loop. So a module with no matching section, or a failing `_create_linked_module_task`, raises after earlier modules' roots have landed, and the record is never moved out of `Waiting`.
- t1995 made the TUI reload the session on that failure path, so the partial roots now show in Browse. The operation record still reads `Waiting` with no agents, so the Running tab and operation detail show it as waiting forever. Nothing will ever complete it, because a from-sections op has no agent and no poller.
- t1995 reproduced this with a two-module request (`parser`, `missing`) where only `parser` has a section. `n001_module_decomposer_sections_parser` is created, then `ValueError: no section found for module 'missing'` is raised. The fixture is in `tests/test_brainstorm_from_sections_reload.py` (`test_partial_failure_shows_roots_created_before_the_error`).

## Suggested fix

Mirror prune's failure boundary:
- A failure before the first write is a refusal: delete the group record, like `run_prune_operation` does on `PruneRefused`. The candidates are no modules, no source head, invalid sections, and ideally an up-front check that every module has a section.
- A failure after the first write keeps the record and marks it `status: Error` with the stage or module reached, best-effort, as `apply_prune_dimensions` does at `brainstorm_session.py:1620`.

Consider validating every module's section before the loop, so a missing section becomes a write-free refusal instead of a partial apply.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T19:51:33Z status=pass attempt=1 type=human
