---
Task: t386_2_status_heartbeat_command_system.md
Parent Task: aitasks/t386_subagents_infra.md
Sibling Tasks: aitasks/t386/t386_1_*.md, t386_3_*.md through t386_7_*.md
Archived Sibling Plans: aiplans/archived/p386/p386_1_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: Status, Heartbeat & Command System

## Step 1: Create `agentcrew/agentcrew_utils.py`

Create `.aitask-scripts/agentcrew/agentcrew_utils.py`:

1. YAML helpers: `read_yaml(path)`, `write_yaml(path, data)`, `update_yaml_field(path, field, value)`
2. Status constants:
   - `AGENT_STATUSES = ["Waiting", "Ready", "Running", "Completed", "Aborted", "Error", "Paused"]`
   - `CREW_STATUSES = ["Initializing", "Running", "Killing", "Paused", "Completed", "Error"]`
3. Valid transitions dicts for both agent and agentcrew
4. `validate_agent_transition(current, target)` — returns bool
5. `validate_crew_transition(current, target)` — returns bool
6. `compute_crew_status(agent_statuses)` — derive agentcrew status from list of agent statuses
7. DAG operations: `topo_sort(agents_dict)` (Kahn's BFS), `detect_cycles(agents_dict)`
8. `get_ready_agents(worktree_path)` — agents with Waiting status whose all deps are Completed
9. Heartbeat: `check_agent_alive(alive_path, timeout_seconds)`, `get_stale_agents(worktree_path, timeout)`
10. Path helpers: `list_agent_files(worktree_path, suffix)`, `get_agent_names(worktree_path)`

## Step 2: Create `agentcrew/agentcrew_status.py`

Create `.aitask-scripts/agentcrew/agentcrew_status.py`:

1. Argument parsing (argparse): sub-commands `get`, `set`, `list`, `heartbeat`
2. `cmd_get(crew_id, agent_name=None)`:
   - If agent_name: read `<agent>_status.yaml`, output `AGENT_STATUS:<status>`, `AGENT_PROGRESS:<pct>`, `AGENT_HEARTBEAT:<ts>`
   - If no agent: read `_crew_status.yaml`, output `CREW_STATUS:<status>`, `CREW_PROGRESS:<pct>`
3. `cmd_set(crew_id, agent_name, new_status)`:
   - Validate transition
   - Update `<agent>_status.yaml` status field + timestamps
   - Recompute agentcrew status, update `_crew_status.yaml`
4. `cmd_list(crew_id)`:
   - Read all `*_status.yaml` + `*_alive.yaml`
   - Output: `AGENT:<name> STATUS:<status> PROGRESS:<pct> HEARTBEAT:<ts>` per agent
5. `cmd_heartbeat(crew_id, agent_name, message=None)`:
   - Update `<agent>_alive.yaml`: `last_heartbeat`, optional `progress_message`

## Step 3: Create bash wrapper `aitask_crew_status.sh`

Thin wrapper following `aitask_board.sh` pattern:
- Detect Python (venv > system)
- `exec "$PYTHON" "$SCRIPT_DIR/agentcrew/agentcrew_status.py" "$@"`

## Step 4: Create `aitask_crew_command.sh` (bash only)

Create `.aitask-scripts/aitask_crew_command.sh`:
- Sub-commands: `send`, `send-all`, `list`, `ack`
- `send`: Append command entry to `<agent>_commands.yaml` using heredoc/sed
- `send-all`: Loop through all Running agents, send to each
- `list`: Read and display `<agent>_commands.yaml`
- `ack`: Clear `pending_commands` in `<agent>_commands.yaml`

## Step 5: Create `agentcrew/__init__.py`

Empty package init file.

## Step 6: Update `ait` dispatcher

Add `status` and `command` subcommands to the agentcrew case.

## Step 7: Write tests and verify

- `tests/test_crew_status.sh`
- `python -m py_compile` on Python files
- `shellcheck` on bash files

## Step 8: Post-Implementation (Step 9)
