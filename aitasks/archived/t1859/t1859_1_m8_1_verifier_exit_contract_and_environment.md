---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: feature
status: Done
labels: [testing, testmap, gates]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
implemented_with: claudecode/opus5_5
created_at: 2026-10-19 15:42
updated_at: 2026-10-20 18:55
completed_at: 2026-10-20 18:55
---

Child of t1859 (test-map **M8 — Completion policy and gates**), submodule
**M8.1 — Verifier exit contract and environment**, wave **A**. This sets the
contract that `./ait test --gate` speaks to the gate machinery: a host refusing
resources (exit 75) or the framework failing to run (exit 3) must become a
verifier **error** that the orchestrator retries. It must never become a code
failure and never a skip. It also covers how the command learns which task and
gate run it serves, and how a one-line result reaches the ledger.

Authoritative spec: `aidocs/testing_engine/n014_explorer_006_proposal.md` —
the Module Map `#### M8` row, component *Gates*, *Run Surface → Output and
exit contract / The two environment variables*, *Workflow Seam → Gates*,
`assumption_gate_exit_contract_reused`, and Open question 4. The parent's
coarse plan `aiplans/p1859_testmap_m8_completion_policy_and_gates.md` lists
the cut fixes this row carries in *Deviations*: Dev 1 (64 stays a fail) and
Dev 2 (the result carrier).

This coarse plan records what the proposal fixes for M8.1. It does not design
internals against providers that do not exist yet; the Reality check does that
when this child is picked. M8.1 consumes no other test-map module and is
pickable now.

## Key Files to Modify

- `.aitask-scripts/lib/gate_verifier_lib.sh`:
  - `run_project_command_key()`, for opted-in keys: exit 75 → `PROJECT_CMD_STATUS=error`,
    `CODE=3`, `REASON=command_refused`; exit 3 → `error`/3/`command_errored`;
    64 and every other non-zero stay `fail`; 2 stays the opt-in skip. Update the
    docblock table, which is the single canonical statement.
  - `run_command_gate()`: export `AIT_GATE_TASK_ID`, `AIT_GATE_RUN_ID` and
    `AIT_GATE_RESULT_FILE=.aitask-gates/<task>/<gate>_<run>.result` around the
    command; append the `error` block and return 3.
  - **The result carrier:** truncate the file before each command. The value
    used is the one written by the command that decided the verdict (the
    failing one, else the last writer). Take the first line only, strip CR/LF
    and cap the length. Use it as `result=`, keeping the status reason as a
    prefix. An absent or empty file keeps today's text.
- `.aitask-scripts/aitask_run_project_command.sh`: `--task-id` also exports
  `AIT_GATE_TASK_ID`, and the helper reports the new `error` verdict. Its
  header currently promises that exit 3 prints no `VERDICT:`. Restate that
  contract, either as `VERDICT:error` + `REASON:command_refused|command_errored`
  with exit 3, or by keeping exit 3 verdict-less. The `build-verification.md`
  capture form ("rc 3 or empty verdict → infrastructure") must still classify
  it as infrastructure; M9.1 adds the specific branch later.
- `tests/test_gate_verifiers.sh`: new cases (use the file-backed counters if
  bodies run in subshells; see CLAUDE.md).

## Reference Files for Patterns

- The existing opt-in skip row (`GATE_COMMAND_SKIP_EXIT`) and its tests in
  `tests/test_gate_verifiers.sh`.
- `lib/gate_orchestrator.py`: `map_exit` (3 → error) and `reconcile_terminal`
  (a matching appended block is a no-op). `lib/gate_ledger.py`:
  `VALID_STATUSES` includes `error`.

## Implementation Plan

0. **Reality check (MANDATORY, before any code; record the outcome in the plan
   file).** Follow t1859 body §2. The child plan lists the items.
1. Add the two rows and the carrier to the lib; update the docblock.
2. Add the export to the helper and restate its header contract.
3. Write the tests, including negative controls.

## Verification Steps

- Opted-in 75 / 3 → `error` block with the right reason, return 3.
- Not opted in: 75 / 3 → fail. 64 → fail. 2 → skip, unchanged.
- The command sees both ids; `--task-id` exports `AIT_GATE_TASK_ID`.
- The carrier: present, absent, multi-line, a list of commands.
- `bash tests/test_gate_verifiers.sh` and `shellcheck` are green.
- No path requires a human action.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-20T14:09:17Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-20T14:35:30Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-20T15:55:28Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:fcbe308648e20ca4

> **✅ gate:risk_evaluated** run=2026-10-20T15:55:28Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1859_1/risk_evaluated_2026-10-20T15:55:28Z-risk_evaluated-a1.log`
