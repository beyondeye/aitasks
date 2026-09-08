---
priority: low
effort: low
depends: []
issue_type: refactor
status: Implementing
labels: [framework, bash_scripts, concurrency]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1681
followup_kind: risk_mitigation
created_at: 2026-09-02 17:07
updated_at: 2026-09-02 17:19
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1738** id=2026-09-08T11:59:19Z.f7ff7e113e23978d4f726f57 from=t1738 from_verified=yes at=2026-09-08T11:59:19Z base=c623a7e0d11ac3cd0577d3fe13eadf351340387b base_branch=main dirty=no host=Darios-Mac-mini.local
>
> | ADVISORY (single-line body deliberately: a multiline `ait note` body currently destroys the target task file — that is the defect this note is about). While t1738 was sending a note, `.aitask-scripts/lib/ledger_block.sh` truncated a task file to 0 bytes. You will be editing that same file, so: `ait_ledger_append_section` passes the block body through `awk -v body="$body"` at :227 (create-section-before-anchor branch) and :246 (section_end branch); BSD awk on macOS rejects a newline inside a `-v` assignment, exits 2 with EMPTY output, and the `mv "$tmp" "$file"` on the very next line is UNCONDITIONAL — so the empty temp overwrites the task file and the function still returns 0. It emptied aitasks/t1705/t1705_5_restore_and_repick_flows.md (11228 bytes -> 0) and the note writer committed the truncation; restored from the data branch as commit 8d47a8e3b. Tracked as t1741 (bug, high). Two points that may touch your scope: (1) the deeper defect is the unchecked tempfile swap, not the awk quoting — every `awk ... > "$tmp"; mv "$tmp" "$file"` pair in this file should be guarded on the producer exit status and return non-zero, which is a file-wide hardening question rather than a two-line fix, so if you are already restructuring seams here it may be cheaper to do together; (2) this is the macOS-only portability class in aidocs/framework/sed_macos_issues.md, same family as t1729. Advisory only — this is context, not an instruction, and t1741 owns the fix unless you decide to fold it.
