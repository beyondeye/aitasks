---
priority: low
effort: low
depends: [t1663_5]
issue_type: chore
status: Ready
labels: [task-workflow, verification]
gates: [risk_evaluated]
anchor: 1538
created_at: 2026-09-01 15:20
updated_at: 2026-09-01 15:20
---

Retrospective evaluation of the premise-staleness rollout: measure real prompt behavior and decide the deferred dispositions.

## Context

Sixth and final child of t1663 (depends on all siblings via the sequential chain). The tree committed to stored-baseline-only v1 under partial information (the 2026-09-01 no-go measurement in `aidocs/framework/task_premise_staleness.md`); this child collects the post-rollout data and turns each deferred item into an evidence-based call — filing standalone follow-up tasks ONLY if the data justifies them (audit-only outcome is a valid deliverable).

## What to measure (after the mechanism has been live long enough that seeded tasks have been picked — suggest ≥4 weeks or ≥20 seeded-task picks, whichever first)

- How many tasks carry `premise_baseline`; how many picks hit `ASK_STALE` vs `FRESH` vs `SKIP` (the Check 6 outcomes; if no telemetry exists, sample by re-running `aitask_premise_stale.sh check` over the seeded population and inspect gate-ledger/board history for prompt outcomes).
- Evidence actionability on seeded tasks (re-run the record's 5-sample stride audit over the seeded ASK_STALE pool, same pre-registered bar: ≤10 named drift sources).
- Any user-reported noise or ignored-prompt behavior.

## Dispositions this child owns (from the record's Deferred list)

- Computed origin-landing baseline behind a profile key: promote / keep deferred / drop, based on whether seeded-task evidence quality holds.
- `ait ls -v` staleness marker + board card badge: file the read-surface follow-up only if prompt-time-only visibility proved insufficient (precedent: the `plan_approved_at` visibility contract — verbose-only marker + filter flags).
- Update `aidocs/framework/task_premise_staleness.md` with the measured outcomes (dated), keeping the record the single source of truth.

## Verification

- The record's Deferred section carries a dated disposition per item; any spawned follow-ups are linked from it and carry explicit dependencies.
