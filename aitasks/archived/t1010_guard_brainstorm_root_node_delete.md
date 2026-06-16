---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: codex/gpt5_5
created_at: 2026-06-16 14:22
updated_at: 2026-06-16 16:16
completed_at: 2026-06-16 16:16
---

## Problem

The brainstorm TUI has **no guard preventing deletion of the DAG root node** (`n000_init`). Deleting the root cascade-deletes its entire descendants closure — i.e. every node in the graph — leaving a nodeless, broken session with no recovery path short of a full session delete/re-init. The only protection today is the generic two-click confirmation modal, which is not root-aware.

## Evidence (exploration findings)

Node-delete flow: `A` keybinding → `action_node_action` → `NodeActionSelectModal` (`delete` op) → `_open_delete_node_modal` → `DeleteNodeModal` (double-confirm) → `_on_delete_node_result` → `delete_node_cascade`.

At every layer the root is treated like any other node:

- `delete_node_cascade` (`.aitask-scripts/brainstorm/brainstorm_dag.py:273`) — the only check is `missing_root`, which merely means "node id not found in the graph" (lines 293-299). There is no check for "this node *is* the graph root."
- `_node_action_op_states` (`.aitask-scripts/brainstorm/brainstorm_app.py:4144`) — disables `module_decompose` / `module_merge` / `module_sync` on the umbrella root (lines 4162-4174), but `delete` is never placed in the disabled map, so it defaults to enabled on every node including the root.
- `NodeActionSelectModal._OPS` (`.aitask-scripts/brainstorm/brainstorm_app.py:4453`) always lists `delete`.
- `_open_delete_node_modal` / `_on_delete_node_result` (`brainstorm_app.py:4364`, `4390`) only re-check node existence + the running-agent guard — no root check.

The root node `n000_init` is created at session init (`.aitask-scripts/brainstorm/brainstorm_session.py:140`). Deleting it: closure = all nodes; all `current_heads` repoint to `_first_surviving_parent(root)` = `None` (root has no parent) and are cleared.

## Proposed fix

Add a root-node guard so the root cannot be cascade-deleted. Options (decide during planning):

1. **Disable the `delete` op on the root** in `_node_action_op_states` (mirror the existing module-op disable pattern), with reason e.g. "cannot delete the root design".
2. **Defense-in-depth:** also reject root deletion in `delete_node_cascade` (and/or `_on_delete_node_result`) — return a `is_root`/refusal report rather than wiping the graph — so the CLI/programmatic path is protected too, not just the TUI picker.

Identify the root robustly (it has no parent / is the earliest node) rather than hard-coding `n000_init`.

## Acceptance

- Attempting to delete the root node is blocked (op disabled in the picker with a clear reason, and/or `delete_node_cascade` refuses with a report flag).
- Deleting non-root nodes is unaffected.
- Add/extend tests covering: root-delete refusal, and that non-root cascade delete still works.

## Note

Discovered while exploring the brainstorm code from the `aitasks_go` checkout; the brainstorm source lives in this framework repo, so the task is tracked here.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-16T13:11:15Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-06-16T13:15:25Z status=pass attempt=1 type=human
