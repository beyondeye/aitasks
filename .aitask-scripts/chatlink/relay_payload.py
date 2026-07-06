"""relay_payload — agent-side task-payload writer for the Q&A relay.

Runs inside the spawned (sandboxed) agent as its LAST relay act: builds the
task-creation payload (contract 7), validates it via the shared
:class:`chatlink.relay.TaskPayload` schema, and atomically writes
``payload.json`` into the session spool. The producer-side validation is
shape-strict but repo-agnostic — the gateway (t1120_6) re-validates from the
same dataclass and layers repo allowlists (``task_types.txt`` /
``labels.txt``) plus control-char stripping on top.

Contract: **stdlib-only** (imports only ``chatlink.relay``); the agent never
creates the task and never touches git — the gateway commits.

Output protocol (stdout):
    PAYLOAD_WRITTEN:<path>    on success (exit 0)
    ERROR:<reason>            on stderr for usage/validation errors (exit 2);
                              nothing is written on failure.

Usage (normally via the ``aitask_relay_payload.sh`` wrapper):
    python3 -m chatlink.relay_payload --relay-dir <session_dir> \
        --name fix_login_timeout --title "Fix login timeout" \
        --priority high --effort medium --issue-type bug \
        --labels auth,backend --description-file /tmp/desc.md

``session_id`` is derived from the session directory name (contract 1 —
the dir name IS the session id); ``--description-file -`` reads stdin.

Spec: ``aidocs/chat/qa_relay_protocol.md`` §Task payload.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from chatlink.relay import RelayError, SessionDir, TaskPayload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="relay_payload",
        description="Validate and write the final task payload to the "
                    "chatlink relay spool.")
    p.add_argument("--relay-dir", required=True,
                   help="the relay SESSION directory (bind-mounted in sandbox)")
    p.add_argument("--name", required=True,
                   help="task name slug ([a-z0-9_], ≤ 64)")
    p.add_argument("--title", required=True, help="task title (≤ 120 chars)")
    p.add_argument("--priority", required=True,
                   choices=("high", "medium", "low"))
    p.add_argument("--effort", required=True,
                   choices=("high", "medium", "low"))
    p.add_argument("--issue-type", required=True,
                   help="issue type slug (gateway checks it against "
                        "task_types.txt)")
    p.add_argument("--labels", default="",
                   help="comma-separated label slugs (may be empty)")
    p.add_argument("--description-file", required=True,
                   help="path to the description markdown ('-' for stdin)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    session_path = Path(args.relay_dir)
    if not session_path.is_dir():
        print(f"ERROR:relay dir does not exist: {session_path}",
              file=sys.stderr)
        return 2

    if args.description_file == "-":
        description = sys.stdin.read()
    else:
        try:
            description = Path(args.description_file).read_text()
        except OSError as exc:
            print(f"ERROR:cannot read description file: {exc}",
                  file=sys.stderr)
            return 2

    labels = [l for l in (s.strip() for s in args.labels.split(",")) if l]

    session = SessionDir(session_path)
    try:
        payload = TaskPayload(
            session_id=session.session_id,
            name=args.name,
            title=args.title,
            priority=args.priority,
            effort=args.effort,
            issue_type=args.issue_type,
            labels=labels,
            description=description,
        )
        payload.validate()
        session.write_payload(payload.to_dict())
    except RelayError as exc:
        print(f"ERROR:{exc}", file=sys.stderr)
        return 2

    print(f"PAYLOAD_WRITTEN:{session.path / 'payload.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
