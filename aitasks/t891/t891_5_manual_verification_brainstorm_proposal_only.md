---
priority: medium
effort: medium
depends: [t891_4]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [t891_2, t891_3, t891_4]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-01 11:49
updated_at: 2026-06-11 13:11
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t891_2] grep -rn 'detailer|patcher|"detail"|"patch"' .aitask-scripts/brainstorm/ returns only intentional matches (no live wiring)
- [ ] [t891_2] All brainstorm .py files parse; brainstorm test suite passes
- [ ] [t891_2] Launch `ait brainstorm`: operation menu no longer offers Detail or Patch; explore/compare/synthesize still work; no poll-timer errors in logs
- [ ] [t891_2] Deleted: aitask_brainstorm_apply_detailer.sh, aitask_brainstorm_apply_patcher.sh, templates/detailer.md, templates/patcher.md
- [ ] [t891_3] grep -rn 'plan_file|read_plan|PLANS_DIR|br_plans|node_has_plan|view_plan|PlanRequested' .aitask-scripts/brainstorm/ returns nothing live
- [ ] [t891_3] Launch `ait brainstorm`: node-detail modal has no Plan tab; no plan badges (●/○) in the DAG; l/V no longer bound to plan view
- [ ] [t891_3] Opening a node that previously had a plan does not error
- [ ] [t891_4] finalize_session references no plan_file/br_plans; finalizing a plan-less session does not raise
- [ ] [t891_4] End-to-end: finalize a brainstorm session → aitask created/linked carries the proposal content (not a plan)
- [ ] [t891_4] grep -rn 'plan_file|br_plans' .aitask-scripts/brainstorm/ is clean across the whole module
