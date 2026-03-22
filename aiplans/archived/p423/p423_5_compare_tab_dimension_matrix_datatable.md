---
Task: t423_5_compare_tab_dimension_matrix_datatable.md
Parent Task: aitasks/t423_design_and_finalize_brainstorm_tui.md
Sibling Tasks: aitasks/t423/t423_6_*.md, aitasks/t423/t423_7_*.md
Archived Sibling Plans: aiplans/archived/p423/p423_*_*.md
Worktree: (none - working on current branch)
Branch: (current)
Base branch: main
---

## Context

Implement the Compare tab (Tab 3) showing a dimension matrix table for comparing 2+ nodes. Uses Textual's DataTable with color-coded cells (green=identical, yellow=similar, red=different). Currently a placeholder label.

## Key Files

- `.aitask-scripts/brainstorm/brainstorm_app.py` — Main file: new modal, replace placeholder, keybindings, matrix builder
- `.aitask-scripts/brainstorm/brainstorm_schemas.py` — `extract_dimensions()`, `is_dimension_field()`
- `.aitask-scripts/brainstorm/brainstorm_dag.py` — `list_nodes()`, `read_node()`, `get_dimension_fields()`
- `.aitask-scripts/diffviewer/diff_engine.py` — Pattern: `SequenceMatcher` for similarity (0.6 threshold)
- `.aitask-scripts/diffviewer/plan_manager_screen.py` — Pattern: `Checkbox` for multi-select

## Implementation

### 1. Add imports to `brainstorm_app.py`
- Add `DataTable, Checkbox` to textual.widgets import
- Add `from difflib import SequenceMatcher`
- Add `from rich.text import Text`
- Add `from brainstorm.brainstorm_schemas import extract_dimensions`

### 2. Create `CompareNodeSelectModal(ModalScreen)`
- Checkbox-based selection for 2-4 nodes (follows InitSessionModal + Checkbox pattern)
- Validate: at least 2, at most 4 selected
- Dismiss with list of selected node IDs or None on cancel

### 3. Replace Compare tab placeholder (lines 377-384)
- Replace placeholder label with hint: "Press 'c' to select nodes for comparison"
- Keep `id="compare_content"` on the VerticalScroll container

### 4. Add `_build_compare_matrix(selected_nodes)` method
- Extract dimensions for each node via `extract_dimensions(read_node(...))`
- Collect union of all dimension keys
- Build DataTable with "Dimension" column + one column per node
- Color-code cells using `Rich.Text` with styles:
  - All identical → green
  - Max pairwise similarity > 0.6 → yellow
  - Otherwise → red
- Add similarity score row at bottom (pairwise average via SequenceMatcher.ratio())

### 5. Add `_on_compare_selected` callback
- If selection is None (cancelled), do nothing
- Otherwise call `_build_compare_matrix(selected)`

### 6. Add key handlers in `on_key`
- `c` key (on Compare tab, not in modal): open CompareNodeSelectModal
- `d` key (on Compare tab, with compare_nodes set): launch diff for first two nodes' proposals

### 7. Add CSS for modal and table

## Manual Verification
1. Run app with a session that has 2+ nodes
2. Press `3` → Compare tab with hint text
3. Press `c` → node selection modal with checkboxes
4. Select 2-3 nodes → DataTable renders with dimension matrix
5. Green/yellow/red coloring correct
6. Similarity score row at bottom
7. `d` key launches diff for proposals
8. `c` again → re-select different nodes

## Final Implementation Notes

- **Actual work done:** Replaced Compare tab placeholder in `brainstorm_app.py` with a fully functional dimension matrix comparison feature. Added `CompareNodeSelectModal` (checkbox-based, 2-4 nodes), `_build_compare_matrix()` (DataTable with color-coded Rich `Text` cells), `_add_similarity_row()` (pairwise SequenceMatcher average), and key handlers for `c` (select nodes) and `d` (launch diff). Added CSS for compare modal and table. Total: +212/-4 lines in a single file.
- **Deviations from plan:** None significant. Plan was followed as written.
- **Issues encountered:** None.
- **Key decisions:** Used Rich `Text` objects with style colors for per-cell coloring in DataTable (green/yellow/red). Used `SequenceMatcher.ratio()` with 0.6 threshold for similarity (matching existing pattern in `diff_engine.py`). The `d` key launches system `diff --color=always` for proposal text comparison.
- **Notes for sibling tasks:** `_compare_nodes` instance attribute stores the currently compared node IDs (set after matrix build). The `CompareNodeSelectModal` pattern (Checkbox-based selection with validation) can be reused for Actions tab wizard (t423_6). The `extract_dimensions` import from `brainstorm_schemas` is now available at app level. CSS IDs used: `compare_hint`, `compare_table`, `compare_select_dialog`, `compare_select_title`, `compare_checkbox_list`, `compare_select_buttons`.
