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

## Final Implementation Notes

- **Actual work done:** Replaced the skeleton `NodeDetailModal` in `brainstorm_app.py` with a full 3-tab implementation. Added `Markdown`, `read_plan`, `read_proposal` imports. Constructor now accepts `session_path` alongside `node_id`. `compose()` yields TabbedContent with Metadata (Static + Rich markup), Proposal (Markdown widget), and Plan (Markdown widget) tabs. `on_mount()` loads data into all tabs. Updated CSS (height 80%→90%, added tab/scroll styling, removed placeholder). Updated both invocation sites (Dashboard Enter key, DAG NodeSelected) to pass `session_path`. Total: +78/-17 lines in a single file.
- **Deviations from plan:** Minor — plan listed CSS width as 80% which was already correct. Height changed to 90% per task spec. Used `VerticalScroll` wrappers around tab content for scrollability (not explicitly in original plan but follows established patterns).
- **Issues encountered:** None.
- **Key decisions:** Used Rich markup (`[bold]...[/bold]`) for metadata labels in the Static widget rather than plain text — matches the dashboard detail pane pattern. Used Textual's `Markdown` widget for proposal/plan rendering rather than Static, enabling proper markdown formatting. Wrapped each tab's content in `VerticalScroll` for long content scrollability.
- **Notes for sibling tasks:** `NodeDetailModal` now requires two arguments: `node_id: str` and `session_path: Path`. The modal's TabbedContent uses IDs `tab_metadata`, `tab_proposal`, `tab_plan`. Tab content widgets use IDs `metadata_content` (Static), `proposal_content` (Markdown), `plan_content` (Markdown). If future tasks need to add tabs or actions to the modal, the `on_mount()` pattern loads data after compose. The `Markdown` widget import is now available for use elsewhere in the app.
