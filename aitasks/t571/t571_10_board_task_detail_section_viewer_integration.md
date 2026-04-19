---
priority: high
effort: medium
depends: [5]
issue_type: refactor
status: Implementing
labels: [brainstorming, ait_brainstorm, ui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-19 08:47
updated_at: 2026-04-19 09:41
---

<!-- section: context [dimensions: motivation, integration] -->

## Context

Sibling task of t571_5 (shared section viewer library). This task integrates that library into the **board** TUI: add a section minimap to `TaskDetailScreen`'s plan view and a `shift+v` binding to open `SectionViewerScreen` for full-screen reading.

**Depends on t571_5.** Do not start until `.aitask-scripts/lib/section_viewer.py` exists.

<!-- /section: context -->

<!-- section: files_to_modify [dimensions: deliverables] -->

## Key Files to Modify

- **MODIFY** `.aitask-scripts/board/aitask_board.py` — `TaskDetailScreen` at line 1895: update `toggle_view()` at line 2180 to mount/remove `SectionMinimap(id="board_minimap")` inside `#md_view`; add `Binding("shift+v", "fullscreen_plan", ...)` to BINDINGS (lines 1898–1922); add handlers for `SectionSelected` and `ToggleFocus`

<!-- /section: files_to_modify -->

<!-- section: reference_patterns [dimensions: patterns] -->

## Reference Files for Patterns

- `.aitask-scripts/board/aitask_board.py:13` — sys.path already inserts `parent.parent/"lib"`; section_viewer import works without further setup. `parse_sections` import goes via section_viewer's re-export
- `.aitask-scripts/board/aitask_board.py:2082-2083` — `VerticalScroll(id="md_view")` contains `Markdown(self.task_data.content)` with no id; current toggle query uses selector `#md_view Markdown`
- `.aitask-scripts/board/aitask_board.py:2088-2100` — button row including `(V)iew Plan` button id `btn_view`
- `.aitask-scripts/board/aitask_board.py:1898-1922` — BINDINGS list; `p`/`P` already bound to `action_pick`, `v`/`V` to `action_toggle_view`; `shift+v` and `f` are free

<!-- /section: reference_patterns -->

<!-- section: toggle_view_enhancement [dimensions: integration, widget-design] -->

## 1. `toggle_view()` — mount/unmount minimap during plan view

When switching INTO plan view (`self._showing_plan` becomes True), after updating the `#md_view Markdown` widget content with the plan text:

```python
from section_viewer import SectionMinimap
parsed = parse_sections(plan_content)
md_view = self.query_one("#md_view", VerticalScroll)
if parsed.sections:
    minimap = self.query_one("#board_minimap", SectionMinimap) if <exists> else None
    if minimap is None:
        minimap = SectionMinimap(id="board_minimap")
        md_view.mount(minimap, before="Markdown")
    minimap.populate(parsed)
    self._plan_parsed = parsed
    self._plan_text = plan_content
else:
    # Remove minimap if present
    existing = md_view.query("#board_minimap")
    for w in existing:
        w.remove()
```

When switching BACK to task view, always remove `#board_minimap` from `#md_view`.

<!-- /section: toggle_view_enhancement -->

<!-- section: scroll_selected [dimensions: integration, scroll-estimation] -->

## 2. Handle `SectionMinimap.SectionSelected`

```python
def on_section_minimap_section_selected(self, event) -> None:
    from section_viewer import estimate_section_y
    md_view = self.query_one("#md_view", VerticalScroll)
    total = self._plan_text.count('\n') + 1
    y = estimate_section_y(self._plan_parsed, event.section_name, total, md_view.virtual_size.height)
    if y is not None:
        md_view.scroll_to(y=y, animate=True)
    event.stop()
```

<!-- /section: scroll_selected -->

<!-- section: focus_routing [dimensions: focus-management, keybinding] -->

## 3. Focus routing — Tab between minimap and board markdown

Per the keyboard contract defined in t571_5:

- `on_section_minimap_toggle_focus(event)` → focus `#md_view Markdown`; `event.stop()`
- Add `TaskDetailScreen.BINDINGS += [Binding("tab", "focus_minimap", "Minimap")]`
- `action_focus_minimap()`:
  - Scope guard: the focused widget should be `#md_view Markdown` AND `#board_minimap` must exist; if not, `raise SkipAction()`
  - Else focus the minimap via `.focus_first_row()`

The guard is critical because `TaskDetailScreen` has many form fields the user tabs between — we must not hijack Tab globally.

<!-- /section: focus_routing -->

<!-- section: fullscreen_binding [dimensions: keybinding, integration] -->

## 4. `shift+v` → full-screen plan viewer

Add `Binding("shift+v", "fullscreen_plan", "Fullscreen plan")` to BINDINGS.

```python
def action_fullscreen_plan(self) -> None:
    plan_content = self._read_plan_content()  # extract helper from toggle_view()
    if plan_content:
        from section_viewer import SectionViewerScreen
        self.app.push_screen(SectionViewerScreen(
            plan_content,
            title=f"Plan for t{self.task_data.id}"))
    else:
        self.notify("No plan file found", severity="warning")
```

Extract `_read_plan_content()` from existing plan-resolution code in `toggle_view()` so both paths share the same path-lookup logic.

<!-- /section: fullscreen_binding -->

<!-- section: binding_safety [dimensions: keybinding, robustness] -->

## 5. Binding safety

Verify `p` still triggers `action_pick` on the board (not overridden by our new bindings). Verify `v` still triggers `action_toggle_view`. Only `shift+v` is newly bound. This is critical because board users rely on `p` for pick and `v` for quick toggle.

<!-- /section: binding_safety -->

<!-- section: verification [dimensions: testing] -->

## Verification Steps

1. Open `ait board` and navigate to a task whose plan has `<!-- section: ... [dimensions: ...] -->` markers (t571_5 and sibling plans are ready fixtures)
2. Open `TaskDetailScreen` (e.g., press Enter on the task)
3. Press `v` → plan view shows; minimap appears above markdown
4. Tab → focus moves to plan markdown. Tab again → focus returns to last-highlighted minimap row
5. Up/Down on minimap → moves focus without scrolling
6. Enter on a row → plan scrolls to that section
7. Press `shift+v` → `SectionViewerScreen` opens with split layout; same contract; Escape closes
8. Press `v` again → back to task view; minimap removed
9. Task with non-sectioned plan → plan view shows markdown only, no minimap
10. Confirm `p` still triggers pick (regression check on binding)

<!-- /section: verification -->

<!-- section: post_implementation [dimensions: workflow] -->

## Step 9: Post-Implementation

Follow Step 9 from the shared workflow for commit, archival, and push.

<!-- /section: post_implementation -->
