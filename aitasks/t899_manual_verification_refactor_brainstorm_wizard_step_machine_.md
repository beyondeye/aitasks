---
priority: medium
effort: medium
depends: [898]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [898]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-02 07:51
updated_at: 2026-06-02 09:14
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t898

## Verification Checklist

- [ ] Drive `ait brainstorm` and confirm the step indicator + every transition matches pre-refactor behaviour (per aidocs/tui_conventions.md):
- [ ] explore op: op-select -> node-select -> config -> confirm; Enter/Next/Back/Esc + mouse click each step; step indicator shows "of 4"
- [ ] explore op on a node WITH sections: section-select appears after node choice; indicator becomes "of 5" (node-select stays "of 4" on first visit, "of 5" after visiting sections via Back)
- [ ] patch op: same shape as explore; patch-on-node-with-no-plan is blocked and stays on node-select (guard intact)
- [ ] detail op: op-select -> node-select -> [section-select?] -> confirm (NO config step); detail "node" is recorded into the summary
- [ ] compare op and synthesize op: op-select -> config -> confirm (NO node-select); Tab cycles control groups on config; up/down navigates the section checkboxes
- [ ] session ops (pause/resume/finalize/archive): op-select -> confirm directly; confirm label now reads "Step 2 of 2" (was "Step 3 of 3") -- confirm this is acceptable
- [ ] delete op: still opens the delete modal (no wizard steps)
- [ ] "A"-key node-action modal entry from the Graph/Dashboard tab: enters mid-flow at node-select for the chosen node and advances correctly into the Actions tab
- [ ] Esc/Back from every step returns to the correct previous step for all op families (resolver-driven prev); up/down navigation works on op-select and node-select OperationRows and cycles focus on confirm
