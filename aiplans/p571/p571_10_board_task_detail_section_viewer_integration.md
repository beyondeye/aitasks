---
Task: t571_10_board_task_detail_section_viewer_integration.md
Parent Task: aitasks/t571_more_structured_brainstorming_created_plan.md
Sibling Tasks: aitasks/t571/t571_5_*.md, aitasks/t571/t571_6_*.md, aitasks/t571/t571_7_*.md, aitasks/t571/t571_8_*.md, aitasks/t571/t571_9_*.md
Archived Sibling Plans: aiplans/archived/p571/p571_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t571_10 — Board TaskDetailScreen Section Viewer Integration

<!-- section: context [dimensions: motivation, integration] -->

## Context

Integrate the shared `.aitask-scripts/lib/section_viewer.py` module (from t571_5) into the **board** TUI's `TaskDetailScreen`. Two entry points:

1. **Inline minimap in plan view** — when the user toggles to plan view (`v` key), a `SectionMinimap` appears inside `#md_view` above the Markdown
2. **Full-screen plan viewer via `shift+v`** — pushes a `SectionViewerScreen` for dedicated reading

Board users already use `p` for pick and `v` for toggle — we must NOT override either. Only `shift+v` is newly bound.

**Depends on t571_5.** Do NOT start until `.aitask-scripts/lib/section_viewer.py` exists.

<!-- /section: context -->

<!-- section: files_and_lines [dimensions: deliverables] -->

## Files and Line References

- `.aitask-scripts/board/aitask_board.py`:
  - sys.path insert at line 13 covers `lib/`; rely on `section_viewer.py`'s own sys.path self-insert for brainstorm access — no changes needed here
  - `TaskDetailScreen` at line 1895
  - BINDINGS at lines 1898–1922 (`p`/`P` → pick, `v`/`V` → toggle_view, `shift+v`/`f` free)
  - `compose()` at lines 1952–2100+, `VerticalScroll#md_view` at lines 2082–2083 containing `Markdown(self.task_data.content)` (no id on the Markdown)
  - `toggle_view()` at lines 2180–2207 (currently toggles `self._showing_plan` and swaps content via `self.query_one("#md_view Markdown", Markdown)`)
  - `btn_view` button at lines 2088–2100 (`(V)iew Plan` / `(V)iew Task`)

<!-- /section: files_and_lines -->

<!-- section: toggle_view_enhancement [dimensions: integration, widget-design] -->

## 1. `toggle_view()` — mount/remove minimap on plan toggle

Refactor `toggle_view()` to extract the plan-reading logic into `_read_plan_content()`:
```python
def _read_plan_content(self) -> str | None:
    """Return the plan content for the current task, or None if no plan file exists."""
    # Move the existing path-lookup & file-read logic here.
```

Then in the plan-direction branch of `toggle_view()`, after updating the Markdown with plan content:
```python
from brainstorm.brainstorm_sections import parse_sections
from section_viewer import SectionMinimap
parsed = parse_sections(plan_content)
md_view = self.query_one("#md_view", VerticalScroll)
if parsed.sections:
    self._plan_parsed = parsed
    self._plan_text = plan_content
    existing = md_view.query("#board_minimap")
    if not existing:
        minimap = SectionMinimap(id="board_minimap")
        # Mount BEFORE the Markdown inside #md_view
        md_view.mount(minimap, before="Markdown")
    md_view.query_one("#board_minimap", SectionMinimap).populate(parsed)
else:
    for w in list(md_view.query("#board_minimap")):
        w.remove()
```

In the task-direction branch (going back to task view), unconditionally remove `#board_minimap`:
```python
md_view = self.query_one("#md_view", VerticalScroll)
for w in list(md_view.query("#board_minimap")):
    w.remove()
```

Initialize `self._plan_parsed = None`, `self._plan_text = ""` in `__init__`.

<!-- /section: toggle_view_enhancement -->

<!-- section: section_select_handler [dimensions: integration, scroll-estimation] -->

## 2. Handle `SectionMinimap.SectionSelected`

```python
def on_section_minimap_section_selected(self, event) -> None:
    if self._plan_parsed is None:
        return
    from section_viewer import estimate_section_y
    md_view = self.query_one("#md_view", VerticalScroll)
    total = self._plan_text.count('\n') + 1
    y = estimate_section_y(self._plan_parsed, event.section_name, total, md_view.virtual_size.height)
    if y is not None:
        md_view.scroll_to(y=y, animate=True)
    event.stop()
```

<!-- /section: section_select_handler -->

<!-- section: focus_routing [dimensions: focus-management, keybinding] -->

## 3. Tab focus contract (crucial: scoped guard)

Minimap→content:
```python
def on_section_minimap_toggle_focus(self, event) -> None:
    self.query_one("#md_view Markdown", Markdown).focus()
    event.stop()
```

Content→minimap (screen-level):
```python
BINDINGS = [..., Binding("tab", "focus_minimap", "Minimap")]

def action_focus_minimap(self) -> None:
    from textual.actions import SkipAction
    md = self.query_one("#md_view Markdown", Markdown)
    minimaps = self.query("#board_minimap")
    if self.screen.focused is not md or not minimaps:
        raise SkipAction()
    minimaps.first().focus_first_row()
```

The `SkipAction` guard is especially important here: `TaskDetailScreen` is a form with many fields the user Tabs between. The binding must only activate when plan markdown has focus AND a minimap is mounted.

<!-- /section: focus_routing -->

<!-- section: fullscreen_binding [dimensions: keybinding, integration] -->

## 4. `shift+v` → full-screen `SectionViewerScreen`

Add to BINDINGS:
```python
Binding("shift+v", "fullscreen_plan", "Fullscreen plan"),
```

```python
def action_fullscreen_plan(self) -> None:
    plan_content = self._read_plan_content()
    if plan_content:
        from section_viewer import SectionViewerScreen
        self.app.push_screen(SectionViewerScreen(
            plan_content,
            title=f"Plan for t{self.task_data.id}"))
    else:
        self.notify("No plan file found", severity="warning")
```

<!-- /section: fullscreen_binding -->

<!-- section: binding_safety [dimensions: keybinding, robustness] -->

## 5. Binding safety regression

After adding the new bindings, manually confirm:
- `p` still triggers `action_pick` (not overridden by any new binding)
- `v` still triggers `action_toggle_view`
- `shift+v` is the ONLY newly bound key
- Tab inside the form navigates fields as before (the guard must pass through)

<!-- /section: binding_safety -->

<!-- section: verification [dimensions: testing] -->

## Verification

Fixture content: t571_5's plan embeds ~11 sectioned entries. Open the board and drive through:

1. `ait board` → select task `t571_5` → open `TaskDetailScreen`
2. Press `v` → plan view shows. Minimap appears above the markdown with all section names + dimension tags
3. Tab → focus moves to plan markdown. Tab again → focus returns to the last-highlighted minimap row
4. Up/Down on minimap → focus cycles, no scroll
5. Enter on a row → plan scrolls to that section
6. Press `shift+v` → `SectionViewerScreen` opens with split layout; Tab/Arrow/Enter contract holds; Escape closes
7. Press `v` again → back to task view; `#board_minimap` is removed
8. Select a task with no plan sections → `v` shows plan markdown only (no minimap)
9. Regression: `p` still triggers pick; Tab still cycles form fields when plan view is NOT active

<!-- /section: verification -->

<!-- section: post_implementation [dimensions: workflow] -->

## Step 9: Post-Implementation

Follow Step 9 from the shared workflow for commit, archival, and push.

<!-- /section: post_implementation -->
