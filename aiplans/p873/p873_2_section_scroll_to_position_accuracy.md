---
Task: t873_2_section_scroll_to_position_accuracy.md
Parent Task: aitasks/t873_fix_brainstorm_dimension_proposal_linking_and_compare.md
Sibling Tasks: aitasks/t873/t873_*.md
Archived Sibling Plans: aiplans/archived/p873/p873_*_*.md
Worktree: aiwork/t873_2_section_scroll_to_position_accuracy
Branch: aitask/t873_2_section_scroll_to_position_accuracy
Base branch: main
---

# Plan: t873_2 — Section scroll-to-position accuracy

Replace the crude raw-line-ratio scroll estimate in `SectionViewer` with a real
rendered-offset lookup, so jumping to a proposal section lands on that section.

## Root cause
`SectionAwareMarkdown.scroll_to_section()`
(`.aitask-scripts/lib/section_viewer.py:277-289`) uses
`ratio = section.start_line / total_lines` (set in `update_content` :268-275) then
`target_y = ratio * max_scroll_y`. Raw source lines include hidden HTML-comment
markers / section tags the Textual `Markdown` widget renders at different or zero
heights, so on 373–709-line proposals the target drifts off-section. The repo
already notes "Textual's `Markdown` widget does not expose per-line offsets."

## Steps
1. **Probe the installed Textual `Markdown` API** (no version pinned in repo):
   - Prefer `Markdown.goto_anchor(slug)` if present — anchors are heading-slug
     based; map each section to the slug of its first rendered heading.
   - Else query the `Markdown` child block widgets (heading/`MarkdownBlock`),
     find the block for the section's first heading, and scroll via
     `self.scroll_to_widget(block, ...)` or
     `self.scroll_to(y=block.region.y - self.region.y + self.scroll_offset.y)`.
2. **`update_content`** — keep enough state to resolve a section to its first
   heading (section name + first heading line from `section.content`); retain the
   line-ratio only as a defensive fallback.
3. **`scroll_to_section(name)`** — resolve the real offset (step 1) and scroll;
   fall back to the old ratio math only when no block matches.
4. **Timing** — resolution must run after layout. Keep
   `SectionViewerScreen._poll_auto_scroll` (`:392`) which polls
   `virtual_size.height`; the minimap path (`on_section_minimap_section_selected`
   `:420`) already fires post-layout.
5. **Test** — add a unit test for the block-resolution helper where the layer is
   mockable (e.g. correct block index for a multi-section doc). Note in Final
   Implementation Notes that primary validation is manual (t873 mv sibling).

## Verification
- `bash tests/run_all_python_tests.sh`.
- Manual (no regeneration): `ait brainstorm` → session `crew-brainstorm-635` →
  n004 (709-line) → Enter on a deep-section dimension row lands on that section's
  heading; repeat on n002 (373/585-line); confirm minimap selection also lands
  accurately.

## Post-implementation
Follow task-workflow Step 8 (review/commit) and Step 9 (archival/merge). Record
any related upstream defect in the plan's Final Implementation Notes.
