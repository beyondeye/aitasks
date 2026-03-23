"""AgentCrew TUI Dashboard: monitor and manage agentcrews with Textual."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure agentcrew package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agentcrew_utils import (
    AGENT_STATUSES,
    AGENTCREW_DIR,
    CREW_STATUSES,
    check_agent_alive,
    crew_worktree_path,
    format_elapsed,
    get_agent_names,
    list_agent_files,
    list_crews,
    read_yaml,
    topo_sort,
    _parse_timestamp,
)
from agentcrew_log_utils import (
    list_agent_logs,
    read_log_tail,
    read_log_full,
    format_log_size,
)

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ProgressBar, Static
from textual import on

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AIT_PATH = str(Path(__file__).resolve().parent.parent.parent / "ait")

STATUS_COLORS = {
    "Running": "#50FA7B",
    "Error": "#FF5555",
    "Aborted": "#FF5555",
    "Waiting": "#BD93F9",
    "Initializing": "#BD93F9",
    "Ready": "#BD93F9",
    "Completed": "#6272A4",
    "Paused": "#FFB86C",
    "Killing": "#FF7979",
    "Unknown": "#888888",
}

RUNNER_STALE_SECONDS = 120  # Consider runner stale after 2 minutes without heartbeat


# ---------------------------------------------------------------------------
# Data Layer
# ---------------------------------------------------------------------------


def _elapsed_since(ts_str: str) -> float | None:
    """Return seconds elapsed since a timestamp string, or None."""
    ts = _parse_timestamp(str(ts_str))
    if ts is None:
        return None
    return (datetime.now(timezone.utc) - ts).total_seconds()


def _heartbeat_age(ts_str: str) -> str:
    """Return a human-readable heartbeat age string."""
    elapsed = _elapsed_since(ts_str)
    if elapsed is None:
        return "never"
    return f"{format_elapsed(elapsed)} ago"


def _read_file_preview(path: str, max_lines: int = 5) -> str:
    """Read first N lines of a text file for preview."""
    if not os.path.isfile(path):
        return ""
    lines = []
    with open(path) as f:
        for i, line in enumerate(f):
            if i >= max_lines:
                lines.append("...")
                break
            lines.append(line.rstrip())
    return "\n".join(lines)


class CrewManager:
    """Thin wrapper around agentcrew_utils for TUI data needs."""

    def refresh_all(self) -> list[dict]:
        """Return list of all crews with summary info."""
        return list_crews()

    def load_crew(self, crew_id: str) -> dict | None:
        """Load full crew data including all agents."""
        wt = crew_worktree_path(crew_id)
        if not os.path.isdir(wt):
            return None

        meta_path = os.path.join(wt, "_crew_meta.yaml")
        status_path = os.path.join(wt, "_crew_status.yaml")
        runner_path = os.path.join(wt, "_runner_alive.yaml")

        meta = read_yaml(meta_path) if os.path.isfile(meta_path) else {}
        status_data = read_yaml(status_path) if os.path.isfile(status_path) else {}
        runner_data = read_yaml(runner_path) if os.path.isfile(runner_path) else {}

        # Load all agents
        agents = {}
        for status_file in list_agent_files(wt, "_status.yaml"):
            data = read_yaml(status_file)
            name = data.get("agent_name", "")
            if not name:
                continue

            alive_path = os.path.join(wt, f"{name}_alive.yaml")
            alive_data = read_yaml(alive_path) if os.path.isfile(alive_path) else {}

            agents[name] = {
                "status": data.get("status", "Unknown"),
                "agent_type": data.get("agent_type", ""),
                "group": data.get("group", ""),
                "depends_on": data.get("depends_on", []),
                "progress": data.get("progress", 0),
                "started_at": data.get("started_at", ""),
                "completed_at": data.get("completed_at", ""),
                "pid": data.get("pid"),
                "error_message": data.get("error_message"),
                "heartbeat": alive_data.get("last_heartbeat", ""),
                "last_message": alive_data.get("last_message", ""),
                "work2do_preview": _read_file_preview(
                    os.path.join(wt, f"{name}_work2do.md")
                ),
                "output_preview": _read_file_preview(
                    os.path.join(wt, f"{name}_output.md")
                ),
            }

        # Compute topo order
        dep_graph = {name: a.get("depends_on", []) for name, a in agents.items()}
        try:
            topo_order = topo_sort(dep_graph)
        except ValueError:
            topo_order = sorted(agents.keys())

        # Compute per-type concurrency
        agent_types = meta.get("agent_types", {})
        type_counts: dict[str, dict] = {}
        for name, a in agents.items():
            atype = a["agent_type"]
            if atype not in type_counts:
                type_counts[atype] = {"running": 0, "max": 0}
                if atype in agent_types:
                    type_counts[atype]["max"] = agent_types[atype].get("max_parallel", 0)
            if a["status"] == "Running":
                type_counts[atype]["running"] += 1

        return {
            "id": crew_id,
            "name": meta.get("name", crew_id),
            "meta": meta,
            "status": status_data.get("status", "Unknown"),
            "progress": status_data.get("progress", 0),
            "created_at": meta.get("created_at", ""),
            "started_at": status_data.get("started_at", ""),
            "updated_at": status_data.get("updated_at", ""),
            "runner": {
                "status": runner_data.get("status", ""),
                "hostname": runner_data.get("hostname", ""),
                "heartbeat": runner_data.get("last_heartbeat", ""),
                "pid": runner_data.get("pid"),
                "requested_action": runner_data.get("requested_action"),
            },
            "agents": agents,
            "topo_order": topo_order,
            "type_counts": type_counts,
        }

    def get_runner_info(self, crew_id: str) -> dict:
        """Get runner status information."""
        wt = crew_worktree_path(crew_id)
        runner_path = os.path.join(wt, "_runner_alive.yaml")
        if not os.path.isfile(runner_path):
            return {"status": "none", "hostname": "", "heartbeat": "", "stale": True}

        data = read_yaml(runner_path)
        hb = data.get("last_heartbeat", "")
        elapsed = _elapsed_since(str(hb)) if hb else None
        stale = elapsed is None or elapsed > RUNNER_STALE_SECONDS

        return {
            "status": data.get("status", "unknown"),
            "hostname": data.get("hostname", ""),
            "heartbeat": hb,
            "stale": stale,
            "heartbeat_age": _heartbeat_age(str(hb)) if hb else "never",
        }

    def start_runner(self, crew_id: str) -> bool:
        """Launch a runner for the crew as a detached process."""
        try:
            subprocess.Popen(
                [AIT_PATH, "crew", "runner", "--crew", crew_id],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except OSError:
            return False

    def stop_runner(self, crew_id: str) -> bool:
        """Request runner to stop by sending stop command."""
        try:
            result = subprocess.run(
                [AIT_PATH, "crew", "command", "send-all", "--crew", crew_id,
                 "--command", "kill"],
                capture_output=True, text=True, timeout=10,
            )
            # Also update runner_alive.yaml requested_action
            wt = crew_worktree_path(crew_id)
            runner_path = os.path.join(wt, "_runner_alive.yaml")
            if os.path.isfile(runner_path):
                from agentcrew_utils import update_yaml_field
                update_yaml_field(runner_path, "requested_action", "stop")
            return True
        except (OSError, subprocess.TimeoutExpired):
            return False

    def send_command(self, crew_id: str, agent_name: str, command: str) -> bool:
        """Send a command to a specific agent."""
        try:
            result = subprocess.run(
                [AIT_PATH, "crew", "command", "send", "--crew", crew_id,
                 "--agent", agent_name, "--command", command],
                capture_output=True, text=True, timeout=10,
            )
            return "COMMAND_SENT:" in result.stdout
        except (OSError, subprocess.TimeoutExpired):
            return False

    def cleanup_crew(self, crew_id: str) -> bool:
        """Cleanup a completed crew's worktree."""
        try:
            result = subprocess.run(
                [AIT_PATH, "crew", "cleanup", "--crew", crew_id, "--batch"],
                capture_output=True, text=True, timeout=30,
            )
            return "CLEANED:" in result.stdout
        except (OSError, subprocess.TimeoutExpired):
            return False


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------


