"""Process stats gathering for AgentCrew — reads /proc for OS-level info."""

from __future__ import annotations

import os
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agentcrew_utils import (
    crew_worktree_path,
    format_elapsed,
    list_agent_files,
    read_yaml,
    write_yaml,
    _parse_timestamp,
)


# ---------------------------------------------------------------------------
# Constants (resolved once at import time)
# ---------------------------------------------------------------------------

_CLK_TCK = os.sysconf("SC_CLK_TCK")
_PAGE_SIZE = os.sysconf("SC_PAGE_SIZE")


def _get_boot_time() -> float:
    """Return system boot time as Unix timestamp from /proc/stat."""
    try:
        with open("/proc/stat") as f:
            for line in f:
                if line.startswith("btime "):
                    return float(line.split()[1])
    except (OSError, ValueError):
        pass
    return 0.0


_BOOT_TIME = _get_boot_time()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is alive."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # process exists, just no permission to signal
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_process_info(pid: int) -> dict | None:
    """Get OS-level process info from /proc/<pid>/stat.

    Returns dict with: alive, cpu_time_seconds, memory_rss_mb,
    wall_time_seconds, create_time.  Returns None if process not found.
    """
    stat_path = f"/proc/{pid}/stat"
    try:
        with open(stat_path) as f:
            stat_line = f.read()
    except (FileNotFoundError, PermissionError):
        if _check_pid_alive(pid):
            return {
                "alive": True,
                "cpu_time_seconds": None,
                "memory_rss_mb": None,
                "wall_time_seconds": None,
                "create_time": None,
            }
        return None

    # Parse: pid (comm) state fields...
    # comm can contain spaces and parens, so find the last ')' to split
    try:
        end_comm = stat_line.rindex(")")
        fields = stat_line[end_comm + 2 :].split()
        # fields[0] = state, fields[11] = utime (field 14), etc.
        utime = int(fields[11])  # field 14
        stime = int(fields[12])  # field 15
        starttime = int(fields[19])  # field 22
        rss = int(fields[21])  # field 24
    except (ValueError, IndexError):
        return {
            "alive": True,
            "cpu_time_seconds": None,
            "memory_rss_mb": None,
            "wall_time_seconds": None,
            "create_time": None,
        }

    cpu_seconds = (utime + stime) / _CLK_TCK
    memory_mb = (rss * _PAGE_SIZE) / (1024 * 1024)

    start_epoch = _BOOT_TIME + starttime / _CLK_TCK
    wall_seconds = max(0, datetime.now(timezone.utc).timestamp() - start_epoch)
    create_dt = datetime.fromtimestamp(start_epoch, tz=timezone.utc)

    return {
        "alive": True,
        "cpu_time_seconds": round(cpu_seconds, 2),
        "memory_rss_mb": round(memory_mb, 1),
        "wall_time_seconds": round(wall_seconds, 1),
        "create_time": create_dt.strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_all_agent_processes(crew_id: str) -> list[dict]:
    """Get process info for all agents with PIDs in a crew.

    Returns list of dicts with agent metadata + OS stats for agents
    whose status is Running or Paused and have a pid field.
    """
    wt = crew_worktree_path(crew_id)
    if not os.path.isdir(wt):
        return []

    results = []
    for status_file in list_agent_files(wt, "_status.yaml"):
        data = read_yaml(status_file)
        name = data.get("agent_name", "")
        status = data.get("status", "")
        pid = data.get("pid")

        if not name or not pid or status not in ("Running", "Paused"):
            continue

        pid = int(pid)
        proc_info = get_process_info(pid)
        process_alive = proc_info is not None and proc_info.get("alive", False)

        # Read heartbeat
        alive_path = os.path.join(wt, f"{name}_alive.yaml")
        heartbeat_age = "never"
        last_message = ""
        if os.path.isfile(alive_path):
            alive_data = read_yaml(alive_path)
            hb = alive_data.get("last_heartbeat", "")
            if hb:
                ts = _parse_timestamp(str(hb))
                if ts:
                    elapsed = (datetime.now(timezone.utc) - ts).total_seconds()
                    heartbeat_age = format_elapsed(elapsed)
            last_message = alive_data.get("last_message", "")

        results.append(
            {
                "agent_name": name,
                "agent_type": data.get("agent_type", ""),
                "group": data.get("group", ""),
                "status": status,
                "pid": pid,
                "started_at": data.get("started_at", ""),
                "process_alive": process_alive,
                "cpu_time": proc_info.get("cpu_time_seconds") if proc_info else None,
                "memory_rss_mb": proc_info.get("memory_rss_mb") if proc_info else None,
                "wall_time": proc_info.get("wall_time_seconds") if proc_info else None,
                "heartbeat_age": heartbeat_age,
                "last_message": last_message,
            }
        )

    return results


def get_runner_process_info(crew_id: str) -> dict | None:
    """Get runner process info including OS stats if local."""
    wt = crew_worktree_path(crew_id)
    runner_path = os.path.join(wt, "_runner_alive.yaml")
    if not os.path.isfile(runner_path):
        return None

    data = read_yaml(runner_path)
    pid = data.get("pid")
    hostname = data.get("hostname", "")
    local_hostname = socket.gethostname()
    is_local = hostname == local_hostname

    result = {
        "pid": int(pid) if pid else None,
        "hostname": hostname,
        "status": data.get("status", "unknown"),
        "started_at": data.get("started_at", ""),
        "last_heartbeat": data.get("last_heartbeat", ""),
        "remote": not is_local,
    }

    if pid and is_local:
        proc_info = get_process_info(int(pid))
        if proc_info:
            result["process_alive"] = proc_info["alive"]
            result["cpu_time"] = proc_info.get("cpu_time_seconds")
            result["memory_rss_mb"] = proc_info.get("memory_rss_mb")
            result["wall_time"] = proc_info.get("wall_time_seconds")
        else:
            result["process_alive"] = False
    elif pid and not is_local:
        result["process_alive"] = None  # Can't check remote

    return result


def sync_stale_processes(crew_id: str) -> list[str]:
    """Auto-correct stale agents: if Running but PID dead and runner dead, mark as Error.

    Returns list of agent names that were corrected.
    """
    wt = crew_worktree_path(crew_id)
    if not os.path.isdir(wt):
        return []

    # Check if runner is alive (only sync if runner is dead)
    runner_path = os.path.join(wt, "_runner_alive.yaml")
    if os.path.isfile(runner_path):
        runner_data = read_yaml(runner_path)
        runner_pid = runner_data.get("pid")
        runner_hostname = runner_data.get("hostname", "")
        local_hostname = socket.gethostname()

        if runner_hostname != local_hostname:
            return []  # Can't verify remote
        if runner_pid and _check_pid_alive(int(runner_pid)):
            return []  # Runner alive, let it handle cleanup

    corrected = []
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    for status_file in list_agent_files(wt, "_status.yaml"):
        data = read_yaml(status_file)
        name = data.get("agent_name", "")
        status = data.get("status", "")
        pid = data.get("pid")

        if not name or status != "Running" or not pid:
            continue

        if not _check_pid_alive(int(pid)):
            data["status"] = "Error"
            data["error_message"] = "Process exited unexpectedly"
            data["completed_at"] = now_str
            write_yaml(status_file, data)
            corrected.append(name)

    return corrected
