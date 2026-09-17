"""CLI entry point for brainstorm session management.

Provides subcommands for init, status, list, finalize, archive, delete, exists
and paths (read-only id -> path resolver). Called by bash wrapper scripts
(aitask_brainstorm_*.sh).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

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
    UMBRELLA_SUBGRAPH,
    get_head,
    get_node_ancestors,
    is_safe_node_id,
    list_nodes,
    node_parents_raw,
    read_node_safe,
)
from brainstorm.brainstorm_op_refs import OpDataRef, file_for_ref  # noqa: E402
from agentcrew.agentcrew_utils import read_yaml, write_yaml  # noqa: E402


def cmd_init(args: argparse.Namespace) -> None:
    """Initialize a brainstorm session in an existing crew worktree."""
    spec = ""
    if args.spec_file:
        spec = Path(args.spec_file).read_text(encoding="utf-8")

    proposal_file = args.proposal_file or None

    wt = init_session(
        task_num=args.task_num,
        task_file=args.task_file,
        user_email=args.email or "",
        initial_spec=spec,
        initial_proposal_file=proposal_file,
    )
    print(f"SESSION_PATH:{wt}")

    if proposal_file:
        from brainstorm.brainstorm_crew import register_initializer
        from agentcrew.agentcrew_runner_control import start_runner

        crew_id = f"brainstorm-{args.task_num}"
        agent_name = register_initializer(
            session_dir=wt,
            crew_id=crew_id,
            imported_path=str(Path(proposal_file).resolve()),
            task_file=args.task_file,
            group_name="bootstrap",
            launch_mode="interactive",
        )
        print(f"INITIALIZER_AGENT:{agent_name}")

        if start_runner(crew_id):
            print(f"RUNNER_STARTED:{crew_id}")
        else:
            print(f"RUNNER_START_FAILED:{crew_id}", file=sys.stderr)


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
    """Export HEAD node's proposal to aiplans/ and mark session completed."""
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
        data["progress"] = 100
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


# --- paths: read-only id -> path resolver ------------------------------------
#
# Output grammar (one record per line; every resolution outcome exits 0, a
# malformed task num / node id exits 2 before any stdout):
#   SESSION_PATH:<path>|NOT_FOUND
#   TASK_FILE:<path>|NOT_FOUND|INVALID
#   NODE:<id>|PROPOSAL:<path|NOT_FOUND>|META:<path|NOT_FOUND>|PARENTS:<tokens>
#   ANCESTOR:<node>|<token>|DEPTH:<n>|MODULE:<token>|PARENTS:<tokens>|PROPOSAL:<path|NOT_FOUND>
# A token is a safe node id or a "!"-prefixed sentinel (!INVALID, !MISSING);
# <tokens> is a comma-joined list of tokens. No YAML-derived value is emitted
# unless it passes its field's charset, so no field can carry "|", "," or a
# newline.

_TASK_NUM_RE = re.compile(r"([0-9]+)(?:_([0-9]+))?")
_PATH_RE = re.compile(r"[A-Za-z0-9_./-]+")
_SLUG = r"[A-Za-z0-9_-]+"


def _tok(value: object) -> str:
    return value if is_safe_node_id(value) else "!INVALID"  # type: ignore[return-value]


def _tokens(values: list | None) -> str:
    return ",".join(_tok(v) for v in values or [])


def _path(path: object) -> str:
    text = str(path)
    if (
        _PATH_RE.fullmatch(text)
        and not text.startswith("/")
        and ".." not in text.split("/")
    ):
        return text
    return "INVALID"


def _existing(path: Path) -> str:
    return _path(path) if path.is_file() else "NOT_FOUND"


def _task_file_allowed(task_num: str, value: object) -> bool:
    """True if ``value`` is exactly the shape ``aitask_query_files.sh resolve``
    writes for ``task_num``: its own active task file, nothing else."""
    if not isinstance(value, str):
        return False
    m = _TASK_NUM_RE.fullmatch(task_num)
    if m is None:
        return False
    parent, child = m.group(1), m.group(2)
    if child is None:
        pattern = rf"aitasks/t{re.escape(parent)}_{_SLUG}\.md"
    else:
        pattern = (
            rf"aitasks/t{re.escape(parent)}/"
            rf"t{re.escape(parent)}_{re.escape(child)}_{_SLUG}\.md"
        )
    return re.fullmatch(pattern, value) is not None


