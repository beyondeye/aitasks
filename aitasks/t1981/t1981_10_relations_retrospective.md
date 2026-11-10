---
priority: low
effort: low
depends: [t1981_8, t1981_9, t1981_11]
issue_type: chore
status: Ready
labels: [task_relations]
gates: [risk_evaluated]
anchor: 1981
created_at: 2026-11-04 15:39
updated_at: 2026-11-10 12:47
---

## Context

Child of t1981: the **retrospective evaluation** (D13.3 in
`aidocs/framework/task_relations.md`). The design made several choices on
partial information and deferred decisions to measured data. This child reads
that data and decides. It files standalone follow-up tasks **only where the
data justifies them**. An audit-only outcome is a valid result.

**Precondition:** relation analysis has been enabled in this repository for at
least 4 weeks, or at least 100 records exist. If neither holds when this task
is picked, report the counts and stop (Postpone).

## Inputs

- The store (`ait relations status`, `usage`, records).
- The local ledgers `pull.jsonl` and `notify.jsonl`, from every host that ran
  analysis. Ask the user to collect them from other hosts.
- The archive: completion times.
- The D13.1 / D13.2 replay reports in t1981_2's archived plan.

## Questions to answer, each with the numbers behind it

1. **The D5 default** (`relations.enabled: false`). Actual usage: jobs, tokens,
   cost and wall time per day, per operation and per trigger. Should the default
   change?
2. **Stale-relation handling (explicit reassessment, D11).**
   - Were stale relations shown at pick time or offered at Step 8e still useful?
   - Did they cause misleading or unwanted notifications (stale PUSH rows
     declined, or sent but wrong)?
   - Should the refresh triggers change? Today there is no re-analysis on plan
     edits, and `sweep --stale` is the only catch-up.
   - Should the display rule change? Today stale relations are shown with a
     marker and never hidden.
3. **Push precision.** The share of PUSH rows sent vs declined, and the share
   that were `unconfirmed_impact` in PULL. Did the direction guard and the
   impact-only confirmation behave as intended?
4. **Incomplete analysis at Step 8e.** How often each state occurred
   (`inputs_mismatch`, `unverifiable`, `pending`, `failed`, `missing`), and the
   option chosen each time.
5. **The late-relation gap (D8).** Records published after their source landed,
   with targets that were in flight at that moment. Is a retained review needed?
   If yes, the follow-up design **must** use one resolution identity shared by
   the immediate and the later path, scoped to (source, target, landed change),
   so it never duplicates a note already sent.
6. **Reverse lookup cost (D3).** Is a tree-SHA-keyed cache needed (reads > 500 ms)?
7. **Roadmap integration (D9).** Should `lib/roadmap_policy.py` get an obsolete
   band slot?
8. **Non-Claude headless support (D5).**
9. **Orphan-branch module (D1).** Should `aitask_lock.sh` / `aitask_claim_id.sh`
   adopt `lib/orphan_ref_store.py`?

## Deliverable

The findings, with numbers, written into this child's plan. Follow-up tasks are
created only for the questions the data answers "change".

## Implementation plan

See `aiplans/p1981/p1981_10_relations_retrospective.md`.
