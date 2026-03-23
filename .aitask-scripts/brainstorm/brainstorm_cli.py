"""CLI entry point for brainstorm session management.

Provides subcommands for init, status, list, finalize, archive, and exists.
Called by bash wrapper scripts (aitask_brainstorm_*.sh).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Allow importing sibling packages
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brainstorm.brainstorm_session import (  # noqa: E402
    archive_session,
    crew_worktree,
    delete_session,
    finalize_session,
    init_session,
    list_sessions,
    load_session,
    save_session,
    session_exists,
)
from brainstorm.brainstorm_dag import (  # noqa: E402
    get_head,
    list_nodes,
)
from agentcrew.agentcrew_utils import read_yaml, write_yaml  # noqa: E402


def cmd_init(args: argparse.Namespace) -> None:
    """Initialize a brainstorm session in an existing crew worktree."""
    spec = ""
    if args.spec_file:
        spec = Path(args.spec_file).read_text(encoding="utf-8")

    wt = init_session(
        task_num=args.task_num,
        task_file=args.task_file,
        user_email=args.email or "",
        initial_spec=spec,
    )
    print(f"SESSION_PATH:{wt}")


def cmd_status(args: argparse.Namespace) -> None:
    """Display session status details."""
    if not session_exists(args.task_num):
        print(f"ERROR:No brainstorm session for task {args.task_num}", file=sys.stderr)
        sys.exit(1)

    session = load_session(args.task_num)
    wt = crew_worktree(args.task_num)
    head = get_head(wt)
    nodes = list_nodes(wt)

    print(f"task_id: {session.get('task_id', args.task_num)}")
    print(f"status: {session.get('status', 'unknown')}")
    print(f"crew_id: {session.get('crew_id', '')}")
    print(f"head: {head or '(none)'}")
    print(f"nodes: {len(nodes)}")
    print(f"created_at: {session.get('created_at', '')}")
    print(f"updated_at: {session.get('updated_at', '')}")
    print(f"created_by: {session.get('created_by', '')}")


def cmd_list(args: argparse.Namespace) -> None:
    """List all brainstorm sessions."""
    sessions = list_sessions()
    if not sessions:
        print("No brainstorm sessions found.")
        return

    # Header
    print(f"{'TASK':<8} {'STATUS':<12} {'HEAD':<10} {'NODES':<6} {'UPDATED'}")
    print("-" * 55)
    for s in sessions:
        task_num = s.get("task_num", "?")
        status = s.get("status", "?")
        wt = crew_worktree(task_num)
        head = get_head(wt) if wt.is_dir() else None
        nodes = list_nodes(wt) if wt.is_dir() else []
        updated = s.get("updated_at", "")
        print(f"{task_num:<8} {status:<12} {head or '(none)':<10} {len(nodes):<6} {updated}")


def cmd_finalize(args: argparse.Namespace) -> None:
    """Copy HEAD node's plan to aiplans/ and mark session completed."""
    if not session_exists(args.task_num):
        print(f"ERROR:No brainstorm session for task {args.task_num}", file=sys.stderr)
        sys.exit(1)

    dest = finalize_session(args.task_num)
    print(f"PLAN:{dest}")


def cmd_archive(args: argparse.Namespace) -> None:
    """Mark session as archived and set crew status to Completed."""
    if not session_exists(args.task_num):
        print(f"ERROR:No brainstorm session for task {args.task_num}", file=sys.stderr)
        sys.exit(1)

    archive_session(args.task_num)

    # Also set crew status to Completed so crew cleanup can process it
    wt = crew_worktree(args.task_num)
    crew_status_path = wt / "_crew_status.yaml"
    if crew_status_path.is_file():
        data = read_yaml(str(crew_status_path))
        data["status"] = "Completed"
        write_yaml(str(crew_status_path), data)

    print(f"ARCHIVED:{args.task_num}")


def cmd_delete(args: argparse.Namespace) -> None:
    """Delete a brainstorm session entirely."""
    if not session_exists(args.task_num):
        print(f"ERROR:No brainstorm session for task {args.task_num}", file=sys.stderr)
        sys.exit(1)

    delete_session(args.task_num)
    print(f"DELETED:{args.task_num}")


def cmd_exists(args: argparse.Namespace) -> None:
    """Check if a brainstorm session exists."""
    if session_exists(args.task_num):
        print("EXISTS")
    else:
        print("NOT_EXISTS")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="brainstorm_cli",
        description="Brainstorm session management CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Initialize a brainstorm session")
    p_init.add_argument("--task-num", required=True, help="Task number")
    p_init.add_argument("--task-file", required=True, help="Path to task file")
    p_init.add_argument("--email", default="", help="User email")
    p_init.add_argument("--spec-file", default="", help="Path to file with initial spec content")
    p_init.set_defaults(func=cmd_init)

    # status
    p_status = subparsers.add_parser("status", help="Show session status")
    p_status.add_argument("--task-num", required=True, help="Task number")
    p_status.set_defaults(func=cmd_status)

    # list
    p_list = subparsers.add_parser("list", help="List all sessions")
    p_list.set_defaults(func=cmd_list)

    # finalize
    p_fin = subparsers.add_parser("finalize", help="Copy HEAD plan to aiplans/")
    p_fin.add_argument("--task-num", required=True, help="Task number")
    p_fin.set_defaults(func=cmd_finalize)

    # archive
    p_arch = subparsers.add_parser("archive", help="Mark session archived")
    p_arch.add_argument("--task-num", required=True, help="Task number")
    p_arch.set_defaults(func=cmd_archive)

    # delete
    p_del = subparsers.add_parser("delete", help="Delete session entirely")
    p_del.add_argument("--task-num", required=True, help="Task number")
    p_del.set_defaults(func=cmd_delete)

    # exists
    p_exists = subparsers.add_parser("exists", help="Check if session exists")
    p_exists.add_argument("--task-num", required=True, help="Task number")
    p_exists.set_defaults(func=cmd_exists)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
