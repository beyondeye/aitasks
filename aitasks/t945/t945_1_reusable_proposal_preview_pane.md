---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [ait_brainstorm, brainstorm_explore]
created_at: 2026-06-08 09:31
updated_at: 2026-06-08 09:31
---

## Context

Part of t945. Build the **reusable side-by-side proposal-preview component**
that both the explore (t945_2) and module-decompose (t945_3) wizard config
steps will mount. No op wiring lands here — this child delivers shared
infrastructure only, exercisable via a tiny internal harness.

In `ait brainstorm`, the explore / module-decompose config steps collect a
free-text input (Exploration Mandate / Decomposition Plan) but show no view of
the proposal being written against. This component renders the source
proposal (markdown + section **minimap**) beside the input.

User-locked decisions:
- Side-by-side: input left, proposal+minimap right.
- **Adjustable split:** a key cycles the ratio between input-wide / 50-50 /
  proposal-wide.
- **Reflow-stable scroll:** on a ratio change the markdown reflows; keep the
  line that was at the top still at the top.
- Navigable minimap exactly like `NodeDetailModal` (Tab focuses minimap;
  Enter/up-down on a row scrolls proposal to that section).

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — add the `ProposalPreviewPane`
  widget (near `_InlineSectionMinimap`, line 882) and a
  `_mount_config_with_preview(...)` helper used by the config step
  (`_actions_show_config`, line 6770); add an App-level
  `on_section_minimap_section_selected` handler and a Tab→focus-minimap action
  for the Actions tab; add the ratio-cycle binding + CSS width classes for the
  two panes (CSS region ~line 2871, alongside `#dashboard_split`).
- `.aitask-scripts/lib/shortcut_scopes.py` — register the new ratio-cycle
  keybinding (per `aidocs/framework/tui_conventions.md`); surface it in the
  Actions footer.

## Reference Files for Patterns
- `_InlineSectionMinimap` (`brainstorm_app.py:882`) — Tab-binding-free
  `SectionMinimap` subclass; `.populate(parsed)`.
- `NodeDetailModal` proposal tab + `on_section_minimap_section_selected`
  (`brainstorm_app.py:954-1058`) — the canonical mount order (minimap mounted
  `before` the `Markdown` inside a `VerticalScroll`) and the scroll-to-section
  math (minimap-height correction against `max_scroll_y`, using
  `estimate_section_y`). The new App-level handler mirrors this.
- `section_viewer.py:269` (`SectionMinimap`, `estimate_section_y`,
  `SectionMinimap.SectionSelected`).
- `parse_sections` (`brainstorm/brainstorm_sections.py:77`).
- Split-pane precedent: `Horizontal#dashboard_split` (40%/60%) + its CSS
  (`brainstorm_app.py:2871`).

## Implementation Plan
1. **`ProposalPreviewPane` widget:** a container holding a `VerticalScroll`
   with an inline minimap mounted `before` a `Markdown`. API:
   `populate(proposal_text)` (parse sections → fill markdown + minimap; hide
   minimap when no sections) and `scroll_to_section(name)` reusing
   `estimate_section_y` math from NodeDetailModal lines 1038-1057.
2. **`_mount_config_with_preview(container, left_builder, proposal_text)`:**
   lays out the config step as a side-by-side split (a `Horizontal` with a
   left `VerticalScroll` and the `ProposalPreviewPane` on the right). Calls
   `left_builder(left_container)` to mount the op-specific inputs **verbatim**
   so the existing collectors in `_actions_collect_config` keep resolving them
   (they query the outer `#actions_content` recursively). IMPORTANT: the
   preview pane must add NO extra `TextArea`/`CycleField`/`RadioSet` — only a
   `Markdown` + minimap `VerticalScroll` — so explore's `query_one(TextArea)` /
   `query_one(CycleField)` stay unambiguous.
3. **Adjustable split ratio:** App-level binding (registered in
   `shortcut_scopes.py`) that cycles input-wide / 50-50 / proposal-wide by
   swapping CSS width classes on the two panes. Active only while a
   preview-bearing config step is mounted.
4. **Reflow-stable scroll:** before a ratio change, capture the top visible
   source line (`scroll.scroll_offset.y` → line ratio via `text.count("\n")`);
   after the markdown reflows at the new width (`call_after_refresh`), scroll so
   that same line is back at the top.
5. **App-level section handler + Tab focus:** mirror NodeDetailModal's
   `on_section_minimap_section_selected` (route the Actions-tab minimap's
   `SectionSelected` to the active pane) and `action_focus_minimap`
   (Tab: input → minimap).

## Verification Steps
- Run `bash tests/...` for any brainstorm app tests touched; `shellcheck`
  N/A (Python).
- Launch `ait brainstorm`; mount the pane via the internal harness (or wait for
  t945_2 to exercise it). Confirm: minimap rows navigate and scroll the
  proposal; Tab moves focus input↔minimap; the ratio-cycle key cycles three
  widths; after each ratio change the previously-top line stays at the top.
