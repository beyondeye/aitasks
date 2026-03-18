---
priority: high
effort: high
depends: [t419_1]
issue_type: refactor
status: Implementing
labels: [agentcrew]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-18 14:58
updated_at: 2026-03-18 22:06
---

## Context
AgentCrew currently has no concept of operation groups. For the brainstorm engine (t419), we need a persistent crew per session where multiple operations (explore, compare, hybridize) add agents over time. Groups allow scheduling priority (earlier operations first), group-level commands, and group-level status queries.

## Key Files to Modify
- .aitask-scripts/agentcrew/agentcrew_utils.py — add group-aware helpers (get_group_agents, get_group_status, group_sort_key)
- .aitask-scripts/agentcrew/agentcrew_runner.py — modify find_ready_agents() to sort by group priority before applying concurrency limits
- .aitask-scripts/agentcrew/agentcrew_status.py — add --group filter flag
- .aitask-scripts/agentcrew/agentcrew_report.py — add --group filter flag
- .aitask-scripts/agentcrew/agentcrew_dashboard.py — display group column/info in agent list
- .aitask-scripts/aitask_crew_addwork.sh — accept --group flag, write group to agent status YAML, update _groups.yaml
- .aitask-scripts/aitask_crew_command.sh — add send-group subcommand
- aidocs/agentcrew/agentcrew_architecture.md — document group feature

## Reference Files for Patterns
- .aitask-scripts/agentcrew/agentcrew_utils.py — existing DAG ops, status constants, YAML I/O patterns
- .aitask-scripts/agentcrew/agentcrew_runner.py — current find_ready_agents() and concurrency limit logic
- .aitask-scripts/aitask_crew_command.sh — current send/send-all subcommands (pattern for send-group)
- .aitask-scripts/aitask_crew_addwork.sh — current agent registration flow

## Implementation Plan

### Schema Changes
1. Add optional group field to agent_status.yaml schema (string, e.g. explore_001)
2. Create _groups.yaml schema: list of groups with name, sequence (auto-increment), description, created_at

### ait crew addwork --group
3. Add --group flag to aitask_crew_addwork.sh argument parsing
4. Write group field to agent_status.yaml when provided
5. Auto-create/update _groups.yaml: if group name is new, append with next sequence number

### Runner Group Priority
6. In agentcrew_runner.py find_ready_agents(): after finding Ready agents, sort by group sequence (read from _groups.yaml) before applying per-type and overall concurrency limits
7. Agents without a group get lowest priority (sorted last)

### Group Commands
8. Add send-group subcommand to aitask_crew_command.sh: sends command to all agents matching --group filter
9. Pattern: iterate agent statuses, filter by group field, send command to each

### Group Queries
10. Add --group flag to agentcrew_status.py: filter output to agents in specified group
11. Add --group flag to agentcrew_report.py: filter report to group
12. Add group_status() helper to agentcrew_utils.py: returns Completed/Running/Error for a group based on its agents

### Dashboard
13. Add group column to agent list in agentcrew_dashboard.py
14. Optionally add group filter keybinding

### Documentation
15. Update aidocs/agentcrew/agentcrew_architecture.md with group section

## Verification
- Create a test crew with agents in different groups
- Verify --group flag works on addwork, status, report, command
- Verify runner prioritizes lower-sequence groups
- Verify send-group sends commands to all agents in the group
- Verify dashboard shows group information
