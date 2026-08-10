---
title: Gate-Guarded Archival
category: design
tags: [aitasks, gates, archival, task-workflow, re-entry, deferred-archival, ledger, code-binding]
sources: [aitask-gate-framework.md, integration-roadmap.md, dependency-unblock-semantics.md]
confidence: high
created: 2026-06-14
updated: 2026-08-04
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
every declared gate has derived status `pass`** — and, for a human gate signed
asynchronously, iff that signature still binds the *current* code (see
"signature re-validation" below). Status is derived from the `## Gate Runs`
ledger (decision **D6** — no new coarse `status` value, no denormalized
`gates_summary` field). A declared gate with **no recorded run** counts as
not-pass (pending).

This differs from the dependency-unblock criterion: unblocking dependents
filters to the registry's `blocks_dependents` gates (integration gates only);
**archival requires *all* declared gates**, including post-integration sign-off
gates (async human review, `docs_updated`, manual verification). So the declared
list and the ledger settle *which* gates and *whether they passed*; the registry
is consulted only to re-validate an async human gate's signature.

`archive_status(task_file, registry_file)` in `lib/gate_ledger.py` returns one of:

| Result | Meaning |
|--------|---------|
| `NO_GATES` | No declared gates → archive exactly as today (the dormant case). |
| `ALL_PASS` | Every declared gate is `pass` → archival may proceed. |
| `BLOCKED:<csv>` | One or more declared gates are not `pass`, **or** carry a code-stale signature (below). |

Surfaced as `aitask_gate.sh archive-ready <task-id>` (python-delegated,
degrades to `NO_GATES` if Python is absent), and enforced in
`aitask_archive.sh` (a `gate_guard()` mirroring the existing
`verification_gate_and_carryover()`): on `BLOCKED` it prints `GATE_PENDING:<csv>`
and exits 2, refusing to archive — defense-in-depth for **any** caller, not just
task-workflow.

### The ledger is not the last word: signature re-validation (t1409)

A gate whose *ledger* reads `pass` can still block. Human gates signed via
`ait gate pass` carry a **code-bound witness** (`code_digest=` — see the async
human-gate section of [[aitask-gate-framework]]), and a signature against a
different code state is not an approval of the current code. So `archive_status`
takes the registry, and adds any **ledger-satisfied human gate whose witness is
code-stale** to the blocked list, via the shared
`gate_ledger.stale_signed_gates()` that the orchestrator's `_read_state` also
uses — one classifier, two enforcement points.

Without this the code-binding held only until the first `pass`: the orchestrator
short-circuits on all-satisfied and `archive_status` was ledger-only, so a code
change made *after* sign-off (e.g. while resuming a headless task to fix a
machine-gate failure) archived unreviewed.

Three properties are load-bearing:

- **Only `stale` blocks.** An **absent** witness must stay accepted — an attended
  session records `review_approved` directly from the interactive review and
  never writes one — and an **unstamped** witness stays accepted for backward
  compatibility. Unverifiable freshness (no git / no commits) resolves to
  *accept*, never to a guessed `stale`.
- **This guard reports; it does not write.** `archive-ready` is a read-only
  decision verb. Recording the resulting `pending` belongs to `ait gates run`,
  the single writer of observed human-gate blocks. Between the code change and
  the next `gates run`, `ait gate status` reads `pass` while `archive-ready`
  reads `BLOCKED` — that window is the contract.
- **The digest is computed lazily.** `stale_signed_gates()` applies a no-git
  pre-filter (satisfied + `type: human` + a stamped witness on disk) and only
  shells out to git if something survives it, so the common no-witness case
  costs archival nothing.

### Which surfaces re-validate (t1416)

