---
Task: t423_5_compare_tab_dimension_matrix_datatable.md
Parent Task: aitasks/t423_design_and_finalize_brainstorm_tui.md
Worktree: (none - working on current branch)
Branch: (current)
Base branch: main
---

## Context

Implement the Compare tab (Tab 3) showing a dimension matrix table for comparing 2+ nodes. Uses Textual's DataTable with color-coded cells.

## Implementation

1. On entering Compare tab, show node selection dialog (checkboxes for 2-4 nodes)
2. After selection, build dimension matrix:
   a. Extract all dimension fields from selected nodes via extract_dimensions()
   b. Create DataTable: rows = dimension fields, columns = node IDs
   c. Populate cells with values
3. Color-coding: compare cell values across columns
   - Green: all values identical
   - Yellow: values similar (substring match or >0.6 similarity)
   - Red: values different
4. Add similarity score row at bottom
5. `d` key: launch external diff viewer for proposal text comparison (subprocess)

### Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` -- Replace Compare tab placeholder with matrix implementation

### Reference Files for Patterns
- `.aitask-scripts/brainstorm/brainstorm_schemas.py` -- `get_dimension_fields()`, `extract_dimensions()`
- `.aitask-scripts/brainstorm/brainstorm_dag.py` -- `list_nodes()`, `read_node()`

### Manual Verification
1. Switch to Compare tab -- node selection dialog
2. Select 2-3 nodes -- matrix renders
3. Same values green, different red
4. Navigate rows with arrows

## Post-Implementation

Follow Step 9 of the task workflow (testing, verification, commit).
