---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [trails, skills]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1989
followup_kind: risk_mitigation
implemented_with: claudecode/opus5_5
created_at: 2026-10-16 01:30
updated_at: 2026-10-19 16:48
---

## Origin

Risk-mitigation ("after") follow-up for t2023, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — scripts that re-arm EXIT after sourcing (gate, note, create, verification_followup, registry_lock acquire/release) drop the archive sweep and still leak on bundled resolves

From t2023's plan `## Risk`:
- The leak is fixed for every `$( )` resolve whose script keeps the archive EXIT trap. But scripts that run `trap … EXIT` *after* sourcing replace it: `aitask_gate.sh`, `aitask_note.sh`, `aitask_create.sh`, `aitask_verification_followup.sh`, and `registry_lock_acquire` (whose release runs `trap - EXIT`). Those scripts can still leak one dir per bundled resolve on the paths where they re-arm, so "every caller" is covered but not airtight. · severity: medium

## Goal

Make the EXIT-trap re-arm sites keep the archive sweep, either by chaining instead of replacing or clearing, or through a shared EXIT-handler registry, without breaking the ledger lock's first-command-in-trap contract.

Context from t2023 (`lib/archive_utils.sh`):
- Extraction dirs are `ait-archive.<pid>.<nonce>.XXXXXX` under a TMPDIR base pinned at first source.
- `_ait_archive_cleanup` sweeps this shell's tag. It is installed either bare (`trap _ait_archive_cleanup EXIT`) or, when the sourcing script already had an EXIT trap, as `_ait_archive_exit_chain`. That wrapper runs the cleanup, re-arms the current trap text with its token replaced by the caller's handler, restores `$?`, and evals the handler.
- A later bare `trap X EXIT` replaces that whole trap. `registry_lock_acquire` (lib/registry_lock.sh:130) does exactly that, and `registry_lock_release` (:153) then runs `trap - EXIT`. The ledger-lock sections in `aitask_gate.sh` / `aitask_note.sh` arm `trap 'ait_ledger_lock_exit_trap' EXIT`, which also replaces it.
- `ait_ledger_lock_exit_trap` must remain the first command in the trap (or receive the status explicitly). It ends with `exit "$rc"`, so nothing appended after it ever runs. `tests/test_ledger_lock_exit_trap.sh` and `tests/test_gate_lock_characterization.sh` pin that contract.

Also record, as part of the same composition family: `txn_chain_exit_trap` (lib/txn_snapshot.sh:214) *prepends*. Placed in front of a status-reading handler, it hands that handler the prepended handler's 0, so the explicit ledger spelling `rc=$?; …; ait_ledger_lock_exit_trap "$rc"` exits 0 for an `exit 42`. That happens with or without t2023's wrapper; t2023's test 13d2 pins the unwrapped value.

Verify with a per-test probe TMPDIR. A bundled `$( )` resolve in each re-arming script path should leave no `ait-archive.*` dir, and the ledger first-command detector must still fire on the misuse spelling.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-19T13:48:51Z status=pass attempt=1 type=human
