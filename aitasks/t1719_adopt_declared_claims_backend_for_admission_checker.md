---
priority: high
effort: high
depends: []
issue_type: refactor
status: Ready
labels: [gates, backend]
created_at: 2026-09-06 17:07
updated_at: 2026-09-06 17:07
---

Swap the parallel-admission checker's **evidence backend** to t1343's
declared-claims model — a per-task claim store under `.aitask-gates/<id>/` with
deterministic set intersection emitting `PAIR:` / `PHASE:` / `UNCLAIMED:` /
`CLEAN:`.

This is a **backend swap behind an unchanged verdict contract**, not a rewrite.
`decide()` keeps its `CLEAR` / `CLEAR_CAVEATED` / `CONFLICT` / `UNCHECKABLE`
vocabulary and its `UNCHECKABLE_CAUSE:` line protocol; only where the in-flight
file surface comes from changes.

## Why this matters more than it did

t1343's `depends: [1275]` is satisfied — t1275 landed 2026-08-25 — and
t1569_4's preflight is the consumer surface t1343 was previously missing.

**It is also what closes the point-in-time race.** The current checker
*observes* a surface; a claim registry *reserves* it. Every "CLEAR means no
known conflict at check time, never safe to run in parallel" hedge in the
roadmap, the preflight and their docs exists because of that gap.

## Evidence from the first real roadmap run (2026-09-06)

Measured over 255 candidates by `aitask_backlog_roadmap.sh`:

- **214 of 255 candidates are `UNCHECKABLE`**, cause `no_plan=214`.
- 0 candidates were `CLEAR`. The parallel-safe lane was **empty**.

The cause is evidence availability: an in-flight claim's surface is read from
its plan file only, and most `Implementing` tasks carry no plan. A claim store
written at claim time exists in exactly the claim→plan window where the plan
does not.

Coordinate with **t1688**, which attacks the same gap from the other side (a
task-body surface + a pre-pick assessment). These are complementary, not
duplicates: t1688 widens the evidence available *today*; this task replaces the
evidence model. Decide the sequencing before implementing either.

## Coordination

Bidirectional note added to t1343.
