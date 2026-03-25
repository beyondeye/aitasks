---
Task: t462_3_dashboard_processes_screen.md
Parent Task: aitasks/t462_running_processes_ui.md
Sibling Tasks: aitasks/t462/t462_1_process_stats_utility.md, aitasks/t462/t462_2_hard_kill_implementation.md, aitasks/t462/t462_4_brainstorm_processes_section.md
Archived Sibling Plans: aiplans/archived/p462/p462_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t462_3 — AgentCrew Dashboard Processes Screen

## Overview

Add `ProcessListScreen` (stacked screen) and `ProcessCard` widget to `agentcrew_dashboard.py`. Accessible from `CrewDetailScreen` via `o` keybinding. Shows running agent processes with OS stats and control actions.

## Steps

### Step 1: Add imports

At the top of `agentcrew_dashboard.py`, add:

```python
from agentcrew.agentcrew_process_stats import (
    get_all_agent_processes, get_runner_process_info, sync_stale_processes
)
from agentcrew.agentcrew_runner_control import hard_kill_agent
```

### Step 2: Add CSS rules

Add to the `CSS` string inside the `AgentCrewDashboard` App class:

```css
ProcessCard { height: auto; padding: 0 2; margin: 0 0 1 0; }
ProcessCard:focus { background: $accent; color: $text; }
ProcessCard.-dead { opacity: 0.6; }
#runner-process-info { height: auto; padding: 1 2; background: $surface; margin: 0 0 1 0; }
#no-processes { padding: 2 4; color: $text-muted; }
```

### Step 3: Create `ProcessCard` widget

Add after the existing `AgentCard` class. Follow the same pattern:

```python
class ProcessCard(Static, can_focus=True):
    """Displays a running agent process with OS-level stats."""

    def __init__(self, proc_data: dict, crew_id: str, **kwargs):
        super().__init__(**kwargs)
        self.proc_data = proc_data
        self.crew_id = crew_id
        self.agent_name = proc_data["agent_name"]

    def render(self) -> str:
        d = self.proc_data
        alive = d.get("process_alive", False)
        status = d.get("status", "")

        # Status indicator
        if alive and status == "Running":
            dot = "[green]●[/]"
        elif status == "Paused":
            dot = "[yellow]●[/]"
        elif not alive:
            dot = "[red]●[/]"
        else:
            dot = "[dim]●[/]"

        # Format stats
        pid_str = str(d.get("pid", "?"))
        wall = format_elapsed(d["wall_time"]) if d.get("wall_time") is not None else "?"
        cpu = f'{d["cpu_time"]:.1f}s' if d.get("cpu_time") is not None else "?"
        rss = f'{d["memory_rss_mb"]:.0f}MB' if d.get("memory_rss_mb") is not None else "?"
        hb = d.get("heartbeat_age", "?")
        agent_type = d.get("agent_type", "")
        name = d["agent_name"]

        line1 = f"{dot} {name}"
        if agent_type:
            line1 += f" ({agent_type})"
        line1 += f"  PID: {pid_str}  Wall: {wall}  CPU: {cpu}  RSS: {rss}  HB: {hb}"

        msg = d.get("last_message", "")
        if msg:
            line1 += f"\n    Last: {msg}"
        if not alive:
            line1 += "\n    [red]Process dead but status not updated[/]"

        return line1
```

If not alive, add the `-dead` CSS class in `on_mount`:

```python
    def on_mount(self) -> None:
        if not self.proc_data.get("process_alive", False):
            self.add_class("-dead")
```

### Step 4: Create `ProcessListScreen`

Add after `ProcessCard`:

