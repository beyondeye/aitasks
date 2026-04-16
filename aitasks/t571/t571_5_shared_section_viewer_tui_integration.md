---
priority: high
effort: high
depends: []
issue_type: refactor
status: Ready
labels: [brainstorming, ait_brainstorm, ui, codebrowser]
created_at: 2026-04-16 12:00
updated_at: 2026-04-16 12:00
---

## Context

This is child task 5 of t571 (Structured Brainstorming Sections). It creates a shared, reusable section-aware viewer module in `.aitask-scripts/lib/` and integrates it into all three TUIs: codebrowser, brainstorm, and board.

Currently each TUI renders plan/proposal/task markdown content using plain Textual `Markdown` widgets with no section awareness. This task adds:
1. A shared module with reusable Textual widgets for section navigation
2. Integration into each TUI where plan/proposal content is displayed

**Depends on**: t571_1 (section parser module)

## Key Files to Modify

- **CREATE**: `.aitask-scripts/lib/section_viewer.py` — Shared viewer module with reusable widgets
- **MODIFY**: `.aitask-scripts/codebrowser/detail_pane.py` — Enhanced detail pane with section minimap
- **MODIFY**: `.aitask-scripts/codebrowser/codebrowser_app.py` — Add `p` keybinding for full-screen plan viewer
- **MODIFY**: `.aitask-scripts/codebrowser/annotation_data.py` — Add `plan_sections` field to TaskDetailContent
- **MODIFY**: `.aitask-scripts/brainstorm/brainstorm_app.py` — Enhanced NodeDetailModal with section minimap
- **MODIFY**: `.aitask-scripts/board/aitask_board.py` — Enhanced TaskDetailScreen plan view with section minimap

## Reference Files for Patterns

- `.aitask-scripts/brainstorm/brainstorm_sections.py` (t571_1) — `parse_sections()`, `ParsedContent`, `ContentSection`
- `.aitask-scripts/lib/tui_switcher.py` — Demonstrates shared-lib-module pattern: defines reusable Textual widgets/mixins imported by multiple TUIs
- `.aitask-scripts/codebrowser/history_screen.py` — `HistoryScreen` (ModalScreen) with left/right split layout, focus switching, escape-to-dismiss. Architectural reference for `SectionViewerScreen`
- `.aitask-scripts/codebrowser/history_list.py` — `HistoryList` with focusable rows. Pattern for `SectionMinimap` rows
- `.aitask-scripts/codebrowser/detail_pane.py` — Current DetailPane (99 lines): `VerticalScroll` with Static header + Markdown + placeholder. Uses `update_content(TaskDetailContent)`.
- `.aitask-scripts/codebrowser/annotation_data.py` — `TaskDetailContent` dataclass (lines 23-28): `task_id`, `plan_content`, `task_content`, `has_plan`, `has_task`
- `.aitask-scripts/codebrowser/codebrowser_app.py` — Main app, BINDINGS list (line 153), `action_view_plan()` pattern to add
- `.aitask-scripts/brainstorm/brainstorm_app.py` `NodeDetailModal` (lines 233-318) — Three-tab modal (Metadata/Proposal/Plan), each tab has `VerticalScroll` + `Markdown` widget
- `.aitask-scripts/board/aitask_board.py` `TaskDetailScreen` (line 1895) — Modal with `VerticalScroll` + `Markdown`, plan toggle via `(V)iew Plan` button (lines 2186-2207)

## Implementation Plan

### Part 1: Shared Module (`.aitask-scripts/lib/section_viewer.py`)

Create three reusable Textual widgets:

#### 1.1 `SectionMinimap(VerticalScroll)` Widget

A compact vertical list of section names with dimension tags.

```python
class SectionRow(Static):
    """A single row in the section minimap."""
    class Selected(Message):
        def __init__(self, section_name: str) -> None:
            self.section_name = section_name
            super().__init__()

    def __init__(self, name: str, dimensions: list[str], **kwargs):
        super().__init__(**kwargs)
        self.section_name = name
        self.dimensions = dimensions
        self.can_focus = True

    def render(self) -> str:
        dim_str = f" [{', '.join(self.dimensions)}]" if self.dimensions else ""
        return f" {self.section_name}{dim_str}"

    def on_click(self) -> None:
        self.post_message(self.Selected(self.section_name))

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.post_message(self.Selected(self.section_name))


class SectionMinimap(VerticalScroll):
    """Minimap of content sections with dimension tags."""
    class SectionSelected(Message):
        def __init__(self, section_name: str) -> None:
            self.section_name = section_name
            super().__init__()

    def populate(self, parsed: ParsedContent) -> None:
        self.remove_children()
        for section in parsed.sections:
            row = SectionRow(section.name, section.dimensions)
            self.mount(row)

    def on_section_row_selected(self, event: SectionRow.Selected) -> None:
        self.post_message(self.SectionSelected(event.section_name))
```

CSS: subtle background, compact rows (height: 1 each), accent highlight on focus.

#### 1.2 `SectionAwareMarkdown(VerticalScroll)` Widget

Wraps a Textual `Markdown` widget with section scroll-to support.

```python
class SectionAwareMarkdown(VerticalScroll):
    """Markdown viewer that supports scrolling to named sections."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._section_positions: dict[str, float] = {}  # name -> scroll offset

    def compose(self):
        yield Markdown(id="section_md")

    def update_content(self, text: str, parsed: ParsedContent | None = None):
        self.query_one("#section_md", Markdown).update(text)
        if parsed:
            # Estimate section positions based on line numbers
            total_lines = text.count('\n') + 1
            for s in parsed.sections:
                self._section_positions[s.name] = s.start_line / total_lines

    def scroll_to_section(self, name: str) -> None:
        if name in self._section_positions:
            ratio = self._section_positions[name]
            target_y = ratio * self.virtual_size.height
            self.scroll_to(y=target_y, animate=True)
```

