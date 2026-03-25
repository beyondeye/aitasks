---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [brainstorming]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-25 11:42
updated_at: 2026-03-25 13:28
---

## Brainstorm App Processes Section in Status Tab

Add a "Running Processes" section to the existing Status tab (tab 5) in the brainstorm TUI, between the runner status section and the operation groups section.

### Context

The brainstorm app (`brainstorm_app.py`) uses 5 tabs via TabbedContent: Dashboard (1), DAG (2), Compare (3), Actions (4), Status (5). The Status tab already shows:
1. Runner status (active/stopped/stale) with start/stop buttons
2. Operation groups with nested agent status rows
3. Log files

This task adds a "Running Processes" section between the runner status and operation groups that shows OS-level process information (CPU time, memory, wall time) and provides control actions (pause, resume, kill, hard kill).

The process stats come from `agentcrew_process_stats.py` (t462_1) and the hard kill function from `agentcrew_runner_control.py` (t462_2).

### Key Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_app.py` — Add ProcessRow widget, modify `_refresh_status_tab()`, add keybindings

### Reference Files for Patterns

- `.aitask-scripts/brainstorm/brainstorm_app.py` — `AgentStatusRow` widget for row layout pattern; `_refresh_status_tab()` for refresh pattern; `_mount_agent_row()` for mounting agent widgets
- `.aitask-scripts/agentcrew/agentcrew_process_stats.py` — `get_all_agent_processes()`, `get_runner_process_info()`, `sync_stale_processes()` (created in t462_1)
- `.aitask-scripts/agentcrew/agentcrew_runner_control.py` — `send_agent_command()`, `hard_kill_agent()` (hard_kill from t462_2)

### Implementation Plan

1. **Add imports at top of `brainstorm_app.py`:**
   ```python
   from agentcrew.agentcrew_process_stats import (
       get_all_agent_processes, get_runner_process_info, sync_stale_processes
   )
   from agentcrew.agentcrew_runner_control import hard_kill_agent
   ```

2. **Create `ProcessRow(Static, can_focus=True)` widget:**
   - Similar to `AgentStatusRow` but shows OS-level stats
   - Constructor takes: agent_name, pid, status, wall_time, cpu_time, memory_rss_mb, heartbeat_age, last_message, process_alive, crew_id
   - `render()` displays:
     ```
     [status_dot] agent_name  PID: 12345  Wall: 2h 15m  CPU: 45.2s  RSS: 128MB  HB: 30s  [p]ause [k]ill [K] hard kill
     ```
   - Color coding: green=alive, red=dead but status Running, yellow=Paused
   - Store agent_name and crew_id as attributes

3. **Modify `_refresh_status_tab()` to include process section:**
   - After the runner status section (around where `#status-runner` is mounted)
   - Before the operation groups section
   - Add a section header: "Running Processes"
   - Call `sync_stale_processes(crew_id)` on first load (use a flag to avoid repeated syncs)
   - Call `get_all_agent_processes(crew_id)` for process data
   - Mount `ProcessRow` widgets for each process
   - If no processes: show "No running processes" label
   - Container ID: `#status-processes` for targeted updates

4. **Augment runner status display:**
   - Use `get_runner_process_info(crew_id)` to get runner PID, CPU, memory
   - Add PID and resource stats to existing runner status line
   - Example: "Runner active (PID: 12345, CPU: 12.3s, RSS: 64MB) — hostname, 5s ago"

5. **Add key handlers for process actions:**
   - In the existing `on_key()` method, add handlers when Status tab is active and a `ProcessRow` is focused:
     - `p` → pause/resume: Call `send_agent_command(crew_id, agent_name, "pause"/"resume")` based on current status
     - `k` → graceful kill: Call `send_agent_command(crew_id, agent_name, "kill")`
     - `K` (shift-k) → hard kill: Call `hard_kill_agent(crew_id, agent_name)`, show result via `self.notify()`
   - Check if `self.focused` is a `ProcessRow` before handling these keys

6. **CSS additions (in App.CSS):**
   ```css
   ProcessRow { height: auto; padding: 0 2; }
   ProcessRow:focus { background: $accent; }
   ProcessRow.-dead { opacity: 0.6; }
   #status-processes { height: auto; margin: 1 0; }
   .process-header { text-style: bold; padding: 0 2; }
   ```

7. **Refresh behavior:**
   - Process data refreshes with the existing 30-second `_refresh_status_tab()` timer
   - The section is only rendered when Status tab is active (existing optimization)
   - After hard kill action: trigger immediate `_refresh_status_tab()` via `set_timer(2.0, ...)`

### Verification Steps

- Launch brainstorm TUI, switch to Status tab (press 5)
- Verify "Running Processes" section appears between runner status and groups
- Verify ProcessRow widgets show PID, wall time, CPU time, memory
- Verify runner status line shows augmented PID/resource info
- Test `p` (pause), `k` (kill), `K` (hard kill) on focused ProcessRow
- Verify 30-second auto-refresh updates process stats
- Test with no running agents — "No running processes" message
- Test after hard kill — verify immediate refresh shows updated status
