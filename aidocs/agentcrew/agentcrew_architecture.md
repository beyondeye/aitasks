# AgentCrew Architecture Reference

AgentCrew is a file-based DAG orchestration system for coordinating multiple AI code agents. Agents communicate through YAML files in a shared git branch — no backend infrastructure required. A central runner script launches agents, monitors heartbeats, enforces concurrency limits, and manages the lifecycle.

## Lifecycle

```
ait crew init          Create crew branch + worktree, write metadata
        ↓
ait crew addwork       Register agents with work2do files and dependencies
        ↓
ait crew runner        Launch orchestrator loop (continuous or one-shot)
        ↓
  [agents execute]     Agents read work2do, write output, send heartbeats
        ↓
ait crew report        Query status, aggregate outputs
        ↓
ait crew cleanup       Remove completed crew worktrees and branches
```

## Branch and Worktree Structure

Each crew operates on a dedicated git branch with its own worktree:

- **Branch:** `crew-<id>` (created from HEAD at init time)
- **Worktree:** `.aitask-crews/crew-<id>/`
- **Parent directory:** `.aitask-crews/` (created automatically)

The branch holds all coordination files. Agents write their status and output to this branch. The runner serializes git operations (commit + push) so agents never conflict. Actual implementation work (source code changes) happens on main or task branches — the crew branch is purely for coordination.

## File Layout

All files live in the crew worktree at `.aitask-crews/crew-<id>/`.

### Crew-Level Files

| File | Type | Purpose |
|------|------|---------|
| `_crew_meta.yaml` | Static config | Agent types, heartbeat timeout, agent list |
| `_crew_status.yaml` | Dynamic state | Crew status, progress, timestamps |
| `_runner_alive.yaml` | Runner heartbeat | PID, hostname, heartbeat, control signals |

### Per-Agent Files (7 files per agent)

| File | Purpose | Written by |
|------|---------|-----------|
| `<agent>_status.yaml` | Status, progress, dependencies, timestamps | Runner (state transitions) |
| `<agent>_work2do.md` | Task specification for the agent | `addwork` (read-only after creation) |
| `<agent>_input.md` | Input data from upstream agents or runner | Runner or upstream agents |
| `<agent>_output.md` | Results written by the agent | Agent |
| `<agent>_instructions.md` | Lifecycle instructions (which scripts to call) | `addwork` (template) |
| `<agent>_commands.yaml` | Inbound command queue (kill, pause, resume) | CLI or runner |
| `<agent>_alive.yaml` | Heartbeat timestamp and progress message | Agent |

## YAML Schemas

### `_crew_meta.yaml` (static configuration)

```yaml
id: sprint1                           # Crew identifier
name: Sprint 1 Planning               # Human-readable display name
created_at: 2026-03-17 12:00:00       # UTC timestamp
created_by: user@example.com          # From userconfig.yaml
agents: [planner, coder, reviewer]    # Registered agent names
heartbeat_timeout_minutes: 5          # Agent heartbeat timeout (default: 5)
agent_types:
  impl:
    agent_string: claudecode/opus4_6   # Code agent to launch
    max_parallel: 0                    # 0 = unlimited, >0 = max concurrent
  review:
    agent_string: claudecode/sonnet4_6
    max_parallel: 2
```

### `_crew_status.yaml` (dynamic state)

```yaml
status: Running                       # See crew status state machine below
progress: 33                          # Percentage (0-100), derived from agents
started_at: 2026-03-17 12:01:00       # When first agent started
updated_at: 2026-03-17 12:05:00       # Last status recomputation
```

### `_runner_alive.yaml` (runner heartbeat and control)

```yaml
status: running                       # "running" or "stopped"
pid: 12345                            # Runner process ID
hostname: workstation-1               # Machine where runner is executing
started_at: 2026-03-17 12:00:00       # Runner start time
last_heartbeat: 2026-03-17 12:05:00   # Last heartbeat update
next_check_at: 2026-03-17 12:05:30    # When next iteration will run
interval: 30                          # Seconds between iterations
requested_action: null                # Set to "stop" for graceful shutdown
```

