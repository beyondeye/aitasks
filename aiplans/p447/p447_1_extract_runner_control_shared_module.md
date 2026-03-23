---
Task: t447_1_extract_runner_control_shared_module.md
Parent Task: aitasks/t447_add_crew_runner_control_to_brainstorm_tui.md
Sibling Tasks: aitasks/t447/t447_2_add_runner_ui_to_brainstorm_status_tab.md, aitasks/t447/t447_3_push_crew_worktree_after_addwork.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Plan: Extract runner control into shared module

### Step 1: Create `.aitask-scripts/agentcrew/agentcrew_runner_control.py`

Create the new shared module with functions extracted from `agentcrew_dashboard.py`.

```python
"""Shared runner control functions for AgentCrew TUIs."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from agentcrew_utils import (
    crew_worktree_path,
    format_elapsed,
    read_yaml,
    update_yaml_field,
    _parse_timestamp,
)

AIT_PATH = str(Path(__file__).resolve().parent.parent.parent / "ait")

RUNNER_STALE_SECONDS = 120  # Consider runner stale after 2 minutes without heartbeat


def _elapsed_since(ts_str: str) -> float | None:
    """Return seconds elapsed since a timestamp string, or None."""
    ts = _parse_timestamp(str(ts_str))
    if ts is None:
        return None
    from datetime import datetime, timezone
    return (datetime.now(timezone.utc) - ts).total_seconds()


def _heartbeat_age(ts_str: str) -> str:
    """Return a human-readable heartbeat age string."""
    elapsed = _elapsed_since(ts_str)
    if elapsed is None:
        return "never"
    return f"{format_elapsed(elapsed)} ago"


def get_runner_info(crew_id: str) -> dict:
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


def start_runner(crew_id: str) -> bool:
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


def stop_runner(crew_id: str) -> bool:
    """Request runner to stop by sending stop command."""
    try:
        subprocess.run(
            [AIT_PATH, "crew", "command", "send-all", "--crew", crew_id,
             "--command", "kill"],
            capture_output=True, text=True, timeout=10,
        )
        wt = crew_worktree_path(crew_id)
        runner_path = os.path.join(wt, "_runner_alive.yaml")
        if os.path.isfile(runner_path):
            update_yaml_field(runner_path, "requested_action", "stop")
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False
```

### Step 2: Update `agentcrew_dashboard.py`

**2a: Remove extracted code (lines 62-83):**
- Delete `RUNNER_STALE_SECONDS = 120`
- Delete `_elapsed_since()` function
- Delete `_heartbeat_age()` function

**2b: Add import at top (after existing imports):**
```python
from agentcrew_runner_control import (
    RUNNER_STALE_SECONDS,
    _elapsed_since,
    _heartbeat_age,
    get_runner_info as _get_runner_info,
    start_runner as _start_runner,
    stop_runner as _stop_runner,
)
```

**2c: Replace CrewManager method bodies:**

```python
def get_runner_info(self, crew_id: str) -> dict:
    """Get runner status information."""
    return _get_runner_info(crew_id)

def start_runner(self, crew_id: str) -> bool:
    """Launch a runner for the crew as a detached process."""
    return _start_runner(crew_id)

def stop_runner(self, crew_id: str) -> bool:
    """Request runner to stop by sending stop command."""
    return _stop_runner(crew_id)
```

### Step 3: Verify

1. `cd .aitask-scripts && python -c "from agentcrew.agentcrew_runner_control import get_runner_info, start_runner, stop_runner; print('OK')"`
2. `cd .aitask-scripts && python -c "from agentcrew.agentcrew_dashboard import CrewManager; print('OK')"`
3. Check no remaining direct references to old standalone helpers in dashboard

### Step 9: Post-Implementation

Archive task and plan per workflow.
