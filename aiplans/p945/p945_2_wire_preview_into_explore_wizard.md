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

Second child of t945: show the selected base node's proposal side-by-side with
the Exploration Mandate input in the explore wizard config step, reusing the
t945_1 component.

**Part A (done — original wiring):** `_config_explore_no_node`
(`brainstorm_app.py:7048`) was refactored to lay out input-left /
proposal-preview-right via `_mount_config_with_preview`, with the mandate
`TextArea`, `CycleField`, and `Next ▶` built in a `left_builder` closure and the
base node's proposal (`read_proposal`) shown in the right pane. Collector
invariance verified.

**Part B (this revision — review feedback):** Live testing surfaced three issues
in the underlying preview component delivered by t945_1:
1. The minimap is mounted *inside* the scrollable pane, so it scrolls out of
   view when the proposal scrolls. It should be a **fixed sibling pane** that
   stays visible — "in all places where the minimap is currently inlined."
2. The ratio-cycle shortcut (`ctrl+b`) **does not fire** — it collides with a
   preexisting Textual binding.
3. Clicking a minimap row **overshoots** the scroll target slightly.

Per the scope decision, **t945_2 fixes these for the explore preview pane
(`ProposalPreviewPane`)**; the identical refactor of `NodeDetailModal`'s
Proposal/Plan tabs is split into a **separate follow-up task** (created during
implementation) to keep this task focused. Fixing `ProposalPreviewPane` also
benefits t945_3 (decompose), which reuses the same component.

## Key insight — reuse the proven fullscreen pattern

