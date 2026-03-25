---
priority: medium
effort: medium
depends: [t462_2]
issue_type: feature
status: Implementing
labels: [agentcrew]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-25 11:42
updated_at: 2026-03-25 12:54
---

## AgentCrew Dashboard Processes Screen

Add a new `ProcessListScreen` (stacked screen) to the AgentCrew Dashboard TUI showing running agent processes with OS-level stats and control actions.

### Context

The agentcrew dashboard (`agentcrew_dashboard.py`) uses stacked screens: Main -> CrewDetailScreen -> LogBrowserScreen -> LogViewScreen. The CrewDetailScreen already shows AgentCards with workflow status, progress, and heartbeat info. This task adds a new ProcessListScreen focused on the OS-level process view with CPU time, memory, wall time, and direct process control actions including hard kill.

The process stats come from `agentcrew_process_stats.py` (t462_1) and the hard kill function from `agentcrew_runner_control.py` (t462_2).

### Key Files to Modify

- `.aitask-scripts/agentcrew/agentcrew_dashboard.py` — Add ProcessListScreen, ProcessCard widget, keybinding in CrewDetailScreen

### Reference Files for Patterns

- `.aitask-scripts/agentcrew/agentcrew_dashboard.py` — LogBrowserScreen (lines ~550-700) for stacked screen pattern; AgentCard for widget layout; CrewDetailScreen for keybinding pattern
- `.aitask-scripts/agentcrew/agentcrew_process_stats.py` — `get_all_agent_processes()`, `get_runner_process_info()`, `sync_stale_processes()` (created in t462_1)
- `.aitask-scripts/agentcrew/agentcrew_runner_control.py` — `send_agent_command()`, `hard_kill_agent()` (hard_kill from t462_2)

### Implementation Plan

1. **Add imports at top of `agentcrew_dashboard.py`:**
   ```python
   from agentcrew.agentcrew_process_stats import (
       get_all_agent_processes, get_runner_process_info, sync_stale_processes
   )
   from agentcrew.agentcrew_runner_control import hard_kill_agent
   ```

2. **Create `ProcessCard(Static, can_focus=True)` widget:**
   - Constructor takes: agent_name, pid, status, wall_time, cpu_time, memory_rss_mb, heartbeat_age, last_message, process_alive, agent_type
   - `render()` displays a compact card:
     ```
     [status_dot] agent_name (type)  PID: 12345  Wall: 2h 15m  CPU: 45.2s  RSS: 128MB  HB: 30s ago
     Last: Processing file 3 of 10
     ```
   - Color-coded status dot: green=Running+alive, yellow=Paused, red=Running+dead, grey=other
   - Add `on_focus`/`on_blur` for highlight effect
   - Store agent_name and crew_id as attributes for action dispatch

3. **Create `ProcessListScreen(Screen):`**
   - `BINDINGS`:
     - `Binding("p", "pause_resume", "Pause/Resume")`
     - `Binding("k", "kill_agent", "Kill")`
     - `Binding("K", "hard_kill", "Hard Kill")`
     - `Binding("f5", "refresh", "Refresh")`
     - `Binding("escape", "go_back", "Back")`
   - `compose()`:
     - Header with title "Running Processes - <crew_name>"
     - Static widget for runner process info (PID, CPU, memory, hostname)
     - VerticalScroll containing ProcessCard widgets
     - Footer with keybinding hints
   - `on_mount()`:
     - Call `sync_stale_processes(crew_id)` once on load to auto-correct stale agents
     - Initial data load
     - `set_interval(5.0, self._refresh_data)` for auto-refresh
   - `_refresh_data()`:
     - Call `get_all_agent_processes(crew_id)`
     - Call `get_runner_process_info(crew_id)`
     - Rebuild ProcessCard widgets (remove old, mount new)
   - Action handlers:
     - `action_pause_resume()`: Get focused ProcessCard, call `send_agent_command(crew_id, agent_name, "pause"/"resume")` based on current status
     - `action_kill_agent()`: Call `send_agent_command(crew_id, agent_name, "kill")`
     - `action_hard_kill()`: Call `hard_kill_agent(crew_id, agent_name)`, show result via `self.notify()`
     - `action_go_back()`: `self.app.pop_screen()`

4. **Add keybinding to `CrewDetailScreen`:**
   - Add `Binding("o", "view_processes", "Processes")` to BINDINGS
   - Add `action_view_processes()` method that does `self.app.push_screen(ProcessListScreen(self.crew_id))`

5. **CSS additions (in App.CSS):**
   ```css
   ProcessCard { height: auto; padding: 0 2; margin: 0 0 1 0; }
   ProcessCard:focus { background: $accent; }
   ProcessCard.-dead { opacity: 0.6; }
   #runner-info { height: 3; padding: 1 2; background: $surface; }
   ```

6. **Helper function for time formatting:**
   - `format_wall_time(seconds: float) -> str` — "2h 15m", "45m 30s", "12s"
   - `format_cpu_time(seconds: float) -> str` — "45.2s", "1m 23s"
   - `format_memory(mb: float) -> str` — "128MB", "1.2GB"
   - May already exist in agentcrew_utils.py as `format_elapsed()` — reuse if so

### Verification Steps

- Launch `ait crew dashboard`, select a crew with running agents
- Press `o` to open ProcessListScreen
- Verify process cards show PID, wall time, CPU time, memory
- Verify auto-refresh updates stats every 5 seconds
- Test `p` (pause), `k` (kill), `K` (hard kill) on a running agent
- Test with no running agents — should show "No running processes" message
- Press `escape` to go back to CrewDetailScreen
