"""Shared utilities for AgentCrew: YAML helpers, status validation, DAG ops, heartbeat."""

from __future__ import annotations

import glob
import os
import subprocess
import sys
from collections import deque
from datetime import datetime, timezone

import yaml

# ---------------------------------------------------------------------------
# Status constants (must match .aitask-scripts/lib/agentcrew_utils.sh)
# ---------------------------------------------------------------------------

AGENT_STATUSES = [
    "Waiting", "Ready", "Running", "MissedHeartbeat",
    "Completed", "Aborted", "Error", "Paused",
]
CREW_STATUSES = ["Initializing", "Running", "Killing", "Paused", "Completed", "Error"]

# ---------------------------------------------------------------------------
# Valid state transitions
# ---------------------------------------------------------------------------

AGENT_TRANSITIONS: dict[str, list[str]] = {
    "Waiting": ["Ready"],
    "Ready": ["Running"],
    "Running": ["Completed", "Error", "Aborted", "Paused", "MissedHeartbeat"],
    # Soft-stale grace state: heartbeat missed but not yet declared dead.
    "MissedHeartbeat": ["Running", "Error", "Aborted"],
    "Paused": ["Running"],
    # Terminal states — no outgoing transitions (except Error, which is recoverable).
    # Error is recoverable: a heartbeat-watchdog timeout does not prove the agent
    # failed. An agent that gets falsely Error'd may still write Completed at end
    # of work, or resume Running mid-flight. Aborted is intentionally terminal —
    # Aborted is always user-initiated, not a watchdog accident.
    "Completed": [],
    "Aborted": [],
    "Error": ["Waiting", "Running", "Completed"],
}

CREW_TRANSITIONS: dict[str, list[str]] = {
    "Initializing": ["Running"],
    "Running": ["Killing", "Paused", "Completed", "Error"],
    "Killing": ["Completed", "Error"],
    "Paused": ["Running", "Killing"],
    # Terminal states
    "Completed": [],
    "Error": [],
}

# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------

AGENTCREW_DIR = ".aitask-crews"


