---
Task: t386_3_agent_runner_orchestrator.md
Parent Task: aitasks/t386_subagents_infra.md
Sibling Tasks: aitasks/t386/t386_1_*.md, t386_2_*.md, t386_4_*.md through t386_7_*.md
Archived Sibling Plans: aiplans/archived/p386/p386_1_*.md, p386_2_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: Agent Runner (Orchestrator)

## Step 1: Implement `agentset_runner.py`

Create `.aitask-scripts/agentset/agentset_runner.py`:

### 1a: Argument parsing
- `--agentset <id>` (required)
- `--interval <seconds>` (default: 30)
- `--max-concurrent <n>` (default: 3, overall cap)
- `--once` (single iteration, no loop)
- `--dry-run` (show actions without executing)
- `--batch` (structured output)
- `--check` (diagnostic mode, exit 0 if running, 1 if not)

### 1b: Single-instance enforcement
- `git -C <worktree> pull` to get latest `_runner_alive.yaml`
- Parse runner alive file
- If `status: running`:
  - Same hostname: check PID via `os.kill(pid, 0)` + heartbeat freshness (2x interval)
  - Different hostname: heartbeat freshness only
  - Alive: print error + exit 1
  - Stale: log warning, clean up, proceed
- Write own status: PID (`os.getpid()`), hostname (`socket.gethostname()`), timestamps
- `git commit+push`

### 1c: Diagnostic mode (`--check`)
- `git pull`, read `_runner_alive.yaml`
- Print: status, hostname, PID, heartbeat age, next_check_at, alive/stale assessment
- Exit 0 if running, 1 if not

### 1d: Main loop
```python
while not should_stop:
    update_runner_alive(heartbeat, next_check_at)
    git_pull()
    if check_requested_action() == "stop":
        graceful_shutdown()
        break
    statuses = read_all_agent_statuses()
    stale = get_stale_agents(statuses, timeout)
    mark_stale_as_error(stale)
    process_pending_commands(statuses)
    ready = get_ready_agents(statuses)
    ready = enforce_type_limits(ready, meta.agent_types)
    ready = ready[:max_concurrent - count_running(statuses)]
    for agent in ready:
        launch_agent(agent)
    update_agentset_status(statuses)
    git_commit_push_if_changes()
    if once:
        break
    sleep(interval)
```

### 1e: Per-type max_parallel enforcement
- Read `agent_types` from `_agentset_meta.yaml`
- Count currently Running agents per type
- Only launch agents of type X if running_count < max_parallel (0 = unlimited)

### 1f: Agent launching
- Read `agent_type` from `_status.yaml`
- Look up `agent_string` in `_agentset_meta.yaml` agent_types
- `subprocess.Popen(["./ait", "codeagent", "--agent-string", agent_string, "invoke", "raw", "--prompt", work2do_content])`
- Store PID in `_status.yaml`, set status to Running, `started_at`

### 1g: Graceful shutdown
- Signal handlers: `signal.signal(SIGTERM, handler)`, `signal.signal(SIGINT, handler)`
- Also triggered by `requested_action: stop`
- Send kill commands to all Running agents via `aitask_agentset_command.sh send-all <id> kill`
- Update `_runner_alive.yaml` status to `stopped`
- Update `_agentset_status.yaml` status to `Killing`

### 1h: Progress and ETA
- Progress: `completed_count / total_count * 100`
- ETA: average completion time of finished agents * remaining count

## Step 2: Create bash wrapper

`.aitask-scripts/aitask_agentset_runner.sh` — thin wrapper with venv detection.

## Step 3: Update `ait` dispatcher

Add `runner` subcommand to agentset case.

## Step 4: Write tests

`tests/test_agentset_runner.sh`:
- Init agentset, add 3 agents (A depends on nothing, B depends on A, C depends on A+B)
- `--once --dry-run` shows A as ready first
- After manually marking A complete, B becomes ready
- Per-type limit enforcement (set max_parallel=1, verify only 1 launched)

## Step 5: Post-Implementation (Step 9)
