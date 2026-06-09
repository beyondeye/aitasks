---
Task: t946_nodedetailmodal_separate_minimap_pane.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# t946 — Move NodeDetailModal's section minimap into a fixed sibling pane

## Context

`NodeDetailModal` (`.aitask-scripts/brainstorm/brainstorm_app.py`) is the node-detail
dialog in `ait brainstorm`. Its **Proposal** and **Plan** tabs each mount an
`_InlineSectionMinimap` *inside* the tab's `VerticalScroll`, before the `Markdown`
(`on_mount`, proposal `:1157-1160`, plan `:1171-1174`). Two consequences:

1. The minimap **scrolls out of view** as the markdown scrolls (it's inside the
   scroll container).
2. `on_section_minimap_section_selected` (`:1176-1220`) compensates with a crude
   `estimate_section_y` + `±minimap_height` correction that **slightly overshoots**.

This is the last inline-minimap site. The sibling task **t945_2** already performed
the identical refactor on the explore wizard's `ProposalPreviewPane` (same file,
`:954-1067`), converging on the proven `SectionViewerScreen` layout
(`lib/section_viewer.py:474`): a fixed-width minimap **sibling** beside a scrollable
`SectionAwareMarkdown` whose `request_scroll_to_section` scrolls to the section's
**actual rendered heading** (exact, no overshoot, no line-ratio math). This task
applies that same refactor to `NodeDetailModal`'s two tabs. The Metadata tab is
untouched.

Reference: archived plan `aiplans/archived/p945/p945_2_wire_preview_into_explore_wizard.md`
(Part B), and the in-file `ProposalPreviewPane` it produced.

## Approach

Mirror `ProposalPreviewPane` / `SectionViewerScreen`: each tab becomes a
`Horizontal` holding a fixed-width `_InlineSectionMinimap` sibling + a
`SectionAwareMarkdown`. The minimap is **composed once** (not mounted in `on_mount`)
and shown/hidden via `display`; section navigation delegates to
`SectionAwareMarkdown.request_scroll_to_section`.

`_InlineSectionMinimap` (`:886`, no-Tab subclass) and the modal's `Tab` routing are
**kept as-is** — the minimap keeps the same ids (`proposal_minimap` / `plan_minimap`),
so `action_focus_minimap` (`:1222-1247`) needs no change. `action_fullscreen_view`
(`v`) and `action_export` (`e`) read `self._proposal_text` / `self._plan_text`,
which are still set — unaffected.

### 1. `compose()` — proposal/plan tabs (`brainstorm_app.py:1100-1109`)

Replace each tab's `VerticalScroll(Markdown(...), id="..._scroll")` with a
`Horizontal` containing a fixed minimap + a `SectionAwareMarkdown`:

```python
with TabPane("Proposal", id="tab_proposal"):
    with Horizontal(id="proposal_pane"):
        yield _InlineSectionMinimap.cls()(
            id="proposal_minimap", classes="node_detail_minimap"
        )
        yield SectionAwareMarkdown(id="proposal_content")
with TabPane("Plan", id="tab_plan"):
    with Horizontal(id="plan_pane"):
        yield _InlineSectionMinimap.cls()(
            id="plan_minimap", classes="node_detail_minimap"
        )
        yield SectionAwareMarkdown(id="plan_content")
```

Add a lazy import at the top of `compose()` (matching `ProposalPreviewPane.compose`,
`:1004`): `from section_viewer import SectionAwareMarkdown`. The Metadata tab's
`VerticalScroll(Static(id="metadata_content"), id="metadata_scroll")` is unchanged.

### 2. `on_mount()` — proposal/plan loading (`brainstorm_app.py:1147-1174`)

Drop the inline `mount(minimap, before="#..._content")`. Instead update the
`SectionAwareMarkdown` and populate/toggle the already-composed minimap (mirroring
`ProposalPreviewPane.populate`, `:1015-1032`):

