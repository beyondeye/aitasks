---
Task: t423_4_node_detail_modal_tabbed_viewer.md
Parent Task: aitasks/t423_design_and_finalize_brainstorm_tui.md
Worktree: (none - working on current branch)
Branch: (current)
Base branch: main
---

## Context

Implement the Node Detail modal as a ModalScreen with TabbedContent (3 tabs: Metadata, Proposal, Plan). Opened from any tab via Enter on a node.

## Implementation

1. Create `NodeDetailModal(ModalScreen)` accepting node_id parameter
2. compose() yields TabbedContent with 3 TabPanes: Metadata, Proposal, Plan
3. Metadata tab: Static labels for node_id, parents, description, created_at, created_by_group + dimension fields (req_*, comp_*, tradeoff_*, assumption_*)
4. Proposal tab: Markdown widget rendering content from read_proposal()
5. Plan tab: Markdown widget rendering content from read_plan() or "No plan generated" placeholder
6. Esc closes modal (Binding already in ModalScreen)
7. CSS for modal sizing (80% width, 90% height, centered)

### Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` -- Implement NodeDetailModal(ModalScreen)

### Reference Files for Patterns
- `.aitask-scripts/brainstorm/brainstorm_dag.py` -- `read_node()`, `read_proposal()`, `read_plan()`
- `.aitask-scripts/brainstorm/brainstorm_schemas.py` -- `get_dimension_fields()` for dimension extraction
- `.aitask-scripts/board/aitask_board.py` -- ModalScreen pattern

### Manual Verification
1. Enter on node -- modal opens with 3 tabs
2. Metadata tab shows YAML fields + dimensions
3. Proposal tab renders markdown
4. Plan tab renders markdown or placeholder
5. Tab switching preserves scroll position
6. Esc closes modal

## Post-Implementation

Follow Step 9 of the task workflow (testing, verification, commit).
