"""AgentCrew reporting CLI: summary, detail, output aggregation, crew listing."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from agentcrew_utils import (
    AGENTCREW_DIR,
    check_agent_alive,
    crew_worktree_path,
    format_elapsed,
    get_agent_names,
    list_agent_files,
    list_crews,
    read_yaml,
    topo_sort,
    _parse_timestamp,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _elapsed_since(ts_str: str) -> float | None:
    """Return seconds elapsed since a timestamp string, or None."""
    ts = _parse_timestamp(ts_str)
    if ts is None:
        return None
    return (datetime.now(timezone.utc) - ts).total_seconds()


def _heartbeat_age(ts_str: str) -> str:
    """Return a human-readable heartbeat age string."""
    elapsed = _elapsed_since(ts_str)
    if elapsed is None:
        return "never"
    return f"{format_elapsed(elapsed)} ago"


def _read_file_content(path: str, max_lines: int = 0) -> str:
    """Read a text file's content, optionally limiting lines."""
    if not os.path.isfile(path):
        return ""
    with open(path) as f:
        if max_lines > 0:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    lines.append(f"... ({max_lines} lines shown)\n")
                    break
                lines.append(line)
            return "".join(lines)
        return f.read()


# ---------------------------------------------------------------------------
# Sub-command: summary
# ---------------------------------------------------------------------------


def cmd_summary(crew_id: str, batch: bool, group_filter: str | None = None) -> int:
    """Print a summary report for a crew."""
    wt = crew_worktree_path(crew_id)
    if not os.path.isdir(wt):
        print(f"ERROR:Crew '{crew_id}' not found", file=sys.stderr)
        return 1

    meta = read_yaml(os.path.join(wt, "_crew_meta.yaml"))
    status_data = read_yaml(os.path.join(wt, "_crew_status.yaml"))
    runner_path = os.path.join(wt, "_runner_alive.yaml")
    runner_data = read_yaml(runner_path) if os.path.isfile(runner_path) else {}

    crew_status = status_data.get("status", "Unknown")
    crew_progress = status_data.get("progress", 0)
    created_at = meta.get("created_at", "")
    started_at = status_data.get("started_at", "")

    # Compute elapsed time
    elapsed_str = ""
    elapsed_secs = _elapsed_since(str(started_at)) if started_at else None
    if elapsed_secs is not None:
        elapsed_str = format_elapsed(elapsed_secs)

    # Runner info
    runner_status = runner_data.get("status", "stopped")
    runner_hb = str(runner_data.get("last_heartbeat", ""))

    # Load all agent data
    agents = []
    for status_file in list_agent_files(wt, "_status.yaml"):
        data = read_yaml(status_file)
        name = data.get("agent_name", "")
        if not name:
            continue
        if group_filter and data.get("group", "") != group_filter:
            continue
        alive_path = os.path.join(wt, f"{name}_alive.yaml")
        alive_data = read_yaml(alive_path) if os.path.isfile(alive_path) else {}

        agent_started = data.get("started_at", "")
        agent_elapsed = _elapsed_since(str(agent_started)) if agent_started else None

        agent_hb = str(alive_data.get("last_heartbeat", ""))
        deps = data.get("depends_on", [])
        blocked_by = []
        if data.get("status") == "Waiting" and deps:
            for dep in deps:
                dep_status_path = os.path.join(wt, f"{dep}_status.yaml")
                if os.path.isfile(dep_status_path):
                    dep_data = read_yaml(dep_status_path)
                    if dep_data.get("status") != "Completed":
                        blocked_by.append(dep)

        agents.append({
            "name": name,
            "status": data.get("status", "Unknown"),
            "progress": data.get("progress", 0),
            "elapsed": agent_elapsed,
            "heartbeat": agent_hb,
            "blocked_by": blocked_by,
        })

    if batch:
        print(f"CREW_ID:{crew_id}")
        print(f"CREW_STATUS:{crew_status}")
        print(f"CREW_PROGRESS:{crew_progress}")
        if elapsed_str:
            print(f"CREW_ELAPSED:{elapsed_str}")
        print(f"RUNNER_STATUS:{runner_status}")
        for a in agents:
            parts = [f"AGENT:{a['name']}", f"STATUS:{a['status']}", f"PROGRESS:{a['progress']}"]
            if a["elapsed"] is not None:
                parts.append(f"ELAPSED:{int(a['elapsed'])}")
            if a["heartbeat"]:
                parts.append(f"HEARTBEAT:{a['heartbeat']}")
            if a["blocked_by"]:
                parts.append(f"BLOCKED_BY:{','.join(a['blocked_by'])}")
            print(" ".join(parts))
    else:
        print(f"Crew: {meta.get('name', crew_id)} ({crew_status})")
        line2_parts = []
        if created_at:
            line2_parts.append(f"Created: {created_at}")
        if elapsed_str:
            line2_parts.append(f"Elapsed: {elapsed_str}")
        line2_parts.append(f"Progress: {crew_progress}%")
        print(" | ".join(line2_parts))
        print(f"Runner: {runner_status}", end="")
        if runner_hb:
            print(f" (heartbeat: {_heartbeat_age(runner_hb)})", end="")
        print()
        print()

        # Agent table
        if agents:
            # Calculate column widths
            name_w = max(len(a["name"]) for a in agents)
            name_w = max(name_w, 4)  # min "Name" header
            status_w = max(len(a["status"]) for a in agents)
            status_w = max(status_w, 6)  # min "Status" header

            print(f"  {'Name':<{name_w}}  {'Status':<{status_w}}  {'Prog':>5}  Details")
            print(f"  {'-' * name_w}  {'-' * status_w}  -----  -------")
            for a in agents:
                details = []
                if a["elapsed"] is not None:
                    details.append(f"({format_elapsed(a['elapsed'])})")
                if a["heartbeat"] and a["status"] == "Running":
                    details.append(f"heartbeat: {_heartbeat_age(a['heartbeat'])}")
                if a["blocked_by"]:
                    details.append(f"blocked by: {', '.join(a['blocked_by'])}")
                detail_str = ", ".join(details) if details else ""
                prog_str = f"{a['progress']}%"
                print(f"  {a['name']:<{name_w}}  {a['status']:<{status_w}}  {prog_str:>5}  {detail_str}")

    return 0


