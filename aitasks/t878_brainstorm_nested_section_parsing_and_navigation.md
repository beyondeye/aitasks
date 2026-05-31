---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [brainstorming, ait_brainstorm, ui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-31 16:19
updated_at: 2026-05-31 16:36
boardidx: 100
---

## Origin

Spawned from t873_2 during Step 8b review (upstream defect follow-up). t873_2
fixed proposal section scroll accuracy + auto-scroll, but its diagnosis surfaced
a separate, pre-existing parsing limitation that bounds what section navigation
can ever resolve.

## Upstream defect

`.aitask-scripts/brainstorm/brainstorm_sections.py:70-109` — `parse_sections` is
**non-reentrant**: it only opens a new section when not already inside one
(`if open_m and cur_name is None`) and only closes on a matching `<!-- /section:
NAME -->`. The brainstorm agent templates emit **nested** section markers — a
catch-all `<!-- section: components [dimensions: component_*] -->` wrapping many
`<!-- section: component_X [dimensions: component_X] -->` subsections. The parser
swallows every nested open marker as plain content of the outer section, so the
inner `component_*` subsections are never parsed as their own `ContentSection`.

User-visible effect: in `ait brainstorm`, opening a `component_X` dimension from
the node detail pane lands on the parent `## Components` heading rather than that
component's own subsection heading; the minimap likewise lists only the
top-level sections. (Confirmed against `crew-brainstorm-635` n004: 20 open/close
tags collapse to 7 parsed sections.)

## Diagnostic context

From t873_2 (`aiplans/p873/p873_2_section_scroll_to_position_accuracy.md`):
verifying the scroll fix against real session-635 data showed `parse_sections`
returns only top-level sections. t873_2's scroll fix correctly lands every
*parsed* section at the viewport top, but cannot target an unparsed subsection.
t873_1 (glob expansion) made `get_sections_for_dimension(component_X)` resolve to
the `components` section because the outer section's `[dimensions: ...]` tag
lists all the component keys explicitly — so the link works, but navigation
granularity is capped at the wrapper section.

## Suggested fix

Make `parse_sections` represent nesting (a stack of open sections, or a parent/
child tree on `ContentSection`), then thread nested sections through the minimap
list and `get_sections_for_dimension` so a `component_X` dimension resolves to —
and the viewer scrolls to — that subsection's own heading. Reuse
`section_viewer.correlate_sections_to_toc` for the heading→`header_id` mapping
(it already keys on the section's first heading, which works per-subsection).
Touches `brainstorm_sections.py` (parser + `validate_sections` duplicate-name
check), `brainstorm_app.py` (detail pane / `on_dimension_row_activated` / compare
wizard section sources), and `section_viewer.py` (minimap population). Mind the
existing duplicate-section-name validation when subsection names repeat across
parents.
