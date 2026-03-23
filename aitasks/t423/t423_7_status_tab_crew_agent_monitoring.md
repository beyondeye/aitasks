---
priority: medium
effort: medium
depends: [t423_6]
issue_type: feature
status: Implementing
labels: [brainstorming, tui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-20 12:41
updated_at: 2026-03-23 13:10
---

## Context
Implement the Status tab (Tab 5) for real-time crew/agent monitoring. Shows operation groups, individual agent statuses, and output previews with auto-refresh.

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — Replace Status tab placeholder with monitoring implementation

## Reference Files for Patterns
- `.aitask-scripts/agentcrew/agentcrew_utils.py` — `read_yaml()` for reading br_groups.yaml and agent status files
- `.aitask-scripts/brainstorm/brainstorm_session.py` — `crew_worktree()` for crew path

## Implementation
1. Read br_groups.yaml from crew worktree to get operation groups
2. Build a DataTable or VerticalScroll with expandable rows:
   - Group row: group ID, operation type, status (Running/Completed/Failed), agent count
   - Agent rows (expanded): agent ID, type, status, created_at, output file path
3. Expandable: focus on group row, press Enter to expand/collapse agent list
4. Agent output preview: show last 10 lines of _output.md when expanded
5. Auto-refresh via @work(thread=True) polling crew worktree every 30s
6. Color-coded status: green=Completed, yellow=Running/Waiting, red=Error/Aborted

## Manual Verification
1. After running brainstorm ops → Status tab shows groups
2. Groups show type, status, agent count
3. Expand group → shows agents with status/timestamps
4. Colors match status (green/yellow/red)
5. Auto-refresh updates after ~30s