# ---------------------------------------------------------------------------
# Sub-command: detail
# ---------------------------------------------------------------------------


def cmd_detail(crew_id: str, agent_name: str, batch: bool) -> int:
    """Print detailed report for a specific agent."""
    wt = crew_worktree_path(crew_id)
    if not os.path.isdir(wt):
        print(f"ERROR:Crew '{crew_id}' not found", file=sys.stderr)
        return 1

    status_path = os.path.join(wt, f"{agent_name}_status.yaml")
    if not os.path.isfile(status_path):
        print(f"ERROR:Agent '{agent_name}' not found in crew '{crew_id}'", file=sys.stderr)
        return 1

    status_data = read_yaml(status_path)
    alive_path = os.path.join(wt, f"{agent_name}_alive.yaml")
    alive_data = read_yaml(alive_path) if os.path.isfile(alive_path) else {}

    work2do_path = os.path.join(wt, f"{agent_name}_work2do.md")
    output_path = os.path.join(wt, f"{agent_name}_output.md")
    work2do_content = _read_file_content(work2do_path, max_lines=20)
    output_content = _read_file_content(output_path)

    if batch:
        print(f"AGENT:{agent_name}")
        print(f"STATUS:{status_data.get('status', 'Unknown')}")
        print(f"PROGRESS:{status_data.get('progress', 0)}")
        print(f"AGENT_TYPE:{status_data.get('agent_type', '')}")
        deps = status_data.get("depends_on", [])
        if deps:
            print(f"DEPENDS_ON:{','.join(deps)}")
        print(f"STARTED_AT:{status_data.get('started_at', '')}")
        print(f"COMPLETED_AT:{status_data.get('completed_at', '')}")
        hb = alive_data.get("last_heartbeat", "")
        if hb:
            print(f"HEARTBEAT:{hb}")
        msg = alive_data.get("last_message", "")
        if msg:
            print(f"HEARTBEAT_MESSAGE:{msg}")
        err = status_data.get("error_message", "")
        if err:
            print(f"ERROR_MESSAGE:{err}")
        if work2do_content:
            print(f"HAS_WORK2DO:true")
        if output_content:
            print(f"HAS_OUTPUT:true")
    else:
        print(f"Agent: {agent_name}")
        print(f"Status: {status_data.get('status', 'Unknown')}")
        print(f"Progress: {status_data.get('progress', 0)}%")
        print(f"Type: {status_data.get('agent_type', 'N/A')}")
        deps = status_data.get("depends_on", [])
        if deps:
            print(f"Depends on: {', '.join(deps)}")
        print(f"Started: {status_data.get('started_at', 'N/A')}")
        print(f"Completed: {status_data.get('completed_at', 'N/A')}")
        hb = alive_data.get("last_heartbeat", "")
        if hb:
            print(f"Heartbeat: {_heartbeat_age(hb)}")
        msg = alive_data.get("last_message", "")
        if msg:
            print(f"Last message: {msg}")
        err = status_data.get("error_message", "")
        if err:
            print(f"Error: {err}")

        if work2do_content:
            print()
            print("--- Work2Do (preview) ---")
            print(work2do_content)

        if output_content:
            print()
            print("--- Output ---")
            print(output_content)

    return 0


