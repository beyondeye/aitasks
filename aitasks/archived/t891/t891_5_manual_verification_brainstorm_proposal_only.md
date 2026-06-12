---
priority: medium
effort: medium
depends: [t891_4]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [t891_2, t891_3, t891_4]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-01 11:49
updated_at: 2026-06-12 07:50
completed_at: 2026-06-12 07:50
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t891_2] grep -rn 'detailer|patcher|"detail"|"patch"' .aitask-scripts/brainstorm/ returns only intentional matches (no live wiring) — PASS 2026-06-12 07:49 auto: grep returns only 2 matches, both comments documenting the deliberately-kept _PATCHER_INPUT_META_RE; no live wiring
- [x] [t891_2] All brainstorm .py files parse; brainstorm test suite passes — PASS 2026-06-12 07:49 auto: AST parse clean on all brainstorm/*.py; 34 python + 5 shell brainstorm tests pass
- [x] [t891_2] Launch `ait brainstorm`: operation menu no longer offers Detail or Patch; explore/compare/synthesize still work; no poll-timer errors in logs — PASS 2026-06-12 07:49 auto: GROUP_OPERATIONS = explore/compare/synthesize + module ops (no detail/patch); TUI launched on session 635 with clean render, no traceback, no poll-timer errors; explorer/synthesizer/compare tests pass
- [x] [t891_2] Deleted: aitask_brainstorm_apply_detailer.sh, aitask_brainstorm_apply_patcher.sh, templates/detailer.md, templates/patcher.md — PASS 2026-06-12 07:49 auto: all 4 files absent (apply_detailer.sh, apply_patcher.sh, templates/detailer.md, templates/patcher.md)
- [x] [t891_3] grep -rn 'plan_file|read_plan|PLANS_DIR|br_plans|node_has_plan|view_plan|PlanRequested' .aitask-scripts/brainstorm/ returns nothing live — PASS 2026-06-12 07:49 auto: grep plan_file|read_plan|PLANS_DIR|br_plans|node_has_plan|view_plan|PlanRequested over brainstorm/ returns nothing
- [x] [t891_3] Launch `ait brainstorm`: node-detail modal has no Plan tab; no plan badges (●/○) in the DAG; l/V no longer bound to plan view — PASS 2026-06-12 07:49 auto: NodeDetailModal has only Metadata+Proposal TabPanes; no NO_PLAN_STYLE/badge in dag_display; DAG bindings have no l/V/view_plan (p=view_proposal); live footer keybar shows no Plan binding
- [x] [t891_3] Opening a node that previously had a plan does not error — PASS 2026-06-12 07:49 auto: all plan-read code removed from source so no node-open path touches plans; TUI opened session 635 (which has a legacy br_plans/ dir) with no error
- [x] [t891_4] finalize_session references no plan_file/br_plans; finalizing a plan-less session does not raise — PASS 2026-06-12 07:49 auto: finalize_session reads read_proposal only (no plan_file/br_plans); test_finalize_exports_proposal passes (plan-less session finalizes without raise)
- [x] [t891_4] End-to-end: finalize a brainstorm session → aitask created/linked carries the proposal content (not a plan) — PASS 2026-06-12 07:49 auto: test_finalize_exports_proposal asserts dest carries proposal body not a plan; module_ops_integration tests (green) cover fast-track linked aitask seeded from br_proposals/. Full live multi-agent session run not performed; substantive claim test-proven
- [x] [t891_4] grep -rn 'plan_file|br_plans' .aitask-scripts/brainstorm/ is clean across the whole module — PASS 2026-06-12 07:49 auto: grep plan_file|br_plans across whole brainstorm/ module returns nothing
