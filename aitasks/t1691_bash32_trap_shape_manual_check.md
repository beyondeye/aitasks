---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [framework, bash_scripts, concurrency]
anchor: 1681
followup_kind: risk_mitigation
created_at: 2026-09-02 17:06
updated_at: 2026-09-02 17:34
---

## Origin

Risk-mitigation ("after") follow-up for t1681, created at Step 8d after implementation landed.

## Risk addressed

Addresses code-health bullet 2 of `aiplans/p1681_*.md`:

> The guard is designed to degrade to today's behaviour on an unrecognised trap
> rendering, which means it can also *silently stop guarding* on such a shell (e.g.
> macOS bash 3.2, untested here) · severity: medium

## Goal

t1681 added `_ait_ledger_exit_trap_is_first()` to `.aitask-scripts/lib/ledger_block.sh`.
It decides whether `ait_ledger_lock_exit_trap` is the first command of the EXIT trap by
reading `trap -p EXIT` from inside the firing trap and matching bash's
`trap -- 'HANDLER' EXIT` rendering.

That parse **fails safe**: a rendering it cannot recognise returns "no complaint", so the
guard degrades to the pre-t1681 behaviour instead of inventing a failure. The cost of that
choice is that on a shell which renders traps differently the guard becomes a **silent
no-op** — the hazardous `trap 'cleanup; ait_ledger_lock_exit_trap' EXIT` spelling would
once again report a died section as success, with nothing to say so.

Two facts the guard rests on are unverified outside Linux bash 5.x:

1. `trap -p EXIT` inside a command substitution reports the **parent's** trap (the POSIX
   `saved=$(trap)` idiom), not the subshell's reset one.
2. bash renders the handler single-quoted and verbatim, whatever shape it was installed in.

`tests/test_ledger_lock_exit_trap.sh` pins both as **group 0**, and case 2 asserts the
guard actually *fires* (the warning text) rather than merely that the exit status is
nonzero — so a shell where the parse fails produces a red suite rather than silence. What
is missing is running that suite anywhere other than this box.

## Verification Steps

- On a **macOS** machine (system bash 3.2 at `/bin/bash`), run:
  `/bin/bash tests/test_ledger_lock_exit_trap.sh`
- Confirm **group 0 (0a-0d)** passes — the `trap -- '…' EXIT` rendering is what the guard
  parses.
- Confirm **case 2 / 2b-i** passes — the guard fires and warns on the naive chain. A pass
  here is the whole point: it proves the guard is live on that shell, not silently
  degraded.
- Confirm cases 1 / 2b / 2c exit exactly 1 and case 3 preserves 7 / 255 exactly.
- Confirm cases 8-11 behave (0-255 accepted verbatim; 256/512/010/08 rejected with exactly
  one stderr line and no `value too great for base` / `integer expected` diagnostic).

**If group 0 or case 2 fails**, the guard is inert on that platform. Do not "fix" it by
loosening the parse — spawn a follow-up to replace the textual `trap -p` inspection with a
shape-agnostic detection (e.g. an explicit `ait_ledger_lock_install_exit_trap` installer
helper that owns the trap string, making the hazardous spelling unwritable rather than
merely detectable).

## Context

- Seam: `.aitask-scripts/lib/ledger_block.sh` (`ait_ledger_lock_exit_trap`,
  `_ait_ledger_exit_trap_is_first`)
- Test: `tests/test_ledger_lock_exit_trap.sh`
- Consumer using the chained spelling: `.aitask-scripts/aitask_note.sh`
- Portability notes: `aidocs/framework/sed_macos_issues.md`
