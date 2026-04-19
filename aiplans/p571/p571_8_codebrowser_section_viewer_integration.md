---
Task: t571_8_codebrowser_section_viewer_integration.md
Parent Task: aitasks/t571_more_structured_brainstorming_created_plan.md
Sibling Tasks: aitasks/t571/t571_5_*.md, aitasks/t571/t571_6_*.md, aitasks/t571/t571_7_*.md, aitasks/t571/t571_9_*.md, aitasks/t571/t571_10_*.md
Archived Sibling Plans: aiplans/archived/p571/p571_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t571_8 — Codebrowser Section Viewer Integration

<!-- section: context [dimensions: motivation, integration] -->

## Context

Integrate the shared `.aitask-scripts/lib/section_viewer.py` module (from t571_5) into the **codebrowser** TUI. Two entry points for users:

1. **Detail pane minimap** — when the current annotation's plan has sections, a minimap appears above the existing `#detail_markdown`
2. **Full-screen plan viewer** — `p` key pushes a `SectionViewerScreen` with a split layout (minimap + markdown)

The plan for t571_5 itself carries section markers, so once this task lands the user can open any task annotated by t571_5 (or any of its siblings) in codebrowser and see a populated minimap.

**Depends on t571_5.** Do NOT start until `.aitask-scripts/lib/section_viewer.py` exists and exports `SectionMinimap`, `SectionViewerScreen`, `estimate_section_y`.

<!-- /section: context -->

<!-- section: files_and_lines [dimensions: deliverables] -->

## Files and Line References

- `.aitask-scripts/codebrowser/detail_pane.py` (99 lines today) — modify `update_content()` lines 53–83; widget IDs `#detail_header`, `#detail_markdown`, `#detail_placeholder`
- `.aitask-scripts/codebrowser/codebrowser_app.py` — add `Binding("p", "view_plan", ...)` to BINDINGS list (lines 235–252); existing sys.path insert at line 28 handles `lib/`
- `.aitask-scripts/codebrowser/annotation_data.py` — extend `TaskDetailContent` (lines 22–28) with `plan_sections: list | None = None`

<!-- /section: files_and_lines -->

<!-- section: detail_pane_changes [dimensions: integration, widget-design] -->

## 1. `detail_pane.py` — Mount minimap above markdown

Extend `DetailPane.update_content()`:

```python
def update_content(self, detail: TaskDetailContent | None) -> None:
    self._current_detail = detail  # NEW: expose on instance
    ...
    if content and detail and detail.has_plan:
        # IMPORTANT: import parse_sections from section_viewer (convenience re-export),
        # NOT from brainstorm.brainstorm_sections. The lib module self-inserts
        # `.aitask-scripts/` into sys.path on first import, so importing
        # `brainstorm.*` directly before `section_viewer` fails with ModuleNotFoundError.
        # See t571_10 Final Implementation Notes for the fix history.
        from section_viewer import SectionMinimap, parse_sections
        parsed = parse_sections(content)
        if parsed.sections:
            self._cached_parsed = parsed
            self._cached_plan_text = content
            # Ensure minimap exists before #detail_markdown
            if not self.query("#detail_minimap"):
                minimap = SectionMinimap(id="detail_minimap")
                self.mount(minimap, before="#detail_markdown")
            self.query_one("#detail_minimap", SectionMinimap).populate(parsed)
        else:
            for w in list(self.query("#detail_minimap")):
                w.remove()
```

Initialize `self._current_detail = None`, `self._cached_parsed = None`, `self._cached_plan_text = ""` in `__init__`.

<!-- /section: detail_pane_changes -->

<!-- section: scroll_handler [dimensions: integration, scroll-estimation] -->

## 2. `detail_pane.py` — Handle `SectionSelected` and `ToggleFocus`

```python
def on_section_minimap_section_selected(self, event) -> None:
    from section_viewer import estimate_section_y
    if self._cached_parsed is None:
        return
    total = self._cached_plan_text.count('\n') + 1
    y = estimate_section_y(
        self._cached_parsed, event.section_name, total, self.virtual_size.height)
    if y is not None:
        self.scroll_to(y=y, animate=True)
    event.stop()

def on_section_minimap_toggle_focus(self, event) -> None:
    self.query_one("#detail_markdown", Markdown).focus()
    event.stop()
```

<!-- /section: scroll_handler -->

<!-- section: focus_routing [dimensions: focus-management, keybinding] -->

## 3. `detail_pane.py` — Tab on markdown returns focus to minimap

Add screen-level Tab binding on `DetailPane`:

```python
BINDINGS = [Binding("tab", "focus_minimap", "Minimap")]

def action_focus_minimap(self) -> None:
    from textual.actions import SkipAction
    focused = self.screen.focused
    markdown = self.query_one("#detail_markdown", Markdown)
    if focused is not markdown:
        raise SkipAction()
    minimaps = self.query("#detail_minimap")
    if not minimaps:
        raise SkipAction()
    minimaps.first().focus_first_row()
```

Guard: only fires when `#detail_markdown` is focused AND `#detail_minimap` exists. Otherwise `SkipAction` lets Textual's default Tab-nav proceed (important because codebrowser has other focus targets).

<!-- /section: focus_routing -->

<!-- section: app_binding [dimensions: keybinding, integration] -->

## 4. `codebrowser_app.py` — `V` key opens `SectionViewerScreen`

**Cross-TUI alignment:** `V` (uppercase / `shift+v`) is the shared fullscreen-viewer key across board (t571_10), codebrowser (this task), and brainstorm (t571_9). See p571_10's "Cross-TUI Keybinding Alignment" section.

Add to BINDINGS list:
```python
Binding("V", "view_plan", "Fullscreen plan"),
```

Add method:
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

<!-- /section: app_binding -->

<!-- section: annotation_data_change [dimensions: data-model] -->

## 5. `annotation_data.py` — Add optional `plan_sections` field

```python
@dataclass
class TaskDetailContent:
    task_id: str
    plan_content: str = ""
    task_content: str = ""
    has_plan: bool = False
    has_task: bool = False
    plan_sections: list | None = None  # NEW — reserved for callers that want to avoid re-parsing
```

No behavioral change in this task — the field is added for future use. The detail pane currently re-parses plans itself.

<!-- /section: annotation_data_change -->

<!-- section: verification [dimensions: testing] -->

## Verification

Test against real fixture content in the repo:

1. `ait codebrowser` → navigate to `.aitask-scripts/lib/section_viewer.py` (created by t571_5). Its annotation references t571_5's plan, which has sections
2. Press `d` → detail pane shows with minimap. Rows = section names from the plan + their dimension tags
3. Tab → focus moves to plan markdown. Tab again → focus returns to the last-highlighted row in the minimap
4. Up/Down on minimap → focus cycles between rows without scrolling
5. Enter on a row → plan scrolls to that section
6. Press `V` (uppercase / `shift+v`) → `SectionViewerScreen` opens as a modal with left minimap + right markdown. Contract holds. Escape closes
7. Navigate to a file annotated by a task with NO section markers in its plan → detail pane renders without a minimap; Tab behavior falls through to Textual default
8. Press `V` when no plan is available → warning notification, no crash

<!-- /section: verification -->

<!-- section: post_implementation [dimensions: workflow] -->

## Step 9: Post-Implementation

Follow Step 9 from the shared workflow for commit, archival, and push.

<!-- /section: post_implementation -->
