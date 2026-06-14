---
title: Gate-Guarded Archival
category: design
tags: [aitasks, gates, archival, task-workflow, re-entry, deferred-archival, ledger]
sources: [aitask-gate-framework.md, integration-roadmap.md, dependency-unblock-semantics.md]
confidence: high
created: 2026-06-14
updated: 2026-06-14
---

# Gate-Guarded Archival

Phase 2 of the gate-framework roadmap ([[integration-roadmap]], decision
**D5**). This is the companion to [[dependency-unblock-semantics]] (t635_3):
that doc decides *when a gated task releases its dependents*; this one decides
*when a gated task may archive*.

## Problem

Today task-workflow **Step 9** archives a task at workflow end, and
`aitask_archive.sh` moves it to `aitasks/archived/` unconditionally. Once gates
exist, *workflow-end* and *all-gates-pass* stop coinciding: a task whose code is
committed but whose human review / manual verification / `docs_updated` gate
pends for days would be archived prematurely. Archive is an **immutable record**
— archiving early kills re-entry (the roadmap explicitly rejects re-entry from
archive).

## Criterion (D5 + D6)

A task that declares gates (the `gates:` frontmatter field) may archive **iff
every declared gate has derived status `pass`**. State is derived from the
`## Gate Runs` ledger only (decision **D6** — no new coarse `status` value, no
denormalized `gates_summary` field). A declared gate with **no recorded run**
counts as not-pass (pending).

This differs from the dependency-unblock criterion: unblocking dependents
filters to the registry's `blocks_dependents` gates (integration gates only);
**archival requires *all* declared gates**, including post-integration sign-off
gates (async human review, `docs_updated`, manual verification). So no registry
lookup is needed — just the declared list and the ledger.

`archive_status(task_file)` in `lib/gate_ledger.py` returns one of:

| Result | Meaning |
|--------|---------|
| `NO_GATES` | No declared gates → archive exactly as today (the dormant case). |
| `ALL_PASS` | Every declared gate is `pass` → archival may proceed. |
| `BLOCKED:<csv>` | One or more declared gates are not `pass`. |

Surfaced as `aitask_gate.sh archive-ready <task-id>` (python-delegated,
degrades to `NO_GATES` if Python is absent), and enforced in
`aitask_archive.sh` (a `gate_guard()` mirroring the existing
`verification_gate_and_carryover()`): on `BLOCKED` it prints `GATE_PENDING:<csv>`
and exits 2, refusing to archive — defense-in-depth for **any** caller, not just
task-workflow.

## Deferred-archival state contract

When Step 9 archival is blocked by a pending gate and the user defers, the task:

- **stays `Implementing`** — the status enum is unchanged (D6). `Ready` would
  lose the "work done, gated" distinction (`Ready` means "not started"); a new
  status value is forbidden by D6.
- **keeps its `## Gate Runs` ledger entries** — together with `Implementing`,
  this *is* the in-flight resume signal that t635_5 (ledger-driven re-entry) and
  t635_7 (gate-aware pick) key on.
- **keeps its lock held** — an `Implementing` + locked task is exactly the
  "in-flight, awaiting resume" shape the existing crash-recovery / reclaim path
  (Step 4 `RECLAIM_*` signals) already handles. Lock/resume generalization is
  t635_5's domain; this task does not touch lock semantics.

## Two archival-offer triggers (re-entry is never *required*)

A single reusable archival offer (built on `archive-ready`) fires from the
**earliest** of two points, so the user never has to re-pick a task just to
archive it:

1. **Immediate, in-session (Step 9).** When archival is blocked, the user is
   offered "Resolve now & archive": satisfy the pending gate(s) in the current
   session (record each pass), and the moment `archive-ready` flips to
   `ALL_PASS`, archive immediately — no re-pick.
2. **Next-pick backstop (Step 3, Check 4).** For the genuinely-async case (the
   session ended before the last gate passed), the next `/aitask-pick <id>`
   detects `ALL_PASS` and offers archival.

Profile-gated auto-apply of these offers
(`auto_complete_on_all_gates_pass`) is the autonomous lane's concern (t635_17),
not introduced here.

## Escape hatch

`aitask_archive.sh --ignore-gates` bypasses the guard (archives despite pending
gates). It is the script-level realization of the framework table's
"(profile-gated)" escape hatch — a manual override, and the hook a future
autonomous lane (t635_17) wires a profile to. task-workflow itself never passes
it (it defers instead).

## Dormancy / sequencing

The guard keys off the **declared `gates:` field**, which no task carries yet —
`gates:` population is **t635_14** (Phase 4). So the mechanism ships the contract
+ enforcement now and is **inert** until t635_14 makes it live: `aitask_archive.sh`
finds no task with declared gates, the guard is a no-op, and archival proceeds
exactly as today. `record_gates: true` records checkpoint *runs* in `## Gate
Runs`, but the `gates:` *field* stays empty, so even on the `fast` profile the
guard does not fire. Correctness is proven by synthetic-fixture tests
(`tests/test_gate_guarded_archival.sh`). This task lands after t635_2/t635_3 and
before t635_14 flips the switch.

When t635_14 populates `gates:`, the integration gates recorded `pass` by t635_2
(`build_verified` / `review_approved` / `merge_approved`) archive normally; only
post-integration gates that pass out-of-band (async human review, `docs_updated`,
manual verification) defer archival — exactly the regression class this design
neutralizes.

## Rejected alternatives

- **Next-pick (Step 3) as the *only* archival trigger.** Forces a pointless
  stop-and-re-pick cycle when the last gate is satisfiable in the current
  session. Hence the immediate in-session offer (trigger 1).
- **Revert to `Ready` on deferral.** Loses the "work done, gated" distinction and
  conflates with "approved, not started"; `Ready` is wrong for an in-flight task.
- **A new `status` value (e.g. `Verifying`).** Forbidden by D6 (drift risk);
  state is derived from the ledger.
- **Release the lock on deferral.** Overreaches into t635_5's re-entry contract;
  an `Implementing` + locked task is the established in-flight/crash-recovery
  shape.
- **Auto-apply the archival offer here.** `auto_complete_on_all_gates_pass` is a
  profile key the roadmap assigns to t635_17 (autonomous lane); introducing it
  here would step on that scope and the shared "Gates" settings group.

## See also

- [[integration-roadmap]] — Phase 2, decisions D5/D6.
- [[aitask-gate-framework]] — "Relationship to existing `status` field"; the
  `aitask-archive` integration-table row.
- [[dependency-unblock-semantics]] — the companion unblock-timing decision
  (t635_3); archival is the distinct *all-gates-pass* event.
