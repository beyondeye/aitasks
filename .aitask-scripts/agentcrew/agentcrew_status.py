#!/usr/bin/env python3
"""AgentCrew status management CLI.

Sub-commands: get, set, list, heartbeat.
Structured output for parsing by bash scripts and the crew runner.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from agentcrew.agentcrew_utils import (
    AGENTCREW_DIR,
    AGENT_STATUSES,
    check_agent_alive,
    compute_crew_status,
    crew_worktree_path,
    get_agent_names,
    get_ready_agents,
    get_stale_agents,
    list_agent_files,
    read_yaml,
    update_yaml_field,
    validate_agent_transition,
    write_yaml,
)


def resolve_crew(crew_id: str) -> str:
    """Resolve and validate crew worktree path."""
    wt = crew_worktree_path(crew_id)
    if not os.path.isdir(wt):
        print(f"Error: Crew '{crew_id}' not found: worktree '{wt}' does not exist", file=sys.stderr)
        sys.exit(1)
    return wt


def now_utc() -> str:
    """Return current UTC timestamp as string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------


def cmd_get(args: argparse.Namespace) -> None:
    """Get status of a crew or specific agent."""
    wt = resolve_crew(args.crew)

    if args.agent:
        # Agent-level status
        status_path = os.path.join(wt, f"{args.agent}_status.yaml")
        if not os.path.isfile(status_path):
            print(f"Error: Agent '{args.agent}' not found in crew '{args.crew}'", file=sys.stderr)
            sys.exit(1)
        data = read_yaml(status_path)
        print(f"AGENT_STATUS:{data.get('status', 'Unknown')}")
        print(f"AGENT_PROGRESS:{data.get('progress', 0)}")

        # Heartbeat info
        alive_path = os.path.join(wt, f"{args.agent}_alive.yaml")
        if os.path.isfile(alive_path):
            alive_data = read_yaml(alive_path)
            hb = alive_data.get("last_heartbeat", "")
            print(f"AGENT_HEARTBEAT:{hb if hb else 'never'}")
        else:
            print("AGENT_HEARTBEAT:never")
    else:
        # Crew-level status
        crew_status_path = os.path.join(wt, "_crew_status.yaml")
        if not os.path.isfile(crew_status_path):
            print(f"Error: Crew status file not found for '{args.crew}'", file=sys.stderr)
            sys.exit(1)
        data = read_yaml(crew_status_path)
        print(f"CREW_STATUS:{data.get('status', 'Unknown')}")
        print(f"CREW_PROGRESS:{data.get('progress', 0)}")


def cmd_set(args: argparse.Namespace) -> None:
    """Set agent status with transition validation."""
    wt = resolve_crew(args.crew)

    if not args.agent:
        print("Error: --agent is required for 'set' command", file=sys.stderr)
        sys.exit(1)

    status_path = os.path.join(wt, f"{args.agent}_status.yaml")
    if not os.path.isfile(status_path):
        print(f"Error: Agent '{args.agent}' not found in crew '{args.crew}'", file=sys.stderr)
        sys.exit(1)

    data = read_yaml(status_path)
    current = data.get("status", "Unknown")

    if args.status:
        new_status = args.status
        if new_status not in AGENT_STATUSES:
            print(f"Error: Invalid status '{new_status}'. Valid: {', '.join(AGENT_STATUSES)}", file=sys.stderr)
            sys.exit(1)

        if not validate_agent_transition(current, new_status):
            print(f"Error: Invalid transition {current} -> {new_status} for agent '{args.agent}'", file=sys.stderr)
            sys.exit(1)

        data["status"] = new_status
        now = now_utc()

        if new_status == "Running" and not data.get("started_at"):
            data["started_at"] = now
        if new_status in ("Completed", "Aborted", "Error"):
            data["completed_at"] = now

        print(f"STATUS_SET:{args.agent}:{current}:{new_status}")

    if args.progress is not None:
        data["progress"] = args.progress

    write_yaml(status_path, data)

    # Recompute crew status
    _recompute_crew_status(wt)


