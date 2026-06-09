---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: refactor
status: Done
labels: [ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-08 12:31
updated_at: 2026-06-09 11:56
completed_at: 2026-06-09 11:56
---

## Context

Follow-up split out of t945_2. During t945_2's review the user asked to move
the section minimap out of the scrollable content into a **fixed sibling pane**
"in all places where the minimap is currently inlined". t945_2 did this for the
explore wizard's `ProposalPreviewPane`; this task applies the identical refactor
to the remaining inline site: `NodeDetailModal`'s **Proposal** and **Plan** tabs.

## Problem

In `NodeDetailModal` (`.aitask-scripts/brainstorm/brainstorm_app.py`), each tab
mounts an `_InlineSectionMinimap` *inside* the tab's `VerticalScroll`, `before`
the `Markdown` (`on_mount`, proposal ~`:1092-1095`, plan ~`:1106-1109`). So the
minimap scrolls out of view, and `on_section_minimap_section_selected`
(~`:1111-1155`) needs a crude `estimate_section_y` + `±minimap_height`
correction that slightly overshoots.

## The fix (mirror t945_2's ProposalPreviewPane + SectionViewerScreen)

Adopt the proven `SectionViewerScreen` layout (`lib/section_viewer.py:474`):
a fixed-width `SectionMinimap` sibling beside a scrollable `SectionAwareMarkdown`.

1. In `compose()` (proposal tab ~`:1035`, plan tab ~`:1040`), replace
   `VerticalScroll(Markdown(id="proposal_content"), id="proposal_scroll")` (and
   the plan equivalent) with a `Horizontal` containing a fixed
   `_InlineSectionMinimap` (id `proposal_minimap` / `plan_minimap`) + a
   `SectionAwareMarkdown` (id `proposal_content` / `plan_content`). Add CSS for
   the fixed minimap column (see `ProposalPreviewPane.DEFAULT_CSS` in t945_2 and
   `#sv_minimap` in section_viewer.py).
2. In `on_mount()`, drop the inline `mount(minimap, before=...)`; instead
   `content.update_content(text, parsed)` + `minimap.populate(parsed)` (toggle
   `minimap.display` when there are no sections, as `ProposalPreviewPane.populate`
   does).
3. Rewrite `on_section_minimap_section_selected` (~`:1111-1155`) to delegate to
   the active tab's `SectionAwareMarkdown.request_scroll_to_section(name)` —
   removing the `estimate_section_y` / `minimap_height` math (fixes the
   overshoot here too).
4. Keep `action_focus_minimap` (~`:1157-1182`) — the Tab focus routing is
   unchanged; the minimap is still a descendant with the same id.

## Reference

- t945_2 archived plan `aiplans/archived/p945/p945_2_*.md` — the same refactor on
  `ProposalPreviewPane` (base class → `Horizontal`, lazy `SectionAwareMarkdown`,
  `request_scroll_to_section` delegation).
- `SectionViewerScreen` / `SectionAwareMarkdown` (`lib/section_viewer.py`) — the
  canonical fixed-minimap-beside-scroll pattern.

## Verification

- Launch `ait brainstorm`, open a node detail (Enter), Proposal and Plan tabs:
  the minimap stays fixed/visible while the content scrolls; selecting a minimap
  row scrolls the heading to the top without overshooting; Tab still focuses the
  minimap; `v` fullscreen still works.
