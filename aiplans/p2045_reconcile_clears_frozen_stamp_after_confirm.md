---
Task: t2045_reconcile_clears_frozen_stamp_after_confirm.md
Base branch: main
Output branch: main
---

# t2045 — reconcile retires the frozen stamp and attempt mark after a confirm

## Context

`agent_freeze._reconcile_restoring` settles a `restoring` record whose restore
coordinator died. In the `launch_pid and observed.pane_pid == launch_pid` row it
issues `restore-confirm` and returns `LIVE:<id>|rollout` (t2040) or
`LIVE:<id>|liveness`. On success it never retires the pane's marks, which the
coordinator always does (`agent_restore._clear_frozen_stamp` → guarded
`frozen_ops.clear_stamp_if` + `frozen_ops.clear_restore_attempt`). Result: the
record is `live` but its pane still carries `@aitask_frozen=<id>`, so
`freeze_pane` answers `FREEZE_SKIPPED:<id>|already frozen` for ever. Later
reconcile passes skip `live` records, so nothing fixes it.

## Design decisions

- **One rule, one place.** Move the body of `agent_restore._clear_frozen_stamp`
  into a new shared helper `frozen_ops.retire_restore_marks(pane_id, record_id,
  nonce)` in `.aitask-scripts/lib/agent_frozen_ops.py` (same docstring
  rationale: both are GUARDED single `if-shell -F` dispatches, t1875). The
  coordinator's `_clear_frozen_stamp` becomes a one-line delegate (kept, because
  `tests/test_agent_restore.py:1485,1495` call it). `agent_freeze` cannot import
  `agent_restore` (layering: both engines sit on `frozen_ops`), so the shared
  module is the right home.
- **The attempt nonce is recoverable: the PRE-lease `rec["op_nonce"]`.** The
  coordinator's attempt mark value is `restore_attempt_value(record_id, N1)`
  where N1 is the nonce `restore-begin` minted — the record's `op_nonce` until
  someone leases it. `_reconcile_restoring` already receives the pre-lease
  snapshot (`reconcile()` reads it "BEFORE LEASING" for exactly the
  `last_error` reason), so `rec.get("op_nonce", "")` is N1. The lease's own
  nonce (N2) must NOT be used: it matches no mark. An empty `op_nonce` yields a
  value that fails `_RESTORE_MARK_RE`, so the mark clear is a no-op (fail safe).
  On a same-pane restore no pane carries a mark and the dispatch is a no-op,
  exactly as in the coordinator.
- **Stamp guard** is `clear_stamp_if(observed.pane_id, record_id)` — never an
  unconditional unset (t1875 recycled-`%N` rule). The pane is
  `observed.pane_id`, the pane just confirmed.
- **Residual (accepted, documented in a code comment):** if an EARLIER reconcile
  pass took the lease on this same `restoring` record and then failed to settle
  it (`RECONCILE_FAILED` on `restore-confirm` / abort — store errors), the
  pre-lease `op_nonce` is that pass's nonce, not N1, and the mark is not
  retired (the stamp still is). Fails in the safe direction — a stale mark
  only over-reports a survivor; it never strips another attempt's claim. Not
  worth new persistent state (no `prev_nonce` field) for a store-error-only path.

## Steps

1. `agent_frozen_ops.py` — add after `clear_stamp_if`:
   ```python
   def retire_restore_marks(pane_id: str, record_id: str, nonce: str) -> None:
       """Retire a restored pane's marks: the stamp, and this attempt's mark.
       <docstring moved from agent_restore._clear_frozen_stamp>"""
       if pane_id:
           clear_stamp_if(pane_id, record_id)
           clear_restore_attempt(pane_id, restore_attempt_value(record_id, nonce))
   ```
2. `agent_restore.py` — `_clear_frozen_stamp` body becomes
   `frozen_ops.retire_restore_marks(pane_id, record_id, nonce)` with a short
   docstring pointing at the shared helper.
