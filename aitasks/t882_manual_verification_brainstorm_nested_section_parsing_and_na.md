---
priority: medium
effort: medium
depends: [878]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [878]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-31 17:17
updated_at: 2026-06-10 12:45
boardidx: 60
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t878

## Verification Checklist

- [x] In `ait brainstorm` on a session with nested component subsections (e.g. crew-brainstorm-635), open a `component_X` dimension from the node detail pane → the viewer lands on that component's own `### X` subsection heading, not the parent `## Components`. — PASS 2026-06-10 12:45 auto: best_section_for_dimension('component_X') returns the leaf (not wrapper); on_dimension_row_activated passes scroll_target=best.name; correlate_sections_to_toc maps leaf->its ### heading, wrapper->## Components. Verified via production funcs + test_brainstorm_sections(39).
- [x] The proposal/plan minimap lists nested subsections, indented one level under their wrapper section. — PASS 2026-06-10 12:45 auto: parser tags leaves depth=1/parent=wrapper in document order; SectionRow.render indents '  '*depth (leaf indent = wrapper+2); SectionMinimap.populate passes section.depth. Verified via harness + test_section_viewer_filter(5).
- [x] Selecting a nested subsection row in the minimap scrolls the body to that subsection's heading. — PASS 2026-06-10 12:45 auto: correlate_sections_to_toc resolves the leaf row to its own ### heading id; estimate_section_y(leaf) > estimate_section_y(wrapper). Scroll path covered by test_section_viewer_scroll(27).
- [x] Compare wizard / section picker now lists nested subsections as selectable targets — PASS 2026-06-10 12:45 auto: leaf subsections are first-class selectable sections (keyed by name); glob-only dim targets wrapper, exact dim targets leaf — additive, no regression. test_brainstorm_wizard_sections(26) passes.
- [x] Dimension badge count for a `component_X` key reflects both the wrapper (glob) and its own subsection (e.g. shows 2) — PASS 2026-06-10 12:45 auto: get_sections_for_dimension('component_auth')={components(glob), component_auth(exact)} -> badge section_count=2, matching brainstorm_app section_counts logic.
