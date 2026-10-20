---
Task: t2071_txn_chain_status_preserving_prepend.md
Branch: main
Base branch: main
Output branch: main
---

# Plan: make `txn_chain_exit_trap` status-preserving (t2071)

## Context

`txn_chain_exit_trap` (`.aitask-scripts/lib/txn_snapshot.sh:251`) prepends a
handler to the current EXIT trap with `eval "trap '$1; '$cur EXIT"`. Whatever
follows the prepended handler then sees *its* status as `$?`, not the dying
one. t2032 recorded this as a known limit: in front of a status-reading
handler — the explicit ledger spelling `rc=$?; …; ait_ledger_lock_exit_trap
"$rc"` — an `exit 42` ends **0** (a failure reported as success).
`tests/test_resolve_tar_zst.sh` 13d2 pins that today as `explicit.txn = "0 0"`.

Fix: capture `$?` before the prepended handler and restore it (errexit-safe)
before the rest of the trap — the same `(exit "$rc") && :` idiom
`_ait_archive_exit_chain` (`lib/archive_utils.sh`) already uses.

Prototyped in the scratchpad (bash, `set -euo pipefail` and `set +e`, handler
returning 0 or 3): a status-reading caller after the prepend sees 42 and the
script exits 42. A prepended handler that *fails under errexit* still aborts
the trap — pre-existing behaviour, unchanged; shipped prepended handlers
(`_txn_exit_trap`, `_fold_abort_cleanup`) end in `return 0` by contract.

## Changes

### 1. `.aitask-scripts/lib/txn_snapshot.sh`

```bash
txn_chain_exit_trap() {
    local cur
    cur="$(trap -p EXIT)"; cur="${cur#trap -- }"; cur="${cur% EXIT}"
    eval "trap '__txn_chain_rc=\$?; (exit \"\$__txn_chain_rc\") && :; $1; (exit \"\$__txn_chain_rc\") && :; '$cur EXIT"
}
```

- **Restore on both sides of the handler.** The assignment `__txn_chain_rc=$?`
  itself sets `$?` to 0, so a capture alone would hand the prepended handler 0
  — a regression, since today the first prepended handler sees the dying status
  and `_txn_exit_trap` reports it ("aborted before the commit (exit N)"). So the
  status is restored right after the capture (handler entry) and again after
  the handler (for the old trap). Verified inline: with the capture-only draft
  `h1 sees 0`; with both restores, two nested prepends and the caller all see 42.
- A global (trap text runs at top level, `local` is unavailable). Nested
  prepends reuse it sequentially, each capture/restore pair self-contained.
- Rewrite the header comment: replace the "Known limit of PREPENDING" paragraph
  with the status-preserving contract, and keep the one remaining caveat: a
  prepended handler must not fail under errexit (it aborts the trap). State
  that the ledger first-command detector still fires for the **bare**
  `ait_ledger_lock_exit_trap` behind a prepend — `$?` is right, but the detector
  reads trap position, and that stays a reported failure (`1` + warning),
  never a silent success.
- Update `_txn_exit_trap`'s comment ("It is first in the chain, so it destroys
  no status a later handler needs") to say the chain restores the status.

### 2. `.aitask-scripts/lib/archive_utils.sh` — `_ait_archive_exit_chain` comment

The bullet "`$?` is … the dying one, or whatever a handler that a later
composer prepended ahead of us returned" → the dying one (a
`txn_chain_exit_trap` prepend restores it). Keep the `trap -p` /
first-command-detector bullet (still true). Comment-only.

### 3. `aidocs/framework/shell_conventions.md` ("Re-arm the archive sweep…")

Replace the composition caveat ("the handler after it receives the prepended
handler's status… Never prepend in front of a status-reading handler") with:
the prepend restores the dying status for later handlers, but the bare
`ait_ledger_lock_exit_trap` is still no longer *first*, so it still reports a
generic failure — use the explicit `rc=$?; …; ait_ledger_lock_exit_trap "$rc"`
spelling when a prepend may follow. Current-state wording only.

### 4. Tests

- `tests/test_resolve_tar_zst.sh` 13d2: `explicit.txn` → `"42 0"` (was
  `"0 0"`); `bare.txn` stays `"1 1"` (detector still fires), `misuse.txn` stays
  `"1 1"`. Differential (wrapped == unwrapped) is unchanged and must still hold.
  Update the 13d2 comment. Add an `EXPLICIT_TXN_RC` guard next to the
  `BARE_TXN_RC` one asserting the explicit spelling now ends 42 in the wrapped
  child (the property this task delivers, pinned directly, not only via the
  expectation table).
- `tests/test_archive_utils.sh` J2b ledger: values unchanged (bare spelling
  → 1 + warning). Add a sibling case **J2b ledger (explicit)**: explicit
  spelling + real txn prepend + re-source → exits 42, no warning, cleanup ran.
- `tests/test_txn_snapshot.sh`: new **Group E — `txn_chain_exit_trap` status
  preservation**, driving child `bash` processes:
  - E1: `set -euo pipefail`, caller trap `rc=$?; echo caller=$rc`, prepend a
    handler that ends in a 0 status → caller sees 42, script exits 42.
  - E2: the prepended handler itself sees the dying status — its first command
    records `$?`, asserted `= 42`.
  - E3: two prepends, the outer one ending in a 0 status (`false || true`) →
    order `h2, h1, caller`, and each one's recorded entry status is asserted
    `= 42` (not just the caller's).
  - E2b: the real `_txn_exit_trap` with `_TXN_ACTIVE=true` and
    `txn_rollback` / `txn_rollback_report` / `txn_snap_cleanup` stubbed to
    record their args → the report context reads `(exit 42)`.
  - E4: `set +e`, prepended handler returns 3 → caller still sees 42.
  - E5: no prior trap → handler runs, exit 42.
  - E0 (negative control): the same E1 fixture with the pre-fix composition
    (`eval "trap '$1; '$cur EXIT"`, inline copy) → caller sees 0, proving the
    fixture detects the defect.
  - E0b (mutant control): the capture-only spelling (no entry restore, inline
    copy) → the prepended handler records 0, proving E2/E3 detect a lost
    entry status.
  - Update the file-header group list.

## Verification

```bash
bash tests/test_txn_snapshot.sh
bash tests/test_resolve_tar_zst.sh
bash tests/test_archive_utils.sh
for t in tests/test_txn*.sh tests/test_attach*.sh tests/test_fold_mark*.sh; do bash "$t" >/dev/null 2>&1 || echo "FAIL $t"; done
python3 tests/test_archive_rearm_tripwire.py
shellcheck .aitask-scripts/lib/txn_snapshot.sh
```

Plus mutant checks in a scratch copy of the lib (never the shared worktree):
reverting the function must turn E1/E3/E4 and the 13d2/J2b explicit cases red;
dropping only the entry restore must turn E2/E2b/E3 red.

## Post-implementation

Step 9 of the task workflow (commit `bug: … (t2071)`, archival).

## Risk

### Code-health risk: low
- A prepended handler that fails under errexit still aborts the trap before the later handlers (e.g. `registry_lock_release`) — pre-existing and unchanged; shipped handlers return 0 by contract, and the new comment states it · severity: low · → mitigation: none (documented in the function comment)

### Goal-achievement risk: low
None identified.
