---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [framework]
gates: [risk_evaluated]
anchor: 1311
created_at: 2026-07-29 17:00
updated_at: 2026-07-29 17:00
---

## Origin

Spawned from t1311 during Step 8b review. Both defects were hit live while
re-picking t1311 after its "before" risk-mitigation (t1317) had landed.

## Upstream defect

- `.claude/skills/task-workflow/risk-mitigation-followup.md:136-194` — Part 2
  ("before" creation) has no idempotency guard: re-picking a task whose
  before-mitigation was already created and landed would create a duplicate task
  and re-add it to `depends:` / `risk_mitigation_tasks`. The plan line already
  carries a `created: t<id>` annotation that a guard could read.
- `.claude/skills/task-workflow/planning.md:29-56` — Step 6.0a's force-reverify
  handoff is inert under `plan_preference: use_current`.
  `aitask_risk_mitigation_landed.sh` returns `FORCE_VERIFY:0` when the plan has
  no prior `plan_verified` entry, on the stated assumption that "`decide` already
  returns VERIFY" — but `decide` only runs on the **verify** path. A parent task
  under the `fast` profile (`plan_preference: use_current`) therefore never
  re-verifies its plan after a before-mitigation lands.

## Diagnostic context

t1311's first session evaluated risk, created t1317 as a `timing: before`
mitigation, wired `depends: [1317]` + `risk_mitigation_tasks: [1317]`, reverted
t1311 to `Ready`, and ended — exactly as designed. t1317 then landed and
archived.

On the second `/aitask-pick 1311` (profile `fast`), both defects surfaced:

1. **Step 6.0a produced `FORCE_VERIFY:0`** even though t1317 had demonstrably
   landed after the plan was written. Cause: the plan's `plan_verified` list was
   empty, so the helper took its "no prior verification → `decide` will return
   VERIFY anyway" early return. But `fast` sets `plan_preference: use_current`
   for parent tasks, so the Verify Decision sub-procedure never runs and `decide`
   is never called. The plan was used as-is, un-re-verified, against a codebase
   that had changed underneath it. The helper's own comment states the assumption
   that makes this a real gap rather than an intended shortcut.

2. **Step 7 would have re-created the mitigation.** The dispatch condition is
   just "the approved plan has a `### Planned mitigations` subsection with ≥1
   `before` line" — which is permanently true, because the design part writes
   that subsection into the plan and never removes it. Part 2's procedure has no
   step that checks whether the named mitigation already exists. The implementing
   agent had to notice the `created: t1317` annotation and skip Part 2 by hand,
   and would then also have hit the workflow-stopping branch (`risk_before_created:
   true` reverts the task to `Ready` and ends the session), making the task
   permanently un-implementable without manual intervention.

## Suggested fix

For (1): make Step 6.0a's force-verify signal independent of the plan-preference
path — either honour `FORCE_VERIFY:1` by overriding `use_current` for that pick,
or drop the "no prior verification → no-op" early return so a landed mitigation
always forces a re-verify. Note the helper's early return is *correct* for the
`verify` path; the fix belongs at the caller or in the return contract, not by
deleting the branch.

For (2): give Part 2 an idempotency guard keyed on the `created: t<id>`
annotation the plan line already carries — treat an annotated line whose task
exists (active or archived) as already-created, and skip it. Set
`risk_before_created: true` only for mitigations actually created in this run, so
a task with no *new* before-mitigations proceeds to implementation instead of
being reverted to `Ready`.

Verify with a fixture task whose plan carries an annotated, already-landed
`before` line: re-picking it must neither create a second mitigation nor stop the
workflow.
