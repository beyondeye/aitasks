"""AgentCrew Runner — central orchestrator for launching and monitoring agents."""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentcrew.agentcrew_utils import (
    AGENTCREW_DIR,
    AGENT_STATUSES,
    check_agent_alive,
    compute_crew_status,
    crew_worktree_path,
    get_agent_names,
    get_ready_agents,
    get_stale_agents,
    group_sort_key,
    list_agent_files,
    load_groups,
    read_yaml,
    update_yaml_field,
    validate_agent_transition,
    write_yaml,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RUNNER_ALIVE_FILE = "_runner_alive.yaml"
CREW_META_FILE = "_crew_meta.yaml"
CREW_STATUS_FILE = "_crew_status.yaml"
CONFIG_FILE = "aitasks/metadata/crew_runner_config.yaml"

DEFAULT_INTERVAL = 30
DEFAULT_MAX_CONCURRENT = 3

_log_handles: dict[str, object] = {}  # agent_name → open file handle for log
_repo_root: str | None = None  # cached repo root (set in main)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resolve_repo_root() -> str:
    """Return the absolute path to the main repository root."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()

def now_utc() -> str:
    """Return current UTC timestamp as string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str, batch: bool = False) -> None:
    """Print a log message (suppressed in batch mode unless prefixed)."""
    if not batch:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"[{ts}] {msg}", file=sys.stderr)


def append_to_agent_log(worktree: str, name: str, message: str) -> None:
    """Append a timestamped message to an agent's log file."""
    log_path = os.path.join(worktree, f"{name}_log.txt")
    if not os.path.isfile(log_path):
        return
    with open(log_path, "a") as f:
        f.write(f"\n=== {now_utc()} | {message} ===\n")


