---
title: Dependency-Unblock Semantics for Gated Tasks
category: design
tags: [aitasks, gates, dependencies, unblock, depends, blocking, deferred-archival, ledger]
sources: [aitask-gate-framework.md, integration-roadmap.md]
confidence: high
created: 2026-06-14
updated: 2026-06-14
---

# Dependency-Unblock Semantics for Gated Tasks

How a task's `depends:` edges clear once the **gate framework** makes task
completion multi-stage. This is the design for **t635_3** (Phase 2 of
[[integration-roadmap]], "open problem 1"), and the contract that **t635_4**
(gate-guarded archival) and **t635_14** (profile gate declaration) build on.

## The problem

Today a dependency unblocks **purely on file existence**. `aitask_ls.sh`
(`is_task_uncompleted()`) returns "still blocking" iff the upstream task's ID is
present in the active-task set; archival removes the file, and the dependent
unblocks. (The board TUI has a parallel rule: a dep is unresolved while its
`status != 'Done'`.)

The gate framework's decision **D5** defers archival until *every* declared gate
passes (t635_4). That introduces a regression: a task whose substantive work is
done — code built, committed, merged — but whose **human or asynchronous
sign-off pends for days** (async remote review, a documentation gate, a manual
verification) **stays in the active set**, so its dependents stay blocked
*longer than they do today*. Deferred archival without an explicit unblock point
makes dependent availability worse, not better.

This document fixes the explicit unblock point so that deferred archival is
strictly an improvement.

## Model (decided with the user, 2026-06-14)

A **combined registry + per-task** model. Two surfaces, both expressing the same
idea — "which gates must pass before this task releases its dependents":

1. **Registry per-gate flag `blocks_dependents`** (`aitasks/metadata/gates.yaml`).
   A gate marked `blocks_dependents: true` is **required to pass before the
   owning task's dependents unblock**. This is the project-wide default per
   gate, declared once where gate semantics live.

2. **Per-task list `also_blocks_dependents`** (task frontmatter). An **additional**
   set of gates that must pass before *this specific task's* dependents unblock.
   It augments (never shrinks) the registry-default required set. Registered for
   durability across `ait update` / `ait create` / fold exactly like `gates:`.

### The unblock criterion

For an **active** upstream task `U` referenced by a dependent's `depends:`:

```
declared  = U.gates                       (frontmatter; absent/empty = "ungated")
also      = U.also_blocks_dependents       (per-task additions)
required  = { g ∈ declared : registry[g].blocks_dependents }  ∪  also

if required is empty            -> NO_GATES   (fall back to file-existence:
                                              U blocks until archived = today)
elif every g ∈ required is pass -> SATISFIED  (dependents proceed, even while
                                              non-required gates still pend)
else                            -> BLOCKED    (still-pending required gates)
```

The decision is a property of the **upstream** task, evaluated per `depends:`
edge. Derived gate state uses the standard last-run-wins derivation
(`gate_ledger.derive_status`). The implementation lives in
`.aitask-scripts/lib/gate_ledger.py` (`dependents_status` /
`required_unblock_gates`), surfaced as `aitask_gate.sh deps-unblock <task-id>`
(`SATISFIED` | `BLOCKED:<csv>` | `NO_GATES`), and consumed by `aitask_ls.sh`.

### Chain shapes (all uniform)

- **Ungated upstream** (no `gates:` field) → `NO_GATES` → file-existence
  (unchanged; honors the framework contract "no `gates:` = behaves like today").
- **Gated upstream, ungated dependent** → the upstream's gate state drives the
  unblock; the dependent being ungated is irrelevant.
- **Ungated upstream, gated dependent** → unchanged. A task's own gates never
  affect when *its* dependencies clear.

## The `blocks_dependents` flag on the 5 seeded gates

The axis is **"once this gate passes, is the task's code available for dependents
to build on?"** — *not* machine-vs-human. Integration gates are required;
pre-code and (future) post-integration sign-off gates are not.

