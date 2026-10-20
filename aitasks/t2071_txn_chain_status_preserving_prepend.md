---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [trails, skills]
gates: [risk_evaluated]
anchor: 1989
followup_kind: risk_mitigation
created_at: 2026-10-20 09:16
updated_at: 2026-10-20 09:16
---

## Origin

Risk-mitigation ("after") follow-up for t2032, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — txn_chain_exit_trap prepend hands a status-reading handler the prepended handler's status

From t2032's plan `## Risk`:
- `txn_chain_exit_trap`'s prepend hands a status-reading handler the prepended handler's status. This is only recorded here, not fixed. No shipped prepend sits in front of a status-reading handler today. · severity: low · → mitigation: txn_chain_status_preserving_prepend

## Goal

Make `txn_chain_exit_trap` (`.aitask-scripts/lib/txn_snapshot.sh`) status-preserving: capture `$?` before the prepended handler runs and restore it (e.g. `(exit "$rc") && :`, errexit-safe) before the rest of the trap, so a status-reading handler composed after it — the explicit ledger spelling `rc=$?; …; ait_ledger_lock_exit_trap "$rc"`, or the bare `ait_ledger_lock_exit_trap` once wrapped by `lib/archive_utils.sh`'s `_ait_archive_exit_chain` — sees the dying status instead of the prepended handler's.

Context from t2032:
- The caveat is currently documented at `txn_chain_exit_trap` and in `aidocs/framework/shell_conventions.md` ("Re-arm the archive sweep…" bullet) — update both once fixed.
- `tests/test_archive_utils.sh` Group 13d2 / J2b pin today's value (a bare ledger trap + txn prepend → exit 1 with the first-command warning; the explicit spelling → 0). Decide the intended values, update those pins, and keep the differential (wrapped vs unwrapped composition must agree).
- The ledger first-command detector (`_ait_ledger_exit_trap_is_first`, `lib/ledger_block.sh`) reads `trap -p EXIT`: after a prepend, the bare spelling is no longer first, so it must still fire — preserving `$?` must not silence it.
- Shipped prepends today: `with_attach_lock` callers (rollback before `registry_lock_release`) — verify none regress (`tests/test_txn*.sh`, `tests/test_attach*.sh`, `tests/test_fold_mark*.sh`).
