---
priority: medium
effort: medium
depends: [t884_7]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [884_1, 884_2, 884_3, 884_4, 884_5, 884_6, 884_7]
created_at: 2026-06-01 00:35
updated_at: 2026-06-01 00:35
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t884_1] In `ait board`, a task with risk set shows its level; the detail-pane Risk CycleField cycles low/medium/high and saves; a task with no risk renders blank (no error).
- [ ] [t884_1] `ait create` interactive flow offers a Risk selection and `ait update` interactive flow offers Risk.
- [ ] [t884_1] Folding a task carrying risk_mitigation_tasks into a primary preserves the primary's risk and drops risk_mitigation_tasks.
- [ ] [t884_2] `ait settings` -> Profiles tab shows the risk_evaluation toggle under Planning; cycle + save persists to YAML and round-trips on reload.
- [ ] [t884_3] With risk_evaluation enabled, picking a task runs the risk-evaluation step at end of planning (assesses code-health AND goal-achievement) and the plan gains a populated ## Risk section; with it disabled, no risk step appears.
- [ ] [t884_3] After plan approval, the task's risk frontmatter field is written with the assessed aggregate level (visible in ait board).
- [ ] [t884_4] The mitigation step proposes before/after tasks and creates only the confirmed ones; a "before" mitigation makes the original show Blocked until it lands; an "after" mitigation is created post-implementation (Step 8d).
- [ ] [t884_5] After a "before" mitigation lands, re-picking the original forces plan re-verification (verify mode), not a silent skip; a task with no risk_mitigation_tasks picks normally.
- [ ] [t884_6] The website renders the new risk docs (board risk field, risk-eval workflow, risk_evaluation profile key) with no broken links.
- [ ] [t884_7] The deferred follow-up tasks (Codex/OpenCode ports, priority+risk enum refactor, gates integration) exist with correct t884 cross-references.
