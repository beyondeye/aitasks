---
Task: t439_4_brainstorm_status_tab.md
Parent Task: aitasks/t439_agentcrew_logging.md
Sibling Tasks: aitasks/t439/t439_1_runner_log_capture.md, aitasks/t439/t439_2_shared_log_utils.md, aitasks/t439/t439_3_dashboard_log_browser.md
Archived Sibling Plans: aiplans/archived/p439/p439_*_*.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

## Plan: Brainstorm TUI Status Tab

### Context
The brainstorm TUI's Status tab (tab 5) is currently a placeholder at `brainstorm_app.py:627-634`. This task populates it with agent status monitoring and log browsing, reusing the shared log utilities from t439_2. The brainstorm_app.py already imports `crew_worktree` from brainstorm_session to get the worktree path.

### Changes to `.aitask-scripts/brainstorm/brainstorm_app.py`

#### 1. Add imports (after existing imports at top)

```python
from agentcrew.agentcrew_log_utils import (
    list_agent_logs, read_log_tail, read_log_full, format_log_size,
)
from agentcrew.agentcrew_utils import (
    check_agent_alive, format_elapsed, list_agent_files,
    read_yaml, _parse_timestamp,
)
```

#### 2. Add `LogDetailModal` (after existing modal classes, ~line 268)

Modal screen for viewing log content. Pattern: follow `NodeDetailModal`.

```python
class LogDetailModal(ModalScreen):
    """Modal to view agent log file content."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close"),
        Binding("r", "refresh", "Refresh"),
        Binding("t", "show_tail", "Tail"),
        Binding("f", "show_full", "Full"),
    ]

    def __init__(self, log_path: str, agent_name: str) -> None:
        super().__init__()
        self.log_path = log_path
        self.agent_name = agent_name
        self._mode = "tail"

    def compose(self) -> ComposeResult:
        with Container(id="log_modal_container"):
            yield Label(f"Log: {self.agent_name}", id="log_modal_title")
            yield Label("", id="log_modal_info")
            yield VerticalScroll(Label("Loading...", id="log_modal_content"), id="log_modal_scroll")

    def on_mount(self) -> None:
        self._load_content()

    def _load_content(self) -> None:
        import os
        size = format_log_size(os.path.getsize(self.log_path)) if os.path.isfile(self.log_path) else "0 B"
        self.query_one("#log_modal_info", Label).update(f"Size: {size}  Mode: {self._mode}  [t=tail, f=full, r=refresh]")
        if self._mode == "tail":
            content = read_log_tail(self.log_path) or "(empty)"
        else:
            content = read_log_full(self.log_path) or "(empty)"
        self.query_one("#log_modal_content", Label).update(content)

    def action_dismiss_modal(self) -> None:
        self.dismiss()

    def action_refresh(self) -> None:
        self._load_content()

    def action_show_tail(self) -> None:
        self._mode = "tail"
        self._load_content()

    def action_show_full(self) -> None:
        self._mode = "full"
        self._load_content()
```

Add CSS for the modal (in the app CSS):
```css
#log_modal_container {
    width: 90%;
    height: 85%;
    background: $surface;
    border: solid $primary;
    padding: 1 2;
}
#log_modal_scroll {
    height: 1fr;
}
```

#### 3. Add `StatusAgentRow` widget

Focusable row for agent status display in the Status tab.

```python
class StatusAgentRow(Static, can_focus=True):
    """Agent status row in the brainstorm Status tab."""

    def __init__(self, name: str, data: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent_name = name
        self.agent_data = data

    def render(self) -> str:
        d = self.agent_data
        status = d.get("status", "Unknown")
        # Color map (reuse from agentcrew dashboard convention)
        colors = {"Running": "#50FA7B", "Error": "#FF5555", "Completed": "#6272A4",
                  "Waiting": "#BD93F9", "Ready": "#BD93F9", "Paused": "#FFB86C"}
        color = colors.get(status, "#888888")
        hb = d.get("heartbeat", "")
        hb_str = ""
        if hb:
            ts = _parse_timestamp(str(hb))
            if ts:
                from datetime import datetime, timezone
                elapsed = (datetime.now(timezone.utc) - ts).total_seconds()
                hb_str = f"  ♥ {format_elapsed(elapsed)} ago"
        msg = d.get("last_message", "")
        msg_str = f"  {msg}" if msg else ""
        atype = d.get("agent_type", "")
        type_label = f" ({atype})" if atype else ""
        return f"[{color}]●[/{color}] {self.agent_name}{type_label}  [{color}]{status}[/{color}]{hb_str}{msg_str}"
```

