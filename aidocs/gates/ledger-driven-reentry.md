---
title: Ledger-Driven Re-entry
category: design
tags: [aitasks, gates, re-entry, resume, task-workflow, crash-recovery, ledger, deferred-archival]
sources: [aitask-gate-framework.md, integration-roadmap.md, gate-guarded-archival.md]
confidence: high
created: 2026-06-15
updated: 2026-06-15
---

# Ledger-Driven Re-entry

Phase 2 of the gate-framework roadmap ([[integration-roadmap]], decision
**D3** — re-entry is priority #1). This is the companion to
[[gate-guarded-archival]] (t635_4): that doc decides *when a gated task may
archive*; this one decides *where a re-entered in-flight task resumes*.

## Problem

A task left `Implementing` — a crash, a lost session, multi-day work, or
gate-guarded archival deferring at workflow end (t635_4) — should resume from
the first unmet checkpoint, skipping what is already done. Today re-entry state
lives only in the conversation: the crash-recovery path (task-workflow Step 4)
reclaims the lock, but the workflow then re-runs Step 6 (for child tasks,
re-verifies the plan) and Step 7 from the top. That is wasteful and lossy — the
durable record of "plan approved, code reviewed" exists in the ledger but is
not consulted.

## Criterion

Re-entry keys off the **recorded `## Gate Runs` checkpoints** (t635_2:
`plan_approved` → `review_approved`), **not** the declared `gates:` field. This
is the crucial contrast with [[gate-guarded-archival]]'s `archive_status`, which
reads declared gates: archival asks "is every *declared* gate pass?"; re-entry
asks "how far did the *recorded workflow* get?". The two derivations are
deliberately separate functions in `lib/gate_ledger.py` and must not be
conflated.

`resume_point(task_file)` derives a 3-state result via the same back-to-front
last-block-wins rule (decision **D6**, `derive_status`) — so a re-opened
checkpoint (`pass` → `fail`) correctly demotes the resume stage:

| Result | Condition | Resume target |
|--------|-----------|---------------|
| `PLAN` | `plan_approved` not `pass` (incl. empty ledger) | Plan from scratch (today's flow) |
| `IMPLEMENT` | `plan_approved` pass, `review_approved` not pass | Step 7 implementation body |
| `POSTIMPL` | `review_approved` pass | Step 9 (merge / build / archive) |

`risk_evaluated` (a quick post-approval write) and `build_verified` /
`merge_approved` (which live inside Step 9) are **not** re-entry boundaries —
the workflow cannot act on them as distinct resume points, so they collapse into
the three stages above.

Surfaced as `aitask_gate.sh resume-point <task-id>` (python-delegated, degrades
to `PLAN` if Python is absent — safe: plan from scratch as today).

## Re-entry flow (task-workflow)

1. **Step 3 Check 5** reads `status`; if `Implementing`, runs `resume-point`.
   `PLAN` → no-op (normal flow). `IMPLEMENT` / `POSTIMPL` → set the
   `resume_point` context variable and show a banner with the recorded state and
   resume target. It then **proceeds to Step 4** — ownership must be (re)claimed
   before any work resumes.
2. **Step 4** claims/reclaims ownership exactly as today (the crash-recovery
   reclaim prompt, now ledger-enriched, is the confirmation).
3. **Re-entry Routing** (end of Step 4) routes by `resume_point`: `IMPLEMENT` →
   Step 7's implementation body; `POSTIMPL` → Step 9.

### Routing is gated on `resume_point`, not on the reclaim branch

`aitask_pick_own.sh` emits a `RECLAIM_*` signal only when the task was already
`Implementing` **and** assigned to the same email. A force-unlock takeover of
someone else's in-flight task returns plain `OWNED` with no reclaim signal — so
binding the routing to crash-recovery's `reclaim` return would silently lose the
resume on that path. The Re-entry Routing gate therefore fires at the end of
Step 4 on **any** ownership-success path, keyed only on the `resume_point`
context variable.

### `IMPLEMENT` resumes at the implementation body, not Step 7's top

Step 7's pre-implementation gates include two **non-idempotent task creators** —
Cross-Repo Child Assignment and Risk-mitigation "before" creation — each of
which *ends the workflow* when it fires. A task that is still a normal
`Implementing` single task is therefore necessarily *past* them; re-running Step
7 from the top would double-create. So `IMPLEMENT` resumes at the "Follow the
approved plan" body, re-running only the idempotent ownership guard and Agent
Attribution (which re-records the resuming agent).

## Folds into the existing reclaim confirmation

Re-entry introduces **no new prompt**. The crash-recovery reclaim prompt already
asks "Reclaim and continue?" and surveys uncommitted changes; it is enriched to
show the resume target. This keeps the conservative-by-default posture: a stale
ledger cannot cause silent harm because `IMPLEMENT` lands at Step 7 (which
re-runs implementation anyway) and `POSTIMPL` lands at Step 9 (whose merge
approval is NON-SKIPPABLE).

## Live immediately (contrast with t635_4 dormancy)

Unlike gate-guarded archival — dormant until t635_14 populates the `gates:`
field — re-entry keys off the **recorded** ledger, which `record_gates: true`
already populates. So it goes **live immediately for the `fast` profile**: a
re-picked in-flight `fast` task with recorded checkpoints resumes from the first
unmet one. It stays inert where the ledger is empty (profiles without
`record_gates`, or a task that crashed before `plan_approved`): `resume-point`
returns `PLAN` and the flow is exactly today's. A plan-existence guard falls back
to `PLAN` if a checkpoint was recorded but no plan was externalized.

## Crash-recovery generalization

`crash-recovery.md` now treats the gate ledger as the **primary** progress
signal: its survey runs `aitask_gate.sh status` and reports the resume target,
with the old plan-file-marker heuristic kept as a fallback for empty ledgers.
Its `reclaim` / `decline` return contract is unchanged — routing is driven by the
`resume_point` context variable at the end of Step 4, so crash-recovery only
surveys and displays; it does not route.

## Rejected alternatives

- **A finer resume stage per recorded gate.** `risk_evaluated` /
  `build_verified` / `merge_approved` are not workflow re-entry boundaries
  (risk is a post-approval write; build/merge live inside Step 9), so per-gate
  stages add states the workflow cannot act on. The 3-state collapse is exact.
- **A separate "resume here?" AskUserQuestion.** Redundant with the reclaim
  prompt the user already answers; re-entry folds into it instead.
- **Gating the skill edits behind `record_gates` (Jinja).** Re-entry keys off
  ledger *presence*, not the recording profile key; an empty ledger already
  derives to `PLAN`, so the prose is profile-invariant and inert without a
  ledger (mirrors t635_4 Check 4).
- **Binding routing to crash-recovery's `reclaim` branch.** Loses the resume on
  the plain-`OWNED` takeover path (see above).
- **Re-running Step 7 from the top on `IMPLEMENT`.** Double-creates the
  non-idempotent post-approval tasks (see above).

## See also

- [[integration-roadmap]] — Phase 2, decision D3 (re-entry priority #1).
- [[gate-guarded-archival]] — the companion archival-timing decision (t635_4);
  the deferred-`Implementing` state is exactly the in-flight resume signal this
  doc keys on.
- [[aitask-gate-framework]] — "Decision tree (re-entry)" and "Re-entry contract";
  the stateful re-entrant orchestrator (t635_11) reuses the same derivation.
