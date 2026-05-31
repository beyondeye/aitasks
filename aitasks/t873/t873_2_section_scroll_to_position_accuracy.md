---
priority: high
effort: medium
depends: [t873_1]
issue_type: bug
status: Ready
labels: [brainstorming, ait_brainstorm, ui]
created_at: 2026-05-31 13:13
updated_at: 2026-05-31 13:13
---

Fix defect #2 of parent t873: proposal-section navigation lands off-target. When a dimension row's proposal jump resolves, `SectionViewer` scrolls to a crude proportional estimate over raw source line numbers, so on long proposals it drifts and misses the intended section.

## Context
`SectionAwareMarkdown.scroll_to_section()` (`.aitask-scripts/lib/section_viewer.py:277-289`) computes `ratio = section.start_line / total_lines` (set in `update_content`, :268-275) then `target_y = ratio * max_scroll_y`. This is a proportional estimate over **raw source line numbers** — including hidden HTML-comment section markers and tags the Textual `Markdown` widget renders at different (or zero) heights. On the 373–709-line proposals in session `crew-brainstorm-635` the target drifts noticeably and lands off the intended section. The code already acknowledges this: `estimate_section_y` notes "Textual's `Markdown` widget does not expose per-line offsets."

This child is fully independent of the others (different file). It depends on its sibling only by the framework's default sequential ordering.

## Key Files to Modify
- `.aitask-scripts/lib/section_viewer.py` — `SectionAwareMarkdown` (`update_content` :268-275, `scroll_to_section` :277-289). The fix replaces the raw-line-ratio math with a real rendered-offset lookup.

## Reference Files for Patterns
- `SectionViewerScreen.on_mount`/`_poll_auto_scroll` (`section_viewer.py:367,392`) already defers auto-scroll, polling `virtual_size.height` until the Markdown finishes laying out — **keep this deferral**; rendered block offsets are not valid until layout completes.
- `on_section_minimap_section_selected` (`:420`) calls `content.scroll_to_section(event.section_name)` — the same entry point must keep working.
- `ContentSection` carries `name`, `start_line`, `content` (`brainstorm_sections.py:20-29`); the section's first heading text can be recovered from `content`.
- Existing tests: `tests/test_section_viewer_filter.py` (unittest; `bash tests/run_all_python_tests.sh`). No Textual version is pinned in the repo — the implementer must check the installed version's `Markdown` API.

## Implementation Plan
1. Determine the installed Textual `Markdown` API surface for navigation:
   - If `Markdown.goto_anchor(slug)` is available, map each section to the slug of its first rendered heading and use it (anchors are heading-slug based).
   - Otherwise, query the `Markdown` widget's child block widgets (e.g. `MarkdownBlock` / heading widgets), match the one corresponding to the section's first heading, and scroll via `self.scroll_to_widget(block)` or `self.scroll_to(y=block.region.y - self.region.y + self.scroll_offset.y)`.
2. In `update_content`, instead of (or in addition to) the line ratio, retain enough to resolve a section to its first heading (the section name and/or first heading line of `section.content`).
3. Rewrite `scroll_to_section(name)` to resolve the real rendered offset and scroll to it; fall back to the existing ratio math only if the block can't be found (defensive).
4. Ensure the resolution runs after layout (the existing `_poll_auto_scroll` path; the minimap-driven path runs post-layout already).
5. Add a unit test where feasible (e.g. assert the resolution helper picks the correct block index for a multi-section document); acknowledge in the plan that primary validation is manual (covered by the t873 aggregate manual-verification sibling).

## Verification Steps
- `bash tests/run_all_python_tests.sh`.
- Manual (no regeneration): `ait brainstorm` → session 635 → focus n004 (709-line proposal) → Enter on a dimension row whose section sits deep in the proposal → the viewer should land on that section's heading, not an off-by-screens position. Repeat for n002 (373/585-line). Confirm minimap selection also lands accurately.
