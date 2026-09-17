---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [scheduling, planning]
gates: [risk_evaluated]
anchor: 1569
followup_kind: risk_mitigation
created_at: 2026-09-17 09:02
updated_at: 2026-09-17 09:02
---

## Origin

Risk-mitigation ("after") follow-up for t1814, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — post-hoc description edits may inflate task_declared precision

From t1814's `## Risk`: "Archived task descriptions may have been edited after the work started (hindsight), inflating description precision/recall; the plan side has `--plan-scope pre-implementation` but the description side has no equivalent cut · severity: medium · → mitigation: creation_time_description_hindsight".

## Goal

Bound the hindsight bias in t1814's `task_declared` precision numbers before
anyone acts on its Q1 recommendation. The recommendation is that description
overlaps grade like plan overlaps, which would lift PINNED 6 to parity.

t1814 measured, on a frozen snapshot of the 400-task common cohort at hub
threshold 10:
- Promoted whole-body description precision was 0.4387, against a plan
  pre-implementation reference of 0.4036.
- In the description-vs-plan pairing it was 0.4333.

Those numbers read the CURRENT archived task files. A description edited while
or after the work happened (a fold, a hand edit naming the files that actually
changed) would look more precise than it was at admission time.

Do this:
1. For each archived task in the cohort, recover the task file's FIRST version
   on the task-data branch: `git log --diff-filter=A --format=%H -- <path>` in
   `.aitask-data`, following renames into `aitasks/archived/`. Then `git show`
   that blob.
2. Run the same sweep over those creation-time bodies. Reuse
   `sweep_population(..., source="task")` machinery against a scratch root
   built from the recovered bodies, with the batch map and corpus frozen as in
   t1814's pre-phase.
3. Report creation-time vs current precision, recall and hard-stop share for
   `--source task` (common) and `--source task-vs-plan` (pre-implementation),
   on an identical `SWEEP_COHORT:` digest.
4. Record whether t1814's Q1 conclusion (description precision ≥ plan
   reference) survives. If it does, note that to t1688_2. Tasks whose first
   version cannot be recovered (e.g. created before the data branch existed)
   are excluded, and the count is reported.

Key files: `.aitask-scripts/lib/parallel_admission_collect.py`
(`sweep_population`, `_archived_task_paths`),
`.aitask-scripts/lib/parallel_admission_sweep.py`, and the measurement tables in
`aiplans/archived/p1814_measure_task_declared_precision.md`.