### `<agent>_status.yaml` (agent coordination state)

```yaml
agent_name: coder                     # Agent identifier
agent_type: impl                      # References _crew_meta.yaml agent_types key
status: Running                       # See agent status state machine below
depends_on: [planner]                 # Upstream agent dependencies
created_at: 2026-03-17 12:00:00
started_at: 2026-03-17 12:01:00      # Set on transition to Running
completed_at:                         # Set on transition to terminal state
progress: 45                          # 0-100, set by agent
pid: 12346                            # Process ID of launched agent
error_message:                        # Set if status is Error
```

### `<agent>_alive.yaml` (agent heartbeat)

```yaml
last_heartbeat: 2026-03-17 12:05:00   # Agent's last heartbeat signal
last_message: Processing file 3 of 10 # Optional progress message
```

### `<agent>_commands.yaml` (inbound command queue)

```yaml
pending_commands:
- command: pause                       # One of: kill, pause, resume, update_instructions
  sent_at: '2026-03-17 12:04:00'
  sent_by: user                        # "user" or "runner"
```

Empty state: `pending_commands: []`

## Status State Machines

### Agent Statuses

Valid statuses: `Waiting`, `Ready`, `Running`, `Completed`, `Aborted`, `Error`, `Paused`

```
Waiting ──→ Ready ──→ Running ──→ Completed (terminal)
                         │
                         ├──→ Error (terminal)
                         │
                         ├──→ Aborted (terminal)
                         │
                         └──→ Paused ──→ Running
```

**Transition details:**
- `Waiting → Ready`: All dependencies completed (set by runner)
- `Ready → Running`: Agent launched (set by runner)
- `Running → Completed/Error/Aborted`: Agent finishes (set by agent or runner)
- `Running → Paused`: Pause command processed (set by runner)
- `Paused → Running`: Resume command processed (set by runner)
- **Terminal states:** `Completed`, `Aborted`, `Error` — no outgoing transitions

### Crew Statuses

Valid statuses: `Initializing`, `Running`, `Killing`, `Paused`, `Completed`, `Error`

```
Initializing ──→ Running ──→ Completed (terminal)
                    │
                    ├──→ Error (terminal)
                    │
                    ├──→ Killing ──→ Completed (terminal)
                    │                    │
                    │                    └──→ Error (terminal)
                    │
                    └──→ Paused ──→ Running
                            │
                            └──→ Killing
```

**Crew status is derived** from agent statuses — it is recomputed by the runner after each state change. Derivation rules (in priority order):

1. All agents `Completed` → Crew `Completed`
2. Any `Error` + no `Running` agents → Crew `Error`
3. Any `Running` agent → Crew `Running`
4. All `Waiting` → Crew `Initializing`
5. Any `Paused` + no `Running` → Crew `Paused`
6. Mixed states → Crew `Running`

## Agent Types and Per-Type Concurrency

Agent types are defined in `_crew_meta.yaml` under `agent_types`. Each type maps to:

- **`agent_string`**: Identifies the code agent and model (e.g., `claudecode/opus4_6`). Used by the runner to launch the agent via `ait codeagent --agent-string <value>`.
- **`max_parallel`**: Maximum concurrent agents of this type. `0` means unlimited. The runner enforces this limit when selecting which ready agents to launch.

**Enforcement order:**
1. Per-type `max_parallel` limits are applied first
2. Overall `max_concurrent` limit is applied second

Example: With `max_concurrent: 3`, `impl.max_parallel: 1`, `review.max_parallel: 2` — if 4 agents are ready (2 impl, 2 review), the runner launches: 1 impl (type limit) + 2 review = 3 total (overall limit).

## DAG Dependency Model

