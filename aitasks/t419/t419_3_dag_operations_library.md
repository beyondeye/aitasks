---
priority: high
effort: medium
depends: [t419_2, 1]
issue_type: feature
status: Implementing
labels: [brainstorming]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-18 14:58
updated_at: 2026-03-19 08:45
---

## Context
The brainstorm engine (t419) needs a Python library for managing the design space DAG — creating nodes, tracking the graph state, and managing sessions. This is the data layer that the CLI scripts (t419_4) and TUI (t419_6) will use.

## Key Files to Read
- aidocs/brainstorming/brainstorm_engine_architecture.md — data format specs (created by t419_1)
- .aitask-scripts/agentcrew/agentcrew_utils.py — reference for YAML I/O patterns, DAG operations (topo_sort, cycle detection)
- .aitask-scripts/board/task_yaml.py — YAML frontmatter parsing patterns

## Deliverable
Create new Python module at .aitask-scripts/brainstorm/ with:

### brainstorm_dag.py — DAG Operations
- create_node(session_dir, node_id, parents, description, dimensions, proposal_content) — creates nXXX_name.yaml in nodes/ and nXXX_name.md in proposals/
- read_node(session_dir, node_id) — reads and returns node YAML as dict
- update_node(session_dir, node_id, updates) — updates specific fields in node YAML
- list_nodes(session_dir) — returns all node IDs sorted by creation order
- get_head(session_dir) — reads graph_state.yaml and returns current HEAD node ID
- set_head(session_dir, node_id) — updates HEAD in graph_state.yaml, appends to history
- get_parents(session_dir, node_id) — returns parent node IDs from node YAML
- get_children(session_dir, node_id) — finds all nodes that list this node as a parent
- next_node_id(session_dir) — reads and increments next_node_id in graph_state.yaml
- get_node_lineage(session_dir, node_id) — trace ancestry back to root (for context gathering)

### brainstorm_session.py — Session Management
- init_session(task_num, task_file, user_email, initial_spec) — creates .aitask-brainstorm/task_num/ with session.yaml, graph_state.yaml, nodes/, proposals/, plans/ dirs
- load_session(task_num) — loads and returns session.yaml as dict
- save_session(task_num, updates) — updates session.yaml fields
- session_exists(task_num) — checks if session dir exists
- list_sessions() — lists all active brainstorm sessions
- finalize_session(task_num) — copies HEAD node plan to aiplans/, marks session completed
- archive_session(task_num) — moves session data to archived location

### brainstorm_schemas.py — Validation
- validate_node(data) — validates node YAML against expected schema
- validate_graph_state(data) — validates graph_state.yaml
- validate_session(data) — validates session.yaml
- NODE_SCHEMA, GRAPH_STATE_SCHEMA, SESSION_SCHEMA — schema definitions as dicts

## Verification
- Unit tests in tests/test_brainstorm_dag.sh or tests/test_brainstorm_dag.py
- Test create_node creates both YAML and MD files with correct content
- Test set_head updates graph_state and appends to history
- Test get_children correctly finds reverse references
- Test init_session creates correct directory structure
- Test finalize_session copies plan to aiplans/