def read_yaml(path: str) -> dict:
    """Read a YAML file and return its contents as a dict."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def write_yaml(path: str, data: dict) -> None:
    """Write a dict to a YAML file."""
    with open(path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)


def update_yaml_field(path: str, field: str, value) -> None:
    """Update a single field in a YAML file, preserving other fields."""
    data = read_yaml(path)
    data[field] = value
    write_yaml(path, data)

# ---------------------------------------------------------------------------
# Status validation
# ---------------------------------------------------------------------------


def validate_agent_transition(current: str, target: str) -> bool:
    """Return True if the agent status transition is valid."""
    if current not in AGENT_TRANSITIONS:
        return False
    return target in AGENT_TRANSITIONS[current]


def validate_crew_transition(current: str, target: str) -> bool:
    """Return True if the crew status transition is valid."""
    if current not in CREW_TRANSITIONS:
        return False
    return target in CREW_TRANSITIONS[current]


def compute_crew_status(agent_statuses: list[str]) -> str:
    """Derive the overall crew status from a list of agent statuses.

    Rules:
    - All Completed -> Completed
    - Any Error (no Running/MissedHeartbeat) -> Error
    - Any Running or MissedHeartbeat -> Running
    - All Waiting -> Initializing
    - Any Paused (no Running/MissedHeartbeat) -> Paused
    - Otherwise -> Running (mixed active states)

    MissedHeartbeat is treated as Running for rollup so a transient missed
    heartbeat doesn't flip the crew to Error during the grace window.
    """
    if not agent_statuses:
        return "Initializing"

    status_set = set(agent_statuses)
    active = {"Running", "MissedHeartbeat"}

    if status_set == {"Completed"}:
        return "Completed"

    if "Error" in status_set and not (status_set & active):
        return "Error"

    if status_set & active:
        return "Running"

    if status_set == {"Waiting"}:
        return "Initializing"

    if "Paused" in status_set and not (status_set & active):
        return "Paused"

    # Mixed states (e.g. some Ready, some Waiting, some Completed) -> Running
    return "Running"

# ---------------------------------------------------------------------------
# DAG operations
# ---------------------------------------------------------------------------


def topo_sort(agents: dict[str, list[str]]) -> list[str]:
    """Topological sort via Kahn's BFS. Returns ordered list of agent names.

    agents: {name: [dependency_names]}
    Raises ValueError if a cycle is detected.
    """
    # Build in-degree and adjacency (dep -> dependents)
    in_degree: dict[str, int] = {name: 0 for name in agents}
    dependents: dict[str, list[str]] = {name: [] for name in agents}

    for name, deps in agents.items():
        for dep in deps:
            if dep in agents:
                in_degree[name] += 1
                dependents[dep].append(name)

    queue = deque(name for name, deg in in_degree.items() if deg == 0)
    result: list[str] = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for dependent in dependents[node]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(result) != len(agents):
        missing = set(agents) - set(result)
        raise ValueError(f"Circular dependency detected involving: {', '.join(sorted(missing))}")

    return result


def detect_cycles(agents: dict[str, list[str]]) -> list[str] | None:
    """Detect cycles in the agent dependency graph.

    Returns None if no cycle, or a list of agent names involved in a cycle.
    """
    try:
        topo_sort(agents)
        return None
    except ValueError:
        # Find the agents that couldn't be sorted
        in_degree: dict[str, int] = {name: 0 for name in agents}
        for name, deps in agents.items():
            for dep in deps:
                if dep in agents:
                    in_degree[name] += 1

        queue = deque(name for name, deg in in_degree.items() if deg == 0)
        visited: set[str] = set()
        while queue:
            node = queue.popleft()
            visited.add(node)
            for name, deps in agents.items():
                if node in deps and name not in visited:
                    in_degree[name] -= 1
                    if in_degree[name] == 0:
                        queue.append(name)

        return sorted(set(agents) - visited)

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def crew_worktree_path(crew_id: str) -> str:
    """Return the filesystem path for a crew's worktree."""
    return os.path.join(AGENTCREW_DIR, f"crew-{crew_id}")


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def git_cmd(worktree: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command in the given worktree directory."""
    cmd = ["git", "-C", worktree] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def git_pull(worktree: str, batch: bool = False) -> None:
    """Pull latest changes in the worktree (best-effort)."""
    result = git_cmd(worktree, "pull", "--rebase=false", check=False)
    if result.returncode != 0 and not batch:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"[{ts}] git pull warning: {result.stderr.strip()}", file=sys.stderr)


def git_commit_push_if_changes(worktree: str, message: str, batch: bool = False) -> None:
    """Stage all changes in worktree, commit and push if there are changes."""
    git_cmd(worktree, "add", "-A", check=False)
    # Check if there are staged changes
    result = git_cmd(worktree, "diff", "--cached", "--quiet", check=False)
    if result.returncode != 0:
        git_cmd(worktree, "commit", "-m", message, check=False)
        push_result = git_cmd(worktree, "push", check=False)
        if push_result.returncode != 0 and not batch:
            ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
            print(f"[{ts}] git push warning: {push_result.stderr.strip()}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Agent file enumeration
# ---------------------------------------------------------------------------


def list_agent_files(worktree_path: str, suffix: str) -> list[str]:
    """List all agent files with the given suffix in the worktree.

    Excludes crew-level files (prefixed with _).
    """
    pattern = os.path.join(worktree_path, f"*{suffix}")
    return [
        f for f in sorted(glob.glob(pattern))
        if not os.path.basename(f).startswith("_")
    ]


def get_agent_names(worktree_path: str) -> list[str]:
    """Get all agent names from _status.yaml files in the worktree."""
    names = []
    for status_file in list_agent_files(worktree_path, "_status.yaml"):
        data = read_yaml(status_file)
        name = data.get("agent_name", "")
        if name:
            names.append(name)
    return names

# ---------------------------------------------------------------------------
# Ready-agent detection
# ---------------------------------------------------------------------------


def get_ready_agents(worktree_path: str) -> list[str]:
    """Return agents with Waiting status whose all dependencies are Completed.

    These agents are eligible to transition to Ready.
    """
    # Load all agent statuses and dependencies
    agent_data: dict[str, dict] = {}
    for status_file in list_agent_files(worktree_path, "_status.yaml"):
        data = read_yaml(status_file)
        name = data.get("agent_name", "")
        if name:
            agent_data[name] = data

    ready = []
    for name, data in agent_data.items():
        if data.get("status") != "Waiting":
            continue
        deps = data.get("depends_on", [])
        if not deps:
            ready.append(name)
            continue
        # Check all deps are Completed
        all_done = all(
            agent_data.get(dep, {}).get("status") == "Completed"
            for dep in deps
        )
        if all_done:
            ready.append(name)

    return sorted(ready)

# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


def _parse_timestamp(ts_str: str) -> datetime | None:
    """Parse a UTC timestamp string. Returns None if empty or invalid."""
    if not ts_str:
        return None
    ts_str = str(ts_str).strip()
    if not ts_str:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(ts_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def check_agent_alive(alive_path: str, timeout_seconds: int = 300) -> bool:
    """Check if an agent's heartbeat is within the timeout.

    Returns True if alive (heartbeat within timeout), False if stale or no heartbeat.
    """
    data = read_yaml(alive_path)
    last_hb = data.get("last_heartbeat")
    if not last_hb:
        return False
    ts = _parse_timestamp(str(last_hb))
    if ts is None:
        return False
    now = datetime.now(timezone.utc)
    return (now - ts).total_seconds() <= timeout_seconds


def get_stale_agents(worktree_path: str, timeout_seconds: int = 300) -> list[str]:
    """Return names of Running agents whose heartbeat exceeds the timeout."""
    stale = []
    for status_file in list_agent_files(worktree_path, "_status.yaml"):
        data = read_yaml(status_file)
        name = data.get("agent_name", "")
        status = data.get("status", "")
        if not name or status != "Running":
            continue
        alive_path = os.path.join(worktree_path, f"{name}_alive.yaml")
        if not os.path.isfile(alive_path):
            stale.append(name)
            continue
        if not check_agent_alive(alive_path, timeout_seconds):
            stale.append(name)
    return sorted(stale)


# ---------------------------------------------------------------------------
# Crew listing
# ---------------------------------------------------------------------------


def list_crews() -> list[dict]:
    """List all agentcrews by scanning .aitask-crews/ directories.

    Returns a list of dicts, each with keys:
      id, name, status, progress, created_at, started_at, updated_at,
      agent_count, runner_status, runner_heartbeat
    """
    crews_dir = AGENTCREW_DIR
    if not os.path.isdir(crews_dir):
        return []

    results = []
    prefix = "crew-"
    for entry in sorted(os.listdir(crews_dir)):
        entry_path = os.path.join(crews_dir, entry)
        if not os.path.isdir(entry_path) or not entry.startswith(prefix):
            continue

        crew_id = entry[len(prefix):]
        meta_path = os.path.join(entry_path, "_crew_meta.yaml")
        status_path = os.path.join(entry_path, "_crew_status.yaml")
        runner_path = os.path.join(entry_path, "_runner_alive.yaml")

        meta = read_yaml(meta_path) if os.path.isfile(meta_path) else {}
        status_data = read_yaml(status_path) if os.path.isfile(status_path) else {}
        runner_data = read_yaml(runner_path) if os.path.isfile(runner_path) else {}

        agent_names = get_agent_names(entry_path)

        results.append({
            "id": crew_id,
            "name": meta.get("name", crew_id),
            "status": status_data.get("status", "Unknown"),
            "progress": status_data.get("progress", 0),
            "created_at": meta.get("created_at", ""),
            "started_at": status_data.get("started_at", ""),
            "updated_at": status_data.get("updated_at", ""),
            "agent_count": len(agent_names),
            "runner_status": runner_data.get("status", ""),
            "runner_heartbeat": runner_data.get("last_heartbeat", ""),
        })

    return results


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def load_groups(crew_dir: str) -> list[dict]:
    """Load _groups.yaml, return list of group dicts sorted by sequence."""
    groups_file = os.path.join(crew_dir, "_groups.yaml")
    if not os.path.exists(groups_file):
        return []
    data = read_yaml(groups_file)
    groups = data.get("groups", [])
    return sorted(groups, key=lambda g: g.get("sequence", 999))


def get_group_agents(crew_dir: str, group_name: str) -> list[str]:
    """Return agent names belonging to the specified group."""
    agents = []
    for f in list_agent_files(crew_dir, "_status.yaml"):
        data = read_yaml(f)
        if data.get("group", "") == group_name:
            name = data.get("agent_name", "")
            if name:
                agents.append(name)
    return agents


def get_group_status(crew_dir: str, group_name: str) -> str:
    """Return derived status for a group: Completed/Running/Error/Waiting."""
    agents = get_group_agents(crew_dir, group_name)
    if not agents:
        return "Waiting"
    statuses = []
    for name in agents:
        sf = os.path.join(crew_dir, f"{name}_status.yaml")
        if os.path.exists(sf):
            data = read_yaml(sf)
            statuses.append(data.get("status", "Waiting"))
    if all(s == "Completed" for s in statuses):
        return "Completed"
    active = {"Running", "MissedHeartbeat"}
    status_set = set(statuses)
    if "Error" in status_set and not (status_set & active):
        return "Error"
    if status_set & active:
        return "Running"
    return "Waiting"


def group_sort_key(agent_status: dict, groups: list[dict]) -> tuple:
    """Return sort key for group-priority scheduling.

    Lower sequence = higher priority. No-group agents sort last.
    """
    group_name = agent_status.get("group", "")
    if not group_name:
        return (999, agent_status.get("agent_name", ""))
    for g in groups:
        if g.get("name") == group_name:
            return (g.get("sequence", 999), agent_status.get("agent_name", ""))
    return (999, agent_status.get("agent_name", ""))


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def format_elapsed(seconds: float) -> str:
    """Format a duration in seconds to a human-readable string."""
    if seconds < 0:
        return "0s"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        secs = seconds % 60
        return f"{minutes}m" if secs == 0 else f"{minutes}m {secs}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h" if mins == 0 else f"{hours}h {mins}m"
