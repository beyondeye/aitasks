---
priority: medium
effort: high
depends: [t386_2, 1, 2]
issue_type: feature
status: Done
labels: [agentcrew]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-15 10:51
updated_at: 2026-03-17 09:53
completed_at: 2026-03-17 09:53
---

## Agent Runner (Orchestrator)

### Context
The runner is the central orchestration component of the AgentCrew infrastructure. It periodically checks agent states, resolves dependencies, launches ready agents, monitors health, and commits/pushes state changes. It runs as a single-instance process per agentcrew, with cross-machine awareness. Depends on t386_1 and t386_2.

### Goal
Implement the runner as a Python script (`agentcrew_runner.py`) with a bash wrapper, featuring: topological sort for dependency resolution, single-instance enforcement (cross-machine aware via git), per-type `max_parallel` enforcement, graceful shutdown, and diagnostics.

### Key Files to Create
- `.aitask-scripts/agentcrew/agentcrew_runner.py` — Python core: main orchestration loop
- `.aitask-scripts/aitask_crew_runner.sh` — Thin bash wrapper (venv detection, exec Python)
- `tests/test_crew_runner.sh` — Tests for dep resolution, launch order, dry-run

### Runner Main Loop
Args: `--crew <id> --interval 30 --max-concurrent 3 --once --dry-run --batch --check`

Each iteration:
1. Update `_runner_alive.yaml` (heartbeat + next_check_at)
2. `git pull` to receive commands/stop signals
3. Check `requested_action` in `_runner_alive.yaml` — if `stop`, graceful shutdown
4. Read all agent statuses
5. Check agent heartbeats, mark stale agents as Error
6. Process pending commands
7. Find ready agents (Waiting + all deps Completed)
8. Enforce per-type `max_parallel` limits from `_crew_meta.yaml`
9. Launch ready agents up to limit
10. Compute agentcrew status, write to `_crew_status.yaml`
11. `git commit+push` if changes
12. Sleep for interval

### Single-Instance Enforcement (Cross-Machine)
1. `git pull` the agentcrew branch
2. Read `_runner_alive.yaml` — if `status: running`:
   - Same hostname: check PID alive (`kill -0`) AND heartbeat fresh (within 2x interval)
   - Different hostname: heartbeat freshness only
   - If alive: refuse to start
   - If stale: clean up, proceed
3. Write own PID/hostname/status, commit+push

### Agent Launching
- Resolve `agent_type` from `_status.yaml` -> look up `agent_string` in `_crew_meta.yaml` agent_types
- Launch via `subprocess.Popen(["ait", "codeagent", "--agent-string", resolved, "invoke", ...])`
- Store PID in `_status.yaml`, update status to Running

### Diagnostic Mode
`--check` flag: `git pull` first, prints runner status (alive/stale/stopped), hostname, PID, heartbeat age, next check time. Exit 0 if running, 1 if not.

### Graceful Shutdown
- Signal handlers: SIGTERM/SIGINT
- Also triggered by `requested_action: stop` in `_runner_alive.yaml`
- Send kill commands to all running agents
- Update `_runner_alive.yaml` status to `stopped`
- Transition agentcrew to Killing

### Reference Files for Patterns
- `.aitask-scripts/agentcrew/agentcrew_utils.py` — Shared DAG/status logic (from t386_2)
- `.aitask-scripts/aitask_board.sh` — Python launcher pattern
- `.aitask-scripts/aitask_sync.sh` — Timeout and network handling
- `.aitask-scripts/aitask_codeagent.sh` — Agent invocation patterns

### Verification
- `bash tests/test_crew_runner.sh`
- `python -m py_compile .aitask-scripts/agentcrew/agentcrew_runner.py`
- Manual: init agentcrew with 3 agents (A->B->C), run `--once --dry-run` to verify launch order