#### 1.3 `SectionViewerScreen(ModalScreen)` Full-Screen Viewer

Split layout modal for deep plan/proposal reading.

```python
class SectionViewerScreen(ModalScreen):
    BINDINGS = [Binding("escape", "close", "Close")]

    def __init__(self, content: str, title: str = "Plan Viewer"):
        super().__init__()
        self._content = content
        self._title = title

    def compose(self):
        with Container(id="section_viewer"):
            yield Label(self._title, id="sv_title")
            with Horizontal(id="sv_split"):
                yield SectionMinimap(id="sv_minimap")
                yield SectionAwareMarkdown(id="sv_content")

    def on_mount(self):
        parsed = parse_sections(self._content)
        self.query_one("#sv_minimap", SectionMinimap).populate(parsed)
        self.query_one("#sv_content", SectionAwareMarkdown).update_content(
            self._content, parsed)

    def on_section_minimap_section_selected(self, event):
        self.query_one("#sv_content", SectionAwareMarkdown).scroll_to_section(
            event.section_name)

    def action_close(self):
        self.dismiss()
```

CSS: minimap width ~30 chars with border-right, content fills remaining space.

### Part 2: Codebrowser Integration

#### 2.1 Enhanced DetailPane (`detail_pane.py`)

When plan content has sections, mount a `SectionMinimap` above the markdown:

```python
# In update_content():
from brainstorm.brainstorm_sections import parse_sections
# After setting markdown content...
parsed = parse_sections(content)
if parsed.sections:
    minimap = SectionMinimap(id="detail_minimap")
    # Mount before markdown widget
    minimap.populate(parsed)
    # Handle SectionSelected → scroll markdown
```

Add `sys.path` insert for brainstorm module access (follow existing `codebrowser_app.py` pattern at line 28).

#### 2.2 Plan Viewer Keybinding (`codebrowser_app.py`)

Add `Binding("p", "view_plan", "Plan viewer")` to BINDINGS list.

```python
def action_view_plan(self) -> None:
    """Open full-screen plan viewer for current annotation's task."""
    if self._current_detail and self._current_detail.has_plan:
        self.push_screen(SectionViewerScreen(
            self._current_detail.plan_content,
            title=f"Plan for t{self._current_detail.task_id}"))
    else:
        self.notify("No plan available for current task", severity="warning")
```

#### 2.3 TaskDetailContent Extension (`annotation_data.py`)

Add parsed sections field:
```python
@dataclass
class TaskDetailContent:
    task_id: str
    plan_content: str = ""
    task_content: str = ""
    has_plan: bool = False
    has_task: bool = False
    plan_sections: list | None = None  # list[ContentSection] when parsed
```

### Part 3: Brainstorm TUI Integration

Modify `NodeDetailModal` (line 233 in `brainstorm_app.py`):

In the Proposal tab (`tab_proposal`), after loading proposal content:
```python
parsed = parse_sections(proposal)
if parsed.sections:
    minimap = SectionMinimap()
    minimap.populate(parsed)
    # Mount above proposal Markdown in the proposal_scroll container
```

Same for Plan tab (`tab_plan`).

Handle `SectionMinimap.SectionSelected` to scroll the corresponding `VerticalScroll` to the section position.

### Part 4: Board TUI Integration

Modify `TaskDetailScreen` (line 1895 in `aitask_board.py`):

In `_toggle_plan_view()` (line 2186), when showing plan content:
```python
from brainstorm.brainstorm_sections import parse_sections
parsed = parse_sections(content)
if parsed.sections:
    minimap = SectionMinimap()
    minimap.populate(parsed)
    # Mount above markdown widget in md_view
```

Handle `SectionMinimap.SectionSelected` for scroll navigation.

Add keybinding to open `SectionViewerScreen` for full-screen plan reading (e.g., `shift+v` or `f` for "fullscreen").

### Sys.path Setup for Imports

All three TUIs need to import from both `brainstorm.brainstorm_sections` and `lib.section_viewer`. The import pattern already exists — see `codebrowser_app.py` line 28 and `brainstorm_app.py` which add parent directories to sys.path.

For the shared lib module:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from section_viewer import SectionMinimap, SectionAwareMarkdown, SectionViewerScreen
```

For the brainstorm parser:
```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from brainstorm.brainstorm_sections import parse_sections
```

## Verification Steps

1. **Codebrowser detail pane**: Open codebrowser, navigate to a file annotated by a task with section-structured plan. Press `d` for detail pane — verify minimap appears above plan content with section names + dimension tags
2. **Codebrowser minimap click**: Click a section name in minimap — verify plan scrolls to that section
3. **Codebrowser full viewer**: Press `p` to open SectionViewerScreen — verify left minimap + right content split layout. Navigate sections with up/down
4. **Codebrowser no sections**: Test with plan that has NO sections — verify detail pane works normally without minimap
5. **Brainstorm TUI**: Open NodeDetailModal, view Proposal and Plan tabs — verify minimaps appear when content has sections
6. **Board TUI**: Open TaskDetailScreen, toggle to plan view — verify minimap appears. Test full-screen viewer keybinding
7. **No plan**: Test `p` key when no plan is available — verify appropriate warning message
8. **Shared module**: Verify `section_viewer.py` works when imported by all three TUIs (no import errors, no path issues)
9. **Graceful fallback**: All three integrations should work normally when content has no sections (no minimap, just plain markdown)