3. `agent_freeze.py` `_reconcile_restoring`:
   - next to `mismatch`, bind `coordinator_nonce = rec.get("op_nonce", "")`
     with a comment: pre-lease read, it is the nonce the attempt mark was
     derived from; the residual above.
   - rollout branch: on `rc == 0`, call
     `frozen_ops.retire_restore_marks(observed.pane_id, record_id, coordinator_nonce)`
     before returning `LIVE:<id>|rollout`.
   - liveness branch: same on `rc == 0` before `LIVE:<id>|liveness` (expand the
     conditional-expression return into an if).
   - Never on a failed confirm or an abort path (those keep the stamp: the
     record goes back to `frozen` and the stand-in needs it).
4. Tests — `tests/test_agent_freeze.py`, `ReconcileRestoringTests`:
   - helper that runs a confirm the realistic way: stale coordinator
     (`op_owner_pid` dead, `op_started_at` old, as in the handover-race test),
     PRE-lease snapshot, `agent_freeze._Lease(self.rid)` so the lease mints N2
     ≠ N1; pane model stamped `@aitask_frozen=<rid>` and carrying
     `@aitask_restore_attempt=restore_attempt_value(rid, N1)`.
   - `test_a_liveness_confirm_retires_the_stamp_and_attempt_mark` and
     `test_a_rollout_confirm_retires_the_stamp_and_attempt_mark`: after `LIVE:…`,
     pane `@aitask_frozen == ""`, attempt mark `== ""`, and
     `agent_freeze.freeze_pane(AGENT_PANE)` succeeds (no `FREEZE_SKIPPED`).
     The N2≠N1 setup makes a mutant that uses the lease nonce fail.
   - Negative control: pane stamp names ANOTHER record and the mark names
     another attempt → both kept after the confirm.
   - Control: an abort path (dead pane) keeps the stamp (already covered by the
     existing STANDIN tests' state; add an explicit assertion in one).
   - `tests/test_agent_frozen_ops.py`: a small test that
     `retire_restore_marks` issues both guarded dispatches and is a no-op for an
     empty pane id.

### Post-phase (risk mitigations)

1. [pin_delegate_parity] In `tests/test_agent_restore.py`, next to the existing
   `_clear_frozen_stamp` tests (~line 1485), add a test that records the fake
   tmux calls of `agent_restore._clear_frozen_stamp(pane, rid, nonce)` and of
   `agent_frozen_ops.retire_restore_marks(pane, rid, nonce)` on identical pane
   models and asserts the two call lists are equal (both guarded `if-shell`
   dispatches, same order, same values).

## Verification

- `python3 tests/test_agent_freeze.py`, `python3 tests/test_agent_restore.py`,
  `python3 tests/test_agent_frozen_ops.py` (or via
  `bash tests/run_all_python_tests.sh --test-dir` subset), all green.
- Red proof: temporarily reverting step 3 makes the two new confirm tests fail
  (run in a scratch copy, not by git-restoring the shared tree).
- Optional live check from the task (kill coordinator after
  `restore-launched`, `reconcile`, freeze again) — not required.

## Step 9

Post-implementation: commit code + plan, archive via `aitask_archive.sh 2045`.

## Risk

### Code-health risk: low
- Moving `_clear_frozen_stamp`'s body into `frozen_ops` could change the
  coordinator's behaviour if the delegate drifts · severity: low (residual — addressed by inline post-phase pin_delegate_parity) · → mitigation: inline post-phase pin_delegate_parity

### Goal-achievement risk: low
- The attempt mark is not retired when an earlier failed reconcile lease replaced
  `op_nonce` (documented residual; stamp is still cleared, so the
  freeze-again goal holds) · severity: low · → mitigation: retire_mark_after_replaced_lease

### Planned mitigations
- timing: after | name: retire_mark_after_replaced_lease | type: bug | priority: low | effort: medium | inline_risk: medium | added_complexity: medium | addresses: goal-achievement: attempt mark not retired after a replaced op_nonce | desc: In reconcile's restoring confirm, recover the attempt mark from the pane itself when the pre-lease op_nonce is not the coordinator's, clearing it under a compound guard (mark value AND pane_pid == launch_pid); extend the fake tmux for compound if-shell conditions
- timing: post-phase | name: pin_delegate_parity | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health: delegate drift between coordinator and shared helper | desc: Assert _clear_frozen_stamp and retire_restore_marks issue identical tmux dispatches
