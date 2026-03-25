---
priority: medium
effort: low
depends: []
issue_type: feature
status: Implementing
labels: [agentcrew]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-25 08:18
updated_at: 2026-03-25 09:35
---

## Summary

Add the per-agent reset functionality (Error → Waiting) to the brainstorm TUI, matching what was implemented in the agentcrew dashboard TUI in t452.

## Reference Implementation

See `agentcrew_dashboard.py` (committed in t452):
- `action_reset_agent()` method in `CrewDetailScreen` — validates agent is in Error state, sends `reset` command via `manager.send_command()`
- `w` keybinding: `Binding("w", "reset_agent", "Reset to Waiting")`

## Key Points

- The `reset` command is already registered in `VALID_COMMANDS` in `aitask_crew_command.sh`
- The runner already handles the `reset` command in `process_pending_commands()`
- The `Error → Waiting` transition is already allowed in `AGENT_TRANSITIONS`
- Only the TUI integration in the brainstorm screen needs to be added
