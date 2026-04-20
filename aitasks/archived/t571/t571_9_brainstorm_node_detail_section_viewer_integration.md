---
priority: high
effort: medium
depends: [5]
issue_type: refactor
status: Done
labels: [brainstorming, ait_brainstorm, ui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-19 08:47
updated_at: 2026-04-20 10:26
completed_at: 2026-04-20 10:26
---

<!-- section: context [dimensions: motivation, integration] -->

## Context

Sibling task of t571_5 (shared section viewer library). This task integrates that library into the **brainstorm** TUI: add section minimaps to the Proposal and Plan tabs of `NodeDetailModal` so users exploring the DAG can see the dimensional structure of each node's proposal and plan.

**Depends on t571_5.** Do not start until `.aitask-scripts/lib/section_viewer.py` exists.

<!-- /section: context -->

<!-- section: files_to_modify [dimensions: deliverables] -->

## Key Files to Modify

- **MODIFY** `.aitask-scripts/brainstorm/brainstorm_app.py` — `NodeDetailModal` at line 251: add `SectionMinimap` above `#proposal_content` and `#plan_content` Markdown widgets when content has sections; handle `SectionSelected` to scroll the containing `VerticalScroll`; handle `ToggleFocus` to focus the companion Markdown; add a screen-level `Binding("tab", "focus_minimap", ...)` guarded to the active tab's Markdown

<!-- /section: files_to_modify -->

<!-- section: reference_patterns [dimensions: patterns] -->

## Reference Files for Patterns

- `.aitask-scripts/brainstorm/brainstorm_app.py:49` — `parse_sections` is already imported here (unused); reuse
- `.aitask-scripts/brainstorm/brainstorm_app.py:11-12` — sys.path already inserts `parent.parent` AND `parent.parent/"lib"`, so both brainstorm_sections and section_viewer imports work without further setup
- `.aitask-scripts/brainstorm/brainstorm_app.py:266-281` — NodeDetailModal tab structure: Metadata / Proposal / Plan tabs with widget IDs `proposal_content` and `plan_content`
- `.aitask-scripts/lib/section_viewer.py` (from t571_5) — imports: `from section_viewer import SectionMinimap`

<!-- /section: reference_patterns -->

<!-- section: node_detail_modal_enhancement [dimensions: integration, widget-design] -->

## 1. `NodeDetailModal.on_mount()` — mount minimaps in tabs

After loading proposal content (around line 305, `Markdown(id="proposal_content").update(proposal)`):
```python
from section_viewer import SectionMinimap
parsed_proposal = parse_sections(proposal)
if parsed_proposal.sections:
    prop_scroll = self.query_one("#tab_proposal VerticalScroll", VerticalScroll)
    minimap = SectionMinimap(id="proposal_minimap")
    prop_scroll.mount(minimap, before="#proposal_content")
    minimap.populate(parsed_proposal)
    self._proposal_parsed = parsed_proposal
```

Same pattern for plan tab with id `plan_minimap` and `self._plan_parsed`.

<!-- /section: node_detail_modal_enhancement -->

<!-- section: section_select_routing [dimensions: integration, scroll-estimation] -->

## 2. Handle `SectionMinimap.SectionSelected`

```python
def on_section_minimap_section_selected(self, event) -> None:
    minimap_id = event.control.id
    if minimap_id == "proposal_minimap":
        parsed = self._proposal_parsed
        scroll = self.query_one("#tab_proposal VerticalScroll", VerticalScroll)
        total = <proposal_text>.count('\n') + 1
    else:  # plan_minimap
        parsed = self._plan_parsed
        scroll = self.query_one("#tab_plan VerticalScroll", VerticalScroll)
        total = <plan_text>.count('\n') + 1
    from section_viewer import estimate_section_y
    y = estimate_section_y(parsed, event.section_name, total, scroll.virtual_size.height)
    if y is not None:
        scroll.scroll_to(y=y, animate=True)
    event.stop()
```

Cache proposal_text and plan_text on the modal instance during `on_mount()` so this handler can recompute total lines without re-reading files.

<!-- /section: section_select_routing -->

<!-- section: focus_routing [dimensions: focus-management, keybinding] -->

## 3. Focus routing — Tab between minimap and markdown per tab

Per the keyboard contract defined in t571_5:

- `on_section_minimap_toggle_focus(event)` → look at `event.control.id`; if `proposal_minimap` focus `#proposal_content`, if `plan_minimap` focus `#plan_content`; `event.stop()`
- Add `NodeDetailModal.BINDINGS += [Binding("tab", "focus_minimap", "Minimap")]`
- `action_focus_minimap()`:
  - Use `TabbedContent.active` to determine which tab is active
  - Scope guard: `self.screen.focused` should be the active tab's Markdown; if not, `raise SkipAction()`
  - Else focus the matching minimap via `.focus_first_row()`

<!-- /section: focus_routing -->

<!-- section: graceful_fallback [dimensions: robustness] -->

## 4. Graceful fallback

When a node's proposal or plan has no section markers, skip mounting the minimap for that tab. The tab's VerticalScroll then holds only the Markdown, same as before. Tab key on that Markdown → raises `SkipAction` from `action_focus_minimap`, so Textual's default tab-nav still works.

<!-- /section: graceful_fallback -->

<!-- section: verification [dimensions: testing] -->

## Verification Steps

1. Open `ait brainstorm` on a DAG that has at least one node whose proposal or plan contains `<!-- section: ... [dimensions: ...] -->` markers (the new plans for t571_5 and siblings can be used as test fixtures if copied into a node)
2. Open a `NodeDetailModal` on that node
3. Switch to the Proposal tab → verify minimap appears above the markdown with section names + dimension tags
4. Tab → focus moves to proposal markdown. Tab again → focus returns to last-highlighted minimap row
5. Up/Down → focus moves between rows without content scroll
6. Enter on a row → proposal scrolls to that section
7. Switch to Plan tab → same behavior with the plan content's minimap (independent state)
8. Node with no section markers → no minimap, Markdown renders normally, Tab still navigates the modal cleanly

<!-- /section: verification -->

<!-- section: post_implementation [dimensions: workflow] -->

## Step 9: Post-Implementation

Follow Step 9 from the shared workflow for commit, archival, and push.

<!-- /section: post_implementation -->
