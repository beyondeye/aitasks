---
priority: medium
effort: medium
depends: [t439_3]
issue_type: feature
status: Ready
labels: [brainstorming, agentcrew]
created_at: 2026-03-23 12:55
updated_at: 2026-03-23 12:55
---

## Populate Brainstorm TUI Status tab with agent status + log browsing

### Context
The brainstorm TUI's Status tab (tab 5) is currently a placeholder: "Status — coming in follow-up tasks" (brainstorm_app.py:630). This task populates it with agent status monitoring and log browsing, reusing the shared log utilities from t439_2. Depends on t439_2 (shared log utils) and t439_3 (dashboard log browser — for reusable patterns).

### Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — Replace Status tab placeholder, add log detail modal

### Reference Files for Patterns
- `.aitask-scripts/agentcrew/agentcrew_dashboard.py` lines 266-327 — `AgentCard` widget (agent status display)
- `.aitask-scripts/agentcrew/agentcrew_dashboard.py` lines 94-184 — `CrewManager.load_crew()` (loading agent data)
- `.aitask-scripts/agentcrew/agentcrew_log_utils.py` — Shared log utilities (from t439_2)
- `.aitask-scripts/brainstorm/brainstorm_app.py` lines 106-160 — `NodeDetailModal` pattern (modal screen)
- `.aitask-scripts/brainstorm/brainstorm_session.py` — `crew_worktree()` function to get the crew worktree path

### Implementation Plan

#### 1. Import dependencies
```python
from agentcrew.agentcrew_log_utils import list_agent_logs, read_log_tail, read_log_full, format_log_size
from agentcrew.agentcrew_utils import (
    list_agent_files, read_yaml, check_agent_alive, format_elapsed, _parse_timestamp
)
```

#### 2. Create `LogDetailModal` (modal screen)
Similar to `NodeDetailModal` but shows log content:
- Tabbed content with "Tail" and "Full" tabs
- Keybinding `r` to refresh
- `escape` to dismiss
- Shows agent name + file size in header

#### 3. Replace Status tab placeholder (lines 627-634)
Replace the placeholder Label with a structured layout:

**Top section — Agent Status Summary:**
- Runner status (active/stale/none) with heartbeat age
- List of agents with: name, status (color-coded), heartbeat age, last message
- Use data from `<agent>_status.yaml` and `<agent>_alive.yaml` files in the crew worktree

**Bottom section — Agent Logs:**
- List of `*_log.txt` files sorted by last modified (most recent first)
- Each entry shows: agent name, file size, last modified time
- Focusable rows; Enter → push `LogDetailModal`

#### 4. Add refresh logic
- Auto-refresh the Status tab content every 5 seconds using `set_interval()`
- Only refresh when the Status tab is active (check `tabbed.active == "tab_status"`)

#### 5. Wire up `crew_worktree()` for the session
The brainstorm TUI already has `self.session_path`. Use `crew_worktree(self.task_num)` from `brainstorm_session` to get the crew worktree path for reading agent files and logs.

### Verification Steps
1. Initialize a brainstorm session: `ait brainstorm init <task_num>`
2. Launch an explore operation from the Actions tab
3. Switch to the Status tab (press `5`)
4. Verify agent statuses are shown with color-coded status and heartbeat info
5. Verify agent logs are listed below, sorted by last modified
6. Press Enter on a log entry to view content in a modal
7. Verify auto-refresh updates the status display
8. Verify the same log utilities are used as in the agentcrew dashboard (shared code)
