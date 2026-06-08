---
Task: t945_1_reusable_proposal_preview_pane.md
Parent Task: aitasks/t945_show_proposal_viewer_side_by_side_to_explore_and_decompose.md
Sibling Tasks: aitasks/t945/t945_2_wire_preview_into_explore_wizard.md, aitasks/t945/t945_3_wire_preview_into_decompose_and_add_source_node_choice.md
Archived Sibling Plans: aiplans/archived/p945/p945_*_*.md
Worktree: aiwork/t945_1_reusable_proposal_preview_pane
Branch: aitask/t945_1_reusable_proposal_preview_pane
Base branch: main
---

# t945_1 — Reusable side-by-side proposal-preview component

## Context

First child of t945. The explore / module-decompose wizard config steps in
`ait brainstorm` collect a free-text input but show no view of the proposal
being written against. This child builds the **reusable** component both
wizards will mount (t945_2 = explore, t945_3 = decompose). No op wiring lands
here — only shared infrastructure, exercisable via a small internal harness.

User-locked decisions (see parent plan): side-by-side (input left,
proposal+minimap right); adjustable split (key cycles input-wide / 50-50 /
proposal-wide); reflow-stable scroll (keep top line on top after a ratio
change); navigable minimap like `NodeDetailModal` (Tab focuses minimap,
Enter/↑↓ jumps the proposal to a section).

## Existing pieces to reuse
- `_InlineSectionMinimap` (`brainstorm_app.py:882`) — Tab-binding-free
  `SectionMinimap` subclass; `.populate(parsed)`.
- `NodeDetailModal` proposal tab + `on_section_minimap_section_selected`
  (`brainstorm_app.py:954-1058`) — canonical mount order (minimap mounted
  `before` the `Markdown` inside a `VerticalScroll`) and scroll-to-section math
  (minimap-height correction against `max_scroll_y`, via `estimate_section_y`).
- `SectionMinimap`, `estimate_section_y`, `SectionMinimap.SectionSelected`
  (`.aitask-scripts/lib/section_viewer.py:269`).
- `parse_sections` (`brainstorm/brainstorm_sections.py:77`).
- Split-pane precedent: `Horizontal#dashboard_split` (40%/60%) + CSS
  (`brainstorm_app.py:2871`).
- `aidocs/framework/tui_conventions.md` — register new keybindings in
  `shortcut_scopes.py`; footer must surface new ops; use `self.screen.query_one`
  not `App.query_one`.

## Implementation steps

1. **`ProposalPreviewPane` widget** (in `brainstorm_app.py`, near
   `_InlineSectionMinimap`): a container with a `VerticalScroll` holding an
   inline minimap mounted `before` a `Markdown`.
   - `populate(proposal_text: str)`: `parse_sections(text)`; update the
     `Markdown`; if `parsed.sections`, mount/refresh the minimap and
     `.populate(parsed)`, else hide the minimap. Stash `parsed` + `text` for
     scroll math.
   - `scroll_to_section(name)`: reuse the math at `brainstorm_app.py:1038-1057`
     (`estimate_section_y` against `max_scroll_y - minimap_height`).
   - Give the markdown/minimap a unique id/class so the Actions-tab handler can
     find them without colliding with `NodeDetailModal`'s `#proposal_minimap`.

2. **`_mount_config_with_preview(container, left_builder, proposal_text)`
   helper:** mount a `Horizontal` into `#actions_content` with a left
   `VerticalScroll` and a right `ProposalPreviewPane`. Call
   `left_builder(left)` to mount op-specific inputs verbatim. Call
   `pane.populate(proposal_text)`. **Constraint:** the pane must add no extra
   `TextArea`/`CycleField`/`RadioSet` (only `Markdown` + minimap `VerticalScroll`)
   so explore's `query_one(TextArea)`/`query_one(CycleField)` stay unambiguous.
   `_actions_collect_config` queries `#actions_content` recursively, so inputs
   nested in the left pane are still found.

3. **Adjustable split ratio:** App-level binding registered in
   `shortcut_scopes.py` (and shown in the Actions footer) that cycles three CSS
   width classes (input-wide / 50-50 / proposal-wide) on the two panes. Guard
   it to act only while a preview-bearing config step is mounted (check the
   pane exists on the Actions tab).

4. **Reflow-stable scroll:** before swapping width classes, record the top
   visible source line = `round(scroll.scroll_offset.y / max_scroll_y *
   total_lines)` (total = `text.count("\n")+1`); after the reflow
   (`call_after_refresh`), set `scroll.scroll_y` so that line ratio is back at
   the top (inverse mapping against the new `max_scroll_y`). Encapsulate as a
   `ProposalPreviewPane` method so callers just call `on_ratio_change()`.

5. **App-level section handler + Tab focus:** add
   `on_section_minimap_section_selected` on `BrainstormApp` that, when the event
   originates from the Actions-tab pane's minimap, calls
   `pane.scroll_to_section(event.section_name)` (mirror lines 1014-1058). Add a
   Tab action that focuses the pane's minimap from the left-pane input (mirror
   `action_focus_minimap`, lines 1060-1082), no-op when focus is already inside
   the minimap.

## Verification
- Launch `ait brainstorm`. Exercise the pane via the internal harness (or land
  t945_2 to drive it). Confirm: minimap rows navigate and scroll the proposal;
  Tab moves focus input↔minimap; the ratio-cycle key cycles three widths;
  after each ratio change the previously-top line stays at the top.
- Run any touched brainstorm app tests under `tests/`.

## Reference to parent workflow
On completion follow task-workflow Step 8 (review) → Step 9 (archival).
See parent plan for the overall t945 decomposition.
