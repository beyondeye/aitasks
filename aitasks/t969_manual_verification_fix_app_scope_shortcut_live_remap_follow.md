---
priority: medium
effort: medium
depends: [964]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [964]
created_at: 2026-06-10 18:17
updated_at: 2026-06-10 18:17
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t964

## Verification Checklist

- [ ] Launch a TUI (e.g. Settings), open the Shortcuts editor (?), rebind an App-scope key (e.g. e export to another key), restart, then press the new key — confirm the action fires and the old key no longer does.
- [ ] Repeat for a modal scope (e.g. shared.agent_cmd / shared.stale_entry) — confirm the rebound key fires inside the modal.
- [ ] Confirm framework keys (ctrl+c quit, ctrl+p command palette) still work while a shortcut override is active.