Agents declare dependencies via the `depends_on` field in `_status.yaml`. Dependencies are validated at registration time.

### Ready Detection

An agent is **ready** when:
- Status is `Waiting`, AND
- `depends_on` is empty, OR all dependencies have status `Completed`

### Topological Sort

Used by `ait crew report output` to aggregate outputs in dependency order. Implementation: Kahn's BFS algorithm (in `agentcrew_utils.py`). Raises `ValueError` if a cycle is detected.

### Cycle Detection

Performed at agent registration time (`ait crew addwork`) using DFS. If the proposed agent would create a cycle, registration is rejected. Both bash (`detect_circular_deps()` in `lib/agentcrew_utils.sh`) and Python implementations exist.

## Runner Orchestration

The runner (`ait crew runner`) is the central orchestrator. It runs in a loop, each iteration performing:

```
1. Update runner heartbeat (_runner_alive.yaml)
2. Git pull (best-effort, non-blocking)
3. Check for stop request (requested_action in _runner_alive.yaml)
4. Read all agent statuses
5. Mark stale agents as Error (heartbeat timeout exceeded)
6. Process pending commands (pause/resume from _commands.yaml)
7. Find ready agents (Waiting + all deps Completed)
8. Filter by per-type max_parallel limits
9. Filter by overall max_concurrent limit
10. Launch ready agents (Waiting → Ready → Running, spawn subprocess)
11. Recompute crew status from all agent statuses
12. Report progress (PROGRESS, ETA, RUNNING count, READY count)
13. Check if all agents terminal → stop runner
14. Git commit + push all changes
15. Sleep for interval seconds
```

### Runner Configuration

Stored in `aitasks/metadata/crew_runner_config.yaml`:

```yaml
interval: 30          # Seconds between runner iterations
max_concurrent: 3     # Maximum agents running simultaneously
```

**Resolution order:** CLI args (`--interval`, `--max-concurrent`) > config file > hardcoded defaults (30s, 3).

The `ait setup` command seeds this file from `seed/crew_runner_config.yaml`.

### Runner Flags

```
--crew <id>          Required. Crew identifier.
--interval N         Override iteration interval.
--max-concurrent N   Override max concurrent agents.
--once               Single iteration then exit.
--dry-run            Show actions without executing.
--check              Diagnostic mode (report runner status).
--force              Force-kill existing runner on same host.
--batch              Structured output for scripting.
```

## Single-Instance Enforcement

Only one runner can be active per crew. Enforcement uses `_runner_alive.yaml`:

**Same host** (hostname matches):
1. Check if PID is alive (`os.kill(pid, 0)`)
2. Check heartbeat freshness (≤ `interval × 2` seconds)
3. Both alive AND fresh → reject (or force-kill with `--force`)
4. PID dead OR heartbeat stale → allow takeover

**Different host** (hostname differs):
1. Fresh heartbeat → reject (cannot force-kill remote process)
2. Stale heartbeat → allow takeover with warning

## Concurrent Write Strategy

The crew worktree is a shared filesystem. Conflict is avoided by role separation:

- **Agents write:** `_alive.yaml` (heartbeat), `_output.md` (results). These are agent-owned files.
- **Runner writes:** `_status.yaml` (state transitions), `_crew_status.yaml`, `_runner_alive.yaml`. Runner uses field-level YAML updates (read → modify → write).
- **CLI writes:** `_commands.yaml` (appends to pending queue).
- **Runner serializes git:** Only the runner runs `git add -A && git commit && git push`. Agents never touch git directly.

No explicit file locking is used. Field-level updates assume YAML reads and writes are atomic enough for the single-writer-per-file pattern.

## Command and Control

Commands are sent to agents via `_commands.yaml`. Valid commands: `kill`, `pause`, `resume`, `update_instructions`.

### Sending Commands

```bash
# Single agent
ait crew command send --crew <id> --agent <name> --command <cmd>

# All running agents
ait crew command send-all --crew <id> --command <cmd>
```

