---
Task: t945_2_wire_preview_into_explore_wizard.md
Parent Task: aitasks/t945_show_proposal_viewer_side_by_side_to_explore_and_decompose.md
Sibling Tasks: aitasks/t945/t945_1_reusable_proposal_preview_pane.md, aitasks/t945/t945_3_wire_preview_into_decompose_and_add_source_node_choice.md
Archived Sibling Plans: aiplans/archived/p945/p945_*_*.md
Worktree: aiwork/t945_2_wire_preview_into_explore_wizard
Branch: aitask/t945_2_wire_preview_into_explore_wizard
Base branch: main
---

# t945_2 — Wire the preview pane into the explore wizard

## Context

Second child of t945. Use the reusable proposal-preview component from t945_1
to show the selected base node's proposal side-by-side with the Exploration
Mandate input in the explore wizard's config step.

Depends on t945_1 (read its archived plan
`aiplans/archived/p945/p945_1_*.md` for the `ProposalPreviewPane` /
`_mount_config_with_preview` API before starting).

## Existing pieces to reuse
- `_mount_config_with_preview` + `ProposalPreviewPane` (from t945_1).
- `read_proposal` (`brainstorm/brainstorm_dag.py:514`).
- Current explore config: `_config_explore_no_node` (`brainstorm_app.py:6813`).

## Implementation steps

1. **Refactor `_config_explore_no_node` (`brainstorm_app.py:6813`):** move the
   existing mounts — the `Base Node:` label, the `Exploration Mandate` label +
   `TextArea`, the `CycleField("Parallel explorers", ...)`, and the `Next ▶`
   button — into a `left_builder(left)` closure that mounts them into the left
   pane.
2. Resolve the base node and its proposal:
   ```python
   node_id = self._wizard_config.get("_selected_node", "?")
   try:
       proposal = read_proposal(self.session_path, node_id)
   except Exception:
       proposal = "*No proposal found.*"
   self._mount_config_with_preview(container, left_builder, proposal)
   ```
3. Keep the `Base Node:` label in the left-pane header for context.

## Collector invariance (must verify, do not regress)
`_actions_collect_config` explore branch (`brainstorm_app.py:7148-7157`) reads
`container.query_one(TextArea)` (mandate) and `container.query_one(CycleField)`
(parallel) against `#actions_content`. These are single-match queries — they
raise if the preview pane introduced a second `TextArea`/`CycleField`. t945_1
guarantees the pane adds neither (only `Markdown` + minimap `VerticalScroll`).
Confirm by running an explore through to the confirm step.

## Verification
- Launch `ait brainstorm`; run explore → select a node → config step. Confirm:
  the selected node's proposal renders on the right with a working minimap (Tab
  focus, Enter/↑↓ section jump); the ratio-cycle key works; submitting the
  mandate (`Next ▶`) proceeds to confirm exactly as before.
- Confirm `_actions_collect_config` collects mandate + parallel without
  `query_one` ambiguity errors.

## Reference to parent workflow
On completion follow task-workflow Step 8 (review) → Step 9 (archival).
