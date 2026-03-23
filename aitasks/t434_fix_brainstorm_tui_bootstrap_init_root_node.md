---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [brainstorming, tui]
created_at: 2026-03-23 09:36
updated_at: 2026-03-23 10:22
---

## Problem

The brainstorm TUI initialization creates an empty session (br_session.yaml, br_graph_state.yaml, br_groups.yaml, empty directories) but **does not create an initial root node** (n000_init). This leaves users stuck with zero nodes after init — all design operations (explore, compare, hybridize, detail, patch) require selecting existing nodes, creating a deadlock.

The architecture doc (`aidocs/brainstorming/brainstorm_engine_architecture.md`) assumes n000_init exists in all examples, but no code path actually creates it.

Additionally, the task description (`initial_spec`) is stored in br_session.yaml but never displayed anywhere in the TUI — users can't see what they're brainstorming about.

## Root Cause

1. `brainstorm_session.py:init_session()` creates session files and directories but stops there — no node creation
2. `brainstorm_app.py:_config_explore()` (line 1007) iterates `list_nodes()` to show base node selection, but with 0 nodes, the list is empty and nothing can be selected
3. `brainstorm_app.py:_update_session_status()` (line 722) displays status info but omits `initial_spec`
4. Session status transitions from `init` → `active` only on first design op (line 1274), but that code is unreachable without nodes

## Required Fixes

### Fix 1: Create root node during initialization (critical)

In `init_session()` (or in `brainstorm_cli.py:cmd_init()` after init_session returns), create an `n000_init` root node:
- `node_id`: `n000_init`
- `parents`: `[]` (root)
- `description`: Brief summary extracted from the task title/first line
- `proposal_file`: `br_proposals/n000_init.md` — populated with the full initial_spec (task file content)
- `created_by_group`: `bootstrap`
- Set as HEAD in br_graph_state.yaml
- Increment next_node_id to 1
- Transition session status from `init` to `active`

### Fix 2: Display task brief in TUI dashboard

In `_update_session_status()`, add the task description (or a truncated summary) to the session status display. Users need to see what they're brainstorming about. Options:
- Show first ~5 lines of `initial_spec` in the session status area
- Or add a dedicated "Brief" section/widget on the Dashboard tab

### Fix 3: Handle edge case — explore with no nodes (defensive)

In `_config_explore()`, if `list_nodes()` returns empty, show a helpful message instead of an empty form. This is a safety net in case a session somehow ends up without nodes.

## Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_session.py` — init_session() or new helper
- `.aitask-scripts/brainstorm/brainstorm_cli.py` — cmd_init() to call node creation
- `.aitask-scripts/brainstorm/brainstorm_app.py` — _update_session_status(), _config_explore()
- `.aitask-scripts/brainstorm/brainstorm_dag.py` — create_node() already exists, just needs to be called

## Verification

- Launch `ait brainstorm <task_num>` on a task without an existing session
- After init, Dashboard should show: Nodes: 1, HEAD: n000_init, and the task brief
- The n000_init node should appear in the node list with the task description as its proposal
- The explore operation should show n000_init as the available base node
- The DAG tab should render the single root node
