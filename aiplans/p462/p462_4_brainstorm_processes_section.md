---
Task: t462_4_brainstorm_processes_section.md
Parent Task: aitasks/t462_running_processes_ui.md
Sibling Tasks: aitasks/t462/t462_1_process_stats_utility.md, aitasks/t462/t462_2_hard_kill_implementation.md, aitasks/t462/t462_3_dashboard_processes_screen.md
Archived Sibling Plans: aiplans/archived/p462/p462_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t462_4 — Brainstorm App Processes Section in Status Tab

## Overview

Add a "Running Processes" section to the existing Status tab (tab 5) in `brainstorm_app.py`, between the runner status and operation groups sections. Show OS-level process stats and provide control actions.

## Steps

### Step 1: Add imports

At the top of `brainstorm_app.py`, add:

```python
from agentcrew.agentcrew_process_stats import (
    get_all_agent_processes, get_runner_process_info, sync_stale_processes
)
from agentcrew.agentcrew_runner_control import hard_kill_agent
```

### Step 2: Add CSS rules

Add to the `CSS` string inside the brainstorm App class:

```css
ProcessRow { height: auto; padding: 0 2; }
ProcessRow:focus { background: $accent; color: $text; }
ProcessRow.-dead { opacity: 0.6; }
#status-processes { height: auto; margin: 1 0; }
.process-section-header { text-style: bold; padding: 0 2; color: $text; }
```

### Step 3: Create `ProcessRow` widget

Add near the existing `AgentStatusRow` class. Follow the same pattern:

```python
class ProcessRow(Static, can_focus=True):
    """Displays a running agent process with OS stats in Status tab."""

    def __init__(self, proc_data: dict, crew_id: str, **kwargs):
        super().__init__(**kwargs)
        self.proc_data = proc_data
        self.crew_id = crew_id
        self.agent_name = proc_data["agent_name"]

    def render(self) -> str:
        d = self.proc_data
        alive = d.get("process_alive", False)
        status = d.get("status", "")

        if alive and status == "Running":
            dot = "[green]●[/]"
        elif status == "Paused":
            dot = "[yellow]●[/]"
        elif not alive:
            dot = "[red]●[/]"
        else:
            dot = "[dim]●[/]"

        pid_str = str(d.get("pid", "?"))
        wall = format_elapsed(d["wall_time"]) if d.get("wall_time") is not None else "?"
        cpu = f'{d["cpu_time"]:.1f}s' if d.get("cpu_time") is not None else "?"
        rss = f'{d["memory_rss_mb"]:.0f}MB' if d.get("memory_rss_mb") is not None else "?"
        hb = d.get("heartbeat_age", "?")

        line = f"{dot} {d['agent_name']}  PID:{pid_str}  Wall:{wall}  CPU:{cpu}  RSS:{rss}  HB:{hb}"
        if not alive:
            line += "  [red]DEAD[/]"
        return line

    def on_mount(self) -> None:
        if not self.proc_data.get("process_alive", False):
            self.add_class("-dead")
```

### Step 4: Modify `_refresh_status_tab()` to include process section

In the `_refresh_status_tab()` method, after the runner status section (where `#status-runner` is populated) and before the operation groups section:

1. Find the container for the status tab content (likely `#tab_status` or the VerticalScroll inside it)
2. Add a "Running Processes" section header
3. Call `get_all_agent_processes(crew_id)` for process data
4. On first refresh only, call `sync_stale_processes(crew_id)` — use an instance flag `_processes_synced`
5. Mount `ProcessRow` widgets for each process
6. If no processes, mount a dim label: "No running processes"

The exact insertion point depends on how the status tab content is structured. Look for where runner info ends and groups begin, and insert between them.

Add to `__init__`:
```python
self._processes_synced = False
```

In `_refresh_status_tab()`, after runner section:
```python
# --- Running Processes section ---
process_container = self.query_one("#status-processes", default=None)
if process_container is None:
    # First time: mount the container after runner section
    process_container = Vertical(id="status-processes")
    # Mount after the runner section widget
    # (find correct insertion point based on existing layout)

# Sync stale processes on first load
if not self._processes_synced and self._crew_id:
    corrected = sync_stale_processes(self._crew_id)
    if corrected:
        self.notify(f"Auto-corrected {len(corrected)} stale agent(s)")
    self._processes_synced = True

# Refresh process list
process_container.remove_children()
process_container.mount(Static("Running Processes", classes="process-section-header"))

processes = get_all_agent_processes(self._crew_id)
if not processes:
    process_container.mount(Static("[dim]No running processes[/]"))
else:
    for proc in processes:
        process_container.mount(ProcessRow(proc, self._crew_id))
```

### Step 5: Augment runner status display with process info

In the existing runner status display section of `_refresh_status_tab()`, enhance with OS stats:

```python
runner_proc = get_runner_process_info(self._crew_id)
if runner_proc and runner_proc.get("pid"):
    extra = []
    if not runner_proc.get("remote"):
        if runner_proc.get("cpu_time") is not None:
            extra.append(f"CPU: {runner_proc['cpu_time']:.1f}s")
        if runner_proc.get("memory_rss_mb") is not None:
            extra.append(f"RSS: {runner_proc['memory_rss_mb']:.0f}MB")
    extra_str = f" ({', '.join(extra)})" if extra else ""
    # Append to existing runner status text: f"PID: {runner_proc['pid']}{extra_str}"
```

### Step 6: Add key handlers for process actions

In the `on_key()` method (or wherever key events are handled), add process action handling when a `ProcessRow` is focused:

```python
# In on_key handler:
if isinstance(self.focused, ProcessRow):
    proc_row = self.focused
    if event.key == "p":
        status = proc_row.proc_data.get("status", "")
        cmd = "resume" if status == "Paused" else "pause"
        ok = send_agent_command(proc_row.crew_id, proc_row.agent_name, cmd)
        self.notify(f"{'Resumed' if cmd == 'resume' else 'Paused'} {proc_row.agent_name}" if ok
                    else f"Failed to {cmd}", severity="information" if ok else "error")
        event.prevent_default()
    elif event.key == "k":
        ok = send_agent_command(proc_row.crew_id, proc_row.agent_name, "kill")
        self.notify(f"Kill sent to {proc_row.agent_name}" if ok else "Failed to send kill",
                    severity="information" if ok else "error")
        event.prevent_default()
    elif event.key == "K":
        result = hard_kill_agent(proc_row.crew_id, proc_row.agent_name)
        self.notify(result["message"], severity="information" if result["success"] else "error")
        if result["success"]:
            self.set_timer(2.0, self._refresh_status_tab)
        event.prevent_default()
```

### Step 7: Import `format_elapsed`

Ensure `format_elapsed` is available for `ProcessRow`. The brainstorm app already imports from `agentcrew_utils` — add `format_elapsed` if not already imported.

### Step 8: Verify

1. Launch brainstorm TUI, press `5` for Status tab
2. Verify "Running Processes" section appears between runner and groups
3. Verify ProcessRow widgets show PID, wall time, CPU time, RSS, heartbeat age
4. Verify runner status shows augmented PID/resource info
5. Focus a ProcessRow, test `p` (pause), `k` (kill), `K` (hard kill)
6. Verify 30-second auto-refresh updates process data
7. Test with no running agents: "No running processes" message

## Step 9: Post-Implementation

See task-workflow SKILL.md Step 9 for archival, merge, and cleanup.
