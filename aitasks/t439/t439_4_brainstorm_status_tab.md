---
priority: medium
effort: medium
depends: [t439_3]
issue_type: feature
status: Implementing
labels: [brainstorming, agentcrew]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-23 12:55
updated_at: 2026-03-23 18:55
---

## Add log browsing to Brainstorm TUI Status tab

### Context
The brainstorm TUI's Status tab (tab 5) was implemented by t423_7 with operation group display, agent status monitoring (color-coded), expand/collapse groups, output previews, and auto-refresh (30s). This task adds **log browsing** on top of that existing infrastructure, reusing shared log utilities from t439_2.

**Important — t423_7 already implemented:**
- `GroupRow` widget for expandable operation groups
- `AGENT_STATUS_COLORS` constant for color-coded statuses
- `_refresh_status_tab()` method that populates `#status_content` with groups and agent rows
- `_mount_group_agents()` / `_mount_agent_row()` for agent detail display with heartbeat and output preview
- Auto-refresh timer (30s) and refresh on tab activation via `on_tabbed_content_tab_activated()`
- `self._expanded_groups` set for expand/collapse state

**This task only adds:** LogDetailModal, StatusLogRow, log file listing, and extends `_refresh_status_tab()` to append log entries.

### Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — Add LogDetailModal, StatusLogRow, extend `_refresh_status_tab()` with log section

### Reference Files for Patterns
- `.aitask-scripts/agentcrew/agentcrew_dashboard.py` lines 266-327 — `AgentCard` widget pattern
- `.aitask-scripts/agentcrew/agentcrew_log_utils.py` — Shared log utilities (from t439_2)
- `.aitask-scripts/brainstorm/brainstorm_app.py` — `NodeDetailModal` pattern, existing `GroupRow` and `_refresh_status_tab()` from t423_7
- `aiplans/archived/p423/p423_7_status_tab_crew_agent_monitoring.md` — Implementation notes from t423_7

### Implementation Plan

#### 1. Import log utilities
```python
from agentcrew.agentcrew_log_utils import list_agent_logs, read_log_tail, read_log_full, format_log_size
```
Note: `list_agent_files`, `format_elapsed`, `read_yaml` are already imported (added by t423_7).

#### 2. Create `LogDetailModal` (modal screen)
Similar to `NodeDetailModal` but shows log content:
- Tabbed content with "Tail" and "Full" tabs
- Keybinding `r` to refresh, `t` for tail, `f` for full
- `escape` to dismiss
- Shows agent name + file size in header

#### 3. Create `StatusLogRow` (focusable widget)
Focusable row for log file entries. Posts a `Selected` message with log path and agent name on Enter.

#### 4. Extend `_refresh_status_tab()` — add log section
After the existing groups/agents section (DO NOT replace it), append:
- A "Agent Logs" section header
- List of `*_log.txt` files sorted by last modified (most recent first)
- Each entry as a `StatusLogRow` showing: agent name, file size, last modified time

#### 5. Wire up log opening
- Add Enter handler for `StatusLogRow` in `on_key()`: push `LogDetailModal`
- Add CSS for `StatusLogRow` and `LogDetailModal`

### Verification Steps
1. Initialize a brainstorm session: `ait brainstorm init <task_num>`
2. Launch an explore operation from the Actions tab
3. Switch to the Status tab (press `5`)
4. Verify existing agent statuses still display correctly (from t423_7)
5. Verify agent logs are listed below the agent section, sorted by last modified
6. Press Enter on a log entry to view content in a modal
7. Press `t`/`f`/`r` in modal for tail/full/refresh
8. Verify auto-refresh updates both agent statuses and log list
