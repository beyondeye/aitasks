---
priority: medium
effort: medium
depends: [t439_2]
issue_type: feature
status: Done
labels: [agentcrew]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-23 12:54
updated_at: 2026-03-23 18:45
completed_at: 2026-03-23 18:45
---

## Add log browsing to AgentCrew Dashboard TUI

### Context
The AgentCrew dashboard TUI (`agentcrew_dashboard.py`) shows crew and agent status but has no way to view agent execution logs. This task adds a log browser screen accessible from the crew detail view. Depends on t439_2 (shared log utils) for the log reading functions.

### Key Files to Modify
- `.aitask-scripts/agentcrew/agentcrew_dashboard.py` — Add LogBrowserScreen, LogViewScreen, keybinding

### Reference Files for Patterns
- `.aitask-scripts/agentcrew/agentcrew_dashboard.py` lines 393-617 — `CrewDetailScreen` pattern (Screen subclass with bindings, refresh, agent cards)
- `.aitask-scripts/agentcrew/agentcrew_log_utils.py` — The shared log utilities (from t439_2)
- `.aitask-scripts/brainstorm/brainstorm_app.py` lines 106-268 — Modal screen patterns (NodeDetailModal)

### Implementation Plan

#### 1. Import log utilities
Add import at top of file:
```python
from agentcrew.agentcrew_log_utils import list_agent_logs, read_log_tail, read_log_full, format_log_size
```

#### 2. Add `LogEntry` widget (similar pattern to `AgentCard`)
A focusable row showing: agent name, log size, last modified time. Posts a `Selected` message on focus with the log path.

#### 3. Create `LogBrowserScreen` (similar to `CrewDetailScreen`)
- Screen with header showing crew name + "Agent Logs"
- `VerticalScroll` containing `LogEntry` widgets sorted by mtime (most recent first)
- Keybinding `enter` → push `LogViewScreen` for selected log
- Keybinding `escape` → go back
- Auto-refresh every 5 seconds (reuse pattern from `CrewDetailScreen._refresh_data`)

#### 4. Create `LogViewScreen`
- Screen showing log content in a scrollable `Label` or `TextArea` (read-only)
- Keybindings:
  - `r` → refresh/reload content
  - `t` → show tail only (last 50 lines)
  - `f` → show full content
  - `escape` → go back
- Initially shows tail view
- Header shows agent name + file size + last modified

#### 5. Add keybinding to `CrewDetailScreen`
Add `Binding("l", "view_logs", "Logs")` to the BINDINGS list.

`action_view_logs()`:
```python
def action_view_logs(self) -> None:
    self.app.push_screen(LogBrowserScreen(self.crew_id, self.manager))
```

### Verification Steps
1. Start a crew with agents, let them produce log files
2. Open `ait crew dashboard`, navigate to a crew detail view
3. Press `l` to open log browser
4. Verify logs are listed sorted by last modified
5. Press Enter on a log to view content
6. Press `r` to refresh, `t` for tail, `f` for full
7. Press escape to navigate back through screens
