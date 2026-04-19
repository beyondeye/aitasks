---
priority: high
effort: medium
depends: [5]
issue_type: refactor
status: Ready
labels: [brainstorming, ait_brainstorm, ui, codebrowser]
created_at: 2026-04-19 08:46
updated_at: 2026-04-19 08:46
---

<!-- section: context [dimensions: motivation, integration] -->

## Context

Sibling task of t571_5 (shared section viewer library). This task integrates that library into the **codebrowser** TUI: add a section minimap to the detail pane, a full-screen `SectionViewerScreen` bound to `p`, and an optional `plan_sections` field on `TaskDetailContent`.

**Depends on t571_5.** Do not start until `.aitask-scripts/lib/section_viewer.py` exists.

<!-- /section: context -->

<!-- section: files_to_modify [dimensions: deliverables] -->

## Key Files to Modify

- **MODIFY** `.aitask-scripts/codebrowser/detail_pane.py` — mount `SectionMinimap(id="detail_minimap")` above `#detail_markdown` when the plan has sections; handle `SectionSelected` to scroll the outer `VerticalScroll`; handle `ToggleFocus` to focus `#detail_markdown`
- **MODIFY** `.aitask-scripts/codebrowser/codebrowser_app.py` — add `Binding("p", "view_plan", "Plan viewer")` to BINDINGS (lines 235–252); add `action_view_plan()` that pushes `SectionViewerScreen` with the current detail's `plan_content`
- **MODIFY** `.aitask-scripts/codebrowser/annotation_data.py` — extend `TaskDetailContent` (lines 22–28) with `plan_sections: list | None = None`

<!-- /section: files_to_modify -->

<!-- section: reference_patterns [dimensions: patterns] -->

## Reference Files for Patterns

- `.aitask-scripts/codebrowser/history_screen.py` — `action_toggle_focus()` at lines 428–456 as reference for tab focus swapping between minimap and content
- `.aitask-scripts/codebrowser/detail_pane.py` current `update_content()` lines 53–83 (widget IDs: `#detail_header`, `#detail_markdown`, `#detail_placeholder`)
- `.aitask-scripts/lib/section_viewer.py` (from t571_5) — the module this task imports from

<!-- /section: reference_patterns -->

<!-- section: detail_pane_integration [dimensions: integration, widget-design] -->

## 1. `detail_pane.py` — minimap mount

In `update_content()`, after setting `#detail_markdown` content when `detail.has_plan`:

- `from section_viewer import SectionMinimap, estimate_section_y` (sys.path already covers `lib/`)
- `from brainstorm.brainstorm_sections import parse_sections` — section_viewer's self-insert of parent.parent on sys.path is done at import time, so by the time we import `parse_sections`, the path is set
- Parse `detail.plan_content`; if `parsed.sections`, locate-or-create `SectionMinimap(id="detail_minimap")` and mount it **before** `#detail_markdown` inside the outer `VerticalScroll`; call `minimap.populate(parsed)` and cache `parsed` on the instance
- If `parsed.sections` is empty, remove `#detail_minimap` if present
- Store `self._current_detail = detail` as an instance attribute (currently only a local in `update_content()`) so `codebrowser_app.action_view_plan()` can read it

<!-- /section: detail_pane_integration -->

<!-- section: scroll_selected [dimensions: integration, scroll-estimation] -->

## 2. `detail_pane.py` — handle `SectionMinimap.SectionSelected`

Add handler on `DetailPane`:
```python
def on_section_minimap_section_selected(self, event) -> None:
    parsed = self._cached_parsed
    total = self._cached_plan_content.count('\n') + 1
    y = estimate_section_y(parsed, event.section_name, total, self.virtual_size.height)
    if y is not None:
        self.scroll_to(y=y, animate=True)
    event.stop()
```

<!-- /section: scroll_selected -->

<!-- section: focus_routing [dimensions: focus-management, keybinding] -->

## 3. Focus routing — Tab between minimap and markdown

Per the keyboard contract defined in t571_5:

- Tab on `SectionMinimap` emits `ToggleFocus`; `DetailPane.on_section_minimap_toggle_focus()` focuses `#detail_markdown`
- Tab on `#detail_markdown` must return focus to the minimap. Add `DetailPane.BINDINGS = [Binding("tab", "focus_minimap", "Minimap")]` with `action_focus_minimap()` guarded via `self.screen.focused` check — if the focused widget is `#detail_markdown` AND `#detail_minimap` exists, call `minimap.focus_first_row()`; otherwise `raise SkipAction()` to let Textual's default tab-nav handle it

<!-- /section: focus_routing -->

<!-- section: plan_viewer_binding [dimensions: keybinding, integration] -->

## 4. `codebrowser_app.py` — `p` key opens `SectionViewerScreen`

- Add `Binding("p", "view_plan", "Plan viewer")` to BINDINGS list
- `action_view_plan()`:
  ```python
  def action_view_plan(self) -> None:
      detail_pane = self.query_one("#detail_pane", DetailPane)
      detail = getattr(detail_pane, "_current_detail", None)
      if detail and detail.has_plan and detail.plan_content:
          from section_viewer import SectionViewerScreen
          self.push_screen(SectionViewerScreen(
              detail.plan_content,
              title=f"Plan for t{detail.task_id}"))
      else:
          self.notify("No plan available for current task", severity="warning")
  ```

<!-- /section: plan_viewer_binding -->

<!-- section: annotation_data [dimensions: data-model] -->

## 5. `annotation_data.py` — extend `TaskDetailContent`

Add optional field (line 29 onward):
```python
plan_sections: list | None = None  # list[ContentSection] when parsed
```

No import changes needed. Default `None` preserves existing call sites. Currently-unused here; reserved for callers that want to avoid re-parsing.

<!-- /section: annotation_data -->

<!-- section: verification [dimensions: testing] -->

## Verification Steps

1. Open codebrowser, navigate to a file annotated by a task with a sectioned plan (e.g., t571_5's plan at `aiplans/p571/p571_5_shared_section_viewer_tui_integration.md` — it has ~11 sections across multiple dimensions including `keybinding`, `widget-design`, `focus-management`)
2. Press `d` to show the detail pane → verify minimap appears above plan content with all section names + dimension tags
3. Tab → focus moves from minimap to markdown. Tab again → focus returns to last-highlighted minimap row
4. Up/Down in minimap → moves focus between rows without scrolling the content
5. Enter on a row → plan scrolls toward that section
6. Press `p` → `SectionViewerScreen` opens with left minimap + right markdown; Tab/Arrow/Enter contract holds; Escape closes
7. Open a file whose plan has no section markers → detail pane works normally, no minimap
8. Press `p` with no plan → warning notification, no crash

<!-- /section: verification -->

<!-- section: post_implementation [dimensions: workflow] -->

## Step 9: Post-Implementation

Follow Step 9 from the shared workflow for commit, archival, and push.

<!-- /section: post_implementation -->