```python
class ProcessListScreen(Screen):
    """Shows running agent processes with OS stats and control actions."""

    BINDINGS = [
        Binding("p", "pause_resume", "Pause/Resume"),
        Binding("k", "kill_agent", "Kill"),
        Binding("K", "hard_kill", "Hard Kill"),
        Binding("f5", "refresh", "Refresh"),
        Binding("escape", "go_back", "Back"),
    ]

    def __init__(self, crew_id: str, crew_name: str = "", **kwargs):
        super().__init__(**kwargs)
        self.crew_id = crew_id
        self.crew_name = crew_name

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"Processes — {self.crew_name or self.crew_id}", id="process-title")
        yield Static("", id="runner-process-info")
        yield VerticalScroll(id="process-list")
        yield Footer()

    def on_mount(self) -> None:
        # Sync stale processes on first load
        corrected = sync_stale_processes(self.crew_id)
        if corrected:
            self.notify(f"Auto-corrected {len(corrected)} stale agent(s): {', '.join(corrected)}")
        self._refresh_data()
        self.set_interval(5.0, self._refresh_data)

    def _refresh_data(self) -> None:
        # Runner info
        runner = get_runner_process_info(self.crew_id)
        runner_widget = self.query_one("#runner-process-info", Static)
        if runner and runner.get("pid"):
            parts = [f"Runner PID: {runner['pid']}"]
            if runner.get("remote"):
                parts.append(f"(remote: {runner.get('hostname', '?')})")
            else:
                if runner.get("cpu_time") is not None:
                    parts.append(f"CPU: {runner['cpu_time']:.1f}s")
                if runner.get("memory_rss_mb") is not None:
                    parts.append(f"RSS: {runner['memory_rss_mb']:.0f}MB")
                alive = runner.get("process_alive")
                if alive is False:
                    parts.append("[red]DEAD[/]")
            runner_widget.update("  ".join(parts))
        else:
            runner_widget.update("[dim]No runner active[/]")

        # Agent processes
        container = self.query_one("#process-list", VerticalScroll)
        container.remove_children()

        processes = get_all_agent_processes(self.crew_id)
        if not processes:
            container.mount(Static("[dim]No running processes[/]", id="no-processes"))
        else:
            for proc in processes:
                container.mount(ProcessCard(proc, self.crew_id))

    def _get_focused_process(self) -> ProcessCard | None:
        focused = self.focused
        if isinstance(focused, ProcessCard):
            return focused
        return None

    def action_pause_resume(self) -> None:
        card = self._get_focused_process()
        if not card:
            self.notify("No process selected", severity="warning")
            return
        status = card.proc_data.get("status", "")
        cmd = "resume" if status == "Paused" else "pause"
        ok = send_agent_command(self.crew_id, card.agent_name, cmd)
        self.notify(f"{'Resumed' if cmd == 'resume' else 'Paused'} {card.agent_name}" if ok
                    else f"Failed to {cmd} {card.agent_name}", severity="information" if ok else "error")

    def action_kill_agent(self) -> None:
        card = self._get_focused_process()
        if not card:
            self.notify("No process selected", severity="warning")
            return
        ok = send_agent_command(self.crew_id, card.agent_name, "kill")
        self.notify(f"Kill sent to {card.agent_name}" if ok
                    else f"Failed to send kill to {card.agent_name}", severity="information" if ok else "error")

    def action_hard_kill(self) -> None:
        card = self._get_focused_process()
        if not card:
            self.notify("No process selected", severity="warning")
            return
        result = hard_kill_agent(self.crew_id, card.agent_name)
        self.notify(result["message"], severity="information" if result["success"] else "error")
        if result["success"]:
            self.set_timer(1.0, self._refresh_data)

    def action_refresh(self) -> None:
        self._refresh_data()

    def action_go_back(self) -> None:
        self.app.pop_screen()
```

### Step 5: Add `send_agent_command` import

Ensure `ProcessListScreen` can use `send_agent_command`. Add to the imports at top if not already accessible:

```python
from agentcrew.agentcrew_runner_control import hard_kill_agent, send_agent_command
```

But note the dashboard already imports `send_agent_command` — check existing imports and add `hard_kill_agent` alongside.

### Step 6: Add keybinding to `CrewDetailScreen`

In the `CrewDetailScreen` class, add to `BINDINGS`:

```python
Binding("o", "view_processes", "Processes"),
```

Add the action method:

```python
def action_view_processes(self) -> None:
    self.app.push_screen(ProcessListScreen(self.crew_id, self.crew_name))
```

Where `self.crew_name` comes from the crew data already loaded in `CrewDetailScreen`.

### Step 7: Add `format_elapsed` import

The `ProcessCard` uses `format_elapsed` from `agentcrew_utils`. Ensure it's imported.

### Step 8: Verify

1. Launch `ait crew dashboard`
2. Select a crew, press `o` → should show ProcessListScreen
3. Verify ProcessCards show PID, wall time, CPU time, RSS, heartbeat age
4. Test `p`, `k`, `K` actions
5. Press `escape` → back to CrewDetailScreen
6. Verify 5-second auto-refresh

## Final Implementation Notes

- **Actual work done:** Added `ProcessCard` widget, `ProcessListScreen` stacked screen, `CrewManager.hard_kill()` method, imports for `agentcrew_process_stats` and `hard_kill_agent`, CSS rules, `o` keybinding and `action_view_processes()` in `CrewDetailScreen`. All in `agentcrew_dashboard.py` (+182 lines).
- **Deviations from plan:**
  - **crew_name access:** Plan called `self.crew_name` but `CrewDetailScreen` stores it in `self.crew_data['name']`. Fixed to use `self.crew_data.get('name', self.crew_id)`.
  - **Import style:** Plan imported `send_agent_command` directly. Instead, used existing `_send_agent_command` alias via `CrewManager.send_command()` pattern for consistency. Added `hard_kill_agent as _hard_kill_agent` to the existing runner_control import block and wrapped it in `CrewManager.hard_kill()`.
  - **Async patterns:** Plan's `_refresh_data()` was sync. Made it `async` with `await container.remove_children()` / `await container.mount()` matching the established pattern in `CrewDetailScreen` and `AgentCrewDashboard`.
  - **format_elapsed:** Plan Step 7 was unnecessary — already imported at module top from `agentcrew_utils`.
  - **CSS placement:** Used screen-level `CSS` class variable on `ProcessListScreen` instead of adding to `AgentCrewDashboard.CSS`, matching the pattern used by `CrewDetailScreen`.
- **Issues encountered:** None.
- **Key decisions:** Passed `manager: CrewManager` to `ProcessListScreen` for consistency with `LogBrowserScreen` pattern, rather than calling module functions directly.
- **Notes for sibling tasks:** The brainstorm TUI (t462_4) should follow the same pattern: import `get_all_agent_processes`/`get_runner_process_info`/`sync_stale_processes` from `agentcrew_process_stats` and `hard_kill_agent` from `agentcrew_runner_control`. The `ProcessCard` widget from the dashboard could potentially be reused if the brainstorm TUI imports it, but it's tightly coupled to the dashboard's Textual patterns — better to create an independent widget there.

## Step 9: Post-Implementation

See task-workflow SKILL.md Step 9 for archival, merge, and cleanup.