### Command Processing

The runner processes `pause` and `resume` commands by transitioning agent status. Kill is **not** processed by the runner — it is the agent's responsibility to check for kill commands and perform a clean shutdown.

**Pause flow:** CLI sends `pause` → runner reads `_commands.yaml` → validates `Running → Paused` → updates status → clears pending commands.

**Kill flow:** CLI sends `kill` → agent polls `_commands.yaml` at checkpoints → agent runs abort procedure → agent sets status to `Aborted`.

**Graceful shutdown:** When the runner receives SIGTERM/SIGINT or `requested_action: stop`:
1. Sends `kill` to all running agents via `send-all`
2. Updates runner status to `stopped`
3. Updates crew status to `Killing`
4. Commits and pushes

## Heartbeat and Stuck-Agent Detection

Agents signal liveness by updating `<agent>_alive.yaml` at regular intervals (via `ait crew status --crew <id> --agent <name> heartbeat`).

**Timeout:** Configured in `_crew_meta.yaml` as `heartbeat_timeout_minutes` (default: 5 minutes = 300 seconds).

**Detection:** Each runner iteration calls `get_stale_agents()` which checks all `Running` agents:
- If `_alive.yaml` doesn't exist, or `last_heartbeat` is missing/unparseable, or `now - last_heartbeat > timeout` → agent is stale.

**Action on stale agent:**
- Status set to `Error`
- `error_message` set to `"Heartbeat timeout — agent presumed dead"`
- `completed_at` set to current time

## TUI Dashboard

The crew dashboard (`ait crew dashboard`) provides a Textual-based terminal UI for monitoring and managing crews. See the dedicated dashboard documentation for keybindings, screens, and features.

## CLI Reference

All commands route through the `ait` dispatcher:

| Command | Script | Purpose |
|---------|--------|---------|
| `ait crew init` | `aitask_crew_init.sh` | Create crew branch + worktree |
| `ait crew addwork` | `aitask_crew_addwork.sh` | Register agent with work2do |
| `ait crew status` | `aitask_crew_status.sh` → `agentcrew_status.py` | Get/set agent and crew status |
| `ait crew command` | `aitask_crew_command.sh` | Send commands to agents |
| `ait crew runner` | `aitask_crew_runner.sh` → `agentcrew_runner.py` | Start/check orchestrator |
| `ait crew report` | `aitask_crew_report.sh` → `agentcrew_report.py` | Summary, detail, output aggregation |
| `ait crew cleanup` | `aitask_crew_cleanup.sh` | Remove completed crews |
| `ait crew dashboard` | `aitask_crew_dashboard.sh` → `agentcrew_dashboard.py` | TUI monitoring |

## Key Implementation Files

| File | Purpose |
|------|---------|
| `.aitask-scripts/agentcrew/agentcrew_utils.py` | Status constants, transitions, DAG ops, heartbeat checking |
| `.aitask-scripts/agentcrew/agentcrew_runner.py` | Runner orchestrator (main loop, single-instance, agent launch) |
| `.aitask-scripts/agentcrew/agentcrew_status.py` | Status management CLI |
| `.aitask-scripts/agentcrew/agentcrew_report.py` | Reporting and output aggregation |
| `.aitask-scripts/agentcrew/agentcrew_dashboard.py` | Textual TUI dashboard |
| `.aitask-scripts/lib/agentcrew_utils.sh` | Bash utilities (YAML I/O, validation, cycle detection) |
| `.aitask-scripts/aitask_crew_command.sh` | Command control (send, send-all, list, ack) |
| `.aitask-scripts/aitask_crew_addwork.sh` | Agent registration (creates 7 files per agent) |
| `.aitask-scripts/aitask_crew_init.sh` | Crew initialization |
| `.aitask-scripts/aitask_crew_cleanup.sh` | Worktree and branch cleanup |
| `seed/crew_runner_config.yaml` | Default runner configuration template |
