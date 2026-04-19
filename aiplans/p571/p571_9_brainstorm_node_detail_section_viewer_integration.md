---
Task: t571_9_brainstorm_node_detail_section_viewer_integration.md
Parent Task: aitasks/t571_more_structured_brainstorming_created_plan.md
Sibling Tasks: aitasks/t571/t571_5_*.md, aitasks/t571/t571_6_*.md, aitasks/t571/t571_7_*.md, aitasks/t571/t571_8_*.md, aitasks/t571/t571_10_*.md
Archived Sibling Plans: aiplans/archived/p571/p571_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t571_9 — Brainstorm NodeDetailModal Section Viewer Integration

<!-- section: context [dimensions: motivation, integration] -->

## Context

Integrate the shared `.aitask-scripts/lib/section_viewer.py` module (from t571_5) into the **brainstorm** TUI's `NodeDetailModal`. Both the Proposal tab and the Plan tab get their own independent `SectionMinimap` above the existing Markdown widget.

This closes the most important loop: brainstorming is where users actually author and iterate on sectioned proposals/plans, so seeing sections at a glance with their dimension tags makes DAG exploration substantially more ergonomic.

**Depends on t571_5.** Do NOT start until `.aitask-scripts/lib/section_viewer.py` exists.

<!-- /section: context -->

<!-- section: files_and_lines [dimensions: deliverables] -->

## Files and Line References

- `.aitask-scripts/brainstorm/brainstorm_app.py`:
  - `parse_sections` already imported at line 49
  - sys.path inserts at lines 11–12 cover both `parent.parent` and `parent.parent/"lib"` — no sys.path changes needed
  - `NodeDetailModal` class at line 251
  - Tab structure at lines 266–281: `#tab_metadata`, `#tab_proposal` (contains `Markdown#proposal_content`), `#tab_plan` (contains `Markdown#plan_content`)
  - `on_mount()` at lines 287–329 — loads proposal/plan content into those Markdowns

<!-- /section: files_and_lines -->

<!-- section: on_mount_enhancement [dimensions: integration, widget-design] -->

## 1. `NodeDetailModal.on_mount()` — mount per-tab minimaps

After loading proposal content (`Markdown(id="proposal_content").update(proposal)`):

```python
from section_viewer import SectionMinimap
parsed = parse_sections(proposal)
if parsed.sections:
    self._proposal_parsed = parsed
    self._proposal_text = proposal
    prop_scroll = self.query_one("#tab_proposal VerticalScroll", VerticalScroll)
    minimap = SectionMinimap(id="proposal_minimap")
    prop_scroll.mount(minimap, before="#proposal_content")
    minimap.populate(parsed)
```

Same pattern for plan content with id `plan_minimap`, and store `self._plan_parsed`, `self._plan_text`.

Initialize `self._proposal_parsed = None`, `self._proposal_text = ""`, `self._plan_parsed = None`, `self._plan_text = ""` in `__init__`.

<!-- /section: on_mount_enhancement -->

<!-- section: section_select_routing [dimensions: integration, scroll-estimation] -->

## 2. Route `SectionSelected` by minimap id

```python
def on_section_minimap_section_selected(self, event) -> None:
    from section_viewer import estimate_section_y
    minimap_id = event.control.id
    if minimap_id == "proposal_minimap":
        parsed, text, scroll_sel = self._proposal_parsed, self._proposal_text, "#tab_proposal VerticalScroll"
    elif minimap_id == "plan_minimap":
        parsed, text, scroll_sel = self._plan_parsed, self._plan_text, "#tab_plan VerticalScroll"
    else:
        return
    if parsed is None:
        return
    scroll = self.query_one(scroll_sel, VerticalScroll)
    total = text.count('\n') + 1
    y = estimate_section_y(parsed, event.section_name, total, scroll.virtual_size.height)
    if y is not None:
        scroll.scroll_to(y=y, animate=False)  # nav, not animation — matches t571_11 fix; see section_viewer.py scroll_to_section
    event.stop()
```

<!-- /section: section_select_routing -->

<!-- section: focus_routing [dimensions: focus-management, keybinding] -->

## 3. Tab focus contract — both directions

Minimap→content side:
```python
def on_section_minimap_toggle_focus(self, event) -> None:
    if event.control.id == "proposal_minimap":
        self.query_one("#proposal_content", Markdown).focus()
    elif event.control.id == "plan_minimap":
        self.query_one("#plan_content", Markdown).focus()
    event.stop()
```