# ---------------------------------------------------------------------------
# Sub-command: output
# ---------------------------------------------------------------------------


def cmd_output(crew_id: str, batch: bool, group_filter: str | None = None) -> int:
    """Aggregate all agent output files in dependency order."""
    wt = crew_worktree_path(crew_id)
    if not os.path.isdir(wt):
        print(f"ERROR:Crew '{crew_id}' not found", file=sys.stderr)
        return 1

    # Build dependency graph for topo sort
    agents_deps: dict[str, list[str]] = {}
    for status_file in list_agent_files(wt, "_status.yaml"):
        data = read_yaml(status_file)
        name = data.get("agent_name", "")
        if name:
            if group_filter and data.get("group", "") != group_filter:
                continue
            agents_deps[name] = data.get("depends_on", [])

    try:
        ordered = topo_sort(agents_deps)
    except ValueError:
        ordered = sorted(agents_deps.keys())

    found_output = False
    for agent_name in ordered:
        output_path = os.path.join(wt, f"{agent_name}_output.md")
        content = _read_file_content(output_path)
        if not content.strip():
            continue
        found_output = True
        if batch:
            print(f"OUTPUT_AGENT:{agent_name}")
            print(content)
            print(f"OUTPUT_END:{agent_name}")
        else:
            print(f"=== {agent_name} ===")
            print(content)
            print()

    if not found_output:
        if batch:
            print("NO_OUTPUT")
        else:
            print("No agent output files found.")

    return 0


# ---------------------------------------------------------------------------
# Sub-command: list
# ---------------------------------------------------------------------------


def cmd_list(batch: bool) -> int:
    """List all agentcrews."""
    crews = list_crews()

    if not crews:
        if batch:
            print("NO_CREWS")
        else:
            print("No agentcrews found.")
        return 0

    if batch:
        for c in crews:
            parts = [
                f"CREW:{c['id']}",
                f"STATUS:{c['status']}",
                f"PROGRESS:{c['progress']}",
                f"AGENTS:{c['agent_count']}",
            ]
            if c["runner_status"]:
                parts.append(f"RUNNER:{c['runner_status']}")
            print(" ".join(parts))
    else:
        # Calculate column widths
        id_w = max(len(c["id"]) for c in crews)
        id_w = max(id_w, 2)
        name_w = max(len(c["name"]) for c in crews)
        name_w = max(name_w, 4)
        status_w = max(len(c["status"]) for c in crews)
        status_w = max(status_w, 6)

        print(f"  {'ID':<{id_w}}  {'Name':<{name_w}}  {'Status':<{status_w}}  {'Prog':>5}  Agents  Runner")
        print(f"  {'-' * id_w}  {'-' * name_w}  {'-' * status_w}  -----  ------  ------")
        for c in crews:
            runner = c["runner_status"] or "N/A"
            prog_str = f"{c['progress']}%"
            print(f"  {c['id']:<{id_w}}  {c['name']:<{name_w}}  {c['status']:<{status_w}}  {prog_str:>5}  {c['agent_count']:>6}  {runner}")

    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AgentCrew reporting CLI",
        prog="ait crew report",
    )
    parser.add_argument("--batch", action="store_true", help="Structured output for scripting")

    subparsers = parser.add_subparsers(dest="command")

    sp_summary = subparsers.add_parser("summary", help="Crew overview with agent statuses")
    sp_summary.add_argument("--crew", required=True, help="Crew ID")
    sp_summary.add_argument("--group", help="Filter to agents in this group")

    sp_detail = subparsers.add_parser("detail", help="Detailed agent report")
    sp_detail.add_argument("--crew", required=True, help="Crew ID")
    sp_detail.add_argument("--agent", required=True, help="Agent name")

    sp_output = subparsers.add_parser("output", help="Aggregate agent outputs")
    sp_output.add_argument("--crew", required=True, help="Crew ID")
    sp_output.add_argument("--group", help="Filter to agents in this group")

    subparsers.add_parser("list", help="List all agentcrews")

    args = parser.parse_args()
    batch = args.batch

    if args.command == "summary":
        return cmd_summary(args.crew, batch, getattr(args, "group", None))
    elif args.command == "detail":
        return cmd_detail(args.crew, args.agent, batch)
    elif args.command == "output":
        return cmd_output(args.crew, batch, getattr(args, "group", None))
    elif args.command == "list":
        return cmd_list(batch)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