`SectionViewerScreen` (`lib/section_viewer.py:474`) already lays a minimap beside
scrollable content the right way: a `Horizontal` with a fixed-width
`SectionMinimap` sibling + a `SectionAwareMarkdown` content pane. Crucially,
`SectionAwareMarkdown.scroll_to_section` (`section_viewer.py:448`) scrolls to the
section's **actual rendered heading** (via Textual's table-of-contents anchors,
with a settle loop in `_apply_pending_scroll`) instead of the crude
`estimate_section_y` line-ratio math the inline panes use. Adopting it:
- makes the minimap a fixed sibling (fixes #1),
- **fixes the overshoot for free** (#3) — exact heading anchors, no
  `±minimap_height` correction,
- deletes the duplicated scroll math in `ProposalPreviewPane`.

## Implementation steps (Part B)

### 1. Refactor `ProposalPreviewPane` (`brainstorm_app.py:908-1003`)
Change the base class from `VerticalScroll` to **`Horizontal`** and compose a
fixed minimap sibling + a scrollable `SectionAwareMarkdown`:

- `compose()`: lazily import and yield `_InlineSectionMinimap.cls()(classes="preview_proposal_minimap")`
  then `SectionAwareMarkdown(id="preview_proposal_content")` (lazy
  `from section_viewer import SectionAwareMarkdown`, matching the existing
  lazy-import pattern). Keep `_InlineSectionMinimap` (no Tab binding) so the
  existing app-level Tab focus routing (`_focus_preview_minimap`) is unchanged.
- `populate(text)`: `parsed = parse_sections(text)`;
  `content.update_content(text, parsed)`; if `parsed.sections`,
  `minimap.populate(parsed)` and `minimap.display = True`, else
  `minimap.display = False`. (No more mount/remove churn — both children exist
  from `compose`; just toggle `display`.)
- `scroll_to_section(name)`: delegate to
  `content.request_scroll_to_section(name)` (drops the `estimate_section_y` +
  `minimap_height` correction entirely → fixes overshoot).
- `on_ratio_change()`: capture/restore the top source line on the **inner
  `SectionAwareMarkdown`** scroll (it is itself a `VerticalScroll`), not on
  `self`. Same line-ratio capture-before-reflow / restore-after-`call_after_refresh`
  logic, retargeted to the content widget.
- `DEFAULT_CSS`: give the minimap a fixed full-height column, e.g.
  `ProposalPreviewPane > .preview_proposal_minimap { width: 28; max-width: 28; height: 1fr; }`
  and `ProposalPreviewPane > #preview_proposal_content { width: 1fr; }`. Drop the
  old `border-left/padding` block (or move to the content side) as appropriate.

The app-level message handler `on_section_minimap_section_selected`
(`brainstorm_app.py:7010`, gated on `.has_class("preview_proposal_minimap")`) and
`_focus_preview_minimap` (`:7026`) need no logic change — the minimap is still a
descendant with the same class.

### 2. Fix the ratio-cycle keybinding collision
- Change `Binding("ctrl+b", "cycle_preview_ratio", "Preview width")`
  (`brainstorm_app.py:3387`) to a combo Textual/TextArea does not consume —
  **`ctrl+shift+b`** (consistent with the existing `ctrl+shift+*` retry
  bindings; a shift+ctrl letter is not swallowed by the focused mandate
  `TextArea`). Update the two references to the old key: the CSS-region comment
  at `:2984` and the `action_cycle_preview_ratio` docstring at `:6994`. The
  `check_action`/`on_key` mapping keys off the **action name**
  (`cycle_preview_ratio`, `:3519`), so no change there.
- Verify the new key fires while the mandate `TextArea` is focused (manual).

### 3. Update the pilot test (`tests/test_brainstorm_proposal_preview.py`)
The test drives `ProposalPreviewPane` directly. Update its structural
assumptions to the new layout: content is a `SectionAwareMarkdown`
(`#preview_proposal_content`) sibling of the minimap; the minimap is present
from `compose` and toggled via `display` (not mounted/removed); section
navigation now routes through `request_scroll_to_section`. Keep coverage for
populate / minimap-rows / ratio-class toggling; adapt the scroll-to-section and
reflow assertions to the delegated `SectionAwareMarkdown` behavior (the
TOC-anchor scroll is async — assert via the same `request_scroll_to_section` +
`call_after_refresh` settle the widget already supports, or assert the target
section was requested).

### 4. Create the NodeDetailModal follow-up task (post-approval, Step 7)
Create a standalone task: *"Refactor NodeDetailModal Proposal/Plan tabs to the
separate-pane minimap layout"*. Description captures the same design: wrap each
tab's content in a `Horizontal` with a fixed `SectionMinimap` sibling +
`SectionAwareMarkdown`, drop the inline `mount(before=...)` and the
`estimate_section_y`/`minimap_height` correction in
`on_section_minimap_section_selected` (`brainstorm_app.py:1111-1155`), keep
`action_focus_minimap`. Reference this plan and `SectionViewerScreen` as the
model. (labels: `ait_brainstorm`; issue_type: refactor.)

## Verification
- Launch `ait brainstorm`; explore → select a node → config step. Confirm:
  - the minimap stays **fixed/visible** while scrolling the proposal markdown;
  - clicking/activating a minimap row scrolls the proposal so the section's
    heading lands at the top **without overshooting**;
  - `ctrl+shift+b` cycles the split width (balanced → proposal-wide →
    input-wide) **even while the mandate input is focused**, and the previously
    top line stays put across the reflow;
  - submitting the mandate (`Next ▶`) proceeds to confirm exactly as before, and
    `_actions_collect_config` still collects mandate + parallel without
    `query_one` ambiguity.
- `python tests/test_brainstorm_proposal_preview.py` passes.
- `python -m py_compile .aitask-scripts/brainstorm/brainstorm_app.py`.

## Risk

### Code-health risk: medium
- Part B rewrites a **shared, already-tested widget** (`ProposalPreviewPane`,
  reused by t945_3) and changes its base class + public child structure, and
  rewrites its pilot test. · severity: medium · → mitigation: handled in-task —
  the refactor *converges on* the proven `SectionViewerScreen` /
  `SectionAwareMarkdown` pattern (less bespoke code, not more), the pilot test
  is updated in the same commit, and the explore flow is manually verified.
- Keybinding change touches a shared `BINDINGS` entry + two stale references. ·
  severity: low · → mitigation: grep-verified the three sites; action name
  (the real coupling point) is unchanged.

### Goal-achievement risk: low
- None material. The separate-pane layout and exact-heading scroll are exactly
  what the user asked for and are already proven in `SectionViewerScreen`; the
  one runtime-only unknown (does `ctrl+shift+b` reach the app past the focused
  `TextArea`) is called out as an explicit manual verification step.

_No separate before/after mitigation tasks: the medium code-health risk is
bounded and covered by the updated pilot test + manual verification; the
NodeDetailModal blast radius is removed from this task by the split into a
dedicated follow-up. No spike/characterization task warranted._

## Reference to parent workflow
On completion follow task-workflow Step 8 (review) → Step 9 (archival).
