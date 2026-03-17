---
Task: t386_3_agent_runner_orchestrator.md
Parent Task: aitasks/t386_subagents_infra.md
Sibling Tasks: aitasks/t386/t386_1_*.md, t386_2_*.md, t386_4_*.md through t386_7_*.md
Archived Sibling Plans: aiplans/archived/p386/p386_1_*.md, p386_2_*.md, p386_8_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: Agent Runner (Orchestrator)

## Step 1: Implement `agentcrew_runner.py`

Create `.aitask-scripts/agentcrew/agentcrew_runner.py`:

### 1a: Argument parsing
- `--crew <id>` (required)
- `--interval <seconds>` (default: None — resolved from config)
- `--max-concurrent <n>` (default: None — resolved from config)
- `--once` (single iteration, no loop)
- `--dry-run` (show actions without executing)
- `--batch` (structured output)
- `--check` (diagnostic mode, exit 0 if running, 1 if not)
- `--force` (kill existing local runner and restart)

**Config resolution order** (for `interval` and `max_concurrent`):
1. CLI args (highest priority, if explicitly provided)
2. `aitasks/metadata/crew_runner_config.yaml` (project-wide defaults)
3. Hardcoded fallbacks: interval=30, max_concurrent=3

### 1b: Single-instance enforcement
- `git -C <worktree> pull` to get latest `_runner_alive.yaml`
- If `status: running`:
  - **Same hostname:** check PID via `os.kill(pid, 0)` + heartbeat freshness (2x interval)
    - If alive AND `--force`: kill old runner (`os.kill(pid, SIGTERM)`), wait briefly, clean up, proceed
    - If alive AND no `--force`: print error ("Runner already active, use --force to restart"), exit 1
    - If stale (PID dead or heartbeat expired): log warning, clean up, proceed
  - **Different hostname:** heartbeat freshness only
    - If fresh: refuse to start (even with `--force` — cannot kill remote process), exit 1
    - If stale: log warning, clean up, proceed
- Write own PID (`os.getpid()`), hostname (`socket.gethostname()`), timestamps
- `git commit+push` in worktree

### 1c: Diagnostic mode (`--check`)
- `git pull`, read `_runner_alive.yaml`
- Print: status, hostname, PID, heartbeat age, next_check_at, alive/stale assessment
- Exit 0 if running, 1 if not

### 1d: Main loop
```python
while not should_stop:
    update_runner_alive(heartbeat, next_check_at)
    git_pull(worktree)
    if check_requested_action() == "stop":
        graceful_shutdown()
        break
    statuses = read_all_agent_statuses(worktree)
    stale = get_stale_agents(worktree, timeout)
    mark_stale_as_error(stale)
    process_pending_commands(statuses)
    ready = get_ready_agents(worktree)  # Waiting agents with deps Completed
    ready = enforce_type_limits(ready, meta.agent_types)
    ready = ready[:max_concurrent - count_running(statuses)]
    for agent in ready:
        launch_agent(agent)  # Waiting→Ready→Running + subprocess.Popen
    update_crew_status(statuses)
    git_commit_push_if_changes(worktree)
    if once:
        break
    sleep(interval)
```

**Key detail — agent state transitions:** `get_ready_agents()` returns `Waiting` agents with deps completed. Runner must transition each through `Waiting→Ready→Running` using `update_yaml_field()` and `validate_agent_transition()`.

### 1e: Per-type max_parallel enforcement
- Read `agent_types` from `_crew_meta.yaml`
- Count currently Running agents per type
- Only launch agents of type X if running_count < max_parallel (0 = unlimited)

### 1f: Agent launching
- Read `agent_type` from `_status.yaml`
- Look up `agent_string` in `_crew_meta.yaml` agent_types
- Read work2do content from `<agent>_work2do.md`
- `subprocess.Popen(["./ait", "codeagent", "--agent-string", agent_string, "invoke", "raw", "-p", work2do_content], cwd=worktree_path)`
- Store PID in `_status.yaml`, set status to Running, `started_at`
- Note: `exec` chain in ait→codeagent.sh preserves PID for tracking

### 1g: Graceful shutdown
- Signal handlers: `signal.signal(SIGTERM, handler)`, `signal.signal(SIGINT, handler)`
- Also triggered by `requested_action: stop` in `_runner_alive.yaml`
- Send kill commands via subprocess: `./ait crew command send-all --crew <id> --command kill`
- Update `_runner_alive.yaml` status to `stopped`
- Update `_crew_status.yaml` status to `Killing`

### 1h: Progress and ETA
- Progress: `completed_count / total_count * 100`
- ETA: average completion time of finished agents * remaining count