#### 4. Add `StatusLogRow` widget

Focusable row for log file entries in the Status tab.

```python
class StatusLogRow(Static, can_focus=True):
    """Log file entry row in the brainstorm Status tab."""

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
        size = format_log_size(d["size"])
        return f"  📄 {d['name']}  [{size}]  Updated: {d['mtime_str']}"

    def on_focus(self) -> None:
        self.post_message(self.Selected(self.log_info["path"], self.log_info["name"]))
```

#### 5. Replace Status tab placeholder (lines 627-634)

Replace:
```python
            with TabPane("Status", id="tab_status"):
                yield VerticalScroll(
                    Label(
                        "Status \u2014 coming in follow-up tasks",
                        id="status_placeholder",
                    ),
                    id="status_content",
                )
```

With:
```python
            with TabPane("Status", id="tab_status"):
                yield VerticalScroll(id="status_content")
```

#### 6. Add `_refresh_status_tab()` method to `BrainstormApp`

Called on mount and via set_interval(5.0). Only refreshes when Status tab is active.

```python
async def _refresh_status_tab(self) -> None:
    """Refresh the Status tab with agent status and log list."""
    tabbed = self.query_one(TabbedContent)
    if tabbed.active != "tab_status":
        return

    wt_path = str(crew_worktree(self.task_num))
    if not os.path.isdir(wt_path):
        return

    container = self.query_one("#status_content", VerticalScroll)
    await container.remove_children()

    # Agent status section
    await container.mount(Label("[bold]Agent Status[/bold]", classes="status_section_title"))

    for status_file in sorted(Path(wt_path).glob("*_status.yaml")):
        data = read_yaml(str(status_file))
        name = data.get("agent_name", "")
        if not name:
            continue
        alive_path = os.path.join(wt_path, f"{name}_alive.yaml")
        alive_data = read_yaml(alive_path) if os.path.isfile(alive_path) else {}
        agent_info = {
            "status": data.get("status", "Unknown"),
            "agent_type": data.get("agent_type", ""),
            "heartbeat": alive_data.get("last_heartbeat", ""),
            "last_message": alive_data.get("last_message", ""),
        }
        await container.mount(StatusAgentRow(name, agent_info))

    # Log files section
    await container.mount(Label(""))
    await container.mount(Label("[bold]Agent Logs[/bold]  (Enter to view)", classes="status_section_title"))

    logs = list_agent_logs(wt_path)
    if not logs:
        await container.mount(Label("  No log files yet"))
    else:
        for log_info in logs:
            await container.mount(StatusLogRow(log_info))
```

#### 7. Wire up refresh and log opening

- In `on_mount()` or `_load_existing_session()`, call `self.set_interval(5.0, self._refresh_status_tab)`
- Add handler for `StatusLogRow.Selected` message to track selected log
- Add Enter handler for Status tab: when a `StatusLogRow` is focused, push `LogDetailModal`
- Handle the Enter key in `on_key()`: check if focused widget is `StatusLogRow`, open modal

#### 8. Add CSS for status rows

```python
StatusAgentRow { height: 1; padding: 0 1; }
StatusLogRow { height: 1; padding: 0 1; }
StatusLogRow:focus { background: $accent 20%; }
```

### Verification
1. `ait brainstorm init <task_num>` → initialize session
2. Launch an explore from Actions tab
3. Switch to Status tab (press `5`)
4. Verify agent statuses are listed with colors and heartbeat
5. Verify log files appear below, sorted by mtime
6. Press Enter on a log → modal opens with content
7. Press `t`/`f`/`r` in modal for tail/full/refresh
8. Verify auto-refresh updates the display every 5s

### Step 9: Post-Implementation
Archive task, commit, push per standard workflow.
