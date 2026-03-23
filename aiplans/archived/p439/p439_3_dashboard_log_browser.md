---
Task: t439_3_dashboard_log_browser.md
Parent Task: aitasks/t439_agentcrew_logging.md
Sibling Tasks: aitasks/t439/t439_1_runner_log_capture.md, aitasks/t439/t439_2_shared_log_utils.md, aitasks/t439/t439_4_brainstorm_status_tab.md
Archived Sibling Plans: aiplans/archived/p439/p439_*_*.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

## Plan: Dashboard Log Browser

### Context
The AgentCrew dashboard TUI (`agentcrew_dashboard.py`) shows crew/agent status but cannot view agent execution logs. This adds log browsing screens accessible via keybinding from the crew detail view.

### Changes to `.aitask-scripts/agentcrew/agentcrew_dashboard.py`

#### 1. Add imports (top of file, after existing imports)

```python
from agentcrew.agentcrew_log_utils import (
    list_agent_logs, read_log_tail, read_log_full, format_log_size,
)
```

#### 2. Add `LogEntry` widget (after `AgentCard` class, ~line 328)

Focusable row widget displaying one log file entry. Pattern: follow `AgentCard`.

```python
class LogEntry(Static, can_focus=True):
    """Displays a single agent log file entry."""

    class Selected(Message):
        def __init__(self, log_path: str, agent_name: str) -> None:
            super().__init__()
            self.log_path = log_path
            self.agent_name = agent_name

    def __init__(self, log_info: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self.log_info = log_info

    def render(self) -> str:
        d = self.log_info
        name = d["name"]
        size = format_log_size(d["size"])
        mtime = d["mtime_str"]
        return f"  {name}  [{size}]  Last updated: {mtime}"

    def on_focus(self) -> None:
        self.post_message(self.Selected(self.log_info["path"], self.log_info["name"]))
```

#### 3. Add `LogViewScreen` (after `LogEntry`)

Screen showing a single log file's content.

```python
class LogViewScreen(Screen):
    """View the content of a single agent log file."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("t", "show_tail", "Tail"),
        Binding("f", "show_full", "Full"),
    ]

    CSS = """
    LogViewScreen { layout: vertical; }
    #log-header { height: 2; background: $surface; padding: 0 2; }
    #log-content { height: 1fr; }
    """

    def __init__(self, log_path: str, agent_name: str) -> None:
        super().__init__()
        self.log_path = log_path
        self.agent_name = agent_name
        self._mode = "tail"  # "tail" or "full"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(f"Log: {self.agent_name}", id="log-header")
        yield VerticalScroll(Label("Loading...", id="log-text"), id="log-content")
        yield Footer()

    def on_mount(self) -> None:
        self._load_content()

    def _load_content(self) -> None:
        size = format_log_size(os.path.getsize(self.log_path)) if os.path.isfile(self.log_path) else "0 B"
        self.query_one("#log-header", Label).update(
            f"[bold]{self.agent_name}[/bold]  ({size})  Mode: {self._mode}"
        )
        if self._mode == "tail":
            content = read_log_tail(self.log_path) or "(empty)"
        else:
            content = read_log_full(self.log_path) or "(empty)"
        self.query_one("#log-text", Label).update(content)

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_refresh(self) -> None:
        self._load_content()
        self.notify("Refreshed")

    def action_show_tail(self) -> None:
        self._mode = "tail"
        self._load_content()

    def action_show_full(self) -> None:
        self._mode = "full"
        self._load_content()
```

#### 4. Add `LogBrowserScreen` (after `LogViewScreen`)

```python
class LogBrowserScreen(Screen):
    """Browse agent log files for a crew."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("enter", "open_log", "View"),
        Binding("f5", "refresh", "Refresh"),
    ]

    CSS = """
    LogBrowserScreen { layout: vertical; }
    #logs-header { height: 2; background: $surface; padding: 0 2; }
    #logs-list { height: 1fr; }
    LogEntry { height: 1; padding: 0 1; }
    LogEntry:focus { background: $accent 20%; }
    """

    def __init__(self, crew_id: str, manager: CrewManager) -> None:
        super().__init__()
        self.crew_id = crew_id
        self.manager = manager
        self.selected_path = ""
        self.selected_name = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(f"Agent Logs — {self.crew_id}", id="logs-header")
        yield VerticalScroll(id="logs-list")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_list()
        self.set_interval(5.0, self._refresh_list)

    async def _refresh_list(self) -> None:
        from agentcrew.agentcrew_utils import crew_worktree_path
        wt = crew_worktree_path(self.crew_id)
        logs = list_agent_logs(wt)

        container = self.query_one("#logs-list", VerticalScroll)
        await container.remove_children()

        if not logs:
            await container.mount(Label("  No log files found"))
            return

        for log_info in logs:
            await container.mount(LogEntry(log_info))

    @on(LogEntry.Selected)
    def on_log_selected(self, event: LogEntry.Selected) -> None:
        self.selected_path = event.log_path
        self.selected_name = event.agent_name

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_open_log(self) -> None:
        if self.selected_path:
            self.app.push_screen(LogViewScreen(self.selected_path, self.selected_name))

    async def action_refresh(self) -> None:
        await self._refresh_list()
        self.notify("Refreshed")
```

#### 5. Add keybinding to `CrewDetailScreen` (line 402)

Add to BINDINGS list:
```python
Binding("l", "view_logs", "Logs"),
```

Add action method:
```python
def action_view_logs(self) -> None:
    self.app.push_screen(LogBrowserScreen(self.crew_id, self.manager))
```

### Verification
1. Open `ait crew dashboard`, navigate to a crew that has run agents
2. Press `l` in crew detail → log browser opens
3. Verify logs listed sorted by mtime
4. Press Enter → log view opens with tail content
5. Press `f` for full, `t` for tail, `r` to refresh
6. Press escape to navigate back

## Final Implementation Notes
- **Actual work done:** All 5 planned changes implemented — log utils import, `LogEntry` widget, `LogViewScreen`, `LogBrowserScreen`, and `CrewDetailScreen` keybinding/action. Exactly as specified in the plan.
- **Deviations from plan:** Removed the redundant local `from agentcrew.agentcrew_utils import crew_worktree_path` import in `LogBrowserScreen._refresh_list` since `crew_worktree_path` is already imported at the top of the file. Also adjusted the top-level import from `agentcrew.agentcrew_log_utils` to `agentcrew_log_utils` (relative import matching the existing pattern in the dashboard file).
- **Issues encountered:** None
- **Key decisions:** Used existing top-level `crew_worktree_path` import instead of adding a redundant local import. Followed `AgentCard` widget pattern exactly for `LogEntry`.
- **Notes for sibling tasks:** The `LogEntry` widget, `LogViewScreen`, and `LogBrowserScreen` are available as reference patterns for t439_4 (brainstorm TUI). The import pattern is `from agentcrew_log_utils import ...` (not `from agentcrew.agentcrew_log_utils`). Log browser uses 5-second auto-refresh. The `LogViewScreen` accepts `log_path` and `agent_name` constructor args and supports tail/full modes — the brainstorm `LogDetailModal` can follow the same approach.

### Step 9: Post-Implementation
Archive task, commit, push per standard workflow.
