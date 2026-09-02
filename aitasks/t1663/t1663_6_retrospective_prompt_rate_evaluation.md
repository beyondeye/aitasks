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
updated_at: 2026-09-02 10:05
---

Retrospective evaluation of the premise-staleness rollout: measure real prompt behavior and decide the deferred dispositions.

## Context

Sixth and final child of t1663 (depends on all siblings via the sequential chain). The tree committed to stored-baseline-only v1 under partial information (the 2026-09-01 no-go measurement in `aidocs/framework/task_premise_staleness.md`); this child collects the post-rollout data and turns each deferred item into an evidence-based call — filing standalone follow-up tasks ONLY if the data justifies them (audit-only outcome is a valid deliverable).

## What to measure (after the mechanism has been live long enough that seeded tasks have been picked — suggest ≥4 weeks or ≥20 seeded-task picks, whichever first)

- How many tasks carry `premise_baseline`; how many picks hit `ASK_STALE` vs `FRESH` vs `SKIP` (the Check 6 outcomes; if no telemetry exists, sample by re-running `aitask_premise_stale.sh check` over the seeded population and inspect gate-ledger/board history for prompt outcomes).
- Evidence actionability on seeded tasks (re-run the record's 5-sample stride audit over the seeded ASK_STALE pool, same pre-registered bar: ≤10 named drift sources).
- Any user-reported noise or ignored-prompt behavior.
- **Tier-B reachability (a measured input added by t1673).** Split the seeded population by trigger: how many tasks were seeded via `--file-ref` (Tier A) vs `--verifies` (Tier B), and of the `--verifies`-seeded ones, how many are `issue_type: manual_verification` and therefore routed away by task-workflow Step 3 Check 3 before the premise check ever runs. t1673 established that no in-framework *creation* caller currently produces a non-manual-verification `--verifies` task, so Tier B may ship live-by-contract but unexercised. If the Tier-A-only population is near-empty, the mechanism's organic coverage is the finding, not a side note.

## Dispositions this child owns (from the record's Deferred list)

- Computed origin-landing baseline behind a profile key: promote / keep deferred / drop, based on whether seeded-task evidence quality holds.
- `ait ls -v` staleness marker + board card badge: file the read-surface follow-up only if prompt-time-only visibility proved insufficient (precedent: the `plan_approved_at` visibility contract — verbose-only marker + filter flags).
- **Persisted exact-origin field for `--followup-of`** (added by t1673): the only way to make Tier B reachable for ordinary follow-ups without overturning `followup_origin.py`'s rule 1. Shape is the t1468_1 / t1468_2 field-foundation + creation-seams pair. Promote to a standalone task only if the seeded population shows the mechanism is worth extending.
- **Seeding on post-creation scope acquisition** (added by t1673): `aitask_update.sh --file-ref` / `--verifies` and `aitask_fold_mark.sh`'s unions can give an existing task a resolvable scope with no baseline, which reads `SKIP` forever. Decide whether to close that gap, and if so how "since when" is established honestly.
- Update `aidocs/framework/task_premise_staleness.md` with the measured outcomes (dated), keeping the record the single source of truth.

## Verification

- The record's Deferred section carries a dated disposition per item; any spawned follow-ups are linked from it and carry explicit dependencies.
