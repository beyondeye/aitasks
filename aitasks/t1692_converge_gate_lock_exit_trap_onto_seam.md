---
priority: low
effort: low
depends: []
issue_type: refactor
status: Implementing
labels: [framework, bash_scripts, concurrency]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1681
followup_kind: risk_mitigation
created_at: 2026-09-02 17:07
updated_at: 2026-09-02 17:17
---

## Origin

Risk-mitigation ("after") follow-up for t1681, created at Step 8d after implementation landed.

## Risk addressed

Addresses code-health bullet 3 of `aiplans/p1681_*.md`:

> `aitask_gate.sh` keeps a byte-for-byte duplicate of the trap function, so the
> seam and its largest sibling now diverge in safety · severity: low

## Goal

t1681 hardened `ait_ledger_lock_exit_trap` in `.aitask-scripts/lib/ledger_block.sh`: it
now takes an optional explicit status (validated against the decimal 0-255 domain) and,
in the no-arg form, detects being chained behind another command in the EXIT trap —
warning and exiting exactly 1 instead of silently reporting a died section as success.

`.aitask-scripts/aitask_gate.sh` does **not** benefit. It carries its own private
`_gate_lock_exit_trap()` (around line 147) that is a byte-for-byte copy of the *pre*-t1681
seam function:

```bash
_gate_lock_exit_trap() {
    local rc=$?
    if ! release_gate_lock; then
        if [[ $rc -eq 0 ]]; then rc=1; fi
    fi
    exit "$rc"
}
```

It is installed **bare** at three sites (around lines 290, 964, 1214), so it is correct
today — nothing runs in front of it. But it is unguarded: the next person who needs
cleanup at one of those three sites can reintroduce the exact defect t1681 closed, and the
seam's guard will not see it. That divergence was left deliberately in t1681, whose task
required gate behaviour to be unchanged; it is not a bug, it is duplication with a known
expiry.

Collapse `_gate_lock_exit_trap` onto the guarded seam function so all three sites get the
guard. `release_gate_lock` is already a thin wrapper over `ait_ledger_lock_release`
(`acquire_gate_lock` / `release_gate_lock` / `release_gate_lock_checked` all delegate to
the seam), so the seam's trap releases the same lock the local copy does — confirm that
before assuming it.

## Verification Steps

- `bash tests/test_gate_lock_characterization.sh` stays green (47/47 at time of writing).
  **Test 5 ("trap releases lock on die") is the load-bearing one** — it is what proves the
  three converted sites still release on a die.
- `bash tests/test_gate_ledger.sh` stays green (37/37).
- `bash tests/test_ledger_lock_exit_trap.sh` stays green (77/77) — the seam's own contract
  must not shift to accommodate gate.
- `bash tests/test_note_append.sh` stays green (110/110) — the seam's other consumer.
- Add a gate-side case proving the guard is now live there: a driver that installs
  `trap 'cleanup; ait_ledger_lock_exit_trap' EXIT` around a gate-lock section and asserts
  the death is not reported as success. Without it the convergence is untested at the very
  point that motivates it.
- `shellcheck -S warning .aitask-scripts/aitask_gate.sh`.

## Context

- Duplicate to remove: `.aitask-scripts/aitask_gate.sh` `_gate_lock_exit_trap` (~line 147)
- Its three bare install sites: `.aitask-scripts/aitask_gate.sh` ~lines 290, 964, 1214
- Guarded seam: `.aitask-scripts/lib/ledger_block.sh` `ait_ledger_lock_exit_trap`
- Reference conversion of a chained consumer: `.aitask-scripts/aitask_note.sh`
- Characterization suite that pins the gate lock's wording and behaviour:
  `tests/test_gate_lock_characterization.sh`
