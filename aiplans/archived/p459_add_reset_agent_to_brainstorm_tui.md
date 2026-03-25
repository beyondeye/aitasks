---
Task: t459_add_reset_agent_to_brainstorm_tui.md
Worktree: (current directory)
Branch: main
Base branch: main
---

# Plan: Add Reset Agent to Brainstorm TUI (t459)

## Context

The agentcrew dashboard TUI (t452) already has per-agent reset functionality (Error → Waiting) via the `w` keybinding. The brainstorm TUI lacks this feature. The backend infrastructure (runner command handling, state transitions) is already in place — only the TUI integration needs to be added.

## Changes

### 1. Add `send_agent_command()` to `agentcrew_runner_control.py`

Extract the `send_command` logic from `CrewManager` in the dashboard into a standalone function in `agentcrew_runner_control.py` (which the brainstorm app already imports from). Update `CrewManager.send_command()` to delegate.

### 2. Add `AgentStatusRow` widget class to brainstorm_app.py

Focusable widget following the `StatusLogRow` pattern, storing agent_name, agent_status, crew_id, and display_line.

### 3. Add CSS for `AgentStatusRow`

Focus/hover styles matching `GroupRow` pattern.

### 4. Modify `_mount_agent_row()` to use `AgentStatusRow`

Replace `Label` with `AgentStatusRow`, passing crew_id from session data.

### 5. Add `w` key handler in `on_key()`

Validates Error state, sends reset command via `send_agent_command()`, shows notification, refreshes status tab.

### 6. Update import

Add `send_agent_command` to the existing import from `agentcrew.agentcrew_runner_control`.

## Files Modified

1. `.aitask-scripts/agentcrew/agentcrew_runner_control.py` — add `send_agent_command()`
2. `.aitask-scripts/agentcrew/agentcrew_dashboard.py` — update import, delegate `CrewManager.send_command()`
3. `.aitask-scripts/brainstorm/brainstorm_app.py` — add `AgentStatusRow`, CSS, key handler, import

## Verification

1. Run brainstorm TUI: `./ait brainstorm <task_num>`
2. Navigate to Status tab, expand a group with an agent in Error state
3. Focus the agent row — should see "(w: reset)" hint
4. Press `w` — should see "Agent <name> reset to Waiting" notification, UI refreshes after 2 seconds
5. Press `w` on a non-Error agent — should see warning notification

## Final Implementation Notes
- **Actual work done:** Added `AgentStatusRow` focusable widget, `w` key handler with direct status file update, focus hint for Error agents, CSS styles, delayed refresh for runner actions. Extracted `send_agent_command()` to `agentcrew_runner_control.py` and made `CrewManager.send_command()` delegate to it.
- **Deviations from plan:** Reset uses direct status file update instead of `send_agent_command()` — the runner-based command approach was unreliable when the runner wasn't active or was slow to process. Start/stop runner actions also updated to use delayed refresh (2-second timer) instead of immediate refresh.
- **Issues encountered:** Initial implementation sent reset via runner command, but the status file wasn't updated when the runner wasn't active. Changed to always update the status file directly. Also added focus/blur handlers to `AgentStatusRow` to trigger re-render of the "(w: reset)" hint.
- **Key decisions:** Direct status file update is more reliable for the brainstorm TUI since agents are often in Error state without an active runner. The `send_agent_command()` function remains available in `agentcrew_runner_control.py` for use cases where the runner is expected to be active.
