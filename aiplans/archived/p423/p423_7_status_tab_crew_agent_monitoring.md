---
Task: t423_7_status_tab_crew_agent_monitoring.md
Parent Task: aitasks/t423_design_and_finalize_brainstorm_tui.md
Worktree: (none - working on current branch)
Branch: (current)
Base branch: main
---

## Context

Implement the Status tab (Tab 5) for real-time crew/agent monitoring. Shows operation groups, individual agent statuses, and output previews with auto-refresh.

## Implementation

1. Read br_groups.yaml from crew worktree to get operation groups
2. Build a DataTable or VerticalScroll with expandable rows:
   - Group row: group ID, operation type, status (Running/Completed/Failed), agent count
   - Agent rows (expanded): agent ID, type, status, created_at, output file path
3. Expandable: focus on group row, press Enter to expand/collapse agent list
4. Agent output preview: show last 10 lines of _output.md when expanded
5. Auto-refresh via @work(thread=True) polling crew worktree every 30s
6. Color-coded status: green=Completed, yellow=Running/Waiting, red=Error/Aborted

### Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` -- Replace Status tab placeholder with monitoring implementation

### Reference Files for Patterns
- `.aitask-scripts/agentcrew/agentcrew_utils.py` -- `read_yaml()` for reading br_groups.yaml and agent status files
- `.aitask-scripts/brainstorm/brainstorm_session.py` -- `crew_worktree()` for crew path

### Manual Verification
1. After running brainstorm ops -- Status tab shows groups
2. Groups show type, status, agent count
3. Expand group -- shows agents with status/timestamps
4. Colors match status (green/yellow/red)
5. Auto-refresh updates after ~30s

## Final Implementation Notes

- **Actual work done:** Replaced Status tab placeholder in `brainstorm_app.py` with full operation group monitoring. Added `AGENT_STATUS_COLORS` constant (7 agent statuses), `GroupRow` widget (focusable, expandable/collapsible), and 3 new methods: `_refresh_status_tab()`, `_mount_group_agents()`, `_mount_agent_row()`. Added `on_tabbed_content_tab_activated()` for refresh on tab switch. Added auto-refresh timer (30s). Added CSS for GroupRow, agent detail rows, and output preview. Total: +239/-10 lines in a single file.
- **Deviations from plan:** Used `set_interval(30, ...)` instead of `@work(thread=True)` for auto-refresh — simpler and avoids thread management. Used `Label` widgets with rich markup for agent rows instead of a separate `StatusAgentRow` widget — keeps it simpler since the rows don't need focus or interaction. Used `VerticalScroll.remove_children()` (sync) rather than async `await container.remove_children()` since `_refresh_status_tab` is called from both sync (`on_key` Enter handler) and timer contexts.
- **Issues encountered:** None.
- **Key decisions:** Kept log browsing entirely out of scope per t439_4 split. Used dict-based group access pattern from `_mount_recent_ops()` since `br_groups.yaml` uses dict structure (not list). Used `datetime.fromisoformat()` for heartbeat parsing instead of importing `_parse_timestamp` from agentcrew_utils to avoid private function dependency. Output preview reads last 10 lines directly instead of importing `_read_file_preview` from agentcrew_dashboard (avoids cross-module dependency for a simple operation).
- **Notes for sibling tasks:** `GroupRow` widget is reusable for any expandable group display. `AGENT_STATUS_COLORS` dict maps all 7 agent statuses to colors. `_refresh_status_tab()` clears and rebuilds `#status_content` entirely on each call — t439_4 should extend this method to append log file listing after the agent sections. `self._expanded_groups` (set of group names) tracks expand/collapse state across refreshes. `self._status_refresh_timer` is started in `_load_existing_session()` with 30s interval. The `on_tabbed_content_tab_activated` handler triggers immediate refresh when switching to Status tab. CSS class `.status_empty` replaces the old `#status_placeholder` ID-based style.
