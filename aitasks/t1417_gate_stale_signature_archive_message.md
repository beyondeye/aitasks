---
priority: low
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [verification, backend]
gates: [risk_evaluated]
anchor: 635
followup_kind: risk_mitigation
created_at: 2026-08-04 18:35
updated_at: 2026-08-13 23:07
---

## Origin

Risk-mitigation ("after") follow-up for t1409, created at Step 8d after
implementation landed.

## Risk addressed

**Code-health — a bare `BLOCKED:<gate>` for a gate whose ledger says `pass`.**
From t1409's plan `## Risk` section:

> `archive-ready` returns a bare `BLOCKED:<gate>` for a gate whose ledger still
> reads `pass`, so `aitask_archive.sh`'s `GATE_PENDING:<csv>` tells the user to
> wait for a gate rather than to re-sign a stale signature · severity: low

## Background

t1409 made `gate_ledger.archive_status()` block archival when a ledger-satisfied
human gate's `ait gate pass` witness was signed against a different code state.
It reports this through the existing `BLOCKED:<csv>` channel, which
`aitask_archive.sh gate_guard()` renders as `GATE_PENDING:<csv>` + exit 2.

That message is accurate for the ordinary case (the gate never passed) but
misleading for the new one: the gate *did* pass, the code moved underneath it,
and the remedy is not to wait — it is to re-review and re-sign with
`ait gate pass <task-id> <gate>`. Today the user has to run `ait gates run <id>`
to discover which of the two situations they are in.

## Goal

Give the stale-signature case its own signal so the remedy is stated where the
refusal happens.

- Widen the decision's return so a stale-signed gate is distinguishable from a
  never-passed one — e.g. `archive_status()` returns the stale set alongside the
  non-pass set, and `aitask_gate.sh archive-ready` emits
  `BLOCKED:<csv>` plus a `STALE_SIGNATURE:<csv>` line (or a combined form).
  Keep the existing `BLOCKED:` line shape so current parsers do not break —
  `aitask_query_files.sh inflight` and task-workflow Step 3 Check 4 both consume
  it.
- Teach `aitask_archive.sh gate_guard()` to print the re-sign instruction naming
  the offending gate(s) when the stale set is non-empty.
- Consider the same distinction for task-workflow Step 9's archival-blocked
  offer, so "Resolve now & archive" points at re-signing rather than at waiting.

## Verification

- A fixture that signs a gate, mutates code, then runs `aitask_archive.sh` and
  asserts the stale-specific message and exit 2 — with a negative control
  showing a genuinely-pending gate still produces the ordinary `GATE_PENDING`
  wording.
- `tests/test_query_files_inflight.sh` and `tests/test_gate_guarded_archival.sh`
  must still pass unchanged: the `BLOCKED:<csv>` contract they pin is
  load-bearing for pick-time re-entry.
