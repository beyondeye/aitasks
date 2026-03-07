"""Detail pane widget showing plan/task content for the current annotation."""

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_task_id: str | None = None

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
            self.query_one("#detail_header", Static).update("")
            self.query_one("#detail_markdown", Markdown).update("")
            self.query_one("#detail_placeholder").display = True
            self.query_one("#detail_markdown").display = False
            return

        if detail.task_id == self._current_task_id:
            return  # Same task, skip redundant update

        self._current_task_id = detail.task_id
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
        self.scroll_home(animate=False)

    def show_multiple_tasks(self, task_ids: list[str]) -> None:
        """When selection spans multiple tasks, show a summary."""
        self._current_task_id = None
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