| Gate | `blocks_dependents` | Why |
|------|---------------------|-----|
| `plan_approved`   | false | No code exists yet |
| `risk_evaluated`  | false | No code exists yet |
| `build_verified`  | true  | Implementation compiles / verify passes |
| `review_approved` | true  | Code committed (integration point for current-branch profiles) |
| `merge_approved`  | true  | Code on the base branch (integration point for worktree profiles) |

At the current stage the required set among the 5 is effectively `merge_approved`
(worktree) / `review_approved` (current-branch) — i.e. **the same point as
today's archival**. So this change introduces **neither a regression nor a
premature unblock now**. The flag becomes load-bearing once later phases add
*post-integration* gates with `blocks_dependents: false` — async human review
(t635_15), `docs_updated` (t635_19), manual verification — which is exactly the
regression class this design neutralizes: those gates can pend for days without
holding dependents.

## Dormancy / sequencing

The new behavior only differs from today for a task that is **active AND declares
gates AND has all required gates passed while still active**. That state is only
produced once **deferred archival** (t635_4) and a **populated `gates:` field**
(t635_14, Phase 4) exist. Until then, `aitask_ls.sh` finds no active task with a
`gates:` field, the gate-aware path is skipped entirely (a grep guard → zero
overhead, zero behavior change), and correctness is proven by synthetic-fixture
tests (`tests/test_dependency_unblock.sh`).

This is deliberate: t635_3 ships the **mechanism + contract**; t635_4 flips the
switch that makes it matter. t635_3 must land **before or with** t635_4 (a
deferred-archival change without this design would regress dependent
availability).

## Edge cases

- **Empty required set** (a task declares gates but flags none as blocking, and
  has no `also_blocks_dependents`): `NO_GATES` → falls back to file-existence
  (block until archived). Conservative — never unblocks prematurely.
- **An `also_blocks_dependents` entry that is not a declared/recorded gate**: it
  has no `pass` run, so it stays pending and keeps the task `BLOCKED`. This is
  visible (the gate name shows up in `BLOCKED:<csv>`) and safe (a typo blocks
  rather than silently unblocks); it should be a declared gate.

## Relationship to the framework's open question 4

The framework doc's open question 4 ("cross-task gates" — depend on a *specific*
gate of a *specific* upstream, e.g. `parent:t40:review`) stays deferred. This
design resolves the **unblock-timing** question by making the upstream's own gate
state the unblock signal. `also_blocks_dependents` lives on the **upstream**
(controlling when it releases *all* its dependents), not as a per-edge selector.
True per-edge gate dependencies remain out of scope.

## Rejected alternatives

- **Unblock at all-gates-pass (= archival).** Simplest, but inherits the exact
  slow-sign-off regression this design exists to fix.
- **Pure "machine unblocks, human doesn't".** Breaks worktree mode:
  `merge_approved` is a *human* gate but is the point at which code reaches the
  base branch — a dependent unblocked at `build_verified` would branch off a base
  without the upstream's code. The integration-vs-pre/post axis is correct;
  machine/human is not.
- **Per-task-only (no registry default).** Forces every task to re-declare the
  same unblock set → noise. The registry holds the sane default; the per-task
  list augments it.
- **Naming `unblocks_dependents:` / `unblock_after:`** (the roadmap straw-men).
  `blocks_dependents` reads naturally against the existing "blocked" vocabulary
  ("this gate blocks the task's dependents until it passes"); `also_blocks_dependents`
  parallels it for the per-task additions.

## See also

- [[aitask-gate-framework]] — the substrate contract (gate runs, registry, derivation).
- [[integration-roadmap]] — phase sequencing; this resolves Phase-2 open problem 1.
- t635_4 — gate-guarded archival (the consumer; archival stays the *all-gates-pass*
  event, distinct from unblock).
- t635_8 — shared Python gate-ledger parser (extends `gate_ledger.py`; TUIs consume
  `dependents_status`, do not fork it).
- t635_9 — board In-Flight view (wires the same gate-aware unblock into the board's
  independent dependency computation).
