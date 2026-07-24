---
priority: medium
effort: medium
depends: [1211]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [1211]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-24 10:55
updated_at: 2026-07-24 11:01
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1211

## Verification Checklist

- [ ] Launch `ait board`, press `?` to open the shortcuts editor; confirm the shared scopes are listed and the board still works afterwards (this is the register_scope_bindings sweep path)
- [ ] Open `ait settings` -> Shortcuts tab; confirm every TUI's bindings still appear and none are missing (the register_all_known_bindings sweep path)
- [ ] In one board session, open and close the `?` shortcuts editor several times; confirm bindings still render correctly with no stale, duplicated or vanished entries (repeated sweeps overwrite the probe entry rather than accumulating)
- [ ] From the TUI switcher, trigger the agent-command / explore launch dialog; confirm the AgentCommandScreen dialog opens normally (this is the live isinstance surface that the canonical-name rebinding used to break)
- [ ] Confirm no `shortcut_scopes: could not load <module>` warnings are printed to stderr during any of the sweeps above