class AgentCard(Static, can_focus=True):
    """Displays a single agent's status in the detail view."""

    class Selected(Message):
        """Fired when an agent card is focused."""
        def __init__(self, agent_name: str) -> None:
            super().__init__()
            self.agent_name = agent_name

    def __init__(self, name: str, data: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent_name = name
        self.agent_data = data

    def render(self) -> str:
        d = self.agent_data
        status = d.get("status", "Unknown")
        color = STATUS_COLORS.get(status, "#888888")
        progress = d.get("progress", 0)
        atype = d.get("agent_type", "")
        deps = d.get("depends_on", [])

        # Progress bar as text
        bar_width = 10
        filled = int(bar_width * progress / 100) if progress else 0
        bar = "█" * filled + "░" * (bar_width - filled)

        # Heartbeat
        hb = d.get("heartbeat", "")
        hb_str = _heartbeat_age(str(hb)) if hb else ""

        # Last message from agent
        msg = d.get("last_message", "")
        msg_str = f"  {msg}" if msg else ""

        # Blocked-by info
        blocked = ""
        if status in ("Waiting", "Ready") and deps:
            blocked = f"  ⏳ Blocked by: {', '.join(deps)}"

        # Error message
        error = ""
        if status == "Error" and d.get("error_message"):
            error = f"  ⚠ {d['error_message']}"

        type_label = f" ({atype})" if atype else ""
        group = d.get("group", "")
        group_label = ""
        if group:
            g = group if len(group) <= 15 else group[:12] + "..."
            group_label = f" [{g}]"
        hb_label = f"  ♥ {hb_str}" if hb_str else ""

        return (
            f"[{color}]●[/{color}] {self.agent_name}{type_label}{group_label}  "
            f"[{color}]{status}[/{color}]  "
            f"{bar} {progress}%"
            f"{hb_label}{blocked}{error}{msg_str}"
        )

    def on_focus(self) -> None:
        self.post_message(self.Selected(self.agent_name))


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
        self._mode = "tail"

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


class CrewCard(Static, can_focus=True):
    """Displays a single crew in the list view."""

    class Selected(Message):
        """Fired when a crew card is activated."""
        def __init__(self, crew_id: str) -> None:
            super().__init__()
            self.crew_id = crew_id

    def __init__(self, crew_data: dict, runner_info: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self.crew_data = crew_data
        self.runner_info = runner_info

    def render(self) -> str:
        d = self.crew_data
        crew_id = d.get("id", "?")
        name = d.get("name", crew_id)
        status = d.get("status", "Unknown")
        color = STATUS_COLORS.get(status, "#888888")
        progress = d.get("progress", 0)
        agent_count = d.get("agent_count", 0)

        # Progress bar
        bar_width = 15
        filled = int(bar_width * progress / 100) if progress else 0
        bar = "█" * filled + "░" * (bar_width - filled)

        # Runner status
        ri = self.runner_info
        r_status = ri.get("status", "none")
        if r_status == "none":
            runner_label = "[dim]No runner[/dim]"
        elif ri.get("stale", True):
            runner_label = f"[#FF5555]Runner stale[/#FF5555] ({ri.get('hostname', '?')})"
        else:
            runner_label = (
                f"[#50FA7B]Runner active[/#50FA7B] "
                f"({ri.get('hostname', '?')}, {ri.get('heartbeat_age', '?')})"
            )

        # Elapsed time
        started = d.get("started_at", "")
        elapsed_str = ""
        if started:
            elapsed = _elapsed_since(str(started))
            if elapsed is not None:
                elapsed_str = f"  ⏱ {format_elapsed(elapsed)}"

        return (
            f"[bold]{crew_id}[/bold]  {name}  "
            f"[{color}]{status}[/{color}]  "
            f"{bar} {progress}%  "
            f"Agents: {agent_count}{elapsed_str}  "
            f"{runner_label}"
        )


# ---------------------------------------------------------------------------
# Detail Screen
# ---------------------------------------------------------------------------


class CrewDetailScreen(Screen):
    """Full detail view for a single agentcrew."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("r", "start_runner", "Start Runner"),
        Binding("k", "stop_runner", "Stop Runner"),
        Binding("l", "view_logs", "Logs"),
        Binding("p", "pause_agent", "Pause/Resume"),
        Binding("x", "kill_agent", "Kill Agent"),
        Binding("f5", "refresh", "Refresh"),
    ]

    CSS = """
    CrewDetailScreen {
        layout: vertical;
    }
    #detail-header {
        height: 3;
        background: $surface;
        padding: 0 2;
    }
    #detail-runner-bar {
        height: 1;
        background: $surface-darken-1;
        padding: 0 2;
    }
    #detail-concurrency {
        height: 1;
        background: $surface-darken-1;
        padding: 0 2;
    }
    #agent-list {
        height: 1fr;
        border-top: solid $primary;
    }
    #agent-detail-panel {
        height: 8;
        background: $surface;
        border-top: solid $accent;
        padding: 0 2;
        overflow-y: auto;
    }
    AgentCard {
        height: 1;
        padding: 0 1;
    }
    AgentCard:focus {
        background: $accent 20%;
    }
    """

    def __init__(self, crew_id: str, manager: CrewManager) -> None:
        super().__init__()
        self.crew_id = crew_id
        self.manager = manager
        self.crew_data: dict = {}
        self.selected_agent: str = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Loading...", id="detail-header")
        yield Label("", id="detail-runner-bar")
        yield Label("", id="detail-concurrency")
        yield VerticalScroll(id="agent-list")
        yield Label("", id="agent-detail-panel")
        yield Footer()

    def on_mount(self) -> None:
        self.call_later(self._refresh_data)
        self.set_interval(5.0, self._refresh_data)

    async def _refresh_data(self) -> None:
        data = self.manager.load_crew(self.crew_id)
        if data is None:
            self.query_one("#detail-header", Label).update("Crew not found")
            return

        self.crew_data = data
        status = data["status"]
        color = STATUS_COLORS.get(status, "#888888")
        progress = data["progress"]

        # Header
        bar_width = 20
        filled = int(bar_width * progress / 100) if progress else 0
        bar = "█" * filled + "░" * (bar_width - filled)

        elapsed_str = ""
        started = data.get("started_at", "")
        if started:
            elapsed = _elapsed_since(str(started))
            if elapsed is not None:
                elapsed_str = f"  ⏱ {format_elapsed(elapsed)}"

        header_text = (
            f"[bold]{data['name']}[/bold]  ({data['id']})  "
            f"[{color}]{status}[/{color}]  "
            f"{bar} {progress}%{elapsed_str}"
        )
        self.query_one("#detail-header", Label).update(header_text)

        # Runner bar
        runner = data.get("runner", {})
        r_status = runner.get("status", "")
        r_host = runner.get("hostname", "")
        r_hb = runner.get("heartbeat", "")
        r_action = runner.get("requested_action")

        if not r_status:
            runner_text = "[dim]Runner: not configured[/dim]"
        elif r_action == "stop":
            runner_text = f"[#FFB86C]Runner: stopping[/#FFB86C]  Host: {r_host}"
        else:
            hb_age = _heartbeat_age(str(r_hb)) if r_hb else "never"
            ri = self.manager.get_runner_info(self.crew_id)
            if ri.get("stale", True):
                runner_text = (
                    f"[#FF5555]Runner: stale[/#FF5555]  "
                    f"Host: {r_host}  Last heartbeat: {hb_age}"
                )
            else:
                runner_text = (
                    f"[#50FA7B]Runner: active[/#50FA7B]  "
                    f"Host: {r_host}  Heartbeat: {hb_age}"
                )

        self.query_one("#detail-runner-bar", Label).update(runner_text)

        # Per-type concurrency
        tc = data.get("type_counts", {})
        parts = []
        for atype, counts in tc.items():
            running = counts["running"]
            max_p = counts["max"]
            limit_str = str(max_p) if max_p > 0 else "∞"
            parts.append(f"{atype}: {running}/{limit_str}")
        conc_text = "  ".join(parts) if parts else ""
        self.query_one("#detail-concurrency", Label).update(conc_text)

        # Agent list
        agent_list = self.query_one("#agent-list", VerticalScroll)
        await agent_list.remove_children()

        agents = data.get("agents", {})
        topo_order = data.get("topo_order", sorted(agents.keys()))

        for name in topo_order:
            if name in agents:
                card = AgentCard(name, agents[name], id=f"agent-{name}")
                await agent_list.mount(card)

        # Restore selection if possible
        if self.selected_agent and self.selected_agent in agents:
            self._update_detail_panel(self.selected_agent)

    def _update_detail_panel(self, agent_name: str) -> None:
        agents = self.crew_data.get("agents", {})
        if agent_name not in agents:
            return

        d = agents[agent_name]
        lines = [f"[bold]{agent_name}[/bold]"]

        if d.get("started_at"):
            lines.append(f"Started: {d['started_at']}")
        if d.get("completed_at"):
            lines.append(f"Completed: {d['completed_at']}")
        if d.get("work2do_preview"):
            lines.append(f"Work: {d['work2do_preview'][:80]}")
        if d.get("output_preview"):
            lines.append(f"Output: {d['output_preview'][:80]}")

        self.query_one("#agent-detail-panel", Label).update("\n".join(lines))

    @on(AgentCard.Selected)
    def on_agent_selected(self, event: AgentCard.Selected) -> None:
        self.selected_agent = event.agent_name
        self._update_detail_panel(event.agent_name)

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_view_logs(self) -> None:
        self.app.push_screen(LogBrowserScreen(self.crew_id, self.manager))

    def action_start_runner(self) -> None:
        if self.manager.start_runner(self.crew_id):
            self.notify("Runner started")
        else:
            self.notify("Failed to start runner", severity="error")

    def action_stop_runner(self) -> None:
        if self.manager.stop_runner(self.crew_id):
            self.notify("Stop signal sent to runner")
        else:
            self.notify("Failed to stop runner", severity="error")

    def action_pause_agent(self) -> None:
        if not self.selected_agent:
            self.notify("No agent selected", severity="warning")
            return
        agents = self.crew_data.get("agents", {})
        agent = agents.get(self.selected_agent, {})
        status = agent.get("status", "")
        if status == "Running":
            cmd = "pause"
        elif status == "Paused":
            cmd = "resume"
        else:
            self.notify(f"Cannot pause/resume agent in {status} state", severity="warning")
            return
        if self.manager.send_command(self.crew_id, self.selected_agent, cmd):
            self.notify(f"Sent {cmd} to {self.selected_agent}")
        else:
            self.notify(f"Failed to send {cmd}", severity="error")

    def action_kill_agent(self) -> None:
        if not self.selected_agent:
            self.notify("No agent selected", severity="warning")
            return
        if self.manager.send_command(self.crew_id, self.selected_agent, "kill"):
            self.notify(f"Kill signal sent to {self.selected_agent}")
        else:
            self.notify("Failed to send kill", severity="error")

    async def action_refresh(self) -> None:
        await self._refresh_data()
        self.notify("Refreshed")


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------


class AgentCrewDashboard(App):
    """TUI dashboard for monitoring and managing agentcrews."""

    TITLE = "AgentCrew Dashboard"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("enter", "open_detail", "Detail"),
        Binding("r", "start_runner", "Start Runner"),
        Binding("k", "stop_runner", "Stop Runner"),
        Binding("d", "cleanup", "Cleanup"),
        Binding("f5", "refresh", "Refresh"),
        Binding("tab", "focus_next", "Next", show=False),
        Binding("shift+tab", "focus_previous", "Prev", show=False),
    ]

    CSS = """
    Screen {
        layout: vertical;
    }
    #crew-list {
        height: 1fr;
    }
    #empty-message {
        text-align: center;
        padding: 4;
        color: $text-muted;
    }
    CrewCard {
        height: 2;
        padding: 0 1;
        margin: 0 0 0 0;
    }
    CrewCard:focus {
        background: $accent 20%;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.manager = CrewManager()
        self.crews: list[dict] = []
        self._selected_crew_id: str = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(id="crew-list")
        yield Footer()

    def on_mount(self) -> None:
        self.call_later(self._refresh_data)
        self.set_interval(5.0, self._refresh_data)

    async def _refresh_data(self) -> None:
        self.crews = self.manager.refresh_all()
        crew_list = self.query_one("#crew-list", VerticalScroll)
        await crew_list.remove_children()

        if not self.crews:
            await crew_list.mount(
                Label(
                    "No agentcrews found.\n\n"
                    "Create one with: ait crew init --id <name> --name 'Display Name'",
                    id="empty-message",
                )
            )
            return

        for crew in self.crews:
            ri = self.manager.get_runner_info(crew["id"])
            card = CrewCard(crew, ri, id=f"crew-{crew['id']}")
            await crew_list.mount(card)

    def _get_focused_crew_id(self) -> str | None:
        """Get the crew_id from the currently focused CrewCard."""
        focused = self.focused
        if isinstance(focused, CrewCard):
            return focused.crew_data.get("id")
        return None

    def action_open_detail(self) -> None:
        crew_id = self._get_focused_crew_id()
        if crew_id:
            self.push_screen(CrewDetailScreen(crew_id, self.manager))
        else:
            self.notify("No crew selected", severity="warning")

    def action_start_runner(self) -> None:
        crew_id = self._get_focused_crew_id()
        if not crew_id:
            self.notify("No crew selected", severity="warning")
            return
        if self.manager.start_runner(crew_id):
            self.notify(f"Runner started for {crew_id}")
        else:
            self.notify("Failed to start runner", severity="error")

    def action_stop_runner(self) -> None:
        crew_id = self._get_focused_crew_id()
        if not crew_id:
            self.notify("No crew selected", severity="warning")
            return
        if self.manager.stop_runner(crew_id):
            self.notify(f"Stop signal sent to {crew_id}")
        else:
            self.notify("Failed to stop runner", severity="error")

    async def action_cleanup(self) -> None:
        crew_id = self._get_focused_crew_id()
        if not crew_id:
            self.notify("No crew selected", severity="warning")
            return
        # Only allow cleanup for terminal states
        for crew in self.crews:
            if crew["id"] == crew_id:
                status = crew.get("status", "")
                if status not in ("Completed", "Error", "Aborted"):
                    self.notify(
                        f"Cannot cleanup crew in {status} state (must be Completed/Error/Aborted)",
                        severity="warning",
                    )
                    return
                break

        if self.manager.cleanup_crew(crew_id):
            self.notify(f"Cleaned up {crew_id}")
            await self._refresh_data()
        else:
            self.notify("Cleanup failed", severity="error")

    async def action_refresh(self) -> None:
        await self._refresh_data()
        self.notify("Refreshed")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    app = AgentCrewDashboard()
    app.run()


if __name__ == "__main__":
    main()
