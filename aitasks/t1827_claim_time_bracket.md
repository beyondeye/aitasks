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
created_at: 2026-09-17 11:27
updated_at: 2026-09-17 11:27
---

## Origin

Risk-mitigation ("after") follow-up for t1824, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — creation time is stricter than admission time

From t1824's `## Risk`: "Creation-time is stricter than admission-time; legitimate pre-claim edits (coordination sections, checklists) are admission-visible, so creation time is only the strict bound · severity: low · → mitigation: claim_time_bracket".

## Goal

t1824 bounded hindsight bias in t1814's `task_declared` precision using each
archived task description's FIRST data-branch version. It found that on the
393-task cohort, `e845e8423e8130f9|393`, creation-time precision is ≥ current
(task 0.4562 vs 0.4461; task-vs-plan 0.4467 vs 0.4393) and ≥ the plan
pre-implementation reference (0.4068) at threshold 10. See
`aiplans/archived/p1824_creation_time_description_hindsight.md` for tables and
method.

Creation time is the strict bound. What the admission checker actually sees is
the body at claim time, which includes legitimate pre-claim edits. Measure that
bracket:

1. For each cohort task, find the first commit on the data branch whose subject
   names the task's OWN id: `ait: Start work on t<id>:` (claim). Do not use a
   commit that merely touched the file: those "Start work" commits routinely
   carry other tasks' files through the shared index. Take the task file's
   content in that commit's PARENT (the pre-claim body). Tasks with no own
   claim commit are excluded and counted.
2. Reuse t1824's method unchanged: frozen t1814 inputs via a validated
   root-aware wrapper, and one explicit cohort intersected across the current,
   creation and claim roots, imposed by pruning. Check digest equality, check
   byte-identical plan outputs across roots, and include a negative control.
   Re-validate the wrapper against t1814's published outputs first, and account
   for any cohort dropout.
3. Report claim-time vs creation-time vs current precision / recall /
   hard-stop share for `--source task --population common` and
   `--source task-vs-plan` at pre-implementation scope, thresholds 8/10/20.
   State whether claim time lies between the two, and whether t1814's Q1 rule
   (description precision ≥ plan reference) still holds, conditional on the
   cohort.
4. Note the result to t1688_2.

Known limit carried from t1824: a reparented task's history under its previous
id is invisible when keying by id (`635_13` was the one cohort case).
