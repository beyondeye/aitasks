"""History detail pane: right-side widget showing full task info for completed tasks."""

from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Optional

from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Input, Markdown, Static
from textual import work

from history_data import (
    CompletedTask,
    PlatformInfo,
    TaskCommitInfo,
    detect_platform_info,
    find_child_tasks,
    find_commits_for_task,
    find_sibling_tasks,
    load_plan_content,
    load_task_content,
)
from history_list import _focus_neighbor, _format_labels, _type_color


# ---------------------------------------------------------------------------
# Custom Messages
# ---------------------------------------------------------------------------


class NavigateToFile(Message):
    """Posted when the user selects an affected file to open in the codebrowser."""

    def __init__(self, file_path: str) -> None:
        super().__init__()
        self.file_path = file_path


class HistoryBrowseEvent(Message):
    """Posted when a task is explicitly browsed (for updating recently opened)."""

    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id


# ---------------------------------------------------------------------------
# Field Widgets
# ---------------------------------------------------------------------------


class MetadataField(Static):
    """Read-only metadata field (not focusable — no enter action)."""

    can_focus = False

    DEFAULT_CSS = """
    MetadataField {
        height: 1;
        padding: 0 1;
    }
    """


class IssueLinkField(Static):
    """Focusable issue URL field. Press Enter to open in browser."""

    can_focus = True

    DEFAULT_CSS = """
    IssueLinkField {
        height: 1;
        padding: 0 1;
    }
    IssueLinkField:focus {
        background: $accent 20%;
    }
    """

    def __init__(self, url: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.url = url

    def render(self) -> str:
        return f"  [b]Issue:[/b] {self.url}  [dim](Enter to open)[/dim]"

    def on_key(self, event) -> None:
        if event.key == "enter":
            webbrowser.open(self.url)
            event.prevent_default()
            event.stop()
        elif event.key == "down":
            _focus_neighbor(self, 1)
            event.prevent_default()
            event.stop()
        elif event.key == "up":
            _focus_neighbor(self, -1)
            event.prevent_default()
            event.stop()


class PullRequestLinkField(Static):
    """Focusable pull request URL field. Press Enter to open in browser."""

    can_focus = True

    DEFAULT_CSS = """
    PullRequestLinkField {
        height: 1;
        padding: 0 1;
    }
    PullRequestLinkField:focus {
        background: $accent 20%;
    }
    """

    def __init__(self, url: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.url = url

    def render(self) -> str:
        return f"  [b]Pull Request:[/b] {self.url}  [dim](Enter to open)[/dim]"

    def on_key(self, event) -> None:
        if event.key == "enter":
            webbrowser.open(self.url)
            event.prevent_default()
            event.stop()
        elif event.key == "down":
            _focus_neighbor(self, 1)
            event.prevent_default()
            event.stop()
        elif event.key == "up":
            _focus_neighbor(self, -1)
            event.prevent_default()
            event.stop()


class CommitLinkField(Static):
    """Clickable commit link that opens the commit page in a browser."""

    can_focus = True

    DEFAULT_CSS = """
    CommitLinkField {
        height: 1;
        padding: 0 1;
    }
    CommitLinkField:focus {
        background: $accent 20%;
    }
    """

    def __init__(
        self, commit: TaskCommitInfo, platform_info: Optional[PlatformInfo], **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.commit = commit
        self.platform_info = platform_info

    def render(self) -> str:
        c = self.commit
        date_short = c.date[:10] if c.date else ""
        hint = "  [dim](Enter to open)[/dim]" if self.platform_info else ""
        return (
            f"  [bold #7aa2f7]{c.hash}[/] {c.message}  [dim]{date_short}[/]{hint}"
        )

    def on_key(self, event) -> None:
        if event.key == "enter":
            if self.platform_info:
                url = self.platform_info.commit_url_template.format(
                    hash=self.commit.hash
                )
                webbrowser.open(url)
            event.prevent_default()
            event.stop()
        elif event.key == "down":
            _focus_neighbor(self, 1)
            event.prevent_default()
            event.stop()
        elif event.key == "up":
            _focus_neighbor(self, -1)
            event.prevent_default()
            event.stop()


class ChildTaskField(Static):
    """Clickable child task link that navigates within the detail pane."""

    can_focus = True

    DEFAULT_CSS = """
    ChildTaskField {
        height: 1;
        padding: 0 1;
    }
    ChildTaskField:focus {
        background: $accent 20%;
    }
    """

    def __init__(self, task: CompletedTask, **kwargs) -> None:
        super().__init__(**kwargs)
        self.completed_task = task

    def render(self) -> str:
        t = self.completed_task
        color = _type_color(t.issue_type)
        name = t.name.replace("_", " ")
        return f"  [bold #7aa2f7]t{t.task_id}[/] - {name}  [{color}]\\[{t.issue_type}][/]"

    def on_key(self, event) -> None:
        if event.key == "enter":
            # The detail pane listens for this to navigate
            pane = self._find_detail_pane()
            if pane:
                pane.show_task(self.completed_task.task_id, focus_after_render=True)
            event.prevent_default()
            event.stop()
        elif event.key == "down":
            _focus_neighbor(self, 1)
            event.prevent_default()
            event.stop()
        elif event.key == "up":
            _focus_neighbor(self, -1)
            event.prevent_default()
            event.stop()

    def _find_detail_pane(self) -> Optional["HistoryDetailPane"]:
        """Walk ancestors to find the HistoryDetailPane."""
        node = self.parent
        while node is not None:
            if isinstance(node, HistoryDetailPane):
                return node
            node = node.parent
        return None


class SiblingCountField(Static):
    """Shows sibling count, Enter or 's' opens the sibling picker modal."""

    can_focus = True

    DEFAULT_CSS = """
    SiblingCountField {
        height: 1;
        padding: 0 1;
    }
    SiblingCountField:focus {
        background: $accent 20%;
    }
    """

    def __init__(self, sibling_tasks: list[CompletedTask], **kwargs) -> None:
        super().__init__(**kwargs)
        self.sibling_tasks = sibling_tasks

    def render(self) -> str:
        count = len(self.sibling_tasks)
        if count == 0:
            return "  [dim]No siblings[/]"
        label = "sibling" if count == 1 else "siblings"
        return f"  {count} {label}  [dim](Enter or 's' to browse)[/dim]"

    def on_key(self, event) -> None:
        if event.key in ("enter", "s"):
            if self.sibling_tasks:
                self._open_picker()
            event.prevent_default()
            event.stop()
        elif event.key == "down":
            _focus_neighbor(self, 1)
            event.prevent_default()
            event.stop()
        elif event.key == "up":
            _focus_neighbor(self, -1)
            event.prevent_default()
            event.stop()

    def _open_picker(self) -> None:
        pane = self._find_detail_pane()
        if pane:

            def _on_pick(task_id: str | None) -> None:
                if task_id:
                    pane.show_task(task_id, focus_after_render=True)

            self.app.push_screen(SiblingPickerModal(self.sibling_tasks), _on_pick)

    def _find_detail_pane(self) -> Optional["HistoryDetailPane"]:
        node = self.parent
        while node is not None:
            if isinstance(node, HistoryDetailPane):
                return node
            node = node.parent
        return None


class AffectedFileField(Static):
    """Clickable file path that navigates back to the codebrowser."""

    can_focus = True

    DEFAULT_CSS = """
    AffectedFileField {
        height: 1;
        padding: 0 1;
    }
    AffectedFileField:focus {
        background: $accent 20%;
    }
    """

    def __init__(self, file_path: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.file_path = file_path

    def render(self) -> str:
        return f"  \U0001f4c4 {self.file_path}  [dim](Enter to open)[/dim]"

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.post_message(NavigateToFile(self.file_path))
            event.prevent_default()
            event.stop()
        elif event.key == "down":
            _focus_neighbor(self, 1)
            event.prevent_default()
            event.stop()
        elif event.key == "up":
            _focus_neighbor(self, -1)
            event.prevent_default()
            event.stop()


class _BackButton(Static):
    """Navigation back button at the top of the detail pane."""

    can_focus = True

    DEFAULT_CSS = """
    _BackButton {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    _BackButton:focus {
        background: $accent 20%;
    }
    """

    def __init__(self, previous_task_id: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.previous_task_id = previous_task_id

    def render(self) -> str:
        return f"\u25c0 Back to t{self.previous_task_id}"

    def on_key(self, event) -> None:
        if event.key == "enter":
            pane = self._find_detail_pane()
            if pane:
                pane.go_back()
            event.prevent_default()
            event.stop()
        elif event.key == "down":
            _focus_neighbor(self, 1)
            event.prevent_default()
            event.stop()
        elif event.key == "up":
            _focus_neighbor(self, -1)
            event.prevent_default()
            event.stop()

    def _find_detail_pane(self) -> Optional["HistoryDetailPane"]:
        node = self.parent
        while node is not None:
            if isinstance(node, HistoryDetailPane):
                return node
            node = node.parent
        return None


class _SectionHeader(Static):
    """Non-focusable section header."""

    DEFAULT_CSS = """
    _SectionHeader {
        height: 1;
        margin-top: 1;
        padding: 0 1;
        text-style: bold;
        color: $text;
        background: $surface-lighten-1;
    }
    """


class _ViewIndicator(Static):
    """Shows whether viewing task or plan content."""

    DEFAULT_CSS = """
    _ViewIndicator {
        height: 1;
        padding: 0 1;
        text-style: italic;
        color: $text-muted;
    }
    """


# ---------------------------------------------------------------------------
# SiblingPickerModal
# ---------------------------------------------------------------------------


class _SiblingItem(Static):
    """A selectable sibling task in the picker modal."""

    can_focus = True

    DEFAULT_CSS = """
    _SiblingItem {
        height: 1;
        padding: 0 1;
    }
    _SiblingItem:focus {
        background: $accent 20%;
    }
    """

    def __init__(self, task: CompletedTask, **kwargs) -> None:
        super().__init__(**kwargs)
        self.completed_task = task

    def render(self) -> str:
        t = self.completed_task
        color = _type_color(t.issue_type)
        name = t.name.replace("_", " ")
        labels = _format_labels(t.labels)
        return f"  [bold #7aa2f7]t{t.task_id}[/]  {name}  [{color}]\\[{t.issue_type}][/]  {labels}"

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.screen.dismiss(self.completed_task.task_id)
            event.prevent_default()
            event.stop()
        elif event.key == "down":
            _focus_neighbor(self, 1)
            event.prevent_default()
            event.stop()
        elif event.key == "up":
            # If first item, move focus back to search input
            parent = self.parent
            if parent is not None:
                focusable = [
                    w for w in parent.children
                    if w.can_focus and w.display and w.styles.display != "none"
                ]
                try:
                    idx = focusable.index(self)
                except ValueError:
                    idx = 1
                if idx == 0:
                    modal = self.screen
                    if isinstance(modal, SiblingPickerModal):
                        modal.query_one("#sibling_search", Input).focus()
                    event.prevent_default()
                    event.stop()
                    return
            _focus_neighbor(self, -1)
            event.prevent_default()
            event.stop()


class SiblingPickerModal(ModalScreen[str | None]):
    """Modal dialog for browsing sibling tasks with fuzzy search."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close"),
    ]

    DEFAULT_CSS = """
    SiblingPickerModal {
        align: center middle;
    }
    #sibling_picker_dialog {
        width: 60%;
        max-height: 50%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #sibling_search {
        margin-bottom: 0;
    }
    #sibling_keybind_help {
        height: 1;
        padding: 0 1;
        color: $text-muted;
        margin-bottom: 1;
    }
    #sibling_list {
        height: 1fr;
    }
    """

    def __init__(self, siblings: list[CompletedTask]) -> None:
        super().__init__()
        self._siblings = siblings
        self._filtered = list(siblings)

    def compose(self):
        with Container(id="sibling_picker_dialog"):
            yield Input(placeholder="Search siblings...", id="sibling_search")
            yield Static(
                "[dim]\\[Up/Down] navigate  \\[Enter] select  \\[Esc] cancel[/]",
                id="sibling_keybind_help",
            )
            yield VerticalScroll(id="sibling_list")

    def on_mount(self) -> None:
        self._refresh_list()
        self.query_one("#sibling_search", Input).focus()

    def on_key(self, event) -> None:
        """Handle Down arrow from Input to move focus to first sibling item."""
        if event.key == "down":
            focused = self.focused
            if isinstance(focused, Input) and focused.id == "sibling_search":
                container = self.query_one("#sibling_list", VerticalScroll)
                items = list(container.query(_SiblingItem))
                if items:
                    items[0].focus()
                    items[0].scroll_visible()
                    event.prevent_default()
                    event.stop()

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.lower()
        self._filtered = [
            s for s in self._siblings if query in s.name.lower()
        ]
        self._refresh_list()

    def _refresh_list(self) -> None:
        container = self.query_one("#sibling_list", VerticalScroll)
        for item in container.query(_SiblingItem):
            item.remove()
        for task in self._filtered:
            container.mount(_SiblingItem(task))

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# HistoryDetailPane
# ---------------------------------------------------------------------------


class HistoryDetailPane(VerticalScroll):
    """Right-side detail pane showing full info for a selected completed task."""

    BINDINGS = [
        Binding("v", "toggle_view", "Toggle task/plan", show=False),
        Binding("V", "toggle_view", "Toggle task/plan", show=False),
    ]

    DEFAULT_CSS = """
    HistoryDetailPane {
        background: $surface;
    }
    HistoryDetailPane #detail_placeholder {
        color: $text-muted;
        text-align: center;
        margin-top: 4;
    }
    HistoryDetailPane .body-markdown {
        margin: 0 1;
    }
    """

    def __init__(self, project_root: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._project_root: Path | None = project_root
        self._nav_stack: list[str] = []
        self._task_index: list[CompletedTask] = []
        self._platform_info: PlatformInfo | None = None
        self._showing_plan = False
        self._task_content_cache: dict[str, str | None] = {}
        self._plan_content_cache: dict[str, str | None] = {}
        self._body_md = None  # reference to current Markdown widget

    def compose(self):
        yield Static(
            "Select a task from the list\nto view details",
            id="detail_placeholder",
        )

    def set_context(
        self,
        project_root: Path,
        task_index: list[CompletedTask],
        platform_info: PlatformInfo | None,
    ) -> None:
        """Set shared context after data loading completes."""
        self._project_root = project_root
        self._task_index = task_index
        self._platform_info = platform_info

    def show_task(
        self,
        task_id: str,
        is_explicit_browse: bool = True,
        focus_after_render: bool = False,
    ) -> None:
        """Load and display task details. Pushes onto navigation stack."""
        self._nav_stack.append(task_id)
        if is_explicit_browse:
            self.post_message(HistoryBrowseEvent(task_id))
        self._showing_plan = False
        self._load_and_render(task_id, focus_after_render)

    def go_back(self) -> None:
        """Pop navigation stack, show previous task (no browse event)."""
        if len(self._nav_stack) > 1:
            self._nav_stack.pop()
            prev = self._nav_stack[-1]
            self._showing_plan = False
            self._render_task(prev)
            self._focus_first_field()

    def _focus_first_field(self) -> None:
        """Focus the first focusable field in this pane."""
        for child in self.children:
            if child.can_focus and child.display and child.styles.display != "none":
                child.focus()
                child.scroll_visible()
                return

    def clear_stack(self) -> None:
        """Reset navigation stack."""
        self._nav_stack.clear()

    @work(thread=True)
    def _load_and_render(self, task_id: str, focus_after: bool = False) -> None:
        """Load commit and content data in a worker thread, then render."""
        if self._project_root is None:
            return

        # Pre-load content if not cached
        if task_id not in self._task_content_cache:
            self._task_content_cache[task_id] = load_task_content(
                self._project_root, task_id
            )
        if task_id not in self._plan_content_cache:
            self._plan_content_cache[task_id] = load_plan_content(
                self._project_root, task_id
            )

        # Load commits (always fresh — not cached)
        commits = find_commits_for_task(task_id, self._project_root)

        # Schedule UI update on the main thread
        self.app.call_from_thread(self._render_task, task_id, commits, focus_after)

    def _render_task(
        self,
        task_id: str,
        commits: list[TaskCommitInfo] | None = None,
        focus_after: bool = False,
    ) -> None:
        """Clear and rebuild all sections for the given task."""
        # Remove all children synchronously to avoid DuplicateIds on re-mount
        self.remove_children()

        # Find the CompletedTask in the index
        task = self._find_task(task_id)
        if task is None:
            self.mount(Static(f"Task t{task_id} not found in index", id="detail_placeholder"))
            return

        meta = task.metadata
        is_child = "_" in task_id

        # -- Back button --
        if len(self._nav_stack) > 1:
            prev_id = self._nav_stack[-2]
            self.mount(_BackButton(prev_id))

        # -- Title --
        name = task.name.replace("_", " ")
        self.mount(
            Static(
                f"[bold]t{task_id}[/bold]  {name}",
                classes="detail-title",
            )
        )

        # -- Metadata block --
        self.mount(_SectionHeader("Metadata"))
        self.mount(MetadataField(f"  [b]Priority:[/b] {task.priority}"))
        self.mount(MetadataField(f"  [b]Effort:[/b] {task.effort}"))
        self.mount(
            MetadataField(
                f"  [b]Type:[/b] [{_type_color(task.issue_type)}]{task.issue_type}[/]"
            )
        )
        if task.labels:
            self.mount(MetadataField(f"  [b]Labels:[/b] {_format_labels(task.labels)}"))
        if task.commit_date:
            self.mount(MetadataField(f"  [b]Commit date:[/b] {task.commit_date[:10]}"))

        # -- Issue / PR links --
        issue_url = meta.get("issue", "")
        if issue_url:
            self.mount(IssueLinkField(issue_url))
        pr_url = meta.get("pull_request", "")
        if pr_url:
            self.mount(PullRequestLinkField(pr_url))

        # -- Commits --
        if commits:
            self.mount(_SectionHeader(f"Commits ({len(commits)})"))
            for commit in commits:
                self.mount(CommitLinkField(commit, self._platform_info))

        # -- Children (for parent tasks) --
        if not is_child:
            children = find_child_tasks(task_id, self._task_index)
            if children:
                self.mount(_SectionHeader(f"Children ({len(children)})"))
                for child_task in children:
                    self.mount(ChildTaskField(child_task))

        # -- Siblings (for child tasks) --
        if is_child:
            siblings = find_sibling_tasks(task_id, self._task_index)
            self.mount(_SectionHeader("Siblings"))
            self.mount(SiblingCountField(siblings))

        # -- Affected files --
        if commits:
            # Collect unique files across all commits, preserving order
            seen: set[str] = set()
            all_files: list[str] = []
            for commit in commits:
                for f in commit.affected_files:
                    if f not in seen:
                        seen.add(f)
                        all_files.append(f)
            if all_files:
                self.mount(_SectionHeader(f"Affected Files ({len(all_files)})"))
                for fpath in all_files:
                    self.mount(AffectedFileField(fpath))

        # -- Body (task/plan content) --
        self.mount(_SectionHeader("Description"))
        self.mount(
            _ViewIndicator(
                "[b]Viewing:[/b] Task  [dim](press 'v' to toggle plan)[/dim]"
            )
        )

        content = self._get_body_content(task_id)
        md = Markdown(content or "*No content available*", classes="body-markdown")
        self._body_md = md
        self.mount(md)

        self.scroll_home(animate=False)

        if focus_after:
            self._focus_first_field()

    def _get_body_content(self, task_id: str) -> str | None:
        """Return task or plan content based on current toggle state."""
        if self._showing_plan:
            raw = self._plan_content_cache.get(task_id)
            if raw:
                return self._strip_frontmatter(raw)
            return None
        else:
            raw = self._task_content_cache.get(task_id)
            if raw:
                return self._strip_frontmatter(raw)
            return None

    @staticmethod
    def _strip_frontmatter(text: str) -> str:
        """Strip YAML frontmatter from markdown content."""
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()
        return text

    def action_toggle_view(self) -> None:
        """Toggle between task content and plan content."""
        if not self._nav_stack:
            return
        task_id = self._nav_stack[-1]

        # Check if plan content is available
        plan_content = self._plan_content_cache.get(task_id)
        if plan_content is None and not self._showing_plan:
            self.app.notify("No plan file found", severity="warning")
            return

        self._showing_plan = not self._showing_plan

        # Update indicator
        indicators = self.query(_ViewIndicator)
        for ind in indicators:
            if self._showing_plan:
                ind.update("[b]Viewing:[/b] [#FFB86C]Plan[/]  [dim](press 'v' to toggle task)[/dim]")
            else:
                ind.update("[b]Viewing:[/b] Task  [dim](press 'v' to toggle plan)[/dim]")

        # Update markdown body
        content = self._get_body_content(task_id)
        if self._body_md is not None:
            self._body_md.update(content or "*No content available*")

    def _find_task(self, task_id: str) -> CompletedTask | None:
        """Find a task in the index by ID."""
        for t in self._task_index:
            if t.task_id == task_id:
                return t
        return None

    def on_markdown_link_clicked(self, event: Markdown.LinkClicked) -> None:
        """Open markdown links in browser."""
        webbrowser.open(event.href)
        event.prevent_default()
        event.stop()
