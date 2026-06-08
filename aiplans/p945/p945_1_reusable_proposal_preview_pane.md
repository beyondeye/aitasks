---
Task: t945_1_reusable_proposal_preview_pane.md
Parent Task: aitasks/t945_show_proposal_viewer_side_by_side_to_explore_and_decompose.md
Sibling Tasks: aitasks/t945/t945_2_wire_preview_into_explore_wizard.md, aitasks/t945/t945_3_wire_preview_into_decompose_and_add_source_node_choice.md
Archived Sibling Plans: aiplans/archived/p945/p945_*_*.md
Worktree: aiwork/t945_1_reusable_proposal_preview_pane
Branch: aitask/t945_1_reusable_proposal_preview_pane
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-08 11:04
---

# t945_1 — Reusable side-by-side proposal-preview component

## Context

First child of t945. The explore / module-decompose wizard config steps in
`ait brainstorm` collect a free-text input (Exploration Mandate /
Decomposition Plan) but show no view of the proposal being written against.
This child builds the **reusable** component both wizards will mount (t945_2 =
explore, t945_3 = decompose). No op wiring lands here — only shared
infrastructure, exercisable via a small internal harness.

User-locked decisions (see parent plan): side-by-side (input left,
proposal+minimap right); adjustable split (key cycles input-wide / 50-50 /
proposal-wide); reflow-stable scroll (keep top line on top after a ratio
change); navigable minimap like `NodeDetailModal` (Tab focuses minimap,
Enter/↑↓ jumps the proposal to a section).

## Plan verification (2026-06-08)

Re-verified all cited references against current code. All entities exist; line
numbers drifted slightly but structure/signatures match:
- `_InlineSectionMinimap` (line 882) — factory returning a `_NoTabMinimap`
  subclass of `SectionMinimap` with empty `BINDINGS` (Tab removed); `.populate(parsed)`.
- `NodeDetailModal` proposal tab build at ~938-998; minimap mounted **before**
  `#proposal_content` Markdown inside a `VerticalScroll`
  (`prop_scroll.mount(prop_minimap, before="#proposal_content")`).
- `on_section_minimap_section_selected` handler now at **1014-1058**; the
  scroll-to-section math (`estimate_section_y` against `max_scroll_y - minimap_height`)
  is at **1038-1057**.
- `action_focus_minimap` at **1060-1085**.
- `_actions_show_config` at **6767**; `_config_explore_no_node` at **6813**;
  `_config_module_decompose` at **6962**; `_actions_collect_config` at **7134**
  (explore branch 7148-7157, module_decompose 7201-7205).
- CSS `#dashboard_split` `Horizontal` 40%/60% at ~2871.
- `section_viewer.py`: `estimate_section_y(parsed, name, total_lines, virtual_height)`;
  `SectionMinimap.SectionSelected(section_name)`.
- `parse_sections(text) -> ParsedContent` with `.sections` (brainstorm_sections.py:77).
- `read_proposal(session_path, node_id)` (brainstorm_dag.py:514).
- `shortcut_scopes.py`: manifest registry `KNOWN_BINDING_SOURCES`; `brainstorm_app`
  already registered with scopes `("brainstorm", "brainstorm.compare_select")`.

## Existing pieces to reuse
- `_InlineSectionMinimap` (`brainstorm_app.py:882`) — Tab-binding-free
  `SectionMinimap` subclass; `.populate(parsed)`.
- `NodeDetailModal` proposal tab + `on_section_minimap_section_selected`
  (`brainstorm_app.py:938-1058`) — canonical mount order (minimap mounted
  `before` the `Markdown` inside a `VerticalScroll`) and scroll-to-section math
  (minimap-height correction against `max_scroll_y`, via `estimate_section_y`).
- `SectionMinimap`, `estimate_section_y`, `SectionMinimap.SectionSelected`
  (`.aitask-scripts/lib/section_viewer.py`).
- `parse_sections` (`brainstorm/brainstorm_sections.py:77`).
- Split-pane precedent: `Horizontal#dashboard_split` (40%/60%) + CSS
  (`brainstorm_app.py:~2871`).
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
     find them without colliding with `NodeDetailModal`'s `#proposal_minimap` /
     `#proposal_content`.

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
   pane exists on the Actions tab); on guard-miss raise
   `textual.actions.SkipAction`.

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
   `action_focus_minimap`, lines 1060-1085), no-op when focus is already inside
   the minimap.

## Verification
- Launch `ait brainstorm`. Exercise the pane via the internal harness (or land
  t945_2 to drive it). Confirm: minimap rows navigate and scroll the proposal;
  Tab moves focus input↔minimap; the ratio-cycle key cycles three widths;
  after each ratio change the previously-top line stays at the top.
- Run any touched brainstorm app tests under `tests/`.

## Risk

### Code-health risk: medium
- Touches `brainstorm_app.py`, a large, complex Textual TUI, adding an
  App-level `on_section_minimap_section_selected` handler + a Tab focus action
  alongside `NodeDetailModal`'s existing ones — risk of message-routing / focus
  collision. · severity: medium · → mitigation: handled in-task (unique
  id/class for the pane's minimap; guard scoped to `self.screen.query_one`
  raising `SkipAction` on miss).
- New keybinding + CSS width classes added to shared registry/CSS. · severity:
  low · → mitigation: register per `shortcut_scopes.py` manifest + surface in
  footer per `tui_conventions.md`.

### Goal-achievement risk: medium
- Reflow-stable scroll (capture top line → reflow via `call_after_refresh` →
  restore) is timing- and math-sensitive; getting the line-ratio mapping
  pixel-stable is fiddly. · severity: medium · → mitigation: handled in-task
  (reuse NodeDetailModal's proven `estimate_section_y`/`max_scroll_y`
  correction; explicit Verification step checks top-line stability).
- Standalone verification is partial — full exercise depends on t945_2 wiring
  it into the explore wizard. · severity: low · → mitigation: internal harness
  for this child; end-to-end coverage via parent t945's manual-verification
  flow.

_No separate before/after mitigation tasks: both dimensions are medium and
bounded, with risks addressed inside this task's own implementation and
verification (and the parent's manual-verification flow). No spike or
characterization-test task is warranted._
