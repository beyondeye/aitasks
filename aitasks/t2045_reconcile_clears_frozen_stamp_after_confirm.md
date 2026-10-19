---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [frozen, session_persistence]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2040
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-16 16:12
updated_at: 2026-10-19 12:56
---

## Origin

Found in review of t2040 (verified codex restore). A pre-existing defect that the new
`--rollout-session` confirm in reconcile inherits. The reviewer reproduced it with the
stateful harness in `tests/test_agent_freeze.py`, for both the liveness and the rollout
confirm.

## The defect

`agent_freeze._reconcile_restoring` (`.aitask-scripts/lib/agent_freeze.py`, the
`launch_pid and observed.pane_pid == launch_pid` row) settles an abandoned restore with
`restore-confirm`. It returns either `LIVE:<id>|rollout` (t2040) or `LIVE:<id>|liveness`.
On success it never clears the pane's `@aitask_frozen` stamp, nor the restore-attempt
mark.

The restore coordinator does clear both on success (`agent_restore._clear_frozen_stamp`,
guarded via `frozen_ops.clear_stamp_if` / `clear_restore_attempt`). Recovery does not.
The result:

- the record is `live`, but its running pane still carries `@aitask_frozen=<id>`;
- `freeze_pane` on that pane immediately returns `FREEZE_SKIPPED:<id>|already frozen`,
  so the recovered agent can never be frozen again;
- later reconcile passes skip `live` records, so nothing repairs it.

## Fix

After a successful confirm in `_reconcile_restoring` (both the rollout branch and the
liveness branch), clear the stamp and the attempt mark with the same GUARDED single
dispatches the coordinator uses. Use `frozen_ops.clear_stamp_if(pane, record_id)`, and
`clear_restore_attempt` with the attempt value derived from the coordinator's nonce,
if it can be recovered. If it cannot, decide in planning how a recovered gone-pane
attempt's mark is retired; see `agent_frozen_ops.find_restore_survivors` and t1875.

Never clear unconditionally: a server restart can recycle the `%N`, and an unguarded
unset would strip another record's stamp (the t1875 rule).

## Verification

- Unit (`tests/test_agent_freeze.py`, `ReconcileRestoringTests`): after
  `LIVE:<id>|rollout` and after `LIVE:<id>|liveness`, the pane's `@aitask_frozen` is
  empty, and `freeze_pane` on the recovered agent succeeds (it does not report
  `FREEZE_SKIPPED … already frozen`).
- Negative control: a pane whose stamp names ANOTHER record keeps it.
- Optionally live: kill a coordinator after `restore-launched`, run `reconcile`, then
  freeze the recovered agent again.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-19T09:56:56Z status=pass attempt=1 type=human