t1409 wired the re-validation into the two enforcing surfaces and left four
read-side ones ledger-only on a single cost argument ("a git subprocess per task
per refresh"). t1416 measured that cost and decided the split **per surface** —
the four turned out not to be alike.

| Surface | Re-validates? | Why |
|---|---|---|
| `Engine._read_state()` (`ait gates run`) | **yes** | The write-side enforcer. Threads the engine's per-run digest. |
| `archive_status(file, registry)` (`archive-ready`) | **yes** | The read-side archival guard; lazy digest. |
| `gate_orchestrator.unlocked()` (`ait gates unlocked`) | **yes** | One-shot, single-task, human-invoked — there is no per-task loop, so the affordability argument never applied. Costs at most one digest. |
| `read_task_gate_state(file, registry, digest)` (board) | **yes** | The board threads a **once-per-refresh** memo (`TaskManager.code_digest_for_refresh`), so a refresh costs exactly one digest no matter how many tasks are signed — and zero when none are. |
| `deps-unblock` (`ait ls`) | **yes** | A *semantics* decision, not a cost one — see [[dependency-unblock-semantics]]. Since t1472 `ait ls` goes through the batched twin (`deps-unblock-batch`), which threads a once-per-batch memo, so a whole `ait ls` costs **one** digest no matter how many tasks are signed — the same property the board row above claims, reached the same way. |
| `archive_status_from_text()` (stats, trail) | **no — ratified** | Below. |
| monitor / minimonitor compact gate column | **no — ratified** | Below. |

**The two ratified ledger-only surfaces**, for reasons that are contractual
rather than merely economic:

- **`archive_status_from_text()`** is a **pure-text** function — no filesystem, no
  registry, no task id — which is the entire reason it exists beside
  `archive_status`. Re-validation needs all three, so threading a digest would
  not extend it but replace it. More decisively, `trail_gather.task_record()`
  hashes its verdict (`gates_pending`) into the trail's `input_digest` staleness
  key: a code-state-dependent verdict would flip every trail's staleness result
  on unrelated commits, turning a correctness fix into a correctness regression.
- **The monitor's compact gate column** calls `read_task_gate_state` with **no
  registry**, so it cannot classify a human gate at all. Its cache is keyed on
  the *task file*'s `(st_mtime_ns, st_size)`, and a code change does not touch
  that file — so a digest-sensitive verdict would need the digest in the cache
  key, recomputed on every 3 s tick, undoing the t1111_1 optimization that
  removed the per-tick cache clear. It also runs cross-project, where the
  cwd-relative witness path resolves elsewhere.

A task whose only unmet gate is a stale signature therefore still reads
archivable on those two, and blocked at the enforcing one. That is now a stated
contract with named reasons, not an untracked gap.

**Enforcement.** `tests/test_gate_ledger_only_surfaces.py` is a drift guard: it
scans `.aitask-scripts/` for ledger-only consumers and fails unless each is
registered with a reason, so the split cannot grow silently. Because the guard is
syntactic, it also treats any **re-binding** of a watched function (aliased
import, assignment, `map`/`partial` use, `getattr` on the gate modules) as a
finding — and the paired production convention is that
`archive_status_from_text` and `read_task_gate_state` are **called directly,
never aliased or indirected**. `tests/test_gate_stale_witness_parity.sh` pins the
flip on the three surfaces that now re-validate, each with its own single-mutation
negative control.

**Cost, measured (t1416).** `code_digest()` ≈ 5 ms on the framework repo. The
no-git pre-filter in `stale_signed_gates()` means a task with no stamped witness
pays ~2 µs, so the added cost is linear in the number of *signed* tasks, not in
the task count: +2.2% on `ait ls` at 50 signed tasks (crossing +10% around 230,
where the caller should thread the digest), and exactly one digest per board
refresh at any number.

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

The guard keys off the **declared `gates:` field**. `gates:` population is
**t635_14** (Phase 4), which has now landed: the shipped `fast` profile declares
`default_gates: [risk_evaluated]`, so `fast` tasks (and any task backfilled or
created under `fast`) carry `gates: [risk_evaluated]` and the guard **is now live
for them** — archival defers until `risk_evaluated` is recorded `pass`. The Step-9
gate orchestrator records that pass during the workflow (the risk verifier inspects
the `## Risk` section + frontmatter levels the producer authored), so a normal
`fast` run archives straight through; the guard only bites if the risk artifacts
are missing. The `default` profile declares no gates, so its tasks remain in the
dormant case (no `gates:` field → guard is a no-op → archives as today). Correctness
is proven by synthetic-fixture tests (`tests/test_gate_guarded_archival.sh`).

For a task declaring more gates, the integration gates recorded `pass` by t635_2
(`build_verified` / `review_approved` / `merge_approved`) archive normally; only
post-integration gates that pass out-of-band (async human review, `docs_updated`,
manual verification) defer archival — exactly the regression class this design
neutralizes. **Caveat:** declaring a human gate requires `record_gates: true` (only
the workflow records those), or archival deadlocks — see `task-workflow/profiles.md`
§Gate Declaration Model.

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