**`_runner_alive.yaml` schema (new file):**
```yaml
status: running|stopped
pid: <int>
hostname: <str>
started_at: <timestamp>
last_heartbeat: <timestamp>
next_check_at: <timestamp>
interval: <seconds>
requested_action: null|stop
```

## Step 1.5: Create runner configuration files

**Project-wide defaults:** `aitasks/metadata/crew_runner_config.yaml`
```yaml
# Default configuration for the AgentCrew runner.
# CLI arguments override these values.
# If this file is absent, hardcoded defaults are used (interval: 30, max_concurrent: 3).

interval: 30          # Seconds between runner iterations
max_concurrent: 3     # Maximum agents running simultaneously (across all types)
```

**Seed template:** `seed/crew_runner_config.yaml` — identical content, copied by `ait setup`

## Step 2: Create bash wrapper

`.aitask-scripts/aitask_crew_runner.sh` — thin wrapper with venv detection, following `aitask_crew_status.sh` pattern.

## Step 3: Update `ait` dispatcher

Add `runner` subcommand to agentcrew case. Update available subcommands help text.

## Step 4: Write tests

`tests/test_crew_runner.sh`:
- Init agentcrew, add 3 agents (A depends on nothing, B depends on A, C depends on A+B)
- `--once --dry-run` shows A as ready first
- After manually marking A complete, B becomes ready
- Per-type limit enforcement (set max_parallel=1, verify only 1 launched)
- Single-instance detection (write runner_alive, verify refusal)
- `--check` diagnostic output
- Config resolution (config file vs CLI args vs defaults)
- `python -m py_compile` to verify syntax

## Step 5: Post-Implementation (Step 9)

Archive task, update parent, push.

## Additional: Create Child Task t386_9

Create `t386_9_crew_runner_config_tui.md` for adding `crew_runner_config.yaml` editing support to `ait settings` TUI.

## Final Implementation Notes
- **Actual work done:** Created `agentcrew_runner.py` (~430 LOC) with full orchestration loop: argument parsing, config resolution (CLI > YAML config > defaults), single-instance enforcement with `--force` flag (local only), diagnostic `--check` mode, main loop with heartbeat/pull/stale-check/command-processing/ready-agent-detection/type-limits/agent-launching/crew-status-recomputation/commit-push, graceful shutdown (SIGTERM/SIGINT + `requested_action: stop`), progress tracking with ETA. Created `aitask_crew_runner.sh` bash wrapper (venv detection pattern from `aitask_crew_status.sh`). Added `runner` subcommand to `ait` dispatcher. Created `crew_runner_config.yaml` in both `aitasks/metadata/` and `seed/`. Wrote comprehensive test suite (10 tests, 20 assertions). Created child task t386_9 for TUI config editing. Updated t386_6 to note config file documentation need.
- **Deviations from plan:** Added `--force` flag for local-only runner restart (user request — original plan only had refuse-to-start). Added `crew_runner_config.yaml` configuration file with resolution hierarchy (user request — original plan had hardcoded defaults only). Created child task t386_9 for future TUI config editing (user request). Runner auto-stops when all agents reach terminal state (not in original plan but logical behavior). Sleep loop uses 1-second increments for responsive signal handling instead of a single `time.sleep(interval)`.
- **Issues encountered:** (1) Test 6 (single-instance detection) initially used `os.getpid()` from a Python one-liner to write the alive file, but that process exited before the runner checked. Fixed by using `$$` (parent shell PID). (2) `local` keyword used in a subshell context outside a function — removed `local` qualifier.
- **Key decisions:** Config resolution uses 3-tier priority (CLI > file > hardcoded) to allow project-wide defaults without requiring CLI args. Agent launching uses `subprocess.Popen` with `cwd=worktree_path` so `./ait` resolves relative to the worktree. Runner processes pause/resume commands directly (kill commands are only sent during graceful shutdown via `ait crew command send-all`). Progress ETA extrapolates from average completed agent time.
- **Notes for sibling tasks:** The runner is invoked via `ait crew runner --crew <id>`. Config file is at `aitasks/metadata/crew_runner_config.yaml`. The `_runner_alive.yaml` schema is: `{status, pid, hostname, started_at, last_heartbeat, next_check_at, interval, requested_action}`. To stop a runner: set `requested_action: stop` in `_runner_alive.yaml` and commit+push, or send SIGTERM to its PID. The `--check` flag provides diagnostics without starting. The runner auto-transitions agents through `Waiting→Ready→Running` when launching. t386_6 should document the config file schema and resolution order. t386_9 is a new task for TUI editing of the config file.