Content→minimap side (screen-level Tab binding on `NodeDetailModal`):
```python
BINDINGS = [..., Binding("tab", "focus_minimap", "Minimap")]

def action_focus_minimap(self) -> None:
    from textual.actions import SkipAction
    tabbed = self.query_one(TabbedContent)
    focused = self.screen.focused
    if tabbed.active == "tab_proposal":
        md = self.query_one("#proposal_content", Markdown)
        mm_sel = "#proposal_minimap"
    elif tabbed.active == "tab_plan":
        md = self.query_one("#plan_content", Markdown)
        mm_sel = "#plan_minimap"
    else:
        raise SkipAction()
    if focused is not md:
        raise SkipAction()
    minimaps = self.query(mm_sel)
    if not minimaps:
        raise SkipAction()
    minimaps.first().focus_first_row()
```

<!-- /section: focus_routing -->

<!-- section: fullscreen_binding [dimensions: keybinding, integration] -->

## 4. `V` → full-screen `SectionViewerScreen` (shared key)

**Cross-TUI alignment:** `V` (uppercase / `shift+v`) is the shared fullscreen-viewer key across board (t571_10), codebrowser (t571_8), and brainstorm (this task). See p571_10's "Cross-TUI Keybinding Alignment" section.

Add to `NodeDetailModal.BINDINGS`:

```python
Binding("V", "fullscreen_plan", "Fullscreen plan"),
```

Dispatch to the currently-active tab:

```python
def action_fullscreen_plan(self) -> None:
    tabbed = self.query_one(TabbedContent)
    if tabbed.active == "tab_proposal":
        content = self._proposal_text
        title = f"Proposal: {self._node_name}"
    elif tabbed.active == "tab_plan":
        content = self._plan_text
        title = f"Plan: {self._node_name}"
    else:
        self.notify("Fullscreen viewer only works on Proposal or Plan tab", severity="warning")
        return
    if content:
        from section_viewer import SectionViewerScreen
        self.app.push_screen(SectionViewerScreen(content, title=title))
    else:
        self.notify("No content on this tab", severity="warning")
```

(Stores `self._node_name` as whatever human-readable name is already available on the modal — usually the DAG node title. Adjust to match the existing attribute.)

<!-- /section: fullscreen_binding -->

<!-- section: graceful_fallback [dimensions: robustness] -->

## 5. Graceful fallback

If a node's proposal or plan has no section markers, skip mounting the minimap for that tab. The tab's `VerticalScroll` holds only the Markdown, same as before. Tab key on that Markdown raises `SkipAction` → Textual's default tab-nav runs (e.g. cycle through visible focus targets).

<!-- /section: graceful_fallback -->

<!-- section: verification [dimensions: testing] -->

## Verification

Fixture content: the t571_5 plan (`aiplans/p571/p571_5_shared_section_viewer_tui_integration.md`) has ~11 sections across multiple dimensions. Copy its body (or craft a similar node proposal) into a brainstorm DAG node for testing, then:

1. `ait brainstorm` on the DAG, open `NodeDetailModal` on the test node
2. Switch to the Proposal tab → minimap appears above the markdown; dimension tags visible
3. Tab → focus moves to the Proposal Markdown. Tab again → focus returns to the last-highlighted row
4. Up/Down on minimap → focus cycles through rows, no content scroll
5. Enter on a row → proposal scrolls to that section
6. Switch to the Plan tab → independent minimap state; repeat Tab/Arrow/Enter checks
7. Switch back to Proposal tab → minimap state (last-highlighted row) preserved in-session
8. Open a node with no section markers → no minimap on the respective tab; Tab navigation unaffected
9. Press `V` (uppercase / `shift+v`) on the Proposal tab → `SectionViewerScreen` opens full-screen with proposal content. Escape closes.
10. Switch to the Plan tab and press `V` → fullscreen viewer opens with plan content.
11. Press `V` on the Metadata tab → notification "Fullscreen viewer only works on Proposal or Plan tab", no crash.

<!-- /section: verification -->

<!-- section: post_implementation [dimensions: workflow] -->

## Step 9: Post-Implementation

Follow Step 9 from the shared workflow for commit, archival, and push.

<!-- /section: post_implementation -->