def parse_timestamp(ts_str: str) -> datetime | None:
    """Parse a UTC timestamp string."""
    if not ts_str:
        return None
    ts_str = str(ts_str).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(ts_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def resolve_config(cli_interval: int | None, cli_max_concurrent: int | None) -> tuple[int, int]:
    """Resolve interval and max_concurrent from CLI args > config file > defaults."""
    interval = cli_interval
    max_concurrent = cli_max_concurrent

    # Try config file for any unresolved values
    if interval is None or max_concurrent is None:
        if os.path.isfile(CONFIG_FILE):
            cfg = read_yaml(CONFIG_FILE)
            if interval is None:
                interval = cfg.get("interval")
            if max_concurrent is None:
                max_concurrent = cfg.get("max_concurrent")

    # Fallback to hardcoded defaults
    if interval is None:
        interval = DEFAULT_INTERVAL
    if max_concurrent is None:
        max_concurrent = DEFAULT_MAX_CONCURRENT

    return int(interval), int(max_concurrent)


def git_cmd(worktree: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command in the given worktree directory."""
    cmd = ["git", "-C", worktree] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def git_pull(worktree: str, batch: bool = False) -> None:
    """Pull latest changes in the worktree (best-effort)."""
    result = git_cmd(worktree, "pull", "--rebase=false", check=False)
    if result.returncode != 0 and not batch:
        log(f"git pull warning: {result.stderr.strip()}", batch)


def git_commit_push_if_changes(worktree: str, message: str, batch: bool = False) -> None:
    """Stage all changes in worktree, commit and push if there are changes."""
    git_cmd(worktree, "add", "-A", check=False)
    # Check if there are staged changes
    result = git_cmd(worktree, "diff", "--cached", "--quiet", check=False)
    if result.returncode != 0:
        git_cmd(worktree, "commit", "-m", message, check=False)
        push_result = git_cmd(worktree, "push", check=False)
        if push_result.returncode != 0 and not batch:
            log(f"git push warning: {push_result.stderr.strip()}", batch)


# ---------------------------------------------------------------------------
# Single-instance enforcement
# ---------------------------------------------------------------------------

def check_pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is alive."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def enforce_single_instance(worktree: str, interval: int, force: bool, batch: bool) -> None:
    """Ensure only one runner is active for this crew.

    Raises SystemExit if another runner is alive and cannot be displaced.
    """
    alive_path = os.path.join(worktree, RUNNER_ALIVE_FILE)
    if not os.path.isfile(alive_path):
        return

    data = read_yaml(alive_path)
    status = data.get("status", "")
    if status != "running":
        return

    remote_hostname = data.get("hostname", "")
    remote_pid = data.get("pid")
    my_hostname = socket.gethostname()
    stale_threshold = interval * 2

    # Check heartbeat freshness
    hb = parse_timestamp(str(data.get("last_heartbeat", "")))
    heartbeat_fresh = False
    if hb is not None:
        age = (datetime.now(timezone.utc) - hb).total_seconds()
        heartbeat_fresh = age <= stale_threshold

    if remote_hostname == my_hostname:
        # Same host — check PID + heartbeat
        pid_alive = remote_pid is not None and check_pid_alive(int(remote_pid))
        if pid_alive and heartbeat_fresh:
            if force:
                log(f"Force-killing existing runner (PID {remote_pid})", batch)
                try:
                    os.kill(int(remote_pid), signal.SIGTERM)
                    # Wait briefly for the old runner to clean up
                    for _ in range(10):
                        if not check_pid_alive(int(remote_pid)):
                            break
                        time.sleep(0.5)
                except OSError:
                    pass
                # Clean up stale state
                write_yaml(alive_path, {
                    "status": "stopped",
                    "pid": int(remote_pid),
                    "hostname": remote_hostname,
                    "last_heartbeat": data.get("last_heartbeat", ""),
                    "started_at": data.get("started_at", ""),
                    "next_check_at": "",
                    "interval": data.get("interval", interval),
                    "requested_action": None,
                })
            else:
                print(f"ERROR: Runner already active on this host (PID {remote_pid}). "
                      f"Use --force to restart.", file=sys.stderr)
                sys.exit(1)
        elif not pid_alive or not heartbeat_fresh:
            reason = "PID dead" if not pid_alive else "heartbeat stale"
            log(f"Stale runner detected ({reason}), cleaning up", batch)
    else:
        # Different host — heartbeat freshness only
        if heartbeat_fresh:
            print(f"ERROR: Runner active on different host '{remote_hostname}'. "
                  f"Cannot force-kill remote process.", file=sys.stderr)
            sys.exit(1)
        else:
            log(f"Stale runner on '{remote_hostname}' (heartbeat expired), taking over", batch)


# ---------------------------------------------------------------------------
# Runner alive management
# ---------------------------------------------------------------------------

def write_runner_alive(worktree: str, interval: int, status: str = "running",
                       requested_action: str | None = None) -> None:
    """Write/update the runner alive file."""
    alive_path = os.path.join(worktree, RUNNER_ALIVE_FILE)
    now = now_utc()
    next_check = ""
    if status == "running":
        next_ts = datetime.now(timezone.utc).timestamp() + interval
        next_check = datetime.fromtimestamp(next_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    data = {
        "status": status,
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "started_at": now if status == "running" else read_yaml(alive_path).get("started_at", now),
        "last_heartbeat": now,
        "next_check_at": next_check,
        "interval": interval,
        "requested_action": requested_action,
    }
    write_yaml(alive_path, data)


def update_runner_heartbeat(worktree: str, interval: int) -> None:
    """Update heartbeat and next_check_at in the runner alive file."""
    alive_path = os.path.join(worktree, RUNNER_ALIVE_FILE)
    now = now_utc()
    next_ts = datetime.now(timezone.utc).timestamp() + interval
    next_check = datetime.fromtimestamp(next_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    update_yaml_field(alive_path, "last_heartbeat", now)
    update_yaml_field(alive_path, "next_check_at", next_check)


def check_requested_action(worktree: str) -> str | None:
    """Check if a stop action was requested via _runner_alive.yaml."""
    alive_path = os.path.join(worktree, RUNNER_ALIVE_FILE)
    if not os.path.isfile(alive_path):
        return None
    data = read_yaml(alive_path)
    action = data.get("requested_action")
    return str(action) if action else None


# ---------------------------------------------------------------------------
# Agent management
# ---------------------------------------------------------------------------

def read_all_agent_statuses(worktree: str) -> dict[str, dict]:
    """Read all agent status files and return {name: data}."""
    agents = {}
    for status_file in list_agent_files(worktree, "_status.yaml"):
        data = read_yaml(status_file)
        name = data.get("agent_name", "")
        if name:
            agents[name] = data
    return agents


def count_running(agents: dict[str, dict]) -> int:
    """Count agents with Running status."""
    return sum(1 for d in agents.values() if d.get("status") == "Running")


def mark_stale_as_error(worktree: str, stale_agents: list[str],
                        agents: dict[str, dict], batch: bool) -> None:
    """Mark stale agents as Error."""
    for name in stale_agents:
        status_file = os.path.join(worktree, f"{name}_status.yaml")
        current = agents[name].get("status", "")
        if validate_agent_transition(current, "Error"):
            log(f"Agent '{name}' heartbeat stale — marking as Error", batch)
            update_yaml_field(status_file, "status", "Error")
            update_yaml_field(status_file, "error_message", "Heartbeat timeout — agent presumed dead")
            update_yaml_field(status_file, "completed_at", now_utc())
            agents[name]["status"] = "Error"
            append_to_agent_log(worktree, name, "STALE: heartbeat timeout — marked as Error")


def process_pending_commands(worktree: str, agents: dict[str, dict], batch: bool) -> None:
    """Process pending runner-level commands from agent command files.

    The runner processes 'pause' and 'resume' commands directed at Running agents.
    'kill' commands are sent by graceful_shutdown, not processed here.
    """
    for name, data in agents.items():
        cmd_file = os.path.join(worktree, f"{name}_commands.yaml")
        if not os.path.isfile(cmd_file):
            continue
        cmd_data = read_yaml(cmd_file)
        pending = cmd_data.get("pending_commands", [])
        if not pending:
            continue

        current_status = data.get("status", "")
        processed = False

        for cmd_entry in pending:
            command = cmd_entry.get("command", "")
            if command == "pause" and current_status == "Running":
                if validate_agent_transition(current_status, "Paused"):
                    log(f"Pausing agent '{name}'", batch)
                    status_file = os.path.join(worktree, f"{name}_status.yaml")
                    update_yaml_field(status_file, "status", "Paused")
                    agents[name]["status"] = "Paused"
                    processed = True
            elif command == "resume" and current_status == "Paused":
                if validate_agent_transition(current_status, "Running"):
                    log(f"Resuming agent '{name}'", batch)
                    status_file = os.path.join(worktree, f"{name}_status.yaml")
                    update_yaml_field(status_file, "status", "Running")
                    agents[name]["status"] = "Running"
                    processed = True
            elif command == "reset" and current_status == "Error":
                if validate_agent_transition(current_status, "Waiting"):
                    log(f"Resetting agent '{name}' to Waiting", batch)
                    if batch:
                        print(f"CMD_RESET:{name}")
                    status_file = os.path.join(worktree, f"{name}_status.yaml")
                    update_yaml_field(status_file, "status", "Waiting")
                    update_yaml_field(status_file, "error_message", "")
                    update_yaml_field(status_file, "completed_at", "")
                    agents[name]["status"] = "Waiting"
                    append_to_agent_log(worktree, name,
                                        "RESET: Error → Waiting (command)")
                    processed = True

        if processed:
            # Ack commands
            write_yaml(cmd_file, {"pending_commands": []})


def enforce_type_limits(ready: list[str], agents: dict[str, dict],
                        meta: dict) -> list[str]:
    """Filter ready agents based on per-type max_parallel limits."""
    agent_types_config = meta.get("agent_types", {})

    # Count currently running agents per type
    running_per_type: dict[str, int] = {}
    for data in agents.values():
        if data.get("status") == "Running":
            atype = data.get("agent_type", "")
            running_per_type[atype] = running_per_type.get(atype, 0) + 1

    filtered = []
    # Track how many we're adding per type in this batch
    adding_per_type: dict[str, int] = {}

    for name in ready:
        agent_data = agents.get(name, {})
        atype = agent_data.get("agent_type", "")
        type_config = agent_types_config.get(atype, {})
        max_parallel = type_config.get("max_parallel", 0)

        if max_parallel <= 0:
            # 0 = unlimited
            filtered.append(name)
            adding_per_type[atype] = adding_per_type.get(atype, 0) + 1
        else:
            current_running = running_per_type.get(atype, 0)
            current_adding = adding_per_type.get(atype, 0)
            if current_running + current_adding < max_parallel:
                filtered.append(name)
                adding_per_type[atype] = current_adding + 1

    return filtered


def launch_agent(worktree: str, name: str, agents: dict[str, dict],
                 meta: dict, dry_run: bool, batch: bool) -> None:
    """Launch a single agent: transition Waiting→Ready→Running and start process."""
    status_file = os.path.join(worktree, f"{name}_status.yaml")
    work2do_file = os.path.join(worktree, f"{name}_work2do.md")

    # Read agent type and resolve agent_string
    agent_data = agents.get(name, {})
    atype = agent_data.get("agent_type", "")
    agent_types_config = meta.get("agent_types", {})
    type_config = agent_types_config.get(atype, {})
    agent_string = type_config.get("agent_string", "")

    if not agent_string:
        log(f"WARNING: No agent_string for type '{atype}', skipping agent '{name}'", batch)
        return

    # Read work2do content
    if not os.path.isfile(work2do_file):
        log(f"WARNING: No work2do file for agent '{name}', skipping", batch)
        return
    with open(work2do_file) as f:
        work2do_content = f.read().strip()

    if dry_run:
        print(f"DRY_RUN: Would launch agent '{name}' (type={atype}, "
              f"agent_string={agent_string})")
        return

    # Assemble the full prompt with file path references
    worktree_rel = os.path.relpath(worktree, _repo_root) if _repo_root else worktree
    agent_files_preamble = (
        f"## Your Agent Files\n\n"
        f"All your files are in: {worktree_rel}\n\n"
        f"- `_work2do.md` \u2192 {worktree_rel}/{name}_work2do.md\n"
        f"- `_input.md` \u2192 {worktree_rel}/{name}_input.md\n"
        f"- `_output.md` \u2192 {worktree_rel}/{name}_output.md\n"
        f"- `_instructions.md` \u2192 {worktree_rel}/{name}_instructions.md\n"
        f"- `_status.yaml` \u2192 {worktree_rel}/{name}_status.yaml\n"
        f"- `_commands.yaml` \u2192 {worktree_rel}/{name}_commands.yaml\n"
        f"- `_alive.yaml` \u2192 {worktree_rel}/{name}_alive.yaml\n"
        f"\n---\n\n"
    )
    full_prompt = agent_files_preamble + work2do_content

    # Write assembled prompt to a file instead of passing inline
    prompt_file = os.path.join(worktree, f"{name}_prompt.md")
    with open(prompt_file, "w") as pf:
        pf.write(full_prompt)
    prompt_rel = os.path.relpath(prompt_file, _repo_root) if _repo_root else prompt_file

    # Transition Waiting → Ready
    current = agent_data.get("status", "")
    if current == "Waiting":
        if validate_agent_transition(current, "Ready"):
            update_yaml_field(status_file, "status", "Ready")
            agents[name]["status"] = "Ready"
            current = "Ready"

    # Transition Ready → Running
    if current == "Ready":
        if validate_agent_transition(current, "Running"):
            update_yaml_field(status_file, "status", "Running")
            update_yaml_field(status_file, "started_at", now_utc())
            agents[name]["status"] = "Running"

    # Launch the agent process
    log(f"Launching agent '{name}' (type={atype}, string={agent_string})", batch)
    try:
        # Capture agent stdout/stderr to a per-agent log file
        log_path = os.path.join(worktree, f"{name}_log.txt")
        log_fh = open(log_path, "a")
        ait_cmd = os.path.join(_repo_root, "ait") if _repo_root else "./ait"
        short_prompt = f"Read and follow all instructions in the file: {prompt_rel}"
        cmd = [ait_cmd, "codeagent", "--agent-string", agent_string,
               "invoke", "raw", "-p", short_prompt]
        log_fh.write(f"=== Agent: {name} | Type: {atype} | String: {agent_string} ===\n")
        log_fh.write(f"=== Started: {now_utc()} ===\n")
        log_fh.write(f"=== Prompt file: {prompt_rel} ===\n")
        log_fh.write(f"=== Command: {' '.join(cmd)} ===\n")
        log_fh.write(f"{'=' * 60}\n")
        log_fh.flush()

        proc = subprocess.Popen(cmd, cwd=_repo_root or ".", stdout=log_fh, stderr=log_fh)
        _log_handles[name] = log_fh
        update_yaml_field(status_file, "pid", proc.pid)
        agents[name]["pid"] = proc.pid
        # Write initial heartbeat so agent isn't considered stale before it
        # writes its own first heartbeat
        alive_path = os.path.join(worktree, f"{name}_alive.yaml")
        update_yaml_field(alive_path, "last_heartbeat", now_utc())
        if batch:
            print(f"LAUNCHED:{name}:{proc.pid}")
    except OSError as e:
        log(f"ERROR: Failed to launch agent '{name}': {e}", batch)
        update_yaml_field(status_file, "status", "Error")
        update_yaml_field(status_file, "error_message", f"Launch failed: {e}")
        update_yaml_field(status_file, "completed_at", now_utc())
        agents[name]["status"] = "Error"


def recompute_crew_status(worktree: str, agents: dict[str, dict]) -> None:
    """Recompute and write the crew status from all agent statuses."""
    agent_statuses = [d.get("status", "") for d in agents.values()]
    new_status = compute_crew_status(agent_statuses)

    crew_status_path = os.path.join(worktree, CREW_STATUS_FILE)
    data = read_yaml(crew_status_path)
    old_status = data.get("status", "")

    total = len(agents)
    completed = sum(1 for s in agent_statuses if s == "Completed")
    progress = int(completed / total * 100) if total > 0 else 0

    data["status"] = new_status
    data["progress"] = progress
    data["updated_at"] = now_utc()

    # Set started_at on first transition to Running
    if new_status == "Running" and old_status == "Initializing" and not data.get("started_at"):
        data["started_at"] = now_utc()

    write_yaml(crew_status_path, data)


# ---------------------------------------------------------------------------
# Progress and ETA
# ---------------------------------------------------------------------------

def compute_progress_eta(agents: dict[str, dict]) -> tuple[int, str]:
    """Compute progress percentage and ETA estimate."""
    total = len(agents)
    if total == 0:
        return 0, "N/A"

    completed = sum(1 for d in agents.values() if d.get("status") == "Completed")
    progress = int(completed / total * 100)

    # ETA: average completion time of finished agents * remaining
    completed_times = []
    for d in agents.values():
        if d.get("status") == "Completed" and d.get("started_at") and d.get("completed_at"):
            started = parse_timestamp(str(d["started_at"]))
            finished = parse_timestamp(str(d["completed_at"]))
            if started and finished:
                completed_times.append((finished - started).total_seconds())

    remaining = total - completed
    if completed_times and remaining > 0:
        avg_time = sum(completed_times) / len(completed_times)
        eta_seconds = avg_time * remaining
        if eta_seconds > 3600:
            eta = f"{eta_seconds / 3600:.1f}h"
        elif eta_seconds > 60:
            eta = f"{eta_seconds / 60:.0f}m"
        else:
            eta = f"{eta_seconds:.0f}s"
    else:
        eta = "N/A"

    return progress, eta


# ---------------------------------------------------------------------------
# Diagnostic mode
# ---------------------------------------------------------------------------

def cmd_check(worktree: str, interval: int, batch: bool) -> int:
    """Diagnostic mode: print runner status and exit."""
    git_pull(worktree, batch)

    alive_path = os.path.join(worktree, RUNNER_ALIVE_FILE)
    if not os.path.isfile(alive_path):
        if batch:
            print("RUNNER_STATUS:not_running")
        else:
            print("Runner: not running (no alive file)")
        return 1

    data = read_yaml(alive_path)
    status = data.get("status", "unknown")
    hostname = data.get("hostname", "unknown")
    pid = data.get("pid", "unknown")
    hb_str = str(data.get("last_heartbeat", ""))
    next_check = data.get("next_check_at", "")
    started_at = data.get("started_at", "")

    hb = parse_timestamp(hb_str)
    if hb:
        age = (datetime.now(timezone.utc) - hb).total_seconds()
        age_str = f"{age:.0f}s ago"
        stale_threshold = interval * 2
        alive_assessment = "alive" if age <= stale_threshold else "stale"
    else:
        age_str = "never"
        alive_assessment = "stale"

    if batch:
        print(f"RUNNER_STATUS:{status}")
        print(f"RUNNER_HOSTNAME:{hostname}")
        print(f"RUNNER_PID:{pid}")
        print(f"RUNNER_HEARTBEAT:{hb_str}")
        print(f"RUNNER_HEARTBEAT_AGE:{age_str}")
        print(f"RUNNER_NEXT_CHECK:{next_check}")
        print(f"RUNNER_ALIVE:{alive_assessment}")
    else:
        print(f"Runner status: {status}")
        print(f"  Hostname:    {hostname}")
        print(f"  PID:         {pid}")
        print(f"  Started:     {started_at}")
        print(f"  Heartbeat:   {hb_str} ({age_str})")
        print(f"  Next check:  {next_check}")
        print(f"  Assessment:  {alive_assessment}")

    return 0 if status == "running" and alive_assessment == "alive" else 1


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------

class ShutdownRequested(Exception):
    """Raised when SIGTERM/SIGINT is received."""


_should_stop = False


def _signal_handler(signum: int, frame) -> None:
    """Handle SIGTERM/SIGINT by setting the stop flag."""
    global _should_stop
    _should_stop = True


def graceful_shutdown(worktree: str, crew_id: str, interval: int, batch: bool) -> None:
    """Perform graceful shutdown: kill agents, update status."""
    log("Graceful shutdown initiated", batch)

    # Send kill command to all running agents
    cmd_path = os.path.join(_repo_root, "ait") if _repo_root else "./ait"

    subprocess.run(
        [cmd_path, "crew", "command", "send-all", "--crew", crew_id, "--command", "kill"],
        capture_output=True, check=False,
    )

    # Update runner alive to stopped
    write_runner_alive(worktree, interval, status="stopped")

    # Update crew status to Killing
    crew_status_path = os.path.join(worktree, CREW_STATUS_FILE)
    if os.path.isfile(crew_status_path):
        update_yaml_field(crew_status_path, "status", "Killing")
        update_yaml_field(crew_status_path, "updated_at", now_utc())

    # Close agent log file handles
    for name, fh in _log_handles.items():
        try:
            fh.close()
        except Exception:
            pass
    _log_handles.clear()

    git_commit_push_if_changes(worktree, "runner: graceful shutdown", batch)

    if batch:
        print("SHUTDOWN:complete")
    else:
        log("Shutdown complete", batch)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_loop(worktree: str, crew_id: str, interval: int, max_concurrent: int,
             once: bool, dry_run: bool, batch: bool,
             reset_errors: bool = False) -> int:
    """Run the main orchestration loop."""
    global _should_stop

    meta_path = os.path.join(worktree, CREW_META_FILE)
    if not os.path.isfile(meta_path):
        print(f"ERROR: Crew meta file not found: {meta_path}", file=sys.stderr)
        return 1

    meta = read_yaml(meta_path)

    # Get heartbeat timeout from meta
    hb_timeout_min = meta.get("heartbeat_timeout_minutes", 5)
    hb_timeout = int(hb_timeout_min) * 60

    # Install signal handlers
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    # Write initial runner alive
    if not dry_run:
        write_runner_alive(worktree, interval)
        git_commit_push_if_changes(worktree, "runner: started", batch)

    # Reset errored agents if requested (one-time at startup)
    if reset_errors:
        startup_agents = read_all_agent_statuses(worktree)
        for name, data in startup_agents.items():
            if data.get("status") == "Error":
                if dry_run:
                    log(f"DRY_RUN: Would reset agent '{name}' to Waiting", batch)
                    if batch:
                        print(f"RESET_DRY:{name}")
                else:
                    status_file = os.path.join(worktree, f"{name}_status.yaml")
                    update_yaml_field(status_file, "status", "Waiting")
                    update_yaml_field(status_file, "error_message", "")
                    update_yaml_field(status_file, "completed_at", "")
                    log(f"Reset errored agent '{name}' to Waiting", batch)
                    if batch:
                        print(f"RESET:{name}")
                    append_to_agent_log(worktree, name,
                                        "RESET: Error → Waiting (--reset-errors)")
        if not dry_run:
            git_commit_push_if_changes(worktree, "runner: reset errored agents",
                                       batch)

    iteration = 0
    while not _should_stop:
        iteration += 1
        log(f"--- Iteration {iteration} ---", batch)

        # Update heartbeat
        if not dry_run:
            update_runner_heartbeat(worktree, interval)

        # Pull latest changes
        if not dry_run:
            git_pull(worktree, batch)

        # Check for stop request
        action = check_requested_action(worktree)
        if action == "stop":
            graceful_shutdown(worktree, crew_id, interval, batch)
            break

        # Read all agent statuses
        agents = read_all_agent_statuses(worktree)

        # Mark stale agents as Error
        stale = get_stale_agents(worktree, hb_timeout)
        if stale:
            mark_stale_as_error(worktree, stale, agents, batch)

        # Process pending commands
        process_pending_commands(worktree, agents, batch)

        # Find ready agents
        ready = get_ready_agents(worktree)
        if ready:
            log(f"Ready agents: {', '.join(ready)}", batch)

        # Sort by group priority (lower sequence first, no-group last)
        groups = load_groups(worktree)
        if groups and ready:
            agent_data = {
                name: read_yaml(os.path.join(worktree, f"{name}_status.yaml"))
                for name in ready
            }
            ready = sorted(
                ready,
                key=lambda n: group_sort_key(agent_data.get(n, {}), groups),
            )

        # Enforce per-type limits
        ready = enforce_type_limits(ready, agents, meta)

        # Enforce overall max concurrent
        running_count = count_running(agents)
        available_slots = max(0, max_concurrent - running_count)
        ready = ready[:available_slots]

        # Launch ready agents
        for agent_name in ready:
            launch_agent(worktree, agent_name, agents, meta, dry_run, batch)

        # Recompute crew status
        if not dry_run:
            recompute_crew_status(worktree, agents)

        # Progress report
        progress, eta = compute_progress_eta(agents)
        if batch:
            print(f"PROGRESS:{progress}")
            print(f"ETA:{eta}")
            print(f"RUNNING:{count_running(agents)}")
            print(f"READY:{len(get_ready_agents(worktree))}")
        else:
            log(f"Progress: {progress}% | Running: {count_running(agents)}/{max_concurrent} | ETA: {eta}", batch)

        # Check if all agents are in terminal state
        all_terminal = all(
            d.get("status") in ("Completed", "Aborted", "Error")
            for d in agents.values()
        ) if agents else False

        if all_terminal:
            log("All agents in terminal state — stopping runner", batch)
            if not dry_run:
                write_runner_alive(worktree, interval, status="stopped")
                recompute_crew_status(worktree, agents)
            if batch:
                print("ALL_TERMINAL")
            break

        # Commit and push changes
        if not dry_run:
            git_commit_push_if_changes(worktree, f"runner: iteration {iteration}", batch)

        if once:
            if batch:
                print("ONCE_COMPLETE")
            break

        # Sleep until next iteration
        log(f"Sleeping {interval}s", batch)
        for _ in range(interval):
            if _should_stop:
                break
            time.sleep(1)

    # Final cleanup
    if _should_stop and not once:
        graceful_shutdown(worktree, crew_id, interval, batch)

    return 0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """Parse arguments and dispatch to the appropriate command."""
    parser = argparse.ArgumentParser(
        prog="ait crew runner",
        description="AgentCrew Runner — orchestrate agent execution",
    )
    parser.add_argument("--crew", required=True, help="Crew identifier")
    parser.add_argument("--interval", type=int, default=None,
                        help=f"Seconds between iterations (default: config or {DEFAULT_INTERVAL})")
    parser.add_argument("--max-concurrent", type=int, default=None,
                        help=f"Max concurrent agents (default: config or {DEFAULT_MAX_CONCURRENT})")
    parser.add_argument("--once", action="store_true", help="Run single iteration")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without executing")
    parser.add_argument("--batch", action="store_true", help="Structured output")
    parser.add_argument("--check", action="store_true", help="Diagnostic mode")
    parser.add_argument("--force", action="store_true",
                        help="Force restart if runner already active on same host")
    parser.add_argument("--reset-errors", action="store_true",
                        help="Reset Error agents back to Waiting before starting")

    args = parser.parse_args()
    crew_id = args.crew

    # Resolve repo root (for ait command path)
    global _repo_root
    _repo_root = resolve_repo_root()

    # Resolve worktree
    worktree = crew_worktree_path(crew_id)
    if not os.path.isdir(worktree):
        print(f"ERROR: Crew worktree not found: {worktree}", file=sys.stderr)
        print(f"Run 'ait crew init --id {crew_id}' first.", file=sys.stderr)
        return 1

    # Resolve config
    interval, max_concurrent = resolve_config(args.interval, args.max_concurrent)

    # Diagnostic mode
    if args.check:
        return cmd_check(worktree, interval, args.batch)

    # Single-instance enforcement
    if not args.dry_run:
        git_pull(worktree, args.batch)
        enforce_single_instance(worktree, interval, args.force, args.batch)

    if not args.batch:
        log(f"Starting runner for crew '{crew_id}'")
        log(f"  Worktree:       {worktree}")
        log(f"  Interval:       {interval}s")
        log(f"  Max concurrent: {max_concurrent}")
        log(f"  Mode:           {'once' if args.once else 'continuous'}"
            f"{'  (dry-run)' if args.dry_run else ''}")

    return run_loop(worktree, crew_id, interval, max_concurrent,
                    args.once, args.dry_run, args.batch, args.reset_errors)


if __name__ == "__main__":
    sys.exit(main())