def cmd_list(args: argparse.Namespace) -> None:
    """List all agents with their status, progress, and heartbeat."""
    wt = resolve_crew(args.crew)
    timeout = _get_heartbeat_timeout(wt)
    group_filter = getattr(args, "group", None) or None

    for status_file in list_agent_files(wt, "_status.yaml"):
        data = read_yaml(status_file)
        name = data.get("agent_name", "")
        if not name:
            continue
        if group_filter and data.get("group", "") != group_filter:
            continue
        status = data.get("status", "Unknown")
        progress = data.get("progress", 0)

        alive_path = os.path.join(wt, f"{name}_alive.yaml")
        hb = "never"
        if os.path.isfile(alive_path):
            alive_data = read_yaml(alive_path)
            hb_val = alive_data.get("last_heartbeat", "")
            if hb_val:
                hb = str(hb_val)

        print(f"AGENT:{name} STATUS:{status} PROGRESS:{progress} HEARTBEAT:{hb}")

    # Also show ready agents and stale agents (filtered by group if active)
    ready = get_ready_agents(wt)
    stale = get_stale_agents(wt, timeout)
    if group_filter:
        from agentcrew.agentcrew_utils import get_group_agents
        group_members = set(get_group_agents(wt, group_filter))
        ready = [a for a in ready if a in group_members]
        stale = [a for a in stale if a in group_members]
    if ready:
        print(f"READY_AGENTS:{','.join(ready)}")
    if stale:
        print(f"STALE_AGENTS:{','.join(stale)}")


def cmd_heartbeat(args: argparse.Namespace) -> None:
    """Update agent heartbeat."""
    wt = resolve_crew(args.crew)

    if not args.agent:
        print("Error: --agent is required for 'heartbeat' command", file=sys.stderr)
        sys.exit(1)

    # Verify agent exists
    status_path = os.path.join(wt, f"{args.agent}_status.yaml")
    if not os.path.isfile(status_path):
        print(f"Error: Agent '{args.agent}' not found in crew '{args.crew}'", file=sys.stderr)
        sys.exit(1)

    alive_path = os.path.join(wt, f"{args.agent}_alive.yaml")
    now = now_utc()

    data = {}
    if os.path.isfile(alive_path):
        data = read_yaml(alive_path)
    data["last_heartbeat"] = now
    if args.message:
        data["last_message"] = args.message

    write_yaml(alive_path, data)
    print(f"HEARTBEAT_UPDATED:{args.agent}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_heartbeat_timeout(wt: str) -> int:
    """Read heartbeat timeout from crew meta, default 300s (5min)."""
    meta_path = os.path.join(wt, "_crew_meta.yaml")
    if os.path.isfile(meta_path):
        data = read_yaml(meta_path)
        minutes = data.get("heartbeat_timeout_minutes", 5)
        try:
            return int(minutes) * 60
        except (TypeError, ValueError):
            pass
    return 300


def _recompute_crew_status(wt: str) -> None:
    """Recompute and update the crew-level status from all agent statuses."""
    statuses = []
    for status_file in list_agent_files(wt, "_status.yaml"):
        data = read_yaml(status_file)
        s = data.get("status")
        if s:
            statuses.append(s)

    new_crew_status = compute_crew_status(statuses)
    crew_status_path = os.path.join(wt, "_crew_status.yaml")

    if os.path.isfile(crew_status_path):
        crew_data = read_yaml(crew_status_path)
        crew_data["status"] = new_crew_status
        crew_data["updated_at"] = now_utc()

        # Compute overall progress
        total = len(statuses)
        if total > 0:
            completed = sum(1 for s in statuses if s == "Completed")
            crew_data["progress"] = int(completed * 100 / total)

        write_yaml(crew_status_path, crew_data)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AgentCrew status management",
        prog="ait crew status",
    )
    parser.add_argument("--crew", required=True, help="Crew identifier")
    parser.add_argument("--agent", help="Agent name (omit for crew-level)")

    sub = parser.add_subparsers(dest="command")

    # get
    sub.add_parser("get", help="Get status of crew or agent")

    # set
    set_p = sub.add_parser("set", help="Set agent status")
    set_p.add_argument("--status", help="New status value")
    set_p.add_argument("--progress", type=int, help="Progress percentage (0-100)")

    # list
    list_p = sub.add_parser("list", help="List all agents with status")
    list_p.add_argument("--group", help="Filter to agents in this group")

    # heartbeat
    hb_p = sub.add_parser("heartbeat", help="Update agent heartbeat")
    hb_p.add_argument("--message", help="Optional progress message")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "get": cmd_get,
        "set": cmd_set,
        "list": cmd_list,
        "heartbeat": cmd_heartbeat,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
