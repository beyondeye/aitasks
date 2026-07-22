---
priority: medium
effort: medium
depends: [t1162_5]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1162_1, 1162_2, 1162_3, 1162_4, 1162_5]
anchor: 1162
created_at: 2026-07-22 11:02
updated_at: 2026-07-22 11:02
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1162_1] Run ./.aitask-scripts/aitask_work_report_gather.sh --list-columns in this repo and confirm the emitted columns match ait board's left-to-right order, with Unsorted first only when it currently has tasks
- [ ] [t1162_2] Run ./.aitask-scripts/aitask_codeagent.sh --dry-run invoke work-report --columns now --tasks <some-id> and confirm the composed command resolves the lightweight default model (same class as explain) and passes --columns/--tasks through verbatim
- [ ] [t1162_3] Run /aitask-work-report with no arguments in an agent session; confirm interactive column + task selection, the horizon prompt, and a drafted report containing exactly the selected tasks in board order (no report file written)
- [ ] [t1162_3] Zero-history projection: run the skill against a tree with no archived completions and confirm the report states insufficient completion history instead of fabricating a rate
- [ ] [t1162_3] Custom horizon: choose a custom label via free text and confirm it labels the report without changing task membership
- [ ] [t1162_4] Happy path: ait board -> focus a column -> press w -> change both selections -> launch an agent -> choose a period -> confirm the report contains exactly the selected tasks in board order with a clearly labeled projection section
- [ ] [t1162_4] Validation-error stop: launch from the board, then archive or delete one selected task before the agent runs the gatherer; confirm the skill stops with the error shown and offers re-select/abort (does NOT draft)
- [ ] [t1162_4] Stale reorder: reorder a selected task within its column after board launch; confirm task_order_changed stops the draft
- [ ] [t1162_4] Footer gating: w is visible only in persistent kanban views when a focused card or collapsed-column placeholder identifies a column; hidden in In-Flight and By-Topic views
- [ ] [t1162_5] Browse the built website docs and confirm the skill page, workflow page, and board shortcut row render and cross-link correctly
