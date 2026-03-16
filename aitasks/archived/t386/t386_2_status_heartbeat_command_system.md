---
priority: medium
effort: high
depends: [t386_1, 1]
issue_type: feature
status: Done
labels: [agentcrew]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-15 10:51
updated_at: 2026-03-16 22:22
completed_at: 2026-03-16 22:22
---

## Agent Status, Heartbeat & Command System

### Context
This child task builds the status management, heartbeat monitoring, and command delivery system for the AgentCrew infrastructure. It depends on t386_1 (data model and init/add scripts).

### Goal
Implement reliable YAML-based status read/update, heartbeat monitoring with stuck-agent detection, and a command system for sending kill/pause/resume signals to agents. The core logic is in Python (`agentcrew_status.py`, `agentcrew_utils.py`) with a thin bash wrapper for CLI use.

### Key Files to Create
- `.aitask-scripts/agentcrew/agentcrew_utils.py` — Shared Python module: YAML read/write helpers, DAG operations (topo sort via Kahn's BFS, cycle detection), status validation (valid transitions for both agent and agentcrew states), heartbeat timestamp math. Used by status, runner, and report modules.
- `.aitask-scripts/agentcrew/agentcrew_status.py` — Python core: sub-commands `get`, `set`, `list`, `heartbeat`. Reliable YAML parsing for `*_status.yaml` and `*_alive.yaml`. State machine validation. Structured output: `AGENT_STATUS:`, `AGENT_PROGRESS:`, etc.
- `.aitask-scripts/aitask_crew_status.sh` — Thin bash wrapper (venv detection, exec Python)
- `.aitask-scripts/aitask_crew_command.sh` — Bash-only script: sub-commands `send`, `send-all`, `list`, `ack`. Appends commands to `*_commands.yaml`. Output: `COMMAND_SENT:<cmd>`
- `.aitask-scripts/agentcrew/__init__.py` — Package init
- `tests/test_crew_status.sh` — Tests for status transitions, heartbeat, commands

### Status State Machines

**Agent statuses:** Waiting, Ready, Running, Completed, Aborted, Error, Paused
**Valid transitions:**
- Waiting -> Ready (deps met)
- Ready -> Running (launched)
- Running -> Completed|Error|Aborted|Paused
- Paused -> Running (resumed)

**AgentCrew statuses:** Initializing, Running, Killing, Paused, Completed, Error
**Computation from agents:**
- All Completed -> AgentCrew Completed
- Any Error (no Running) -> AgentCrew Error
- Any Running -> AgentCrew Running
- All Waiting -> Initializing

### Heartbeat System
- Configurable timeout (default 5min) in `_crew_meta.yaml`
- `check_agent_alive()`: compare `last_heartbeat` in `*_alive.yaml` to current time
- `get_stale_agents()`: return Running agents exceeding timeout

### Command System
- Commands: `kill`, `pause`, `resume`, `update_instructions`
- Format in `*_commands.yaml`:
  ```yaml
  pending_commands:
    - command: kill
      sent_at: <timestamp>
      sent_by: runner|user
  ```
- `ack` sub-command clears pending commands after agent processes them

### Reference Files for Patterns
- `.aitask-scripts/board/task_yaml.py` — YAML handling patterns
- `.aitask-scripts/aitask_board.sh` — Python launcher wrapper pattern
- `.aitask-scripts/aitask_lock.sh` — Structured output (check/list)
- `.aitask-scripts/lib/terminal_compat.sh` — `portable_date` for timestamp compat

### Verification
- `bash tests/test_crew_status.sh`
- `python -m py_compile .aitask-scripts/agentcrew/agentcrew_status.py`
- `python -m py_compile .aitask-scripts/agentcrew/agentcrew_utils.py`
- `shellcheck .aitask-scripts/aitask_crew_status.sh .aitask-scripts/aitask_crew_command.sh`