def _task_file_field(task_num: str) -> str:
    try:
        value = load_session(task_num).get("task_file")
    except (OSError, ValueError, yaml.YAMLError):
        return "NOT_FOUND"
    if not _task_file_allowed(task_num, value):
        return "INVALID"
    return value if Path(value).is_file() else "NOT_FOUND"  # type: ignore[arg-type]


def _module_token(data: dict | None) -> str:
    if data is None:
        return "!MISSING"
    label = data.get("module_label")
    if not label:
        return UMBRELLA_SUBGRAPH
    return _tok(label)


def cmd_paths(args: argparse.Namespace) -> None:
    """Resolve a session's task file and node proposal/metadata paths (read-only)."""
    task_num = args.task_num
    if _TASK_NUM_RE.fullmatch(task_num) is None:
        print(f"Error: invalid task number: {task_num!r}", file=sys.stderr)
        sys.exit(2)
    for nid in args.node_ids:
        if not is_safe_node_id(nid):
            print(f"Error: invalid node id: {nid!r}", file=sys.stderr)
            sys.exit(2)

    if not session_exists(task_num):
        print("SESSION_PATH:NOT_FOUND")
        return
    session = crew_worktree(task_num)
    print(f"SESSION_PATH:{_path(session)}")
    print(f"TASK_FILE:{_task_file_field(task_num)}")

    node_ids = args.node_ids or [n for n in list_nodes(session) if is_safe_node_id(n)]
    for nid in node_ids:
        data = read_node_safe(session, nid)
        proposal = _existing(file_for_ref(session, OpDataRef("node_proposal", nid)))
        meta = _existing(file_for_ref(session, OpDataRef("node_metadata", nid)))
        print(
            f"NODE:{nid}|PROPOSAL:{proposal}|META:{meta}"
            f"|PARENTS:{_tokens(node_parents_raw(data))}"
        )
        if not args.lineage:
            continue
        for ancestor, depth in get_node_ancestors(session, nid):
            if not is_safe_node_id(ancestor):
                print(
                    f"ANCESTOR:{nid}|!INVALID|DEPTH:{depth}|MODULE:!MISSING"
                    f"|PARENTS:|PROPOSAL:NOT_FOUND"
                )
                continue
            adata = read_node_safe(session, ancestor)
            aproposal = _existing(
                file_for_ref(session, OpDataRef("node_proposal", ancestor))  # type: ignore[arg-type]
            )
            print(
                f"ANCESTOR:{nid}|{ancestor}|DEPTH:{depth}"
                f"|MODULE:{_module_token(adata)}"
                f"|PARENTS:{_tokens(node_parents_raw(adata))}"
                f"|PROPOSAL:{aproposal}"
            )


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
    p_init.add_argument(
        "--proposal-file",
        default="",
        help="Optional markdown file to use as initial proposal (analyzed by initializer agent)",
    )
    p_init.set_defaults(func=cmd_init)

    # status
    p_status = subparsers.add_parser("status", help="Show session status")
    p_status.add_argument("--task-num", required=True, help="Task number")
    p_status.set_defaults(func=cmd_status)

    # list
    p_list = subparsers.add_parser("list", help="List all sessions")
    p_list.set_defaults(func=cmd_list)

    # finalize
    p_fin = subparsers.add_parser("finalize", help="Export HEAD proposal to aiplans/")
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

    # paths (read-only resolver for the brainstorm-discuss skill)
    p_paths = subparsers.add_parser(
        "paths", help="Resolve session, task file and node paths (read-only)"
    )
    p_paths.add_argument("--task-num", required=True, help="Task number")
    p_paths.add_argument(
        "--lineage", action="store_true", help="Also emit every ancestor of each node"
    )
    p_paths.add_argument("node_ids", nargs="*", help="Node ids (default: all nodes)")
    p_paths.set_defaults(func=cmd_paths)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
