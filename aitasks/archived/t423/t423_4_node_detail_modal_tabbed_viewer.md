---
priority: medium
effort: medium
depends: [t423_3]
issue_type: feature
status: Done
labels: [brainstorming, tui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-20 12:40
updated_at: 2026-03-22 13:01
completed_at: 2026-03-22 13:01
---

## Context
Implement the Node Detail modal as a ModalScreen with TabbedContent (3 tabs: Metadata, Proposal, Plan). Opened from any tab via Enter on a node.

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — Implement NodeDetailModal(ModalScreen)

## Reference Files for Patterns
- `.aitask-scripts/brainstorm/brainstorm_dag.py` — `read_node()`, `read_proposal()`, `read_plan()`
- `.aitask-scripts/brainstorm/brainstorm_schemas.py` — `get_dimension_fields()` for dimension extraction
- `.aitask-scripts/board/aitask_board.py` — ModalScreen pattern

## Implementation
1. Create `NodeDetailModal(ModalScreen)` accepting node_id parameter
2. compose() yields TabbedContent with 3 TabPanes: Metadata, Proposal, Plan
3. Metadata tab: Static labels for node_id, parents, description, created_at, created_by_group + dimension fields (req_*, comp_*, tradeoff_*, assumption_*)
4. Proposal tab: Markdown widget rendering content from read_proposal()
5. Plan tab: Markdown widget rendering content from read_plan() or "No plan generated" placeholder
6. Esc closes modal (Binding already in ModalScreen)
7. CSS for modal sizing (80% width, 90% height, centered)

## Manual Verification
1. Enter on node → modal opens with 3 tabs
2. Metadata tab shows YAML fields + dimensions
3. Proposal tab renders markdown
4. Plan tab renders markdown or placeholder
5. Tab switching preserves scroll position
6. Esc closes modal
