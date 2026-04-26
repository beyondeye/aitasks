"""Shared runner control functions for AgentCrew TUIs."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure sibling modules (agentcrew_utils) are importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agentcrew_utils import (
    crew_worktree_path,
    format_elapsed,
    read_yaml,
    write_yaml,
    update_yaml_field,
    _parse_timestamp,
)

AIT_PATH = str(Path(__file__).resolve().parent.parent.parent / "ait")

RUNNER_STALE_SECONDS = 120  # Consider runner stale after 2 minutes without heartbeat
RUNNER_LAUNCH_LOG = "_runner_launch.log"
RUNNER_LAUNCH_VERIFY_SECONDS = 1.5  # Grace window to catch immediate runner crashes


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
    """Launch a runner for the crew as a detached process.

    Returns True only if the spawned process is still alive after
    RUNNER_LAUNCH_VERIFY_SECONDS. Captured stdout/stderr is appended to
    <worktree>/_runner_launch.log so an early crash leaves a traceback
    on disk for inspection (the previous DEVNULL redirect silently
    swallowed import errors and made the TUI report success on a dead
    process).
    """
    wt = crew_worktree_path(crew_id)
    log_path = os.path.join(wt, RUNNER_LAUNCH_LOG)
    try:
        log_fh = open(log_path, "a")
    except OSError:
        return False

    log_fh.write(
        f"\n=== {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} "
        f"| start_runner({crew_id}) ===\n"
    )
    log_fh.flush()

    try:
        proc = subprocess.Popen(
            [AIT_PATH, "crew", "runner", "--crew", crew_id],
            start_new_session=True,
            stdout=log_fh,
            stderr=log_fh,
        )
    except OSError:
        log_fh.close()
        return False

    deadline = time.monotonic() + RUNNER_LAUNCH_VERIFY_SECONDS
    while time.monotonic() < deadline:
        rc = proc.poll()
        if rc is not None:
            log_fh.write(f"=== child exited early with code {rc} ===\n")
            log_fh.close()
            return False
        time.sleep(0.1)

    log_fh.close()
    return True


def send_agent_command(crew_id: str, agent_name: str, command: str) -> bool:
    """Send a command to a specific agent via ait crew command send."""
    try:
        result = subprocess.run(
            [AIT_PATH, "crew", "command", "send", "--crew", crew_id,
             "--agent", agent_name, "--command", command],
            capture_output=True, text=True, timeout=10,
        )
        return "COMMAND_SENT:" in result.stdout
    except (OSError, subprocess.TimeoutExpired):
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
