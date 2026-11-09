---
priority: low
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [task_relations, backlog]
gates: [risk_evaluated]
anchor: 1981
created_at: 2026-11-09 11:01
updated_at: 2026-11-09 11:01
---

## Context

Deferred from t1981_6, the obsolescence layer (`aidocs/framework/task_relations.md` D9, "Obsolescence API").

In v1, every path row is **context**: `path_deleted`, `path_renamed`, `path_ambiguous`. Context rows never trigger an assessment, never enter `evidence_digest`, and never reach the assessor. Each row reports a factual file event: how the cited name's latest lifetime ended, following renames forward in sequence and showing `lifetimes=<n>`.

The rows stay context because nothing proves that the task's **current** citation refers to the lifetime that ended. Two plan-review rounds on t1981_6 rejected the cheap attempts:

- **Anchoring at the task's `created_at`** fails when the reference is introduced by a later edit or by the plan.
- **Anchoring at the oldest task-data commit that added the token** fails when a citation is removed and reintroduced. In "cite A, drop the citation, A→B, recreate A, cite A again, delete the new A", the oldest mention selects the wrong lifetime.
- **A single deletion** cannot distinguish a reference written before the deletion from a task proposing to recreate the file.

## Goal

Attribute a path event to the current citation when that can be **proved**, and promote only those rows to signal. Everything unproved stays context.

## Directions to evaluate

- Date the **current** citation, not the oldest: the newest commit that added the token without a later commit removing it (a blame-style walk over the task file and plan in the task-data history), per occurrence.
- Treat a stamped plan's `data_commit` (the approval stamp, D2) as a bound: a path cited in the approved plan was cited no later than the approval.
- Recognise planned recreation ("recreate `x`", a path under "Files to create") as context, never signal.
- Any promotion of path rows to signal changes `evidence_digest` for many tasks and resurfaces dismissals. Plan the rollout, and measure the signal rate first (t1981_6 measured 75 path rows over 544 tasks, all context).

## References

- `.aitask-scripts/lib/obsolescence_evidence.py` (`path_fact`, `path_rows`, `History`).
- `tests/test_obsolescence_evidence.py`: the lifetime fixtures and the "path rows never assert obsolescence" cases, which must keep holding for unproved attributions.
- The archived plan of t1981_6: design decisions 1 and 9, and the plan-review history.