```python
from section_viewer import SectionAwareMarkdown
# --- Proposal tab ---
try:
    proposal = read_proposal(self.session_path, self.node_id)
except Exception:
    proposal = "*No proposal found.*"
self._proposal_text = proposal
parsed_proposal = parse_sections(proposal)
prop_content = self.query_one("#proposal_content", SectionAwareMarkdown)
prop_content.update_content(proposal, parsed_proposal)
prop_minimap = self.query_one("#proposal_minimap")
prop_minimap.populate(parsed_proposal)   # clears stale rows; none when no sections
if parsed_proposal.sections:
    self._proposal_parsed = parsed_proposal
    prop_minimap.display = True
else:
    self._proposal_parsed = None
    prop_minimap.display = False
```

Same shape for the Plan tab using `read_plan` (keep the existing `None → "*No plan
generated.*"` fallback), `#plan_content`, `#plan_minimap`, `self._plan_parsed`.
Note: `populate()` is always called (it clears rows and adds one per section), then
`display` is toggled — this matches the t945_2 deviation note that fixed a stale-rows
bug on re-populate.

### 3. `on_section_minimap_section_selected()` (`brainstorm_app.py:1176-1220`)

Rewrite to delegate to the selected minimap's content widget — deleting the
`estimate_section_y` import and the `minimap_height` / `body_scroll_range` math:

```python
def on_section_minimap_section_selected(self, event) -> None:
    """Scroll the selected tab's content to the chosen section's heading."""
    from section_viewer import SectionAwareMarkdown
    minimap_id = event.control.id
    if minimap_id == "proposal_minimap":
        parsed, content_id = self._proposal_parsed, "#proposal_content"
    elif minimap_id == "plan_minimap":
        parsed, content_id = self._plan_parsed, "#plan_content"
    else:
        return
    if parsed is None:
        return
    content = self.query_one(content_id, SectionAwareMarkdown)
    content.request_scroll_to_section(event.section_name)
    content.focus()   # SectionAwareMarkdown is a VerticalScroll → up/down scroll
    event.stop()
```

`content.focus()` preserves the existing post-select behavior (focus the scrollable
so arrow keys scroll); `Tab` still returns to the minimap via `action_focus_minimap`.

### 4. `action_focus_minimap()` (`brainstorm_app.py:1222-1247`) — unchanged

Queries `#proposal_minimap` / `#plan_minimap` and calls `focus_first_row()`, which
is a safe no-op when the minimap has no rows (`section_viewer.py:333-340`). Minimaps
now exist from `compose` (display:none when empty) but remain in the DOM, so the
`query` still resolves. No edit needed.

### 5. CSS (`brainstorm_app.py:3252`)

`#proposal_scroll` / `#plan_scroll` no longer exist. Narrow the existing shared rule
to Metadata only and add rules for the new layout (mirroring
`SectionViewerScreen #sv_minimap` `:509-514` and `ProposalPreviewPane` CSS `:980-996`):

```css
#metadata_scroll {
    height: 1fr;
    padding: 1 2;
}
#proposal_pane, #plan_pane {
    height: 1fr;
}
.node_detail_minimap {
    width: 32;
    max-width: 32;
    height: 1fr;
    max-height: 100%;
}
#proposal_content, #plan_content {
    width: 1fr;
    height: 1fr;
    padding: 0 1;
}
```

The `.node_detail_minimap` class (id/class specificity) overrides
`SectionMinimap.DEFAULT_CSS`'s `height: auto; max-height: 12` so the minimap fills
the column full-height, exactly as `#sv_minimap` does for the fullscreen viewer.

### 6. Pilot test — `tests/test_brainstorm_node_detail_minimap.py` (new)

Add a focused pilot test mirroring `tests/test_brainstorm_operation_detail_screen.py`'s
harness (host `App` pushes the modal against a synthesized session dir). The sibling
refactor (t945_2) added a pilot test for `ProposalPreviewPane`; this gives the
NodeDetailModal refactor equivalent structural coverage. Fixtures are trivial — write
`br_nodes/<id>.yaml`, `br_proposals/<id>.md`, `br_plans/<id>_plan.md` (dir constants
`NODES_DIR="br_nodes"`, `PROPOSALS_DIR="br_proposals"`, `PLANS_DIR="br_plans"` from
`brainstorm_dag.py:22-24`). Drive via `App.run_test()` Pilot and assert:

