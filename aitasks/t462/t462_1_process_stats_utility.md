---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [agentcrew, brainstorming]
created_at: 2026-03-25 10:37
updated_at: 2026-03-25 10:37
---

## Process Stats Utility Module

Create a shared Python module for gathering OS-level process statistics from agent PIDs tracked in status files.

### Context

The agentcrew runner spawns agent processes and stores their PIDs in `<agent>_status.yaml` files. The brainstorm and agentcrew TUIs need to display OS-level process information (CPU time, memory, running time) and detect stale processes whose PIDs are no longer alive. This utility provides the shared backend for both TUIs.

### Key Files to Create

- `.aitask-scripts/agentcrew/agentcrew_process_stats.py` — NEW module

### Reference Files for Patterns

- `.aitask-scripts/agentcrew/agentcrew_runner_control.py` — Same module pattern (pure functions, imports from agentcrew_utils)
- `.aitask-scripts/agentcrew/agentcrew_utils.py` — Provides `read_yaml()`, `crew_worktree_path()`, `list_agent_files()`
- `.aitask-scripts/agentcrew/agentcrew_runner.py` — PID tracking logic, `check_pid_alive` pattern (lines 158-224)

### Implementation Plan

#### Functions to implement:

1. **`get_process_info(pid: int) -> dict | None`**
   - Read `/proc/<pid>/stat` for: utime + stime (CPU time in clock ticks, convert to seconds), starttime (process start time), rss (resident set size in pages, convert to MB)
   - Read `/proc/<pid>/status` for VmRSS if needed as fallback
   - Use `os.sysconf('SC_CLK_TCK')` for clock tick conversion
   - Use `os.sysconf('SC_PAGE_SIZE')` for page size conversion
   - Calculate wall_time from starttime vs system boot time (`/proc/stat` btime)
   - Return dict: `{alive: True, cpu_time_seconds: float, memory_rss_mb: float, wall_time_seconds: float, create_time: str}`
   - Return None if `/proc/<pid>` doesn't exist (process dead)
   - Handle PermissionError gracefully (return partial info)

2. **`get_all_agent_processes(crew_id: str) -> list[dict]`**
   - Use `crew_worktree_path(crew_id)` to find crew directory
   - Use `list_agent_files(crew_id)` or glob for `*_status.yaml` files
   - For each agent with status in (Running, Paused) and a `pid` field:
     - Call `get_process_info(pid)`
     - Read `<agent>_alive.yaml` for heartbeat info
     - Combine into dict: `{agent_name, agent_type, group, status, pid, started_at, process_alive, cpu_time, memory_rss_mb, wall_time, heartbeat_age, last_message}`
   - Also include agents with status Running but dead PID (mark `process_alive: False`)

3. **`get_runner_process_info(crew_id: str) -> dict | None`**
   - Read `_runner_alive.yaml` for runner PID, hostname, last_heartbeat
   - If hostname matches local host: call `get_process_info(pid)`
   - If remote: return dict with `remote: True`, no OS stats
   - Return None if no runner info file

4. **`sync_stale_processes(crew_id: str) -> list[str]`**
   - Check if runner is alive (PID check + hostname check)
   - If runner is dead:
     - For each agent with status `Running` but dead PID:
       - Update `<agent>_status.yaml`: status -> Error, error_message -> "Process exited unexpectedly", completed_at -> now
     - Return list of agent names that were corrected
   - If runner is alive: skip (let runner handle its own cleanup via heartbeat timeout)
   - If runner is remote: skip (can't verify remote PIDs)

#### Edge cases:
- PID reuse: unlikely for short-lived processes, but `/proc/<pid>/cmdline` can be checked against expected command pattern
- Permission errors on `/proc/<pid>`: return partial info with `cpu_time: None`
- Remote runner: skip OS stats, indicate "remote" in return data
- No crew worktree: return empty list

### Verification Steps

- Import the module and call `get_process_info(os.getpid())` — should return valid stats for current process
- Create a test crew with a known running process, verify `get_all_agent_processes()` returns correct data
- Kill a process manually, verify `sync_stale_processes()` updates the status file
