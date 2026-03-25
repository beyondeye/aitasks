---
Task: t462_2_hard_kill_implementation.md
Parent Task: aitasks/t462_running_processes_ui.md
Sibling Tasks: aitasks/t462/t462_1_process_stats_utility.md, aitasks/t462/t462_3_dashboard_processes_screen.md, aitasks/t462/t462_4_brainstorm_processes_section.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t462_2 — Hard Kill Implementation

## Overview

Add `hard_kill_agent(crew_id, agent_name)` to `.aitask-scripts/agentcrew/agentcrew_runner_control.py` that sends SIGKILL directly to an agent process and cleans up its status file.

## Steps

### Step 1: Add imports to agentcrew_runner_control.py

Add `signal` and `socket` to imports at the top of the file:

```python
import os
import signal
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
```

Note: `datetime` is already imported lazily inside `_elapsed_since()`. Move it to top-level for reuse.

### Step 2: Implement `hard_kill_agent()` function

Add after the existing `stop_runner()` function (around line 106):

```python
def hard_kill_agent(crew_id: str, agent_name: str) -> dict:
    """Send SIGKILL to an agent process and clean up status files.

    Returns dict with: success (bool), message (str), was_alive (bool).
    """
    wt = crew_worktree_path(crew_id)
    status_path = os.path.join(wt, f"{agent_name}_status.yaml")

    if not os.path.isfile(status_path):
        return {"success": False, "message": f"Agent '{agent_name}' not found", "was_alive": False}

    data = read_yaml(status_path)
    status = data.get("status", "")
    pid = data.get("pid")

    if status not in ("Running", "Paused"):
        return {"success": False, "message": f"Agent status is '{status}', not killable", "was_alive": False}

    if not pid:
        return {"success": False, "message": "No PID recorded for agent", "was_alive": False}

    pid = int(pid)

    # Hostname safety check
    runner_path = os.path.join(wt, "_runner_alive.yaml")
    if os.path.isfile(runner_path):
        runner_data = read_yaml(runner_path)
        runner_hostname = runner_data.get("hostname", "")
        local_hostname = socket.gethostname()
        if runner_hostname and runner_hostname != local_hostname:
            return {"success": False,
                    "message": f"Cannot hard kill remote process on {runner_hostname}",
                    "was_alive": False}

    # Attempt SIGKILL
    was_alive = False
    try:
        os.kill(pid, signal.SIGKILL)
        was_alive = True
    except ProcessLookupError:
        was_alive = False  # Already dead
    except PermissionError:
        return {"success": False, "message": f"Permission denied killing PID {pid}", "was_alive": False}

    # Update status file
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    data["status"] = "Aborted"
    data["error_message"] = "Hard killed by user"
    data["completed_at"] = now_str
    write_yaml(status_path, data)

    # Clear pending commands
    cmd_path = os.path.join(wt, f"{agent_name}_commands.yaml")
    if os.path.isfile(cmd_path):
        cmd_data = read_yaml(cmd_path)
        cmd_data["pending_commands"] = []
        write_yaml(cmd_path, cmd_data)

    # Log the action
    log_path = os.path.join(wt, f"{agent_name}_log.txt")
    try:
        with open(log_path, "a") as f:
            f.write(f"[{now_str}] HARD_KILL: Process {pid} killed by user (was_alive: {was_alive})\n")
    except OSError:
        pass  # Best effort

    return {"success": True,
            "message": f"Hard killed agent '{agent_name}' (PID {pid}, was_alive: {was_alive})",
            "was_alive": was_alive}
```

### Step 3: Add `write_yaml` to imports from agentcrew_utils

Update the import from `agentcrew_utils`:

```python
from agentcrew_utils import (
    crew_worktree_path,
    format_elapsed,
    read_yaml,
    write_yaml,
    update_yaml_field,
    _parse_timestamp,
)
```

### Step 4: Verify

- Call `hard_kill_agent()` on a test crew/agent — verify PID killed and status updated
- Check `<agent>_log.txt` for HARD_KILL entry
- Test with already-dead process — should succeed with `was_alive: False`
- Test with remote hostname — should reject with clear message

## Step 5: Post-Implementation

See task-workflow SKILL.md Step 9 for archival, merge, and cleanup.
