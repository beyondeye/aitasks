---
priority: medium
effort: medium
depends: [808]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [808]
created_at: 2026-05-20 07:57
updated_at: 2026-05-20 07:57
boardidx: 180
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t808

## Verification Checklist

- [ ] Launch a brainstorm session and run a patcher agent; confirm the patcher output auto-applies via the TUI poll loop (_try_apply_patcher_if_needed) and the DAG refreshes with the new patched node.
- [ ] Confirm an IMPACT_FLAG patcher result populates the patcher impact banner with the IMPACT block text verbatim.
- [ ] Trigger a patcher apply failure (malformed _output.md) and confirm the error banner shows the `ait brainstorm apply-patcher ...` retry hint.
- [ ] Press ctrl+shift+r to force-retry a failed patcher apply; confirm it re-applies and clears the impact/error banner.
- [ ] Confirm explorer and synthesizer auto-apply still create nodes and merge NEW_DIMENSIONS correctly after the shared-core refactor.
