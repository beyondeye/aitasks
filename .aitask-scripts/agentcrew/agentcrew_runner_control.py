"""Shared runner control functions for AgentCrew TUIs."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Ensure sibling modules (agentcrew_utils) are importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

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
