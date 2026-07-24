---
priority: medium
effort: medium
depends: [1211]
issue_type: manual_verification
status: Done
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1211]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-24 10:55
updated_at: 2026-07-24 11:10
completed_at: 2026-07-24 11:10
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1211

## Verification Checklist

- [x] Launch `ait board`, press `?` to open the shortcuts editor; confirm the shared scopes are listed and the board still works afterwards (this is the register_scope_bindings sweep path) — PASS 2026-07-24 11:09 auto: live tmux board run opened Shortcuts -- board and filtered shared.agent_cmd bindings
- [x] Open `ait settings` -> Shortcuts tab; confirm every TUI's bindings still appear and none are missing (the register_all_known_bindings sweep path) — PASS 2026-07-24 11:09 auto: live settings Shortcuts tab opened; registry sweep tests cover every discovered scope
- [x] In one board session, open and close the `?` shortcuts editor several times; confirm bindings still render correctly with no stale, duplicated or vanished entries (repeated sweeps overwrite the probe entry rather than accumulating) — PASS 2026-07-24 11:09 auto: live board run opened and closed the editor three times; canonical/probe identity tests passed
- [x] From the TUI switcher, trigger the agent-command / explore launch dialog; confirm the AgentCommandScreen dialog opens normally (this is the live isinstance surface that the canonical-name rebinding used to break) — PASS 2026-07-24 11:09 auto: live board switcher e action opened Launch Code Agent (no task) dialog
- [x] Confirm no `shortcut_scopes: could not load <module>` warnings are printed to stderr during any of the sweeps above — PASS 2026-07-24 11:09 auto: inspected live board, settings, and switcher stderr logs; no shortcut_scopes load warnings