- Proposal/Plan content widgets are `SectionAwareMarkdown` siblings of the minimaps
  inside `#proposal_pane` / `#plan_pane` (no `#proposal_scroll` / `#plan_scroll`).
- With a multi-section proposal, `#proposal_minimap` is present and `display is True`
  with one `SectionRow` per section.
- With a no-section / empty body, the corresponding minimap has `display is False`.
- Selecting a section (post a `SectionMinimap.SectionSelected` or invoke the handler)
  routes through `request_scroll_to_section` without raising (the async TOC scroll
  itself stays manual-verification).

## Verification

- `python -m py_compile .aitask-scripts/brainstorm/brainstorm_app.py`
- `python tests/test_brainstorm_node_detail_minimap.py` (new) passes.
- `python tests/test_brainstorm_proposal_preview.py` still passes (shared file; no
  intended change to `ProposalPreviewPane`).
- Manual (`ait brainstorm`): open a node detail (Enter), Proposal and Plan tabs —
  the minimap stays **fixed/visible** while content scrolls; selecting a minimap row
  scrolls the heading to the top **without overshooting**; `Tab` still focuses the
  minimap; `v` fullscreen and `e` export still work.

## Risk

### Code-health risk: low
- Converges a bespoke inline-minimap + scroll-math site onto the already-proven,
  already-tested `SectionViewerScreen` / `SectionAwareMarkdown` pattern (less code,
  not more) — the exact refactor t945_2 landed on the sibling `ProposalPreviewPane`
  in the same file. · severity: low · → mitigation: in-task — new pilot test +
  manual verification; `_InlineSectionMinimap`, the `Tab` routing, and the minimap
  ids are kept identical so `action_focus_minimap` is untouched.

### Goal-achievement risk: low
- The separate-pane layout + exact-heading scroll are exactly what the task asks for
  and are already shipping in `SectionViewerScreen` and (post-t945_2)
  `ProposalPreviewPane`. The only runtime-only unknown (async TOC scroll landing
  pixel-exact inside the modal) is already handled by `SectionAwareMarkdown`'s
  `_apply_pending_scroll` settle loop and is covered by the manual verification step.

_No before/after mitigation tasks: risk is low and bounded to one modal; the pilot
test + manual verification cover it._

## Reference to parent workflow
On completion follow task-workflow Step 8 (review) → Step 9 (archival).

## Final Implementation Notes
- **Actual work done:** Refactored `NodeDetailModal` (`brainstorm_app.py`) exactly
  per the plan. `compose()` now lays out the Proposal and Plan tabs as a
  `Horizontal` pane (`#proposal_pane` / `#plan_pane`) holding a fixed-width
  `_InlineSectionMinimap` sibling (`#proposal_minimap` / `#plan_minimap`, class
  `node_detail_minimap`) + a `SectionAwareMarkdown` content widget. `on_mount()`
  drops the inline `mount(minimap, before=…)` and instead `update_content()`s the
  markdown + `populate()`s the minimap, toggling `display` when there are no
  sections. `on_section_minimap_section_selected()` now delegates to
  `SectionAwareMarkdown.request_scroll_to_section` (deleting the
  `estimate_section_y` import + `minimap_height`/`body_scroll_range` overshoot
  math). CSS: narrowed the shared scroll rule to `#metadata_scroll` and added the
  pane / fixed-minimap-column / content rules. Added pilot test
  `tests/test_brainstorm_node_detail_minimap.py` (3 tests).
- **Deviations from plan:** None. Implemented as designed.
- **Issues encountered:** None.
- **Key decisions:** Kept `content.focus()` after a section selection (preserves the
  pre-refactor behavior of focusing the scrollable so up/down scrolls the content;
  `Tab` returns to the minimap via the unchanged `action_focus_minimap`). The pilot
  test asserts delegation via `SectionAwareMarkdown._active_scroll_section` rather
  than the async TOC-anchor scroll landing pixel (that stays manual-verification).
- **Upstream defects identified:** None
- **Tests:** `python -m py_compile` clean; new pilot test 3/3 pass; sibling
  `tests/test_brainstorm_proposal_preview.py` 12/12 still pass; no stale
  `proposal_scroll` / `plan_scroll` / `estimate_section_y` references remain.
