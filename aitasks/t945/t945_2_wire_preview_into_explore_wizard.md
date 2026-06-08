---
priority: medium
effort: low
depends: [t945_1]
issue_type: feature
status: Implementing
labels: [ait_brainstorm, brainstorm_explore]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-08 09:31
updated_at: 2026-06-08 11:37
---

## Context

Part of t945. Wire the reusable proposal-preview component (built in t945_1)
into the **explore** operation's wizard config step, so the selected base
node's proposal is shown side-by-side with the Exploration Mandate input.

Depends on t945_1 (sibling auto-dependency).

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `_config_explore_no_node` (line 6813): refactor to call
    `_mount_config_with_preview` (from t945_1). The existing mandate
    `TextArea`, the `CycleField("Parallel explorers", ...)`, and the
    `Next ▶` button become the body of the `left_builder` callback. The right
    pane shows `read_proposal(self.session_path, node_id)` where `node_id =
    self._wizard_config.get("_selected_node")`.

## Reference Files for Patterns
- t945_1's `_mount_config_with_preview` + `ProposalPreviewPane`.
- `read_proposal` (`brainstorm/brainstorm_dag.py:514`).
- Current explore config: `_config_explore_no_node` (`brainstorm_app.py:6813`).
- Collector to keep working: `_actions_collect_config` explore branch
  (`brainstorm_app.py:7148-7157`) — reads
  `container.query_one(TextArea)` (mandate) and `query_one(CycleField)`
  (parallel). These must stay unambiguous: the preview pane adds no TextArea or
  CycleField (verify in t945_1), so the single-match queries are safe.

## Implementation Plan
1. Move the three existing `container.mount(...)` calls for explore (mandate
   label + `TextArea`, `CycleField`, Next button) into a `left_builder(left)`
   closure that mounts them into the left pane.
2. Read the base node id from `_wizard_config["_selected_node"]` and its
   proposal via `read_proposal`. Call
   `_mount_config_with_preview(container, left_builder, proposal)`.
3. Keep the `Base Node:` label visible (in the left pane header) for context.

## Verification Steps
- Launch `ait brainstorm`; run explore → select a node → config step.
  Confirm the selected node's proposal renders on the right with a working
  minimap (Tab focus, section jump), the ratio-cycle key works, and submitting
  the mandate (`Next ▶`) proceeds to confirm exactly as before.
- Confirm `_actions_collect_config` still collects mandate + parallel without
  error (no `query_one` ambiguity).
