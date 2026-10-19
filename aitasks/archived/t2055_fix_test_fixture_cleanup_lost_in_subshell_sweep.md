---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Done
labels: [trails, skills]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1989
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-19 09:40
updated_at: 2026-10-19 12:27
completed_at: 2026-10-19 12:27
---

## Origin

Spawned from t2031 during Step 8b review.

## Upstream defect

- `tests/test_gate_verifiers.sh` — `new_fixture` does `CLEANUP_DIRS+=` but is called as `$(new_fixture)` (41 sites), so its fixtures leak. This is the same `$( )` state-loss class as t2031.
- The same shape appears in 19 more suites. The list is heuristic: helper bodies containing `CLEANUP_DIRS+=` that are called inside `$( )`. Each hit needs reading to confirm:
  - `new_fixture`: test_gate_active_gates (14), test_gate_cli_wiring (3), test_gate_declaration_backfill (4), test_gate_effective_gates (3), test_gate_no_double_record (3), test_gate_orchestrator (18), test_gate_pass (6), test_gate_procedure_docs (9), test_gate_risk_verifier (10), test_gates_sync_registry (27), test_gate_stale_witness_parity (5), test_run_project_command (24), test_web_merge_materialize (6)
  - `fresh_tmpdir` (8) / `make_repo` (7): test_atomic_task_file_writes
  - `bcrt` (3): test_followup_kind_roundtrip
  - `setup_repo` (10): test_issue_import_amend_guard
  - `new_dir` (7): test_skill_errexit_capture
  - `new_repo` (18): test_verification_stale

## Diagnostic context

From t2031's Final Implementation Notes:

- In `tests/test_docs_vocabulary_coverage.sh`, `make_fixture` appended to `CLEANUP_DIRS` inside a `$(make_fixture)` command substitution. The append died with the subshell, so the `trap cleanup EXIT` never saw the fixtures. Measured with a probe TMPDIR, each run leaked 12 `tmp.*` dirs while the suite reported 30/30 green.
- The sweep that produced the list above was a heuristic awk over `tests/*.sh`: it tracks each function body from `name() {` to `^}`, records helpers whose body contains `CLEANUP_DIRS+=`, and counts `$( name` call sites. It does not prove a leak. A helper might also register the dir in a way that survives, a caller might re-register after the call, or a suite might clean up through a shared parent temp dir. Read each hit before changing it.
- `test_atomic_task_file_writes.sh` `tmpdir_entries` showed up in an earlier, cruder grep. The refined scan does not list it; it is listed in neither place above as confirmed.

## Suggested fix

Apply t2031's pattern to each confirmed suite: the helper sets a result variable (e.g. `_FIXTURE_DIR`) and callers invoke it directly, or callers register in the parent after the call. Confirm each suite with a probe TMPDIR (`TMPDIR=<empty dir> bash tests/<suite>.sh`, then count leftovers) before and after the fix.

Also add an in-suite membership assertion. Guard it with a non-empty/dir-exists check first: t2031 found that `" $X " in " ${ARR[*]} "` passes vacuously when `X` is empty. Consider a shared helper in `tests/lib/` so suites stop hand-rolling this.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-19T08:11:42Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-19T09:19:10Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-19T09:27:17Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:8da37566fac88a4f

> **✅ gate:risk_evaluated** run=2026-10-19T09:27:17Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2055/risk_evaluated_2026-10-19T09:27:17Z-risk_evaluated-a1.log`
