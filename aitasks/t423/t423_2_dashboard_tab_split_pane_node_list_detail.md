---
priority: medium
effort: medium
depends: [t423_1]
issue_type: feature
status: Implementing
labels: [brainstorming, tui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-20 12:40
updated_at: 2026-03-22 11:17
---

## Context
Implement the Dashboard tab (Tab 1) as a split-pane layout. Left pane shows a scrollable node list with HEAD indicator. Right pane shows session status and context-sensitive detail for the focused node.

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — Replace Dashboard tab placeholder with split-pane implementation

## Reference Files for Patterns
- `.aitask-scripts/brainstorm/brainstorm_dag.py` — `list_nodes()`, `get_head()`, `read_node()`
- `.aitask-scripts/brainstorm/brainstorm_session.py` — `load_session()` for session status data
- `.aitask-scripts/board/aitask_board.py` — Focusable Static subclass pattern (TaskCard)

## Implementation
1. Create `DashboardTab` widget using Horizontal container (left 40%, right 60%)
2. Left pane: VerticalScroll with focusable Static rows for each node (from list_nodes + get_head)
3. Right pane: session status panel (status, task, node count, timestamps) + focused node detail
4. On node focus change → update right pane with node metadata, description, parent info
5. Enter on node → push NodeDetailModal with node_id
6. Style HEAD node distinctly (color/bold)

## Manual Verification
1. Launch with 3+ nodes → left pane shows all nodes with HEAD marker
2. Arrow keys navigate node list → right pane updates
3. Right pane shows session status
4. Enter on node → NodeDetailModal opens
