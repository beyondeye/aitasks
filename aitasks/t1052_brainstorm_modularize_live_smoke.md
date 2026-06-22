---
priority: medium
effort: medium
depends: [1048]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1048]
created_at: 2026-06-22 12:19
updated_at: 2026-06-22 12:19
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1048

## Verification Checklist

- [ ] Launch `ait brainstorm <session>` from the real entry point; confirm the app boots and renders the Browse/Session/Running tabs and the header strip.
- [ ] Browse tab: toggle graph/list view; select a node and open the node-op wizard (A/Enter); step forward/back through the wizard steps and confirm filtering works.
- [ ] Proposal preview: confirm the preview pane + minimap render, scroll, and focus-cycle (inputs -> minimap -> proposal) correctly.
- [ ] Session tab: confirm session content renders; press V/Enter on a DimensionRow to push the section viewer.
- [ ] Running tab: confirm GroupRow/AgentStatusRow/ProcessRow render and polling updates status without error.
- [ ] Open representative modals (node detail/hub, compare matrix, operation detail, export, init/delete) and confirm styling/layout is unchanged from before the modularization.
- [ ] Confirm no runtime NameError/traceback appears on any exercised path (the core risk of the module split).
