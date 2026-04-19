"""Detail pane widget showing plan/task content for the current annotation."""

from __future__ import annotations

from textual.actions import SkipAction
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Markdown, Static

from annotation_data import TaskDetailContent


class DetailPane(VerticalScroll):
    """Right-side pane showing plan/task markdown content for the annotated task."""

    DEFAULT_CSS = """
    DetailPane {
        border-left: thick $primary;
        background: $surface;
    }
    DetailPane:focus, DetailPane:focus-within {
        border-left: thick $accent;
    }
    DetailPane #detail_header {
        height: 1;
        dock: top;
        background: $surface-lighten-1;
        padding: 0 1;
    }
    DetailPane #detail_markdown {
        margin: 0 1;
    }
    DetailPane #detail_placeholder {
        color: $text-muted;
        text-align: center;
        margin-top: 2;
    }
    """

    BINDINGS = [Binding("tab", "focus_minimap", "Minimap")]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_task_id: str | None = None
        self._current_detail: TaskDetailContent | None = None
        self._cached_parsed = None
        self._cached_plan_text: str = ""

    def compose(self):
        yield Static("", id="detail_header")
        yield Markdown("", id="detail_markdown")
        yield Static(
            "Move cursor to an annotated line\nto see task/plan details",
            id="detail_placeholder",
        )

    def on_mount(self) -> None:
        self.query_one("#detail_markdown").display = False

    def update_content(self, detail: TaskDetailContent | None) -> None:
        """Update the pane with new task detail content."""
        if detail is None:
            self._current_task_id = None
            self._current_detail = None
            self._cached_parsed = None
            self._cached_plan_text = ""
            self.query_one("#detail_header", Static).update("")
            self.query_one("#detail_markdown", Markdown).update("")
            self.query_one("#detail_placeholder").display = True
            self.query_one("#detail_markdown").display = False
            self._remove_minimap()
            return

        if detail.task_id == self._current_task_id:
            return  # Same task, skip redundant update

        self._current_task_id = detail.task_id
        self._current_detail = detail
        self.query_one("#detail_placeholder").display = False
        self.query_one("#detail_markdown").display = True

        # Prefer plan content, fall back to task content
        if detail.has_plan and detail.plan_content:
            header = f" Plan for t{detail.task_id}"
            content = detail.plan_content
        elif detail.has_task and detail.task_content:
            header = f" Task t{detail.task_id}"
            content = detail.task_content
        else:
            header = f" t{detail.task_id}"
            content = "*No plan or task content available*"

        self.query_one("#detail_header", Static).update(header)
        self.query_one("#detail_markdown", Markdown).update(content)
        self._sync_minimap(detail, content)
        self.scroll_home(animate=False)

    def _sync_minimap(self, detail: TaskDetailContent, content: str) -> None:
        """Mount/populate section minimap when the plan has sections; remove otherwise."""
        if not (detail.has_plan and detail.plan_content):
            self._cached_parsed = None
            self._cached_plan_text = ""
            self._remove_minimap()
            return
        # Import parse_sections via section_viewer (re-export), not directly from
        # brainstorm.brainstorm_sections: section_viewer's import-time sys.path
        # self-insert is what makes brainstorm.* reachable from this package.
        from section_viewer import SectionMinimap, parse_sections

        parsed = parse_sections(content)
        if not parsed.sections:
            self._cached_parsed = None
            self._cached_plan_text = ""
            self._remove_minimap()
            return
        self._cached_parsed = parsed
        self._cached_plan_text = content
        existing = self.query("#detail_minimap")
        if existing:
            minimap = existing.first()
        else:
            minimap = SectionMinimap(id="detail_minimap")
            self.mount(minimap, before="#detail_markdown")
        minimap.populate(parsed)

    def _remove_minimap(self) -> None:
        for w in list(self.query("#detail_minimap")):
            w.remove()

    def on_section_minimap_section_selected(self, event) -> None:
        from section_viewer import estimate_section_y

        if self._cached_parsed is None:
            return
        total = self._cached_plan_text.count("\n") + 1
        y = estimate_section_y(
            self._cached_parsed, event.section_name, total, self.virtual_size.height
        )
        if y is not None:
            self.scroll_to(y=y, animate=False)
        event.stop()

    def on_section_minimap_toggle_focus(self, event) -> None:
        self.query_one("#detail_markdown", Markdown).focus()
        event.stop()

    def action_focus_minimap(self) -> None:
        focused = self.screen.focused
        try:
            markdown = self.query_one("#detail_markdown", Markdown)
        except Exception:
            raise SkipAction()
        if focused is not markdown:
            raise SkipAction()
        minimaps = self.query("#detail_minimap")
        if not minimaps:
            raise SkipAction()
        minimaps.first().focus_first_row()

    def show_multiple_tasks(self, task_ids: list[str]) -> None:
        """When selection spans multiple tasks, show a summary."""
        self._current_task_id = None
        self._current_detail = None
        self._cached_parsed = None
        self._cached_plan_text = ""
        self._remove_minimap()
        self.query_one("#detail_placeholder").display = False
        self.query_one("#detail_markdown").display = True
        self.query_one("#detail_header", Static).update(" Multiple tasks in selection")
        summary = "\n".join(f"- **t{tid}**" for tid in task_ids)
        self.query_one("#detail_markdown", Markdown).update(
            f"Selection spans multiple tasks:\n\n{summary}\n\n"
            "*Move cursor to a single-task region to see details.*"
        )

    def clear(self) -> None:
        """Clear the pane content."""
        self.update_content(None)
